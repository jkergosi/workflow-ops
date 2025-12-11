from fastapi import APIRouter, HTTPException, status, Query, Depends
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
        # Build query
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

        # Get total count
        count_result = query.execute()
        total = len(count_result.data) if count_result.data else 0

        # Apply pagination
        from_index = (page - 1) * page_size
        to_index = from_index + page_size
        query = query.order("started_at", desc=True).range(from_index, to_index - 1)

        result = query.execute()
        deployments_data = result.data or []

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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
                status_code=status.HTTP_404_NOT_FOUND,
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch deployment: {str(e)}",
        )

