"""Authentication endpoints for Auth0 integration."""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, Any, Union

from app.services.auth_service import (
    auth_service,
    get_current_user,
    get_current_user_optional
)
from app.services.database import db_service
from app.services.feature_service import feature_service

router = APIRouter()


class OnboardingRequest(BaseModel):
    """Request body for completing onboarding."""
    organization_name: Optional[str] = None


class UserResponse(BaseModel):
    """Response containing user and tenant info."""
    id: str
    email: str
    name: str
    role: str
    tenant_id: str
    tenant_name: str
    subscription_plan: str
    has_environment: bool
    is_new: bool = False


@router.get("/me")
async def get_current_user_info(user_info: dict = Depends(get_current_user)):
    """Get current authenticated user information."""
    user = user_info.get("user")
    tenant = user_info.get("tenant")

    if not user or not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user has any environments
    env_response = db_service.client.table("environments").select(
        "id", count="exact"
    ).eq("tenant_id", tenant["id"]).execute()
    has_environment = (env_response.count or 0) > 0

    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
        role=user["role"],
        tenant_id=tenant["id"],
        tenant_name=tenant["name"],
        subscription_plan=tenant.get("subscription_tier", "free"),
        has_environment=has_environment,
        is_new=False
    )


@router.get("/status")
async def get_auth_status(user_info: dict = Depends(get_current_user_optional)):
    """Check authentication status and whether onboarding is needed."""
    is_new = user_info.get("is_new", False)
    user = user_info.get("user")
    tenant = user_info.get("tenant")

    if is_new and user is None:
        # User needs to complete onboarding
        return {
            "authenticated": True,
            "onboarding_required": True,
            "user": None,
            "auth0_id": user_info.get("auth0_id"),
            "email": user_info.get("email"),
            "name": user_info.get("name")
        }

    # Check if user has any environments
    has_environment = False
    if tenant:
        env_response = db_service.client.table("environments").select(
            "id", count="exact"
        ).eq("tenant_id", tenant["id"]).execute()
        has_environment = (env_response.count or 0) > 0

    # Get plan features and usage for authenticated users
    features = None
    usage = None
    if tenant:
        try:
            usage = await feature_service.get_usage_summary(tenant["id"])
            features = usage.get("features", {})
        except Exception:
            features = None
            usage = None

    return {
        "authenticated": True,
        "onboarding_required": False,
        "has_environment": has_environment,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"]
        } if user else None,
        "tenant": {
            "id": tenant["id"],
            "name": tenant["name"],
            "subscription_plan": tenant.get("subscription_tier", "free")
        } if tenant else None,
        "features": features,
        "usage": {
            "environments": usage.get("environments") if usage else None,
            "team_members": usage.get("team_members") if usage else None,
        } if usage else None
    }


@router.post("/onboarding")
async def complete_onboarding(
    request: OnboardingRequest,
    user_info: dict = Depends(get_current_user_optional)
):
    """Complete user onboarding - creates user and tenant."""
    if not user_info.get("is_new") or user_info.get("user") is not None:
        # User already exists
        user = user_info.get("user")
        tenant = user_info.get("tenant")

        # Check if user has any environments
        has_environment = False
        if tenant:
            env_response = db_service.client.table("environments").select(
                "id", count="exact"
            ).eq("tenant_id", tenant["id"]).execute()
            has_environment = (env_response.count or 0) > 0

        return {
            "success": True,
            "message": "User already exists",
            "user": UserResponse(
                id=user["id"],
                email=user["email"],
                name=user["name"],
                role=user["role"],
                tenant_id=tenant["id"],
                tenant_name=tenant["name"],
                subscription_plan=tenant.get("subscription_tier", "free"),
                has_environment=has_environment,
                is_new=False
            )
        }

    # Create new user and tenant
    auth0_id = user_info.get("auth0_id")
    email = user_info.get("email")
    name = user_info.get("name")

    if not auth0_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required user information"
        )

    result = await auth_service.create_user_and_tenant(
        auth0_id=auth0_id,
        email=email,
        name=name,
        organization_name=request.organization_name
    )

    user = result["user"]
    tenant = result["tenant"]

    return {
        "success": True,
        "message": "User and tenant created successfully",
        "user": UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            tenant_id=tenant["id"],
            tenant_name=tenant["name"],
            subscription_plan=tenant.get("subscription_tier", "free"),
            has_environment=False,
            is_new=True
        )
    }
