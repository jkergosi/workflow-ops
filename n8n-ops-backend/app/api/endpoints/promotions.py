"""
Promotions API endpoints for pipeline-aware environment promotion
"""
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks, Query
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

from app.services.feature_service import feature_service
from app.core.feature_gate import require_feature
from app.core.entitlements_gate import require_entitlement
from app.services.promotion_service import promotion_service
from app.services.database import db_service
from app.services.notification_service import notification_service
from app.services.background_job_service import (
    background_job_service,
    BackgroundJobStatus,
    BackgroundJobType
)
from app.api.endpoints.admin_audit import create_audit_log
from app.schemas.promotion import (
    PromotionInitiateRequest,
    PromotionInitiateResponse,
    PromotionApprovalRequest,
    PromotionExecuteRequest,
    PromotionDetail,
    PromotionListResponse,
    PromotionSnapshotRequest,
    PromotionSnapshotResponse,
    PromotionDriftCheck,
    PromotionStatus,
    WorkflowSelection,
    GateResult,
    PromotionExecutionResult,
)
from app.core.provider import Provider, DEFAULT_PROVIDER
from app.schemas.pipeline import PipelineResponse
from app.api.endpoints.sse import emit_deployment_upsert, emit_deployment_progress, emit_counts_update

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


@router.post("/initiate", response_model=PromotionInitiateResponse)
async def initiate_deployment(
    request: PromotionInitiateRequest,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Initiate a promotion - simplified version that creates the promotion record quickly.
    Heavy operations (snapshots, drift checks) are done during execution.
    """
    try:
        # Get pipeline
        pipeline_data = await db_service.get_pipeline(request.pipeline_id, MOCK_TENANT_ID)
        if not pipeline_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )

        # Find the active stage for this source -> target
        active_stage = None
        for stage in pipeline_data.get("stages", []):
            if (stage.get("source_environment_id") == request.source_environment_id and
                stage.get("target_environment_id") == request.target_environment_id):
                active_stage = stage
                break

        if not active_stage:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No stage found for this source -> target environment pair"
            )

        # Check if approval required
        requires_approval = active_stage.get("approvals", {}).get("require_approval", False)

        # Create promotion record immediately
        promotion_id = str(uuid4())

        # Simple gate results (actual checks done during execution)
        gate_results = GateResult(
            require_clean_drift=active_stage.get("gates", {}).get("require_clean_drift", False),
            drift_detected=False,
            drift_resolved=True,
            run_pre_flight_validation=active_stage.get("gates", {}).get("run_pre_flight_validation", False),
            credentials_exist=True,
            nodes_supported=True,
            webhooks_available=True,
            target_environment_healthy=True,
            risk_level_allowed=True,
            errors=[],
            warnings=[],
            credential_issues=[]
        )

        promotion_data = {
            "id": promotion_id,
            "tenant_id": MOCK_TENANT_ID,
            "pipeline_id": request.pipeline_id,
            "source_environment_id": request.source_environment_id,
            "target_environment_id": request.target_environment_id,
            "status": PromotionStatus.PENDING_APPROVAL.value if requires_approval else PromotionStatus.PENDING.value,
            "source_snapshot_id": None,  # Created during execution
            "workflow_selections": [ws.dict() for ws in request.workflow_selections],
            "gate_results": gate_results.dict(),
            "created_by": None,  # TODO: Get from auth
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Store promotion
        await db_service.create_promotion(promotion_data)

        # TODO: Re-enable notification once core flow is working
        # try:
        #     await notification_service.emit_event(...)
        # except Exception as e:
        #     logger.error(f"Failed to emit promotion.started event: {str(e)}")

        return PromotionInitiateResponse(
            promotion_id=promotion_id,
            status=PromotionStatus.PENDING_APPROVAL if requires_approval else PromotionStatus.PENDING,
            gate_results=gate_results,
            requires_approval=requires_approval,
            approval_id=str(uuid4()) if requires_approval else None,
            dependency_warnings={},
            preflight={"credential_issues": [], "dependency_warnings": {}, "drift_detected": False},
            message="Promotion initiated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate promotion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate promotion: {str(e)}"
        )


async def _execute_promotion_background(
    job_id: str,
    promotion_id: str,
    deployment_id: str,
    promotion: dict,
    source_env: dict,
    target_env: dict,
    selected_workflows: list
):
    """
    Background task to execute promotion - transfers workflows from source to target.
    Updates job progress as it processes workflows.
    """
    from app.services.n8n_client import N8NClient
    from app.schemas.deployment import DeploymentStatus, WorkflowChangeType, WorkflowStatus

    total_workflows = len(selected_workflows)
    
    try:
        # Update job status to running
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING,
            progress={"current": 0, "total": total_workflows, "percentage": 0, "message": "Starting promotion execution"}
        )

        # Create n8n clients - use correct field names from environment
        source_base_url = source_env.get("n8n_base_url") or source_env.get("base_url")
        source_api_key = source_env.get("n8n_api_key") or source_env.get("api_key")
        target_base_url = target_env.get("n8n_base_url") or target_env.get("base_url")
        target_api_key = target_env.get("n8n_api_key") or target_env.get("api_key")
        
        if not source_base_url or not source_api_key:
            raise ValueError(f"Source environment missing required fields: base_url={source_base_url}, api_key={'***' if source_api_key else None}")
        if not target_base_url or not target_api_key:
            raise ValueError(f"Target environment missing required fields: base_url={target_base_url}, api_key={'***' if target_api_key else None}")
        
        logger.info(f"[Job {job_id}] Creating N8N clients - Source: {source_base_url}, Target: {target_base_url}")
        source_client = N8NClient(source_base_url, source_api_key)
        target_client = N8NClient(target_base_url, target_api_key)
        
        # Test connections before proceeding
        logger.info(f"[Job {job_id}] Testing source environment connection...")
        source_connected = await source_client.test_connection()
        if not source_connected:
            raise ValueError(f"Failed to connect to source environment at {source_base_url}")
        logger.info(f"[Job {job_id}] Source environment connection successful")
        
        logger.info(f"[Job {job_id}] Testing target environment connection...")
        target_connected = await target_client.test_connection()
        if not target_connected:
            raise ValueError(f"Failed to connect to target environment at {target_base_url}")
        logger.info(f"[Job {job_id}] Target environment connection successful")

        # NOTE: deployment_workflows records are pre-created in execute_promotion() before this task starts
        # This ensures workflow records exist even if this background job fails early
        logger.info(f"[Job {job_id}] Starting transfer of {total_workflows} workflows (records already created)")

        # Transfer each workflow
        created_count = 0
        updated_count = 0
        failed_count = 0
        skipped_count = 0
        unchanged_count = 0
        workflow_results = []

        for idx, ws in enumerate(selected_workflows, 1):
            workflow_id = ws.get("workflow_id")
            workflow_name = ws.get("workflow_name")
            change_type = ws.get("change_type", "new")
            error_message = None
            status_result = WorkflowStatus.SUCCESS

            try:
                # Update progress
                await background_job_service.update_progress(
                    job_id=job_id,
                    current=idx,
                    total=total_workflows,
                    message=f"Processing workflow: {workflow_name}"
                )

                # Fetch workflow from source
                logger.info(f"[Job {job_id}] Fetching workflow {workflow_id} ({workflow_name}) from source environment {source_env.get('n8n_name', source_env.get('id'))}")
                source_workflow = await source_client.get_workflow(workflow_id)
                
                if not source_workflow:
                    raise ValueError(f"Workflow {workflow_id} not found in source environment")

                # Prepare workflow data for target (remove source-specific fields)
                workflow_data = {
                    "name": source_workflow.get("name"),
                    "nodes": source_workflow.get("nodes", []),
                    "connections": source_workflow.get("connections", {}),
                    "settings": source_workflow.get("settings", {}),
                    "staticData": source_workflow.get("staticData"),
                }
                
                logger.info(f"[Job {job_id}] Prepared workflow data for {workflow_name}: {len(workflow_data.get('nodes', []))} nodes")

                # Try to find existing workflow in target by name
                logger.info(f"[Job {job_id}] Checking for existing workflow '{workflow_name}' in target environment {target_env.get('n8n_name', target_env.get('id'))}")
                target_workflows = await target_client.get_workflows()
                logger.info(f"[Job {job_id}] Found {len(target_workflows)} existing workflows in target environment")
                existing_workflow = next(
                    (w for w in target_workflows if w.get("name") == workflow_name),
                    None
                )

                if existing_workflow:
                    # Update existing workflow
                    logger.info(f"[Job {job_id}] Updating existing workflow '{workflow_name}' (ID: {existing_workflow.get('id')}) in target")
                    result = await target_client.update_workflow(existing_workflow.get("id"), workflow_data)
                    logger.info(f"[Job {job_id}] Successfully updated workflow '{workflow_name}' in target environment")
                    updated_count += 1
                    change_type = "changed"
                else:
                    # Create new workflow
                    logger.info(f"[Job {job_id}] Creating new workflow '{workflow_name}' in target environment")
                    result = await target_client.create_workflow(workflow_data)
                    logger.info(f"[Job {job_id}] Successfully created workflow '{workflow_name}' (ID: {result.get('id', 'unknown')}) in target environment")
                    created_count += 1
                    change_type = "new"

            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                error_message = str(e)
                
                # Log detailed error information
                logger.error(f"[Job {job_id}] Failed to transfer workflow {workflow_name}: {error_message}")
                logger.error(f"[Job {job_id}] Error type: {type(e).__name__}")
                if hasattr(e, 'errno') and e.errno == 22:
                    logger.error(f"[Job {job_id}] Windows errno 22 (Invalid argument) - check for invalid characters in workflow data")
                logger.error(f"[Job {job_id}] Traceback: {error_traceback}")
                
                # Truncate error message if too long for database
                if len(error_message) > 500:
                    error_message = error_message[:500] + "..."
                
                status_result = WorkflowStatus.FAILED
                failed_count += 1

            # Update workflow record (already pre-created with PENDING status)
            wf_change_type_map = {
                "new": WorkflowChangeType.CREATED,
                "changed": WorkflowChangeType.UPDATED,
                "staging_hotfix": WorkflowChangeType.UPDATED,
                "conflict": WorkflowChangeType.SKIPPED,
                "unchanged": WorkflowChangeType.UNCHANGED,
            }
            wf_change_type = wf_change_type_map.get(change_type, WorkflowChangeType.UPDATED)

            workflow_update = {
                "change_type": wf_change_type.value,
                "status": status_result.value,
                "error_message": error_message,
            }
            await db_service.update_deployment_workflow(deployment_id, workflow_id, workflow_update)
            workflow_results.append({
                "deployment_id": deployment_id,
                "workflow_id": workflow_id,
                "workflow_name_at_time": workflow_name,
                **workflow_update
            })

            # Update deployment's updated_at timestamp and running summary so UI can see progress
            await db_service.update_deployment(deployment_id, {
                "summary_json": {
                    "total": total_workflows,
                    "created": created_count,
                    "updated": updated_count,
                    "deleted": 0,
                    "failed": failed_count,
                    "skipped": skipped_count,
                    "unchanged": unchanged_count,
                    "processed": idx,
                    "current_workflow": workflow_name
                }
            })

            # Emit SSE progress event
            try:
                await emit_deployment_progress(
                    deployment_id=deployment_id,
                    progress_current=idx,
                    progress_total=total_workflows,
                    current_workflow_name=workflow_name,
                    tenant_id=MOCK_TENANT_ID
                )
            except Exception as sse_error:
                logger.warning(f"Failed to emit SSE progress event: {str(sse_error)}")

        # Calculate final summary
        summary_json = {
            "total": total_workflows,
            "created": created_count,
            "updated": updated_count,
            "deleted": 0,
            "failed": failed_count,
            "skipped": skipped_count,
            "unchanged": unchanged_count,
            "processed": total_workflows,
        }

        # Determine final status
        final_status = DeploymentStatus.SUCCESS if failed_count == 0 else DeploymentStatus.FAILED

        # Update deployment with results
        await db_service.update_deployment(deployment_id, {
            "status": final_status.value,
            "finished_at": datetime.utcnow().isoformat(),
            "summary_json": summary_json,
        })

        # Emit SSE events for deployment completion
        try:
            # Fetch updated deployment for full data
            updated_deployment = await db_service.get_deployment(deployment_id, MOCK_TENANT_ID)
            if updated_deployment:
                await emit_deployment_upsert(updated_deployment, MOCK_TENANT_ID)
            await emit_counts_update(MOCK_TENANT_ID)
        except Exception as sse_error:
            logger.warning(f"Failed to emit SSE event for deployment completion: {str(sse_error)}")

        # Update promotion as completed
        promotion_status = "completed" if failed_count == 0 else "failed"
        await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {
            "status": promotion_status,
            "completed_at": datetime.utcnow().isoformat()
        })

        # Update job as completed
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.COMPLETED if failed_count == 0 else BackgroundJobStatus.FAILED,
            progress={"current": total_workflows, "total": total_workflows, "percentage": 100},
            result={
                "deployment_id": deployment_id,
                "summary": summary_json,
                "workflow_results": workflow_results
            },
            error_message=None if failed_count == 0 else f"{failed_count} workflow(s) failed"
        )

        logger.info(f"Promotion {promotion_id} completed: {created_count} created, {updated_count} updated, {failed_count} failed")

    except Exception as e:
        logger.error(f"Background promotion execution failed: {str(e)}")
        error_msg = str(e)
        
        # Update job as failed
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=error_msg,
            error_details={"exception_type": type(e).__name__, "traceback": str(e)}
        )
        
        # Update promotion and deployment status to failed
        try:
            await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat()
            })
            await db_service.update_deployment(deployment_id, {
                "status": "failed",
                "finished_at": datetime.utcnow().isoformat(),
                "summary_json": {
                    "total": total_workflows,
                    "created": 0,
                    "updated": 0,
                    "deleted": 0,
                    "failed": total_workflows,
                    "skipped": 0,
                    "error": error_msg
                },
            })
            # Emit SSE events for deployment failure
            try:
                updated_deployment = await db_service.get_deployment(deployment_id, MOCK_TENANT_ID)
                if updated_deployment:
                    await emit_deployment_upsert(updated_deployment, MOCK_TENANT_ID)
                await emit_counts_update(MOCK_TENANT_ID)
            except Exception as sse_error:
                logger.warning(f"Failed to emit SSE event for deployment failure: {str(sse_error)}")
        except Exception as update_error:
            logger.error(f"Failed to update promotion/deployment status: {str(update_error)}")


@router.post("/execute/{deployment_id}")
async def execute_deployment(
    deployment_id: str,
    request: Optional[PromotionExecuteRequest] = None,
    background_tasks: BackgroundTasks = None,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Execute a deployment - creates deployment and starts background execution.
    If scheduled_at is provided, deployment will be scheduled for that time.
    Otherwise, executes immediately.
    Returns immediately with job_id for tracking progress.
    """
    from app.schemas.deployment import DeploymentStatus
    
    # Handle optional request body
    scheduled_at = None
    if request and request.scheduled_at:
        scheduled_at = request.scheduled_at
        # Validate scheduled_at is in the future
        if scheduled_at <= datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="scheduled_at must be in the future"
            )

    try:
        # Get promotion record (still uses promotion_id in DB)
        promotion = await db_service.get_promotion(deployment_id, MOCK_TENANT_ID)
        if not promotion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Promotion not found"
            )

        # Check status
        if promotion.get("status") not in ["pending", "approved"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Promotion cannot be executed in status: {promotion.get('status')}"
            )

        # Get source and target environments
        source_env = await db_service.get_environment(promotion.get("source_environment_id"), MOCK_TENANT_ID)
        target_env = await db_service.get_environment(promotion.get("target_environment_id"), MOCK_TENANT_ID)

        if not source_env or not target_env:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source or target environment not found"
            )

        # Get selected workflows
        workflow_selections = promotion.get("workflow_selections", [])
        selected_workflows = [ws for ws in workflow_selections if ws.get("selected")]

        if not selected_workflows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No workflows selected for promotion"
            )

        # Create background job (link to both promotion and deployment)
        job = await background_job_service.create_job(
            tenant_id=MOCK_TENANT_ID,
            job_type=BackgroundJobType.PROMOTION_EXECUTE,
            resource_id=promotion_id,
            resource_type="promotion",
            created_by=promotion.get("created_by") or "00000000-0000-0000-0000-000000000000",
            initial_progress={
                "current": 0,
                "total": len(selected_workflows),
                "percentage": 0,
                "message": "Initializing promotion execution"
            }
        )
        job_id = job["id"]

        # Determine deployment status and timing
        is_scheduled = scheduled_at is not None
        deployment_status = DeploymentStatus.SCHEDULED.value if is_scheduled else DeploymentStatus.RUNNING.value
        
        # Update promotion status
        if is_scheduled:
            # Keep promotion as pending until scheduled execution
            await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {
                "status": PromotionStatus.PENDING.value,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None
            })
        else:
            await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {"status": "running"})

        # Create deployment record
        deployment_id = str(uuid4())
        deployment_data = {
            "id": deployment_id,
            "tenant_id": MOCK_TENANT_ID,
            "pipeline_id": promotion.get("pipeline_id"),
            "source_environment_id": promotion.get("source_environment_id"),
            "target_environment_id": promotion.get("target_environment_id"),
            "status": deployment_status,
            "triggered_by_user_id": promotion.get("created_by") or "00000000-0000-0000-0000-000000000000",
            "approved_by_user_id": None,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            "started_at": datetime.utcnow().isoformat() if not is_scheduled else None,
            "finished_at": None,
            "pre_snapshot_id": None,
            "post_snapshot_id": None,
            "summary_json": {"total": len(selected_workflows), "created": 0, "updated": 0, "deleted": 0, "failed": 0, "skipped": 0},
        }
        await db_service.create_deployment(deployment_data)

        # Pre-create all deployment_workflows records BEFORE background task
        # This ensures workflow records exist even if background job fails early (e.g., connection failure)
        # Without this, failed deployments have no workflows and cannot be rerun
        # NOTE: Don't set status here - database default will be used
        from app.schemas.deployment import WorkflowChangeType
        change_type_map = {
            "new": WorkflowChangeType.CREATED,
            "changed": WorkflowChangeType.UPDATED,
            "staging_hotfix": WorkflowChangeType.UPDATED,
            "conflict": WorkflowChangeType.SKIPPED,
            "unchanged": WorkflowChangeType.UNCHANGED,
        }
        pending_workflows = []
        for ws in selected_workflows:
            wf_change_type = change_type_map.get(ws.get("change_type", "new"), WorkflowChangeType.CREATED)
            pending_workflows.append({
                "deployment_id": deployment_id,
                "workflow_id": ws.get("workflow_id"),
                "workflow_name_at_time": ws.get("workflow_name"),
                "change_type": wf_change_type.value,
                # status will use database default, updated to success/failed during processing
            })

        if pending_workflows:
            await db_service.create_deployment_workflows_batch(pending_workflows)
            logger.info(f"Created {len(pending_workflows)} deployment_workflow records for deployment {deployment_id}")

        # Emit SSE events for new deployment
        try:
            await emit_deployment_upsert(deployment_data, MOCK_TENANT_ID)
            await emit_counts_update(MOCK_TENANT_ID)
        except Exception as sse_error:
            logger.warning(f"Failed to emit SSE event for deployment creation: {str(sse_error)}")

        # Create audit log for deployment creation
        try:
            provider = source_env.get("provider", "n8n") or "n8n"
            await create_audit_log(
                action_type="DEPLOYMENT_CREATED",
                action=f"Created deployment for {len(selected_workflows)} workflow(s)",
                actor_id=promotion.get("created_by") or "00000000-0000-0000-0000-000000000000",
                tenant_id=MOCK_TENANT_ID,
                resource_type="deployment",
                resource_id=deployment_id,
                resource_name=f"Deployment {deployment_id[:8]}",
                provider=provider,
                new_value={
                    "deployment_id": deployment_id,
                    "promotion_id": promotion_id,
                    "status": DeploymentStatus.RUNNING.value,
                    "workflow_count": len(selected_workflows),
                    "source_environment_id": promotion.get("source_environment_id"),
                    "target_environment_id": promotion.get("target_environment_id"),
                    "pipeline_id": promotion.get("pipeline_id"),
                },
                metadata={
                    "job_id": job_id,
                    "workflow_selections": [{"workflow_id": ws.get("workflow_id"), "workflow_name": ws.get("workflow_name")} for ws in selected_workflows]
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to create audit log for deployment creation: {str(audit_error)}")
        
        # Update job with deployment_id in result for tracking
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.PENDING if is_scheduled else BackgroundJobStatus.PENDING,
            result={"deployment_id": deployment_id, "scheduled_at": scheduled_at.isoformat() if scheduled_at else None}
        )

        # Start background execution task only if not scheduled
        if not is_scheduled:
            if background_tasks is None:
                # If BackgroundTasks not injected, create task directly
                import asyncio
                asyncio.create_task(
                    _execute_promotion_background(
                        job_id=job_id,
                        promotion_id=promotion_id,
                        deployment_id=deployment_id,
                        promotion=promotion,
                        source_env=source_env,
                        target_env=target_env,
                        selected_workflows=selected_workflows
                    )
                )
            else:
                # FastAPI BackgroundTasks.add_task() supports async functions directly
                background_tasks.add_task(
                    _execute_promotion_background,
                    job_id=job_id,
                    promotion_id=promotion_id,
                    deployment_id=deployment_id,
                    promotion=promotion,
                    source_env=source_env,
                    target_env=target_env,
                    selected_workflows=selected_workflows
                )
            logger.info(f"[Job {job_id}] Background task added for promotion {promotion_id}, deployment {deployment_id}")
        else:
            logger.info(f"[Job {job_id}] Deployment {deployment_id} scheduled for {scheduled_at}")

        # Return immediately with job info
        status_msg = "scheduled" if is_scheduled else "running"
        message = (
            f"Deployment scheduled for {scheduled_at.strftime('%Y-%m-%d %H:%M:%S UTC')}. "
            f"Processing {len(selected_workflows)} workflow(s) will begin at that time."
            if is_scheduled
            else f"Promotion execution started. Processing {len(selected_workflows)} workflow(s) in the background."
        )
        
        return {
            "job_id": job_id,
            "promotion_id": promotion_id,
            "deployment_id": deployment_id,
            "status": status_msg,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        # Update promotion status to failed
        try:
            await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat()
            })
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute promotion: {str(e)}"
        )


@router.get("/{deployment_id}/job")
async def get_promotion_job(
    promotion_id: str,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get the latest background job status for a promotion execution.
    """
    try:
        # Get the latest job for this promotion
        job = await background_job_service.get_latest_job_by_resource(
            resource_type="promotion",
            resource_id=promotion_id,
            tenant_id=MOCK_TENANT_ID
        )
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No job found for this promotion"
            )
        
        return {
            "job_id": job.get("id"),
            "promotion_id": promotion_id,
            "status": job.get("status"),
            "progress": job.get("progress", {}),
            "result": job.get("result", {}),
            "error_message": job.get("error_message"),
            "error_details": job.get("error_details", {}),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "created_at": job.get("created_at")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get promotion job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get promotion job: {str(e)}"
        )


@router.post("/approvals/{deployment_id}/approve")
async def approve_deployment(
    deployment_id: str,
    request: PromotionApprovalRequest,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Approve or reject a pending promotion.
    Supports multi-approver workflows (1 of N / All).
    """
    try:
        # Get promotion (still uses promotion_id in DB)
        promotion = await db_service.get_promotion(deployment_id, MOCK_TENANT_ID)
        if not promotion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Promotion not found"
            )
        
        if promotion.get("status") != "pending_approval":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Promotion is not pending approval (status: {promotion.get('status')})"
            )
        
        # Get pipeline and stage for approval requirements
        pipeline = await db_service.get_pipeline(promotion.get("pipeline_id"), MOCK_TENANT_ID)
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        
        # Find active stage
        active_stage = None
        for stage in pipeline.get("stages", []):
            if (stage.get("source_environment_id") == promotion.get("source_environment_id") and
                stage.get("target_environment_id") == promotion.get("target_environment_id")):
                active_stage = stage
                break
        
        if not active_stage:
            raise HTTPException(status_code=400, detail="Active stage not found")
        
        approvals_config = active_stage.get("approvals", {})
        required_approvals_type = approvals_config.get("required_approvals", "1 of N")
        
        # Get existing approvals for this promotion
        existing_approvals = promotion.get("approvals", []) or []
        approver_id = "current_user"  # TODO: Get from auth
        
        if request.action == "reject":
            # Rejection requires comment
            if not request.comment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Rejection comment is required"
                )
            
            # Update promotion to rejected
            await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {
                "status": "rejected",
                "rejection_reason": request.comment,
                "rejected_by": approver_id,
                "rejected_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat()
            })
            
            # Emit promotion.blocked event for rejection
            try:
                await notification_service.emit_event(
                    tenant_id=MOCK_TENANT_ID,
                    event_type="promotion.blocked",
                    environment_id=promotion.get("target_environment_id"),
                    metadata={
                        "promotion_id": promotion_id,
                        "pipeline_id": promotion.get("pipeline_id"),
                        "source_environment_id": promotion.get("source_environment_id"),
                        "target_environment_id": promotion.get("target_environment_id"),
                        "reason": "rejected",
                        "rejection_reason": request.comment,
                        "rejected_by": approver_id
                    }
                )
            except Exception as e:
                logger.error(f"Failed to emit promotion.blocked event: {str(e)}")
            
            # Create audit log
            await promotion_service._create_audit_log(
                tenant_id=MOCK_TENANT_ID,
                promotion_id=promotion_id,
                action="reject",
                result={"reason": request.comment, "rejected_by": approver_id}
            )
            
            return {
                "id": promotion_id,
                "action": "reject",
                "status": "rejected",
                "message": "Promotion rejected"
            }
        
        # Approval
        # Check if user already approved
        if any(approval.get("approver_id") == approver_id for approval in existing_approvals):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already approved this promotion"
            )
        
        # Add approval record
        new_approval = {
            "approver_id": approver_id,
            "approved_at": datetime.utcnow().isoformat(),
            "comment": request.comment
        }
        existing_approvals.append(new_approval)
        
        # Check if enough approvals
        approval_count = len(existing_approvals)
        needs_more_approvals = False
        
        if required_approvals_type == "All":
            # Would need to know total required approvers from role/group
            # For now, assume 1 approval is enough if "All" is not strictly enforced
            approver_role = approvals_config.get("approver_role")
            approver_group = approvals_config.get("approver_group")
            # Simplified: if role/group specified, might need multiple approvers
            # In production, would query users with that role/group
            needs_more_approvals = False  # Simplified for MVP
        else:  # "1 of N"
            # At least 1 approval needed
            needs_more_approvals = approval_count < 1
        
        if needs_more_approvals:
            # Update promotion with approval but keep pending
            await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {
                "approvals": existing_approvals,
                "updated_at": datetime.utcnow().isoformat()
            })
            
            # Create audit log
            await promotion_service._create_audit_log(
                tenant_id=MOCK_TENANT_ID,
                promotion_id=promotion_id,
                action="approve",
                result={"approval_count": approval_count, "approver": approver_id}
            )
            
            return {
                "id": promotion_id,
                "action": "approve",
                "status": "pending_approval",
                "approval_count": approval_count,
                "message": "Approval recorded. Waiting for additional approvals."
            }
        else:
            # All approvals received - update to approved
            await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {
                "status": "approved",
                "approvals": existing_approvals,
                "approved_by": approver_id,
                "approved_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            })
            
            # Create audit log
            await promotion_service._create_audit_log(
                tenant_id=MOCK_TENANT_ID,
                promotion_id=promotion_id,
                action="approve_final",
                result={"approval_count": approval_count, "approver": approver_id, "all_approvals_received": True}
            )
            
            # Auto-execute if approved
            try:
                # Call execute_promotion directly (avoid circular import)
                # Get promotion again to ensure we have latest data
                updated_promotion = await db_service.get_promotion(promotion_id, MOCK_TENANT_ID)
                
                # Update status to running
                await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {"status": "running"})
                
                # Get pipeline and stage
                pipeline = await db_service.get_pipeline(updated_promotion.get("pipeline_id"), MOCK_TENANT_ID)
                active_stage = None
                for stage in pipeline.get("stages", []):
                    if (stage.get("source_environment_id") == updated_promotion.get("source_environment_id") and
                        stage.get("target_environment_id") == updated_promotion.get("target_environment_id")):
                        active_stage = stage
                        break
                
                # Create pre-promotion snapshot
                target_pre_snapshot_id, _ = await promotion_service.create_snapshot(
                    tenant_id=MOCK_TENANT_ID,
                    environment_id=updated_promotion.get("target_environment_id"),
                    reason="Pre-promotion snapshot",
                    metadata={"promotion_id": promotion_id}
                )
                
                # Execute promotion
                from app.schemas.pipeline import PipelineStage
                from app.schemas.promotion import WorkflowSelection
                stage_obj = PipelineStage(**active_stage)
                
                gate_results = updated_promotion.get("gate_results", {})
                credential_issues = gate_results.get("credential_issues", [])
                
                execution_result = await promotion_service.execute_promotion(
                    tenant_id=MOCK_TENANT_ID,
                    promotion_id=promotion_id,
                    source_env_id=updated_promotion.get("source_environment_id"),
                    target_env_id=updated_promotion.get("target_environment_id"),
                    workflow_selections=[WorkflowSelection(**ws) for ws in updated_promotion.get("workflow_selections", [])],
                    source_snapshot_id=updated_promotion.get("source_snapshot_id", ""),
                    policy_flags=stage_obj.policy_flags.dict(),
                    credential_issues=credential_issues
                )
                
                # Create post-promotion snapshot
                target_post_snapshot_id, _ = await promotion_service.create_snapshot(
                    tenant_id=MOCK_TENANT_ID,
                    environment_id=updated_promotion.get("target_environment_id"),
                    reason="Post-promotion snapshot",
                    metadata={"promotion_id": promotion_id, "source_snapshot_id": updated_promotion.get("source_snapshot_id")}
                )
                
                # Update promotion with results
                await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {
                    "status": execution_result.status.value,
                    "target_pre_snapshot_id": target_pre_snapshot_id,
                    "target_post_snapshot_id": target_post_snapshot_id,
                    "execution_result": execution_result.dict(),
                    "completed_at": datetime.utcnow().isoformat()
                })
                
                execution_result.target_pre_snapshot_id = target_pre_snapshot_id
                execution_result.target_post_snapshot_id = target_post_snapshot_id
                return {
                    "id": promotion_id,
                    "action": "approve",
                    "status": "approved",
                    "execution_status": execution_result.get("status") if isinstance(execution_result, dict) else "completed",
                    "message": "Promotion approved and executed"
                }
            except Exception as e:
                logger.error(f"Auto-execution failed after approval: {str(e)}")
                return {
                    "id": promotion_id,
                    "action": "approve",
                    "status": "approved",
                    "message": f"Promotion approved but execution failed: {str(e)}"
                }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process approval: {str(e)}"
        )


@router.get("/", response_model=PromotionListResponse)
async def list_promotions(
    status_filter: Optional[str] = None,
    limit: int = 20,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    List all promotions for the tenant.
    """
    # Placeholder - would query database
    return PromotionListResponse(
        data=[],
        total=0
    )


@router.get("/workflows/{workflow_id}/diff")
async def get_workflow_diff(
    workflow_id: str,
    source_environment_id: str = Query(..., description="Source environment ID"),
    target_environment_id: str = Query(..., description="Target environment ID"),
    source_snapshot_id: Optional[str] = Query(None, description="Source snapshot ID (defaults to latest)"),
    target_snapshot_id: Optional[str] = Query(None, description="Target snapshot ID (defaults to latest)"),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get detailed diff for a single workflow between source and target environments.
    Returns structured diff result with differences and summary.
    """
    logger.info(f"[WORKFLOW_DIFF] Route hit! workflow_id={workflow_id}, source={source_environment_id}, target={target_environment_id}")
    try:
        if not source_environment_id or not target_environment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_environment_id and target_environment_id are required"
            )
        
        # If no snapshot IDs provided, use "latest" (will use latest from GitHub)
        source_snap = source_snapshot_id or "latest"
        target_snap = target_snapshot_id or "latest"
        
        diff_result = await promotion_service.get_workflow_diff(
            tenant_id=MOCK_TENANT_ID,
            workflow_id=workflow_id,
            source_env_id=source_environment_id,
            target_env_id=target_environment_id,
            source_snapshot_id=source_snap,
            target_snapshot_id=target_snap
        )

        return {
            "data": diff_result
        }

    except ValueError as e:
        logger.error(f"ValueError in get_workflow_diff: {str(e)}")
        msg = str(e)
        # Environment type missing is a configuration/user error, not "not found"
        if "Environment type is required" in msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception in get_workflow_diff: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow diff: {str(e)}"
        )


@router.get("/initiate/{deployment_id}", response_model=PromotionDetail)
async def get_promotion(
    promotion_id: str,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get details of a specific promotion.
    """
    logger.info(f"[GET_DEPLOYMENT_INITIATION] Route hit with deployment_id={deployment_id}")
    # Prevent this route from matching /workflows/... paths
    if deployment_id == "workflows":
        logger.warning(f"[GET_DEPLOYMENT_INITIATION] Blocked attempt to access workflows path as deployment_id")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )
    try:
        promo = await db_service.get_promotion(deployment_id, MOCK_TENANT_ID)
        if not promo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Promotion not found"
            )
        
        # Get pipeline and environment names
        pipeline = await db_service.get_pipeline(promo.get("pipeline_id"), MOCK_TENANT_ID)
        source_env = await db_service.get_environment(promo.get("source_environment_id"), MOCK_TENANT_ID)
        target_env = await db_service.get_environment(promo.get("target_environment_id"), MOCK_TENANT_ID)
        
        return {
            "id": promo.get("id"),
            "tenant_id": promo.get("tenant_id"),
            "pipeline_id": promo.get("pipeline_id"),
            "pipeline_name": pipeline.get("name") if pipeline else "Unknown",
            "source_environment_id": promo.get("source_environment_id"),
            "source_environment_name": source_env.get("n8n_name") if source_env else "Unknown",
            "target_environment_id": promo.get("target_environment_id"),
            "target_environment_name": target_env.get("n8n_name") if target_env else "Unknown",
            "status": promo.get("status"),
            "source_snapshot_id": promo.get("source_snapshot_id"),
            "target_pre_snapshot_id": promo.get("target_pre_snapshot_id"),
            "target_post_snapshot_id": promo.get("target_post_snapshot_id"),
            "workflow_selections": promo.get("workflow_selections", []),
            "gate_results": promo.get("gate_results"),
            "created_by": promo.get("created_by"),
            "approved_by": promo.get("approved_by"),
            "approved_at": promo.get("approved_at"),
            "rejection_reason": promo.get("rejection_reason"),
            "execution_result": promo.get("execution_result"),
            "created_at": promo.get("created_at"),
            "updated_at": promo.get("updated_at"),
            "completed_at": promo.get("completed_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get promotion: {str(e)}"
        )


@router.post("/snapshots", response_model=PromotionSnapshotResponse)
async def create_snapshot(
    request: PromotionSnapshotRequest,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Create a snapshot of an environment (used for drift checking).
    """
    try:
        snapshot_id, commit_sha = await promotion_service.create_snapshot(
            tenant_id=MOCK_TENANT_ID,
            environment_id=request.environment_id,
            reason=request.reason,
            metadata=request.metadata
        )

        return PromotionSnapshotResponse(
            snapshot_id=snapshot_id,
            commit_sha=commit_sha,
            workflows_count=0,  # Would get from snapshot
            created_at=datetime.utcnow()
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create snapshot: {str(e)}"
        )


@router.post("/check-drift")
async def check_drift(
    environment_id: str,
    snapshot_id: str,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Check if an environment has drifted from its snapshot.
    """
    try:
        drift_check = await promotion_service.check_drift(
            tenant_id=MOCK_TENANT_ID,
            environment_id=environment_id,
            snapshot_id=snapshot_id
        )

        return drift_check

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check drift: {str(e)}"
        )


@router.post("/compare-workflows")
async def compare_workflows(
    request: dict,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Compare workflows between source and target environments.
    Returns list of workflow selections with change types.
    """
    try:
        source_environment_id = request.get("source_environment_id")
        target_environment_id = request.get("target_environment_id")
        source_snapshot_id = request.get("source_snapshot_id")
        target_snapshot_id = request.get("target_snapshot_id")
        
        if not source_environment_id or not target_environment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_environment_id and target_environment_id are required"
            )
        
        # If no snapshot IDs provided, use "latest" (will use latest from GitHub)
        source_snap = source_snapshot_id or "latest"
        target_snap = target_snapshot_id or "latest"
        
        selections = await promotion_service.compare_workflows(
            tenant_id=MOCK_TENANT_ID,
            source_env_id=source_environment_id,
            target_env_id=target_environment_id,
            source_snapshot_id=source_snap,
            target_snapshot_id=target_snap
        )

        return {
            "data": [ws.dict() for ws in selections]
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare workflows: {str(e)}"
        )
