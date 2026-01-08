# 02 - Promotions & Deployments

## State Machines

### Promotion State Machine

**File**: `n8n-ops-backend/app/schemas/promotion.py:PromotionStatus`

```
PENDING → PENDING_APPROVAL → APPROVED → RUNNING → COMPLETED
   ↓            ↓                          ↓           
CANCELLED   REJECTED                   FAILED
```

**Transitions**:
- `PENDING → PENDING_APPROVAL`: Requires approval gate
- `PENDING → RUNNING`: No approval required
- `PENDING_APPROVAL → APPROVED`: Admin/approver approves
- `PENDING_APPROVAL → REJECTED`: Admin/approver rejects
- `APPROVED → RUNNING`: Execution starts
- `RUNNING → COMPLETED`: All workflows promoted successfully
- `RUNNING → FAILED`: Any workflow fails, triggers rollback
- `PENDING → CANCELLED`: User cancels before execution

**Code**: `n8n-ops-backend/app/services/promotion_service.py:PromotionService`
- Lines 194-2469: Full promotion service implementation
- Lines 1-50: Critical invariants documentation

### Deployment State Machine

**File**: `n8n-ops-backend/app/schemas/deployment.py:DeploymentStatus`

```
PENDING → SCHEDULED → RUNNING → COMPLETED
   ↓          ↓          ↓           
CANCELLED  CANCELLED  FAILED
```

**Transitions**:
- `PENDING → SCHEDULED`: Scheduled for future execution
- `PENDING → RUNNING`: Immediate execution
- `SCHEDULED → RUNNING`: Scheduler picks up job
- `RUNNING → COMPLETED`: Execution finishes successfully
- `RUNNING → FAILED`: Execution fails
- `PENDING/SCHEDULED → CANCELLED`: User cancels
- Stale detection: `RUNNING` for >1hr → `FAILED` (on startup)

**Code**: `n8n-ops-backend/app/services/deployment_scheduler.py`
- `start_scheduler()`: Background task polling
- `n8n-ops-backend/app/main.py` lines 448-481: Stale cleanup

---

## Snapshot Creation & Rollback

### Pre-Promotion Snapshot

**Purpose**: Create point-in-time backup before mutations

**Implementation**:
- **File**: `promotion_service.py:create_pre_promotion_snapshot()`
- **When**: Before ANY target environment mutations (invariant T002)
- **What**: Captures all workflows in target environment
- **Storage**: Git-backed (`snapshots` table + GitHub repo)
- **Type**: `snapshot_type = "pre_promotion"`

**Code Flow**:
1. `execute_promotion()` → calls `create_pre_promotion_snapshot()`
2. Snapshot ID stored in `promotions.target_pre_snapshot_id`
3. Used for rollback if promotion fails

### Post-Promotion Snapshot

**When**: After successful promotion
**Type**: `snapshot_type = "post_promotion"`
**Purpose**: Record final state for audit/compliance

### Rollback Mechanism

**File**: `promotion_service.py:_rollback_promotion()`

**Trigger Conditions**:
- Any workflow fails to promote
- Gate validation fails mid-execution
- API errors during promotion

**Rollback Steps**:
1. Fetch pre-promotion snapshot by ID
2. Restore ALL successfully promoted workflows from snapshot
3. Log rollback outcome in `promotions.execution_result.rollback_result`
4. Mark promotion as `FAILED`

**Edge Cases Handled**:
- Missing workflows during rollback (404/400 from provider)
  - Code: `promotion_service.rollback_promotion` restores via `update` then falls back to `create`
  - Tests: `tests/test_promotion_atomicity.py::TestRollbackPromotion::test_rollback_creates_workflow_if_not_exists`, `test_rollback_handles_structured_not_found_error`
  - Behavior: continue best-effort; rollback result includes errors instead of raising
- Transient provider errors during rollback (timeouts/429/5xx)
  - Code: `_execute_with_retry` (bounded retries with backoff) wraps provider calls in rollback
  - Tests: `tests/test_promotion_atomicity.py::TestRollbackPromotion::test_rollback_retries_transient_error_and_succeeds`, `test_rollback_stops_after_bounded_retries`
  - Behavior: retry up to 3 attempts, surface error after budget
- Partial promotions always trigger rollback and return a rollback_result
  - Code: `execute_promotion` immediately calls `rollback_promotion` on first failure and returns rollback stats (even on critical failures)
  - Tests: `tests/test_promotion_atomicity.py::TestExecutePromotionWithRollback::*` coverage for rollback inclusion and audit logging
- Legacy (non-canonical) environments without `git_folder`
  - Code: `execute_promotion` falls back to `get_all_workflows_from_github(environment_type, commit_sha)` when `git_folder` is absent
  - Behavior: promotions and rollbacks stay resilient even for legacy envs
- Environment action guards during rollback
  - Behavior: Bypass guards for rollback operations

**Risk**: Partial rollback if target environment becomes unavailable mid-rollback

---

## Idempotency Strategy

### Content Hash Comparison

**File**: `promotion_service.py:normalize_workflow_for_comparison()` (lines 85-156)

**Fields Excluded from Comparison**:
- Metadata: `id`, `createdAt`, `updatedAt`, `versionId`
- Runtime: `triggerCount`, `staticData`, `meta`, `hash`
- Environment-specific: `active`, `tags`, `tagIds`
- UI-specific: node `position`, `positionAbsolute`
- Credentials: Compare by name only (ID differs per env)

**Hash Algorithm**: JSON dump with sorted keys → likely SHA256 (not explicitly stated)

**Idempotency Check**:
```python
source_normalized = normalize_workflow_for_comparison(source_wf)
target_normalized = normalize_workflow_for_comparison(target_wf)
if source_normalized == target_normalized:
    skip_promotion()  # No actual changes
```

**Test**: `tests/test_promotion_idempotency.py`

**Risk**: Normalization may skip legitimate differences if exclusion list is too broad

---

## Conflict Policy Flag Enforcement

### allowOverwritingHotfixes

**Schema**: `n8n-ops-backend/app/schemas/pipeline.py:PipelineStageGates`

**Meaning**: Allow overwriting workflows in target that are newer than source (hotfixes)

**Detection**:
- **File**: `services/diff_service.py`
- **Logic**: Compare `updatedAt` timestamps
- If `target.updatedAt > source.updatedAt` → `DiffStatus.TARGET_HOTFIX`

**Enforcement**:
- **File**: `promotion_service.py:execute_promotion()`
- If `TARGET_HOTFIX` detected and `allowOverwritingHotfixes = false`:
  - Log warning
  - Skip workflow
  - Mark as `skipped` in `deployment_workflows`
- If `allowOverwritingHotfixes = true`:
  - Overwrite target with source

**Test**: Unknown (not found in test files)

### allowForcePromotionOnConflicts

**Schema**: `PipelineStageGates`

**Meaning**: Force promotion even if conflicts detected

**Enforcement**:
- Similar to `allowOverwritingHotfixes`
- Controls behavior when `DiffStatus.TARGET_HOTFIX` or other conflicts exist

**Code**: `promotion_service.py` (embedded in execution logic)

**Test**: Unknown

### allowPlaceholderCredentials

**Schema**: `PipelineStageGates`

**Meaning**: Allow promotion even if credentials missing in target

**Enforcement**:
- **File**: `promotion_validation_service.py:check_credentials_exist()`
- Pre-flight check: Verify all source credentials exist in target
- If missing and `allowPlaceholderCredentials = false` → Block promotion
- If `true` → Allow, log warning

**Test**: `tests/test_promotion_validation.py`

---

## Endpoints, Jobs & Tables

### API Endpoints

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| POST | `/api/v1/promotions` | `promotions.py:create_promotion` | Initiate promotion |
| POST | `/api/v1/promotions/validate` | `promotions.py:validate_promotion` | Pre-flight checks |
| POST | `/api/v1/promotions/compare` | `promotions.py:compare_environments` | Diff computation |
| POST | `/api/v1/promotions/{id}/execute` | `promotions.py:execute_promotion` | Execute promotion |
| POST | `/api/v1/promotions/{id}/approve` | `promotions.py:approve_promotion` | Approve pending |
| POST | `/api/v1/promotions/{id}/reject` | `promotions.py:reject_promotion` | Reject pending |
| GET | `/api/v1/promotions` | `promotions.py:list_promotions` | List history |
| GET | `/api/v1/promotions/{id}` | `promotions.py:get_promotion` | Get details |
| GET | `/api/v1/promotions/drift-check/{env_id}` | `promotions.py:check_drift_policy_blocking` | Check drift blocking |
| POST | `/api/v1/pipelines` | `pipelines.py:create_pipeline` | Create pipeline |
| GET | `/api/v1/pipelines` | `pipelines.py:list_pipelines` | List pipelines |
| GET | `/api/v1/pipelines/{id}` | `pipelines.py:get_pipeline` | Get pipeline |
| POST | `/api/v1/deployments` | `deployments.py:create_deployment` | Schedule deployment |
| GET | `/api/v1/deployments` | `deployments.py:list_deployments` | List deployments |
| GET | `/api/v1/deployments/{id}` | `deployments.py:get_deployment` | Get deployment |
| GET | `/api/v1/sse/deployments/{id}` | `sse.py:stream_deployment` | Real-time progress |

**RBAC (backend enforced)**:
- `POST /promotions/{id}/execute` now requires tenant admin via `require_tenant_admin()` plus `workflow_ci_cd` entitlement.
- Pipeline writes (`POST /pipelines`, `PUT/DELETE /pipelines/{id}`) require tenant admin + `workflow_ci_cd` entitlement.

### Background Jobs

| Job Type | File | Schedule | Purpose |
|----------|------|----------|---------|
| Deployment Scheduler | `deployment_scheduler.py` | Continuous loop (10s interval) | Execute scheduled deployments |
| Stale Deployment Cleanup | `main.py:startup_event` | On startup | Mark stale `RUNNING` deployments as `FAILED` (>1hr) |

**Scheduler Logic**:
```python
async def _scheduler_loop():
    while _scheduler_running:
        deployments = fetch_pending_scheduled_deployments()
        for dep in deployments:
            if dep.scheduled_for <= now():
                await execute_deployment(dep)
        await asyncio.sleep(10)
```

### Database Tables

#### promotions

**Purpose**: Track promotion requests and execution results

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID): Tenant isolation
- `pipeline_id` (UUID): Pipeline used
- `source_environment_id` (UUID): Source env
- `target_environment_id` (UUID): Target env
- `status` (enum): PromotionStatus
- `workflow_selections` (JSONB): Workflows to promote
- `gate_results` (JSONB): Gate check results
- `source_snapshot_id` (UUID): Source snapshot
- `target_pre_snapshot_id` (UUID): Pre-promotion snapshot
- `target_post_snapshot_id` (UUID): Post-promotion snapshot
- `execution_result` (JSONB): Detailed results + rollback info
- `created_by` (UUID): User who initiated
- `approved_by` (UUID): Approver (if applicable)
- `created_at`, `updated_at`, `completed_at`: Timestamps

**Indexes**: Unknown (need migration review)

#### pipelines

**Purpose**: Define promotion paths and gates

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID): Tenant isolation
- `provider` (text): Provider (n8n)
- `name`, `description`: Metadata
- `stages` (JSONB): Ordered stages with gates
- `is_active` (bool): Enable/disable
- `created_at`, `updated_at`: Timestamps

#### deployments

**Purpose**: Track deployment execution (wrapper around promotions)

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID): Tenant isolation
- `promotion_id` (UUID): FK to promotions
- `status` (enum): DeploymentStatus
- `scheduled_for` (timestamp): Scheduled time (nullable)
- `started_at`, `finished_at`: Execution window
- `summary_json` (JSONB): Execution summary
- `is_deleted` (bool): Soft delete

**Indexes**: Likely on `(status, scheduled_for)` for scheduler query

#### deployment_workflows

**Purpose**: Track per-workflow promotion results

**Key Columns**:
- `id` (UUID): Primary key
- `deployment_id` (UUID): FK to deployments
- `workflow_id` (text): n8n workflow ID
- `workflow_name` (text): Workflow name
- `status` (text): success/failed/skipped
- `error_message` (text): Failure reason
- `promoted_at` (timestamp): When promoted

#### snapshots

**Purpose**: Store point-in-time environment backups

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID): Tenant isolation
- `environment_id` (UUID): Environment
- `snapshot_type` (text): pre_promotion, post_promotion, manual_backup
- `workflows` (JSONB): Workflow data
- `git_commit_sha` (text): Git commit reference
- `created_by` (UUID): User
- `created_at`: Timestamp

**Constraints**: Git-backed (stored in GitHub repo)

---

## Test Coverage

### Unit Tests

| Test File | Coverage |
|-----------|----------|
| `test_promotion_service.py` | Core promotion logic |
| `test_promotion_validation.py` | Pre-flight checks |
| `test_diff_service.py` | Diff computation |
| `test_promotion_atomicity.py` | Rollback guarantees |
| `test_promotion_idempotency.py` | Duplicate detection |
| `test_snapshot_before_promotion.py` | Snapshot timing |
| `test_promotion_failure_snapshot_intact.py` | Snapshot integrity |
| `test_rollback_workflow_state.py` | Rollback correctness |

### Integration Tests

| Test File | Coverage |
|-----------|----------|
| `test_promotions_api.py` | API endpoints |
| `test_promotions_api_background.py` | Background execution |
| `test_deployments_api.py` | Deployment endpoints |
| `test_pipelines_api.py` | Pipeline CRUD |

### Specialized Tests

| Test File | Coverage |
|-----------|----------|
| `test_t016_rollback_404_graceful_failure.py` | 404 during rollback |
| `test_t017_rollback_audit_logs.py` | Audit trail completeness |
| `test_t018_environment_action_guards_rollback.py` | Guard bypass during rollback |
| `test_stale_deployment.py` | Stale detection |
| `test_deployment_workflows.py` | Per-workflow tracking |

---

## Risk Areas

### High Risk

1. **Rollback Completeness**: If target environment becomes unavailable mid-rollback, only partial rollback occurs. No retry mechanism documented.
   
2. **Snapshot Timing**: Pre-promotion snapshot created BEFORE mutations, but race condition possible if target environment changes between snapshot and promotion start.

3. **Conflict Flag Enforcement**: `allowOverwritingHotfixes` and `allowForcePromotionOnConflicts` lack comprehensive tests. Edge cases unknown.

4. **Idempotency Normalization**: Normalization excludes many fields. Risk of skipping legitimate differences or promoting unintended changes.

### Medium Risk

1. **Stale Deployment Threshold**: 1-hour threshold may be too short for large promotions with many workflows.

2. **Scheduler Reliability**: Deployment scheduler runs in-process. If process crashes, scheduled deployments may be missed or executed late.

3. **SSE Reconnection**: Real-time progress via SSE. If client disconnects, no retry/resume mechanism documented.

### Low Risk

1. **Gate Validation**: Gates checked during pre-flight, but not re-checked immediately before execution (time gap).

2. **Credential Availability**: Check relies on sync accuracy. Stale credential data could cause false positives/negatives.

---

## Gaps & Missing Features

### Not Implemented

1. **Credential Remapping UI**: Admin credential matrix exists, but no user-facing UI to map credentials during promotion. (PRD requirement CRE
D-008)

2. **Promotion Dry-Run**: No explicit dry-run mode to preview promotion without executing.

3. **Partial Promotion Resume**: If promotion fails, cannot resume from checkpoint. Must retry entire promotion.

4. **Multi-Stage Pipelines**: Pipelines support multiple stages, but multi-stage execution logic untested.

5. **Approval Delegation**: Approval mechanism exists, but no delegation/escalation flow.

### Unclear Behavior

1. **Concurrent Promotions**: Can multiple promotions run simultaneously to same target? Locking mechanism unknown.

2. **Snapshot Retention**: How long are snapshots retained? Cleanup policy not documented.

3. **Rollback Audit**: Rollback logs to audit table, but audit query performance with large rollback payloads unknown.

---

## Critical Invariants (from code documentation)

**File**: `promotion_service.py` lines 1-50

1. **T002**: SNAPSHOT-BEFORE-MUTATE
   - Pre-promotion snapshots MUST be created before ANY target mutations
   
2. **T003**: ATOMIC ROLLBACK ON FAILURE
   - All-or-nothing guarantee. Partial success requires full rollback
   
3. **T004**: IDEMPOTENCY ENFORCEMENT
   - Re-executing same promotion must not create duplicates
   
4. **T005**: CONFLICT POLICY - allowOverwritingHotfixes
   - Strict enforcement of policy flag
   
5. **T006**: CONFLICT POLICY - allowForcePromotionOnConflicts
   - Strict enforcement of policy flag
   
6. **T009**: AUDIT TRAIL COMPLETENESS
   - All operations logged with snapshot IDs, states, failures, rollback outcomes

---

## Diff Status Types

**File**: `schemas/promotion.py:DiffStatus`

| Status | Meaning | Promotion Behavior |
|--------|---------|-------------------|
| ADDED | Workflow only in source | Promote (create in target) |
| MODIFIED | Exists in both, source newer | Promote (update target) |
| DELETED | Workflow only in target | Skip (or delete if configured) |
| UNCHANGED | Identical content | Skip |
| TARGET_HOTFIX | Target has newer version | Skip (unless `allowOverwritingHotfixes`) |

---

## Risk Level Calculation

**File**: `promotion_service.py:calculate_risk_level()`

| Level | Triggers |
|-------|----------|
| LOW | Rename only, minor changes |
| MEDIUM | Error handling changes, settings changes |
| HIGH | Credentials, expressions, triggers, HTTP nodes, code nodes, routing changes |

**Logic**: Heuristic-based scanning of workflow JSON for risky patterns.

**Test**: Unknown (not found in test files)

**Risk**: Risk levels are heuristic and may miss edge cases or misclassify changes.

---

## Recommendations

### Must Fix Before MVP Launch

1. Test `allowOverwritingHotfixes` and `allowForcePromotionOnConflicts` enforcement comprehensively
2. Document snapshot retention policy
3. Add rollback retry mechanism for transient failures
4. Test concurrent promotion scenarios

### Should Fix Post-MVP

1. Implement credential remapping UI
2. Add promotion dry-run mode
3. Add partial promotion resume capability
4. Improve risk level classification (add ML/rule engine)

### Nice to Have

1. Multi-stage pipeline orchestration
2. Approval delegation/escalation
3. Promotion templates
4. Rollback preview/impact analysis

