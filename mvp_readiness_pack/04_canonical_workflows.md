# 04 - Canonical Workflow System

## Canonical Model & Mapping Logic

### Core Concept
- **Canonical Workflow**: Git-backed "source of truth" for a workflow across all environments
- **workflow_env_map**: Junction table mapping canonical workflows to specific environment instances

### Tables

**canonical_workflows**
- `id` (UUID): Primary key (canonical_id)
- `tenant_id`: Tenant isolation
- `canonical_slug`: Human-readable identifier (e.g., `customer_onboarding`)
- `name`: Workflow display name
- `content_hash`: SHA256 of normalized workflow JSON
- `workflow_definition` (JSONB): Actual workflow JSON from Git
- `git_file_path`: Path in Git repo
- `provider`: n8n (enum)
- `created_at`, `updated_at`

**workflow_env_map**
- `id` (UUID): Primary key (surrogate key, added later for performance)
- `canonical_id` (UUID): FK to canonical_workflows (nullable)
- `environment_id` (UUID): FK to environments
- `n8n_workflow_id` (text): Provider-specific ID
- `status`: WorkflowMappingStatus enum
- `env_content_hash`: Hash of workflow as it exists in environment
- `git_content_hash`: Hash of workflow as it exists in Git
- `n8n_updated_at`: Last update timestamp from n8n
- `workflow_name`, `workflow_data` (JSONB): Cached data

**Migration**: `alembic/versions/dcd2f2c8774d_create_canonical_workflow_tables.py`

---

## workflow_env_map Constraints

### Status Enum

**File**: `schemas/canonical_workflow.py:WorkflowMappingStatus`

```python
class WorkflowMappingStatus(str, Enum):
    LINKED = "linked"       # Has canonical_id, tracked
    UNTRACKED = "untracked" # No canonical_id, needs onboarding
    MISSING = "missing"     # Was linked/untracked, now gone from n8n
    IGNORED = "ignored"     # Explicitly ignored by user
    DELETED = "deleted"     # Soft-deleted
```

### Status Precedence Rules

**Lines 32-73** (from code):
1. **DELETED** - Highest precedence (once deleted, stays deleted)
2. **IGNORED** - User-explicit ignore overrides system states
3. **MISSING** - If workflow disappears from n8n during sync
4. **UNTRACKED** - If no canonical_id (not mapped)
5. **LINKED** - Default operational state (has canonical_id + n8n_workflow_id)

### State Transitions

**File**: `services/canonical_env_sync_service.py:sync_environment()`

- New workflow detected → UNTRACKED (if no match) or LINKED (if auto-linked)
- User links untracked → UNTRACKED → LINKED
- Workflow disappears from n8n → LINKED/UNTRACKED → MISSING
- Missing workflow reappears → MISSING → LINKED or UNTRACKED
- User marks as ignored → any state → IGNORED
- Workflow deleted → any state → DELETED

### Unique Constraints

- `(environment_id, n8n_workflow_id)` - Unique per environment
- `(canonical_id, environment_id)` - One canonical workflow per environment (if linked)

**Test**: `tests/test_canonical_onboarding_integrity.py`

---

## Untracked Detection & Onboarding Flow

### Untracked Detection

**Service**: `services/untracked_workflows_service.py:get_untracked()`

**Query Logic**:
```sql
SELECT * FROM workflow_env_map
WHERE tenant_id = ? 
  AND canonical_id IS NULL
  AND status IN ('untracked', 'missing')
  AND is_deleted = false
```

**API**: `GET /api/v1/canonical/untracked?environment_id={id}`

**Detection Timing**:
- During environment sync
- On-demand via API call
- After canonical onboarding (identifies remaining untracked)

### Onboarding Flow

**Service**: `services/canonical_onboarding_service.py`

**Phases**:

#### 1. Preflight Check
**API**: `GET /api/v1/canonical/onboard/preflight`

**Checks**:
- At least one environment configured
- GitHub repository configured
- No active onboarding job running
- Tenant has permission (entitlement check)

**Returns**: `{ready: bool, errors: [], warnings: []}`

#### 2. Inventory Phase
**API**: `POST /api/v1/canonical/onboard/inventory`

**Steps**:
1. Designate "anchor" environment (typically production)
2. Scan all workflows in anchor environment
3. Generate canonical IDs (slug based on workflow name)
4. Create canonical_workflow records
5. Link anchor environment workflows
6. Scan other environments and auto-link where possible (by name matching)

**Background Job**: `BackgroundJobType.CANONICAL_ONBOARDING_INVENTORY`

**Idempotency**: Uses unique constraints to prevent duplicates

**Test**: `tests/test_canonical_onboarding_integrity.py`

#### 3. Migration PR Creation (Optional)
**API**: `POST /api/v1/canonical/onboard/create-pr`

**Purpose**: Create Git PR with initial workflow files

**Not Implemented**: PR creation logic stub exists but not fully implemented

#### 4. Completion Check
**API**: `GET /api/v1/canonical/onboard/completion`

**Returns**: 
- Onboarding status
- Workflows still untracked
- Environments synced

---

## Matrix View Generation

### Purpose
Cross-environment status view showing which workflows exist where and their sync state

### API
**Endpoint**: `GET /api/v1/workflows/matrix`

**File**: `api/endpoints/workflow_matrix.py:get_matrix()`

### Query Logic
```sql
SELECT 
  cw.id AS canonical_id,
  cw.name,
  wem.environment_id,
  wem.status,
  wem.env_content_hash,
  wem.git_content_hash
FROM canonical_workflows cw
LEFT JOIN workflow_env_map wem ON cw.id = wem.canonical_id
WHERE cw.tenant_id = ?
  AND (wem.is_deleted = false OR wem.id IS NULL)
ORDER BY cw.name
```

### Response Format
```json
{
  "workflows": [
    {
      "canonical_id": "...",
      "name": "Customer Onboarding",
      "environments": {
        "env-dev-id": {
          "status": "linked",
          "synced": true
        },
        "env-prod-id": {
          "status": "drift",
          "synced": false
        }
      }
    }
  ]
}
```

### Derived Statuses (Display Only)
- **DRIFT**: `status = LINKED` but `env_content_hash ≠ git_content_hash`
- **OUT_OF_DATE**: Git is newer than environment
- **IN_SYNC**: Hashes match

**Performance Risk**: With 1000+ workflows × 10 environments = 10k+ rows. Query optimization needed (indexes, pagination).

---

## Git ↔ Environment Reconciliation

### Git Sync

**Service**: `services/canonical_repo_sync_service.py`

**Purpose**: Sync workflows FROM Git TO canonical_workflows table

**API**: `POST /api/v1/canonical/sync-repo`

**Steps**:
1. Clone/pull Git repository
2. Scan for workflow JSON files
3. For each file:
   - Compute content hash
   - Upsert canonical_workflow record
   - Update `git_content_hash` in workflow_env_map

**Conflict Handling**: If Git commit creates conflict, sync fails (no automatic resolution)

**Test**: Unknown

### Environment Sync

**Service**: `services/canonical_env_sync_service.py:sync_environment()`

**Purpose**: Sync workflows FROM n8n environment TO workflow_env_map

**API**: `POST /api/v1/environments/{id}/sync` (workflows sync includes canonical logic)

**Steps**:
1. Fetch all workflows from n8n API
2. For each workflow:
   - Check if `workflow_env_map` record exists
   - If yes: Update `env_content_hash`, `n8n_updated_at`, status
   - If no: Create new record with `status = UNTRACKED`
3. Mark workflows not seen as `status = MISSING`

**Batch Size**: 25-30 workflows per batch (hardcoded)

**Test**: Unknown

### Reconciliation

**Service**: `services/canonical_reconciliation_service.py`

**Purpose**: Resolve conflicts between Git and environment

**API**: `POST /api/v1/canonical/reconcile`

**Strategies** (unclear from code):
- Force overwrite environment with Git
- Force overwrite Git with environment
- Manual resolution (user chooses)

**Test**: Unknown

**Gap**: Reconciliation strategy documentation incomplete

---

## Content Hash Tracking

### Hash Algorithm
**Assumption**: Likely SHA256 (not explicitly stated in code reviewed)

**Computation**:
1. Normalize workflow JSON (exclude metadata fields)
2. Sort keys for consistency
3. Compute hash: `hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()`

**Normalization** (from `promotion_service.py:normalize_workflow_for_comparison()`):
- Exclude: `id`, `createdAt`, `updatedAt`, `versionId`, `tags`, `active`, node `position`
- Credentials: Compare by name only (ID differs per env)

### Hash Storage

- **git_content_hash**: Hash of workflow as it exists in Git
- **env_content_hash**: Hash of workflow as it exists in environment

### Hash Comparison

**Drift Detection**: `env_content_hash != git_content_hash` → Drift

**Risk**: Hash collision (SHA256 collision is theoretically possible but practically negligible)

---

## Scheduled Sync

**File**: `services/canonical_sync_scheduler.py`

**Schedulers**:
1. **Git Sync Scheduler**: Periodically sync Git → canonical_workflows
2. **Environment Sync Scheduler**: Periodically sync environments → workflow_env_map

**Schedule**: Configurable per tenant/environment (default: hourly)

**Startup**: `main.py:startup_event()` calls `start_canonical_sync_schedulers()`

**Shutdown**: `main.py:shutdown_event()` calls `stop_canonical_sync_schedulers()`

**Risk**: Scheduler impact on DB load with many tenants/environments

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/canonical/workflows` | List canonical workflows |
| GET | `/canonical/workflows/{id}` | Get canonical workflow |
| POST | `/canonical/sync-repo` | Sync Git → canonical |
| POST | `/canonical/sync-environment/{id}` | Sync environment → map |
| POST | `/canonical/reconcile` | Reconcile conflicts |
| GET | `/canonical/untracked` | List untracked workflows |
| POST | `/canonical/link` | Link untracked to canonical |
| GET | `/canonical/onboard/preflight` | Preflight checks |
| POST | `/canonical/onboard/inventory` | Start onboarding |
| GET | `/canonical/onboard/completion` | Check completion |
| GET | `/workflows/matrix` | Cross-environment matrix view |

---

## Tests

| Test File | Coverage |
|-----------|----------|
| `test_canonical_onboarding_integrity.py` | Onboarding flow, idempotency, constraints |
| `test_untracked_workflows_service.py` | Untracked detection |

**Gaps**: No tests for Git sync, environment sync, reconciliation, matrix view performance

---

## Risk Areas

### High Risk

1. **Canonical ID Generation Collision**: Slug generation based on workflow name. If two workflows have same name, collision possible. Need collision detection + resolution.

2. **Matrix Performance**: With 1000+ workflows, query performance untested. Need indexes on `(canonical_id, environment_id)`.

3. **Git Conflict Handling**: Git sync fails on conflict. No automatic resolution or user-facing conflict UI.

### Medium Risk

1. **Content Hash Algorithm**: Not documented. If algorithm changes, all hashes invalidate.

2. **Batch Size Hardcoded**: 25-30 workflows per batch not configurable. May be too small for large syncs or too large for slow networks.

3. **Reconciliation Strategy**: Strategy unclear. Force overwrite could lose data.

### Low Risk

1. **Scheduled Sync Load**: Hourly sync for many tenants may cause DB load spikes.

2. **Status Precedence Complexity**: 5 states with precedence rules. Edge cases possible.

---

## Gaps & Missing Features

### Not Implemented

1. **Migration PR Creation**: PR creation logic stub exists but not fully implemented.

2. **Configurable Batch Size**: Batch size hardcoded (25-30).

3. **Git Conflict Resolution UI**: No user-facing UI to resolve conflicts.

4. **Multi-Workflow Bulk Link**: Can link one untracked at a time. No bulk link.

5. **Canonical Workflow Templates**: No template system for common workflows.

### Unclear Behavior

1. **Canonical ID Generation**: Collision detection/resolution unclear.

2. **Reconciliation Force Overwrite**: Data loss risk if wrong strategy chosen.

3. **Sync Idempotency**: Can sync be safely retried mid-execution?

---

## Recommendations

### Must Fix Before MVP Launch

1. Document content hash algorithm explicitly
2. Test matrix view performance with 1000+ workflows
3. Add canonical ID collision detection
4. Test Git sync conflict scenarios

### Should Fix Post-MVP

1. Implement Git conflict resolution UI
2. Make batch size configurable
3. Add multi-workflow bulk link
4. Optimize matrix query with indexes/pagination

### Nice to Have

1. Canonical workflow templates
2. Drift trend analysis per canonical workflow
3. Auto-linking by content hash (not just name)
4. Canonical workflow versioning (multiple versions of same canonical)

