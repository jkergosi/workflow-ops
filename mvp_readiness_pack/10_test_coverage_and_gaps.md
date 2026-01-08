# 10 - Test Coverage & Gaps

## How to Run Tests

### Backend Tests

**Location**: `n8n-ops-backend/tests/`

**Runner**: pytest

**Commands**:
```bash
# Run all tests
cd n8n-ops-backend
pytest

# Run specific test file
pytest tests/test_promotion_service.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test function
pytest tests/test_promotion_service.py::test_promotion_idempotency
```

**Configuration**: `n8n-ops-backend/pytest.ini`

**Dependencies**: `n8n-ops-backend/requirements-test.txt`

### Frontend Tests

**Location**: `n8n-ops-ui/tests/`

**Runner**: Playwright (E2E)

**Commands**:
```bash
# Run E2E tests
cd n8n-ops-ui
npm run test:e2e

# Run in headless mode
npm run test:e2e:headless

# Run specific test file
npx playwright test tests/promotion.spec.ts
```

**Configuration**: `n8n-ops-ui/playwright.config.ts`

---

## Test Files Inventory

### Backend Tests (63 files)

**Core Services**:
- `test_promotion_service.py` - Promotion logic
- `test_promotion_validation.py` - Pre-flight checks
- `test_diff_service.py` - Diff computation
- `test_drift_detection_service.py` - Drift detection
- `test_drift_incident_service.py` - Incident lifecycle
- `test_drift_retention_service.py` - Retention enforcement
- `test_observability_service.py` - KPIs, metrics
- `test_background_job_service.py` - Job management
- `test_github_service.py` - Git operations
- `test_n8n_client.py` - n8n API client
- `test_notification_service.py` - Notifications
- `test_sync_status_service.py` - Sync tracking
- `test_webhook_lock_service.py` - Webhook locking
- `test_workflow_analysis_service.py` - Workflow analysis
- `test_entitlements.py` - Entitlement resolution
- `test_feature_gate.py` - Feature gates
- `test_plan_resolver.py` - Plan resolution
- `test_tenant_plan_service.py` - Plan management
- `test_downgrade_service.py` - Downgrade handling (assumed, not listed)
- `test_untracked_workflows_service.py` - Untracked detection

**API Endpoints**:
- `test_auth_api.py` - Authentication
- `test_auth_service.py` - Auth service
- `test_environments_api.py` - Environments
- `test_workflows_api.py` - Workflows
- `test_promotions_api.py` - Promotions
- `test_promotions_api_background.py` - Background promotions
- `test_deployments_api.py` - Deployments
- `test_pipelines_api.py` - Pipelines
- `test_executions_api.py` - Executions
- `test_credentials_api.py` - Credentials
- `test_admin_credentials_api.py` - Admin credential ops
- `test_tags_api.py` - Tags
- `test_teams_api.py` - Team management
- `test_billing_api.py` - Billing
- `test_billing_webhooks.py` - Stripe webhooks
- `test_notifications_endpoints.py` - Notifications
- `test_snapshots_api.py` - Snapshots
- `test_restore_api.py` - Restore
- `test_retention_api.py` - Retention
- `test_support_api.py` - Support tickets
- `test_support_service.py` - Support service
- `test_security_api_keys_api.py` - API keys
- `test_n8n_users_api.py` - N8N users

**Specialized Tests**:
- `test_promotion_atomicity.py` - Rollback guarantees
- `test_promotion_idempotency.py` - Duplicate detection
- `test_promotion_failure_snapshot_intact.py` - Snapshot integrity
- `test_snapshot_before_promotion.py` - Snapshot timing
- `test_rollback_workflow_state.py` - Rollback correctness
- `test_t016_rollback_404_graceful_failure.py` - 404 handling
- `test_t017_rollback_audit_logs.py` - Audit completeness
- `test_t018_environment_action_guards_rollback.py` - Guard bypass
- `test_deployment_workflows.py` - Per-workflow tracking
- `test_stale_deployment.py` - Stale detection
- `test_canonical_onboarding_integrity.py` - Onboarding integrity
- `test_environment_action_guard.py` - Action guards
- `test_audit_middleware.py` - Audit middleware
- `test_aggregations.py` - Aggregation functions
- `test_retention.py` - Retention enforcement

**Security Tests** (`tests/security/`):
- `test_tenant_isolation.py` - Cross-tenant leak scenarios
- `test_impersonation_audit.py` - Impersonation audit trail

**Task-Specific Tests**:
- `test_t008_404_error_handling.py` - 404 error handling
- `test_t009_schema.py` - Schema validation

**Total**: 63 test files

---

## Coverage by MVP Area

### 1. Promotions & Deployments

**Coverage**: ~80% (Strong)

**Unit Tests**:
- ✅ Core promotion logic (`test_promotion_service.py`)
- ✅ Pre-flight validation (`test_promotion_validation.py`)
- ✅ Diff computation (`test_diff_service.py`)
- ✅ Idempotency (`test_promotion_idempotency.py`)
- ✅ Atomicity & rollback (`test_promotion_atomicity.py`)
- ✅ Snapshot timing (`test_snapshot_before_promotion.py`)
- ✅ Rollback state correctness (`test_rollback_workflow_state.py`)
- ✅ 404 handling (`test_t016_rollback_404_graceful_failure.py`)
- ✅ Audit logs (`test_t017_rollback_audit_logs.py`)

**Integration Tests**:
- ✅ Promotion API (`test_promotions_api.py`)
- ✅ Background execution (`test_promotions_api_background.py`)
- ✅ Deployment API (`test_deployments_api.py`)
- ✅ Pipeline API (`test_pipelines_api.py`)

**E2E Tests**:
- ✅ Complete: Full end-to-end promotion flow ([`test_promotion_e2e.py`](../n8n-ops-backend/tests/e2e/test_promotion_e2e.py))
- ✅ Error scenarios: timeout, 404, rate limit, server errors
- ✅ Frontend E2E: Playwright tests for UI flow

**Gaps**:
- ❌ Conflict flag enforcement (`allowOverwritingHotfixes`, `allowForcePromotionOnConflicts`)
- ❌ Multi-stage pipeline execution
- ❌ Concurrent promotion scenarios
- ❌ Rollback retry on transient failures

---

### 2. Drift Detection & Incident Management

**Coverage**: ~60% (Good)

**Unit Tests**:
- ✅ Drift detection (`test_drift_detection_service.py`)
- ✅ Incident lifecycle (`test_drift_incident_service.py`)
- ✅ Retention (`test_drift_retention_service.py`)

**Integration Tests**:
- ⚠️ Partial: API endpoints likely covered but not explicitly listed

**E2E Tests**:
- ❌ None

**Gaps**:
- ❌ TTL enforcement during promotions
- ❌ State transition edge cases
- ❌ Drift approval workflow
- ❌ SLA auto-escalation
- ❌ Payload size limits (JSONB)
- ❌ Concurrent incident creation

---

### 3. Canonical Workflow System

**Coverage**: ~60% (Good)

**Unit Tests**:
- ✅ Onboarding integrity (`test_canonical_onboarding_integrity.py`)
- ✅ Untracked detection (`test_untracked_workflows_service.py`)

**Integration Tests**:
- ⚠️ Partial: API endpoints likely covered

**E2E Tests**:
- ❌ None

**Gaps**:
- ❌ Git sync conflict resolution
- ❌ Matrix view performance (1000+ workflows)
- ❌ Content hash collision detection
- ❌ Reconciliation strategies
- ❌ Batch size configurability
- ❌ Status precedence edge cases

---

### 4. Multi-Tenancy & Security

**Coverage**: ~70% (Strong)

**Unit Tests**:
- ✅ Auth service (`test_auth_service.py`)
- ✅ Feature gates (`test_feature_gate.py`)

**Integration Tests**:
- ✅ Auth API (`test_auth_api.py`)
- ✅ Audit middleware (`test_audit_middleware.py`)

**Security Tests**:
- ✅ Tenant isolation (`tests/security/test_tenant_isolation.py`)
- ✅ Impersonation audit (`tests/security/test_impersonation_audit.py`)

**E2E Tests**:
- ❌ None

**Gaps**:
- ❌ Admin-to-admin impersonation block enforcement
- ❌ Session timeout enforcement
- ❌ RLS policy validation (Supabase-level)
- ❌ Cross-tenant leak scenarios (comprehensive)
- ❌ RBAC server-side enforcement

---

### 5. Billing & Entitlements

**Coverage**: ~50% (Partial)

**Unit Tests**:
- ✅ Entitlement resolution (`test_entitlements.py`)
- ✅ Feature gates (`test_feature_gate.py`)
- ✅ Plan resolver (`test_plan_resolver.py`)
- ✅ Tenant plan service (`test_tenant_plan_service.py`)

**Integration Tests**:
- ✅ Billing API (`test_billing_api.py`)
- ✅ Stripe webhooks (`test_billing_webhooks.py`)

**E2E Tests**:
- ✅ Complete: Downgrade flow with Stripe webhook testing ([`test_downgrade_e2e.py`](../n8n-ops-backend/tests/e2e/test_downgrade_e2e.py))

**Gaps**:
- ❌ Downgrade grace period expiry enforcement
- ❌ USER_CHOICE downgrade strategy
- ❌ Concurrent plan changes
- ❌ Resource reactivation on upgrade
- ❌ Over-limit detection (periodic, not just webhook)
- ❌ Checkout E2E flow

---

### 6. Executions & Observability

**Coverage**: ~40% (Weak)

**Unit Tests**:
- ✅ Observability service (`test_observability_service.py`)
- ✅ Aggregations (`test_aggregations.py`)
- ✅ Retention (`test_retention.py`)

**Integration Tests**:
- ✅ Executions API (`test_executions_api.py`)
- ✅ Retention API (`test_retention_api.py`)

**E2E Tests**:
- ❌ None

**Gaps**:
- ❌ Sparkline aggregation performance (100k+ executions)
- ❌ Error intelligence grouping
- ❌ Materialized view refresh failures
- ❌ SSE reconnection after server restart
- ❌ Execution sync performance (10k+ executions)
- ❌ KPI calculation edge cases

---

## Known Flaky or Failing Tests

**Status**: Unknown

**Recommendation**: Run full test suite and document flaky tests

**Common Flaky Test Patterns**:
- Time-dependent tests (timestamps, TTL)
- External API mocks (n8n, GitHub, Stripe)
- Race conditions (concurrent operations)
- Database transaction timing

---

## Test Infrastructure Gaps

### Missing Test Types

1. **Load Tests**: No performance/load tests for:
   - Workflow sync (10k+ workflows)
   - Execution sync (100k+ executions)
   - Matrix view (1000+ workflows × 10 envs)
   - Concurrent promotions

2. **E2E Tests**: Minimal E2E coverage:
   - No full promotion flow E2E
   - No onboarding flow E2E
   - No drift detection flow E2E
   - No billing checkout flow E2E

3. **Contract Tests**: No API contract tests (OpenAPI validation)

4. **Security Tests**: Limited security testing:
   - No penetration testing
   - No SQL injection tests
   - No XSS/CSRF tests
   - Limited RLS testing

5. **Chaos Tests**: No chaos engineering:
   - DB connection failures
   - n8n API unavailability
   - Stripe webhook failures
   - Network partitions

### Test Infrastructure Issues

1. **Test Data Management**: No documented test data fixtures

2. **Test Isolation**: Unknown if tests share state or run in isolation

3. **CI/CD Integration**: Unknown if tests run in CI/CD pipeline

4. **Test Coverage Reporting**: HTML coverage reports exist (`htmlcov/`) but target coverage unknown

5. **Mock Management**: No centralized mock management for external APIs

---

## Recommendations

### Must Fix Before MVP Launch

1. **✅ COMPLETED: Add E2E Tests**: 5 critical flows implemented:
   - ✅ Full promotion flow (create pipeline → promote → verify) - [`test_promotion_e2e.py`](../n8n-ops-backend/tests/e2e/test_promotion_e2e.py)
   - ✅ Drift detection → incident → reconcile - [`test_drift_e2e.py`](../n8n-ops-backend/tests/e2e/test_drift_e2e.py)
   - ✅ Canonical onboarding flow - [`test_canonical_e2e.py`](../n8n-ops-backend/tests/e2e/test_canonical_e2e.py)
   - ✅ Downgrade flow (Stripe webhook → enforcement) - [`test_downgrade_e2e.py`](../n8n-ops-backend/tests/e2e/test_downgrade_e2e.py)
   - ✅ Impersonation flow - [`test_impersonation_e2e.py`](../n8n-ops-backend/tests/e2e/test_impersonation_e2e.py)
   
   **Frontend E2E** (Playwright):
   - ✅ Promotion UI flow - [`promotion-flow.spec.ts`](../n8n-ops-ui/tests/e2e/promotion-flow.spec.ts)
   - ✅ Drift incident management UI - [`drift-flow.spec.ts`](../n8n-ops-ui/tests/e2e/drift-flow.spec.ts)
   - ✅ Canonical onboarding wizard - [`canonical-onboarding.spec.ts`](../n8n-ops-ui/tests/e2e/canonical-onboarding.spec.ts)
   - ✅ Impersonation UI flow - [`impersonation-flow.spec.ts`](../n8n-ops-ui/tests/e2e/impersonation-flow.spec.ts)
   
   **Test Infrastructure**:
   - ✅ HTTP-boundary mocking using `respx` (no real API calls)
   - ✅ Testkit with factories and golden JSON fixtures ([`tests/testkit/`](../n8n-ops-backend/tests/testkit/))
   - ✅ GitHub Actions CI workflow ([`.github/workflows/e2e-tests.yml`](../.github/workflows/e2e-tests.yml))
   - ✅ Comprehensive documentation ([Backend E2E](../n8n-ops-backend/tests/e2e/README.md), [Frontend E2E](../n8n-ops-ui/tests/e2e/README.md), [Testkit](../n8n-ops-backend/tests/testkit/README.md))

2. **Test Critical Gaps**:
   - Conflict flag enforcement
   - TTL enforcement during promotions
   - Grace period expiry
   - Admin-to-admin impersonation block
   - Session timeout

3. **Load Test Critical Paths**:
   - Workflow sync (10k+ workflows)
   - Matrix view (1000+ workflows)
   - Execution sync (100k+ executions)

4. **Document Flaky Tests**: Run full suite multiple times, identify flaky tests

5. **Set Coverage Target**: Aim for 70% unit test coverage, 50% integration

### Should Fix Post-MVP

1. **Add Contract Tests**: Validate API contracts with OpenAPI
2. **Add Security Tests**: Penetration testing, SQL injection, XSS
3. **Add Chaos Tests**: Simulate failures, test resilience
4. **Improve Test Isolation**: Ensure tests don't share state
5. **Centralize Mocks**: Create mock factory for external APIs

### Nice to Have

1. **Visual Regression Tests**: Screenshot comparison for UI
2. **Accessibility Tests**: WCAG compliance
3. **Mutation Testing**: Test the tests
4. **Property-Based Testing**: Generate test cases automatically

---

## Test Coverage Targets

| Area | Current (Estimate) | Target MVP | Target Post-MVP |
|------|-------------------|------------|-----------------|
| Promotions | 80% | 90% | 95% |
| Drift | 60% | 75% | 90% |
| Canonical | 60% | 75% | 90% |
| Security | 70% | 85% | 95% |
| Billing | 50% | 70% | 85% |
| Observability | 40% | 60% | 80% |
| **Overall** | **60%** | **75%** | **90%** |

---

## Test Execution Time

**Unknown**: Test suite execution time not documented

**Recommendation**: 
- Measure and document test execution time
- Set target: <5 min for unit tests, <30 min for integration tests
- Parallelize tests if needed

---

## Conclusion

**Strengths**:
- Strong promotion/deployment test coverage
- Good security test coverage (tenant isolation, impersonation)
- Specialized atomicity/idempotency tests

**Weaknesses**:
- Minimal E2E test coverage
- No load/performance tests
- Many critical gaps (conflict flags, TTL, grace period expiry)
- No chaos/resilience tests

**Overall Assessment**: Test coverage is **adequate for MVP** but **needs improvement** before production launch. Priority should be:
1. Add critical E2E tests
2. Test identified gaps (conflict flags, TTL, grace periods)
3. Load test critical paths
4. Document and fix flaky tests

