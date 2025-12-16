from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi import status as http_status
from typing import Optional, List
from datetime import datetime, timedelta
from app.services.database import db_service
from app.schemas.deployment import (
    DeploymentResponse,
    DeploymentDetailResponse,
    DeploymentListResponse,
    DeploymentStatus,
    DeploymentWorkflowResponse,
    SnapshotResponse,
)
from app.core.entitlements_gate import require_entitlement
from app.services.background_job_service import background_job_service
from app.services.auth_service import get_current_user
from app.api.endpoints.admin_audit import create_audit_log
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Entitlement gates for CI/CD features

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


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

        # Convert to response models
        deployments = [
            DeploymentResponse(**deployment) for deployment in deployments_data
        ]

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

        deployment = DeploymentResponse(**deployment_result.data)

        # Get deployment workflows
        workflows_result = (
            db_service.client.table("deployment_workflows")
            .select("*")
            .eq("deployment_id", deployment_id)
            .execute()
        )
        workflows = [
            DeploymentWorkflowResponse(**wf) for wf in (workflows_result.data or [])
        ]
        
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
                            deployment = DeploymentResponse(**deployment_result.data)
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

