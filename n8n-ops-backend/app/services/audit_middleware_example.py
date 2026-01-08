"""
Example usage patterns for the audit middleware.

This file demonstrates how to:
1. Integrate the middleware into your FastAPI app
2. Use get_audit_context() for manual audit logging
3. Use get_impersonation_context() when you already have actor/tenant
4. Handle audit logs in different scenarios
"""
from fastapi import FastAPI, Depends, HTTPException, status
from typing import Dict, Any

from app.services.audit_middleware import (
    AuditMiddleware,
    get_audit_context,
    get_impersonation_context,
)
from app.services.auth_service import get_current_user
from app.api.endpoints.admin_audit import create_audit_log


# ============================================================================
# Example 1: Adding the middleware to your FastAPI app
# ============================================================================

def setup_app_with_middleware():
    """
    Example: How to add the audit middleware to your FastAPI app.

    The middleware will automatically:
    - Detect impersonation sessions
    - Log all write operations (POST, PUT, PATCH, DELETE)
    - Record dual-actor attribution (impersonator + impersonated user)
    """
    app = FastAPI()

    # Add the audit middleware
    # This should be added AFTER CORS middleware but BEFORE route handlers
    app.add_middleware(AuditMiddleware)

    return app


# ============================================================================
# Example 2: Using get_audit_context() for comprehensive audit logging
# ============================================================================

async def example_workflow_update_with_full_context(
    workflow_id: str,
    workflow_data: Dict[str, Any],
    user_info: Dict[str, Any] = Depends(get_current_user)
):
    """
    Example: Update a workflow and log the action with full audit context.

    This is the RECOMMENDED approach - it automatically handles both
    normal and impersonation scenarios.
    """
    # Extract complete audit context (handles both normal and impersonation)
    audit_ctx = get_audit_context(user_info)

    # Update the workflow (your business logic here)
    # ... update workflow in database ...

    # Create audit log with complete context
    await create_audit_log(
        action_type="WORKFLOW_UPDATED",
        action=f"Updated workflow {workflow_id}",
        resource_type="workflow",
        resource_id=workflow_id,
        resource_name=workflow_data.get("name"),
        old_value={"status": "active"},  # Example old value
        new_value={"status": "modified"},  # Example new value
        **audit_ctx  # Spreads all audit fields including impersonation
    )

    return {"status": "updated", "workflow_id": workflow_id}


# ============================================================================
# Example 3: Using get_impersonation_context() for partial context
# ============================================================================

async def example_workflow_update_with_partial_context(
    workflow_id: str,
    workflow_data: Dict[str, Any],
    user_info: Dict[str, Any] = Depends(get_current_user)
):
    """
    Example: Update a workflow using partial context extraction.

    Use this when you need to customize actor_id or tenant_id fields
    but still want impersonation context.
    """
    # Extract only impersonation-specific fields
    impersonation_ctx = get_impersonation_context(user_info)

    # Manually extract actor and tenant
    user = user_info.get("user", {})
    tenant = user_info.get("tenant", {})

    # During impersonation, actor_user contains the impersonator
    if user_info.get("impersonating"):
        actor_user = user_info.get("actor_user", {})
        actor_id = actor_user.get("id")
        actor_email = actor_user.get("email")
    else:
        actor_id = user.get("id")
        actor_email = user.get("email")

    # Create audit log with custom fields + impersonation context
    await create_audit_log(
        action_type="WORKFLOW_UPDATED",
        action=f"Updated workflow {workflow_id}",
        actor_id=actor_id,
        actor_email=actor_email,
        tenant_id=tenant.get("id"),
        resource_type="workflow",
        resource_id=workflow_id,
        **impersonation_ctx  # Only spreads impersonation fields
    )

    return {"status": "updated", "workflow_id": workflow_id}


# ============================================================================
# Example 4: Handling different action types during impersonation
# ============================================================================

async def example_user_role_change(
    target_user_id: str,
    new_role: str,
    user_info: Dict[str, Any] = Depends(get_current_user)
):
    """
    Example: Change a user's role and log with proper attribution.

    During impersonation:
    - actor_* fields = platform admin who initiated the change
    - impersonated_* fields = the effective user context
    - tenant_id = the effective tenant (impersonated user's tenant)
    """
    audit_ctx = get_audit_context(user_info)

    # Business logic: Update user role
    # ... update user role in database ...

    # Audit log with proper attribution
    await create_audit_log(
        action_type="USER_ROLE_CHANGED",
        action=f"Changed user role to {new_role}",
        resource_type="user",
        resource_id=target_user_id,
        old_value={"role": "viewer"},
        new_value={"role": new_role},
        **audit_ctx
    )

    return {"status": "role_updated", "user_id": target_user_id}


# ============================================================================
# Example 5: Querying audit logs by impersonation session
# ============================================================================

async def example_get_impersonation_audit_trail(
    session_id: str,
    user_info: Dict[str, Any] = Depends(get_current_user)
):
    """
    Example: Retrieve all actions performed during a specific impersonation session.

    This is useful for:
    - Reviewing what a platform admin did during impersonation
    - Compliance audits
    - Security investigations
    """
    from app.services.database import db_service

    # Query audit logs by impersonation_session_id
    response = db_service.client.table("audit_logs").select(
        "*"
    ).eq(
        "impersonation_session_id", session_id
    ).order(
        "timestamp", desc=True
    ).execute()

    logs = response.data or []

    return {
        "session_id": session_id,
        "actions_count": len(logs),
        "actions": logs
    }


# ============================================================================
# Example 6: Detecting impersonation in your endpoint
# ============================================================================

async def example_sensitive_operation(
    user_info: Dict[str, Any] = Depends(get_current_user)
):
    """
    Example: Detect if an operation is being performed during impersonation.

    Use this to add extra validation or logging for sensitive operations.
    """
    is_impersonating = user_info.get("impersonating", False)

    if is_impersonating:
        # Extra logging for impersonation
        actor_user = user_info.get("actor_user", {})
        impersonated_user = user_info.get("user", {})

        print(f"[IMPERSONATION] Platform admin {actor_user.get('email')} "
              f"is acting as {impersonated_user.get('email')}")

        # You might want to restrict certain operations during impersonation
        # or require additional confirmation

    # Continue with operation
    audit_ctx = get_audit_context(user_info)

    await create_audit_log(
        action_type="SENSITIVE_OPERATION",
        action="Performed sensitive operation",
        **audit_ctx
    )

    return {"status": "completed"}


# ============================================================================
# Example 7: Complex scenario - Promotion with impersonation
# ============================================================================

async def example_promote_workflow_during_impersonation(
    workflow_id: str,
    source_env_id: str,
    target_env_id: str,
    user_info: Dict[str, Any] = Depends(get_current_user)
):
    """
    Example: Promote a workflow and create multiple audit logs.

    This shows how to maintain consistent audit trail across multiple operations.
    """
    audit_ctx = get_audit_context(user_info)

    # Log the promotion start
    await create_audit_log(
        action_type="DEPLOYMENT_CREATED",
        action=f"Started promotion of workflow {workflow_id}",
        resource_type="workflow",
        resource_id=workflow_id,
        metadata={
            "source_environment_id": source_env_id,
            "target_environment_id": target_env_id,
        },
        **audit_ctx
    )

    try:
        # Perform promotion (your business logic)
        # ... promotion logic ...

        # Log success
        await create_audit_log(
            action_type="DEPLOYMENT_COMPLETED",
            action=f"Completed promotion of workflow {workflow_id}",
            resource_type="workflow",
            resource_id=workflow_id,
            metadata={
                "source_environment_id": source_env_id,
                "target_environment_id": target_env_id,
                "status": "success",
            },
            **audit_ctx
        )

        return {"status": "promoted", "workflow_id": workflow_id}

    except Exception as e:
        # Log failure
        await create_audit_log(
            action_type="DEPLOYMENT_FAILED",
            action=f"Failed to promote workflow {workflow_id}: {str(e)}",
            resource_type="workflow",
            resource_id=workflow_id,
            metadata={
                "source_environment_id": source_env_id,
                "target_environment_id": target_env_id,
                "status": "failed",
                "error": str(e),
            },
            **audit_ctx
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Promotion failed: {str(e)}"
        )


# ============================================================================
# Example 8: Background job with audit trail
# ============================================================================

async def example_background_job_with_audit(
    job_id: str,
    user_context: Dict[str, Any]  # Passed from the endpoint that created the job
):
    """
    Example: Create audit logs in background jobs.

    IMPORTANT: When running background jobs, you need to pass the user_context
    from the endpoint that initiated the job, otherwise you won't have access
    to the authentication context.
    """
    audit_ctx = get_audit_context(user_context)

    # Log job start
    await create_audit_log(
        action_type="GITHUB_BACKUP_STARTED",
        action=f"Started background backup job {job_id}",
        resource_type="background_job",
        resource_id=job_id,
        **audit_ctx
    )

    try:
        # Perform background work
        # ... job logic ...

        # Log completion
        await create_audit_log(
            action_type="GITHUB_BACKUP_COMPLETED",
            action=f"Completed background backup job {job_id}",
            resource_type="background_job",
            resource_id=job_id,
            **audit_ctx
        )

    except Exception as e:
        # Log failure
        await create_audit_log(
            action_type="GITHUB_BACKUP_FAILED",
            action=f"Background backup job {job_id} failed: {str(e)}",
            resource_type="background_job",
            resource_id=job_id,
            metadata={"error": str(e)},
            **audit_ctx
        )
        raise


# ============================================================================
# Example 9: Checking if context indicates impersonation
# ============================================================================

def is_impersonating(user_info: Dict[str, Any]) -> bool:
    """
    Example: Simple utility to check if a user context indicates impersonation.

    Returns:
        bool: True if the user is being impersonated, False otherwise
    """
    return user_info.get("impersonating", False)


def get_effective_user_email(user_info: Dict[str, Any]) -> str:
    """
    Example: Get the effective user email (impersonated user if impersonating).

    Returns:
        str: Email of the effective user
    """
    user = user_info.get("user", {})
    return user.get("email", "")


def get_actor_email(user_info: Dict[str, Any]) -> str:
    """
    Example: Get the actor email (impersonator if impersonating, else current user).

    Returns:
        str: Email of the actor performing the action
    """
    if user_info.get("impersonating"):
        actor_user = user_info.get("actor_user", {})
        return actor_user.get("email", "")
    else:
        user = user_info.get("user", {})
        return user.get("email", "")


# ============================================================================
# Example 10: Integration with existing endpoints
# ============================================================================

"""
To integrate the middleware with existing endpoints, you typically need to:

1. Add the middleware to main.py:
   ```python
   from app.services.audit_middleware import AuditMiddleware
   app.add_middleware(AuditMiddleware)
   ```

2. Update existing manual audit log calls to use get_audit_context():
   ```python
   # Old way (manual)
   await create_audit_log(
       action_type="WORKFLOW_UPDATED",
       action="Updated workflow",
       actor_id=user_info["user"]["id"],
       actor_email=user_info["user"]["email"],
       tenant_id=user_info["tenant"]["id"],
   )

   # New way (with impersonation support)
   audit_ctx = get_audit_context(user_info)
   await create_audit_log(
       action_type="WORKFLOW_UPDATED",
       action="Updated workflow",
       **audit_ctx
   )
   ```

3. The middleware will automatically log write operations during impersonation.
   Manual audit logs are still recommended for important business actions to
   capture specific details (old_value, new_value, etc.).
"""
