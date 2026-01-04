"""Feature service for checking plan-based feature access.

This module provides provider-scoped entitlement gating. All feature checks
should use provider_key (default: "n8n") to look up entitlements from
tenant_provider_subscriptions -> provider_plans.features.

Key functions:
- get_effective_entitlements(tenant_id, provider_key) - single source of truth
- has_feature(tenant_id, feature_key, provider_key) - check a specific feature
"""
from typing import Any, Dict, Optional, Tuple, Union
from fastapi import HTTPException, status

from app.services.database import db_service


# Default provider for MVP - all feature checks default to n8n
DEFAULT_PROVIDER = "n8n"


# Feature names that map to plan features
FEATURE_NAMES = {
    "max_environments": "max_environments",
    "max_team_members": "max_team_members",
    "github_backup": "github_backup",
    "github_restore": "github_restore",
    "scheduled_backup": "scheduled_backup",
    "environment_promotion": "environment_promotion",
    "credential_remapping": "credential_remapping",
    "workflow_diff": "workflow_diff",
    "execution_metrics": "execution_metrics",
    "alerting": "alerting",
    "role_based_access": "role_based_access",
    "audit_logs": "audit_logs",
    "audit_retention_days": "audit_retention_days",
    "workflow_lifecycle": "workflow_lifecycle",
    "secret_vault": "secret_vault",
    "compliance_tools": "compliance_tools",
    "environment_protection": "environment_protection",
    "sso_scim": "sso_scim",
    "support": "support",
    # Drift features
    "drift_detection": "drift_detection",
    "drift_incidents": "drift_incidents",
    "drift_full_diff": "drift_full_diff",
    "drift_ttl_sla": "drift_ttl_sla",
    "drift_policies": "drift_policies",
}

# Feature display names for error messages
FEATURE_DISPLAY_NAMES = {
    "max_environments": "Environment Limit",
    "max_team_members": "Team Member Limit",
    "github_backup": "GitHub Backup",
    "github_restore": "GitHub Restore",
    "scheduled_backup": "Scheduled Backups",
    "environment_promotion": "Environment Promotion",
    "credential_remapping": "Credential Remapping",
    "workflow_diff": "Workflow Diff",
    "execution_metrics": "Execution Metrics",
    "alerting": "Alerting",
    "role_based_access": "Role-Based Access Control",
    "audit_logs": "Audit Logs",
    "workflow_lifecycle": "Workflow Lifecycle Management",
    "secret_vault": "Secret Vault Integration",
    "compliance_tools": "Compliance Tools",
    "environment_protection": "Environment Protection",
    "sso_scim": "SSO/SCIM",
    "support": "Support Level",
    # Drift features
    "drift_detection": "Drift Detection",
    "drift_incidents": "Drift Incident Management",
    "drift_full_diff": "Full Drift Diff Visualization",
    "drift_ttl_sla": "Drift TTL/SLA Enforcement",
    "drift_policies": "Drift Policies",
}

# Features that require specific plans
FEATURE_REQUIRED_PLANS = {
    "scheduled_backup": "pro",
    "environment_promotion": "pro",
    "workflow_diff": "pro",
    "alerting": "pro",
    "role_based_access": "pro",
    "audit_logs": "pro",
    "workflow_lifecycle": "pro",
    "credential_remapping": "enterprise",
    "secret_vault": "enterprise",
    "compliance_tools": "enterprise",
    "environment_protection": "enterprise",
    "sso_scim": "enterprise",
    # Drift features - detection is free, management is gated
    # drift_detection: available on all plans (no entry needed)
    "drift_incidents": "pro",
    "drift_full_diff": "agency",
    "drift_ttl_sla": "agency",
    "drift_policies": "enterprise",
}


class FeatureService:
    """Centralized service for checking plan-based feature access."""

    async def get_tenant_subscription(self, tenant_id: str) -> Optional[dict]:
        """Get tenant's subscription with plan features."""
        try:
            response = db_service.client.table("subscriptions").select(
                "*, plan:plan_id(name, display_name, features, max_environments, max_team_members, max_workflows)"
            ).eq("tenant_id", tenant_id).single().execute()

            if response.data:
                return response.data
            return None
        except Exception:
            return None

    async def get_tenant_features(self, tenant_id: str) -> dict:
        """Get all features available for a tenant's plan."""
        subscription = await self.get_tenant_subscription(tenant_id)

        if not subscription or not subscription.get("plan"):
            # Return free plan defaults if no subscription
            return {
                "plan_name": "free",
                "max_environments": 1,
                "max_team_members": 1,
                "github_backup": "manual",
                "github_restore": True,
                "scheduled_backup": False,
                "environment_promotion": False,
                "credential_remapping": False,
                "workflow_diff": False,
                "execution_metrics": "basic",
                "alerting": False,
                "role_based_access": False,
                "audit_logs": False,
                "audit_retention_days": 0,
                "workflow_lifecycle": False,
                "secret_vault": False,
                "compliance_tools": False,
                "environment_protection": False,
                "sso_scim": False,
                "support": "community",
                # Drift features - detection is free for all
                "drift_detection": True,
                "drift_incidents": False,
                "drift_full_diff": False,
                "drift_ttl_sla": False,
                "drift_policies": False,
            }

        plan = subscription["plan"]
        features = plan.get("features", {})

        return {
            "plan_name": plan.get("name", "free"),
            "max_environments": features.get("max_environments", 1),
            "max_team_members": features.get("max_team_members", 1),
            "github_backup": features.get("github_backup", "manual"),
            "github_restore": features.get("github_restore", True),
            "scheduled_backup": features.get("scheduled_backup", False),
            "environment_promotion": features.get("environment_promotion", False),
            "credential_remapping": features.get("credential_remapping", False),
            "workflow_diff": features.get("workflow_diff", False),
            "execution_metrics": features.get("execution_metrics", "basic"),
            "alerting": features.get("alerting", False),
            "role_based_access": features.get("role_based_access", False),
            "audit_logs": features.get("audit_logs", False),
            "audit_retention_days": features.get("audit_retention_days", 0),
            "workflow_lifecycle": features.get("workflow_lifecycle", False),
            "secret_vault": features.get("secret_vault", False),
            "compliance_tools": features.get("compliance_tools", False),
            "environment_protection": features.get("environment_protection", False),
            "sso_scim": features.get("sso_scim", False),
            "support": features.get("support", "community"),
            # Drift features - detection is always true, others from plan
            "drift_detection": True,  # Always available
            "drift_incidents": features.get("drift_incidents", False),
            "drift_full_diff": features.get("drift_full_diff", False),
            "drift_ttl_sla": features.get("drift_ttl_sla", False),
            "drift_policies": features.get("drift_policies", False),
        }

    async def get_feature_value(self, tenant_id: str, feature: str) -> Any:
        """Get a specific feature value for a tenant."""
        features = await self.get_tenant_features(tenant_id)
        return features.get(feature)

    async def can_use_feature(self, tenant_id: str, feature: str) -> Tuple[bool, str]:
        """
        Check if tenant can use a specific feature.
        Returns (can_use, message).
        """
        features = await self.get_tenant_features(tenant_id)
        feature_value = features.get(feature)

        # For boolean features
        if isinstance(feature_value, bool):
            if feature_value:
                return True, ""
            required_plan = FEATURE_REQUIRED_PLANS.get(feature, "pro")
            display_name = FEATURE_DISPLAY_NAMES.get(feature, feature)
            return False, f"{display_name} requires a {required_plan.title()} plan or higher. Please upgrade to access this feature."

        # For features with values like "manual", "scheduled", "basic", "full", etc.
        if feature_value in [False, None, ""]:
            required_plan = FEATURE_REQUIRED_PLANS.get(feature, "pro")
            display_name = FEATURE_DISPLAY_NAMES.get(feature, feature)
            return False, f"{display_name} requires a {required_plan.title()} plan or higher. Please upgrade to access this feature."

        return True, ""

    async def can_add_environment(self, tenant_id: str) -> Tuple[bool, str, int, Union[int, str]]:
        """
        Check if tenant can add a new environment.
        Returns (can_add, message, current_count, max_count).
        """
        features = await self.get_tenant_features(tenant_id)
        max_environments = features.get("max_environments", 1)

        # Get current environment count
        try:
            response = db_service.client.table("environments").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            current_count = response.count or 0
        except Exception:
            current_count = 0

        # Check if unlimited
        if max_environments == "unlimited":
            return True, "", current_count, "unlimited"

        # Check limit
        if current_count >= max_environments:
            return False, f"Environment limit reached ({max_environments}). Upgrade your plan to add more environments.", current_count, max_environments

        return True, "", current_count, max_environments

    async def can_add_team_member(self, tenant_id: str) -> Tuple[bool, str, int, Union[int, str]]:
        """
        Check if tenant can add a new team member.
        Returns (can_add, message, current_count, max_count).
        """
        features = await self.get_tenant_features(tenant_id)
        max_members = features.get("max_team_members", 1)

        # Get current team member count
        try:
            response = db_service.client.table("users").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).eq("status", "active").execute()
            current_count = response.count or 0
        except Exception:
            current_count = 0

        # Check if unlimited
        if max_members == "unlimited":
            return True, "", current_count, "unlimited"

        # Check limit
        if current_count >= max_members:
            return False, f"Team member limit reached ({max_members}). Upgrade your plan to add more team members.", current_count, max_members

        return True, "", current_count, max_members

    async def enforce_feature(self, tenant_id: str, feature: str) -> None:
        """
        Enforce feature access - raises 403 if feature not available.
        Use this as a guard in endpoint handlers.
        """
        can_use, message = await self.can_use_feature(tenant_id, feature)
        if not can_use:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "feature": feature,
                    "message": message,
                    "required_plan": FEATURE_REQUIRED_PLANS.get(feature, "pro"),
                }
            )

    async def enforce_environment_limit(self, tenant_id: str) -> None:
        """
        Enforce environment limit - raises 403 if limit exceeded.
        Use this before creating a new environment.
        """
        can_add, message, current, max_count = await self.can_add_environment(tenant_id)
        if not can_add:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "environment_limit_reached",
                    "current_count": current,
                    "max_count": max_count,
                    "message": message,
                }
            )

    async def enforce_team_member_limit(self, tenant_id: str) -> None:
        """
        Enforce team member limit - raises 403 if limit exceeded.
        Use this before adding a new team member.
        """
        can_add, message, current, max_count = await self.can_add_team_member(tenant_id)
        if not can_add:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "team_member_limit_reached",
                    "current_count": current,
                    "max_count": max_count,
                    "message": message,
                }
            )

    async def get_usage_summary(self, tenant_id: str) -> dict:
        """Get a summary of current usage vs limits for a tenant."""
        features = await self.get_tenant_features(tenant_id)

        # Get environment count
        try:
            env_response = db_service.client.table("environments").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            env_count = env_response.count or 0
        except Exception:
            env_count = 0

        # Get team member count
        try:
            member_response = db_service.client.table("users").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).eq("status", "active").execute()
            member_count = member_response.count or 0
        except Exception:
            member_count = 0

        return {
            "plan_name": features.get("plan_name", "free"),
            "environments": {
                "current": env_count,
                "max": features.get("max_environments", 1),
            },
            "team_members": {
                "current": member_count,
                "max": features.get("max_team_members", 1),
            },
            "features": features,
        }

    # ==========================================================================
    # Provider-Scoped Entitlement System (New)
    # ==========================================================================

    async def get_effective_entitlements(
        self, tenant_id: str, provider_key: str = DEFAULT_PROVIDER
    ) -> Dict[str, Any]:
        """
        Get effective entitlements for a tenant's provider subscription.

        This is the SINGLE SOURCE OF TRUTH for all feature gating.
        Looks up tenant_provider_subscriptions -> provider_plans.features.

        Args:
            tenant_id: The tenant UUID
            provider_key: Provider name (default: "n8n" for MVP)

        Returns:
            Dict with entitlements including:
            - plan_name: The plan name (free, pro, enterprise)
            - provider_key: The provider this applies to
            - features: Dict of feature flags/limits from plan.features JSONB
            - max_environments: Environment limit
            - max_workflows: Workflow limit
            - has_subscription: Whether tenant has an active subscription
        """
        try:
            # Get provider by key
            provider_response = db_service.client.table("providers").select(
                "id, name"
            ).eq("name", provider_key).single().execute()

            if not provider_response.data:
                # Provider not found - return free defaults
                return self._get_free_entitlements(provider_key)

            provider_id = provider_response.data["id"]

            # Get tenant's subscription for this provider
            sub_response = db_service.client.table("tenant_provider_subscriptions").select(
                "*, plan:plan_id(id, name, display_name, features, max_environments, max_workflows)"
            ).eq("tenant_id", tenant_id).eq("provider_id", provider_id).single().execute()

            if not sub_response.data or not sub_response.data.get("plan"):
                # No subscription - tenant hasn't selected this provider
                return {
                    "plan_name": None,
                    "provider_key": provider_key,
                    "features": {},
                    "max_environments": 0,
                    "max_workflows": 0,
                    "has_subscription": False,
                    "status": None,
                }

            plan = sub_response.data["plan"]
            features = plan.get("features", {}) or {}

            return {
                "plan_name": plan.get("name", "free"),
                "provider_key": provider_key,
                "features": features,
                "max_environments": plan.get("max_environments", 1),
                "max_workflows": plan.get("max_workflows", 10),
                "has_subscription": True,
                "status": sub_response.data.get("status", "active"),
            }

        except Exception as e:
            # On error, return free defaults for safety
            print(f"[FeatureService] Error getting entitlements for {tenant_id}/{provider_key}: {e}")
            return self._get_free_entitlements(provider_key)

    def _get_free_entitlements(self, provider_key: str) -> Dict[str, Any]:
        """Return free tier entitlements as fallback."""
        return {
            "plan_name": "free",
            "provider_key": provider_key,
            "features": {
                "github_backup": False,
                "promotions": False,
                "audit_logs": False,
            },
            "max_environments": 1,
            "max_workflows": 10,
            "has_subscription": False,
            "status": None,
        }

    async def has_feature(
        self,
        tenant_id: str,
        feature_key: str,
        provider_key: str = DEFAULT_PROVIDER
    ) -> bool:
        """
        Check if tenant has a specific feature enabled for a provider.

        Args:
            tenant_id: The tenant UUID
            feature_key: Feature to check (e.g., "github_backup", "promotions")
            provider_key: Provider name (default: "n8n" for MVP)

        Returns:
            True if feature is enabled, False otherwise
        """
        entitlements = await self.get_effective_entitlements(tenant_id, provider_key)

        # If no subscription, feature is not available
        if not entitlements.get("has_subscription"):
            return False

        features = entitlements.get("features", {})
        return bool(features.get(feature_key, False))

    async def get_feature_value(
        self,
        tenant_id: str,
        feature_key: str,
        provider_key: str = DEFAULT_PROVIDER,
        default: Any = None
    ) -> Any:
        """
        Get a feature value (for non-boolean features like limits).

        Args:
            tenant_id: The tenant UUID
            feature_key: Feature to get
            provider_key: Provider name (default: "n8n")
            default: Default value if feature not found

        Returns:
            Feature value or default
        """
        entitlements = await self.get_effective_entitlements(tenant_id, provider_key)
        features = entitlements.get("features", {})
        return features.get(feature_key, default)

    async def require_feature(
        self,
        tenant_id: str,
        feature_key: str,
        provider_key: str = DEFAULT_PROVIDER
    ) -> None:
        """
        Require a feature - raises 403 if not available.

        Args:
            tenant_id: The tenant UUID
            feature_key: Feature required
            provider_key: Provider name (default: "n8n")

        Raises:
            HTTPException 403 if feature not available
        """
        entitlements = await self.get_effective_entitlements(tenant_id, provider_key)

        if not entitlements.get("has_subscription"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "provider_not_selected",
                    "provider": provider_key,
                    "message": f"Provider '{provider_key}' has not been selected. Add this provider to access its features.",
                }
            )

        features = entitlements.get("features", {})
        if not features.get(feature_key, False):
            plan_name = entitlements.get("plan_name", "free")
            display_name = FEATURE_DISPLAY_NAMES.get(feature_key, feature_key)
            required_plan = FEATURE_REQUIRED_PLANS.get(feature_key, "pro")

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "feature_not_available",
                    "feature": feature_key,
                    "feature_display_name": display_name,
                    "current_plan": plan_name,
                    "required_plan": required_plan,
                    "provider": provider_key,
                    "message": f"{display_name} requires a {required_plan.title()} plan or higher. Please upgrade to access this feature.",
                }
            )

    async def get_provider_limit(
        self,
        tenant_id: str,
        limit_type: str,
        provider_key: str = DEFAULT_PROVIDER
    ) -> Union[int, str]:
        """
        Get a limit value for a provider subscription.

        Args:
            tenant_id: The tenant UUID
            limit_type: "environments" or "workflows"
            provider_key: Provider name (default: "n8n")

        Returns:
            Limit value (int or "unlimited" for -1)
        """
        entitlements = await self.get_effective_entitlements(tenant_id, provider_key)

        if limit_type == "environments":
            limit = entitlements.get("max_environments", 1)
        elif limit_type == "workflows":
            limit = entitlements.get("max_workflows", 10)
        else:
            limit = 0

        # -1 means unlimited
        if limit == -1:
            return "unlimited"
        return limit


# Singleton instance
feature_service = FeatureService()
