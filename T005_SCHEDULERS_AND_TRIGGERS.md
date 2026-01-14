# T005: Schedulers, Intervals, and Trigger Conditions

**Task:** Map all schedulers, intervals, and trigger conditions
**Primary Files:** `app/services/*_scheduler.py`
**Status:** ✅ Complete

---

## Overview

The WorkflowOps system runs **7 primary schedulers** plus **1 periodic cleanup task** that execute background operations on fixed intervals. All schedulers are started on application startup via `app/main.py` and gracefully stopped on shutdown.

---

## Scheduler Inventory

### 1. Drift Detection Scheduler
**File:** `app/services/drift_scheduler.py`

**Purpose:** Periodically checks for drift between Git and n8n runtime for eligible environments, auto-creates drift incidents when drift is detected.

**Intervals:**
- **Drift Check:** `DRIFT_CHECK_INTERVAL_SECONDS = 300` (5 minutes)
- **TTL Check:** `TTL_CHECK_INTERVAL_SECONDS = 60` (1 minute)
- **Retention Cleanup:** `RETENTION_CLEANUP_INTERVAL_SECONDS = 86400` (24 hours / daily)

**Trigger Conditions:**
- **Drift Detection Loop** (`_process_drift_detection`):
  - Runs every 5 minutes
  - Selection criteria:
    - Environments with `git_repo_url` and `git_pat` NOT NULL
    - Excludes `environment_class = 'dev'` (DEV environments use n8n as source of truth)
    - Tenant must have `drift_detection` feature enabled
  - For each eligible environment:
    - Calls `drift_detection_service.detect_drift()`
    - If drift detected (`with_drift > 0` OR `not_in_git > 0`):
      - Checks if tenant has `drift_incidents` feature enabled
      - Checks for active incident (statuses: `detected`, `acknowledged`, `stabilized`)
      - Checks drift policy for `auto_create_incidents = true`
      - If `auto_create_for_production_only = true`, only creates incident for prod environments
      - Auto-creates drift incident with severity based on affected workflow count:
        - `critical`: ≥10 affected workflows
        - `high`: ≥5 affected workflows
        - `medium`: ≥2 affected workflows
        - `low`: <2 affected workflows
      - Sets TTL based on severity (from drift policy config)

- **TTL Expiration Check** (`_process_ttl_checks`):
  - Runs every 1 minute
  - Queries all active incidents with TTL (`status IN ['detected', 'acknowledged', 'stabilized']` AND `expires_at NOT NULL`)
  - For each incident:
    - If `now >= expires_at`: auto-closes incident (status → `closed`)
    - If `now >= (expires_at - warning_hours)`: sends expiration warning (if not already sent)
  - Warning notification sent based on `expiration_warning_hours` from drift policy (default: 24 hours)

- **Retention Cleanup** (`_process_retention_cleanup`):
  - Runs every 24 hours (daily)
  - Calls `drift_retention_service.cleanup_all_tenants()`
  - Cleans up closed incidents, reconciliation artifacts, and approvals

**Entry Points:**
- `start_all_drift_schedulers()` → starts drift, TTL, and retention schedulers
- `stop_all_drift_schedulers()` → stops all three schedulers

**Startup:** Line 470-472 in `app/main.py`:
```python
from app.services.drift_scheduler import start_all_drift_schedulers
await start_all_drift_schedulers()
```

---

### 2. Canonical Sync Scheduler
**File:** `app/services/canonical_sync_scheduler.py`

**Purpose:** Scheduled safety sync for repository (Git) and environment (n8n) syncs to keep canonical workflow records up-to-date.

**Intervals:**
- **Repo Sync:** `REPO_SYNC_INTERVAL = 30 * 60` (30 minutes)
- **Env Sync:** `ENV_SYNC_INTERVAL = 30 * 60` (30 minutes)
- **Debounce:** `SYNC_DEBOUNCE_SECONDS = 60` (prevents re-triggering same env within 60 seconds)

**Trigger Conditions:**
- **Repository Sync Loop** (`_process_repo_sync_scheduler`):
  - Runs every 30 minutes
  - Selection criteria:
    - All environments with `git_repo_url` and `git_folder` NOT NULL
  - For each environment:
    - Checks debounce (skip if synced within last 60 seconds)
    - Checks last sync time from `canonical_workflow_git_state.last_repo_sync_at`
    - Syncs if `last_sync > REPO_SYNC_INTERVAL` (30 minutes) ago
    - Creates background job (`CANONICAL_REPO_SYNC`)
    - Calls `CanonicalRepoSyncService.sync_repository()`
    - Triggers reconciliation: `CanonicalReconciliationService.reconcile_all_pairs_for_environment()`

- **Environment Sync Loop** (`_process_env_sync_scheduler`):
  - Runs every 30 minutes
  - Selection criteria:
    - All environments (no Git requirement)
  - For each environment:
    - Checks debounce (skip if synced within last 60 seconds)
    - Checks last sync time from `environments.last_sync_at`
    - Syncs if `last_sync > ENV_SYNC_INTERVAL` (30 minutes) ago
    - Creates background job (`CANONICAL_ENV_SYNC`)
    - Calls `CanonicalEnvSyncService.sync_environment()` with SSE support
    - Updates `environments.last_sync_at` on success
    - Triggers reconciliation (with error isolation)

**Feature Flag:**
- **DISABLED BY DEFAULT FOR MVP**
- Must set `SYNC_SCHEDULER_ENABLED=true` in environment to enable
- Config: `app/core/config.py` line 43

**Entry Points:**
- `start_canonical_sync_schedulers()` → starts both repo and env sync schedulers
- `stop_canonical_sync_schedulers()` → stops both schedulers

**Startup:** Line 475-477 in `app/main.py`:
```python
from app.services.canonical_sync_scheduler import start_canonical_sync_schedulers
await start_canonical_sync_schedulers()
```

**Note:** Checks `settings.SYNC_SCHEDULER_ENABLED` before starting (line 294)

---

### 3. Deployment Scheduler
**File:** `app/services/deployment_scheduler.py`

**Purpose:** Polls for scheduled deployments and executes them when their `scheduled_at` time arrives.

**Interval:**
- **Poll Interval:** `30 seconds` (hardcoded in line 216)

**Trigger Conditions:**
- **Scheduled Deployment Loop** (`_process_scheduled_deployments`):
  - Runs every 30 seconds
  - Query: `status = 'scheduled'` AND `scheduled_at NOT NULL` AND `scheduled_at <= now()`
  - For each ready deployment:
    - Validates `scheduled_at` is within 5 seconds of current time (clock skew buffer)
    - Finds matching promotion (`source_environment_id`, `target_environment_id`, `pipeline_id`, `status IN ['pending', 'approved']`)
    - Validates source and target environments exist
    - Validates workflow selections exist
    - **Checks for concurrent promotions** to same target environment (uses `promotion_lock_service`)
      - If blocked: logs warning, leaves as `scheduled` to retry on next poll
      - If available: acquires lock and proceeds
    - Creates background job (`PROMOTION_EXECUTE`)
    - Updates deployment status: `scheduled` → `running`
    - Updates promotion status: `pending/approved` → `running`
    - Executes promotion via `_execute_promotion_background()` in background task
  - On failure: marks deployment as `failed`

**Concurrency Control:**
- Uses `promotion_lock_service.check_and_acquire_promotion_lock()` to prevent race conditions
- Blocks scheduled deployments if another promotion is active on same target environment

**Entry Points:**
- `start_scheduler()` → starts deployment scheduler
- `stop_scheduler()` → stops deployment scheduler

**Startup:** Line 465-467 in `app/main.py`:
```python
from app.services.deployment_scheduler import start_scheduler
await start_scheduler()
```

---

### 4. Rollup Scheduler
**File:** `app/services/rollup_scheduler.py`

**Purpose:** Pre-computes daily execution rollups for faster dashboard performance and refreshes materialized views.

**Intervals:**
- **Rollup Check:** `ROLLUP_INTERVAL_SECONDS = 3600` (1 hour)
- **Backfill Window:** `ROLLUP_DAYS_TO_BACKFILL = 7` (last 7 days on startup)

**Trigger Conditions:**
- **Rollup Scheduler Loop** (`_rollup_scheduler_loop`):
  - On startup:
    - Backfills last 7 days of rollups (`ROLLUP_DAYS_TO_BACKFILL`)
    - Calls `compute_execution_rollup_for_date()` database function
  - Main loop (runs every 1 hour):
    - Computes yesterday's rollups (most important - day is complete)
    - Refreshes materialized views (`refresh_all_materialized_views()`)
    - **During off-peak hours (2-6 AM UTC):**
      - Backfills older dates (2-7 days ago)
      - Small delay (1 second) between computations

- **Materialized View Refresh** (`_refresh_materialized_views`):
  - Calls `refresh_all_materialized_views()` database function
  - Monitors for failures and staleness
  - Emits notification events:
    - `materialized_view.refresh_failed` (per-view failure)
    - `materialized_view.refresh_critical_failure` (system-wide failure)
    - `materialized_view.stale_detected` (view hasn't refreshed recently)
    - `materialized_view.consecutive_failures` (≥3 consecutive failures)

- **Staleness Check** (`_check_stale_materialized_views`):
  - Calls `get_materialized_view_refresh_status()` database function
  - Checks `is_stale`, `last_status`, `minutes_since_last_refresh`, `consecutive_failures`
  - Emits warnings for stale views and consecutive failures

**Entry Points:**
- `start_rollup_scheduler()` → starts rollup scheduler
- `stop_rollup_scheduler()` → stops rollup scheduler

**Startup:** Line 485-487 in `app/main.py`:
```python
from app.services.rollup_scheduler import start_rollup_scheduler
start_rollup_scheduler()
```

---

### 5. Health Check Scheduler
**File:** `app/services/health_check_scheduler.py`

**Purpose:** Periodically pings all active environments to update `last_heartbeat_at` timestamps for health monitoring.

**Interval:**
- **Health Check:** `HEALTH_CHECK_INTERVAL_SECONDS = 60` (1 minute)

**Trigger Conditions:**
- **Health Check Loop** (`_process_health_checks`):
  - Runs every 1 minute
  - Query: `is_active = true`
  - For each active environment:
    - Calls `observability_service.check_environment_health()`
    - Updates `last_heartbeat_at` on success
    - Logs latency and status
  - On failure: logs warning (non-fatal)

**Entry Points:**
- `start_health_check_scheduler()` → starts health check scheduler
- `stop_health_check_scheduler()` → stops health check scheduler

**Startup:** Line 480-482 in `app/main.py`:
```python
from app.services.health_check_scheduler import start_health_check_scheduler
await start_health_check_scheduler()
```

---

### 6. Retention Enforcement Scheduler
**File:** `app/services/background_jobs/retention_job.py`

**Purpose:** Enforces plan-based retention policies for executions and audit logs across all tenants.

**Intervals:**
- **Check Interval:** `RETENTION_CHECK_INTERVAL_SECONDS = 3600` (1 hour)
- **Job Schedule:** Daily at **2 AM UTC** (off-peak hours)
  - `RETENTION_JOB_HOUR_UTC = 2`
  - `RETENTION_JOB_MINUTE_UTC = 0`

**Trigger Conditions:**
- **Retention Scheduler Loop** (runs every 1 hour):
  - Checks if current time matches schedule (2:00 AM UTC)
  - If match: calls `retention_enforcement_service.enforce_all_tenants_retention()`
  - For each tenant:
    - Gets subscription plan retention limits
    - Deletes executions older than retention period
    - Deletes audit logs older than retention period
    - Logs summary metrics

**Config:**
- `EXECUTION_RETENTION_ENABLED`: `bool = True` (default)
- `EXECUTION_RETENTION_DAYS`: `int = 90` (default)
- `RETENTION_JOB_BATCH_SIZE`: `int = 1000` (default)
- `RETENTION_JOB_SCHEDULE_CRON`: `str = "0 2 * * *"` (daily at 2 AM)

**Entry Points:**
- `start_retention_scheduler()` → starts retention scheduler
- `stop_retention_scheduler()` → stops retention scheduler
- `trigger_retention_enforcement(dry_run)` → manual trigger

**Startup:** Line 490-492 in `app/main.py`:
```python
from app.services.background_jobs.retention_job import start_retention_scheduler
start_retention_scheduler()
```

---

### 7. Downgrade Enforcement Scheduler
**File:** `app/services/background_jobs/downgrade_enforcement_job.py`

**Purpose:** Enforces plan downgrades, monitors over-limit tenants, and sends grace period warnings.

**Interval:**
- **Check Interval:** `CHECK_INTERVAL_SECONDS` from `settings.DOWNGRADE_ENFORCEMENT_INTERVAL_SECONDS`
  - Default: `3600` seconds (1 hour)
  - Configurable via `DOWNGRADE_ENFORCEMENT_INTERVAL_SECONDS` env var

**Trigger Conditions:**
- **Downgrade Enforcement Loop** (runs every 1 hour):
  - Calls `downgrade_service` to check for pending downgrades
  - Enforces grace period expirations
  - Sends grace period warnings at **7, 3, and 1 days** before expiration
    - Uses window: `days_threshold ± 0.5 days` to avoid duplicate notifications
  - Monitors over-limit tenants and triggers notifications

**Warning Thresholds:**
- 7 days remaining
- 3 days remaining
- 1 day remaining

**Entry Points:**
- `start_downgrade_enforcement_scheduler()` → starts downgrade scheduler
- `stop_downgrade_enforcement_scheduler()` → stops downgrade scheduler

**Startup:** Line 495-497 in `app/main.py`:
```python
from app.services.background_jobs.downgrade_enforcement_job import start_downgrade_enforcement_scheduler
start_downgrade_enforcement_scheduler()
```

---

### 8. Periodic Job Cleanup Task
**File:** `app/main.py` (inline function)

**Purpose:** Cleans up stale background jobs that got stuck or timed out.

**Interval:**
- **Cleanup Interval:** `300 seconds` (5 minutes)

**Trigger Conditions:**
- **Periodic Cleanup Loop** (`periodic_job_cleanup`):
  - Runs every 5 minutes
  - Calls `background_job_service.cleanup_stale_jobs(max_runtime_hours=24)`
  - Handles:
    - Jobs stuck at 100% completion
    - Jobs that timed out (>24 hours runtime)
    - Pending jobs that never started
  - Updates job status to `failed` or `completed` as appropriate
  - Logs summary: `cleaned_count`, `completed_count`, `failed_count`, `stale_running`, `stale_pending`

**Startup:** Line 457-462 in `app/main.py`:
```python
cleanup_task = asyncio.create_task(periodic_job_cleanup())
app.state.cleanup_task = cleanup_task
```

**Also runs once on startup** (line 448-455) to handle server crashes/restarts.

---

## Event-Driven Triggers (Webhooks)

### GitHub Webhook Handler
**File:** `app/api/endpoints/github_webhooks.py`

**Purpose:** Receives GitHub webhook events to trigger repository syncs when workflow files change.

**Endpoint:** `POST /api/v1/github/webhook`

**Supported Events:**
1. **Push Events** (`X-GitHub-Event: push`):
   - Triggered when commits are pushed to repository
   - Handler: `_handle_push_event()`
   - Triggers: Repository sync for affected environments

2. **Pull Request Events** (`X-GitHub-Event: pull_request`):
   - Only processes `action = closed` AND `pull_request.merged = true`
   - Handler: `_handle_pr_merged_event()`
   - Triggers: Repository sync for affected environments

**Security:**
- Verifies webhook signature using `X-Hub-Signature-256` header
- Uses `GITHUB_WEBHOOK_SECRET` from config
- If secret not configured: accepts webhook (for dev/testing)

**Note:** Webhook triggers are **event-driven** (not scheduled) and execute immediately when repository changes occur.

---

## Scheduler Lifecycle Management

### Startup Sequence (app/main.py)

```python
@app.on_event("startup")
async def startup_event():
    # 1. Cleanup stale jobs from previous run
    await background_job_service.cleanup_stale_jobs(max_runtime_hours=24)

    # 2. Start periodic job cleanup (every 5 minutes)
    cleanup_task = asyncio.create_task(periodic_job_cleanup())
    app.state.cleanup_task = cleanup_task

    # 3. Start deployment scheduler (30s polling)
    await start_scheduler()

    # 4. Start drift detection schedulers (5min, 1min, 24h)
    await start_all_drift_schedulers()

    # 5. Start canonical sync schedulers (30min, 30min) - if enabled
    await start_canonical_sync_schedulers()

    # 6. Start health check scheduler (1min)
    await start_health_check_scheduler()

    # 7. Start rollup scheduler (1h)
    start_rollup_scheduler()

    # 8. Start retention scheduler (daily at 2 AM UTC)
    start_retention_scheduler()

    # 9. Start downgrade enforcement scheduler (1h)
    start_downgrade_enforcement_scheduler()
```

### Shutdown Sequence (app/main.py)

```python
@app.on_event("shutdown")
async def shutdown_event():
    # Stop all schedulers gracefully
    app.state.cleanup_task.cancel()
    await stop_scheduler()  # deployment
    await stop_all_drift_schedulers()  # drift, TTL, retention cleanup
    await stop_canonical_sync_schedulers()  # repo, env sync
    await stop_health_check_scheduler()
    await stop_retention_scheduler()
    await stop_downgrade_enforcement_scheduler()
```

---

## Configuration Summary

### Environment Variables

| Variable | Default | Purpose | File |
|----------|---------|---------|------|
| `SYNC_SCHEDULER_ENABLED` | `false` | Enable/disable canonical sync schedulers | `config.py:43` |
| `EXECUTION_RETENTION_ENABLED` | `true` | Enable/disable retention enforcement | `config.py:33` |
| `EXECUTION_RETENTION_DAYS` | `90` | Default retention period (days) | `config.py:34` |
| `RETENTION_JOB_BATCH_SIZE` | `1000` | Batch size for retention deletions | `config.py:35` |
| `RETENTION_JOB_SCHEDULE_CRON` | `"0 2 * * *"` | Cron schedule for retention job | `config.py:36` |
| `DOWNGRADE_ENFORCEMENT_INTERVAL_SECONDS` | `3600` | Downgrade check interval (seconds) | `config.py:39` |
| `GITHUB_WEBHOOK_SECRET` | `""` | Secret for GitHub webhook signature verification | `config.py` |

### Hardcoded Constants

| Constant | Value | Location |
|----------|-------|----------|
| `DRIFT_CHECK_INTERVAL_SECONDS` | 300 (5 min) | `drift_scheduler.py:28` |
| `TTL_CHECK_INTERVAL_SECONDS` | 60 (1 min) | `drift_scheduler.py:29` |
| `RETENTION_CLEANUP_INTERVAL_SECONDS` | 86400 (24h) | `drift_scheduler.py:30` |
| `REPO_SYNC_INTERVAL` | 1800 (30 min) | `canonical_sync_scheduler.py:35` |
| `ENV_SYNC_INTERVAL` | 1800 (30 min) | `canonical_sync_scheduler.py:36` |
| `SYNC_DEBOUNCE_SECONDS` | 60 | `canonical_sync_scheduler.py:41` |
| `ROLLUP_INTERVAL_SECONDS` | 3600 (1h) | `rollup_scheduler.py:21` |
| `ROLLUP_DAYS_TO_BACKFILL` | 7 | `rollup_scheduler.py:22` |
| `HEALTH_CHECK_INTERVAL_SECONDS` | 60 (1 min) | `health_check_scheduler.py:22` |
| `RETENTION_CHECK_INTERVAL_SECONDS` | 3600 (1h) | `retention_job.py:48` |
| `RETENTION_JOB_HOUR_UTC` | 2 (2 AM) | `retention_job.py:49` |
| `RETENTION_JOB_MINUTE_UTC` | 0 | `retention_job.py:50` |
| Deployment poll interval | 30s | `deployment_scheduler.py:216` |
| Job cleanup interval | 300s (5 min) | `main.py:422` |
| Job max runtime | 24h | `main.py:424` |

---

## Scheduler Interactions

### Sync → Reconciliation → Drift Detection Flow

```
Canonical Sync Scheduler (every 30 min)
  ↓
  Repo Sync OR Env Sync
  ↓
  Canonical Reconciliation Service
  ↓
  (Drift status updated in canonical_workflow_pairs)
  ↓
Drift Detection Scheduler (every 5 min)
  ↓
  Reads drift status, creates incidents
```

### Deployment Scheduling Flow

```
API: POST /deployments (with scheduled_at)
  ↓
  Database: deployment record (status=scheduled)
  ↓
Deployment Scheduler (every 30s)
  ↓
  Queries scheduled deployments (scheduled_at <= now)
  ↓
  Checks promotion lock (prevents concurrent promotions)
  ↓
  Executes promotion in background task
```

### Retention Cleanup Flow

```
Drift Scheduler (daily)
  ↓
  Calls drift_retention_service.cleanup_all_tenants()
  ↓
  Deletes:
    - Closed drift incidents (based on retention policy)
    - Old reconciliation artifacts
    - Old drift approvals

Retention Scheduler (daily at 2 AM UTC)
  ↓
  Calls retention_enforcement_service.enforce_all_tenants_retention()
  ↓
  Deletes:
    - Old executions (based on plan limits)
    - Old audit logs (based on plan limits)
```

---

## Failure Modes & Error Handling

### Debounce & Idempotency
- **Canonical Sync:** 60-second debounce prevents duplicate syncs
- **Drift Detection:** No debounce (always checks all eligible environments)
- **Deployment Scheduler:** Promotion lock prevents concurrent deployments

### Graceful Degradation
- **Sync failures:** Logged as warnings, environment-level (doesn't stop other envs)
- **Health check failures:** Logged as warnings (doesn't affect availability)
- **Drift detection failures:** Logged as errors, environment-level
- **Job cleanup:** Runs every 5 minutes to recover from stuck jobs

### Notification Events
- **Drift incidents:** `drift.detected`, `drift.ttl_expired`, `drift.ttl_warning`
- **Materialized views:** `materialized_view.refresh_failed`, `materialized_view.stale_detected`
- **Downgrade warnings:** Grace period warnings at 7, 3, 1 days

---

## Observability

### Logging
- All schedulers log at `INFO` level on start/stop
- Periodic operations log at `DEBUG` level
- Errors log at `ERROR` level with `exc_info=True`

### Metrics Emitted
- **Drift Detection:** `total_workflows`, `with_drift`, `not_in_git`, `in_sync`
- **Job Cleanup:** `cleaned_count`, `completed_count`, `failed_count`, `stale_running`, `stale_pending`
- **Retention:** `total_deleted`, `total_executions_deleted`, `total_audit_logs_deleted`, `tenants_processed`
- **Rollup:** `rows_affected`, `refresh_time` per materialized view

---

## Summary Table

| Scheduler | Interval | Enabled By Default | Primary Purpose | Selection Criteria |
|-----------|----------|-------------------|-----------------|-------------------|
| **Drift Detection** | 5 min | ✅ Yes | Detect drift, create incidents | Non-DEV envs with Git + drift_detection feature |
| **TTL Checker** | 1 min | ✅ Yes | Expire incidents, send warnings | Active incidents with expires_at |
| **Retention Cleanup** | 24h | ✅ Yes | Clean old incidents/artifacts | All tenants with drift_retention policy |
| **Repo Sync** | 30 min | ❌ No (MVP) | Sync Git → DB | Envs with git_repo_url + git_folder |
| **Env Sync** | 30 min | ❌ No (MVP) | Sync n8n → DB | All environments |
| **Deployment** | 30s | ✅ Yes | Execute scheduled deployments | Deployments with scheduled_at ≤ now |
| **Rollup** | 1h | ✅ Yes | Pre-compute analytics | All tenants (daily rollups) |
| **Health Check** | 1 min | ✅ Yes | Update heartbeat timestamps | Active environments (is_active=true) |
| **Retention** | Daily 2 AM | ✅ Yes | Enforce data retention | All tenants with plan limits |
| **Downgrade** | 1h | ✅ Yes | Enforce plan downgrades | Tenants with pending downgrades |
| **Job Cleanup** | 5 min | ✅ Yes | Clean stale background jobs | Jobs >24h or stuck at 100% |

---

## Code References

### Key Functions by Scheduler

**Drift Scheduler:**
- `_get_environments_for_drift_check()` → line 33
- `_process_drift_detection()` → line 70
- `_handle_drift_detected()` → line 119
- `_create_drift_incident()` → line 212
- `_process_ttl_checks()` → line 319
- `_handle_ttl_expired()` → line 383
- `_process_retention_cleanup()` → line 526

**Canonical Sync Scheduler:**
- `_process_repo_sync_scheduler()` → line 44
- `_process_env_sync_scheduler()` → line 133
- `_get_last_repo_sync_time()` → line 234
- `_get_last_env_sync_time()` → line 256

**Deployment Scheduler:**
- `_process_scheduled_deployments()` → line 33

**Rollup Scheduler:**
- `_compute_rollups_for_date()` → line 25
- `_refresh_materialized_views()` → line 50
- `_check_stale_materialized_views()` → line 111
- `_check_and_compute_rollups()` → line 184
- `_rollup_scheduler_loop()` → line 212

**Health Check Scheduler:**
- `_process_health_checks()` → line 25

**Main Startup/Shutdown:**
- `startup_event()` → `main.py:440`
- `shutdown_event()` → `main.py:539`
- `periodic_job_cleanup()` → `main.py:414`

---

**End of T005 Documentation**
