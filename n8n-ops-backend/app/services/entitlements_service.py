"""Entitlements service for plan-based feature access (Phase 1 + Phase 3 Overrides)."""
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import HTTPException, status
from datetime import datetime, timezone
import logging

from app.services.database import db_service
from app.services.tenant_plan_service import get_current_active_plan
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


# Feature display names for error messages
FEATURE_DISPLAY_NAMES = {
    # Phase 1 features
    "snapshots_enabled": "Snapshots",
    "workflow_ci_cd": "Workflow CI/CD",
    "workflow_limits": "Workflow Limits",
    # Environment features
    "environment_basic": "Basic Environments",
    "environment_health": "Environment Health Monitoring",
    "environment_diff": "Environment Diff/Drift Detection",
    "environment_limits": "Environment Limits",
    # Workflow features
    "workflow_read": "View Workflows",
    "workflow_push": "Push Workflows",
    "workflow_dirty_check": "Dirty State Detection",
    "workflow_ci_cd_approval": "CI/CD Approvals",
    # Snapshot features
    "snapshots_auto": "Automatic Snapshots",
    "snapshots_history": "Snapshot History",
    "snapshots_export": "Snapshot Export",
    # Observability features
    "observability_basic": "Basic Observability",
    "observability_alerts": "Alerts",
    "observability_alerts_advanced": "Advanced Alerts",
    "observability_logs": "Execution Logs",
    "observability_limits": "Log Retention",
    # Security/RBAC features
    "rbac_basic": "Basic RBAC",
    "rbac_advanced": "Advanced RBAC",
    "audit_logs": "Audit Logs",
    "audit_export": "Audit Export",
    # Agency features
    "agency_enabled": "Agency Mode",
    "agency_client_management": "Client Management",
    "agency_whitelabel": "White Label",
    "agency_client_limits": "Client Limits",
    # Enterprise features
    "sso_saml": "SSO/SAML",
    "support_priority": "Priority Support",
    "data_residency": "Data Residency",
    "enterprise_limits": "Enterprise Limits",
}

# Default environment limits by plan (1, 3, or unlimited)
PLAN_ENVIRONMENT_LIMITS = {
    "free": 1,
    "pro": 3,
    "agency": 9999,  # Unlimited
    "enterprise": 9999,  # Unlimited
}

# Minimum plan required for each feature (for upgrade messages)
FEATURE_REQUIRED_PLANS = {
    # Phase 1 features
    "snapshots_enabled": "free",
    "workflow_ci_cd": "pro",
    "workflow_limits": "free",
    # Environment features
    "environment_basic": "free",
    "environment_health": "pro",
    "environment_diff": "pro",
    "environment_limits": "free",
    # Workflow features
    "workflow_read": "free",
    "workflow_push": "free",
    "workflow_dirty_check": "pro",
    "workflow_ci_cd_approval": "agency",
    # Snapshot features
    "snapshots_auto": "pro",
    "snapshots_history": "free",
    "snapshots_export": "pro",
    # Observability features
    "observability_basic": "free",
    "observability_alerts": "pro",
    "observability_alerts_advanced": "enterprise",
    "observability_logs": "pro",
    "observability_limits": "free",
    # Security/RBAC features
    "rbac_basic": "free",
    "rbac_advanced": "agency",
    "audit_logs": "pro",
    "audit_export": "agency",
    # Agency features
    "agency_enabled": "agency",
    "agency_client_management": "agency",
    "agency_whitelabel": "agency",
    "agency_client_limits": "agency",
    # Enterprise features
    "sso_saml": "enterprise",
    "support_priority": "pro",
    "data_residency": "enterprise",
    "enterprise_limits": "enterprise",
}


class EntitlementsService:
    """
    Service for managing and checking entitlements.

    Loads plan + plan-feature mappings for a tenant and produces
    effective entitlements with has_flag() and get_limit() methods.
    """

    # Cache for tenant entitlements (keyed by tenant_id:version)
    _cache: Dict[str, Dict[str, Any]] = {}

    async def get_tenant_entitlements(self, tenant_id: str) -> Dict[str, Any]:
        """
        Load and return effective entitlements for a tenant.
        Uses entitlements_version for cache invalidation.

        Returns:
            {
                "plan_id": str,
                "plan_name": str,
                "entitlements_version": int,
                "features": {
                    "snapshots_enabled": True,
                    "workflow_ci_cd": False,
                    "workflow_limits": 10,
                    ...
                }
            }
        """
        try:
            # Get tenant's current plan assignment
            tenant_plan = await self._get_tenant_plan(tenant_id)

            if not tenant_plan:
                # Fallback to free plan defaults
                return await self._get_free_plan_defaults()

            # Check cache
            cache_key = f"{tenant_id}:{tenant_plan.get('entitlements_version', 1)}"
            if cache_key in self._cache:
                return self._cache[cache_key]

            # Load plan features
            plan_id = tenant_plan.get("plan_id")
            plan_name = tenant_plan.get("plan_name")
            plan_features = await self._get_plan_features(plan_id)
            
            logger.info(f"Tenant {tenant_id} on plan {plan_name} (id: {plan_id}) has {len(plan_features)} plan features")

            # Build base entitlements from plan
            features = {}
            feature_types = {}  # Track feature types for override merging
            for pf in plan_features:
                feature_name = pf.get("feature_name")
                feature_type = pf.get("feature_type")
                value = pf.get("value", {})
                feature_types[feature_name] = feature_type

                if feature_type == "flag":
                    features[feature_name] = value.get("enabled", False)
                    if feature_name == "workflow_ci_cd":
                        logger.info(f"Found workflow_ci_cd feature for plan {plan_name}: enabled={value.get('enabled', False)}")
                elif feature_type == "limit":
                    features[feature_name] = value.get("value", 0)
            
            if "workflow_ci_cd" not in features:
                logger.warning(f"workflow_ci_cd feature not found in plan_features for plan {plan_name} (id: {plan_id})")

            # Phase 3: Apply tenant-specific overrides
            overrides = await self._get_tenant_overrides(tenant_id)
            overrides_applied = []
            for override in overrides:
                feature_name = override.get("feature_name")
                feature_type = override.get("feature_type")
                value = override.get("value", {})

                if feature_type == "flag":
                    features[feature_name] = value.get("enabled", False)
                elif feature_type == "limit":
                    features[feature_name] = value.get("value", 0)
                overrides_applied.append(feature_name)

            if overrides_applied:
                logger.info(f"Applied {len(overrides_applied)} overrides for tenant {tenant_id}: {overrides_applied}")

            # Always use the correct environment limits based on plan name
            # This ensures consistent limits (1 for free, 3 for pro, unlimited for agency/enterprise)
            plan_name = tenant_plan.get("plan_name", "free")
            features["environment_limits"] = PLAN_ENVIRONMENT_LIMITS.get(plan_name, 1)

            result = {
                "plan_id": plan_id,
                "plan_name": plan_name,
                "entitlements_version": tenant_plan.get("entitlements_version", 1),
                "features": features,
                "overrides_applied": overrides_applied  # Track which features were overridden
            }

            # Cache result
            self._cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Failed to get entitlements for tenant {tenant_id}: {e}")
            return await self._get_free_plan_defaults()

    async def has_flag(self, tenant_id: str, feature_name: str) -> bool:
        """Check if a flag feature is enabled for a tenant."""
        entitlements = await self.get_tenant_entitlements(tenant_id)
        return entitlements.get("features", {}).get(feature_name, False)

    async def get_limit(self, tenant_id: str, feature_name: str) -> int:
        """Get the limit value for a limit feature."""
        entitlements = await self.get_tenant_entitlements(tenant_id)
        return entitlements.get("features", {}).get(feature_name, 0)

    async def check_flag(self, tenant_id: str, feature_name: str) -> Tuple[bool, str]:
        """
        Check if a flag feature is enabled.
        Returns (allowed, message).
        """
        allowed = await self.has_flag(tenant_id, feature_name)
        if allowed:
            return True, ""

        # Get required plan for this feature
        required_plan = FEATURE_REQUIRED_PLANS.get(feature_name, "pro")
        display_name = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
        return False, f"{display_name} requires a {required_plan.title()} plan or higher. Please upgrade to access this feature."

    async def check_limit(
        self,
        tenant_id: str,
        feature_name: str,
        current_count: int
    ) -> Tuple[bool, str, int, int]:
        """
        Check if a limit has been reached.
        Returns (allowed, message, current, limit).
        """
        limit = await self.get_limit(tenant_id, feature_name)

        if current_count < limit:
            return True, "", current_count, limit

        display_name = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
        return False, f"{display_name} limit reached ({limit}). Upgrade your plan to increase this limit.", current_count, limit

    async def enforce_flag(
        self,
        tenant_id: str,
        feature_name: str,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        log_denial: bool = True,
    ) -> None:
        """
        Enforce flag feature access - raises 403 if not enabled.
        Use this as a guard in endpoint handlers.

        Phase 3: Logs denial to audit log if log_denial=True.
        """
        allowed, message = await self.check_flag(tenant_id, feature_name)
        if not allowed:
            # Phase 3: Log denial
            if log_denial:
                await audit_service.log_denial(
                    tenant_id=tenant_id,
                    feature_key=feature_name,
                    user_id=user_id,
                    endpoint=endpoint,
                )

            required_plan = FEATURE_REQUIRED_PLANS.get(feature_name, "pro")
            display_name = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "feature": feature_name,
                    "feature_display_name": display_name,
                    "message": message,
                    "required_plan": required_plan,
                }
            )

    async def enforce_limit(
        self,
        tenant_id: str,
        feature_name: str,
        current_count: int,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        resource_type: Optional[str] = None,
        log_limit_exceeded: bool = True,
    ) -> None:
        """
        Enforce limit - raises 403 if limit exceeded.
        Use this before creating new resources.

        Phase 3: Logs limit exceeded to audit log if log_limit_exceeded=True.
        """
        allowed, message, current, limit = await self.check_limit(
            tenant_id, feature_name, current_count
        )
        if not allowed:
            # Phase 3: Log limit exceeded
            if log_limit_exceeded:
                await audit_service.log_limit_exceeded(
                    tenant_id=tenant_id,
                    feature_key=feature_name,
                    current_value=current,
                    limit_value=limit,
                    user_id=user_id,
                    endpoint=endpoint,
                    resource_type=resource_type,
                )

            display_name = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "limit_reached",
                    "feature": feature_name,
                    "feature_display_name": display_name,
                    "current_count": current,
                    "limit": limit,
                    "message": message,
                }
            )

    async def get_workflow_count(self, tenant_id: str) -> int:
        """Get current workflow count across all environments for a tenant."""
        try:
            response = db_service.client.table("workflows").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).eq("is_deleted", False).execute()
            return response.count or 0
        except Exception as e:
            logger.error(f"Failed to get workflow count: {e}")
            return 0

    async def can_create_workflow(self, tenant_id: str) -> Tuple[bool, str, int, int]:
        """Check if tenant can create another workflow."""
        current_count = await self.get_workflow_count(tenant_id)
        return await self.check_limit(tenant_id, "workflow_limits", current_count)

    async def enforce_workflow_limit(self, tenant_id: str) -> None:
        """Enforce workflow limit before creating new workflow."""
        current_count = await self.get_workflow_count(tenant_id)
        await self.enforce_limit(tenant_id, "workflow_limits", current_count)

    async def get_environment_count(self, tenant_id: str) -> int:
        """Get current environment count for a tenant."""
        try:
            response = db_service.client.table("environments").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            return response.count or 0
        except Exception as e:
            logger.error(f"Failed to get environment count: {e}")
            return 0

    async def can_add_environment(self, tenant_id: str) -> Tuple[bool, str, int, int]:
        """Check if tenant can add another environment."""
        current_count = await self.get_environment_count(tenant_id)
        return await self.check_limit(tenant_id, "environment_limits", current_count)

    async def enforce_environment_limit(self, tenant_id: str) -> None:
        """Enforce environment limit before creating new environment."""
        current_count = await self.get_environment_count(tenant_id)
        await self.enforce_limit(tenant_id, "environment_limits", current_count)

    # Private helper methods

    async def _get_tenant_plan(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant's current plan assignment with plan details."""
        try:
            current = await get_current_active_plan(tenant_id)
            if not current:
                return None

            plan_response = (
                db_service.client.table("plans")
                .select("id, name, display_name")
                .eq("id", current.plan_id)
                .single()
                .execute()
            )

            plan = plan_response.data or {}
            if not plan:
                return None

            return {
                "plan_id": plan.get("id"),
                "plan_name": plan.get("name"),
                "plan_display_name": plan.get("display_name"),
                "entitlements_version": current.entitlements_version,
            }
        except Exception as e:
            logger.error(f"Failed to get tenant plan for {tenant_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def _get_plan_features(self, plan_id: str) -> list:
        """Get all features for a plan with their values."""
        try:
            response = db_service.client.table("plan_features").select(
                "value, feature_id, feature:feature_id(name, type)"
            ).eq("plan_id", plan_id).execute()

            result = []
            for pf in response.data or []:
                feature = pf.get("feature", {})
                # If join didn't work, fetch feature separately
                if not feature and pf.get("feature_id"):
                    feature_response = db_service.client.table("features").select("*").eq("id", pf.get("feature_id")).single().execute()
                    if feature_response.data:
                        feature = feature_response.data
                
                if feature:
                    result.append({
                        "feature_name": feature.get("name"),
                        "feature_type": feature.get("type"),
                        "value": pf.get("value", {})
                    })
            return result
        except Exception as e:
            logger.error(f"Failed to get plan features for plan {plan_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    async def _get_tenant_overrides(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Get active, non-expired tenant feature overrides.

        Phase 3: Returns overrides that should be applied on top of base plan features.
        Only returns overrides where:
        - is_active = true
        - expires_at IS NULL OR expires_at > NOW()
        """
        try:
            # Query active overrides with feature details
            response = db_service.client.table("tenant_feature_overrides").select(
                "id, value, expires_at, feature:feature_id(id, name, type, display_name)"
            ).eq("tenant_id", tenant_id).eq("is_active", True).execute()

            now = datetime.now(timezone.utc)
            result = []
            for override in response.data or []:
                # Check expiration
                expires_at = override.get("expires_at")
                if expires_at:
                    # Parse ISO timestamp
                    try:
                        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                        if expiry <= now:
                            # Expired, skip
                            continue
                    except (ValueError, TypeError):
                        pass

                feature = override.get("feature", {})
                result.append({
                    "override_id": override.get("id"),
                    "feature_id": feature.get("id"),
                    "feature_name": feature.get("name"),
                    "feature_type": feature.get("type"),
                    "feature_display_name": feature.get("display_name"),
                    "value": override.get("value", {}),
                    "expires_at": expires_at
                })

            return result
        except Exception as e:
            logger.error(f"Failed to get tenant overrides for {tenant_id}: {e}")
            return []

    async def _get_free_plan_defaults(self) -> Dict[str, Any]:
        """Return default free plan entitlements."""
        return {
            "plan_id": None,
            "plan_name": "free",
            "entitlements_version": 0,
            "features": {
                # Phase 1 features
                "snapshots_enabled": True,
                "workflow_ci_cd": False,
                "workflow_limits": 10,
                # Environment features
                "environment_basic": True,
                "environment_health": False,
                "environment_diff": False,
                "environment_limits": 1,
                # Workflow features
                "workflow_read": True,
                "workflow_push": True,
                "workflow_dirty_check": False,
                "workflow_ci_cd_approval": False,
                # Snapshot features
                "snapshots_auto": False,
                "snapshots_history": 5,
                "snapshots_export": False,
                # Observability features
                "observability_basic": True,
                "observability_alerts": False,
                "observability_alerts_advanced": False,
                "observability_logs": False,
                "observability_limits": 7,
                # Security/RBAC features
                "rbac_basic": True,
                "rbac_advanced": False,
                "audit_logs": False,
                "audit_export": False,
                # Agency features
                "agency_enabled": False,
                "agency_client_management": False,
                "agency_whitelabel": False,
                "agency_client_limits": 0,
                # Enterprise features
                "sso_saml": False,
                "support_priority": False,
                "data_residency": False,
                "enterprise_limits": 0,
            }
        }

    def clear_cache(self, tenant_id: Optional[str] = None) -> None:
        """Clear entitlements cache."""
        if tenant_id:
            keys_to_remove = [k for k in self._cache if k.startswith(f"{tenant_id}:")]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()


# Singleton instance
entitlements_service = EntitlementsService()
