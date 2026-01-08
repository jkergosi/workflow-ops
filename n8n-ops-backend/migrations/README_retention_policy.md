# Execution Retention Policy Migration

## Overview
This migration implements time-based retention for the `executions` table to prevent unbounded database growth and improve query performance for large tenants (100k+ executions).

## Files
- `add_execution_retention_policy.sql` - Standalone SQL migration
- `alembic/versions/20260108_add_execution_retention_policy.py` - Alembic version-controlled migration

## What It Does

### 1. Creates `execution_retention_policies` Table
Stores tenant-specific retention configuration:
- `retention_days`: Number of days to keep executions (default: 90)
- `is_enabled`: Whether retention is active for the tenant
- `min_executions_to_keep`: Safety threshold - always keep at least this many executions
- `last_cleanup_at`, `last_cleanup_deleted_count`: Audit tracking

**Key Feature**: One policy per tenant (enforced by unique constraint)

### 2. Adds Optimized Indexes
- `idx_executions_retention_cleanup`: Speeds up tenant + date queries for cleanup
- `idx_executions_null_started_at`: Handles edge case of incomplete executions
- `idx_retention_policies_tenant`: Fast policy lookups for enabled tenants

### 3. Creates `cleanup_old_executions()` Function
PostgreSQL function for safe, batch cleanup:
```sql
SELECT * FROM cleanup_old_executions(
    p_tenant_id := 'abc-123',
    p_retention_days := 90,
    p_min_executions_to_keep := 100,
    p_batch_size := 1000
);
```

**Returns**: `(deleted_count, execution_summary)` for monitoring

**Safety Features**:
- Never deletes below `min_executions_to_keep` threshold
- Uses batching to avoid long table locks
- Handles both `started_at` and `created_at` dates
- Returns JSONB summary for logging/monitoring

### 4. Adds Updated_at Trigger
Automatically updates `updated_at` timestamp when retention policies are modified.

## Usage Example

### Apply the Migration
```bash
# Using Alembic
alembic upgrade head

# Or apply SQL directly
psql $DATABASE_URL -f migrations/add_execution_retention_policy.sql
```

### Create a Retention Policy for a Tenant
```sql
INSERT INTO execution_retention_policies (tenant_id, retention_days, is_enabled, min_executions_to_keep)
VALUES ('550e8400-e29b-41d4-a716-446655440000', 90, TRUE, 100);
```

### Run Manual Cleanup
```sql
-- Cleanup for specific tenant
SELECT * FROM cleanup_old_executions(
    '550e8400-e29b-41d4-a716-446655440000'::UUID,
    90,  -- retention_days
    100, -- min_executions_to_keep
    1000 -- batch_size
);
```

### Query Retention Status
```sql
-- See all retention policies
SELECT
    tenant_id,
    retention_days,
    is_enabled,
    min_executions_to_keep,
    last_cleanup_at,
    last_cleanup_deleted_count
FROM execution_retention_policies;

-- Check how many old executions exist for a tenant
SELECT COUNT(*)
FROM executions
WHERE tenant_id = '550e8400-e29b-41d4-a716-446655440000'
  AND started_at < NOW() - INTERVAL '90 days';
```

## Integration with Backend Service

The retention service (Task T003) will use this infrastructure:
1. Load retention policies from `execution_retention_policies` table
2. Call `cleanup_old_executions()` function for each tenant
3. Update `last_cleanup_at` and `last_cleanup_deleted_count` after each run
4. Run on schedule (configured via `RETENTION_JOB_SCHEDULE_CRON` in config)

## Performance Considerations

### Index Usage
The migration adds two critical indexes:
- `idx_executions_retention_cleanup`: Used for `WHERE tenant_id = X AND started_at < Y` queries
- `idx_executions_null_started_at`: Handles edge case of stale/incomplete executions

### Batch Processing
The `cleanup_old_executions()` function uses `LIMIT` to delete in batches (default 1000 records). This:
- Prevents long table locks
- Allows incremental cleanup
- Can be tuned via `p_batch_size` parameter

### Safety Threshold
The `min_executions_to_keep` parameter ensures tenants with low activity always maintain some history, even if it's older than the retention period.

## Rollback

### Using Alembic
```bash
alembic downgrade -1
```

### Manual SQL Rollback
```sql
DROP TRIGGER IF EXISTS trigger_update_execution_retention_policies_updated_at ON execution_retention_policies;
DROP FUNCTION IF EXISTS update_execution_retention_policies_updated_at();
DROP FUNCTION IF EXISTS cleanup_old_executions(UUID, INTEGER, INTEGER, INTEGER);
DROP INDEX IF EXISTS idx_executions_null_started_at;
DROP INDEX IF EXISTS idx_executions_retention_cleanup;
DROP INDEX IF EXISTS idx_retention_policies_tenant;
DROP TABLE IF EXISTS execution_retention_policies;
```

## Related Tasks
- **T001**: Add retention configuration to settings ✅ (COMPLETED)
- **T002**: Create database migration for retention policy table ✅ (THIS TASK)
- **T003**: Create retention service with time-based cleanup logic (NEXT)
- **T004**: Add retention management API endpoints
- **T009**: Add retention policy unit tests

## Testing Checklist
- [ ] Verify table creation
- [ ] Insert sample retention policies
- [ ] Test `cleanup_old_executions()` with various parameters
- [ ] Verify indexes are used (via EXPLAIN ANALYZE)
- [ ] Test edge cases (no executions, all executions old, etc.)
- [ ] Verify `min_executions_to_keep` threshold works
- [ ] Test batch deletion with large datasets
