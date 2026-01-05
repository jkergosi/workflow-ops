"""
Admin Overview Endpoint

Provides admin dashboard overview data for Pro+ tenants.
Returns org health, usage, and governance signals.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.services.database import db_service
from app.services.auth_service import get_current_user
from app.services.entitlements_service import entitlements_service

router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================

class CredentialHealth(BaseModel):
    """Credential health counts."""
    healthy: int = 0
    warning: int = 0
    failing: int = 0


class UsageMetric(BaseModel):
    """Usage metric with used and limit values."""
    used: int = 0
    limit: Optional[int] = None


class UsageData(BaseModel):
    """All usage metrics."""
    executions: UsageMetric = UsageMetric()
    workflows: UsageMetric = UsageMetric()
    snapshots: UsageMetric = UsageMetric()
    pipelines: UsageMetric = UsageMetric()


class AdminOverviewResponse(BaseModel):
    """Admin dashboard overview response."""
    environment_count: int = 0
    environment_limit: Optional[int] = None
    credential_health: CredentialHealth = CredentialHealth()
    failed_executions_24h: int = 0
    drift_detected_count: int = 0
    usage: UsageData = UsageData()


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/overview", response_model=AdminOverviewResponse)
async def get_admin_overview(user_info: dict = Depends(get_current_user)):
    """
    Get admin dashboard overview for the current tenant.

    Returns org health tiles, usage pressure data, and governance signals.
    Requires Pro or higher plan.
    """
    tenant = user_info.get("tenant")
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant information not found"
        )

    tenant_id = tenant.get("id")
    subscription_tier = tenant.get("subscription_tier", "free")

    # Check plan - only Pro+ can access
    if subscription_tier == "free":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin Dashboard requires Pro or higher plan"
        )

    try:
        # Get entitlements for limits
        entitlements = await entitlements_service.get_tenant_entitlements(tenant_id)
        features = entitlements.get("features", {})

        # Environment count and limit
        env_response = db_service.client.table("environments").select(
            "id", count="exact"
        ).eq("tenant_id", tenant_id).execute()
        environment_count = env_response.count or 0
        environment_limit = features.get("max_environments")
        if environment_limit == -1 or environment_limit == "unlimited":
            environment_limit = None

        # Credential health
        credential_health = CredentialHealth()
        try:
            creds_response = db_service.client.table("credentials").select(
                "id, health_status"
            ).eq("tenant_id", tenant_id).execute()

            if creds_response.data:
                for cred in creds_response.data:
                    health = cred.get("health_status", "unknown")
                    if health == "healthy" or health == "ok":
                        credential_health.healthy += 1
                    elif health == "warning":
                        credential_health.warning += 1
                    elif health in ("failing", "error", "failed"):
                        credential_health.failing += 1
                    else:
                        # Unknown status counts as healthy
                        credential_health.healthy += 1
        except Exception:
            # If credentials table doesn't have health_status, just count total
            pass

        # Failed executions in last 24 hours
        failed_executions_24h = 0
        try:
            cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            failed_response = db_service.client.table("executions").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).eq(
                "status", "failed"
            ).gte("started_at", cutoff).execute()
            failed_executions_24h = failed_response.count or 0
        except Exception:
            pass

        # Drift detected count
        drift_detected_count = 0
        try:
            # Check for environments with drift detected
            drift_response = db_service.client.table("environments").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).eq(
                "drift_detected", True
            ).execute()
            drift_detected_count = drift_response.count or 0
        except Exception:
            # Fall back to checking drift incidents
            try:
                incidents_response = db_service.client.table("drift_incidents").select(
                    "id", count="exact"
                ).eq("tenant_id", tenant_id).eq(
                    "status", "open"
                ).execute()
                drift_detected_count = incidents_response.count or 0
            except Exception:
                pass

        # Usage data
        usage = UsageData()

        # Workflows count from canonical system
        try:
            # Count unique canonical workflows
            mappings_response = await db_service.client.table("workflow_env_map").select("canonical_id").eq("tenant_id", tenant_id).execute()
            unique_canonical_ids = set()
            for mapping in (mappings_response.data or []):
                cid = mapping.get("canonical_id")
                if cid:
                    unique_canonical_ids.add(cid)
            workflows_used = len(unique_canonical_ids)
            workflows_limit = features.get("max_workflows")
            if workflows_limit == -1 or workflows_limit == "unlimited":
                workflows_limit = None
            usage.workflows = UsageMetric(used=workflows_used, limit=workflows_limit)
        except Exception:
            pass

        # Executions count (this month)
        try:
            month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            exec_response = db_service.client.table("executions").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).gte(
                "started_at", month_start.isoformat()
            ).execute()
            executions_used = exec_response.count or 0
            executions_limit = features.get("max_monthly_executions")
            if executions_limit == -1 or executions_limit == "unlimited":
                executions_limit = None
            usage.executions = UsageMetric(used=executions_used, limit=executions_limit)
        except Exception:
            pass

        # Snapshots count
        try:
            snapshots_response = db_service.client.table("snapshots").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            snapshots_used = snapshots_response.count or 0
            snapshots_limit = features.get("max_snapshots")
            if snapshots_limit == -1 or snapshots_limit == "unlimited":
                snapshots_limit = None
            usage.snapshots = UsageMetric(used=snapshots_used, limit=snapshots_limit)
        except Exception:
            pass

        # Pipelines count
        try:
            pipelines_response = db_service.client.table("pipelines").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            pipelines_used = pipelines_response.count or 0
            pipelines_limit = features.get("max_pipelines")
            if pipelines_limit == -1 or pipelines_limit == "unlimited":
                pipelines_limit = None
            usage.pipelines = UsageMetric(used=pipelines_used, limit=pipelines_limit)
        except Exception:
            pass

        return AdminOverviewResponse(
            environment_count=environment_count,
            environment_limit=environment_limit,
            credential_health=credential_health,
            failed_executions_24h=failed_executions_24h,
            drift_detected_count=drift_detected_count,
            usage=usage
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Admin overview error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch admin overview: {str(e)}"
        )
