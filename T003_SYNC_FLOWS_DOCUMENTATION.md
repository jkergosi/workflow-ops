# T003: Sync Flows Documentation

**Task ID:** T003
**Description:** Trace sync flows (runtime→DB, runtime→Git, Git→DB)
**Primary File:** `app/services/canonical_env_sync_service.py`
**Date:** 2026-01-14

---

## Executive Summary

The WorkflowOps system implements three primary sync flows to maintain consistency between n8n runtime environments, the database, and Git repositories:

1. **Runtime → DB** (Environment Sync): n8n workflows synced to database mappings
2. **Git → DB** (Repository Sync): Git workflow files synced to canonical workflow records
3. **DB → DB** (Reconciliation): Diff computation between environments after syncs

Each sync flow is orchestrated by dedicated services, supports batching and checkpointing for resilience, and triggers reconciliation to update cross-environment diff states.

---

## 1. Sync Flow Overview

### 1.1 Three-Way Sync Architecture

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│             │         │             │         │             │
│  n8n Runtime│◄────────│  Database   │────────►│     Git     │
│ (environments)        │  (PostgreSQL)         │ (Repository) │
│             │         │             │         │             │
└─────────────┘         └─────────────┘         └─────────────┘
       │                       │                       │
       │                       │                       │
       ▼                       ▼                       ▼
 Env Sync Service      Reconciliation      Repo Sync Service
 (runtime → DB)         (DB → DB)           (Git → DB)
```

### 1.2 Sync Coordination

**Orchestrator Service**: `app/services/sync_orchestrator_service.py`
- Single entry point for manual sync requests
- Enforces idempotency (returns existing job if already running)
- Prevents duplicate sync jobs via DB constraints
- Always advances `last_sync_attempted_at` timestamp

**Scheduler Service**: `app/services/canonical_sync_scheduler.py`
- **Default State**: DISABLED (MVP design)
- Enable via: `SYNC_SCHEDULER_ENABLED=true`
- Repo Sync Interval: 30 minutes
- Env Sync Interval: 30 minutes
- Debounce: 60 seconds per environment

---

## 2. Runtime → DB Sync (Environment Sync)

### 2.1 Service Architecture

**File**: `app/services/canonical_env_sync_service.py`

**Entry Point**: `CanonicalEnvSyncService.sync_environment()`

**Trigger Points**:
- Manual sync request: `POST /api/v1/environments/{id}/sync`
- Scheduled sync (if enabled): Every 30 minutes
- Orchestrator service: `sync_orchestrator.request_sync()`

### 2.2 Greenfield Sync Model

The system applies different sync behavior based on environment class:

| Environment Class | Sync Behavior | workflow_data Storage | Purpose |
|-------------------|---------------|----------------------|---------|
| **DEV** | Full sync | ✅ Stored | DEV is source of truth for new workflows |
| **Non-DEV** (Staging, Prod) | Observational sync | ❌ Not stored | Git is source of truth |

**Implementation** (Lines 228-238):
```python
env_class = environment.get("environment_class", "dev").lower()
is_dev = env_class == "dev"

# DEV: workflow_data is provided - full update
# Non-DEV: workflow_data is None - only update env_content_hash
workflow_data=workflow if is_dev else None
```

### 2.3 Sync Flow Steps

#### Phase 1: Discovery (Lines 133-152)
```
1. Emit SSE progress: "discovering_workflows"
2. Call adapter.get_workflows() → Get all workflow summaries from n8n
3. Count total_workflows
4. Emit SSE progress: "updating_environment_state"
```

#### Phase 2: Batched Processing (Lines 179-286)

**Batch Size**: 25 workflows per batch (Line 24: `BATCH_SIZE = 25`)

**Per Batch**:
```python
for batch_start in range(start_index, total_workflows, BATCH_SIZE):
    1. Fetch full workflow data for batch (Lines 186-194)
    2. Process batch with _process_workflow_batch() (Lines 233-238)
    3. Update job progress + emit SSE event (Lines 198-225)
    4. Checkpoint after batch (Lines 251-268)
```

**Checkpoint Data Structure** (Lines 252-256):
```json
{
  "last_processed_index": 50,
  "last_batch_end": 50,
  "total_workflows": 100
}
```

#### Phase 3: Mark Missing Workflows (Lines 288-294)

Workflows that existed in previous syncs but no longer exist in n8n are marked as `MISSING`.

**Implementation**:
```python
n8n_workflow_ids = {w.get("id") for w in n8n_workflow_summaries}
missing_count = await _mark_missing_workflows_missing(
    tenant_id, environment_id, n8n_workflow_ids
)
```

### 2.4 Workflow Processing Logic

**Function**: `_process_workflow_batch()` (Lines 312-471)

#### Short-Circuit Optimization (Lines 368-376)

**Purpose**: Skip processing if workflow unchanged since last sync

**Conditions**:
```python
if existing_status != "missing" and existing_n8n_updated_at and n8n_updated_at:
    if _normalize_timestamp(existing_n8n_updated_at) == _normalize_timestamp(n8n_updated_at):
        # Workflow unchanged - skip processing
        batch_results["skipped"] += 1
        continue
```

**Result**: Avoids expensive hash computation and DB writes for unchanged workflows

#### Hash Computation (Lines 378-384)

**Function**: `compute_workflow_hash()` from `canonical_workflow_service.py`

**Process**:
1. Normalize workflow payload via `normalize_workflow_for_comparison()`
2. Sort JSON keys for deterministic hashing
3. Compute SHA256 hash
4. Check for hash collisions in registry
5. Apply fallback strategy if collision detected

**Collision Detection** (Lines 381-384):
```python
collision = _detect_hash_collision(workflow, content_hash, existing_canonical_id)
if collision:
    batch_results["collision_warnings"].append(collision)
```

#### Auto-Link Logic (Lines 424-434)

**Function**: `_try_auto_link_by_hash()` (Lines 495-554)

**Conditions for Auto-Link**:
1. ✅ Hash matches exactly with Git state
2. ✅ Match is unique (one canonical workflow with this hash)
3. ✅ Canonical ID not already linked to different n8n workflow in same environment

**Query** (Lines 513-519):
```python
git_state_response = (
    db_service.client.table("canonical_workflow_git_state")
    .select("canonical_id")
    .eq("tenant_id", tenant_id)
    .eq("environment_id", environment_id)
    .eq("git_content_hash", content_hash)
    .execute()
)
```

#### Mapping Creation (Lines 439-465)

**Linked Workflow** (Lines 439-450):
```python
await _create_workflow_mapping(
    tenant_id=tenant_id,
    environment_id=environment_id,
    canonical_id=canonical_id,  # NOT NULL
    n8n_workflow_id=n8n_workflow_id,
    content_hash=content_hash,
    status=WorkflowMappingStatus.LINKED,
    workflow_data=workflow if is_dev else None,
    n8n_updated_at=n8n_updated_at
)
```

**Untracked Workflow** (Lines 452-465):
```python
await _create_untracked_mapping(
    tenant_id=tenant_id,
    environment_id=environment_id,
    n8n_workflow_id=n8n_workflow_id,
    canonical_id=None,  # NULL for untracked
    content_hash=content_hash,
    status=WorkflowMappingStatus.UNTRACKED,
    workflow_data=workflow if is_dev else None,
    n8n_updated_at=n8n_updated_at
)
```

### 2.5 Transaction Safety

**Design Principle**: Each workflow is an independent transaction unit

**Error Isolation** (Lines 466-469):
```python
except Exception as e:
    error_msg = f"Error processing workflow {workflow.get('id', 'unknown')}: {str(e)}"
    logger.error(error_msg)
    batch_results["errors"].append(error_msg)
    # Continue processing other workflows
```

**Idempotency** (Lines 619-626):
- Uses `upsert` with unique constraint on `(tenant_id, environment_id, n8n_workflow_id)`
- Duplicate creations are safely handled
- Logs warnings if mapping already exists (indicates logic bug)

### 2.6 Missing Workflow Handling

**Function**: `_mark_missing_workflows_missing()` (Lines 726-785)

**Logic**:
```python
for mapping in (response.data or []):
    n8n_id = mapping.get("n8n_workflow_id")
    if n8n_id and n8n_id not in existing_n8n_ids:
        # Workflow no longer exists in n8n - mark as missing
        update({
            "status": WorkflowMappingStatus.MISSING.value,
            "last_env_sync_at": datetime.utcnow().isoformat()
        })
```

**Preservation**: `n8n_workflow_id` is preserved for history/audit

**Transition Back**: If missing workflow reappears (Lines 388-393):
```python
if existing_status == "missing":
    # Workflow reappeared - transition based on canonical_id
    if existing_canonical_id:
        new_status = WorkflowMappingStatus.LINKED
    else:
        new_status = WorkflowMappingStatus.UNTRACKED
```

---

## 3. Git → DB Sync (Repository Sync)

### 3.1 Service Architecture

**File**: `app/services/canonical_repo_sync_service.py`

**Entry Point**: `CanonicalRepoSyncService.sync_repository()`

**Trigger Points**:
- Manual repo sync request
- Scheduled sync (if enabled): Every 30 minutes
- After Git push/merge (webhook, not implemented)

### 3.2 Sync Flow Steps

#### Step 1: GitHub Service Initialization (Lines 107-126)

**Extract Repo Info**:
```python
repo_url = git_repo_url.rstrip('/').replace('.git', '')
repo_parts = repo_url.split("/")
github_service = GitHubService(
    token=git_pat,
    repo_owner=repo_parts[-2],
    repo_name=repo_parts[-1],
    branch=git_branch
)
```

#### Step 2: Fetch Workflow Files from Git (Lines 139-153)

**Method**: `github_service.get_all_workflow_files_from_github()`

**Returns**: `Dict[file_path, workflow_data]`

**File Path Format**: `workflows/{git_folder}/{canonical_id}.json`

**Commit SHA Handling**:
```python
if not commit_sha:
    branch = github_service.repo.get_branch(git_branch)
    commit_sha = branch.commit.sha
```

#### Step 3: Process Each Workflow File (Lines 156-229)

**Per File**:
```python
for file_path, workflow_data in workflow_files.items():
    1. Extract canonical_id from filename (Line 160)
    2. Compute content_hash (Line 163)
    3. Detect hash collisions (Lines 166-168)
    4. Check if git_content_hash changed (skip-if-unchanged optimization) (Lines 171-177)
    5. Get or create canonical_workflow record (Lines 180-194)
    6. Upsert Git state (Lines 197-204)
    7. Ingest sidecar file if exists (Lines 209-224)
```

### 3.3 Skip-If-Unchanged Optimization (Lines 171-177)

**Purpose**: Avoid expensive DB writes for unchanged Git content

**Logic**:
```python
existing_git_state = await CanonicalWorkflowService.get_canonical_workflow_git_state(
    tenant_id, environment_id, canonical_id
)
if existing_git_state and existing_git_state.get("git_content_hash") == content_hash:
    # Git content unchanged - skip processing
    results["workflows_unchanged"] += 1
    continue
```

### 3.4 Canonical Workflow Git State (Lines 197-204)

**Function**: `CanonicalWorkflowService.upsert_canonical_workflow_git_state()`

**Table**: `canonical_workflow_git_state`

**Upsert Data**:
```python
{
    "tenant_id": tenant_id,
    "environment_id": environment_id,
    "canonical_id": canonical_id,
    "git_path": file_path,
    "git_content_hash": content_hash,
    "git_commit_sha": commit_sha,
    "last_repo_sync_at": datetime.utcnow().isoformat()
}
```

### 3.5 Sidecar File Ingestion (Lines 209-299)

**File Format**: `{workflow_name}.env-map.json`

**Purpose**: Store environment-specific mappings for workflows

**Schema**:
```json
{
  "canonical_workflow_id": "uuid",
  "workflow_name": "...",
  "environments": {
    "env_uuid_1": {
      "environment_type": "prod",
      "n8n_workflow_id": "203",
      "content_hash": "sha256:...",
      "last_seen_at": "..."
    }
  }
}
```

**Processing** (Lines 273-298):
```python
for env_id, env_data in environments.items():
    mapping_data = {
        "tenant_id": tenant_id,
        "environment_id": env_id,
        "canonical_id": canonical_id,
        "n8n_workflow_id": n8n_workflow_id,
        "env_content_hash": content_hash,
        "status": "linked"  # Sidecar implies linked
    }

    db_service.client.table("workflow_env_map").upsert(
        mapping_data,
        on_conflict="tenant_id,environment_id,n8n_workflow_id"
    ).execute()
```

### 3.6 Transaction Safety

**Error Isolation** (Lines 226-229):
```python
except Exception as e:
    error_msg = f"Error processing workflow file {file_path}: {str(e)}"
    logger.error(error_msg)
    results["errors"].append(error_msg)
    # Continue processing other files
```

**Idempotency**: Uses `upsert` for all DB operations

---

## 4. DB → DB Reconciliation (Diff Computation)

### 4.1 Service Architecture

**File**: `app/services/canonical_reconciliation_service.py`

**Entry Point**: `CanonicalReconciliationService.reconcile_environment_pair()`

**Purpose**: Compute diffs between source and target environments after sync operations

### 4.2 Trigger Points

**After Environment Sync** (`canonical_sync_scheduler.py` Lines 195-201):
```python
await CanonicalReconciliationService.reconcile_all_pairs_for_environment(
    tenant_id=tenant_id,
    changed_env_id=environment_id
)
```

**After Repository Sync** (`canonical_sync_scheduler.py` Lines 97-100):
```python
await CanonicalReconciliationService.reconcile_all_pairs_for_environment(
    tenant_id=tenant_id,
    changed_env_id=environment_id
)
```

### 4.3 Debounce Mechanism (Lines 44-57)

**Purpose**: Reduce reconciliation overhead by batching multiple changes

**Debounce Window**: 60 seconds (Line 14: `RECONCILIATION_DEBOUNCE_SECONDS = 60`)

**Logic**:
```python
debounce_key = f"{tenant_id}:{source_env_id}:{target_env_id}"

if not force:
    now = datetime.utcnow()
    if debounce_key in _pending_reconciliations:
        last_request = _pending_reconciliations[debounce_key]
        if (now - last_request).total_seconds() < RECONCILIATION_DEBOUNCE_SECONDS:
            # Still in debounce window - skip
            return {"skipped": True, "reason": "debounced"}
```

### 4.4 Incremental Recomputation (Lines 93-120)

**Purpose**: Only recompute diffs when inputs change

**Check Logic**:
```python
existing_diff = await _get_existing_diff(tenant_id, source_env_id, target_env_id, canonical_id)

if existing_diff:
    source_hash_changed = (
        source_git_state and
        existing_diff.get("source_git_hash") != source_git_state.get("git_content_hash")
    )
    target_hash_changed = (
        target_git_state and
        existing_diff.get("target_git_hash") != target_git_state.get("git_content_hash")
    )
    source_env_hash_changed = (
        source_mapping and
        existing_diff.get("source_env_hash") != source_mapping.get("env_content_hash")
    )
    target_env_hash_changed = (
        target_mapping and
        existing_diff.get("target_env_hash") != target_mapping.get("env_content_hash")
    )

    if not any([source_hash_changed, target_hash_changed, source_env_hash_changed, target_env_hash_changed]):
        # No changes - skip recomputation
        results["diffs_unchanged"] += 1
        continue
```

### 4.5 Diff Status Computation

**Function**: `_compute_diff_status()` (Lines 184-256)

**Inputs**:
- `source_git_state`: Git content hash for source environment
- `target_git_state`: Git content hash for target environment
- `source_mapping`: Environment content hash for source
- `target_mapping`: Environment content hash for target

**Status Logic**:

| Condition | Status | Description |
|-----------|--------|-------------|
| `source_git_hash == target_git_hash` | `UNCHANGED` | Both environments have same Git version |
| `!source_git_state && target_git_state` | `TARGET_ONLY` | Workflow only exists in target Git |
| `source_git_state && !target_git_state` | `ADDED` | Workflow only exists in source Git |
| `source_env_hash != source_git_hash && target_git_hash != source_git_hash` | `CONFLICT` | Both source env and target Git modified independently |
| `source_git_hash == target_env_hash && target_git_hash != source_git_hash` | `TARGET_HOTFIX` | Target was modified in Git (hotfix scenario) |
| `source_git_hash != target_git_hash` (no conflict) | `MODIFIED` | Source is newer than target |

#### Conflict Detection (Lines 229-247)

**Definition**: A conflict occurs when BOTH sides have independent modifications

**Logic**:
```python
source_has_local_changes = (
    source_env_hash is not None and
    source_env_hash != source_git_hash
)
target_git_has_changes = target_git_hash != source_git_hash

if source_has_local_changes and target_git_has_changes:
    # Both source environment and target Git have been modified independently
    # Check if target env also differs from target Git (additional complexity)
    target_has_local_changes = (
        target_env_hash is not None and
        target_env_hash != target_git_hash
    )

    # This is a conflict: source env modified, target Git modified
    return WorkflowDiffStatus.CONFLICT
```

### 4.6 Conflict Metadata (Lines 259-316)

**Purpose**: Capture state of all four sources for conflict resolution

**Structure**:
```json
{
  "conflict_detected_at": "2026-01-14T10:00:00Z",
  "source_git_hash": "abc123...",
  "target_git_hash": "def456...",
  "source_env_hash": "ghi789...",
  "target_env_hash": "jkl012...",
  "conflict_type": "divergent_changes",
  "description": "Source environment and target Git have independent modifications",
  "source_git_updated_at": "...",
  "target_git_updated_at": "...",
  "source_env_updated_at": "...",
  "target_env_updated_at": "..."
}
```

### 4.7 Diff State Persistence (Lines 379-433)

**Table**: `workflow_diff_state`

**Upsert Data**:
```python
diff_data = {
    "tenant_id": tenant_id,
    "source_env_id": source_env_id,
    "target_env_id": target_env_id,
    "canonical_id": canonical_id,
    "diff_status": diff_status.value,
    "computed_at": datetime.utcnow().isoformat(),
    "source_git_hash": source_git_hash,
    "target_git_hash": target_git_hash,
    "source_env_hash": source_env_hash,
    "target_env_hash": target_env_hash,
    "conflict_metadata": conflict_metadata  # Only for CONFLICT status
}

db_service.client.table("workflow_diff_state").upsert(
    diff_data,
    on_conflict="tenant_id,source_env_id,target_env_id,canonical_id"
).execute()
```

### 4.8 Reconcile All Pairs (Lines 475-527)

**Function**: `reconcile_all_pairs_for_environment()`

**Purpose**: Recompute diffs for all environment pairs involving the changed environment

**Logic**:
```python
environments = await db_service.get_environments(tenant_id)
env_ids = [env["id"] for env in environments]
other_env_ids = [env_id for env_id in env_ids if env_id != changed_env_id]

for env_id in other_env_ids:
    # Reconcile source -> target
    await reconcile_environment_pair(tenant_id, changed_env_id, env_id)

    # Reconcile target -> source (reverse direction)
    await reconcile_environment_pair(tenant_id, env_id, changed_env_id)
```

---

## 5. Sync Orchestration

### 5.1 Unified Orchestrator Service

**File**: `app/services/sync_orchestrator_service.py`

**Design Principle**: Single entry point for all sync operations

### 5.2 Idempotent Sync Requests (Lines 83-164)

**Function**: `request_sync()`

**Idempotency Logic**:
```python
# 1. Check for existing active job
existing_job = await get_active_sync_job(tenant_id, environment_id)
if existing_job:
    return existing_job, False  # is_new_job = False

# 2. Always update last_sync_attempted_at BEFORE job creation
await _update_sync_attempted_timestamp(environment_id, tenant_id)

# 3. Attempt atomic job creation
try:
    job = await _create_sync_job_atomic(...)
    if job:
        return job, True  # is_new_job = True
    else:
        # Race condition: another job created between check and insert
        existing_job = await get_active_sync_job(...)
        return existing_job, False
except Exception as e:
    if "duplicate" in str(e).lower() or "constraint" in str(e).lower():
        # Duplicate key error - fetch and return existing job
        existing_job = await get_active_sync_job(...)
        return existing_job, False
    raise
```

### 5.3 Active Job Detection (Lines 43-80)

**Function**: `get_active_sync_job()`

**Query Logic**:
```python
# Check for pending jobs
pending_jobs = await background_job_service.get_jobs(
    tenant_id=tenant_id,
    resource_type="environment",
    resource_id=environment_id,
    job_type=SYNC_JOB_TYPE,
    status=BackgroundJobStatus.PENDING,
    limit=1
)
if pending_jobs:
    return pending_jobs[0]

# Check for running jobs
running_jobs = await background_job_service.get_jobs(
    tenant_id=tenant_id,
    resource_type="environment",
    resource_id=environment_id,
    job_type=SYNC_JOB_TYPE,
    status=BackgroundJobStatus.RUNNING,
    limit=1
)
if running_jobs:
    return running_jobs[0]

return None
```

### 5.4 Sync Completion (Lines 229-259)

**Function**: `complete_sync()`

**Updates**:
```python
# 1. Update environment timestamps
await db_service.update_environment(
    environment_id,
    tenant_id,
    {
        "last_connected": now,
        "last_sync_at": now
    }
)

# 2. Complete the job
await background_job_service.complete_job(
    job_id=job_id,
    result=result or {}
)
```

### 5.5 Sync Failure Handling (Lines 262-290)

**Function**: `fail_sync()`

**Still Advances Timestamp**:
```python
# Update sync timestamp even on failure to prevent immediate retry
await db_service.update_environment(
    environment_id,
    tenant_id,
    {"last_sync_at": now}
)

# Fail the job
await background_job_service.fail_job(
    job_id=job_id,
    error_message=error_message,
    error_details=error_details
)
```

---

## 6. Scheduler Architecture

### 6.1 Scheduler Configuration

**File**: `app/services/canonical_sync_scheduler.py`

**Default State**: DISABLED (MVP design)

**Enable Via**: `settings.SYNC_SCHEDULER_ENABLED = true`

**Intervals**:
- Repo Sync: 30 minutes (Line 35: `REPO_SYNC_INTERVAL = 30 * 60`)
- Env Sync: 30 minutes (Line 36: `ENV_SYNC_INTERVAL = 30 * 60`)

**Debounce**: 60 seconds (Line 41: `SYNC_DEBOUNCE_SECONDS = 60`)

### 6.2 Repository Sync Scheduler (Lines 44-131)

**Function**: `_process_repo_sync_scheduler()`

**Loop Logic**:
```python
while _repo_sync_scheduler_running:
    # Get all environments with Git configured
    all_environments = db_service.client.table("environments").select("*").execute()

    for env in all_environments.data:
        if not env.get("git_repo_url") or not env.get("git_folder"):
            continue

        # Check debounce
        if debounce_key in _repo_sync_in_progress:
            last_attempt = _repo_sync_in_progress[debounce_key]
            if (now - last_attempt).total_seconds() < SYNC_DEBOUNCE_SECONDS:
                continue

        # Check last sync time
        last_sync = await _get_last_repo_sync_time(tenant_id, environment_id)

        # Sync if last sync was more than REPO_SYNC_INTERVAL ago
        if not last_sync or (now - last_sync).total_seconds() > REPO_SYNC_INTERVAL:
            # Create background job
            job = await background_job_service.create_job(...)

            # Run sync
            repo_sync_result = await CanonicalRepoSyncService.sync_repository(...)

            # Trigger reconciliation
            await CanonicalReconciliationService.reconcile_all_pairs_for_environment(...)

            # Complete job
            await background_job_service.complete_job(job["id"], result=repo_sync_result)

    # Wait before next cycle
    await asyncio.sleep(REPO_SYNC_INTERVAL)
```

### 6.3 Environment Sync Scheduler (Lines 133-232)

**Function**: `_process_env_sync_scheduler()`

**Loop Logic**:
```python
while _env_sync_scheduler_running:
    # Get all environments
    all_environments = db_service.client.table("environments").select("*").execute()

    for env in all_environments.data:
        # Check debounce
        if debounce_key in _env_sync_in_progress:
            last_attempt = _env_sync_in_progress[debounce_key]
            if (now - last_attempt).total_seconds() < SYNC_DEBOUNCE_SECONDS:
                continue

        # Check last sync time from environment record
        last_sync = await _get_last_env_sync_time(tenant_id, environment_id)

        # Sync if last sync was more than ENV_SYNC_INTERVAL ago
        if not last_sync or (now - last_sync).total_seconds() > ENV_SYNC_INTERVAL:
            # Create background job
            job = await background_job_service.create_job(...)

            # Run sync with SSE support
            sync_result = await CanonicalEnvSyncService.sync_environment(
                tenant_id=tenant_id,
                environment_id=environment_id,
                environment=env,
                job_id=job["id"],
                tenant_id_for_sse=tenant_id  # Enable SSE events
            )

            # Update last_sync_at
            await db_service.update_environment(
                environment_id, tenant_id,
                {"last_sync_at": datetime.utcnow().isoformat()}
            )

            # Trigger reconciliation
            await CanonicalReconciliationService.reconcile_all_pairs_for_environment(...)

            # Complete job
            await background_job_service.complete_job(job["id"], result=sync_result)

    # Wait before next cycle
    await asyncio.sleep(ENV_SYNC_INTERVAL)
```

### 6.4 Last Sync Timestamp Queries

**Repository Sync** (Lines 234-253):
```python
async def _get_last_repo_sync_time(tenant_id: str, environment_id: str) -> datetime | None:
    response = (
        db_service.client.table("canonical_workflow_git_state")
        .select("last_repo_sync_at")
        .eq("tenant_id", tenant_id)
        .eq("environment_id", environment_id)
        .order("last_repo_sync_at", desc=True)
        .limit(1)
        .execute()
    )

    if response.data and response.data[0].get("last_repo_sync_at"):
        return datetime.fromisoformat(response.data[0]["last_repo_sync_at"].replace("Z", "+00:00"))

    return None
```

**Environment Sync** (Lines 256-280):
```python
async def _get_last_env_sync_time(tenant_id: str, environment_id: str) -> datetime | None:
    # Uses environment-level last_sync_at timestamp
    response = (
        db_service.client.table("environments")
        .select("last_sync_at")
        .eq("tenant_id", tenant_id)
        .eq("id", environment_id)
        .single()
        .execute()
    )

    if response.data and response.data.get("last_sync_at"):
        return datetime.fromisoformat(response.data["last_sync_at"].replace("Z", "+00:00"))

    return None
```

---

## 7. Hash Collision Handling

### 7.1 Collision Registry

**File**: `app/services/canonical_workflow_service.py`

**Global Registry**: `_hash_collision_registry: Dict[str, Dict[str, Any]]` (Line 20)

**Purpose**: Track hash→payload mappings for collision detection

### 7.2 Collision Detection Logic (Lines 75-150)

**Function**: `compute_workflow_hash()`

**Process**:
```python
1. Normalize workflow: normalized = normalize_workflow_for_comparison(workflow)
2. Hash: content_hash = hashlib.sha256(json_str.encode()).hexdigest()
3. Check registry: registered_payload = get_registered_payload(content_hash)
4. If registered_payload exists and registered_payload != normalized:
   # COLLISION DETECTED
   if canonical_id:
       # Apply fallback: append canonical_id and rehash
       fallback_content = {**normalized, "__canonical_id__": canonical_id}
       fallback_hash = hashlib.sha256(fallback_json_str.encode()).hexdigest()
       register_workflow_hash(fallback_hash, fallback_content)
       return fallback_hash
   else:
       # No canonical_id - return colliding hash (unresolved)
       return content_hash
```

### 7.3 Collision Warning Tracking

**Environment Sync** (`canonical_env_sync_service.py` Lines 129, 382-384, 419-421):
```python
results["collision_warnings"] = []  # Initialize

# During processing
collision = _detect_hash_collision(workflow, content_hash, existing_canonical_id)
if collision:
    batch_results["collision_warnings"].append(collision)
```

**Repository Sync** (`canonical_repo_sync_service.py` Lines 135, 166-168):
```python
results["collision_warnings"] = []  # Initialize

# During processing
collision = _detect_hash_collision(workflow_data, content_hash, canonical_id, file_path)
if collision:
    results["collision_warnings"].append(collision)
```

**Collision Warning Format**:
```json
{
  "n8n_workflow_id": "123",
  "workflow_name": "Customer Onboarding",
  "content_hash": "abc123...",
  "canonical_id": "uuid-or-null",
  "message": "Hash collision detected for workflow 'Customer Onboarding' (ID: 123). Hash 'abc123...' maps to different payloads."
}
```

---

## 8. Database Tables Involved

### 8.1 workflow_env_map

**Purpose**: Maps canonical workflows to environment instances

**Key Columns**:
- `canonical_id` (UUID, nullable): FK to canonical_workflows
- `environment_id` (UUID): FK to environments
- `n8n_workflow_id` (text): Provider-specific ID
- `status` (enum): linked | untracked | missing | ignored | deleted
- `env_content_hash` (text): Hash of workflow in environment
- `n8n_updated_at` (timestamp): Last update from n8n
- `workflow_data` (JSONB): Cached workflow payload (DEV only)
- `last_env_sync_at` (timestamp): Last environment sync time

**Unique Constraints**:
- `(tenant_id, environment_id, n8n_workflow_id)`: One mapping per n8n workflow per environment

**Updated By**:
- Environment Sync: Creates/updates mappings
- Sidecar Ingestion: Creates mappings from Git metadata

### 8.2 canonical_workflow_git_state

**Purpose**: Tracks Git state for canonical workflows per environment

**Key Columns**:
- `canonical_id` (UUID): FK to canonical_workflows
- `environment_id` (UUID): FK to environments
- `git_path` (text): Path in Git repo
- `git_content_hash` (text): Hash of workflow in Git
- `git_commit_sha` (text): Commit SHA
- `last_repo_sync_at` (timestamp): Last repo sync time

**Unique Constraint**:
- `(tenant_id, environment_id, canonical_id)`: One Git state per canonical per environment

**Updated By**:
- Repository Sync: Upserts Git state

### 8.3 workflow_diff_state

**Purpose**: Stores computed diffs between environment pairs

**Key Columns**:
- `tenant_id` (UUID)
- `source_env_id` (UUID): FK to environments
- `target_env_id` (UUID): FK to environments
- `canonical_id` (UUID): FK to canonical_workflows
- `diff_status` (enum): unchanged | modified | added | target_only | conflict | target_hotfix
- `source_git_hash` (text): For incremental recompute
- `target_git_hash` (text): For incremental recompute
- `source_env_hash` (text): For incremental recompute
- `target_env_hash` (text): For incremental recompute
- `conflict_metadata` (JSONB): Conflict details (only for CONFLICT status)
- `computed_at` (timestamp): Last diff computation time

**Unique Constraint**:
- `(tenant_id, source_env_id, target_env_id, canonical_id)`: One diff per pair per canonical

**Updated By**:
- Reconciliation Service: Computes and upserts diffs

### 8.4 environments

**Purpose**: Environment configuration

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID)
- `environment_class` (enum): dev | staging | prod
- `git_repo_url` (text): Git repository URL
- `git_branch` (text): Git branch name
- `git_folder` (text): Folder in Git repo for workflows
- `git_pat` (text): GitHub PAT for access
- `last_sync_at` (timestamp): Last sync timestamp
- `last_connected` (timestamp): Last successful connection

**Updated By**:
- Sync Orchestrator: Updates `last_sync_at` before/after sync
- Environment Sync: Updates `last_connected` on success

### 8.5 background_jobs

**Purpose**: Tracks background sync jobs

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID)
- `job_type` (enum): canonical_env_sync | canonical_repo_sync
- `resource_type` (text): environment
- `resource_id` (UUID): Environment ID
- `status` (enum): pending | running | completed | failed
- `progress` (JSONB): Current progress with checkpoint data
- `result` (JSONB): Final sync result
- `metadata` (JSONB): Job metadata (trigger, etc.)

**Unique Constraint**:
- Partial unique index prevents duplicate active jobs per resource

**Updated By**:
- Sync Orchestrator: Creates jobs
- Sync Services: Update progress and status

---

## 9. Sequence Diagrams

### 9.1 Environment Sync Flow (Runtime → DB)

```
User/Scheduler          Orchestrator           EnvSyncService         Adapter (n8n)        Database
     |                       |                       |                       |                 |
     |-- request_sync() ---->|                       |                       |                 |
     |                       |                       |                       |                 |
     |                       |-- check active job -->|                       |                 |
     |                       |<-- existing/null -----|                       |                 |
     |                       |                       |                       |                 |
     |                       |-- update timestamp -->|                       |                 |
     |                       |                       |                       |         [update environments.last_sync_at]
     |                       |                       |                       |                 |
     |                       |-- create_job_atomic ->|                       |         [insert background_jobs]
     |                       |<-- job_id ------------|                       |                 |
     |<-- (job_id, true) ----|                       |                       |                 |
     |                       |                       |                       |                 |
     |                       |                       |-- sync_environment -->|                 |
     |                       |                       |                       |                 |
     |                       |                       |  Phase 1: Discovery   |                 |
     |                       |                       |-- get_workflows() --->|                 |
     |                       |                       |<-- [summaries] -------|                 |
     |                       |                       |                       |                 |
     |                       |                       |  Phase 2: Batched Processing            |
     |                       |                       |  (25 workflows/batch) |                 |
     |                       |                       |-- get_workflow(id) -->|                 |
     |                       |                       |<-- full_workflow -----|                 |
     |                       |                       |                       |                 |
     |                       |                       |-- compute_hash ------>|         [check collision]
     |                       |                       |                       |                 |
     |                       |                       |-- try_auto_link ----->|                 |
     |                       |                       |                       |         [query canonical_workflow_git_state]
     |                       |                       |<-- canonical_id ------|                 |
     |                       |                       |                       |                 |
     |                       |                       |-- upsert mapping ---->|         [upsert workflow_env_map]
     |                       |                       |                       |                 |
     |                       |                       |-- checkpoint -------->|         [update background_jobs.progress]
     |                       |                       |                       |                 |
     |                       |                       |  Phase 3: Mark Missing                  |
     |                       |                       |-- mark_missing ------>|         [update workflow_env_map status=missing]
     |                       |                       |                       |                 |
     |                       |                       |<-- sync_result -------|                 |
     |                       |                       |                       |                 |
     |                       |-- complete_sync ----->|                       |                 |
     |                       |                       |                       |         [update environments.last_sync_at]
     |                       |                       |                       |         [update background_jobs status=completed]
     |                       |                       |                       |                 |
     |                       |-- reconcile_all ----->|                       |                 |
     |                       |                       |                       |         [upsert workflow_diff_state]
```

### 9.2 Repository Sync Flow (Git → DB)

```
Scheduler            RepoSyncService        GitHubService         Database
    |                      |                      |                  |
    |-- sync_repository -->|                      |                  |
    |                      |                      |                  |
    |                      |-- init GitHub ------>|                  |
    |                      |<-- configured -------|                  |
    |                      |                      |                  |
    |                      |-- get_all_workflow_files()              |
    |                      |                      |-- API: list files in git_folder
    |                      |                      |-- API: get file content for each .json
    |                      |<-- Dict[path, data] -|                  |
    |                      |                      |                  |
    |                      |  For each file:      |                  |
    |                      |-- extract canonical_id from filename    |
    |                      |-- compute_hash ----->|          [check collision]
    |                      |                      |                  |
    |                      |-- check existing --->|          [query canonical_workflow_git_state]
    |                      |<-- existing_hash ----|                  |
    |                      |                      |                  |
    |                      |  If hash unchanged:  |                  |
    |                      |  [skip processing]   |                  |
    |                      |                      |                  |
    |                      |  If hash changed:    |                  |
    |                      |-- get/create canonical                  |
    |                      |                      |          [upsert canonical_workflows]
    |                      |                      |                  |
    |                      |-- upsert git_state ->|          [upsert canonical_workflow_git_state]
    |                      |                      |                  |
    |                      |-- try ingest sidecar |                  |
    |                      |                      |-- API: get .env-map.json
    |                      |<-- sidecar_data -----|                  |
    |                      |-- ingest_sidecar --->|          [upsert workflow_env_map]
    |                      |                      |                  |
    |<-- sync_result ------|                      |                  |
```

### 9.3 Reconciliation Flow (DB → DB)

```
Sync Service         ReconciliationService       Database
     |                         |                      |
     |-- reconcile_all_pairs ->|                      |
     |                         |                      |
     |                         |-- get environments ->|
     |                         |<-- env_ids ----------|
     |                         |                      |
     |                         |  For each env pair:  |
     |                         |-- check debounce --->|
     |                         |                      |
     |                         |  If not debounced:   |
     |                         |-- get canonical_workflows
     |                         |<-- list -------------|
     |                         |                      |
     |                         |  For each canonical: |
     |                         |-- get source_git --->|
     |                         |<-- source_git_state -|
     |                         |-- get target_git --->|
     |                         |<-- target_git_state -|
     |                         |-- get source_mapping |
     |                         |<-- source_mapping ---|
     |                         |-- get target_mapping |
     |                         |<-- target_mapping ---|
     |                         |                      |
     |                         |-- check existing_diff|
     |                         |<-- existing_diff ----|
     |                         |                      |
     |                         |  If inputs unchanged:|
     |                         |  [skip recomputation]|
     |                         |                      |
     |                         |  If inputs changed:  |
     |                         |-- compute_diff_status|
     |                         |-- build_conflict_metadata (if conflict)
     |                         |-- upsert_diff_state ->
     |                         |                      | [upsert workflow_diff_state]
     |                         |                      |
     |<-- reconcile_result ----|                      |
```

---

## 10. Key Design Principles

### 10.1 Idempotency

**Every Sync Operation Is Idempotent**:
- ✅ Database operations use `upsert` with unique constraints
- ✅ Duplicate job creation is prevented by DB constraints
- ✅ Existing active jobs are returned instead of creating duplicates
- ✅ Short-circuit optimization skips unchanged workflows
- ✅ Checkpointing allows resumable batch processing

### 10.2 Transaction Safety

**Error Isolation**:
- ✅ Each workflow processed independently within try-catch
- ✅ Individual workflow failures don't halt entire sync
- ✅ Per-workflow errors collected and returned for reporting
- ✅ Missing workflow updates isolated with try-catch

**Atomic Operations**:
- ✅ Database upserts provide atomicity per workflow
- ✅ Job creation uses atomic check-and-insert pattern
- ✅ Timestamp updates use single UPDATE query

### 10.3 Performance Optimization

**Short-Circuit Logic**:
- ✅ Skip environment sync if `n8n_updated_at` unchanged
- ✅ Skip repo sync if `git_content_hash` unchanged
- ✅ Skip reconciliation if diff inputs unchanged
- ✅ Debounce reconciliation (60 seconds per env pair)

**Batching**:
- ✅ Environment sync processes 25 workflows per batch
- ✅ Checkpoint after each batch for resumability
- ✅ Progress tracking with SSE for live updates

### 10.4 Greenfield Model

**Environment Class Behavior**:
- ✅ DEV: Full sync (store `workflow_data`)
- ✅ Non-DEV: Observational sync (only hashes)
- ✅ Git is source of truth for non-DEV environments

### 10.5 Reconciliation Design

**Incremental Computation**:
- ✅ Only recompute diffs when inputs change
- ✅ Track hashes for change detection
- ✅ Debounce to reduce overhead

**Conflict Detection**:
- ✅ Detect when both sides have independent modifications
- ✅ Capture conflict metadata for resolution
- ✅ Distinguish between conflicts and hotfixes

---

## 11. File Reference Index

| Service | File Path | Lines | Description |
|---------|-----------|-------|-------------|
| **Environment Sync** | `app/services/canonical_env_sync_service.py` | 1-787 | Runtime → DB sync service |
| - Sync entry point | | 92-309 | `sync_environment()` |
| - Batch processing | | 312-471 | `_process_workflow_batch()` |
| - Auto-link logic | | 495-554 | `_try_auto_link_by_hash()` |
| - Missing workflows | | 727-785 | `_mark_missing_workflows_missing()` |
| **Repository Sync** | `app/services/canonical_repo_sync_service.py` | 1-301 | Git → DB sync service |
| - Sync entry point | | 83-247 | `sync_repository()` |
| - Sidecar ingestion | | 250-299 | `_ingest_sidecar()` |
| **Reconciliation** | `app/services/canonical_reconciliation_service.py` | 1-529 | DB → DB diff computation |
| - Reconcile pair | | 24-181 | `reconcile_environment_pair()` |
| - Diff computation | | 184-256 | `_compute_diff_status()` |
| - Conflict metadata | | 259-316 | `_build_conflict_metadata()` |
| - Reconcile all | | 475-527 | `reconcile_all_pairs_for_environment()` |
| **Orchestrator** | `app/services/sync_orchestrator_service.py` | 1-295 | Unified sync orchestration |
| - Request sync | | 83-164 | `request_sync()` (idempotent) |
| - Active job check | | 43-80 | `get_active_sync_job()` |
| - Complete sync | | 229-259 | `complete_sync()` |
| - Fail sync | | 262-290 | `fail_sync()` |
| **Scheduler** | `app/services/canonical_sync_scheduler.py` | 1-338 | Automated sync scheduling |
| - Repo scheduler | | 44-131 | `_process_repo_sync_scheduler()` |
| - Env scheduler | | 133-232 | `_process_env_sync_scheduler()` |
| - Start schedulers | | 283-308 | `start_canonical_sync_schedulers()` |
| **Workflow Service** | `app/services/canonical_workflow_service.py` | 1-150+ | Hash computation and collision handling |
| - Hash computation | | 75-150 | `compute_workflow_hash()` |
| - Collision registry | | 18-72 | Registry functions |

---

## 12. Conclusion

The WorkflowOps sync system implements a robust three-way sync architecture with the following characteristics:

**Strengths**:
- ✅ **Idempotent**: All sync operations can be safely retried
- ✅ **Resilient**: Batching with checkpointing allows resumable syncs
- ✅ **Optimized**: Short-circuit logic skips unchanged workflows
- ✅ **Isolated**: Per-workflow error handling prevents cascading failures
- ✅ **Conflict-Aware**: Detects and tracks divergent changes
- ✅ **Flexible**: Greenfield model supports different environment classes

**Key Design Decisions**:
- 🔒 Scheduler disabled by default (manual sync preferred for MVP)
- 🔒 DEV stores full workflow data, non-DEV stores only hashes
- 🔒 Auto-linking by hash for seamless canonical workflow association
- 🔒 60-second debounce on reconciliation to reduce overhead
- 🔒 Hash collision detection with deterministic fallback strategy

**Observability**:
- ✅ SSE progress events for live sync status
- ✅ Background job tracking with progress and checkpoints
- ✅ Collision warnings tracked and returned
- ✅ Per-workflow error collection

This architecture provides a solid foundation for maintaining consistency across n8n environments, database state, and Git repositories while supporting future enhancements like webhook-triggered syncs, conflict resolution UI, and advanced reconciliation strategies.

---

**End of T003 Documentation**
