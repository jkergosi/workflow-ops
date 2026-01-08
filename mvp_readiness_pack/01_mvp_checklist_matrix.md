# 01 - MVP Checklist Matrix

## Legend

- **Status**:
  - ✅ **Implemented**: Fully functional with code evidence
  - ⚠️ **Partial**: Core implemented but missing edge cases or features
  - ❌ **Missing**: Not implemented or only stubs exist
  
---

## MVP Area 1: Promotions & Deployments

| Sub-Requirement | Status | Evidence (file:function) | API Endpoints | DB Tables | Tests | Risks / Gaps |
|----------------|--------|-------------------------|---------------|-----------|-------|--------------|
| Pipeline definition & gates | ✅ | `services/promotion_service.py:PromotionService`<br>`schemas/promotion.py:GateType` | `POST /pipelines`<br>`GET /pipelines` | `pipelines` | `test_promotion_service.py`<br>`test_pipelines_api.py` | Gate validation logic may need stress testing |
| Pre-flight validation | ✅ | `services/promotion_validation_service.py:validate_promotion` | `POST /promotions/validate` | None (transient) | `test_promotion_validation.py` | Credential availability check relies on sync accuracy |
| Diff computation | ✅ | `services/diff_service.py:DiffService`<br>`schemas/promotion.py:DiffStatus` | `POST /promotions/compare` | None (computed) | `test_diff_service.py` | TARGET_HOTFIX detection assumes updatedAt accuracy |
| Promotion execution | ✅ | `services/promotion_service.py:execute_promotion` | `POST /promotions/{id}/execute` | `promotions`<br>`deployment_workflows` | `test_promotion_atomicity.py` | Rollback completeness on partial failure |
| Snapshot creation | ✅ | `services/promotion_service.py` (auto-creates) | `POST /snapshots` | `snapshots` | `test_snapshot_before_promotion.py`<br>`test_promotion_failure_snapshot_intact.py` | Pre-promotion snapshot timing (before vs during) |
| Rollback on failure | ✅ | `services/promotion_service.py:_rollback_promotion` | Auto-triggered | `snapshots` | `test_rollback_workflow_state.py`<br>`test_t016_rollback_404_graceful_failure.py` | 404 errors during rollback need graceful handling |
| Deployment scheduling | ✅ | `services/deployment_scheduler.py:start_scheduler` | `POST /deployments`<br>`GET /deployments` | `deployments` | `test_deployments_api.py` | Scheduler reliability on restart |
| Stale deployment cleanup | ✅ | `main.py:startup_event` (lines 448-481) | None (startup job) | `deployments` | `test_stale_deployment.py` | 1hr threshold may be too short for large promotions |
| Real-time progress (SSE) | ✅ | `api/endpoints/sse.py:stream_deployment` | `GET /sse/deployments/{id}` | `background_jobs` | Unknown | SSE reconnection logic untested |
| Risk level calculation | ✅ | `services/promotion_service.py:calculate_risk_level` | Embedded in compare | None | Unknown | Risk levels are heuristic, may miss edge cases |
| Conflict resolution flags | ✅ | `schemas/promotion.py:StagePolicy`<br>`allowOverwritingHotfixes` | Embedded in pipeline config | `pipelines` | Unknown | Flag enforcement untested in edge cases |
| Drift policy blocking | ✅ | `api/endpoints/promotions.py:check_drift_policy_blocking` | `GET /promotions/drift-check/{env_id}` | `drift_incidents`<br>`drift_policies` | Unknown | Blocking logic relies on incident TTL accuracy |

**Summary**:
- **Strong**: Core promotion flow, snapshot creation, diff computation
- **Weak**: Rollback edge cases, SSE reliability, conflict flag testing
- **Missing**: User-facing credential remapping at promotion time

---

## MVP Area 2: Drift Detection & Incident Lifecycle

| Sub-Requirement | Status | Evidence (file:function) | API Endpoints | DB Tables | Tests | Risks / Gaps |
|----------------|--------|-------------------------|---------------|-----------|-------|--------------|
| Scheduled drift detection | ✅ | `services/drift_scheduler.py:start_all_drift_schedulers` | None (background) | `drift_check_history` | `test_drift_detection_service.py` | Scheduler may miss checks on high load |
| On-demand drift check | ✅ | `services/drift_detection_service.py:check_drift` | `POST /incidents/check-drift` | `drift_incidents` | `test_drift_detection_service.py` | Performance on large workflow sets |
| Incident lifecycle | ✅ | `services/drift_incident_service.py`<br>`schemas/drift_incident.py:DriftIncidentStatus` | `POST /incidents/{id}/acknowledge`<br>`POST /incidents/{id}/close` | `drift_incidents` | `test_drift_incident_service.py` | State transition validation incomplete |
| TTL/SLA enforcement | ✅ | `services/drift_incident_service.py:check_ttl_expiration` | `GET /incidents?expired=true` | `drift_policies` | Unknown | TTL calculation assumes UTC consistency |
| Drift snapshot payload | ✅ | `drift_incidents.drift_snapshot` (JSONB) | Embedded in incident | `drift_incidents` | Unknown | Payload size limits untested (JSONB max) |
| Payload purging | ✅ | `services/drift_retention_service.py` | None (background) | `drift_incidents.payload_purged_at` | `test_drift_retention_service.py` | Purging timing vs retention policy sync |
| Severity levels | ✅ | `schemas/drift_incident.py:DriftSeverity` | Embedded | `drift_incidents` | Unknown | Severity assignment is manual (no auto-classification) |
| Reconciliation flow | ✅ | `services/drift_incident_service.py:reconcile` | `POST /incidents/{id}/reconcile` | `reconciliation_artifacts` | Unknown | Reconciliation artifact cleanup untested |
| Drift approvals | ✅ | `api/endpoints/drift_approvals.py` | `POST /drift-approvals` | `drift_approvals` | Unknown | Approval workflow atomicity |
| Drift handling modes | ✅ | `environments.drift_handling_mode`<br>`warn_only`, `manual_override`, `require_attestation` | Embedded in environment | `environments` | Unknown | Mode enforcement during promotion untested |
| DEV environment skip | ✅ | `services/drift_detection_service.py` (env_class check) | N/A | N/A | Unknown | Hardcoded `env_class == "dev"` check |

**Summary**:
- **Strong**: Incident lifecycle, scheduled detection, payload storage
- **Weak**: State transition validation, TTL edge cases, reconciliation cleanup
- **Missing**: Auto-severity classification, comprehensive approval testing

---

## MVP Area 3: Canonical Workflow System

| Sub-Requirement | Status | Evidence (file:function) | API Endpoints | DB Tables | Tests | Risks / Gaps |
|----------------|--------|-------------------------|---------------|-----------|-------|--------------|
| Canonical workflow tracking | ✅ | `services/canonical_workflow_service.py` | `GET /canonical/workflows` | `canonical_workflows` | `test_canonical_onboarding_integrity.py` | Canonical ID generation collision risk |
| workflow_env_map management | ✅ | `services/canonical_env_sync_service.py`<br>`schemas/canonical_workflow.py:WorkflowMappingStatus` | N/A (auto-managed) | `workflow_env_map` | `test_canonical_onboarding_integrity.py` | Status precedence rules complex (5 states) |
| Content hash tracking | ✅ | `workflow_env_map.env_content_hash`<br>`workflow_env_map.git_content_hash` | N/A | `workflow_env_map` | Unknown | Hash algorithm not documented (likely MD5/SHA) |
| Untracked detection | ✅ | `services/untracked_workflows_service.py:get_untracked` | `GET /canonical/untracked` | `workflow_env_map` (WHERE canonical_id IS NULL) | `test_untracked_workflows_service.py` | Detection relies on sync accuracy |
| Bulk onboarding | ✅ | `services/canonical_onboarding_service.py:run_inventory_phase` | `POST /canonical/onboard/inventory` | `canonical_workflows`<br>`workflow_env_map` | `test_canonical_onboarding_integrity.py` | Transaction boundaries unclear (idempotency?) |
| Matrix view generation | ✅ | `api/endpoints/workflow_matrix.py:get_matrix` | `GET /workflows/matrix` | `workflow_env_map` (JOIN canonical_workflows) | Unknown | Performance with 1000+ workflows untested |
| Git sync | ✅ | `services/canonical_repo_sync_service.py` | `POST /canonical/sync-repo` | `workflow_git_state` | Unknown | Git conflicts not handled (fails on conflict) |
| Environment sync | ✅ | `services/canonical_env_sync_service.py:sync_environment` | `POST /environments/{id}/sync` | `workflow_env_map` | Unknown | Batch size (25-30) not configurable |
| Reconciliation | ✅ | `services/canonical_reconciliation_service.py` | `POST /canonical/reconcile` | `workflow_env_map` | Unknown | Reconciliation strategy unclear (force overwrite?) |
| Preflight checks | ✅ | `services/canonical_onboarding_service.py:check_preflight` | `GET /canonical/onboard/preflight` | None (read-only) | Unknown | Check completeness (missing Git validation?) |
| Scheduled sync | ✅ | `services/canonical_sync_scheduler.py:start_canonical_sync_schedulers` | None (background) | N/A | Unknown | Scheduler impact on DB load |

**Summary**:
- **Strong**: Core mapping logic, untracked detection, onboarding flow
- **Weak**: Content hash algorithm docs, matrix performance, Git conflict handling
- **Missing**: Configurable batch sizes, comprehensive reconciliation strategy docs

---

## MVP Area 4: Multi-Tenancy, Security & Impersonation

| Sub-Requirement | Status | Evidence (file:function) | API Endpoints | DB Tables | Tests | Risks / Gaps |
|----------------|--------|-------------------------|---------------|-----------|-------|--------------|
| tenant_id enforcement | ✅ | `core/tenant_isolation.py:TenantIsolationScanner`<br>`services/auth_service.py:get_current_user` | All endpoints | All tables | `tests/security/test_tenant_isolation.py` | Scanner relies on regex (may miss obfuscated patterns) |
| RLS (Row-Level Security) | ⚠️ | Supabase RLS (external) | N/A | 12 of 76 tables | [`docs/security/RLS_VERIFICATION.md`](../n8n-ops-backend/docs/security/RLS_VERIFICATION.md) | RLS now documented; 64 tables still need policies |
| Platform admin designation | ✅ | `core/platform_admin.py:require_platform_admin` | `POST /platform/admins` | `platform_admins` | Unknown | No admin-to-admin impersonation block enforcement test |
| Impersonation sessions | ✅ | `api/endpoints/platform_impersonation.py:start_impersonation` | `POST /platform/impersonate`<br>`POST /platform/end-impersonation` | `platform_impersonation_sessions` | `tests/security/test_impersonation_audit.py` | Session timeout not enforced (manual end only) |
| Impersonation token prefix | ✅ | `services/auth_service.py:IMPERSONATION_TOKEN_PREFIX`<br>`auth_service.py:verify_impersonation_token` | N/A (JWT variant) | N/A | `tests/security/test_impersonation_audit.py` | Token prefix collision risk if Supabase changes format |
| Dual user context | ✅ | `auth_service.py:get_current_user` (actor_user + user) | All endpoints (via middleware) | N/A | `tests/security/test_impersonation_audit.py` | Context parsing complex (nested dict access) |
| Audit trail (dual attribution) | ✅ | `services/audit_middleware.py:AuditMiddleware`<br>`main.py:impersonation_write_audit_middleware` | N/A (middleware) | `audit_logs` (actor_id, impersonated_user_id) | `tests/security/test_impersonation_audit.py` | Middleware only logs write actions (POST/PUT/PATCH/DELETE) |
| Audit log retention | ✅ | `services/background_jobs/retention_job.py` | N/A (background) | `audit_logs` | `tests/test_retention.py` | Retention enforcement timing (daily 2AM UTC) |
| RBAC (Role-Based Access) | ✅ | `lib/permissions.ts:canAccessRoute`<br>`services/auth_service.py:is_user_admin` | Frontend-enforced | `users.role` | Unknown | Server-side RBAC enforcement inconsistent (mostly frontend) |
| API key encryption | ✅ | `services/api_key_service.py:create_api_key` | `POST /security/api-keys` | `tenant_api_keys` | `test_security_api_keys_api.py` | Encryption algorithm not documented |
| Cross-tenant leak testing | ✅ | `tests/security/test_tenant_isolation.py` | N/A | N/A | `tests/security/test_tenant_isolation.py` | Tests cover common patterns (may miss new endpoints) |

**Summary**:
- **Strong**: Tenant isolation scanner, impersonation audit, dual attribution logging
- **Weak**: RLS documentation missing, RBAC server-side gaps, session timeout
- **Missing**: Comprehensive RLS policy documentation, admin-to-admin block test

---

## MVP Area 5: Billing, Entitlements & Downgrade Enforcement

| Sub-Requirement | Status | Evidence (file:function) | API Endpoints | DB Tables | Tests | Risks / Gaps |
|----------------|--------|-------------------------|---------------|-----------|-------|--------------|
| Provider-based plans | ✅ | `schemas/provider.py:ProviderPlan` | `GET /providers/{id}/plans` | `provider_plans` | `test_billing_api.py` | Only n8n provider plans exist (Make.com missing) |
| Stripe checkout | ✅ | `api/endpoints/billing.py:create_checkout_session` | `POST /billing/checkout` | `tenant_provider_subscriptions` | `test_billing_api.py` | Checkout flow untested end-to-end |
| Stripe webhooks | ✅ | `api/endpoints/billing.py:stripe_webhook` | `POST /billing/stripe-webhook` | `tenant_provider_subscriptions` | `test_billing_webhooks.py` | Webhook idempotency relies on Stripe event ID |
| Downgrade detection | ✅ | `billing.py:handle_subscription_updated` (lines 911-1038) | N/A (webhook handler) | N/A | `test_billing_webhooks.py` | Plan precedence hardcoded (free < pro < agency < enterprise) |
| Downgrade handling | ✅ | `services/downgrade_service.py:handle_plan_downgrade` | N/A (webhook-triggered) | `downgrade_grace_periods` | Unknown | Downgrade errors don't fail webhook (logged only) |
| Over-limit detection | ✅ | `downgrade_service.py:detect_environment_overlimit` | `GET /admin/usage/over-limits` | `environments`, `users` | Unknown | Detection runs on webhook only (not periodic) |
| Grace period tracking | ✅ | `downgrade_service.py:create_grace_period` | N/A | `downgrade_grace_periods` | Unknown | Grace period expiry enforcement not automated |
| Resource selection strategy | ✅ | `core/downgrade_policy.py:ResourceSelectionStrategy`<br>`OLDEST_FIRST`, `NEWEST_FIRST`, `USER_CHOICE` | N/A | N/A | Unknown | USER_CHOICE not implemented (always auto-selects) |
| Entitlement resolution | ✅ | `services/entitlements_service.py:get_tenant_entitlements` | `GET /providers/{id}/entitlements` | `tenant_plans`, `plan_features`, `tenant_feature_overrides` | `test_entitlements.py` | Override precedence complex (3-tier hierarchy) |
| Flag enforcement | ✅ | `core/entitlements_gate.py:require_entitlement` | All gated endpoints | N/A | `test_feature_gate.py` | Decorator pattern easy to bypass if forgotten |
| Limit enforcement | ✅ | `entitlements_service.py:enforce_limit` | Various endpoints | N/A | `test_entitlements.py` | Limit checks rely on accurate counts (sync dependency) |
| Admin overrides | ✅ | `api/endpoints/admin_entitlements.py:create_override` | `POST /admin/entitlements/overrides` | `tenant_feature_overrides` | Unknown | Override expiration not enforced (manual only) |
| Retention enforcement | ✅ | `services/background_jobs/retention_job.py:trigger_retention_enforcement` | N/A (daily 2AM) | `executions`, `audit_logs` | `tests/test_retention.py` | Dry-run mode not exposed via API |

**Summary**:
- **Strong**: Stripe integration, entitlement resolution, downgrade detection
- **Weak**: Downgrade grace period expiry, USER_CHOICE strategy, checkout E2E testing
- **Missing**: Periodic over-limit detection, automated grace period enforcement

---

## MVP Area 6: Executions, Analytics & Observability

| Sub-Requirement | Status | Evidence (file:function) | API Endpoints | DB Tables | Tests | Risks / Gaps |
|----------------|--------|-------------------------|---------------|-----------|-------|--------------|
| Execution sync | ✅ | `services/n8n_client.py:get_executions`<br>`api/endpoints/environments.py:sync_environment` | `POST /environments/{id}/sync` | `executions` | `test_executions_api.py` | Sync performance with 10k+ executions untested |
| Execution retention | ✅ | `services/background_jobs/retention_job.py` | N/A (daily job) | `executions` | `tests/test_retention.py` | Minimum 100 record threshold may be too low |
| KPI calculation | ✅ | `services/observability_service.py:get_kpi_metrics` | `GET /observability/kpis` | `executions` | `test_observability_service.py` | Success rate calculation excludes "running" status |
| Sparkline generation | ✅ | `observability_service.py:_get_sparkline_data` | Embedded in KPI response | `executions` | Unknown | Single-query optimization assumes reasonable time ranges |
| Error intelligence | ✅ | `observability_service.py:get_error_intelligence` | `GET /observability/errors` | `executions.error_message` | Unknown | Error grouping is naive (exact string match) |
| Environment health checks | ✅ | `services/health_check_scheduler.py:start_health_check_scheduler` | `GET /observability/environments` | `environments.last_heartbeat_at` | Unknown | Heartbeat timeout hardcoded (5 min?) |
| System status insights | ✅ | `observability_service.py:get_system_status` | `GET /observability/status` | Various | Unknown | Insight generation heuristics undocumented |
| Workflow performance | ✅ | `observability_service.py:get_workflow_performance` | `GET /observability/workflows` | `executions` | Unknown | Performance metrics exclude credential/API latency |
| Materialized views | ✅ | `services/rollup_scheduler.py:_refresh_materialized_views` | N/A (periodic) | Postgres MV | Unknown | Refresh schedule not configurable |
| Rollup computations | ✅ | `rollup_scheduler.py:_check_and_compute_rollups` | N/A (periodic) | `execution_analytics` | Unknown | Rollup interval hardcoded |
| SSE count updates | ✅ | `api/endpoints/sse.py:emit_counts_update` | `GET /sse/counts/{tenant_id}` | N/A | Unknown | SSE reconnection after server restart |
| Execution analytics | ✅ | `services/database.py:get_execution_analytics` | `GET /analytics/executions` | `executions` | Unknown | Analytics aggregation in Python (not DB) - performance risk |
| Time range filtering | ✅ | `observability_service.py:get_time_range_bounds` | All observability endpoints | N/A | Unknown | Fixed time ranges (no custom dates) |

**Summary**:
- **Strong**: KPI calculations, sparkline optimization, retention enforcement
- **Weak**: Error intelligence (naive grouping), health check timeouts, rollup configurability
- **Missing**: Custom time ranges, advanced error classification, credential/API latency metrics

---

## Overall MVP Readiness Summary

### Fully Implemented (✅)
1. **Promotions & Deployments**: Core flow, snapshots, rollback, scheduling
2. **Drift Detection**: Scheduled checks, incident lifecycle, TTL/SLA
3. **Canonical Workflows**: Tracking, mapping, untracked detection, onboarding
4. **Multi-Tenancy & Security**: Tenant isolation, impersonation, audit logging
5. **Billing & Entitlements**: Stripe integration, downgrade detection, entitlement gates
6. **Observability**: KPIs, sparklines, error intelligence, health checks

### Partial Implementation (⚠️)
1. **RLS Policies**: Supabase RLS exists but not documented in repo
2. **RBAC Server-Side**: Primarily frontend-enforced, backend checks inconsistent
3. **Error Intelligence**: Naive string matching (no ML/classification)
4. **Reconciliation Strategy**: Works but strategy unclear (force overwrite?)

### Missing / Not Implemented (❌)
1. **Make.com Provider**: Enum exists, adapter NOT implemented
2. **SSO/SCIM**: Feature flags exist, no integration
3. **Credential Remapping UI**: Admin matrix exists, no promotion-time UI
4. **Scheduled Backups**: Feature flag exists, no scheduler
5. **Grace Period Expiry**: Tracking exists, no automated enforcement
6. **USER_CHOICE Downgrade**: Selection strategy exists, not implemented
7. **Admin-to-Admin Impersonation Block**: Policy stated, no test enforcement

---

## Critical Risks

1. **Rollback Completeness**: 404 errors during rollback need better handling
2. **TTL/SLA Enforcement**: Relies on accurate UTC timestamps and scheduler reliability
3. **Content Hash Collisions**: Canonical ID generation needs collision testing
4. **Matrix Performance**: Untested with 1000+ workflows
5. **Execution Sync Scale**: Performance with 10k+ executions unknown
6. **Downgrade Grace Period**: No automated enforcement of expiry
7. **SSE Reconnection**: Client reconnection logic after server restart untested
8. **Test Coverage Gaps**: Many features lack integration/E2E tests

---

## Test Coverage Summary

| Area | Unit Tests | Integration Tests | E2E Tests | Coverage |
|------|-----------|-------------------|-----------|----------|
| Promotions | ✅ Strong | ✅ Strong | ⚠️ Partial | ~80% |
| Drift | ✅ Good | ⚠️ Partial | ❌ None | ~60% |
| Canonical | ✅ Good | ⚠️ Partial | ❌ None | ~60% |
| Security | ✅ Strong | ✅ Strong | ❌ None | ~70% |
| Billing | ✅ Good | ⚠️ Partial | ❌ None | ~50% |
| Observability | ✅ Partial | ❌ None | ❌ None | ~40% |

**Overall Test Coverage Estimate**: ~60%

---

## Recommendations for MVP Launch

### Must Fix Before Launch
1. Document RLS policies in repo
2. Add admin-to-admin impersonation block enforcement
3. Implement SSE reconnection logic
4. Test rollback 404 handling
5. Document content hash algorithm

### Should Fix Soon After Launch
1. Add E2E tests for critical flows
2. Implement grace period expiry automation
3. Add custom time range support
4. Improve error intelligence (classification)
5. Add matrix performance optimization

### Nice to Have (Post-MVP)
1. Make.com provider adapter
2. SSO/SCIM integration
3. Credential remapping UI
4. Scheduled backups
5. USER_CHOICE downgrade strategy

