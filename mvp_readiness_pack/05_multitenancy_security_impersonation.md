# 05 - Multi-Tenancy, Security & Impersonation

## tenant_id Enforcement Mechanisms

### Pattern: Extract tenant_id from Authenticated User Context

**File**: `n8n-ops-backend/app/services/auth_service.py:get_current_user()`

**Safe Pattern**:
```python
user_info = await get_current_user(credentials)
tenant = user_info.get("tenant")
tenant_id = tenant["id"]
```

**Never**: `tenant_id: str = ...` from path/query parameters

### Isolation Scanner

**File**: `core/tenant_isolation.py:TenantIsolationScanner`

**Purpose**: Scan all API endpoints to verify tenant isolation patterns

**Safe Patterns** (regex):
- `get_tenant_id\s*\(\s*user_info\s*\)`
- `user_info\s*\.\s*get\s*\(\s*["\']tenant["\']\s*\)`
- `tenant_id\s*=\s*get_tenant_id\s*\(`

**Unsafe Patterns** (regex):
- `tenant_id\s*:\s*str\s*=` (path/query parameter)
- `tenant_id\s*=\s*request\.` (from request object)
- `tenant_id\s*=\s*body\.` (from request body)

**Exempt Endpoints**:
- `/health`, `/auth`, `/login`, `/register`, `/onboard`
- `/platform/admin`, `/platform/impersonation`, `/platform/console` (cross-tenant by design)
- `/test` endpoints

**Usage**:
```python
from app.core.tenant_isolation import TenantIsolationScanner

scanner = TenantIsolationScanner()
results = await scanner.scan_all_endpoints()
report = scanner.generate_report(results)
```

**Test**: `tests/security/test_tenant_isolation.py`

**Risk**: Scanner relies on regex patterns. Obfuscated or dynamic tenant_id extraction may not be detected.

---

## RLS (Row-Level Security) Summary

### Supabase RLS

**Status**: ✅ **Documented** (as of 2026-01-08)

**Current State**:
- 12 of 76 tables have RLS enabled (15.8%)
- Backend uses SERVICE_KEY (bypasses RLS)
- Frontend uses ANON_KEY (enforces RLS when enabled)

**Documentation**: See [`n8n-ops-backend/docs/security/`](../n8n-ops-backend/docs/security/)
- [RLS_POLICIES.md](../n8n-ops-backend/docs/security/RLS_POLICIES.md) - Complete inventory
- [RLS_VERIFICATION.md](../n8n-ops-backend/docs/security/RLS_VERIFICATION.md) - Verification procedures
- [RLS_CHANGE_CHECKLIST.md](../n8n-ops-backend/docs/security/RLS_CHANGE_CHECKLIST.md) - Developer guide

**Gap**: Many critical tables lack RLS policies. See documentation for priority list.

**Recommendation**: Follow migration plan in RLS_POLICIES.md to close gaps.

### Application-Level Filtering

**Pattern**: Every DB query includes `WHERE tenant_id = ?`

**Example** (from `database.py`):
```python
response = self.client.table("environments")\
    .select("*")\
    .eq("tenant_id", tenant_id)\
    .execute()
```

**Universal Pattern**: No query should ever fetch data without tenant_id filter (except platform admin cross-tenant queries).

---

## Impersonation Mechanics

### Platform Admin Designation

**Table**: `platform_admins`

**Columns**:
- `user_id` (UUID): FK to users
- `created_at`: Timestamp

**API**: 
- `POST /api/v1/platform/admins` - Add platform admin
- `DELETE /api/v1/platform/admins/{user_id}` - Remove

**Guard**: `core/platform_admin.py:require_platform_admin()`

```python
def require_platform_admin():
    async def dependency(user_info: dict = Depends(get_current_user)):
        user_id = user_info["user"]["id"]
        # Query platform_admins table
        is_admin = check_platform_admin(user_id)
        if not is_admin:
            raise HTTPException(403, "Platform admin required")
        return user_info
    return dependency
```

**Migration**: `alembic/versions/98c25037a560_create_platform_admins_table.py`

**Test**: Unknown

**Policy**: Cannot impersonate other platform admins (enforced in backend + audited)
**Enforcement**: `platform_impersonation.start` and `tenants.impersonate_tenant_user` block when target is platform admin; blocked attempts write `IMPERSONATION_BLOCKED` audit log with reason.
**Tests**: `tests/security/test_impersonation_audit.py::TestImpersonationSecurityGuardrails` (covers allow admin→tenant-user, block admin→admin with audit)

### Tenant-Scoped Impersonation (same tenant)
- **Endpoint**: `POST /api/v1/auth/impersonate/{user_id}`
- **Guard**: Tenant admin only (server-side `user.role == "admin"`)
- **Test**: `tests/test_rbac_enforcement.py::test_impersonation_requires_admin_role`
- **Notes**: Nesting impersonation is blocked; self-impersonation returns 400.

### Impersonation Sessions

**Table**: `platform_impersonation_sessions`

**Columns**:
- `id` (UUID): Session ID
- `actor_user_id` (UUID): Platform admin performing impersonation
- `impersonated_user_id` (UUID): Target user
- `impersonated_tenant_id` (UUID): Target tenant
- `started_at`, `ended_at`: Session window
- `ip_address`, `user_agent`: Audit metadata

**API**:
- `POST /api/v1/platform/impersonate` - Start session
- `POST /api/v1/platform/end-impersonation` - End session

**Migration**: `alembic/versions/9ed964cd8ba3_create_platform_impersonation_sessions.py`

**Session Lifecycle**:
1. Platform admin calls `/impersonate` with target user_id
2. Backend creates session record with `ended_at = NULL`
3. Backend returns impersonation token (JWT with special prefix)
4. Admin uses token for subsequent requests
5. Admin calls `/end-impersonation` to close session, sets `ended_at`

**Automatic Session Detection** (from `auth_service.py`):
```python
# Check for active impersonation session in get_current_user()
is_platform_admin = check_platform_admin(user_id)
if is_platform_admin:
    active_session = fetch_active_impersonation_session(user_id)
    if active_session:
        target_user = fetch_user(active_session.impersonated_user_id)
        return {
            "user": target_user,  # Effective user
            "actor_user": admin_user,  # Original admin
            "actor_user_id": admin_user_id,
            "impersonation_session_id": session_id,
            "is_impersonating": True
        }
```

**Risk**: Session timeout not enforced (manual end only). Long-running sessions possible.

### Impersonation Token Prefix

**File**: `services/auth_service.py`

**Prefix**: `IMPERSONATION_TOKEN_PREFIX = "imp_"`

**Token Format**: `imp_{base64_payload}`

**Payload**:
```json
{
  "target_id": "user-id-to-impersonate",
  "admin_id": "platform-admin-user-id",
  "session_id": "session-id",
  "exp": timestamp
}
```

**Verification** (`auth_service.py:verify_impersonation_token()`):
1. Check prefix
2. Decode payload
3. Verify signature (HMAC)
4. Check expiration
5. Verify session still active in DB

**Risk**: Token prefix collision if Supabase JWT format changes to start with "imp_".

### Dual User Context

**Structure**:
```python
{
  "user": {...},  # Target user being impersonated
  "tenant": {...},  # Target user's tenant
  "actor_user": {...},  # Platform admin
  "actor_user_id": "...",
  "impersonation_session_id": "...",
  "is_impersonating": True
}
```

**Usage in Endpoints**:
```python
async def some_endpoint(user_info: dict = Depends(get_current_user)):
    tenant_id = user_info["tenant"]["id"]  # Always target tenant
    actor_id = user_info.get("actor_user_id") or user_info["user"]["id"]  # For audit
```

**Audit Pattern**: All write actions log both `actor_id` and `impersonated_user_id`.

---

## Audit Attribution

### Dual Attribution Logging

**Middleware**: `main.py:impersonation_write_audit_middleware()` (lines 22-82)

**Trigger**: All write operations (POST, PUT, PATCH, DELETE) during impersonation

**Log Entry**:
```python
await create_audit_log(
    action_type="impersonation.write",
    action=f"{request.method} {request.url.path}",
    actor_id=session.actor_user_id,  # Platform admin
    tenant_id=session.impersonated_tenant_id,  # Target tenant
    resource_type="http_request",
    resource_id=session_id,
    metadata={
        "impersonated_user_id": session.impersonated_user_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code
    },
    ip_address=request.client.host,
    user_agent=request.headers.get("user-agent")
)
```

**Table**: `audit_logs`

**Columns**:
- `actor_id`: Platform admin who performed action
- `impersonated_user_id`: Target user (if impersonation)
- `impersonation_session_id`: Session ID
- `tenant_id`: Target tenant
- `action_type`, `action`: What was done
- `resource_type`, `resource_id`: What was affected
- `metadata` (JSONB): Additional context
- `ip_address`, `user_agent`: Origin
- `created_at`: Timestamp

**Migration**: `alembic/versions/add_audit_log_impersonation_index.py` (adds indexes)

**Test**: `tests/security/test_impersonation_audit.py`

**Coverage**: Middleware only logs write actions. Read actions during impersonation not logged.

---

## High-Risk Endpoints & Protections

### Cross-Tenant Endpoints (Exempt from Isolation)

| Endpoint Pattern | Purpose | Protection |
|-----------------|---------|------------|
| `/platform/admins` | Platform admin management | `require_platform_admin()` guard |
| `/platform/impersonate` | Start impersonation | `require_platform_admin()` + cannot impersonate other admins |
| `/platform/console` | Support console | `require_platform_admin()` |
| `/admin/entitlements` | Entitlement management | `require_platform_admin()` |
| `/admin/audit-logs` | Audit log queries | `require_platform_admin()` |

### High-Risk Mutation Endpoints

| Endpoint | Risk | Protection |
|----------|------|------------|
| `POST /environments` | Create environment | tenant_id from user context + entitlement limit check |
| `DELETE /environments/{id}` | Delete environment | tenant_id filter + RBAC (admin only) |
| `POST /workflows/{id}/activate` | Activate workflow | tenant_id + environment class policy guard |
| `POST /promotions/{id}/execute` | Execute promotion | tenant_id + drift policy check + gates |
| `POST /billing/stripe-webhook` | Process payment | Stripe signature verification + tenant lookup by customer_id |

### Protection Layers

1. **Authentication**: JWT validation via Supabase
2. **Tenant Isolation**: tenant_id from user context
3. **RBAC**: Role check (admin/developer/viewer)
4. **Entitlements**: Feature gate + limit check
5. **Environment Policy**: Action guard (dev/staging/prod)
6. **Audit**: All actions logged

---

## Tests

| Test File | Coverage |
|-----------|----------|
| `tests/security/test_tenant_isolation.py` | Cross-tenant leak scenarios, endpoint scanning |
| `tests/security/test_impersonation_audit.py` | Impersonation audit trail, dual attribution |

**Gaps**: 
- No test for admin-to-admin impersonation block
- Session timeout enforcement not tested
- RLS policies not tested (Supabase-level)

---

## Risk Areas

### High Risk

1. **RLS Policies Not in Repo**: Configuration lives in Supabase dashboard. No version control or CI/CD validation.

2. **Scanner Regex Limitations**: May miss dynamic or obfuscated tenant_id extraction patterns.

3. **Session Timeout**: No automatic timeout. Long-running impersonation sessions possible.

4. **Admin-to-Admin Block**: Policy stated but test enforcement unknown.

### Medium Risk

1. **Token Prefix Collision**: If Supabase changes JWT format, prefix collision possible.

2. **Read Action Audit Gap**: Only write actions logged during impersonation. Read actions not logged.

3. **RBAC Server-Side Gaps**: Many endpoints rely on frontend RBAC. Server-side enforcement inconsistent.

### Low Risk

1. **Audit Log Performance**: Large audit payloads (e.g., full workflow JSON) may impact query performance.

2. **Impersonation Context Parsing**: Nested dict access (`user_info["tenant"]["id"]`) error-prone.

---

## Gaps & Missing Features

### Not Implemented

1. **Session Timeout**: No automatic timeout enforcement.

2. **Read Action Audit**: Read operations during impersonation not logged.

3. **Admin-to-Admin Block**: Test enforcement unknown.

4. **RLS Policy Version Control**: Policies not in repo.

5. **IP Whitelist**: No IP-based access control.

### Unclear Behavior

1. **Concurrent Impersonation**: Can one admin have multiple active sessions?

2. **Session Hijacking**: Token revocation mechanism unclear.

3. **Cross-Tenant Query Optimization**: Platform admin queries across all tenants - performance untested.

---

## Recommendations

### Must Fix Before MVP Launch

1. ✅ Export RLS policies to SQL files in repo (COMPLETED 2026-01-08)
2. Test admin-to-admin impersonation block
3. Implement session timeout (e.g., 8 hours)
4. Add server-side RBAC enforcement to all mutation endpoints

### Should Fix Post-MVP

1. Log read actions during impersonation
2. Add session hijacking protection (token revocation)
3. Improve scanner to detect dynamic patterns
4. Add IP-based access control for platform admin

### Nice to Have

1. Multi-factor authentication for impersonation
2. Approval workflow for impersonation requests
3. Impersonation session recording/playback
4. Real-time impersonation session dashboard

