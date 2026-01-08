from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from app.services.database import db_service
from app.core.platform_admin import require_platform_admin, is_platform_admin
from app.api.endpoints.admin_audit import create_audit_log


router = APIRouter()

# Migration: 9ed964cd8ba3 - create_platform_impersonation_sessions
# See: alembic/versions/9ed964cd8ba3_create_platform_impersonation_sessions.py


class StartImpersonationRequest(BaseModel):
    target_user_id: str


class StartImpersonationResponse(BaseModel):
    impersonating: bool
    success: bool


@router.post("/impersonate", response_model=StartImpersonationResponse)
async def start_impersonation(
    body: StartImpersonationRequest,
    user_info: dict = Depends(require_platform_admin()),
):
    actor = (user_info or {}).get("user") or {}
    actor_id = actor.get("id")
    if not actor_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    target_user_id = body.target_user_id

    # Load target user (must exist)
    target_resp = db_service.client.table("users").select("id, email, name, role, tenant_id").eq("id", target_user_id).maybe_single().execute()
    target = target_resp.data
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    tenant_id = target.get("tenant_id")

    # Guardrail: never impersonate another platform admin
    if is_platform_admin(target_user_id):
        await create_audit_log(
            action_type="IMPERSONATION_BLOCKED",
            action=f"Blocked impersonation attempt for platform admin user_id={target_user_id}",
            actor_id=actor_id,
            actor_email=actor.get("email"),
            actor_name=actor.get("name"),
            tenant_id=tenant_id,
            resource_type="impersonation",
            resource_id=target_user_id,
            metadata={"target_user_id": target_user_id, "reason": "target_is_platform_admin"},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot impersonate another Platform Admin")

    # End any existing active session for this actor (no nested impersonation)
    db_service.client.table("platform_impersonation_sessions").update(
        {"ended_at": datetime.utcnow().isoformat()}
    ).eq("actor_user_id", actor_id).is_("ended_at", "null").execute()

    session_id = str(uuid.uuid4())
    db_service.client.table("platform_impersonation_sessions").insert(
        {
            "id": session_id,
            "actor_user_id": actor_id,
            "impersonated_user_id": target_user_id,
            "impersonated_tenant_id": tenant_id,
        }
    ).execute()

    await create_audit_log(
        action_type="impersonation.start",
        action=f"Started impersonation for user_id={target_user_id}",
        actor_id=actor_id,
        actor_email=actor.get("email"),
        actor_name=actor.get("name"),
        tenant_id=tenant_id,
        resource_type="impersonation",
        resource_id=session_id,
        metadata={"target_user_id": target_user_id, "tenant_id": tenant_id},
    )

    return StartImpersonationResponse(
        impersonating=True,
        success=True,
    )


@router.post("/impersonate/stop")
async def stop_impersonation(
    user_info: dict = Depends(require_platform_admin(allow_when_impersonating=True)),
):
    impersonating = bool((user_info or {}).get("impersonating"))
    if not impersonating:
        return {"success": True, "message": "Not currently impersonating"}

    session_id = (user_info or {}).get("impersonation_session_id")
    actor = (user_info or {}).get("actor_user") or {}
    tenant = (user_info or {}).get("tenant") or {}
    user = (user_info or {}).get("user") or {}

    if session_id:
        db_service.client.table("platform_impersonation_sessions").update({"ended_at": datetime.utcnow().isoformat()}).eq("id", session_id).execute()
    elif actor.get("id"):
        db_service.client.table("platform_impersonation_sessions").update({"ended_at": datetime.utcnow().isoformat()}).eq("actor_user_id", actor.get("id")).is_("ended_at", "null").execute()

    await create_audit_log(
        action_type="impersonation.stop",
        action=f"Stopped impersonation session_id={session_id}",
        actor_id=actor.get("id"),
        actor_email=actor.get("email"),
        actor_name=actor.get("name"),
        tenant_id=tenant.get("id"),
        resource_type="impersonation",
        resource_id=session_id,
        metadata={"target_user_id": user.get("id"), "tenant_id": tenant.get("id")},
    )

    return {"success": True, "message": "Impersonation ended"}


