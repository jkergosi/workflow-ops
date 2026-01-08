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
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token validation failed"
            )
        except Exception:
            # Some malformed tokens can raise non-JWT exceptions in the underlying libs.
            # Treat all decode failures as unauthenticated to avoid leaking 500s to clients.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token validation failed"
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
        tenant = None
        created_new_tenant = False

        # Check if tenant already exists by email
        existing_tenant = db_service.client.table("tenants").select("*").ilike(
            "email", email
        ).execute()

        if existing_tenant.data and len(existing_tenant.data) > 0:
            # Use existing tenant
            tenant = existing_tenant.data[0]
            # Update tenant name if organization_name provided
            if organization_name and tenant.get("name") != organization_name:
                db_service.client.table("tenants").update({
                    "name": organization_name
                }).eq("id", tenant["id"]).execute()
                tenant["name"] = organization_name
        else:
            # Create new tenant
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
            created_new_tenant = True

        # Check if user already exists for this tenant
        existing_user = db_service.client.table("users").select("*").eq(
            "tenant_id", tenant["id"]
        ).ilike("email", email).execute()

        if existing_user.data and len(existing_user.data) > 0:
            # Update existing user with supabase_auth_id
            user = existing_user.data[0]
            db_service.client.table("users").update({
                "supabase_auth_id": supabase_auth_id,
                "name": name
            }).eq("id", user["id"]).execute()
            user["supabase_auth_id"] = supabase_auth_id
            user["name"] = name
        else:
            # Create new user
            user_data = {
                "tenant_id": tenant["id"],
                "email": email,
                "name": name,
                "role": "admin",
                "status": "active",
                "supabase_auth_id": supabase_auth_id
            }

            user_response = db_service.client.table("users").insert(user_data).execute()

            if not user_response.data or len(user_response.data) == 0:
                # Rollback tenant creation only if we created it
                if created_new_tenant:
                    db_service.client.table("tenants").delete().eq("id", tenant["id"]).execute()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user"
                )

            user = user_response.data[0]

        return {
            "user": user,
            "tenant": tenant,
            "is_new": created_new_tenant
        }


# Impersonation token management (legacy, tenant-scoped admin impersonation)
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

        # Get admin user info for audit trail
        admin_user_response = db_service.client.table("users").select("*, tenants(*)").eq(
            "id", admin_user_id
        ).execute()

        admin_user = None
        admin_tenant = None
        if admin_user_response.data and len(admin_user_response.data) > 0:
            admin_user = admin_user_response.data[0]
            admin_tenant = admin_user.get("tenants")
            if not admin_tenant and admin_user.get("tenant_id"):
                admin_tenant_response = db_service.client.table("tenants").select("*").eq(
                    "id", admin_user["tenant_id"]
                ).execute()
                if admin_tenant_response.data and len(admin_tenant_response.data) > 0:
                    admin_tenant = admin_tenant_response.data[0]

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
            "impersonation_session_id": None,  # Legacy token doesn't have session ID
            "impersonated_user_id": user["id"],
            "impersonated_tenant_id": tenant["id"] if tenant else None,
            "actor_user": {
                "id": admin_user["id"],
                "email": admin_user["email"],
                "name": admin_user.get("name"),
                "role": admin_user.get("role"),
            } if admin_user else {"id": admin_user_id},
            "actor_user_id": admin_user_id,
            "actor_tenant_id": admin_tenant["id"] if admin_tenant else None,
            "admin_id": admin_user_id  # Keep for backward compatibility
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

    # If the caller is a Platform Admin with an active impersonation session, return impersonated context.
    # Migration: 9ed964cd8ba3 - create_platform_impersonation_sessions
    # See: alembic/versions/9ed964cd8ba3_create_platform_impersonation_sessions.py
    is_platform_admin = False
    try:
        pa_resp = db_service.client.table("platform_admins").select("user_id").eq("user_id", user["id"]).maybe_single().execute()
        is_platform_admin = bool(pa_resp.data)
    except Exception:
        is_platform_admin = False

    if is_platform_admin:
        sess_resp = (
            db_service.client.table("platform_impersonation_sessions")
            .select("id, impersonated_user_id, ended_at")
            .eq("actor_user_id", user["id"])
            .is_("ended_at", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        sessions = sess_resp.data or []
        if sessions:
            sess = sessions[0]
            target_user_id = sess.get("impersonated_user_id")
            target_resp = db_service.client.table("users").select("*, tenants(*)").eq("id", target_user_id).execute()
            if target_resp.data and len(target_resp.data) > 0:
                target_user = target_resp.data[0]
                target_tenant = target_user.get("tenants")
                if not target_tenant and target_user.get("tenant_id"):
                    target_tenant_resp = db_service.client.table("tenants").select("*").eq("id", target_user["tenant_id"]).execute()
                    if target_tenant_resp.data and len(target_tenant_resp.data) > 0:
                        target_tenant = target_tenant_resp.data[0]

                return {
                    "user": {
                        "id": target_user["id"],
                        "email": target_user["email"],
                        "name": target_user.get("name"),
                        "role": target_user.get("role", "viewer"),
                    },
                    "tenant": {
                        "id": target_tenant["id"],
                        "name": target_tenant.get("name"),
                        "subscription_tier": target_tenant.get("subscription_tier", "free"),
                    } if target_tenant else None,
                    "impersonating": True,
                    "impersonation_session_id": sess.get("id"),
                    "impersonated_user_id": target_user["id"],
                    "impersonated_tenant_id": target_tenant["id"] if target_tenant else None,
                    "actor_user": {
                        "id": user["id"],
                        "email": user["email"],
                        "name": user.get("name"),
                        "role": user.get("role"),
                    },
                    "actor_user_id": user["id"],
                    "actor_tenant_id": tenant["id"] if tenant else None,
                }

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


def is_user_admin(user: Dict[str, Any]) -> bool:
    """
    Check if a user has admin role.

    Args:
        user: User dictionary containing user information

    Returns:
        bool: True if user has admin role, False otherwise
    """
    if not user:
        return False

    # Handle both nested user dict (from get_current_user response)
    # and direct user dict (from database)
    user_data = user.get("user", user) if "user" in user else user
    role = user_data.get("role", "")

    return role == "admin"


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
                "is_new": False,
                "no_credentials": True
            }

        # Get or create app user
        user_info = await supabase_auth_service.get_or_create_user(supabase_user_id, email)
        
        user = user_info.get("user")
        tenant = user_info.get("tenant")
        
        if not user:
            return user_info

        # If the caller is a Platform Admin with an active impersonation session, return impersonated context.
        # Migration: 9ed964cd8ba3 - create_platform_impersonation_sessions
        # See: alembic/versions/9ed964cd8ba3_create_platform_impersonation_sessions.py
        is_platform_admin = False
        try:
            pa_resp = db_service.client.table("platform_admins").select("user_id").eq("user_id", user["id"]).maybe_single().execute()
            is_platform_admin = bool(pa_resp.data)
        except Exception:
            is_platform_admin = False

        if is_platform_admin:
            sess_resp = (
                db_service.client.table("platform_impersonation_sessions")
                .select("id, impersonated_user_id, ended_at")
                .eq("actor_user_id", user["id"])
                .is_("ended_at", "null")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            sessions = sess_resp.data or []
            if sessions:
                sess = sessions[0]
                target_user_id = sess.get("impersonated_user_id")
                target_resp = db_service.client.table("users").select("*, tenants(*)").eq("id", target_user_id).execute()
                if target_resp.data and len(target_resp.data) > 0:
                    target_user = target_resp.data[0]
                    target_tenant = target_user.get("tenants")
                    if not target_tenant and target_user.get("tenant_id"):
                        target_tenant_resp = db_service.client.table("tenants").select("*").eq("id", target_user["tenant_id"]).execute()
                        if target_tenant_resp.data and len(target_tenant_resp.data) > 0:
                            target_tenant = target_tenant_resp.data[0]

                    return {
                        "user": {
                            "id": target_user["id"],
                            "email": target_user["email"],
                            "name": target_user.get("name"),
                            "role": target_user.get("role", "viewer"),
                        },
                        "tenant": {
                            "id": target_tenant["id"],
                            "name": target_tenant.get("name"),
                            "subscription_tier": target_tenant.get("subscription_tier", "free"),
                        } if target_tenant else None,
                        "impersonating": True,
                        "impersonation_session_id": sess.get("id"),
                        "impersonated_user_id": target_user["id"],
                        "impersonated_tenant_id": target_tenant["id"] if target_tenant else None,
                        "actor_user": {
                            "id": user["id"],
                            "email": user["email"],
                            "name": user.get("name"),
                            "role": user.get("role"),
                        },
                        "actor_user_id": user["id"],
                        "actor_tenant_id": tenant["id"] if tenant else None,
                        "is_new": user_info.get("is_new", False),
                    }

        return user_info

    except HTTPException as e:
        # Invalid/expired tokens should behave like "no credentials" so the UI stays on /login.
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            return {
                "user": None,
                "tenant": None,
                "is_new": False,
                "no_credentials": True
            }
        return {
            "user": None,
            "tenant": None,
            "is_new": True
        }
