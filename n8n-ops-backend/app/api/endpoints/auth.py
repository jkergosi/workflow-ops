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
from app.services.entitlements_service import entitlements_service

router = APIRouter()


class OnboardingRequest(BaseModel):
    """Request body for completing onboarding."""
    organization_name: Optional[str] = None


class UserUpdateRequest(BaseModel):
    """Request body for updating user profile."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None


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
    entitlements = None
    if tenant:
        try:
            usage = await feature_service.get_usage_summary(tenant["id"])
            features = usage.get("features", {})
        except Exception:
            features = None
            usage = None

        # Get entitlements from new entitlements service
        try:
            entitlements = await entitlements_service.get_tenant_entitlements(tenant["id"])
        except Exception:
            entitlements = None

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
        } if usage else None,
        "entitlements": {
            "plan_id": entitlements.get("plan_id") if entitlements else None,
            "plan_name": entitlements.get("plan_name", "free") if entitlements else "free",
            "entitlements_version": entitlements.get("entitlements_version", 0) if entitlements else 0,
            "features": entitlements.get("features", {}) if entitlements else {},
        } if entitlements else None,
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


# =============================================================================
# DEV MODE ENDPOINTS - Bypass Auth0 for local development
# =============================================================================

@router.get("/dev/users")
async def get_dev_users():
    """Get all users for dev mode - allows switching between users."""
    try:
        response = db_service.client.table("users").select("id, email, name, tenant_id, role").execute()
        return {"users": response.data or []}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )


@router.post("/dev/login-as/{user_id}")
async def dev_login_as(user_id: str):
    """Login as a specific user in dev mode - bypasses Auth0."""
    try:
        # Get user
        user_response = db_service.client.table("users").select("*").eq("id", user_id).single().execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = user_response.data

        # Get tenant
        tenant_response = db_service.client.table("tenants").select("*").eq("id", user["tenant_id"]).single().execute()
        if not tenant_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )
        tenant = tenant_response.data

        return {
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user.get("role", "admin"),
            },
            "tenant": {
                "id": tenant["id"],
                "name": tenant["name"],
                "subscription_tier": tenant.get("subscription_tier", "free"),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to login as user: {str(e)}"
        )


@router.post("/dev/create-user")
async def dev_create_user(organization_name: Optional[str] = None):
    """Create a new user and tenant in dev mode for initial setup."""
    import uuid
    from datetime import datetime

    try:
        # Create tenant
        tenant_id = str(uuid.uuid4())
        tenant_data = {
            "id": tenant_id,
            "name": organization_name or "Dev Organization",
            "subscription_tier": "free",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        tenant_response = db_service.client.table("tenants").insert(tenant_data).execute()
        tenant = tenant_response.data[0]

        # Create user
        user_id = str(uuid.uuid4())
        user_data = {
            "id": user_id,
            "tenant_id": tenant_id,
            "email": "dev@example.com",
            "name": "Dev User",
            "role": "admin",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        user_response = db_service.client.table("users").insert(user_data).execute()
        user = user_response.data[0]

        return {
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "role": user["role"],
            },
            "tenant": {
                "id": tenant["id"],
                "name": tenant["name"],
                "subscription_tier": tenant.get("subscription_tier", "free"),
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


# =============================================================================
# END DEV MODE ENDPOINTS
# =============================================================================


@router.patch("/me")
async def update_current_user(
    updates: UserUpdateRequest,
    user_info: dict = Depends(get_current_user)
):
    """Update current user's profile information."""
    user = user_info.get("user")
    tenant = user_info.get("tenant")

    if not user or not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Build update data (only include fields that are provided)
    update_data = {}
    if updates.name is not None:
        update_data["name"] = updates.name
    if updates.email is not None:
        update_data["email"] = updates.email
    if updates.role is not None:
        # Only allow role updates if current user is admin
        if user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can update user roles"
            )
        update_data["role"] = updates.role

    if not update_data:
        # No updates provided
        return UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            tenant_id=tenant["id"],
            tenant_name=tenant["name"],
            subscription_plan=tenant.get("subscription_tier", "free"),
            has_environment=False,
            is_new=False
        )

    try:
        # Update user in database
        response = db_service.client.table("users").update(update_data).eq(
            "id", user["id"]
        ).eq("tenant_id", tenant["id"]).execute()

        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        updated_user = response.data[0]

        # Check if user has any environments
        env_response = db_service.client.table("environments").select(
            "id", count="exact"
        ).eq("tenant_id", tenant["id"]).execute()
        has_environment = (env_response.count or 0) > 0

        return UserResponse(
            id=updated_user["id"],
            email=updated_user["email"],
            name=updated_user["name"],
            role=updated_user["role"],
            tenant_id=tenant["id"],
            tenant_name=tenant["name"],
            subscription_plan=tenant.get("subscription_tier", "free"),
            has_environment=has_environment,
            is_new=False
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )
