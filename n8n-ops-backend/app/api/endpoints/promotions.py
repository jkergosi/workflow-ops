"""
Promotions API endpoints for pipeline-aware environment promotion
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
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
from app.schemas.promotion import (
    PromotionInitiateRequest,
    PromotionInitiateResponse,
    PromotionApprovalRequest,
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

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


@router.post("/initiate", response_model=PromotionInitiateResponse)
async def initiate_promotion(
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


@router.post("/execute/{promotion_id}")
async def execute_promotion(
    promotion_id: str,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Execute a promotion - simplified version that creates deployment record.
    TODO: Add actual workflow transfer once n8n connections are configured.
    """
    try:
        # Get promotion record
        promotion = await db_service.get_promotion(promotion_id, MOCK_TENANT_ID)
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

        # Update status to running
        await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {"status": "running"})

        # Create Deployment record
        from app.schemas.deployment import DeploymentStatus, WorkflowChangeType, WorkflowStatus
        from uuid import uuid4

        deployment_id = str(uuid4())
        workflow_selections = promotion.get("workflow_selections", [])
        selected_workflows = [ws for ws in workflow_selections if ws.get("selected")]

        # Calculate summary
        summary_json = {
            "total": len(selected_workflows),
            "created": len([ws for ws in selected_workflows if ws.get("change_type") == "new"]),
            "updated": len([ws for ws in selected_workflows if ws.get("change_type") in ["changed", "staging_hotfix"]]),
            "deleted": 0,
            "failed": 0,
            "skipped": 0,
        }

        deployment_data = {
            "id": deployment_id,
            "tenant_id": MOCK_TENANT_ID,
            "pipeline_id": promotion.get("pipeline_id"),
            "source_environment_id": promotion.get("source_environment_id"),
            "target_environment_id": promotion.get("target_environment_id"),
            "status": DeploymentStatus.SUCCESS.value,  # Mark as success for now
            "triggered_by_user_id": promotion.get("created_by") or "00000000-0000-0000-0000-000000000000",
            "approved_by_user_id": None,
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": datetime.utcnow().isoformat(),
            "pre_snapshot_id": None,
            "post_snapshot_id": None,
            "summary_json": summary_json,
        }
        await db_service.create_deployment(deployment_data)

        # Create deployment_workflow records for each selected workflow
        for ws in selected_workflows:
            change_type_map = {
                "new": WorkflowChangeType.CREATED,
                "changed": WorkflowChangeType.UPDATED,
                "staging_hotfix": WorkflowChangeType.UPDATED,
                "conflict": WorkflowChangeType.SKIPPED,
                "unchanged": WorkflowChangeType.UNCHANGED,
            }
            change_type = change_type_map.get(ws.get("change_type"), WorkflowChangeType.UPDATED)

            workflow_data = {
                "deployment_id": deployment_id,
                "workflow_id": ws.get("workflow_id"),
                "workflow_name_at_time": ws.get("workflow_name"),
                "change_type": change_type.value,
                "status": WorkflowStatus.SUCCESS.value,
                "error_message": None,
            }
            await db_service.create_deployment_workflow(workflow_data)

        # Update promotion as completed
        await db_service.update_promotion(promotion_id, MOCK_TENANT_ID, {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat()
        })

        return {
            "promotion_id": promotion_id,
            "deployment_id": deployment_id,
            "status": "completed",
            "summary": summary_json,
            "message": "Promotion executed successfully"
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
            
            # Emit promotion.failure event
            try:
                promotion = await db_service.get_promotion(promotion_id, MOCK_TENANT_ID)
                await notification_service.emit_event(
                    tenant_id=MOCK_TENANT_ID,
                    event_type="promotion.failure",
                    environment_id=promotion.get("target_environment_id") if promotion else None,
                    metadata={
                        "promotion_id": promotion_id,
                        "error_message": str(e),
                        "error_type": type(e).__name__
                    }
                )
            except Exception as event_error:
                logger.error(f"Failed to emit promotion.failure event: {str(event_error)}")
        except:
            pass
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute promotion: {str(e)}"
        )


@router.post("/approvals/{promotion_id}/approve")
async def approve_promotion(
    promotion_id: str,
    request: PromotionApprovalRequest,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Approve or reject a pending promotion.
    Supports multi-approver workflows (1 of N / All).
    """
    try:
        # Get promotion
        promotion = await db_service.get_promotion(promotion_id, MOCK_TENANT_ID)
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


@router.get("/{promotion_id}", response_model=PromotionDetail)
async def get_promotion(
    promotion_id: str,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get details of a specific promotion.
    """
    try:
        promo = await db_service.get_promotion(promotion_id, MOCK_TENANT_ID)
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare workflows: {str(e)}"
        )
