"""
Workflow Action Policy endpoint - returns what actions are allowed for a given environment.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.workflow_policy import (
    EnvironmentClass,
    WorkflowPolicyResponse,
    build_policy
)
from app.services.database import db_service
from app.services.auth_service import get_current_user
from app.services.feature_service import feature_service

router = APIRouter()


@router.get("/policy/{environment_id}", response_model=WorkflowPolicyResponse)
async def get_workflow_action_policy(
    environment_id: str,
    user_info: dict = Depends(get_current_user)
) -> WorkflowPolicyResponse:
    """
    Get the workflow action policy for an environment.

    Returns what actions are allowed based on environment class, plan, and role.
    This is used by the frontend to show/hide action buttons in the UI.

    The policy is computed server-side to ensure consistent enforcement.
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

    # Get tenant plan and user role - use plan_resolver as single source of truth
    role = user.get("role", "user")
    # Use plan_resolver (queries tenant_provider_subscriptions) as single source of truth
    from app.services.plan_resolver import resolve_effective_plan
    resolved = await resolve_effective_plan(tenant_id)
    plan = resolved.get("plan_name", "free")

    # Use environment_class from DB - NEVER infer at runtime
    env_class_str = env.get("environment_class", "dev")
    try:
        env_class = EnvironmentClass(env_class_str)
    except ValueError:
        env_class = EnvironmentClass.DEV  # Safe fallback

    # Build policy
    policy = await build_policy(env_class, plan, role)

    return WorkflowPolicyResponse(
        environment_id=environment_id,
        environment_class=env_class,
        plan=plan,
        role=role,
        policy=policy
    )


@router.get("/policy/{environment_id}/workflow/{workflow_id}", response_model=WorkflowPolicyResponse)
async def get_workflow_specific_policy(
    environment_id: str,
    workflow_id: str,
    user_info: dict = Depends(get_current_user)
) -> WorkflowPolicyResponse:
    """
    Get the workflow action policy for a specific workflow.

    This version considers the workflow's drift state to determine
    whether drift incident creation is applicable.
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

    # Get workflow to check drift state
    workflow = await db_service.get_workflow(tenant_id, environment_id, workflow_id)
    has_drift = False
    if workflow:
        sync_status = workflow.get("sync_status", "in_sync")
        has_drift = sync_status in ["local_changes", "conflict"]

    # Get tenant plan and user role - use plan_resolver as single source of truth
    role = user.get("role", "user")
    # Use plan_resolver (queries tenant_provider_subscriptions) as single source of truth
    from app.services.plan_resolver import resolve_effective_plan
    resolved = await resolve_effective_plan(tenant_id)
    plan = resolved.get("plan_name", "free")

    # Use environment_class from DB
    env_class_str = env.get("environment_class", "dev")
    try:
        env_class = EnvironmentClass(env_class_str)
    except ValueError:
        env_class = EnvironmentClass.DEV

    # Build policy with drift state
    policy = build_policy(env_class, plan, role, has_drift=has_drift)

    return WorkflowPolicyResponse(
        environment_id=environment_id,
        environment_class=env_class,
        plan=plan,
        role=role,
        policy=policy
    )
