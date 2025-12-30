"""Admin audit log endpoints."""
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from enum import Enum

from app.services.database import db_service

router = APIRouter()


class AuditActionType(str, Enum):
    # Tenant actions
    TENANT_CREATED = "TENANT_CREATED"
    TENANT_UPDATED = "TENANT_UPDATED"
    TENANT_SUSPENDED = "TENANT_SUSPENDED"
    TENANT_REACTIVATED = "TENANT_REACTIVATED"
    TENANT_CANCELLED = "TENANT_CANCELLED"
    TENANT_DELETION_SCHEDULED = "TENANT_DELETION_SCHEDULED"
    TENANT_PLAN_CHANGED = "TENANT_PLAN_CHANGED"
    # User actions
    USER_CREATED = "USER_CREATED"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED"
    USER_DISABLED = "USER_DISABLED"
    USER_ENABLED = "USER_ENABLED"
    USER_DELETED = "USER_DELETED"
    # Feature actions
    FEATURE_OVERRIDE_ADDED = "FEATURE_OVERRIDE_ADDED"
    FEATURE_OVERRIDE_UPDATED = "FEATURE_OVERRIDE_UPDATED"
    FEATURE_OVERRIDE_REMOVED = "FEATURE_OVERRIDE_REMOVED"
    # Plan actions
    PLAN_CREATED = "PLAN_CREATED"
    PLAN_UPDATED = "PLAN_UPDATED"
    PLAN_DEPRECATED = "PLAN_DEPRECATED"
    # Billing actions
    SUBSCRIPTION_CREATED = "SUBSCRIPTION_CREATED"
    SUBSCRIPTION_CANCELLED = "SUBSCRIPTION_CANCELLED"
    SUBSCRIPTION_UPDATED = "SUBSCRIPTION_UPDATED"
    TRIAL_STARTED = "TRIAL_STARTED"
    TRIAL_EXTENDED = "TRIAL_EXTENDED"
    TRIAL_CANCELLED = "TRIAL_CANCELLED"
    # Settings actions
    SETTINGS_UPDATED = "SETTINGS_UPDATED"
    # Environment sync actions
    ENVIRONMENT_SYNC_STARTED = "ENVIRONMENT_SYNC_STARTED"
    ENVIRONMENT_SYNC_COMPLETED = "ENVIRONMENT_SYNC_COMPLETED"
    ENVIRONMENT_SYNC_FAILED = "ENVIRONMENT_SYNC_FAILED"
    # GitHub backup actions
    GITHUB_BACKUP_STARTED = "GITHUB_BACKUP_STARTED"
    GITHUB_BACKUP_COMPLETED = "GITHUB_BACKUP_COMPLETED"
    GITHUB_BACKUP_FAILED = "GITHUB_BACKUP_FAILED"
    # GitHub restore actions
    GITHUB_RESTORE_STARTED = "GITHUB_RESTORE_STARTED"
    GITHUB_RESTORE_COMPLETED = "GITHUB_RESTORE_COMPLETED"
    GITHUB_RESTORE_FAILED = "GITHUB_RESTORE_FAILED"
    # Deployment actions (already used but adding for completeness)
    DEPLOYMENT_CREATED = "DEPLOYMENT_CREATED"
    DEPLOYMENT_COMPLETED = "DEPLOYMENT_COMPLETED"
    DEPLOYMENT_FAILED = "DEPLOYMENT_FAILED"


class AuditLogResponse(BaseModel):
    id: str
    timestamp: datetime
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    actor_name: Optional[str] = None
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    action: str
    action_type: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    provider: Optional[str] = None  # Provider context (n8n, make) for provider-scoped actions
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    logs: List[AuditLogResponse]
    total: int
    page: int
    page_size: int


class AuditLogCreate(BaseModel):
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    action: str
    action_type: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    provider: Optional[str] = None  # Provider context for provider-scoped actions
    old_value: Optional[dict] = None
    new_value: Optional[dict] = None
    reason: Optional[str] = None
    metadata: Optional[dict] = None


async def create_audit_log(
    action_type: str,
    action: str,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    actor_name: Optional[str] = None,
    tenant_id: Optional[str] = None,
    tenant_name: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    provider: Optional[str] = None,  # Provider context for provider-scoped actions
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Create an audit log entry.

    Args:
        provider: Provider type (n8n, make) for provider-scoped actions.
                  Set to None for platform-scoped actions (tenant, user, plan, etc.)
    """
    try:
        log_data = {
            "action_type": action_type,
            "action": action,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "actor_name": actor_name,
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "resource_name": resource_name,
            "provider": provider,
            "old_value": old_value,
            "new_value": new_value,
            "reason": reason,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "metadata": metadata,
        }
        # Remove None values
        log_data = {k: v for k, v in log_data.items() if v is not None}

        response = db_service.client.table("audit_logs").insert(log_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        # Don't fail the main operation if audit logging fails
        print(f"Failed to create audit log: {e}")
        return None


@router.get("/", response_model=AuditLogListResponse)
async def get_audit_logs(
    start_date: Optional[datetime] = Query(None, description="Filter logs from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter logs until this date"),
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    provider: Optional[str] = Query(None, description="Filter by provider: n8n, make, platform (NULL), or all"),
    search: Optional[str] = Query(None, description="Search in action, resource_name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """Get audit logs with filtering and pagination.

    Provider filter values:
    - n8n: Show only n8n provider actions
    - make: Show only Make.com provider actions
    - platform: Show only platform-scoped actions (provider IS NULL)
    - all (or omit): Show all entries
    """
    try:
        # Build query
        query = db_service.client.table("audit_logs").select("*", count="exact")

        # Apply filters
        if start_date:
            query = query.gte("timestamp", start_date.isoformat())
        if end_date:
            query = query.lte("timestamp", end_date.isoformat())
        if actor_id:
            query = query.eq("actor_id", actor_id)
        if action_type:
            query = query.eq("action_type", action_type)
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        if resource_type:
            query = query.eq("resource_type", resource_type)

        # Provider filter
        if provider and provider != "all":
            if provider == "platform":
                query = query.is_("provider", "null")
            else:
                query = query.eq("provider", provider)

        if search:
            query = query.or_(f"action.ilike.%{search}%,resource_name.ilike.%{search}%,actor_email.ilike.%{search}%")

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order("timestamp", desc=True).range(offset, offset + page_size - 1)

        response = query.execute()

        logs = [AuditLogResponse(**log) for log in (response.data or [])]
        total = response.count or 0

        return AuditLogListResponse(
            logs=logs,
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch audit logs: {str(e)}"
        )


@router.get("/action-types")
async def get_action_types():
    """Get list of all action types for filtering."""
    return {"action_types": [e.value for e in AuditActionType]}


@router.get("/stats")
async def get_audit_stats():
    """Get audit log statistics."""
    try:
        # Get total count
        total_response = db_service.client.table("audit_logs").select("id", count="exact").execute()
        total = total_response.count or 0

        # Get counts by action type (last 30 days)
        thirty_days_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        thirty_days_ago = thirty_days_ago.replace(day=thirty_days_ago.day - 30 if thirty_days_ago.day > 30 else 1)

        recent_response = db_service.client.table("audit_logs").select(
            "action_type"
        ).gte("timestamp", thirty_days_ago.isoformat()).execute()

        # Count by action type
        action_counts = {}
        for log in (recent_response.data or []):
            action_type = log.get("action_type", "unknown")
            action_counts[action_type] = action_counts.get(action_type, 0) + 1

        return {
            "total": total,
            "last_30_days": len(recent_response.data or []),
            "by_action_type": action_counts,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch audit stats: {str(e)}"
        )


@router.post("/export")
async def export_audit_logs(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    action_type: Optional[str] = Query(None),
    tenant_id: Optional[str] = Query(None),
    provider: Optional[str] = Query(None, description="Filter by provider: n8n, make, platform, or all"),
):
    """Export audit logs as JSON (for CSV conversion on frontend)."""
    try:
        query = db_service.client.table("audit_logs").select("*")

        if start_date:
            query = query.gte("timestamp", start_date.isoformat())
        if end_date:
            query = query.lte("timestamp", end_date.isoformat())
        if action_type:
            query = query.eq("action_type", action_type)
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)

        # Provider filter
        if provider and provider != "all":
            if provider == "platform":
                query = query.is_("provider", "null")
            else:
                query = query.eq("provider", provider)

        query = query.order("timestamp", desc=True).limit(10000)

        response = query.execute()

        return {"logs": response.data or [], "count": len(response.data or [])}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export audit logs: {str(e)}"
        )
