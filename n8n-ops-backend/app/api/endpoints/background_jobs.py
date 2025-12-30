"""Background jobs endpoints."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional

from app.services.background_job_service import background_job_service
from app.core.entitlements_gate import require_entitlement

router = APIRouter()


@router.get("/test")
async def test_background_jobs_endpoint():
    """Test endpoint to verify the router is working"""
    return {"status": "ok", "message": "Background jobs router is working"}


@router.get("")
@router.get("/")
async def get_background_jobs(
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_info: dict = Depends(require_entitlement("environment_basic"))
):
    """Get background jobs with optional filters"""
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
        
        logger.info(f"Fetching background jobs for tenant_id={tenant_id}, filters: resource_type={resource_type}, resource_id={resource_id}, job_type={job_type}, status={status}, limit={limit}, offset={offset}")
        
        jobs = await background_job_service.get_jobs(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            job_type=job_type,
            status=status,
            limit=limit,
            offset=offset
        )
        total = await background_job_service.count_jobs(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            job_type=job_type,
            status=status
        )
        
        logger.info(f"Found {len(jobs)} jobs (total: {total}) for tenant_id={tenant_id}")
        logger.info(f"Jobs data type: {type(jobs)}, Total type: {type(total)}")
        
        result = {
            "jobs": jobs if jobs else [],
            "total": total if total is not None else 0
        }
        logger.info(f"Returning result: {result}")
        return result
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

