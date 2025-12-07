"""Feature service for checking plan-based feature access."""
from typing import Any, Optional, Tuple, Union
from fastapi import HTTPException, status

from app.services.database import db_service


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


# Singleton instance
feature_service = FeatureService()
