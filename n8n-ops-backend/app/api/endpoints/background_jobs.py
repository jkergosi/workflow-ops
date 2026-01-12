"""Background jobs endpoints."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional

from app.services.background_job_service import background_job_service
from app.core.entitlements_gate import require_entitlement
from app.schemas.pagination import PaginatedResponse, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.schemas.background_job import BackgroundJobResponse

router = APIRouter()


@router.get("/test")
async def test_background_jobs_endpoint():
    """Test endpoint to verify the router is working"""
    return {"status": "ok", "message": "Background jobs router is working"}


@router.get("", response_model=PaginatedResponse[dict])
@router.get("/", response_model=PaginatedResponse[dict])
async def get_background_jobs(
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    user_info: dict = Depends(require_entitlement("environment_basic"))
):
    """
    Get background jobs with pagination and optional filters.

    Returns a paginated list of background jobs with the standard pagination envelope.
    Jobs are ordered by created_at DESC (newest first) for deterministic pagination.

    Query Parameters:
    - page: Page number (1-indexed, default: 1)
    - page_size: Items per page (default: 50, max: 100)
    - resource_type: Filter by resource type (optional)
    - resource_id: Filter by specific resource (optional)
    - job_type: Filter by job type (optional)
    - status: Filter by status (optional)

    Returns:
    PaginatedResponse with items, total, page, pageSize, totalPages, hasMore
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Validate page_size
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))

        # Get tenant_id from authenticated user
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        tenant_id = tenant["id"]

        # Calculate offset for database query
        offset = (page - 1) * page_size

        logger.info(f"Fetching background jobs for tenant_id={tenant_id}, page={page}, page_size={page_size}, filters: resource_type={resource_type}, resource_id={resource_id}, job_type={job_type}, status={status}")

        jobs = await background_job_service.get_jobs(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            job_type=job_type,
            status=status,
            limit=page_size,
            offset=offset
        )
        total = await background_job_service.count_jobs(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            job_type=job_type,
            status=status
        )

        logger.info(f"Found {len(jobs)} jobs on page {page} (total: {total}) for tenant_id={tenant_id}")

        # Return standardized pagination response
        return PaginatedResponse.create(
            items=jobs if jobs else [],
            total=total if total is not None else 0,
            page=page,
            page_size=page_size
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get jobs: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get jobs: {str(e)}"
        )


@router.get("/{job_id}")
async def get_background_job(
    job_id: str,
    user_info: dict = Depends(require_entitlement("environment_basic"))
):
    """Get a background job by ID"""
    try:
        # Get tenant_id from authenticated user
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        tenant_id = tenant["id"]

        job = await background_job_service.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

        # Verify job belongs to the tenant
        if job.get("tenant_id") != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job: {str(e)}"
        )


@router.post("/{job_id}/cancel")
async def cancel_background_job(
    job_id: str,
    user_info: dict = Depends(require_entitlement("environment_basic"))
):
    """
    Cancel a running or pending background job.

    This operation is safe and idempotent:
    - Only marks the job as CANCELLED in the database
    - Does NOT forcefully kill processes or threads
    - Workers must cooperatively check status and exit gracefully
    - Emits SSE event to notify clients and workers
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Get tenant_id from authenticated user
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        tenant_id = tenant["id"]

        # Get job and verify it belongs to the tenant
        job = await background_job_service.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

        if job.get("tenant_id") != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )

        # Cancel the job
        try:
            updated_job = await background_job_service.cancel_job(job_id)
            logger.info(f"Job {job_id} cancelled by user from tenant {tenant_id}")
            return updated_job
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve)
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}"
        )

