"""Supabase authentication service for verifying JWT tokens and managing user sessions."""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.services.database import db_service

security = HTTPBearer(auto_error=False)


class SupabaseAuthService:
    """Service for Supabase authentication and user management."""

    def __init__(self):
        self.jwt_secret = settings.SUPABASE_JWT_SECRET
        self.algorithms = ["HS256"]

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify a Supabase JWT token and return the payload."""
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=self.algorithms,
                audience="authenticated"
            )
            return payload
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token validation failed: {str(e)}"
            )

    async def get_or_create_user(self, supabase_user_id: str, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Get or create an app user from Supabase auth user."""
        # Check if user exists by supabase_auth_id
        existing = db_service.client.table("users").select("*, tenants(*)").eq(
            "supabase_auth_id", supabase_user_id
        ).execute()

        if existing.data and len(existing.data) > 0:
            user = existing.data[0]
            return {
                "user": user,
                "tenant": user.get("tenants"),
                "is_new": False
            }

        # Check if user exists by email (for existing users without supabase_auth_id)
        # Use case-insensitive matching
        existing_by_email = db_service.client.table("users").select("*, tenants(*)").ilike(
            "email", email
        ).execute()

        if existing_by_email.data and len(existing_by_email.data) > 0:
            # Link existing user to Supabase auth
            user = existing_by_email.data[0]
            db_service.client.table("users").update({
                "supabase_auth_id": supabase_user_id
            }).eq("id", user["id"]).execute()

            return {
                "user": user,
                "tenant": user.get("tenants"),
                "is_new": False
            }

        # User doesn't exist - return None to indicate onboarding needed
        return {
            "user": None,
            "tenant": None,
            "is_new": True,
            "supabase_auth_id": supabase_user_id,
            "email": email,
            "name": name or email.split("@")[0]
        }

    async def create_user_and_tenant(
        self,
        supabase_auth_id: str,
        email: str,
        name: str,
        organization_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new user and their default tenant."""
        # Create tenant first
        tenant_name = organization_name or f"{name}'s Organization"
        tenant_data = {
            "name": tenant_name,
            "email": email,
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
            "email": email,
            "name": name,
            "role": "admin",
            "status": "active",
            "is_active": True,
            "supabase_auth_id": supabase_auth_id
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
            "user": user,
            "tenant": tenant,
            "is_new": True
        }


# Impersonation token management
IMPERSONATION_TOKEN_PREFIX = "impersonate:"
IMPERSONATION_EXPIRE_MINUTES = 60


def create_impersonation_token(admin_user_id: str, target_user_id: str, tenant_id: str) -> str:
    """Create a JWT token for admin impersonation."""
    expire = datetime.utcnow() + timedelta(minutes=IMPERSONATION_EXPIRE_MINUTES)
    payload = {
        "type": "impersonation",
        "admin_id": admin_user_id,
        "target_id": target_user_id,
        "tenant_id": tenant_id,
        "exp": expire
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return f"{IMPERSONATION_TOKEN_PREFIX}{token}"


def verify_impersonation_token(token: str) -> Dict[str, Any]:
    """Verify an impersonation token and return the payload."""
    if not token.startswith(IMPERSONATION_TOKEN_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid impersonation token format"
        )

    jwt_token = token[len(IMPERSONATION_TOKEN_PREFIX):]
    try:
        payload = jwt.decode(jwt_token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "impersonation":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Impersonation token validation failed: {str(e)}"
        )


supabase_auth_service = SupabaseAuthService()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """Dependency to get the current authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    token = credentials.credentials

    # Handle impersonation tokens
    if token.startswith(IMPERSONATION_TOKEN_PREFIX):
        impersonation_payload = verify_impersonation_token(token)
        target_user_id = impersonation_payload.get("target_id")
        admin_user_id = impersonation_payload.get("admin_id")

        # Get target user
        user_response = db_service.client.table("users").select("*, tenants(*)").eq(
            "id", target_user_id
        ).execute()

        if not user_response.data or len(user_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Impersonation target user not found"
            )

        user = user_response.data[0]
        tenant = user.get("tenants")

        # If join didn't return tenant, fetch it separately
        if not tenant and user.get("tenant_id"):
            tenant_response = db_service.client.table("tenants").select("*").eq(
                "id", user["tenant_id"]
            ).execute()
            if tenant_response.data and len(tenant_response.data) > 0:
                tenant = tenant_response.data[0]

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
            } if tenant else None,
            "impersonating": True,
            "admin_id": admin_user_id
        }

    # Verify Supabase JWT
    payload = await supabase_auth_service.verify_token(token)
    supabase_user_id = payload.get("sub")
    email = payload.get("email")

    if not supabase_user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    # Get or create app user
    user_info = await supabase_auth_service.get_or_create_user(supabase_user_id, email)

    if user_info.get("is_new") and user_info.get("user") is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="onboarding_required",
            headers={"X-Onboarding-Required": "true"}
        )

    user = user_info["user"]
    tenant = user_info["tenant"]

    # If join didn't return tenant, fetch it separately
    if not tenant and user.get("tenant_id"):
        tenant_response = db_service.client.table("tenants").select("*").eq(
            "id", user["tenant_id"]
        ).execute()
        if tenant_response.data and len(tenant_response.data) > 0:
            tenant = tenant_response.data[0]

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
        } if tenant else None
    }


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Dict[str, Any]:
    """Dependency to get the current user, allowing new users for onboarding."""
    if not credentials:
        return {
            "user": None,
            "tenant": None,
            "is_new": False,
            "no_credentials": True
        }

    token = credentials.credentials

    # Handle impersonation tokens
    if token.startswith(IMPERSONATION_TOKEN_PREFIX):
        return await get_current_user(credentials)

    try:
        # Verify Supabase JWT
        payload = await supabase_auth_service.verify_token(token)
        supabase_user_id = payload.get("sub")
        email = payload.get("email")

        if not supabase_user_id or not email:
            return {
                "user": None,
                "tenant": None,
                "is_new": True
            }

        # Get or create app user
        return await supabase_auth_service.get_or_create_user(supabase_user_id, email)

    except HTTPException:
        return {
            "user": None,
            "tenant": None,
            "is_new": True
        }
