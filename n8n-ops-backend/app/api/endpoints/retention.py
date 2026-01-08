"""
Execution Retention Management API Endpoints

Provides tenant-level access to execution retention policies and cleanup operations.
These endpoints allow tenants to manage their own execution retention settings and
trigger manual cleanup operations.

Related:
- Service: app/services/retention_service.py
- Config: app/core/config.py (EXECUTION_RETENTION_*)
- Migration: migrations/xxx_add_retention_policy.sql
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from app.services.retention_service import retention_service
from app.services.auth_service import get_current_user
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def get_tenant_id(user_info: dict) -> str:
    """Extract and validate tenant ID from user info."""
    tenant = user_info.get("tenant") or {}
    tenant_id = tenant.get("id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return tenant_id


# ============================================================================
# Schemas
# ============================================================================

class RetentionPolicyResponse(BaseModel):
    """Execution retention policy for a tenant."""
    retention_days: int = Field(
        ...,
        description="Number of days to retain executions",
        ge=1,
        le=365
    )
    is_enabled: bool = Field(
        ...,
        description="Whether automatic retention cleanup is enabled"
    )
    min_executions_to_keep: int = Field(
        ...,
        description="Minimum number of executions to preserve (safety threshold)",
        ge=0
    )
    last_cleanup_at: Optional[str] = Field(
        None,
        description="ISO timestamp of last cleanup operation"
    )
    last_cleanup_deleted_count: int = Field(
        0,
        description="Number of executions deleted in last cleanup",
        ge=0
    )


class UpdateRetentionPolicyRequest(BaseModel):
    """Request to update retention policy settings."""
    retention_days: Optional[int] = Field(
        None,
        description="Number of days to retain executions (1-365)",
        ge=1,
        le=365
    )
    is_enabled: Optional[bool] = Field(
        None,
        description="Enable or disable automatic retention cleanup"
    )
    min_executions_to_keep: Optional[int] = Field(
        None,
        description="Minimum executions to preserve (safety threshold)",
        ge=0
    )


class CreateRetentionPolicyRequest(BaseModel):
    """Request to create a new retention policy."""
    retention_days: int = Field(
        90,
        description="Number of days to retain executions (1-365)",
        ge=1,
        le=365
    )
    is_enabled: bool = Field(
        True,
        description="Enable automatic retention cleanup"
    )
    min_executions_to_keep: int = Field(
        100,
        description="Minimum executions to preserve (safety threshold)",
        ge=0
    )


class CleanupResult(BaseModel):
    """Result of a manual retention cleanup operation."""
    tenant_id: str
    deleted_count: int = Field(
        ...,
        description="Number of executions deleted",
        ge=0
    )
    retention_days: int
    is_enabled: bool
    timestamp: str = Field(
        ...,
        description="ISO timestamp when cleanup completed"
    )
    summary: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed execution summary from cleanup operation"
    )
    skipped: Optional[bool] = Field(
        False,
        description="Whether cleanup was skipped (e.g., retention disabled)"
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for skipping cleanup, if applicable"
    )


class CleanupPreviewResponse(BaseModel):
    """Preview of what would be deleted without actually deleting."""
    tenant_id: str
    total_executions: int = Field(
        ...,
        description="Current total execution count for tenant",
        ge=0
    )
    old_executions_count: int = Field(
        ...,
        description="Number of executions older than retention period",
        ge=0
    )
    executions_to_delete: int = Field(
        ...,
        description="Number of executions that would be deleted (respects min_executions_to_keep)",
        ge=0
    )
    cutoff_date: str = Field(
        ...,
        description="ISO timestamp of retention cutoff (executions before this are old)"
    )
    retention_days: int
    min_executions_to_keep: int
    would_delete: bool = Field(
        ...,
        description="Whether any deletions would actually occur"
    )
    is_enabled: bool = Field(
        ...,
        description="Whether retention is currently enabled for this tenant"
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/policy", response_model=RetentionPolicyResponse)
async def get_retention_policy(
    user_info: dict = Depends(get_current_user)
):
    """
    Get the current execution retention policy for the authenticated tenant.

    Returns the tenant's retention configuration including:
    - Retention period (days)
    - Enabled status
    - Safety thresholds
    - Last cleanup metadata

    If no custom policy exists, returns system defaults from configuration.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        policy = await retention_service.get_retention_policy(tenant_id)

        return RetentionPolicyResponse(
            retention_days=policy["retention_days"],
            is_enabled=policy["is_enabled"],
            min_executions_to_keep=policy["min_executions_to_keep"],
            last_cleanup_at=policy.get("last_cleanup_at"),
            last_cleanup_deleted_count=policy.get("last_cleanup_deleted_count", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get retention policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get retention policy: {str(e)}"
        )


@router.post("/policy", response_model=RetentionPolicyResponse)
async def create_retention_policy(
    request: CreateRetentionPolicyRequest,
    user_info: dict = Depends(get_current_user)
):
    """
    Create or update the execution retention policy for the authenticated tenant.

    This endpoint allows tenants to customize their retention settings.
    Use this to:
    - Set a custom retention period (1-365 days)
    - Enable/disable automatic cleanup
    - Configure safety thresholds

    Note: This operation requires appropriate permissions.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        user_id = user_info.get("id")  # For audit trail

        policy = await retention_service.create_retention_policy(
            tenant_id=tenant_id,
            retention_days=request.retention_days,
            is_enabled=request.is_enabled,
            min_executions_to_keep=request.min_executions_to_keep,
            created_by=user_id,
        )

        logger.info(
            f"Retention policy created/updated for tenant {tenant_id}: "
            f"{request.retention_days} days, enabled={request.is_enabled}"
        )

        return RetentionPolicyResponse(
            retention_days=policy.get("retention_days", request.retention_days),
            is_enabled=policy.get("is_enabled", request.is_enabled),
            min_executions_to_keep=policy.get("min_executions_to_keep", request.min_executions_to_keep),
            last_cleanup_at=policy.get("last_cleanup_at"),
            last_cleanup_deleted_count=policy.get("last_cleanup_deleted_count", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create retention policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create retention policy: {str(e)}"
        )


@router.patch("/policy", response_model=RetentionPolicyResponse)
async def update_retention_policy(
    request: UpdateRetentionPolicyRequest,
    user_info: dict = Depends(get_current_user)
):
    """
    Update specific fields of the execution retention policy for the authenticated tenant.

    Only updates the fields provided in the request (partial update).
    Use this to:
    - Adjust retention period without changing other settings
    - Enable/disable retention while preserving configuration
    - Update safety thresholds

    Note: At least one field must be provided.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        user_id = user_info.get("id")  # For audit trail

        # Validate that at least one field is provided
        if all(
            field is None
            for field in [request.retention_days, request.is_enabled, request.min_executions_to_keep]
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field must be provided for update"
            )

        policy = await retention_service.update_retention_policy(
            tenant_id=tenant_id,
            retention_days=request.retention_days,
            is_enabled=request.is_enabled,
            min_executions_to_keep=request.min_executions_to_keep,
            updated_by=user_id,
        )

        logger.info(f"Retention policy updated for tenant {tenant_id}")

        return RetentionPolicyResponse(
            retention_days=policy.get("retention_days", 90),
            is_enabled=policy.get("is_enabled", True),
            min_executions_to_keep=policy.get("min_executions_to_keep", 100),
            last_cleanup_at=policy.get("last_cleanup_at"),
            last_cleanup_deleted_count=policy.get("last_cleanup_deleted_count", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update retention policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update retention policy: {str(e)}"
        )


@router.get("/preview", response_model=CleanupPreviewResponse)
async def preview_cleanup(
    user_info: dict = Depends(get_current_user)
):
    """
    Preview what would be deleted by a retention cleanup operation without actually deleting.

    This is useful for:
    - Understanding the impact before enabling retention
    - Verifying retention settings are correct
    - Planning cleanup operations

    Returns:
    - Total execution count
    - Count of old executions (past retention period)
    - Count that would actually be deleted (respects min_executions_to_keep)
    - Cutoff date for retention
    - Current retention settings

    Note: No data is modified by this operation.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        preview = await retention_service.get_cleanup_preview(tenant_id)

        if "error" in preview:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate cleanup preview: {preview['error']}"
            )

        return CleanupPreviewResponse(
            tenant_id=preview["tenant_id"],
            total_executions=preview["total_executions"],
            old_executions_count=preview["old_executions_count"],
            executions_to_delete=preview["executions_to_delete"],
            cutoff_date=preview["cutoff_date"],
            retention_days=preview["retention_days"],
            min_executions_to_keep=preview["min_executions_to_keep"],
            would_delete=preview["would_delete"],
            is_enabled=preview["is_enabled"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to preview cleanup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview cleanup: {str(e)}"
        )


@router.post("/cleanup", response_model=CleanupResult)
async def trigger_cleanup(
    force: bool = Query(
        False,
        description="Force cleanup even if retention is disabled for this tenant"
    ),
    user_info: dict = Depends(get_current_user)
):
    """
    Manually trigger execution retention cleanup for the authenticated tenant.

    This operation:
    - Deletes executions older than the retention period
    - Respects the min_executions_to_keep safety threshold
    - Processes data in batches to avoid database locks
    - Updates the retention policy with cleanup metadata

    Parameters:
    - force: If true, runs cleanup even if retention is disabled (use with caution)

    Returns:
    - Number of executions deleted
    - Retention period used
    - Timestamp of cleanup
    - Detailed execution summary

    Note: This is typically run automatically on a schedule. Manual triggers are
    useful for immediate cleanup or testing retention policies.

    Warning: Deleted executions cannot be recovered. Consider using /preview first.
    """
    try:
        tenant_id = get_tenant_id(user_info)

        logger.info(
            f"Manual cleanup triggered for tenant {tenant_id} "
            f"(force={force}) by user {user_info.get('id')}"
        )

        result = await retention_service.cleanup_tenant_executions(
            tenant_id=tenant_id,
            force=force
        )

        if result.get("skipped"):
            logger.info(
                f"Cleanup skipped for tenant {tenant_id}: {result.get('reason')}"
            )
        elif result.get("error"):
            logger.error(
                f"Cleanup failed for tenant {tenant_id}: {result.get('error')}"
            )
        else:
            logger.info(
                f"Cleanup completed for tenant {tenant_id}: "
                f"deleted {result.get('deleted_count', 0)} executions"
            )

        return CleanupResult(
            tenant_id=result["tenant_id"],
            deleted_count=result.get("deleted_count", 0),
            retention_days=result["retention_days"],
            is_enabled=result["is_enabled"],
            timestamp=result["timestamp"],
            summary=result.get("summary"),
            skipped=result.get("skipped", False),
            reason=result.get("reason"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger cleanup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger cleanup: {str(e)}"
        )
