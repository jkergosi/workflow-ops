# Retention Job Scheduler

Automated scheduled job for enforcing plan-based retention policies on executions and audit logs.

## Overview

The retention job scheduler (`retention_job.py`) is a background service that automatically enforces data retention policies based on each tenant's subscription plan. It runs daily during off-peak hours to clean up old executions and audit logs, ensuring compliance with plan limits and maintaining database performance.

## Features

### Core Functionality
- **Automated Enforcement**: Runs daily at 2 AM UTC to enforce retention policies
- **Plan-Based Retention**: Respects each tenant's plan limits (Free: 7 days, Pro: 30 days, etc.)
- **Batch Processing**: Deletes records in batches to avoid database lock contention
- **Comprehensive Logging**: Detailed logs for monitoring and debugging
- **Graceful Shutdown**: Properly handles application restarts

### Safety Features
- **Dry Run Mode**: Preview deletions without actually removing data
- **Minimum Threshold**: Preserves at least 100 records per tenant for historical context
- **Error Isolation**: Continues processing other tenants even if one fails
- **Metrics Tracking**: Records detailed statistics about each run

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       main.py                               │
│  - Starts retention_scheduler on startup                    │
│  - Stops retention_scheduler on shutdown                    │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│            retention_job.py (Scheduler)                     │
│  - Runs every hour to check if job should execute          │
│  - Triggers enforcement at 2 AM UTC daily                   │
│  - Tracks last run date to avoid duplicate runs             │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│      retention_enforcement_service.py (Core Logic)          │
│  - Determines retention policy for each tenant              │
│  - Deletes old executions and audit logs                    │
│  - Returns detailed metrics about enforcement               │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

You can customize the retention job behavior using these environment variables in your `.env` file:

```bash
# Run retention job immediately on startup (default: False)
RETENTION_JOB_RUN_ON_STARTUP=false

# Batch size for deletion operations (default: 1000)
RETENTION_JOB_BATCH_SIZE=1000

# Default retention days if plan cannot be determined (default: 7)
DEFAULT_RETENTION_DAYS=7
```

### Schedule Configuration

By default, the retention job runs daily at **2:00 AM UTC**. This can be changed in `retention_job.py`:

```python
RETENTION_JOB_HOUR_UTC = 2  # Hour to run (0-23)
RETENTION_JOB_MINUTE_UTC = 0  # Minute to run (0-59)
RETENTION_CHECK_INTERVAL_SECONDS = 3600  # How often to check (1 hour)
```

## Usage

### Automatic Startup

The retention scheduler is automatically started when the application starts:

```python
# In main.py startup event
from app.services.background_jobs.retention_job import start_retention_scheduler
start_retention_scheduler()
logger.info("Retention scheduler started")
```

### Manual Triggering

You can manually trigger retention enforcement for testing or administrative purposes:

```python
from app.services.background_jobs.retention_job import trigger_retention_enforcement

# Preview what would be deleted (dry run)
result = await trigger_retention_enforcement(dry_run=True)
print(f"Would delete {result['total_deleted']} records")

# Actually delete old records
result = await trigger_retention_enforcement(dry_run=False)
print(f"Deleted {result['total_deleted']} records")
```

### Check Scheduler Status

```python
from app.services.background_jobs.retention_job import get_retention_scheduler_status

status = await get_retention_scheduler_status()
print(f"Scheduler running: {status['running']}")
print(f"Next run at: {status['next_run_hour_utc']:02d}:{status['next_run_minute_utc']:02d} UTC")
```

### Graceful Shutdown

The scheduler is automatically stopped during application shutdown:

```python
# In main.py shutdown event
from app.services.background_jobs.retention_job import stop_retention_scheduler
await stop_retention_scheduler()
logger.info("Retention scheduler stopped")
```

## Testing

### Run Test Script

A test script is provided to verify the retention job functionality:

```bash
# From the backend directory
python -m app.services.background_jobs.test_retention_job
```

This will:
1. Run a dry run to preview deletions
2. Check the scheduler status
3. Display detailed metrics

### Manual Testing Steps

1. **Preview Deletions (Safe)**:
   ```python
   from app.services.background_jobs.retention_job import trigger_retention_enforcement
   result = await trigger_retention_enforcement(dry_run=True)
   ```

2. **Check Tenant-Specific Policy**:
   ```python
   from app.services.retention_enforcement_service import retention_enforcement_service
   policy = await retention_enforcement_service.get_tenant_retention_policy("tenant-uuid")
   print(f"Plan: {policy['plan_name']}, Retention: {policy['retention_days']} days")
   ```

3. **Get Retention Preview**:
   ```python
   from app.services.retention_enforcement_service import retention_enforcement_service
   preview = await retention_enforcement_service.get_retention_preview("tenant-uuid")
   print(f"Would delete {preview['total_to_delete']} records")
   ```

## Monitoring

### Log Messages

The retention job logs detailed information at each step:

```
INFO - Retention scheduler started - will run daily at 02:00 UTC
INFO - Starting scheduled retention enforcement job
INFO - Tenant abc123 on free plan has 7 days retention
INFO - Deleted 1500 executions for tenant abc123 older than 7 days
INFO - Scheduled retention job completed successfully:
  - Total deleted: 3500 records
  - Executions deleted: 2000
  - Audit logs deleted: 1500
  - Tenants processed: 10
  - Duration: 12.5s
```

### Metrics

Each run returns detailed metrics:

```json
{
  "total_deleted": 3500,
  "total_executions_deleted": 2000,
  "total_audit_logs_deleted": 1500,
  "tenants_processed": 10,
  "tenants_with_deletions": 8,
  "tenants_skipped": 2,
  "errors": [],
  "started_at": "2024-01-08T02:00:00Z",
  "completed_at": "2024-01-08T02:00:12Z",
  "duration_seconds": 12.5,
  "dry_run": false
}
```

## Troubleshooting

### Job Not Running

1. **Check if scheduler is running**:
   ```python
   status = await get_retention_scheduler_status()
   print(status)
   ```

2. **Check application logs**:
   ```bash
   # Look for retention scheduler messages
   grep "Retention scheduler" app.log
   ```

3. **Verify scheduler was started**:
   - Check `main.py` startup event logs
   - Ensure `start_retention_scheduler()` is called

### No Records Being Deleted

1. **Run dry run to check what would be deleted**:
   ```python
   result = await trigger_retention_enforcement(dry_run=True)
   ```

2. **Check tenant retention policies**:
   ```python
   policy = await retention_enforcement_service.get_tenant_retention_policy("tenant-id")
   print(f"Retention period: {policy['retention_days']} days")
   ```

3. **Check minimum threshold**:
   - Tenants with < 100 records are skipped to preserve history
   - Check logs for "Skipping deletion" messages

### Scheduler Stops Unexpectedly

1. **Check for exceptions in logs**:
   ```bash
   grep "Error in retention scheduler" app.log
   ```

2. **Verify graceful shutdown**:
   - Scheduler should log "Retention scheduler stopped" on shutdown
   - Check shutdown event handlers in `main.py`

## Related Components

### Files Modified/Created

- **T009**: `app/services/retention_enforcement_service.py` - Core enforcement logic
- **T010**: Execution retention enforcement implementation
- **T011**: Audit log retention enforcement implementation
- **T012**: `app/services/background_jobs/retention_job.py` - **THIS FILE**
- **Integration**: `app/main.py` - Startup/shutdown integration

### Dependencies

- `retention_enforcement_service`: Core enforcement logic
- `entitlements_service`: Plan determination
- `database.py`: Database operations
- `asyncio`: Async task scheduling

## Best Practices

### Production Deployment

1. **Test with dry run first**:
   ```python
   result = await trigger_retention_enforcement(dry_run=True)
   ```

2. **Monitor first few runs**:
   - Check logs for errors
   - Verify deletion counts match expectations
   - Ensure performance is acceptable

3. **Set appropriate batch size**:
   - Larger batches = faster but more database load
   - Default 1000 is a good balance

4. **Configure off-peak hours**:
   - Default 2 AM UTC is usually low traffic
   - Adjust if your tenant base is in different timezones

### Maintenance

1. **Regular log review**:
   - Check for increasing error rates
   - Monitor execution times
   - Track tenant growth impact

2. **Database optimization**:
   - Ensure indexes on `started_at` (executions) and `accessed_at` (audit logs)
   - Monitor database performance during retention jobs

3. **Policy updates**:
   - Update `PLAN_RETENTION_PERIODS` when adding new plans
   - Coordinate with entitlements service for plan changes

## API Integration

While primarily a background job, you can expose retention operations via API endpoints:

```python
# Example API endpoint for admin panel
@router.post("/admin/retention/trigger")
async def trigger_retention_job(dry_run: bool = False):
    """Manually trigger retention enforcement"""
    from app.services.background_jobs.retention_job import trigger_retention_enforcement
    return await trigger_retention_enforcement(dry_run=dry_run)

@router.get("/admin/retention/status")
async def get_retention_status():
    """Get retention scheduler status"""
    from app.services.background_jobs.retention_job import get_retention_scheduler_status
    return await get_retention_scheduler_status()
```

## Security Considerations

1. **Data Deletion is Permanent**: Once deleted, data cannot be recovered
2. **Plan-Based Access**: Retention enforcement respects plan limits automatically
3. **Minimum Threshold**: Protects against accidental mass deletion
4. **Error Isolation**: Failures in one tenant don't affect others

## Performance

- **Expected Duration**: 10-30 seconds for 100 tenants (varies by data volume)
- **Database Impact**: Minimal due to batch processing and off-peak scheduling
- **Memory Usage**: Low - processes one tenant at a time
- **CPU Usage**: Low - mainly I/O bound operations

## Future Enhancements

Potential improvements for future versions:

1. **Configurable per-tenant schedules**: Allow tenants to choose when their data is cleaned
2. **Retention policy overrides**: Admin ability to extend retention for specific tenants
3. **Archive before delete**: Move old data to cold storage instead of deleting
4. **Webhook notifications**: Notify tenants when retention enforcement runs
5. **Dashboard metrics**: UI to show retention enforcement history and trends
