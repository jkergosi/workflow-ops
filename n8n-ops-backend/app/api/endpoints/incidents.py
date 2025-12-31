"""Drift Incidents API endpoints with full lifecycle management."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional

from app.services.auth_service import get_current_user
from app.services.feature_service import feature_service
from app.services.drift_incident_service import drift_incident_service
from app.schemas.drift_incident import (
    DriftIncidentCreate,
    DriftIncidentUpdate,
    DriftIncidentResponse,
    DriftIncidentListResponse,
    DriftIncidentAcknowledge,
    DriftIncidentResolve,
    DriftIncidentStatus,
)

router = APIRouter()


@router.get("/", response_model=DriftIncidentListResponse)
async def list_incidents(
    environment_id: Optional[str] = Query(None, description="Filter by environment"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_info: dict = Depends(get_current_user),
):
    """List drift incidents for the tenant."""
    tenant_id = user_info["tenant"]["id"]

    # Check feature access for drift incidents
    can_use, message = await feature_service.can_use_feature(tenant_id, "drift_incidents")
    if not can_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "drift_incidents",
                "message": message,
            },
        )

    result = await drift_incident_service.get_incidents(
        tenant_id=tenant_id,
        environment_id=environment_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )

    return DriftIncidentListResponse(
        items=[DriftIncidentResponse(**item) for item in result["items"]],
        total=result["total"],
        has_more=result["has_more"],
    )


@router.post("/", response_model=DriftIncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: DriftIncidentCreate,
    user_info: dict = Depends(get_current_user),
):
    """Create a new drift incident."""
    tenant_id = user_info["tenant"]["id"]
    user_id = user_info["user"]["id"]

    # Check feature access
    can_use, message = await feature_service.can_use_feature(tenant_id, "drift_incidents")
    if not can_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "drift_incidents",
                "message": message,
            },
        )

    # Check drift mode enforcement - incidents cannot be created in passive mode
    from app.core.drift_mode import DriftMode, get_drift_mode_for_plan, can_create_drift_incident
    from app.services.database import db_service
    
    # Get environment to check drift_handling_mode
    environment = await db_service.get_environment(payload.environment_id, tenant_id)
    if not environment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Environment not found"
        )
    
    # Get tenant plan from subscription
    subscription = await feature_service.get_tenant_subscription(tenant_id)
    plan_name = subscription.get("plan", {}).get("name", "free").lower() if subscription else "free"
    
    # Determine drift mode: use environment setting if set, otherwise plan default
    env_drift_mode_str = environment.get("drift_handling_mode")
    if env_drift_mode_str:
        try:
            drift_mode = DriftMode(env_drift_mode_str.lower())
        except ValueError:
            # Invalid drift mode, fall back to plan default
            drift_mode = get_drift_mode_for_plan(plan_name)
    else:
        # No environment setting, use plan default
        drift_mode = get_drift_mode_for_plan(plan_name)
    
    # Enforce: cannot create incidents in passive mode
    if not can_create_drift_incident(drift_mode):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "drift_mode_restriction",
                "message": f"Drift incidents cannot be created in {drift_mode.value} mode. Upgrade to Agency or Enterprise plan to enable drift incident management.",
                "drift_mode": drift_mode.value,
                "required_mode": "managed or enforced"
            },
        )

    incident = await drift_incident_service.create_incident(
        tenant_id=tenant_id,
        environment_id=payload.environment_id,
        user_id=user_id,
        title=payload.title,
        affected_workflows=payload.affected_workflows,
        drift_snapshot=payload.drift_snapshot,
        severity=payload.severity,
    )

    return DriftIncidentResponse(**incident)


@router.get("/stats")
async def get_incident_stats(
    environment_id: Optional[str] = Query(None, description="Filter by environment"),
    user_info: dict = Depends(get_current_user),
):
    """Get drift incident statistics."""
    tenant_id = user_info["tenant"]["id"]

    # Stats are available even without full drift_incidents feature
    stats = await drift_incident_service.get_incident_stats(
        tenant_id=tenant_id,
        environment_id=environment_id,
    )

    return stats


@router.get("/{incident_id}", response_model=DriftIncidentResponse)
async def get_incident(
    incident_id: str,
    user_info: dict = Depends(get_current_user),
):
    """Get a single drift incident."""
    tenant_id = user_info["tenant"]["id"]

    # Check feature access
    can_use, message = await feature_service.can_use_feature(tenant_id, "drift_incidents")
    if not can_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "drift_incidents",
                "message": message,
            },
        )

    incident = await drift_incident_service.get_incident(tenant_id, incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return DriftIncidentResponse(**incident)


@router.patch("/{incident_id}", response_model=DriftIncidentResponse)
async def update_incident(
    incident_id: str,
    payload: DriftIncidentUpdate,
    user_info: dict = Depends(get_current_user),
):
    """Update drift incident fields (not status transitions)."""
    tenant_id = user_info["tenant"]["id"]
    user_id = user_info["user"]["id"]

    # Check feature access
    can_use, message = await feature_service.can_use_feature(tenant_id, "drift_incidents")
    if not can_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "drift_incidents",
                "message": message,
            },
        )

    incident = await drift_incident_service.update_incident(
        tenant_id=tenant_id,
        incident_id=incident_id,
        user_id=user_id,
        title=payload.title,
        owner_user_id=payload.owner_user_id,
        reason=payload.reason,
        ticket_ref=payload.ticket_ref,
        expires_at=payload.expires_at,
        severity=payload.severity,
    )

    return DriftIncidentResponse(**incident)


@router.post("/{incident_id}/acknowledge", response_model=DriftIncidentResponse)
async def acknowledge_incident(
    incident_id: str,
    payload: DriftIncidentAcknowledge,
    user_info: dict = Depends(get_current_user),
):
    """Acknowledge a drift incident."""
    tenant_id = user_info["tenant"]["id"]
    user_id = user_info["user"]["id"]

    # Check feature access
    can_use, message = await feature_service.can_use_feature(tenant_id, "drift_incidents")
    if not can_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "drift_incidents",
                "message": message,
            },
        )

    incident = await drift_incident_service.acknowledge_incident(
        tenant_id=tenant_id,
        incident_id=incident_id,
        user_id=user_id,
        reason=payload.reason,
        owner_user_id=payload.owner_user_id,
        ticket_ref=payload.ticket_ref,
        expires_at=payload.expires_at,
    )

    return DriftIncidentResponse(**incident)


@router.post("/{incident_id}/stabilize", response_model=DriftIncidentResponse)
async def stabilize_incident(
    incident_id: str,
    reason: Optional[str] = None,
    user_info: dict = Depends(get_current_user),
):
    """Mark incident as stabilized (no new drift changes)."""
    tenant_id = user_info["tenant"]["id"]
    user_id = user_info["user"]["id"]

    # Check feature access
    can_use, message = await feature_service.can_use_feature(tenant_id, "drift_incidents")
    if not can_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "drift_incidents",
                "message": message,
            },
        )

    incident = await drift_incident_service.stabilize_incident(
        tenant_id=tenant_id,
        incident_id=incident_id,
        user_id=user_id,
        reason=reason,
    )

    return DriftIncidentResponse(**incident)


@router.post("/{incident_id}/reconcile", response_model=DriftIncidentResponse)
async def reconcile_incident(
    incident_id: str,
    payload: DriftIncidentResolve,
    user_info: dict = Depends(get_current_user),
):
    """Reconcile a drift incident with resolution tracking."""
    tenant_id = user_info["tenant"]["id"]
    user_id = user_info["user"]["id"]

    # Check feature access
    can_use, message = await feature_service.can_use_feature(tenant_id, "drift_incidents")
    if not can_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "drift_incidents",
                "message": message,
            },
        )

    incident = await drift_incident_service.reconcile_incident(
        tenant_id=tenant_id,
        incident_id=incident_id,
        user_id=user_id,
        resolution_type=payload.resolution_type,
        reason=payload.reason,
        resolution_details=payload.resolution_details,
    )

    return DriftIncidentResponse(**incident)


@router.post("/{incident_id}/close", response_model=DriftIncidentResponse)
async def close_incident(
    incident_id: str,
    reason: Optional[str] = None,
    user_info: dict = Depends(get_current_user),
):
    """Close a drift incident."""
    tenant_id = user_info["tenant"]["id"]
    user_id = user_info["user"]["id"]

    # Check feature access
    can_use, message = await feature_service.can_use_feature(tenant_id, "drift_incidents")
    if not can_use:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "feature_not_available",
                "feature": "drift_incidents",
                "message": message,
            },
        )

    incident = await drift_incident_service.close_incident(
        tenant_id=tenant_id,
        incident_id=incident_id,
        user_id=user_id,
        reason=reason,
    )

    return DriftIncidentResponse(**incident)


@router.get("/environment/{environment_id}/active", response_model=Optional[DriftIncidentResponse])
async def get_active_incident(
    environment_id: str,
    user_info: dict = Depends(get_current_user),
):
    """Get the active drift incident for an environment."""
    tenant_id = user_info["tenant"]["id"]

    # This endpoint works even without full drift_incidents feature
    # as it's used by the environment detail page
    incident = await drift_incident_service.get_active_incident_for_environment(
        tenant_id=tenant_id,
        environment_id=environment_id,
    )

    if not incident:
        return None

    return DriftIncidentResponse(**incident)
