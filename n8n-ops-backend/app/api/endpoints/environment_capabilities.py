"""
Environment capabilities endpoint - returns what actions are allowed for an environment.
Used by the UI to show/hide action buttons.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any
from pydantic import BaseModel

from app.services.auth_service import get_current_user
from app.services.database import db_service
from app.services.environment_action_guard import (
    environment_action_guard,
    EnvironmentAction
)
from app.services.feature_service import feature_service
from app.schemas.environment import EnvironmentClass


router = APIRouter()


class EnvironmentCapabilitiesResponse(BaseModel):
    """Response model for environment capabilities"""
    environment_id: str
    environment_class: str
    capabilities: Dict[str, bool]
    policy_flags: Dict[str, bool]


@router.get("/{environment_id}/capabilities", response_model=EnvironmentCapabilitiesResponse)
async def get_environment_capabilities(
    environment_id: str,
    user_info: dict = Depends(get_current_user)
):
    """
    Get environment action capabilities.
    
    Returns which actions are allowed for the given environment based on:
    - Environment class (dev/staging/production)
    - User role (user/admin/superuser)
    - Organization policy flags
    - Subscription plan
    
    This endpoint is used by the UI to show/hide action buttons.
    """
    tenant = user_info.get("tenant", {})
    user = user_info.get("user", {})
    tenant_id = tenant.get("id")
    
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant not found in authentication context"
        )
    
    # Get environment
    env = await db_service.get_environment(environment_id, tenant_id)
    if not env:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Environment not found"
        )
    
    # Get environment class
    env_class_str = env.get("environment_class", "dev")
    try:
        env_class = EnvironmentClass(env_class_str)
    except ValueError:
        env_class = EnvironmentClass.DEV
    
    # Get user role and plan - use provider-scoped entitlements as source of truth
    user_role = user.get("role", "user")
    # Provider-scoped plan check with fallback to tenant.subscription_tier for backwards compatibility
    provider_entitlements = await feature_service.get_effective_entitlements(tenant_id, "n8n")
    plan = provider_entitlements.get("plan_name") or tenant.get("subscription_tier", "free")
    
    # Get org policy flags (from environment metadata or defaults)
    org_policy_flags = env.get("policy_flags", {}) or {}
    
    # Check all actions
    capabilities = {
        "sync_status": environment_action_guard.can_perform_action(
            env_class=env_class,
            action=EnvironmentAction.SYNC_STATUS,
            user_role=user_role,
            org_policy_flags=org_policy_flags,
            plan=plan
        ),
        "backup": environment_action_guard.can_perform_action(
            env_class=env_class,
            action=EnvironmentAction.BACKUP,
            user_role=user_role,
            org_policy_flags=org_policy_flags,
            plan=plan
        ),
        "manual_snapshot": environment_action_guard.can_perform_action(
            env_class=env_class,
            action=EnvironmentAction.MANUAL_SNAPSHOT,
            user_role=user_role,
            org_policy_flags=org_policy_flags,
            plan=plan
        ),
        "diff_compare": environment_action_guard.can_perform_action(
            env_class=env_class,
            action=EnvironmentAction.DIFF_COMPARE,
            user_role=user_role,
            org_policy_flags=org_policy_flags,
            plan=plan
        ),
        "restore_rollback": environment_action_guard.can_perform_action(
            env_class=env_class,
            action=EnvironmentAction.RESTORE_ROLLBACK,
            user_role=user_role,
            org_policy_flags=org_policy_flags,
            plan=plan
        ),
        "edit_in_n8n": environment_action_guard.can_perform_action(
            env_class=env_class,
            action=EnvironmentAction.EDIT_IN_N8N,
            user_role=user_role,
            org_policy_flags=org_policy_flags,
            plan=plan
        ),
    }
    
    return EnvironmentCapabilitiesResponse(
        environment_id=environment_id,
        environment_class=env_class.value,
        capabilities=capabilities,
        policy_flags=org_policy_flags
    )

