"""Feature gate decorator for enforcing plan-based feature access.

Supports both legacy tenant-level checks and new provider-scoped checks.
Provider-scoped checks are preferred for new code.
"""
from functools import wraps
from typing import Callable, Optional

from fastapi import HTTPException, status, Depends, Request

from app.services.feature_service import feature_service, FEATURE_REQUIRED_PLANS, FEATURE_DISPLAY_NAMES, DEFAULT_PROVIDER
from app.services.auth_service import get_current_user


def require_feature(feature_name: str, provider_key: str = DEFAULT_PROVIDER):
    """
    Decorator to enforce feature access on endpoints.

    Provider-scoped: Checks tenant_provider_subscriptions -> plan.features

    Usage:
        @router.post("/scheduled-backup")
        @require_feature("scheduled_backup")  # defaults to n8n provider
        async def create_scheduled_backup(...):
            ...

        @router.post("/make-backup")
        @require_feature("scheduled_backup", provider_key="make")
        async def create_make_backup(...):
            ...

    This will return a 403 error if the feature is not available for the user's plan.
    """
    async def feature_dependency(user_info: dict = Depends(get_current_user)):
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        tenant_id = tenant["id"]

        # Use provider-scoped check
        try:
            await feature_service.require_feature(tenant_id, feature_name, provider_key)
        except HTTPException:
            raise
        except Exception:
            # Fallback to legacy check if provider check fails
            can_use, message = await feature_service.can_use_feature(tenant_id, feature_name)
            if not can_use:
                display_name = FEATURE_DISPLAY_NAMES.get(feature_name, feature_name)
                required_plan = FEATURE_REQUIRED_PLANS.get(feature_name, "pro")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "feature_not_available",
                        "feature": feature_name,
                        "feature_display_name": display_name,
                        "required_plan": required_plan,
                        "message": message,
                    }
                )

        return user_info

    return feature_dependency


def require_provider_feature(feature_name: str, provider_key: str = DEFAULT_PROVIDER):
    """
    Strict provider-scoped feature gate. Only uses provider subscriptions.

    Usage:
        @router.post("/github-backup")
        @require_provider_feature("github_backup")
        async def github_backup(...):
            ...

    Raises:
        403 if provider not selected OR feature not available
    """
    async def feature_dependency(user_info: dict = Depends(get_current_user)):
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        tenant_id = tenant["id"]
        await feature_service.require_feature(tenant_id, feature_name, provider_key)
        return user_info

    return feature_dependency


def require_environment_limit():
    """
    Dependency to enforce environment creation limits.

    Usage:
        @router.post("/environments")
        async def create_environment(
            ...,
            _limit_check: dict = Depends(require_environment_limit())
        ):
            ...
    """
    async def limit_dependency(user_info: dict = Depends(get_current_user)):
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        tenant_id = tenant["id"]
        can_add, message, current, max_count = await feature_service.can_add_environment(tenant_id)

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

        return {
            **user_info,
            "environment_limit": {
                "current": current,
                "max": max_count,
            }
        }

    return limit_dependency


def require_team_member_limit():
    """
    Dependency to enforce team member limits.

    Usage:
        @router.post("/team/members")
        async def add_team_member(
            ...,
            _limit_check: dict = Depends(require_team_member_limit())
        ):
            ...
    """
    async def limit_dependency(user_info: dict = Depends(get_current_user)):
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        tenant_id = tenant["id"]
        can_add, message, current, max_count = await feature_service.can_add_team_member(tenant_id)

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

        return {
            **user_info,
            "team_member_limit": {
                "current": current,
                "max": max_count,
            }
        }

    return limit_dependency


class FeatureChecker:
    """
    Class-based feature checker for more complex scenarios.

    Usage:
        checker = FeatureChecker(tenant_id)
        if await checker.can_use("scheduled_backup"):
            # do something

        # Or raise if not allowed
        await checker.require("scheduled_backup")
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    async def can_use(self, feature: str) -> bool:
        """Check if feature is available (returns bool)."""
        can_use, _ = await feature_service.can_use_feature(self.tenant_id, feature)
        return can_use

    async def require(self, feature: str) -> None:
        """Require feature access (raises 403 if not available)."""
        await feature_service.enforce_feature(self.tenant_id, feature)

    async def get_features(self) -> dict:
        """Get all features for this tenant."""
        return await feature_service.get_tenant_features(self.tenant_id)

    async def get_usage(self) -> dict:
        """Get usage summary for this tenant."""
        return await feature_service.get_usage_summary(self.tenant_id)
