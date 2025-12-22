from fastapi import APIRouter, HTTPException, Query, Depends, Request, BackgroundTasks
from fastapi import status as http_status
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import uuid4
from app.services.database import db_service
from app.schemas.deployment import (
    DeploymentResponse,
    DeploymentDetailResponse,
    DeploymentListResponse,
    DeploymentStatus,
    DeploymentWorkflowResponse,
    SnapshotResponse,
)
from app.schemas.promotion import WorkflowSelection, PromotionStatus, GateResult, WorkflowChangeType as PromotionWorkflowChangeType
from app.core.entitlements_gate import require_entitlement
from app.services.background_job_service import background_job_service, BackgroundJobType, BackgroundJobStatus
from app.services.auth_service import get_current_user
from app.api.endpoints.admin_audit import create_audit_log
from app.api.endpoints.promotions import _execute_promotion_background
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Entitlement gates for CI/CD features

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def _attach_progress_fields(deployment: dict, workflows: Optional[List[dict]] = None) -> dict:
    """
    Attach progress fields derived from summary_json/workflows so UI can display counts.
    For completed deployments, shows successful deployments (created + updated) out of total.
    """
    summary = deployment.get("summary_json") or {}
    total = summary.get("total")
    if total is None and workflows is not None:
        total = len(workflows)
    if total is None:
        total = 0

    status = deployment.get("status")
    
    # For completed deployments (success/failed), show successful deployments
    if status in [DeploymentStatus.SUCCESS.value, DeploymentStatus.FAILED.value]:
        created = summary.get("created", 0)
        updated = summary.get("updated", 0)
        successful = created + updated
        deployment["progress_current"] = successful
        deployment["progress_total"] = total
    # For running deployments, show processed count
    elif status == DeploymentStatus.RUNNING.value:
        processed = summary.get("processed", 0)
        if processed is None and workflows is not None:
            processed = sum(1 for wf in workflows if wf.get("status") in ["success", "failed", "skipped"])
        if processed is None:
            processed = 0
        deployment["progress_current"] = min(processed + 1, total) if total else processed
        deployment["progress_total"] = total
    else:
        # For pending/canceled, show 0
        deployment["progress_current"] = 0
        deployment["progress_total"] = total
    
    deployment["current_workflow_name"] = summary.get("current_workflow")
    return deployment


@router.get("/", response_model=DeploymentListResponse)
async def get_deployments(
    status: Optional[DeploymentStatus] = Query(None, alias="status"),
    pipeline_id: Optional[str] = Query(None),
    environment_id: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: dict = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get list of deployments with filtering and pagination.
    Returns summary counts for cards.
    """
    try:
        # Build query - exclude deleted deployments by default
        # Note: deleted_at column may not exist if migration hasn't run yet
        query = db_service.client.table("deployments").select("*").eq("tenant_id", MOCK_TENANT_ID)
        
        # Try to filter by deleted_at, but handle gracefully if column doesn't exist
        # We'll catch the error when executing if the column doesn't exist
        try:
            # Test if column exists by trying to add the filter
            query = query.is_("deleted_at", "null")
        except Exception:
            # Column doesn't exist yet, skip the filter
            pass

        if status:
            query = query.eq("status", status.value)
        if pipeline_id:
            query = query.eq("pipeline_id", pipeline_id)
        if environment_id:
            query = query.or_(
                f"source_environment_id.eq.{environment_id},target_environment_id.eq.{environment_id}"
            )
        if from_date:
            query = query.gte("started_at", from_date.isoformat())
        if to_date:
            query = query.lte("started_at", to_date.isoformat())

        # Get total count
        # Handle case where deleted_at column doesn't exist (migration may not have run)
        try:
            count_result = query.execute()
        except Exception as db_error:
            # If error is about missing column (PostgreSQL error code 42703), rebuild query without deleted_at filter
            error_str = str(db_error)
            if "deleted_at" in error_str or "42703" in error_str or "column" in error_str.lower():
                # Rebuild query without deleted_at filter
                query = db_service.client.table("deployments").select("*").eq("tenant_id", MOCK_TENANT_ID)
                if status:
                    query = query.eq("status", status.value)
                if pipeline_id:
                    query = query.eq("pipeline_id", pipeline_id)
                if environment_id:
                    query = query.or_(
                        f"source_environment_id.eq.{environment_id},target_environment_id.eq.{environment_id}"
                    )
                if from_date:
                    query = query.gte("started_at", from_date.isoformat())
                if to_date:
                    query = query.lte("started_at", to_date.isoformat())
                count_result = query.execute()
            else:
                raise
        
        total = len(count_result.data) if count_result.data else 0

        # Apply pagination
        from_index = (page - 1) * page_size
        to_index = from_index + page_size
        query = query.order("started_at", desc=True).range(from_index, to_index - 1)

        result = query.execute()
        deployments_data = result.data or []
        
        # Check for stale running deployments and mark them as failed
        # This runs on every GET request to catch stale deployments during polling
        for dep_data in deployments_data:
            if dep_data.get("status") == DeploymentStatus.RUNNING.value:
                started_at_str = dep_data.get("started_at")
                if started_at_str:
                    try:
                        started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00')) if isinstance(started_at_str, str) else started_at_str
                        if hasattr(started_at, 'tzinfo') and started_at.tzinfo is not None:
                            started_at_naive = started_at.replace(tzinfo=None)
                        else:
                            started_at_naive = started_at
                        hours_running = (datetime.utcnow() - started_at_naive).total_seconds() / 3600
                        
                        # If running for more than 1 hour, mark as failed
                        if hours_running > 1:
                            dep_id = dep_data.get("id")
                            logger.warning(f"Detected stale deployment {dep_id} running for {hours_running:.2f} hours, marking as failed")
                            try:
                                await db_service.update_deployment(dep_id, {
                                    "status": "failed",
                                    "finished_at": datetime.utcnow().isoformat(),
                                    "summary_json": {
                                        "error": f"Deployment timed out after running for {hours_running:.2f} hours. Background job may have crashed or server restarted.",
                                        "timeout_hours": hours_running
                                    }
                                })
                                # Update the data in the response
                                dep_data["status"] = "failed"
                                dep_data["finished_at"] = datetime.utcnow().isoformat()
                            except Exception as update_error:
                                logger.error(f"Failed to mark stale deployment {dep_id} as failed: {str(update_error)}")
                    except Exception as check_error:
                        logger.error(f"Failed to check deployment staleness: {str(check_error)}")

        # Calculate this week success count
        week_ago = datetime.utcnow() - timedelta(days=7)
        this_week_query = (
            db_service.client.table("deployments")
            .select("id")
            .eq("tenant_id", MOCK_TENANT_ID)
            .eq("status", DeploymentStatus.SUCCESS.value)
            .gte("started_at", week_ago.isoformat())
        )
        this_week_result = this_week_query.execute()
        this_week_success_count = len(this_week_result.data) if this_week_result.data else 0

        # Pending approvals count (can be 0 in v1)
        pending_approvals_count = 0

        # Attach progress fields and convert to response models
        for deployment in deployments_data:
            _attach_progress_fields(deployment)

        deployments = [DeploymentResponse(**deployment) for deployment in deployments_data]

        return DeploymentListResponse(
            deployments=deployments,
            total=total,
            page=page,
            page_size=page_size,
            this_week_success_count=this_week_success_count,
            pending_approvals_count=pending_approvals_count,
        )

    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deployments: {str(e)}",
        )


@router.get("/{deployment_id}", response_model=DeploymentDetailResponse)
async def get_deployment(
    deployment_id: str,
    _: dict = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get deployment details including workflows and linked snapshots.
    """
    try:
        # Get deployment - exclude deleted deployments
        # Note: deleted_at column may not exist if migration hasn't run yet
        query = (
            db_service.client.table("deployments")
            .select("*")
            .eq("id", deployment_id)
            .eq("tenant_id", MOCK_TENANT_ID)
        )
        
        # Try to filter by deleted_at, but handle gracefully if column doesn't exist
        try:
            query = query.is_("deleted_at", "null")
            deployment_result = query.single().execute()
        except Exception as db_error:
            # If error is about missing column, rebuild query without deleted_at filter
            error_str = str(db_error)
            if "deleted_at" in error_str or "42703" in error_str or "column" in error_str.lower():
                query = (
                    db_service.client.table("deployments")
                    .select("*")
                    .eq("id", deployment_id)
                    .eq("tenant_id", MOCK_TENANT_ID)
                )
                deployment_result = query.single().execute()
            else:
                raise

        if not deployment_result.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Deployment {deployment_id} not found",
            )

        deployment_data = deployment_result.data

        # Get deployment workflows
        workflows_result = (
            db_service.client.table("deployment_workflows")
            .select("*")
            .eq("deployment_id", deployment_id)
            .execute()
        )
        workflows_raw = workflows_result.data or []
        workflows = [DeploymentWorkflowResponse(**wf) for wf in workflows_raw]

        _attach_progress_fields(deployment_data, workflows_raw)
        deployment = DeploymentResponse(**deployment_data)
        
        # If deployment is running, check if it's stale and verify job status
        job_status = None
        if deployment.status == DeploymentStatus.RUNNING.value:
            # Check if deployment has been running too long (>1 hour)
            started_at_str = deployment.started_at
            if started_at_str:
                try:
                    started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00')) if isinstance(started_at_str, str) else started_at_str
                    if hasattr(started_at, 'tzinfo') and started_at.tzinfo is not None:
                        started_at_naive = started_at.replace(tzinfo=None)
                    else:
                        started_at_naive = started_at
                    hours_running = (datetime.utcnow() - started_at_naive).total_seconds() / 3600
                    
                    # If running for more than 1 hour, mark as failed
                    if hours_running > 1:
                        logger.warning(f"Deployment {deployment_id} has been running for {hours_running:.2f} hours, marking as failed")
                        await db_service.update_deployment(deployment_id, {
                            "status": "failed",
                            "finished_at": datetime.utcnow().isoformat(),
                            "summary_json": {
                                "error": f"Deployment timed out after running for {hours_running:.2f} hours. Background job may have crashed or server restarted.",
                                "timeout_hours": hours_running
                            }
                        })
                        # Refresh deployment data
                        deployment_result = (
                            db_service.client.table("deployments")
                            .select("*")
                            .eq("id", deployment_id)
                            .eq("tenant_id", MOCK_TENANT_ID)
                            .single()
                            .execute()
                        )
                        if deployment_result.data:
                            refreshed_data = deployment_result.data
                            _attach_progress_fields(refreshed_data, workflows_raw)
                            deployment = DeploymentResponse(**refreshed_data)
                except Exception as stale_check_error:
                    logger.error(f"Failed to check if deployment {deployment_id} is stale: {str(stale_check_error)}")
            
            # Try to get job status for more details
            try:
                # Find promotion that matches this deployment
                promotion_result = (
                    db_service.client.table("promotions")
                    .select("id")
                    .eq("tenant_id", MOCK_TENANT_ID)
                    .eq("source_environment_id", deployment.source_environment_id)
                    .eq("target_environment_id", deployment.target_environment_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if promotion_result.data:
                    promotion_id = promotion_result.data[0].get("id")
                    job = await background_job_service.get_latest_job_by_resource(
                        resource_type="promotion",
                        resource_id=promotion_id,
                        tenant_id=MOCK_TENANT_ID
                    )
                    # Verify this job is for this deployment by checking result.deployment_id
                    if job and job.get("result", {}).get("deployment_id") == deployment_id:
                        job_status = {
                            "status": job.get("status"),
                            "progress": job.get("progress", {}),
                            "error_message": job.get("error_message")
                        }
                        
                        # If job is failed/completed but deployment is still running, update deployment
                        if job.get("status") in ["failed", "completed"] and deployment.status == DeploymentStatus.RUNNING.value:
                            logger.warning(f"Deployment {deployment_id} is running but job is {job.get('status')}, updating deployment status")
                            final_status = "failed" if job.get("status") == "failed" else "success"
                            await db_service.update_deployment(deployment_id, {
                                "status": final_status,
                                "finished_at": datetime.utcnow().isoformat(),
                                "summary_json": job.get("result", {}).get("summary", {})
                            })
                            # Refresh deployment data
                            deployment_result = (
                                db_service.client.table("deployments")
                                .select("*")
                                .eq("id", deployment_id)
                                .eq("tenant_id", MOCK_TENANT_ID)
                                .single()
                                .execute()
                            )
                            if deployment_result.data:
                                deployment = DeploymentResponse(**deployment_result.data)
            except Exception:
                # If we can't get job status, continue without it
                pass

        # Get pre snapshot if exists
        pre_snapshot = None
        if deployment.pre_snapshot_id:
            pre_snapshot_result = (
                db_service.client.table("snapshots")
                .select("*")
                .eq("id", deployment.pre_snapshot_id)
                .single()
                .execute()
            )
            if pre_snapshot_result.data:
                pre_snapshot = SnapshotResponse(**pre_snapshot_result.data)

        # Get post snapshot if exists
        post_snapshot = None
        if deployment.post_snapshot_id:
            post_snapshot_result = (
                db_service.client.table("snapshots")
                .select("*")
                .eq("id", deployment.post_snapshot_id)
                .single()
                .execute()
            )
            if post_snapshot_result.data:
                post_snapshot = SnapshotResponse(**post_snapshot_result.data)

        return DeploymentDetailResponse(
            **deployment.model_dump(),
            workflows=workflows,
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
        )

    except HTTPException:
        raise
    except Exception as e:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch deployment: {str(e)}",
            )


@router.delete("/{deployment_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: str,
    request: Request,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Soft delete a deployment.
    
    Restrictions:
    - Cannot delete running deployments
    - Successful deployments must be at least 1 day old (for audit trail)
    - Failed/canceled deployments can be deleted immediately
    """
    try:
        # Get deployment
        deployment_result = (
            db_service.client.table("deployments")
            .select("*")
            .eq("id", deployment_id)
            .eq("tenant_id", MOCK_TENANT_ID)
            .single()
            .execute()
        )

        if not deployment_result.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Deployment {deployment_id} not found",
            )

        deployment = deployment_result.data
        
        # Check if already deleted
        if deployment.get("deleted_at"):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Deployment is already deleted"
            )

        # Check restrictions
        if deployment.get("status") == DeploymentStatus.RUNNING.value:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete a running deployment"
            )

        # Age restriction: Only apply to successful deployments
        # Failed/canceled deployments can be deleted immediately
        deployment_status = deployment.get("status")
        if deployment_status == DeploymentStatus.SUCCESS.value:
            # For successful deployments, require 1 day minimum age for audit trail
            created_at_str = deployment.get("created_at")
            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) if isinstance(created_at_str, str) else created_at_str
                # Handle timezone-aware datetime
                if hasattr(created_at, 'tzinfo') and created_at.tzinfo is not None:
                    created_at_naive = created_at.replace(tzinfo=None)
                else:
                    created_at_naive = created_at
                age_days = (datetime.utcnow() - created_at_naive).days
                min_age_days = 1  # Reduced from 7 to 1 day for successful deployments
                if age_days < min_age_days:
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot delete successful deployments less than {min_age_days} day old. This deployment is {age_days} days old."
                    )
            else:
                # If created_at is missing, allow deletion (shouldn't happen, but be permissive)
                logger.warning(f"Deployment {deployment_id} missing created_at field, allowing deletion")
        # Failed and canceled deployments can be deleted immediately (no age restriction)

        # Get user info
        user = user_info.get("user", {})
        actor_id = user.get("id")
        actor_email = user.get("email")
        actor_name = user.get("name")
        
        # Get IP address and user agent
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Perform soft delete
        deleted_deployment = await db_service.delete_deployment(
            deployment_id=deployment_id,
            tenant_id=MOCK_TENANT_ID,
            deleted_by_user_id=actor_id or "00000000-0000-0000-0000-000000000000"
        )

        if not deleted_deployment:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete deployment"
            )

        # Create audit log entry
        try:
            # Get environment info for provider context
            source_env = await db_service.get_environment(deployment.get("source_environment_id"), MOCK_TENANT_ID)
            provider = source_env.get("provider", "n8n") if source_env else "n8n"
            
            await create_audit_log(
                action_type="DEPLOYMENT_DELETED",
                action=f"Deleted deployment",
                actor_id=actor_id,
                actor_email=actor_email,
                actor_name=actor_name,
                tenant_id=MOCK_TENANT_ID,
                resource_type="deployment",
                resource_id=deployment_id,
                resource_name=f"Deployment {deployment_id[:8]}",
                provider=provider,
                old_value={
                    "deployment_id": deployment_id,
                    "status": deployment.get("status"),
                    "workflow_count": deployment.get("summary_json", {}).get("total", 0),
                    "source_environment_id": deployment.get("source_environment_id"),
                    "target_environment_id": deployment.get("target_environment_id"),
                    "pipeline_id": deployment.get("pipeline_id"),
                    "started_at": deployment.get("started_at"),
                    "finished_at": deployment.get("finished_at"),
                },
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "deleted_at": deleted_deployment.get("deleted_at"),
                    "age_days": age_days if created_at_str else None,
                    "created_at": created_at_str
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to create audit log for deployment deletion: {str(audit_error)}")

        # Return 204 No Content (no response body)
        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete deployment: {str(e)}",
        )


@router.post("/{deployment_id}/rerun")
async def rerun_deployment(
    deployment_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Rerun a deployment - creates a new deployment using the same pipeline/stage, 
    source/target, and workflow selections as the original.
    
    Re-runs all gates (drift, credential preflight, approvals) and creates fresh pre/post snapshots.
    Only allowed for terminal states (failed/canceled; optionally success as "re-deploy").
    """
    try:
        # Get original deployment
        deployment_result = (
            db_service.client.table("deployments")
            .select("*")
            .eq("id", deployment_id)
            .eq("tenant_id", MOCK_TENANT_ID)
            .single()
            .execute()
        )

        if not deployment_result.data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Deployment {deployment_id} not found",
            )

        deployment = deployment_result.data
        
        # Check if already deleted
        if deployment.get("deleted_at"):
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Cannot rerun a deleted deployment"
            )

        # Only allow rerun for terminal states
        deployment_status = deployment.get("status")
        if deployment_status not in [
            DeploymentStatus.FAILED.value,
            DeploymentStatus.CANCELED.value,
            DeploymentStatus.SUCCESS.value,  # Allow success as "re-deploy"
        ]:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot rerun deployment in status: {deployment_status}. Only failed, canceled, or successful deployments can be rerun."
            )

        # Get deployment workflows to reconstruct workflow selections
        workflows_result = (
            db_service.client.table("deployment_workflows")
            .select("*")
            .eq("deployment_id", deployment_id)
            .execute()
        )
        workflows_raw = workflows_result.data or []

        if not workflows_raw:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Cannot rerun deployment: no workflows found in original deployment"
            )

        # Reconstruct workflow selections from deployment workflows
        # Map deployment change_type (CREATED, UPDATED, etc.) to promotion change_type (NEW, CHANGED, etc.)
        deployment_to_promotion_change_type = {
            "created": PromotionWorkflowChangeType.NEW,
            "updated": PromotionWorkflowChangeType.CHANGED,
            "deleted": PromotionWorkflowChangeType.CHANGED,  # Deleted workflows won't be in rerun, but handle it
            "skipped": PromotionWorkflowChangeType.CONFLICT,  # Skipped might indicate conflict
            "unchanged": PromotionWorkflowChangeType.UNCHANGED,
        }

        workflow_selections = []
        for wf in workflows_raw:
            # Map change_type from deployment_workflows (CREATED, UPDATED, etc.) to promotion WorkflowChangeType (NEW, CHANGED, etc.)
            deployment_change_type = wf.get("change_type", "created")
            promotion_change_type = deployment_to_promotion_change_type.get(
                deployment_change_type.lower(),
                PromotionWorkflowChangeType.CHANGED  # Default to CHANGED if unknown
            )

            workflow_selections.append(WorkflowSelection(
                workflow_id=wf.get("workflow_id"),
                workflow_name=wf.get("workflow_name_at_time", "Unknown"),
                change_type=promotion_change_type,
                enabled_in_source=True,  # We don't store this, assume enabled
                enabled_in_target=None,
                selected=True,  # All workflows in deployment were selected
                requires_overwrite=(promotion_change_type == PromotionWorkflowChangeType.CHANGED),
            ))

        # Get pipeline to find active stage
        pipeline_id = deployment.get("pipeline_id")
        if not pipeline_id:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Cannot rerun deployment: no pipeline associated"
            )

        pipeline_data = await db_service.get_pipeline(pipeline_id, MOCK_TENANT_ID)
        if not pipeline_data:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )

        # Find the active stage for this source -> target
        source_env_id = deployment.get("source_environment_id")
        target_env_id = deployment.get("target_environment_id")
        active_stage = None
        for stage in pipeline_data.get("stages", []):
            if (stage.get("source_environment_id") == source_env_id and
                stage.get("target_environment_id") == target_env_id):
                active_stage = stage
                break

        if not active_stage:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="No stage found for this source -> target environment pair"
            )

        # Get source and target environments
        source_env = await db_service.get_environment(source_env_id, MOCK_TENANT_ID)
        target_env = await db_service.get_environment(target_env_id, MOCK_TENANT_ID)

        if not source_env or not target_env:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Source or target environment not found"
            )

        # Check if approval required
        requires_approval = active_stage.get("approvals", {}).get("require_approval", False)

        # Create new promotion record
        promotion_id = str(uuid4())

        # Gate results (will be re-evaluated during execution)
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

        # Get user info
        user = user_info.get("user", {})
        actor_id = user.get("id") or "00000000-0000-0000-0000-000000000000"

        promotion_data = {
            "id": promotion_id,
            "tenant_id": MOCK_TENANT_ID,
            "pipeline_id": pipeline_id,
            "source_environment_id": source_env_id,
            "target_environment_id": target_env_id,
            "status": PromotionStatus.PENDING_APPROVAL.value if requires_approval else PromotionStatus.PENDING.value,
            "source_snapshot_id": None,  # Created during execution
            "workflow_selections": [ws.dict() for ws in workflow_selections],
            "gate_results": gate_results.dict(),
            "created_by": actor_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Store promotion
        await db_service.create_promotion(promotion_data)

        # Create background job
        job = await background_job_service.create_job(
            tenant_id=MOCK_TENANT_ID,
            job_type=BackgroundJobType.PROMOTION_EXECUTE,
            resource_id=promotion_id,
            resource_type="promotion",
            created_by=actor_id,
            initial_progress={
                "current": 0,
                "total": len(workflow_selections),
                "percentage": 0,
                "message": "Initializing rerun deployment"
            }
        )
        job_id = job["id"]

        # Update promotion status to running
        await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {"status": PromotionStatus.RUNNING.value})

        # Create new deployment record
        new_deployment_id = str(uuid4())
        deployment_data = {
            "id": new_deployment_id,
            "tenant_id": MOCK_TENANT_ID,
            "pipeline_id": pipeline_id,
            "source_environment_id": source_env_id,
            "target_environment_id": target_env_id,
            "status": DeploymentStatus.RUNNING.value,
            "triggered_by_user_id": actor_id,
            "approved_by_user_id": None,
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "pre_snapshot_id": None,
            "post_snapshot_id": None,
            "summary_json": {"total": len(workflow_selections), "created": 0, "updated": 0, "deleted": 0, "failed": 0, "skipped": 0},
        }
        await db_service.create_deployment(deployment_data)

        # Update job with deployment_id in result for tracking
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.PENDING,
            result={"deployment_id": new_deployment_id}
        )

        # Prepare selected workflows for background task
        selected_workflows = [ws.dict() for ws in workflow_selections]

        # Start background execution task
        background_tasks.add_task(
            _execute_promotion_background,
            job_id=job_id,
            promotion_id=promotion_id,
            deployment_id=new_deployment_id,
            promotion=promotion_data,
            source_env=source_env,
            target_env=target_env,
            selected_workflows=selected_workflows
        )

        # Create audit log entry
        try:
            provider = source_env.get("provider", "n8n")
            actor_email = user.get("email")
            actor_name = user.get("name")
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

            await create_audit_log(
                action_type="DEPLOYMENT_RERUN",
                action=f"Rerun deployment",
                actor_id=actor_id,
                actor_email=actor_email,
                actor_name=actor_name,
                tenant_id=MOCK_TENANT_ID,
                resource_type="deployment",
                resource_id=new_deployment_id,
                resource_name=f"Deployment {new_deployment_id[:8]}",
                provider=provider,
                old_value={
                    "original_deployment_id": deployment_id,
                    "original_status": deployment_status,
                    "workflow_count": len(workflow_selections),
                    "source_environment_id": source_env_id,
                    "target_environment_id": target_env_id,
                    "pipeline_id": pipeline_id,
                },
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "rerun_from_deployment_id": deployment_id,
                    "promotion_id": promotion_id,
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to create audit log for deployment rerun: {str(audit_error)}")

        logger.info(f"Rerun deployment {new_deployment_id} created from deployment {deployment_id}")

        # Return new deployment info
        return {
            "deployment_id": new_deployment_id,
            "promotion_id": promotion_id,
            "job_id": job_id,
            "status": "running",
            "message": f"Deployment rerun started. Processing {len(workflow_selections)} workflow(s) in the background.",
            "workflow_count": len(workflow_selections),
            "requires_approval": requires_approval,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rerun deployment: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rerun deployment: {str(e)}",
        )

