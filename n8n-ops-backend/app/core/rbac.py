from fastapi import Depends, HTTPException, status
from typing import Iterable

from app.services.auth_service import get_current_user
from app.core.platform_admin import is_platform_admin


def require_tenant_role(required_roles: Iterable[str], allow_platform_admin: bool = True):
    roles = {r.lower() for r in required_roles}

    async def dependency(user_info: dict = Depends(get_current_user)) -> dict:
        user = (user_info or {}).get("user") or {}
        tenant = (user_info or {}).get("tenant")

        if not user or not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        role = (user.get("role") or "").lower()
        if role in roles:
            return user_info

        actor_id = user_info.get("actor_user_id") or user.get("id")
        if allow_platform_admin and actor_id and is_platform_admin(actor_id):
            return {**user_info, "actor_is_platform_admin": True}

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

    return dependency


def require_tenant_admin(allow_platform_admin: bool = True):
    return require_tenant_role({"admin"}, allow_platform_admin=allow_platform_admin)

