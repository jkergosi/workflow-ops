"""
Canonical WorkflowActionPolicy schema - used by both frontend and backend.
Field names must match TypeScript interface in types/index.ts

This is the single source of truth for workflow action policies.
"""
from pydantic import BaseModel
from enum import Enum
from typing import Optional, Dict, Any


class EnvironmentClass(str, Enum):
    """Deterministic environment class for policy enforcement"""
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class WorkflowActionPolicy(BaseModel):
    """
    Canonical policy schema - matches frontend exactly.

    Field naming: Use snake_case for backend, frontend converts to camelCase as needed.
    """
    can_view_details: bool = True
    can_open_in_n8n: bool = True
    can_create_deployment: bool = True
    can_edit_directly: bool = False
    can_soft_delete: bool = False       # Archive workflow
    can_hard_delete: bool = False       # Permanently remove (admin-only)
    can_create_drift_incident: bool = False
    drift_incident_required: bool = False
    edit_requires_confirmation: bool = True
    edit_requires_admin: bool = False


class WorkflowPolicyResponse(BaseModel):
    """Response model for workflow policy endpoint"""
    environment_id: str
    environment_class: EnvironmentClass
    plan: str
    role: str
    policy: WorkflowActionPolicy


# Cache for policy matrix
_policy_matrix_cache: Dict[str, WorkflowActionPolicy] = {}
_policy_overrides_cache: Dict[str, Dict[str, Any]] = {}


async def _get_policy_matrix(env_class: EnvironmentClass) -> WorkflowActionPolicy:
    """Get policy matrix for environment class from database."""
    env_class_str = env_class.value
    
    # Check cache first
    if env_class_str in _policy_matrix_cache:
        return _policy_matrix_cache[env_class_str]
    
    # Fetch from database
    try:
        from app.services.database import db_service
        response = db_service.client.table("workflow_policy_matrix").select("*").eq(
            "environment_class", env_class_str
        ).single().execute()
        
        if response.data:
            data = response.data
            policy = WorkflowActionPolicy(
                can_view_details=data.get("can_view_details", True),
                can_open_in_n8n=data.get("can_open_in_n8n", True),
                can_create_deployment=data.get("can_create_deployment", True),
                can_edit_directly=data.get("can_edit_directly", False),
                can_soft_delete=data.get("can_soft_delete", False),
                can_hard_delete=data.get("can_hard_delete", False),
                can_create_drift_incident=data.get("can_create_drift_incident", False),
                drift_incident_required=data.get("drift_incident_required", False),
                edit_requires_confirmation=data.get("edit_requires_confirmation", True),
                edit_requires_admin=data.get("edit_requires_admin", False),
            )
            _policy_matrix_cache[env_class_str] = policy
            return policy
    except Exception:
        pass
    
    # Fallback to default
    defaults = {
        EnvironmentClass.DEV.value: WorkflowActionPolicy(
            can_view_details=True,
            can_open_in_n8n=True,
            can_create_deployment=True,
            can_edit_directly=True,
            can_soft_delete=True,
            can_hard_delete=False,
            can_create_drift_incident=True,
            drift_incident_required=False,
            edit_requires_confirmation=True,
            edit_requires_admin=False,
        ),
        EnvironmentClass.STAGING.value: WorkflowActionPolicy(
            can_view_details=True,
            can_open_in_n8n=True,
            can_create_deployment=True,
            can_edit_directly=True,
            can_soft_delete=False,
            can_hard_delete=False,
            can_create_drift_incident=True,
            drift_incident_required=False,
            edit_requires_confirmation=True,
            edit_requires_admin=True,
        ),
        EnvironmentClass.PRODUCTION.value: WorkflowActionPolicy(
            can_view_details=True,
            can_open_in_n8n=True,
            can_create_deployment=True,
            can_edit_directly=False,
            can_soft_delete=False,
            can_hard_delete=False,
            can_create_drift_incident=True,
            drift_incident_required=True,
            edit_requires_confirmation=False,
            edit_requires_admin=False,
        ),
    }
    default_policy = defaults.get(env_class_str, defaults[EnvironmentClass.DEV.value])
    _policy_matrix_cache[env_class_str] = default_policy
    return default_policy


async def _get_plan_policy_override(plan_name: str, env_class: EnvironmentClass) -> Optional[Dict[str, Any]]:
    """Get plan-based policy override from database."""
    cache_key = f"{plan_name.lower()}:{env_class.value}"
    
    # Check cache first
    if cache_key in _policy_overrides_cache:
        return _policy_overrides_cache[cache_key]
    
    # Fetch from database
    try:
        from app.services.database import db_service
        response = db_service.client.table("plan_policy_overrides").select("*").eq(
            "plan_name", plan_name.lower()
        ).eq("environment_class", env_class.value).single().execute()
        
        if response.data:
            override = {
                "can_edit_directly": response.data.get("can_edit_directly"),
                "can_soft_delete": response.data.get("can_soft_delete"),
                "can_hard_delete": response.data.get("can_hard_delete"),
                "can_create_drift_incident": response.data.get("can_create_drift_incident"),
                "drift_incident_required": response.data.get("drift_incident_required"),
                "edit_requires_confirmation": response.data.get("edit_requires_confirmation"),
                "edit_requires_admin": response.data.get("edit_requires_admin"),
            }
            # Remove None values
            override = {k: v for k, v in override.items() if v is not None}
            _policy_overrides_cache[cache_key] = override
            return override
    except Exception:
        pass
    
    _policy_overrides_cache[cache_key] = None
    return None


async def build_policy(
    env_class: EnvironmentClass,
    plan: str,
    role: str,
    has_drift: bool = False
) -> WorkflowActionPolicy:
    """
    Build policy based on environment class, plan, and role.

    Args:
        env_class: The environment classification (dev/staging/production)
        plan: The tenant's subscription plan (free/pro/agency/enterprise)
        role: The user's role (user/admin/superuser)
        has_drift: Whether the workflow has drift

    Returns:
        WorkflowActionPolicy with all permissions computed
    """
    # Get base policy from database
    base = await _get_policy_matrix(env_class)

    # Create a mutable copy
    policy = WorkflowActionPolicy(
        can_view_details=base.can_view_details,
        can_open_in_n8n=base.can_open_in_n8n,
        can_create_deployment=base.can_create_deployment,
        can_edit_directly=base.can_edit_directly,
        can_soft_delete=base.can_soft_delete,
        can_hard_delete=base.can_hard_delete,
        can_create_drift_incident=base.can_create_drift_incident,
        drift_incident_required=base.drift_incident_required,
        edit_requires_confirmation=base.edit_requires_confirmation,
        edit_requires_admin=base.edit_requires_admin,
    )

    plan_lower = plan.lower()
    is_agency_plus = plan_lower in ['agency', 'enterprise']
    is_admin = role in ['admin', 'superuser']

    # =============================================
    # PLAN-BASED RESTRICTIONS (from database)
    # =============================================
    
    # Get plan-based overrides from database
    plan_override = await _get_plan_policy_override(plan_lower, env_class)
    if plan_override:
        if "can_edit_directly" in plan_override:
            policy.can_edit_directly = plan_override["can_edit_directly"]
        if "can_soft_delete" in plan_override:
            policy.can_soft_delete = plan_override["can_soft_delete"]
        if "can_hard_delete" in plan_override:
            policy.can_hard_delete = plan_override["can_hard_delete"]
        if "can_create_drift_incident" in plan_override:
            policy.can_create_drift_incident = plan_override["can_create_drift_incident"]
        if "drift_incident_required" in plan_override:
            policy.drift_incident_required = plan_override["drift_incident_required"]
        if "edit_requires_confirmation" in plan_override:
            policy.edit_requires_confirmation = plan_override["edit_requires_confirmation"]
        if "edit_requires_admin" in plan_override:
            policy.edit_requires_admin = plan_override["edit_requires_admin"]
    
    # Fallback to hard-coded logic if no database override (for backward compatibility)
    if not plan_override:
        # Free tier: No drift incident workflow at all
        if plan_lower == 'free':
            policy.can_create_drift_incident = False
            policy.drift_incident_required = False

        # Pro tier: Drift incidents optional (not required)
        if plan_lower == 'pro':
            policy.drift_incident_required = False

        # Agency+: Drift incidents required by default in staging/production
        if is_agency_plus:
            if env_class == EnvironmentClass.STAGING:
                policy.can_edit_directly = False  # Even stricter for agency+
                policy.drift_incident_required = True
            # Production already has drift_incident_required = True

    # =============================================
    # ROLE-BASED RESTRICTIONS
    # =============================================

    # Admin-gated actions
    if policy.edit_requires_admin and not is_admin:
        policy.can_edit_directly = False

    # Hard delete: Admin-only in dev, never elsewhere
    if env_class == EnvironmentClass.DEV and is_admin:
        policy.can_hard_delete = True  # Unlocks "Permanently delete" option

    # =============================================
    # DRIFT STATE RESTRICTIONS
    # =============================================

    # Drift incident only if drift exists
    if not has_drift:
        policy.can_create_drift_incident = False
        policy.drift_incident_required = False

    return policy
