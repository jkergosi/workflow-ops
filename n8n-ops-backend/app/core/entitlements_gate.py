"""Entitlements gate decorators for FastAPI endpoints."""
from fastapi import HTTPException, status, Depends

from app.services.entitlements_service import entitlements_service
from app.services.auth_service import get_current_user


def require_entitlement(feature_name: str):
    """
    FastAPI dependency to enforce flag-based entitlement.

    Usage:
        @router.post("/snapshots")
        async def create_snapshot(
            ...,
            user_info: dict = Depends(require_entitlement("snapshots_enabled"))
        ):
            ...
    """
    async def entitlement_dependency(user_info: dict = Depends(get_current_user)):
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        tenant_id = tenant["id"]
        await entitlements_service.enforce_flag(tenant_id, feature_name)
        return user_info

    return entitlement_dependency


def require_workflow_limit():
    """
    FastAPI dependency to enforce workflow limit before creation.

    Usage:
        @router.post("/upload")
        async def upload_workflow(
            ...,
            user_info: dict = Depends(require_workflow_limit())
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
        can_create, message, current, limit = await entitlements_service.can_create_workflow(tenant_id)

        if not can_create:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "workflow_limit_reached",
                    "current_count": current,
                    "limit": limit,
                    "message": message,
                }
            )

        return {
            **user_info,
            "workflow_limit": {
                "current": current,
                "limit": limit,
            }
        }

    return limit_dependency


class EntitlementsChecker:
    """
    Class-based entitlements checker for more complex scenarios.

    Usage:
        checker = EntitlementsChecker(tenant_id)
        if await checker.has_flag("snapshots_enabled"):
            # do something

        # Or raise if not allowed
        await checker.require_flag("snapshots_enabled")
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    async def has_flag(self, feature: str) -> bool:
        """Check if flag feature is enabled (returns bool)."""
        return await entitlements_service.has_flag(self.tenant_id, feature)

    async def get_limit(self, feature: str) -> int:
        """Get limit value for a feature."""
        return await entitlements_service.get_limit(self.tenant_id, feature)

    async def require_flag(self, feature: str) -> None:
        """Require flag feature (raises 403 if not enabled)."""
        await entitlements_service.enforce_flag(self.tenant_id, feature)

    async def require_limit(self, feature: str, current_count: int) -> None:
        """Require limit not exceeded (raises 403 if exceeded)."""
        await entitlements_service.enforce_limit(self.tenant_id, feature, current_count)

    async def get_entitlements(self) -> dict:
        """Get all entitlements for this tenant."""
        return await entitlements_service.get_tenant_entitlements(self.tenant_id)
