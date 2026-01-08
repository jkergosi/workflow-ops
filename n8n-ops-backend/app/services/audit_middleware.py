"""Audit middleware to auto-inject impersonation context into all audit logs.

This middleware automatically captures impersonation context during write operations
and provides utilities for extracting impersonation metadata from user context.

Key Features:
- Automatically logs all write operations (POST, PUT, PATCH, DELETE) during impersonation
- Captures dual-actor attribution (impersonator + impersonated user)
- Provides context extraction utilities for manual audit log creation
- Works seamlessly with existing authentication flow

Usage in FastAPI app:
    from app.services.audit_middleware import AuditMiddleware

    app = FastAPI()
    app.add_middleware(AuditMiddleware)

Usage in endpoints for manual audit logging:
    from app.services.audit_middleware import get_audit_context
    from app.api.endpoints.admin_audit import create_audit_log

    user_context = await get_current_user(credentials)
    audit_ctx = get_audit_context(user_context)

    await create_audit_log(
        action_type="WORKFLOW_UPDATED",
        action="Updated workflow settings",
        **audit_ctx  # Spreads actor_id, tenant_id, impersonation fields
    )
"""
from typing import Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

from app.services.database import db_service
from app.services.auth_service import supabase_auth_service
from app.api.endpoints.admin_audit import create_audit_log

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware to automatically audit write operations during impersonation.

    This middleware:
    1. Intercepts all HTTP requests
    2. Detects write operations (POST, PUT, PATCH, DELETE)
    3. Checks if the request is made during an active impersonation session
    4. Automatically creates audit logs with dual-actor attribution

    The audit log records:
    - actor_user: The impersonator (platform admin)
    - impersonated_user: The effective user being impersonated
    - tenant_id: The effective tenant context
    - action: The HTTP method and path
    - metadata: Additional request details
    """

    # Paths to exclude from automatic audit logging
    EXCLUDED_PATHS = {
        "/api/v1/health",
        "/api/v1/sse",
        "/api/v1/admin/audit",  # Don't log audit log queries
        "/api/v1/observability",  # High-volume monitoring endpoints
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    # HTTP methods that trigger audit logging
    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info("AuditMiddleware initialized")

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process each request and create audit logs for write operations during impersonation.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            Response: The HTTP response
        """
        # Execute the request first
        response = await call_next(request)

        # Only audit write operations
        if request.method not in self.WRITE_METHODS:
            return response

        # Skip excluded paths
        request_path = request.url.path
        if any(request_path.startswith(excluded) for excluded in self.EXCLUDED_PATHS):
            return response

        # Try to audit the operation (don't fail the request if audit fails)
        try:
            await self._create_impersonation_audit_log(request, response)
        except Exception as e:
            # Log the error but don't fail the request
            logger.error(f"Failed to create audit log for {request.method} {request_path}: {e}")

        return response

    async def _create_impersonation_audit_log(
        self,
        request: Request,
        response: Response
    ) -> None:
        """
        Create an audit log if the request was made during an impersonation session.

        Args:
            request: The HTTP request
            response: The HTTP response
        """
        # Extract authorization header
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return

        token = auth_header.split(" ", 1)[1].strip()

        # Verify the token and get the actor user
        try:
            payload = await supabase_auth_service.verify_token(token)
            supabase_user_id = payload.get("sub")
            if not supabase_user_id:
                return
        except Exception:
            # Invalid token - not an error, just skip audit logging
            return

        # Get the actor user from the database
        try:
            actor_resp = db_service.client.table("users").select(
                "id, email, name"
            ).eq(
                "supabase_auth_id", supabase_user_id
            ).maybe_single().execute()

            actor = actor_resp.data or {}
            actor_user_id = actor.get("id")
            if not actor_user_id:
                return
        except Exception as e:
            logger.warning(f"Failed to fetch actor user: {e}")
            return

        # Check for active impersonation session
        try:
            sess_resp = (
                db_service.client.table("platform_impersonation_sessions")
                .select("id, actor_user_id, impersonated_user_id, impersonated_tenant_id")
                .eq("actor_user_id", actor_user_id)
                .is_("ended_at", "null")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            sessions = sess_resp.data or []
            if not sessions:
                # No active impersonation session - skip audit logging
                return

            session = sessions[0]
        except Exception as e:
            logger.warning(f"Failed to fetch impersonation session: {e}")
            return

        # Get impersonated user details
        try:
            impersonated_user_resp = db_service.client.table("users").select(
                "id, email, name"
            ).eq(
                "id", session.get("impersonated_user_id")
            ).maybe_single().execute()

            impersonated_user = impersonated_user_resp.data or {}
        except Exception as e:
            logger.warning(f"Failed to fetch impersonated user: {e}")
            impersonated_user = {}

        # Create the audit log
        try:
            await create_audit_log(
                action_type="IMPERSONATION_ACTION",
                action=f"{request.method} {request.url.path}",
                actor_id=actor_user_id,
                actor_email=actor.get("email"),
                actor_name=actor.get("name"),
                tenant_id=session.get("impersonated_tenant_id"),
                resource_type="http_request",
                resource_id=str(session.get("id")),
                metadata={
                    "method": request.method,
                    "path": str(request.url.path),
                    "query_params": dict(request.query_params),
                    "status_code": response.status_code,
                    "impersonation_session_id": str(session.get("id")),
                },
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                # Impersonation context
                impersonation_session_id=str(session.get("id")),
                impersonated_user_id=str(session.get("impersonated_user_id")),
                impersonated_user_email=impersonated_user.get("email"),
                impersonated_tenant_id=str(session.get("impersonated_tenant_id")),
            )

            logger.info(
                f"Audit log created for impersonation action: "
                f"{request.method} {request.url.path} "
                f"(actor: {actor.get('email')}, "
                f"impersonated: {impersonated_user.get('email')})"
            )
        except Exception as e:
            # Don't fail the request if audit logging fails
            logger.error(f"Failed to create impersonation audit log: {e}")


def get_audit_context(user_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract audit context from user context for manual audit log creation.

    This function provides a consistent way to extract all necessary fields
    for audit logging, including impersonation context when present.

    Args:
        user_context: User context dict from get_current_user dependency

    Returns:
        Dict with all audit log fields:
        - actor_id: The user performing the action (impersonator if impersonating)
        - actor_email: Email of the actor
        - actor_name: Name of the actor
        - tenant_id: The effective tenant context
        - tenant_name: Name of the tenant (if available)
        - impersonation_session_id: Session ID if impersonating (or None)
        - impersonated_user_id: Target user ID if impersonating (or None)
        - impersonated_user_email: Target user email if impersonating (or None)
        - impersonated_tenant_id: Target tenant ID if impersonating (or None)

    Example:
        user_context = await get_current_user(credentials)
        audit_ctx = get_audit_context(user_context)

        await create_audit_log(
            action_type="WORKFLOW_UPDATED",
            action="Updated workflow settings",
            resource_type="workflow",
            resource_id=workflow_id,
            **audit_ctx  # Spreads all audit context fields
        )

    Note:
        During impersonation:
        - actor_* fields represent the impersonator (platform admin)
        - impersonated_* fields represent the effective user being impersonated
        - tenant_id represents the effective tenant context (impersonated user's tenant)
    """
    is_impersonating = user_context.get("impersonating", False)

    # Extract user info (effective user, which may be impersonated)
    # Handle None values gracefully
    user = user_context.get("user") or {}
    tenant = user_context.get("tenant") or {}

    # Base context - effective user and tenant
    context = {
        "tenant_id": tenant.get("id") if tenant else None,
        "tenant_name": tenant.get("name") if tenant else None,
    }

    if is_impersonating:
        # During impersonation: actor is the impersonator, user is the impersonated
        actor_user = user_context.get("actor_user") or {}
        context.update({
            "actor_id": actor_user.get("id") if actor_user else None,
            "actor_email": actor_user.get("email") if actor_user else None,
            "actor_name": actor_user.get("name") if actor_user else None,
            "impersonation_session_id": user_context.get("impersonation_session_id"),
            "impersonated_user_id": user.get("id") if user else None,
            "impersonated_user_email": user.get("email") if user else None,
            "impersonated_tenant_id": tenant.get("id") if tenant else None,
        })
    else:
        # Normal operation: actor is the current user
        context.update({
            "actor_id": user.get("id") if user else None,
            "actor_email": user.get("email") if user else None,
            "actor_name": user.get("name") if user else None,
            "impersonation_session_id": None,
            "impersonated_user_id": None,
            "impersonated_user_email": None,
            "impersonated_tenant_id": None,
        })

    return context


def get_impersonation_context(user_context: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Extract only impersonation-related fields from user context.

    This is a convenience function for when you already have actor_id and tenant_id
    set up and only need the impersonation-specific fields.

    Args:
        user_context: User context dict from get_current_user dependency

    Returns:
        Dict with impersonation fields:
        - impersonation_session_id: Session ID if impersonating (or None)
        - impersonated_user_id: Target user ID if impersonating (or None)
        - impersonated_user_email: Target user email if impersonating (or None)
        - impersonated_tenant_id: Target tenant ID if impersonating (or None)

    Example:
        user_context = await get_current_user(credentials)
        impersonation_ctx = get_impersonation_context(user_context)

        await create_audit_log(
            action_type="USER_UPDATED",
            action="Updated user profile",
            actor_id=user_context["user"]["id"],  # Set manually
            tenant_id=user_context["tenant"]["id"],  # Set manually
            **impersonation_ctx  # Only spreads impersonation fields
        )

    Note:
        This is equivalent to extract_impersonation_context() in admin_audit.py
        but provided here for consistency with the middleware module.
    """
    if not user_context.get("impersonating"):
        return {
            "impersonation_session_id": None,
            "impersonated_user_id": None,
            "impersonated_user_email": None,
            "impersonated_tenant_id": None,
        }

    user = user_context.get("user", {})
    return {
        "impersonation_session_id": user_context.get("impersonation_session_id"),
        "impersonated_user_id": user_context.get("impersonated_user_id"),
        "impersonated_user_email": user.get("email"),
        "impersonated_tenant_id": user_context.get("impersonated_tenant_id"),
    }
