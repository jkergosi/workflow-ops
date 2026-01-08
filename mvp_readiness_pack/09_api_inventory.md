# 09 - API Endpoint Inventory

## Summary Statistics

- **Total Endpoints**: ~327
- **Endpoint Modules**: 51 files in `n8n-ops-backend/app/api/endpoints/`
- **API Prefix**: `/api/v1`

---

## Endpoint Categories

### Authentication & Authorization (13 endpoints)

| Method | Path | Auth | Tenant Scope | Entitlements | Audit Logged | Handler |
|--------|------|------|--------------|--------------|--------------|---------|
| POST | `/auth/register` | None | N/A | None | Yes | `auth.py:register` |
| POST | `/auth/login` | None | N/A | None | Yes | `auth.py:login` |
| POST | `/auth/logout` | JWT | User tenant | None | Yes | `auth.py:logout` |
| GET | `/auth/me` | JWT | User tenant | None | No | `auth.py:get_current_user_info` |
| POST | `/auth/refresh` | JWT | User tenant | None | No | `auth.py:refresh_token` |
| POST | `/auth/forgot-password` | None | N/A | None | Yes | `auth.py:forgot_password` |
| POST | `/auth/reset-password` | Token | N/A | None | Yes | `auth.py:reset_password` |
| POST | `/auth/verify-email` | Token | N/A | None | Yes | `auth.py:verify_email` |
| POST | `/auth/resend-verification` | JWT | User tenant | None | No | `auth.py:resend_verification` |
| POST | `/auth/change-password` | JWT | User tenant | None | Yes | `auth.py:change_password` |
| GET | `/auth/sessions` | JWT | User tenant | None | No | `auth.py:list_sessions` |
| DELETE | `/auth/sessions/{id}` | JWT | User tenant | None | Yes | `auth.py:revoke_session` |
| POST | `/onboard` | JWT | User tenant | None | Yes | `tenants.py:onboard_tenant` |

### Environments (17 endpoints)

| Method | Path | Auth | Tenant Scope | Entitlements | Audit Logged | Handler |
|--------|------|------|--------------|--------------|--------------|---------|
| GET | `/environments` | JWT | User tenant | None | No | `environments.py:list_environments` |
| POST | `/environments` | JWT | User tenant | `environment_limits` | Yes | `environments.py:create_environment` |
| GET | `/environments/{id}` | JWT | User tenant | None | No | `environments.py:get_environment` |
| PUT | `/environments/{id}` | JWT | User tenant | None | Yes | `environments.py:update_environment` |
| DELETE | `/environments/{id}` | JWT | User tenant | None | Yes | `environments.py:delete_environment` |
| POST | `/environments/{id}/test-connection` | JWT | User tenant | None | No | `environments.py:test_connection` |
| POST | `/environments/{id}/sync` | JWT | User tenant | None | Yes | `environments.py:sync_environment` |
| POST | `/environments/{id}/sync-workflows` | JWT | User tenant | None | Yes | `environments.py:sync_workflows` |
| POST | `/environments/{id}/sync-credentials` | JWT | User tenant | None | Yes | `environments.py:sync_credentials` |
| POST | `/environments/{id}/sync-executions` | JWT | User tenant | None | Yes | `environments.py:sync_executions` |
| GET | `/environments/{id}/sync-status` | JWT | User tenant | None | No | `environments.py:get_sync_status` |
| POST | `/environments/{id}/github-test` | JWT | User tenant | None | No | `environments.py:test_github` |
| POST | `/environments/{id}/backup` | JWT | User tenant | `snapshots_enabled` | Yes | `environments.py:backup_environment` |
| GET | `/environments/{id}/capabilities` | JWT | User tenant | None | No | `environment_capabilities.py:get_capabilities` |
| GET | `/environments/{id}/health` | JWT | User tenant | None | No | `environments.py:check_health` |
| POST | `/environments/{id}/restore` | JWT | User tenant | `snapshots_enabled` | Yes | `restore.py:restore_environment` |
| GET | `/environments/{id}/drift` | JWT | User tenant | `drift_detection_enabled` | No | `environments.py:check_drift` |

### Workflows (17 endpoints)

| Method | Path | Auth | Tenant Scope | Entitlements | Audit Logged | Handler |
|--------|------|------|--------------|--------------|--------------|---------|
| GET | `/workflows` | JWT | User tenant | None | No | `workflows.py:list_workflows` |
| POST | `/workflows` | JWT | User tenant | None | Yes | `workflows.py:create_workflow` |
| GET | `/workflows/{id}` | JWT | User tenant | None | No | `workflows.py:get_workflow` |
| PUT | `/workflows/{id}` | JWT | User tenant | None | Yes | `workflows.py:update_workflow` |
| DELETE | `/workflows/{id}` | JWT | User tenant | None | Yes | `workflows.py:delete_workflow` |
| POST | `/workflows/{id}/activate` | JWT | User tenant | Policy guard | Yes | `workflows.py:activate_workflow` |
| POST | `/workflows/{id}/deactivate` | JWT | User tenant | Policy guard | Yes | `workflows.py:deactivate_workflow` |
| POST | `/workflows/upload` | JWT | User tenant | None | Yes | `workflows.py:upload_workflows` |
| POST | `/workflows/{id}/backup` | JWT | User tenant | `snapshots_enabled` | Yes | `workflows.py:backup_workflow` |
| POST | `/workflows/{id}/restore` | JWT | User tenant | `snapshots_enabled` | Yes | `restore.py:restore_workflow` |
| GET | `/workflows/{id}/history` | JWT | User tenant | None | No | `workflows.py:get_workflow_history` |
| GET | `/workflows/{id}/analysis` | JWT | User tenant | None | No | `workflows.py:analyze_workflow` |
| POST | `/workflows/{id}/archive` | JWT | User tenant | None | Yes | `workflows.py:archive_workflow` |
| POST | `/workflows/{id}/unarchive` | JWT | User tenant | None | Yes | `workflows.py:unarchive_workflow` |
| GET | `/workflows/{id}/dependencies` | JWT | User tenant | None | No | `workflows.py:get_dependencies` |
| GET | `/workflows/matrix` | JWT | User tenant | `canonical_workflows_enabled` | No | `workflow_matrix.py:get_matrix` |
| POST | `/workflows/{id}/policy-check` | JWT | User tenant | None | No | `workflow_policy.py:check_policy` |

### Canonical Workflows (13 endpoints)

| Method | Path | Auth | Tenant Scope | Entitlements | Audit Logged | Handler |
|--------|------|------|--------------|--------------|--------------|---------|
| GET | `/canonical/workflows` | JWT | User tenant | `canonical_workflows_enabled` | No | `canonical_workflows.py:list_canonical` |
| GET | `/canonical/workflows/{id}` | JWT | User tenant | `canonical_workflows_enabled` | No | `canonical_workflows.py:get_canonical` |
| POST | `/canonical/sync-repo` | JWT | User tenant | `canonical_workflows_enabled` | Yes | `canonical_workflows.py:sync_repo` |
| POST | `/canonical/sync-environment/{id}` | JWT | User tenant | `canonical_workflows_enabled` | Yes | `canonical_workflows.py:sync_environment` |
| POST | `/canonical/reconcile` | JWT | User tenant | `canonical_workflows_enabled` | Yes | `canonical_workflows.py:reconcile` |
| GET | `/canonical/untracked` | JWT | User tenant | `canonical_workflows_enabled` | No | `untracked_workflows.py:list_untracked` |
| POST | `/canonical/link` | JWT | User tenant | `canonical_workflows_enabled` | Yes | `untracked_workflows.py:link_workflow` |
| GET | `/canonical/onboard/preflight` | JWT | User tenant | `canonical_workflows_enabled` | No | `canonical_workflows.py:preflight_check` |
| POST | `/canonical/onboard/inventory` | JWT | User tenant | `canonical_workflows_enabled` | Yes | `canonical_workflows.py:start_inventory` |
| GET | `/canonical/onboard/completion` | JWT | User tenant | `canonical_workflows_enabled` | No | `canonical_workflows.py:check_completion` |
| POST | `/canonical/onboard/create-pr` | JWT | User tenant | `canonical_workflows_enabled` | Yes | `canonical_workflows.py:create_migration_pr` |
| GET | `/canonical/matrix` | JWT | User tenant | `canonical_workflows_enabled` | No | `workflow_matrix.py:get_canonical_matrix` |
| POST | `/canonical/bulk-link` | JWT | User tenant | `canonical_workflows_enabled` | Yes | `untracked_workflows.py:bulk_link` |

### Pipelines (7 endpoints)

| Method | Path | Auth | Tenant Scope | Entitlements | Audit Logged | Handler |
|--------|------|------|--------------|--------------|--------------|---------|
| GET | `/pipelines` | JWT | User tenant | `promotions_enabled` | No | `pipelines.py:list_pipelines` |
| POST | `/pipelines` | JWT | User tenant | `promotions_enabled` + Admin | Yes | `pipelines.py:create_pipeline` |
| GET | `/pipelines/{id}` | JWT | User tenant | `promotions_enabled` | No | `pipelines.py:get_pipeline` |
| PUT | `/pipelines/{id}` | JWT | User tenant | `promotions_enabled` + Admin | Yes | `pipelines.py:update_pipeline` |
| DELETE | `/pipelines/{id}` | JWT | User tenant | `promotions_enabled` + Admin | Yes | `pipelines.py:delete_pipeline` |
| POST | `/pipelines/{id}/activate` | JWT | User tenant | `promotions_enabled` | Yes | `pipelines.py:activate_pipeline` |
| POST | `/pipelines/{id}/deactivate` | JWT | User tenant | `promotions_enabled` | Yes | `pipelines.py:deactivate_pipeline` |

### Promotions (12 endpoints)

| Method | Path | Auth | Tenant Scope | Entitlements | Audit Logged | Handler |
|--------|------|------|--------------|--------------|--------------|---------|
| GET | `/promotions` | JWT | User tenant | `promotions_enabled` | No | `promotions.py:list_promotions` |
| POST | `/promotions` | JWT | User tenant | `promotions_enabled` | Yes | `promotions.py:create_promotion` |
| GET | `/promotions/{id}` | JWT | User tenant | `promotions_enabled` | No | `promotions.py:get_promotion` |
| POST | `/promotions/validate` | JWT | User tenant | `promotions_enabled` | No | `promotions.py:validate_promotion` |
| POST | `/promotions/compare` | JWT | User tenant | `promotions_enabled` | No | `promotions.py:compare_environments` |
| POST | `/promotions/{id}/execute` | JWT | User tenant | `promotions_enabled` + Admin + Gates | Yes | `promotions.py:execute_promotion` |
| POST | `/promotions/{id}/approve` | JWT | User tenant | `promotions_enabled` | Yes | `promotions.py:approve_promotion` |
| POST | `/promotions/{id}/reject` | JWT | User tenant | `promotions_enabled` | Yes | `promotions.py:reject_promotion` |
| POST | `/promotions/{id}/cancel` | JWT | User tenant | `promotions_enabled` | Yes | `promotions.py:cancel_promotion` |
| GET | `/promotions/{id}/diff` | JWT | User tenant | `promotions_enabled` | No | `promotions.py:get_promotion_diff` |
| GET | `/promotions/drift-check/{env_id}` | JWT | User tenant | `drift_detection_enabled` | No | `promotions.py:check_drift_policy_blocking` |
| POST | `/promotions/{id}/rollback` | JWT | User tenant | `promotions_enabled` | Yes | `promotions.py:rollback_promotion` |

### Deployments (5 endpoints)

| Method | Path | Auth | Tenant Scope | Entitlements | Audit Logged | Handler |
|--------|------|------|--------------|--------------|--------------|---------|
| GET | `/deployments` | JWT | User tenant | None | No | `deployments.py:list_deployments` |
| POST | `/deployments` | JWT | User tenant | `promotions_enabled` | Yes | `deployments.py:create_deployment` |
| GET | `/deployments/{id}` | JWT | User tenant | None | No | `deployments.py:get_deployment` |
| POST | `/deployments/{id}/cancel` | JWT | User tenant | None | Yes | `deployments.py:cancel_deployment` |
| DELETE | `/deployments/{id}` | JWT | User tenant | None | Yes | `deployments.py:delete_deployment` |

### Drift & Incidents (12 endpoints)

| Method | Path | Auth | Tenant Scope | Entitlements | Audit Logged | Handler |
|--------|------|------|--------------|--------------|--------------|---------|
| GET | `/incidents` | JWT | User tenant | `drift_detection_enabled` | No | `incidents.py:list_incidents` |
| GET | `/incidents/{id}` | JWT | User tenant | `drift_detection_enabled` | No | `incidents.py:get_incident` |
| POST | `/incidents/check-drift` | JWT | User tenant | `drift_detection_enabled` | Yes | `incidents.py:check_drift` |
| POST | `/incidents/{id}/acknowledge` | JWT | User tenant | `drift_detection_enabled` | Yes | `incidents.py:acknowledge_incident` |
| POST | `/incidents/{id}/stabilize` | JWT | User tenant | `drift_detection_enabled` | Yes | `incidents.py:stabilize_incident` |
| POST | `/incidents/{id}/reconcile` | JWT | User tenant | `drift_detection_enabled` | Yes | `incidents.py:reconcile_incident` |
| POST | `/incidents/{id}/close` | JWT | User tenant | `drift_detection_enabled` | Yes | `incidents.py:close_incident` |
| POST | `/incidents/{id}/extend-ttl` | JWT | User tenant | `drift_ttl_sla` | Yes | `incidents.py:extend_ttl` |
| PUT | `/incidents/{id}` | JWT | User tenant | `drift_detection_enabled` | Yes | `incidents.py:update_incident` |
| DELETE | `/incidents/{id}` | JWT | User tenant | `drift_detection_enabled` | Yes | `incidents.py:delete_incident` |
| GET | `/drift-policies` | JWT | User tenant | `drift_ttl_sla` | No | `drift_policies.py:get_policies` |
| POST | `/drift-policies` | JWT | User tenant | `drift_ttl_sla` | Yes | `drift_policies.py:create_or_update_policy` |

### Platform Admin (10 endpoints)

| Method | Path | Auth | Tenant Scope | Entitlements | Audit Logged | Handler |
|--------|------|------|--------------|--------------|--------------|---------|
| GET | `/platform/admins` | Platform Admin | Cross-tenant | None | No | `platform_admins.py:list_admins` |
| POST | `/platform/admins` | Platform Admin | Cross-tenant | None | Yes | `platform_admins.py:add_admin` |
| DELETE | `/platform/admins/{user_id}` | Platform Admin | Cross-tenant | None | Yes | `platform_admins.py:remove_admin` |
| POST | `/platform/impersonate` | Platform Admin | Cross-tenant | None | Yes | `platform_impersonation.py:start_impersonation` |
| POST | `/platform/end-impersonation` | Platform Admin | Cross-tenant | None | Yes | `platform_impersonation.py:end_impersonation` |
| GET | `/platform/impersonation/sessions` | Platform Admin | Cross-tenant | None | No | `platform_impersonation.py:list_sessions` |
| GET | `/platform/console/search` | Platform Admin | Cross-tenant | None | No | `platform_console.py:search_tenants` |
| GET | `/platform/console/tenants/{id}` | Platform Admin | Cross-tenant | None | No | `platform_console.py:get_tenant` |
| GET | `/platform/console/tenants/{id}/users` | Platform Admin | Cross-tenant | None | No | `platform_console.py:list_tenant_users` |
| GET | `/platform` | Platform Admin | Cross-tenant | None | No | `platform_overview.py:get_platform_overview` |

**Note**: Platform admin endpoints exempt from tenant isolation by design. Protected by `require_platform_admin()` guard.

---

## Endpoint Protection Patterns

### 1. Authentication
- All endpoints except `/auth/register`, `/auth/login`, `/health` require JWT
- JWT extracted via `Depends(get_current_user)` or `Depends(get_current_user_optional)`

### 2. Tenant Isolation
- tenant_id ALWAYS extracted from user context: `user_info["tenant"]["id"]`
- NEVER from path/query params

### 3. RBAC (Role-Based Access)
- Backend-enforced for sensitive tenant actions:
  - Promotions: `POST /promotions/{id}/execute` requires tenant admin + feature
  - Pipelines: create/update/delete requires tenant admin + feature
  - Billing: subscription/checkout/portal/cancel/reactivate/invoices/payment-history require tenant admin
  - Impersonation: admin-only (platform- or tenant-level guards)
- Pattern: dependency guard (`require_tenant_admin()` or `require_platform_admin()`) plus entitlement gate

### 4. Entitlement Gates
- Decorator: `Depends(require_entitlement("feature_name"))`
- Examples: `snapshots_enabled`, `promotions_enabled`, `drift_detection_enabled`

### 5. Environment Policy Guards
- Action guards based on environment_class: dev/staging/production
- Examples: Block direct edit in production, require approval for delete

### 6. Audit Logging
- Write actions (POST, PUT, PATCH, DELETE) logged automatically via middleware
- Manual logging for sensitive operations: `create_audit_log(...)`

---

## High-Risk Endpoints

### Mutation Endpoints (Require Extra Scrutiny)

1. **POST `/environments`** - Creates new environment, checks limit
2. **DELETE `/environments/{id}`** - Deletes environment and all workflows
3. **POST `/promotions/{id}/execute`** - Executes promotion, creates snapshots
4. **POST `/billing/stripe-webhook`** - Processes payments, downgrades
5. **POST `/platform/impersonate`** - Starts impersonation session
6. **DELETE `/workflows/{id}`** - Deletes workflow (hard delete)
7. **POST `/canonical/reconcile`** - Reconciles drift (may overwrite)

### Performance-Sensitive Endpoints

1. **GET `/workflows`** - Lists workflows (pagination required for 1000+)
2. **GET `/workflows/matrix`** - Matrix view (performance risk with 1000+ workflows)
3. **GET `/executions`** - Lists executions (pagination required for 10k+)
4. **GET `/observability/overview`** - Complex aggregations (2s target)
5. **POST `/environments/{id}/sync`** - Syncs workflows (may take minutes)

---

## Gaps & Recommendations

### Missing Endpoints

1. **Bulk Workflow Operations**: Only `/bulk/sync`, `/bulk/backup`, `/bulk/restore`. No bulk delete, activate, etc.
2. **Workflow Version History**: No endpoint to list workflow versions
3. **Execution Retry**: No endpoint to retry failed executions
4. **Audit Log Export**: No endpoint to export audit logs as CSV/JSON
5. **Health Check Per Service**: Only overall `/health`, no per-service health

### Recommendations

1. **Add API Rate Limiting**: No rate limiting observed in code
2. **Add Request ID Tracking**: No request ID header for tracing
3. **Add Bulk Operations**: Extend bulk endpoints for more actions
4. **Add Webhook Management**: No endpoints to manage webhooks
5. **Add API Documentation**: Generate OpenAPI spec from FastAPI

