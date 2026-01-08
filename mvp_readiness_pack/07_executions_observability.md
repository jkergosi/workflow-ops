# 07 - Executions, Analytics & Observability

## Execution Sync & Retention

### Execution Sync

**File**: `services/n8n_client.py:get_executions()`

**Trigger**: 
- Manual: `POST /api/v1/environments/{id}/sync` (includes executions)
- Selective: `POST /api/v1/environments/{id}/sync?type=executions`

**Flow**:
1. Fetch executions from n8n API (paginated)
2. Normalize status (`success`, `error`, `running`, `waiting`)
3. Upsert to `executions` table
4. Update `execution_analytics` aggregates

**Batch Size**: 100 executions per API call (n8n pagination)

**Performance Risk**: Syncing 10k+ executions may take minutes. No progress tracking for execution sync specifically.

### Execution Retention

**File**: `services/background_jobs/retention_job.py`

**Schedule**: Daily at 2 AM UTC

**Logic**:
```python
retention_days = entitlements.get("execution_retention_days", 7)  # Default: 7 days
cutoff = now() - timedelta(days=retention_days)
delete_executions_before(tenant_id, cutoff, min_preserve=100)
```

**Safety Features**:
- Preserves minimum 100 records per tenant
- Deletes in batches of 1000
- Dry-run mode available (not exposed via API)

**Migration**: `alembic/versions/20260108_add_execution_retention_policy.py`

**Test**: `tests/test_retention.py`

**Risk**: Retention timing (2 AM UTC) may cause DB load spike if many tenants.

---

## Analytics Calculations

### KPI Metrics

**File**: `services/observability_service.py:get_kpi_metrics()`

**API**: `GET /api/v1/observability/kpis?time_range=24h`

**Metrics Computed**:
```python
{
  "total_executions": count(*),
  "success_count": count(*) WHERE status='success',
  "failure_count": count(*) WHERE status='error',
  "success_rate": (success_count / total_executions) * 100,
  "avg_duration_ms": avg(execution_time),
  "p50_duration_ms": percentile(execution_time, 0.50),
  "p95_duration_ms": percentile(execution_time, 0.95),
  "sparkline_data": [...],  // See "Sparkline Generation"
  "delta_vs_previous": {
    "total_executions": +15%,
    "success_rate": -2%
  }
}
```

**Exclusions**:
- `status = 'running'` excluded from success rate calculation
- `execution_time IS NULL` excluded from duration calculations

**Test**: `tests/test_observability_service.py`

### Sparkline Generation

**Optimization**: Single-query aggregation instead of N sequential queries

**File**: `observability_service.py:_get_sparkline_data()` (lines 135-300)

**Logic**:
1. Determine interval based on time range:
   - 1hr: 5-min intervals (12 points)
   - 6hr: 30-min intervals (12 points)
   - 24hr: 1-hr intervals (24 points)
   - 7d: 12-hr intervals (14 points)
   - 30d: 1-day intervals (30 points)

2. Fetch ALL executions in time range (single query)

3. Bucket executions into intervals (Python aggregation)

4. Compute KPIs per bucket

**Performance**: 90%+ improvement over N sequential queries (stated in code comments)

**Risk**: Assumes reasonable execution counts per time range. 100k+ executions may cause memory issues during aggregation.

### Error Intelligence

**File**: `observability_service.py:get_error_intelligence()`

**API**: `GET /api/v1/observability/errors?time_range=24h`

**Logic**:
```python
# Group errors by error_message (naive exact match)
errors = fetch_failed_executions(time_range)
grouped = defaultdict(list)
for error in errors:
    msg = error.get("error_message") or "Unknown error"
    grouped[msg].append(error)

# Generate error groups
return [
    {
        "error_type": msg,
        "count": len(errors),
        "first_seen": min(e["started_at"] for e in errors),
        "last_seen": max(e["started_at"] for e in errors),
        "affected_workflows": len(set(e["workflow_id"] for e in errors)),
        "sample_messages": errors[:5]  # First 5 occurrences
    }
    for msg, errors in grouped.items()
]
```

**Grouping Strategy**: Exact string match on `error_message`

**Limitation**: No error classification, no ML, no fuzzy matching. "Connection timeout" and "Connection timed out" treated as separate errors.

**Test**: Unknown

---

## Indexing Assumptions

### Primary Indexes (Assumed)

**executions** table likely has indexes on:
- `(tenant_id, environment_id, started_at)` - For time-range queries
- `(tenant_id, workflow_id, started_at)` - For per-workflow analytics
- `(tenant_id, normalized_status, started_at)` - For success/failure filtering

**Verification Needed**: Review `alembic/versions/bf7375f4eb69_add_performance_indexes.py`

### Materialized Views

**File**: `services/rollup_scheduler.py:_refresh_materialized_views()`

**Purpose**: Pre-compute expensive aggregations

**Views** (assumed from migration `20260108_add_materialized_views.py`):
- `mv_execution_counts_by_workflow`
- `mv_execution_counts_by_environment`
- `mv_error_summary`

**Refresh Schedule**: Periodic (interval unknown, likely hourly)

**Risk**: Materialized views may be stale. UI shows stale data if refresh fails or is delayed.

---

## Observability Endpoints & SSE Events

### REST Endpoints

| Method | Path | Purpose | Response Time Target |
|--------|------|---------|---------------------|
| GET | `/observability/overview` | Complete observability dashboard | <2s |
| GET | `/observability/kpis` | KPI metrics with sparklines | <500ms |
| GET | `/observability/workflows` | Workflow performance table | <1s |
| GET | `/observability/environments` | Environment health checks | <500ms |
| GET | `/observability/errors` | Error intelligence | <1s |
| GET | `/observability/status` | System status insights | <500ms |
| GET | `/executions` | List executions with filters | <1s |
| GET | `/analytics/executions` | Execution analytics per workflow | <2s |

**File**: `api/endpoints/observability.py`, `api/endpoints/executions.py`

### SSE Events

**File**: `api/endpoints/sse.py`

| Event | Purpose | Payload |
|-------|---------|---------|
| `counts.update` | Real-time count updates | `{total_executions, success_count, failure_count}` |
| `execution.completed` | Execution finished | `{execution_id, status, duration}` |
| `sync.progress` | Sync progress | `{current, total, percentage}` |

**API**: `GET /api/v1/sse/counts/{tenant_id}`

**Connection Management**: 
- Client subscribes to SSE stream
- Server sends updates as they occur
- Client auto-reconnects on disconnect (frontend logic)

**Risk**: SSE reconnection logic after server restart untested. Clients may not receive updates until manual refresh.

---

## Performance Risks

### High Risk

1. **Execution Sync Scale**: Syncing 10k+ executions untested. May take minutes or timeout.

2. **Sparkline Aggregation Memory**: Aggregating 100k+ executions in Python may cause memory issues. Should move aggregation to DB.

3. **Materialized View Staleness**: If refresh fails, UI shows stale data. No alerting on refresh failure.

4. **SSE Reconnection**: Client reconnection after server restart untested. May require manual page refresh.

### Medium Risk

1. **Error Intelligence Performance**: Grouping errors in Python inefficient. Should use DB aggregation.

2. **Retention Load Spike**: All tenants processed at 2 AM UTC. Should stagger.

3. **KPI Query Complexity**: Multiple joins and aggregations. May be slow with large datasets.

### Low Risk

1. **Fixed Time Ranges**: No custom date ranges. Minor UX limitation.

2. **Execution Status Normalization**: Mapping n8n statuses to normalized statuses may miss edge cases.

---

## Database Tables

### executions

**Purpose**: Store execution records

**Key Columns**:
- `id` (UUID), `tenant_id`, `environment_id`, `provider`
- `workflow_id`, `workflow_name`
- `n8n_execution_id`: Provider-specific ID
- `normalized_status`: success/error/running/waiting
- `started_at`, `finished_at`, `execution_time` (ms)
- `error_message`, `error_node`: Error details
- `mode`: manual/trigger/webhook/etc
- `created_at`, `updated_at`

**Indexes**: See "Indexing Assumptions"

### execution_analytics

**Purpose**: Pre-computed analytics columns (added by migration)

**Key Columns**:
- `workflow_id`, `environment_id`, `tenant_id`
- `total_count`, `success_count`, `failure_count`
- `avg_duration`, `p50_duration`, `p95_duration`
- `last_execution_at`, `last_failure_at`
- `last_error_message`

**Update Trigger**: After each execution sync

**Migration**: `alembic/versions/20260107_182000_add_execution_analytics_columns.py`

---

## Tests

| Test File | Coverage |
|-----------|----------|
| `test_observability_service.py` | KPI calculations, sparklines |
| `test_executions_api.py` | Execution API endpoints |
| `test_retention.py` | Retention enforcement |
| `test_aggregations.py` | Aggregation functions |

**Gaps**: No tests for error intelligence, SSE events, materialized view refresh

---

## Gaps & Missing Features

### Not Implemented

1. **Custom Time Ranges**: Only fixed ranges (1h, 6h, 24h, 7d, 30d). No custom date picker.

2. **Error Classification**: No ML or rule-based error classification. Naive string matching only.

3. **Execution Replay**: No ability to retry failed executions from UI.

4. **Execution Diff**: No comparison of execution inputs/outputs between runs.

5. **Alerting**: No alerts on error rate spikes, SLA breaches, or execution failures.

### Unclear Behavior

1. **Sparkline Aggregation Limits**: Max executions per time range unclear. May fail silently.

2. **Materialized View Refresh Failure**: What happens if refresh fails? UI shows stale data? Error logged?

3. **Execution Sync Partial Failure**: If sync fails mid-batch, are previous batches rolled back or committed?

---

## Recommendations

### Must Fix Before MVP Launch

1. Test execution sync with 10k+ executions
2. Move sparkline aggregation to DB (SQL window functions)
3. Add alerting on materialized view refresh failures
4. Test SSE reconnection after server restart

### Should Fix Post-MVP

1. Implement custom time range support
2. Add error classification (ML or rule-based)
3. Move error intelligence grouping to DB
4. Add execution replay capability

### Nice to Have

1. Execution diff comparison
2. Alerting on error rate spikes
3. SLA breach notifications
4. Execution impact analysis (which workflows depend on this execution)

