# Audit Middleware - Comprehensive Guide

## Overview

The Audit Middleware provides automatic audit logging for all write operations during impersonation sessions, ensuring complete visibility and accountability when platform administrators act on behalf of users.

### Key Features

- ✅ **Automatic Audit Logging**: Captures all write operations (POST, PUT, PATCH, DELETE) during impersonation
- ✅ **Dual-Actor Attribution**: Records both the impersonator (platform admin) and impersonated user
- ✅ **Context Extraction Utilities**: Helper functions for manual audit logging
- ✅ **Zero Configuration**: Works seamlessly with existing authentication flow
- ✅ **Non-Intrusive**: Failures in audit logging don't break main operations
- ✅ **Performance Optimized**: Minimal overhead, excluded paths for high-traffic endpoints

---

## Architecture

### Components

1. **AuditMiddleware** - FastAPI middleware that intercepts requests
2. **get_audit_context()** - Extracts complete audit context from user info
3. **get_impersonation_context()** - Extracts only impersonation fields

### Flow Diagram

```
Request → Auth → AuditMiddleware → Endpoint Handler
                      ↓
                 Check if write?
                      ↓
              Check impersonation?
                      ↓
                Create audit log
                      ↓
                 Continue request
```

### Data Model

During impersonation, audit logs contain:

```json
{
  "actor_id": "admin-999",              // Platform admin (impersonator)
  "actor_email": "admin@platform.com",
  "actor_name": "Platform Admin",

  "tenant_id": "tenant-456",            // Effective tenant
  "tenant_name": "Target Tenant",

  "impersonation_session_id": "session-789",
  "impersonated_user_id": "user-123",   // User being impersonated
  "impersonated_user_email": "user@example.com",
  "impersonated_tenant_id": "tenant-456",

  "action_type": "IMPERSONATION_ACTION",
  "action": "POST /api/v1/workflows",
  "timestamp": "2024-01-08T12:34:56Z"
}
```

---

## Installation

### 1. Add Middleware to FastAPI App

In `main.py`:

```python
from fastapi import FastAPI
from app.services.audit_middleware import AuditMiddleware

app = FastAPI()

# Add middleware (after CORS, before route handlers)
app.add_middleware(AuditMiddleware)
```

### 2. Import Context Utilities

In your endpoint files:

```python
from app.services.audit_middleware import get_audit_context, get_impersonation_context
from app.services.auth_service import get_current_user
from app.api.endpoints.admin_audit import create_audit_log
```

---

## Usage Patterns

### Pattern 1: Automatic Audit Logging (Middleware)

The middleware automatically logs all write operations during impersonation:

```python
# No code needed - middleware handles this automatically!
# All POST/PUT/PATCH/DELETE requests during impersonation are logged
```

**What gets logged:**
- HTTP method and path
- Actor (platform admin)
- Impersonated user
- Tenant context
- Request metadata (IP, user-agent, query params, status code)

### Pattern 2: Manual Audit Logging with Full Context

For business-critical operations where you want detailed audit logs:

```python
@router.post("/workflows/{workflow_id}/promote")
async def promote_workflow(
    workflow_id: str,
    user_info: dict = Depends(get_current_user)
):
    # Extract complete audit context
    audit_ctx = get_audit_context(user_info)

    # Your business logic
    result = await perform_promotion(workflow_id)

    # Create detailed audit log
    await create_audit_log(
        action_type="WORKFLOW_PROMOTED",
        action=f"Promoted workflow {workflow_id}",
        resource_type="workflow",
        resource_id=workflow_id,
        resource_name=result.get("name"),
        old_value={"environment": "dev"},
        new_value={"environment": "prod"},
        **audit_ctx  # Spreads all audit fields
    )

    return result
```

**Benefits:**
- Captures business-specific details (old_value, new_value)
- Works in both normal and impersonation scenarios
- Single line of code to extract context

### Pattern 3: Manual Context with Impersonation Fields

When you need custom actor/tenant handling:

```python
@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    new_role: str,
    user_info: dict = Depends(get_current_user)
):
    # Extract only impersonation fields
    impersonation_ctx = get_impersonation_context(user_info)

    # Custom actor extraction
    user = user_info.get("user", {})
    tenant = user_info.get("tenant", {})

    if user_info.get("impersonating"):
        actor = user_info.get("actor_user", {})
    else:
        actor = user

    # Create audit log with custom + impersonation fields
    await create_audit_log(
        action_type="USER_ROLE_CHANGED",
        action=f"Changed user role to {new_role}",
        actor_id=actor.get("id"),
        actor_email=actor.get("email"),
        tenant_id=tenant.get("id"),
        resource_type="user",
        resource_id=user_id,
        **impersonation_ctx
    )

    return {"status": "updated"}
```

---

## Configuration

### Excluded Paths

The middleware skips audit logging for certain paths to avoid noise:

```python
EXCLUDED_PATHS = {
    "/api/v1/health",           # Health checks
    "/api/v1/sse",              # Server-sent events
    "/api/v1/admin/audit",      # Audit log queries
    "/api/v1/observability",    # High-volume monitoring
    "/docs",                    # API documentation
    "/openapi.json",            # OpenAPI spec
    "/redoc",                   # ReDoc documentation
}
```

To add more excluded paths, modify the `EXCLUDED_PATHS` set in `audit_middleware.py`.

### Write Methods

Only these HTTP methods trigger audit logging:

```python
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
```

GET requests are never audited by the middleware (but can be manually audited if needed).

---

## API Reference

### `AuditMiddleware`

FastAPI middleware class that automatically audits write operations during impersonation.

**Usage:**
```python
app.add_middleware(AuditMiddleware)
```

**Behavior:**
- Intercepts all HTTP requests
- Checks if request is a write operation
- Verifies if impersonation session is active
- Creates audit log with dual-actor attribution
- Never fails the main request (errors are logged but swallowed)

---

### `get_audit_context(user_context: dict) -> dict`

Extracts complete audit context from user context.

**Parameters:**
- `user_context`: User context dict from `get_current_user()` dependency

**Returns:**
Dictionary with all audit log fields:
```python
{
    "actor_id": str,
    "actor_email": str,
    "actor_name": str,
    "tenant_id": str,
    "tenant_name": str,
    "impersonation_session_id": Optional[str],
    "impersonated_user_id": Optional[str],
    "impersonated_user_email": Optional[str],
    "impersonated_tenant_id": Optional[str],
}
```

**Example:**
```python
user_info = await get_current_user(credentials)
audit_ctx = get_audit_context(user_info)

await create_audit_log(
    action_type="WORKFLOW_UPDATED",
    action="Updated workflow",
    resource_type="workflow",
    resource_id=workflow_id,
    **audit_ctx
)
```

**Best for:**
- Simple, consistent audit logging
- Handling both normal and impersonation scenarios
- When you don't need custom actor/tenant logic

---

### `get_impersonation_context(user_context: dict) -> dict`

Extracts only impersonation-related fields from user context.

**Parameters:**
- `user_context`: User context dict from `get_current_user()` dependency

**Returns:**
Dictionary with impersonation fields:
```python
{
    "impersonation_session_id": Optional[str],
    "impersonated_user_id": Optional[str],
    "impersonated_user_email": Optional[str],
    "impersonated_tenant_id": Optional[str],
}
```

**Example:**
```python
user_info = await get_current_user(credentials)
impersonation_ctx = get_impersonation_context(user_info)

await create_audit_log(
    action_type="USER_UPDATED",
    action="Updated user",
    actor_id=user_info["user"]["id"],  # Set manually
    tenant_id=user_info["tenant"]["id"],  # Set manually
    **impersonation_ctx
)
```

**Best for:**
- When you need custom actor/tenant extraction
- When integrating with existing audit log calls
- When you want explicit control over actor fields

---

## Querying Audit Logs

### Find All Actions During Impersonation Session

```python
from app.services.database import db_service

response = db_service.client.table("audit_logs").select(
    "*"
).eq(
    "impersonation_session_id", session_id
).order(
    "timestamp", desc=True
).execute()

logs = response.data or []
```

### Find All Actions by Impersonated User

```python
response = db_service.client.table("audit_logs").select(
    "*"
).eq(
    "impersonated_user_id", user_id
).order(
    "timestamp", desc=True
).execute()

logs = response.data or []
```

### Find All Actions by Platform Admin (Actor)

```python
response = db_service.client.table("audit_logs").select(
    "*"
).eq(
    "actor_id", admin_user_id
).is_not(
    "impersonation_session_id", "null"
).order(
    "timestamp", desc=True
).execute()

logs = response.data or []
```

---

## Error Handling

### Middleware Error Handling

The middleware is designed to NEVER fail the main request:

```python
try:
    await self._create_impersonation_audit_log(request, response)
except Exception as e:
    # Log the error but don't fail the request
    logger.error(f"Failed to create audit log: {e}")
```

### Context Extraction Error Handling

Context extraction functions handle missing/None values gracefully:

```python
# Missing fields return None, not exceptions
user_context = {"user": None, "tenant": None}
audit_ctx = get_audit_context(user_context)
# Returns: {"actor_id": None, "tenant_id": None, ...}
```

---

## Performance Considerations

### Middleware Overhead

- **Excluded Paths**: High-traffic endpoints are excluded (health, SSE, observability)
- **Early Returns**: Non-write operations return immediately (no DB queries)
- **Non-Blocking**: Audit log creation doesn't block the response
- **Cached Queries**: Database queries are optimized with proper indexes

### Optimization Tips

1. **Use Indexes**: Ensure `audit_logs` table has indexes on:
   - `impersonation_session_id`
   - `impersonated_user_id`
   - `actor_id`
   - `tenant_id`
   - `timestamp`

2. **Exclude Noisy Endpoints**: Add high-volume endpoints to `EXCLUDED_PATHS`

3. **Batch Queries**: When querying audit logs, use pagination and filters

---

## Security Considerations

### What Gets Logged

✅ **Logged:**
- HTTP method and path
- Actor (impersonator) identity
- Impersonated user identity
- Tenant context
- Request metadata (IP, user-agent, query params)
- Response status code

❌ **Not Logged:**
- Request body (may contain sensitive data)
- Response body (may contain sensitive data)
- Authorization headers (contains tokens)
- Cookie values

### Access Control

Audit logs are only accessible to:
- Platform administrators via `/api/v1/admin/audit` endpoint
- The endpoint requires `require_platform_admin()` dependency

---

## Troubleshooting

### Issue: Audit logs not being created

**Check:**
1. Is the request a write operation? (POST/PUT/PATCH/DELETE)
2. Is there an active impersonation session?
3. Is the path excluded? (Check `EXCLUDED_PATHS`)
4. Check application logs for errors

**Debug:**
```python
import logging
logging.getLogger("app.services.audit_middleware").setLevel(logging.DEBUG)
```

### Issue: Missing impersonation fields in manual logs

**Check:**
1. Are you using `get_audit_context()` or `get_impersonation_context()`?
2. Is the user_context from `get_current_user()` dependency?
3. Is `user_context.get("impersonating")` True?

**Fix:**
```python
# Before
await create_audit_log(
    action_type="ACTION",
    actor_id=user_info["user"]["id"],  # Wrong during impersonation!
    tenant_id=user_info["tenant"]["id"],
)

# After
audit_ctx = get_audit_context(user_info)
await create_audit_log(
    action_type="ACTION",
    **audit_ctx  # Correct in all scenarios
)
```

### Issue: Duplicate audit logs

**Cause:** Both middleware and manual logging are creating logs for the same action.

**Solution:** This is intentional. The middleware creates a generic log for the HTTP request, while manual logs capture business-specific details. If you want to avoid this:

1. Add the endpoint to `EXCLUDED_PATHS`, OR
2. Only use manual logging (remove middleware), OR
3. Accept both logs (recommended for compliance)

---

## Testing

### Run Tests

```bash
pytest tests/test_audit_middleware.py -v
```

### Test Coverage

✅ **Covered:**
- Context extraction for normal users
- Context extraction during impersonation
- Impersonation context extraction
- Edge cases (missing fields, None values)
- Integration scenarios
- Middleware initialization
- Excluded paths
- Write methods detection

---

## Migration Guide

### Updating Existing Endpoints

**Before:**
```python
@router.post("/workflows")
async def create_workflow(user_info: dict = Depends(get_current_user)):
    # Old manual audit logging
    await create_audit_log(
        action_type="WORKFLOW_CREATED",
        action="Created workflow",
        actor_id=user_info["user"]["id"],
        actor_email=user_info["user"]["email"],
        tenant_id=user_info["tenant"]["id"],
    )
```

**After:**
```python
from app.services.audit_middleware import get_audit_context

@router.post("/workflows")
async def create_workflow(user_info: dict = Depends(get_current_user)):
    # New audit logging with impersonation support
    audit_ctx = get_audit_context(user_info)

    await create_audit_log(
        action_type="WORKFLOW_CREATED",
        action="Created workflow",
        **audit_ctx  # Automatically handles impersonation
    )
```

### Benefits of Migration

✅ Automatic impersonation support
✅ Consistent audit logging across all endpoints
✅ Less boilerplate code
✅ Future-proof for new audit fields

---

## Best Practices

### 1. Always Use Context Utilities

```python
# ✅ Good
audit_ctx = get_audit_context(user_info)
await create_audit_log(..., **audit_ctx)

# ❌ Bad
await create_audit_log(
    actor_id=user_info["user"]["id"],  # Breaks during impersonation
    ...
)
```

### 2. Use Meaningful Action Types

```python
# ✅ Good - Specific action type
await create_audit_log(
    action_type="WORKFLOW_PROMOTED",
    action="Promoted workflow from dev to prod",
    ...
)

# ❌ Bad - Generic action type
await create_audit_log(
    action_type="UPDATE",
    action="Updated something",
    ...
)
```

### 3. Include Business Context

```python
# ✅ Good - Rich context
await create_audit_log(
    action_type="USER_ROLE_CHANGED",
    action="Changed user role",
    resource_type="user",
    resource_id=user_id,
    old_value={"role": "viewer"},
    new_value={"role": "admin"},
    reason="User requested admin access",
    **audit_ctx
)

# ❌ Bad - Minimal context
await create_audit_log(
    action_type="USER_UPDATED",
    **audit_ctx
)
```

### 4. Log Both Success and Failure

```python
try:
    result = await perform_operation()
    await create_audit_log(
        action_type="OPERATION_COMPLETED",
        **audit_ctx
    )
except Exception as e:
    await create_audit_log(
        action_type="OPERATION_FAILED",
        metadata={"error": str(e)},
        **audit_ctx
    )
    raise
```

---

## Related Documentation

- `audit_middleware.py` - Source code
- `audit_middleware_example.py` - Usage examples
- `test_audit_middleware.py` - Test suite
- `admin_audit.py` - Audit log endpoints and models
- `auth_service.py` - Authentication and impersonation

---

## Support

For questions or issues:
1. Check this README
2. Review examples in `audit_middleware_example.py`
3. Run tests: `pytest tests/test_audit_middleware.py -v`
4. Check application logs for error messages
