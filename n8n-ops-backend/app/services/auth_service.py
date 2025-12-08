"""Auth0 authentication service for verifying JWT tokens and managing user sessions."""
from typing import Optional, Dict, Any
import httpx
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.services.database import db_service

security = HTTPBearer()


class Auth0Service:
    """Service for Auth0 authentication and user management."""

    def __init__(self):
        self.domain = settings.AUTH0_DOMAIN
        self.api_audience = settings.AUTH0_API_AUDIENCE
        self.algorithms = ["RS256"]
        self._jwks: Optional[Dict] = None

    async def get_jwks(self) -> Dict:
        """Fetch JWKS from Auth0."""
        if self._jwks is None:
            jwks_url = f"https://{self.domain}/.well-known/jwks.json"
            async with httpx.AsyncClient() as client:
                response = await client.get(jwks_url)
                self._jwks = response.json()
        return self._jwks

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify an Auth0 JWT token and return the payload."""
        try:
            # Get the signing key
            jwks = await self.get_jwks()
            unverified_header = jwt.get_unverified_header(token)

            rsa_key = {}
            for key in jwks.get("keys", []):
                if key["kid"] == unverified_header.get("kid"):
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"]
                    }
                    break

            if not rsa_key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unable to find appropriate key"
                )

            # Verify the token
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=self.algorithms,
                audience=self.api_audience,
                issuer=f"https://{self.domain}/"
            )

            return payload

        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token validation failed: {str(e)}"
            )

    async def get_or_create_user(self, auth0_user: Dict[str, Any]) -> Dict[str, Any]:
        """Get or create a user based on Auth0 profile."""
        # Extract user info from Auth0 token
        auth0_id = auth0_user.get("sub")

        # Try multiple possible locations for email claim
        email = (
            auth0_user.get("email") or
            auth0_user.get(f"https://{self.domain}/email") or
            auth0_user.get("https://api.n8nops.com/email") or
            auth0_user.get(f"https://{self.domain}/claims/email")
        )

        # Debug: log what claims we received
        print(f"[Auth Debug] Token claims: {list(auth0_user.keys())}")
        print(f"[Auth Debug] sub={auth0_id}, email={email}")

        if not auth0_id or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required user information from Auth0. Got sub={auth0_id}, email={email}. Available claims: {list(auth0_user.keys())}"
            )

        # Now we can safely extract name (email is guaranteed to exist)
        name = auth0_user.get("name") or auth0_user.get("nickname") or email.split("@")[0]

        # Check if user exists by auth0_id
        existing = db_service.client.table("users").select("*, tenants(*)").eq(
            "auth0_id", auth0_id
        ).execute()

        if existing.data and len(existing.data) > 0:
            user = existing.data[0]
            return {
                "user": user,
                "tenant": user.get("tenants"),
                "is_new": False
            }

        # Check if user exists by email (for users created before Auth0)
        existing_by_email = db_service.client.table("users").select("*, tenants(*)").eq(
            "email", email
        ).execute()

        if existing_by_email.data and len(existing_by_email.data) > 0:
            # Update existing user with auth0_id
            user = existing_by_email.data[0]
            db_service.client.table("users").update({
                "auth0_id": auth0_id
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
            "auth0_id": auth0_id,
            "email": email,
            "name": name
        }

    async def create_user_and_tenant(
        self,
        auth0_id: str,
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
            "auth0_id": auth0_id
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


auth_service = Auth0Service()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Dependency to get the current authenticated user."""
    token = credentials.credentials

    # Verify the token with Auth0
    auth0_payload = await auth_service.verify_token(token)

    # Get or create the user
    user_info = await auth_service.get_or_create_user(auth0_payload)

    if user_info.get("is_new") and user_info.get("user") is None:
        # User needs to complete onboarding
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="onboarding_required",
            headers={"X-Onboarding-Required": "true"}
        )

    return user_info


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Dependency to get the current user, allowing new users for onboarding."""
    token = credentials.credentials
    auth0_payload = await auth_service.verify_token(token)
    return await auth_service.get_or_create_user(auth0_payload)
