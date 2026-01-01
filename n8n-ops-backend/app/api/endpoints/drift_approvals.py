"""Drift Approvals API endpoints for Enterprise governance workflows."""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional

from app.services.auth_service import get_current_user
from app.services.database import db_service
from app.core.entitlements_gate import require_entitlement
from app.schemas.drift_policy import (
    DriftApprovalCreate,
    DriftApprovalDecision,
    DriftApprovalResponse,
    ApprovalStatus,
)

router = APIRouter()


@router.get("/", response_model=List[DriftApprovalResponse])
async def list_approvals(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    incident_id: Optional[str] = Query(None, description="Filter by incident"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("drift_policies")),
):
    """List drift approval requests for the tenant."""
    tenant_id = user_info["tenant"]["id"]

    try:
        query = db_service.client.table("drift_approvals").select(
            "*"
        ).eq("tenant_id", tenant_id)

        if status_filter:
            query = query.eq("status", status_filter)

        if incident_id:
            query = query.eq("incident_id", incident_id)

        response = query.order("created_at", desc=True).range(
            offset, offset + limit - 1
        ).execute()

        return [DriftApprovalResponse(**a) for a in (response.data or [])]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list approvals: {str(e)}",
        )


@router.get("/pending", response_model=List[DriftApprovalResponse])
async def list_pending_approvals(
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("drift_policies")),
):
    """List all pending approval requests for the tenant."""
    tenant_id = user_info["tenant"]["id"]

    try:
        response = db_service.client.table("drift_approvals").select(
            "*"
        ).eq("tenant_id", tenant_id).eq(
            "status", ApprovalStatus.pending.value
        ).order("created_at", desc=True).execute()

        return [DriftApprovalResponse(**a) for a in (response.data or [])]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list pending approvals: {str(e)}",
        )


@router.post("/", response_model=DriftApprovalResponse, status_code=status.HTTP_201_CREATED)
async def request_approval(
    payload: DriftApprovalCreate,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("drift_policies")),
):
    """Request approval for an action on a drift incident."""
    tenant_id = user_info["tenant"]["id"]
    user_id = user_info["user"]["id"]

    try:
        # Verify incident exists
        incident_response = db_service.client.table("drift_incidents").select(
            "id"
        ).eq("id", payload.incident_id).eq("tenant_id", tenant_id).execute()

        if not incident_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found",
            )

        # Check if there's already a pending approval for this action type
        existing = db_service.client.table("drift_approvals").select(
            "id"
        ).eq("incident_id", payload.incident_id).eq(
            "approval_type", payload.approval_type.value
        ).eq("status", ApprovalStatus.pending.value).execute()

        if existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A pending approval for '{payload.approval_type.value}' already exists",
            )

        now = datetime.utcnow().isoformat()

        approval_data = {
            "tenant_id": tenant_id,
            "incident_id": payload.incident_id,
            "approval_type": payload.approval_type.value,
            "status": ApprovalStatus.pending.value,
            "requested_by": user_id,
            "requested_at": now,
            "request_reason": payload.request_reason,
            "extension_hours": payload.extension_hours,
            "created_at": now,
            "updated_at": now,
        }

        response = db_service.client.table("drift_approvals").insert(
            approval_data
        ).execute()

        if response.data:
            return DriftApprovalResponse(**response.data[0])

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create approval request",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create approval request: {str(e)}",
        )


@router.get("/{approval_id}", response_model=DriftApprovalResponse)
async def get_approval(
    approval_id: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("drift_policies")),
):
    """Get a single approval request."""
    tenant_id = user_info["tenant"]["id"]

    try:
        response = db_service.client.table("drift_approvals").select(
            "*"
        ).eq("id", approval_id).eq("tenant_id", tenant_id).single().execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found",
            )

        return DriftApprovalResponse(**response.data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get approval: {str(e)}",
        )


@router.post("/{approval_id}/decide", response_model=DriftApprovalResponse)
async def decide_approval(
    approval_id: str,
    payload: DriftApprovalDecision,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("drift_policies")),
):
    """Approve or reject an approval request."""
    tenant_id = user_info["tenant"]["id"]
    user_id = user_info["user"]["id"]

    # Validate decision value
    if payload.decision not in [ApprovalStatus.approved, ApprovalStatus.rejected]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be 'approved' or 'rejected'",
        )

    try:
        # Get existing approval
        existing = db_service.client.table("drift_approvals").select(
            "*"
        ).eq("id", approval_id).eq("tenant_id", tenant_id).single().execute()

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found",
            )

        approval = existing.data

        if approval["status"] != ApprovalStatus.pending.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot decide on approval in '{approval['status']}' status",
            )

        # Cannot approve your own request
        if approval["requested_by"] == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot approve your own request",
            )

        now = datetime.utcnow().isoformat()

        update_data = {
            "status": payload.decision.value,
            "decided_by": user_id,
            "decided_at": now,
            "decision_notes": payload.decision_notes,
            "updated_at": now,
        }

        response = db_service.client.table("drift_approvals").update(
            update_data
        ).eq("id", approval_id).execute()

        if response.data:
            # If approved, execute the action based on approval type
            if payload.decision == ApprovalStatus.approved:
                await _execute_approved_action(
                    tenant_id=tenant_id,
                    incident_id=approval["incident_id"],
                    approval_type=approval["approval_type"],
                    extension_hours=approval.get("extension_hours"),
                    user_id=user_id,
                )

            return DriftApprovalResponse(**response.data[0])

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update approval",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decide on approval: {str(e)}",
        )


@router.post("/{approval_id}/cancel", response_model=DriftApprovalResponse)
async def cancel_approval(
    approval_id: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("drift_policies")),
):
    """Cancel a pending approval request (by requester only)."""
    tenant_id = user_info["tenant"]["id"]
    user_id = user_info["user"]["id"]

    try:
        # Get existing approval
        existing = db_service.client.table("drift_approvals").select(
            "*"
        ).eq("id", approval_id).eq("tenant_id", tenant_id).single().execute()

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found",
            )

        approval = existing.data

        if approval["status"] != ApprovalStatus.pending.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel approval in '{approval['status']}' status",
            )

        # Only requester or admin can cancel
        if approval["requested_by"] != user_id:
            user_role = user_info["user"].get("role", "viewer")
            if user_role not in ["admin", "super_admin"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the requester or an admin can cancel this request",
                )

        now = datetime.utcnow().isoformat()

        update_data = {
            "status": ApprovalStatus.cancelled.value,
            "updated_at": now,
        }

        response = db_service.client.table("drift_approvals").update(
            update_data
        ).eq("id", approval_id).execute()

        if response.data:
            return DriftApprovalResponse(**response.data[0])

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel approval",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel approval: {str(e)}",
        )


async def _execute_approved_action(
    tenant_id: str,
    incident_id: str,
    approval_type: str,
    extension_hours: Optional[int],
    user_id: str,
) -> None:
    """Execute the action after approval is granted."""
    from app.services.drift_incident_service import drift_incident_service

    now = datetime.utcnow()

    if approval_type == "acknowledge":
        await drift_incident_service.acknowledge_incident(
            tenant_id=tenant_id,
            incident_id=incident_id,
            user_id=user_id,
            reason="Approved via workflow",
        )

    elif approval_type == "extend_ttl":
        if extension_hours:
            from datetime import timedelta
            new_expiry = now + timedelta(hours=extension_hours)
            await drift_incident_service.update_incident(
                tenant_id=tenant_id,
                incident_id=incident_id,
                user_id=user_id,
                expires_at=new_expiry,
            )

    elif approval_type == "close":
        await drift_incident_service.close_incident(
            tenant_id=tenant_id,
            incident_id=incident_id,
            user_id=user_id,
            reason="Approved via workflow",
        )

    elif approval_type == "reconcile":
        # Reconciliation needs additional data, so we just acknowledge here
        # and let the user trigger reconciliation separately
        pass
