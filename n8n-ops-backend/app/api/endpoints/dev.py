"""Dev-only endpoints for bypassing Auth0 during development."""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import uuid

from app.services.database import db_service

router = APIRouter()


class LoginAsRequest(BaseModel):
    user_id: str


class CreateUserRequest(BaseModel):
    organization_name: Optional[str] = None


@router.get("/users")
async def get_dev_users():
    """Get all users for dev login switcher."""
    try:
        response = db_service.client.table("users").select("id, email, name, tenant_id, role").execute()
        return {"users": response.data or []}
    except Exception as e:
        print(f"Error fetching users: {e}")
        return {"users": []}


@router.post("/login-as")
async def dev_login_as(request: LoginAsRequest):
    """Login as a specific user (dev mode only)."""
    try:
        # Get user with tenant
        user_response = db_service.client.table("users").select("*, tenants(*)").eq(
            "id", request.user_id
        ).execute()

        if not user_response.data or len(user_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        user = user_response.data[0]
        tenant = user.get("tenants")

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
            } if tenant else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to login as user: {str(e)}"
        )


@router.post("/create-user")
async def dev_create_user(request: CreateUserRequest):
    """Create a new user and tenant (dev mode only)."""
    try:
        # Create tenant
        tenant_name = request.organization_name or "Dev Organization"
        tenant_data = {
            "name": tenant_name,
            "email": f"dev-{uuid.uuid4().hex[:8]}@example.com",
            "subscription_tier": "free",
            "status": "active"
        }

        tenant_response = db_service.client.table("tenants").insert(tenant_data).execute()

        if not tenant_response.data or len(tenant_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create tenant"
            )

        tenant = tenant_response.data[0]

        # Create user
        user_data = {
            "tenant_id": tenant["id"],
            "email": f"dev-user-{uuid.uuid4().hex[:8]}@example.com",
            "name": "Dev User",
            "role": "admin",
            "status": "active",
        }

        user_response = db_service.client.table("users").insert(user_data).execute()

        if not user_response.data or len(user_response.data) == 0:
            # Rollback tenant creation
            db_service.client.table("tenants").delete().eq("id", tenant["id"]).execute()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )

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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )
