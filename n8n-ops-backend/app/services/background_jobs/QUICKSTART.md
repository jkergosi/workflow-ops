# Retention Job - Quick Start Guide

## What is it?
The retention job automatically deletes old executions and audit logs based on each tenant's subscription plan (e.g., Free: 7 days, Pro: 30 days).

## How does it work?
- Runs **daily at 2 AM UTC** (off-peak hours)
- Checks every hour if it's time to run
- Processes all tenants automatically
- Deletes old data in batches (safe for database)

## Quick Commands

### Test (Safe - No Deletion)
```python
from app.services.background_jobs.retention_job import trigger_retention_enforcement

# Preview what would be deleted
result = await trigger_retention_enforcement(dry_run=True)
print(f"Would delete {result['total_deleted']} records")
```

### Manual Run (Actually Deletes)
```python
# Only use if you need to run retention outside of schedule
result = await trigger_retention_enforcement(dry_run=False)
print(f"Deleted {result['total_deleted']} records")
```

### Check Status
```python
from app.services.background_jobs.retention_job import get_retention_scheduler_status

status = await get_retention_scheduler_status()
print(f"Running: {status['running']}")
print(f"Next run: {status['next_run_hour_utc']:02d}:{status['next_run_minute_utc']:02d} UTC")
```

## Configuration

### Change Run Time
Edit `retention_job.py`:
```python
RETENTION_JOB_HOUR_UTC = 2  # Change to desired hour (0-23)
```

### Change Batch Size
Set environment variable:
```bash
RETENTION_JOB_BATCH_SIZE=1000  # Default is 1000
```

## Monitoring

### Check Logs
```bash
# Look for retention job messages
grep "Retention scheduler" app.log
grep "retention enforcement" app.log
```

### Expected Log Output
```
INFO - Retention scheduler started - will run daily at 02:00 UTC
INFO - Starting scheduled retention enforcement job
INFO - Deleted 1500 executions for tenant abc123 older than 7 days
INFO - Scheduled retention job completed successfully:
  - Total deleted: 3500 records
  - Duration: 12.5s
```

## Troubleshooting

### Job Not Running?
1. Check if scheduler started: `grep "Retention scheduler started" app.log`
2. Verify current time matches schedule: Job runs at 2 AM UTC
3. Check for errors: `grep "Error.*retention" app.log`

### No Records Deleted?
1. Run dry run to see preview: `trigger_retention_enforcement(dry_run=True)`
2. Check tenant has enough records: Minimum 100 records preserved per tenant
3. Verify data is old enough: Must be older than retention period

### Need Help?
- See `RETENTION_JOB_README.md` for full documentation
- See `T012_IMPLEMENTATION_SUMMARY.md` for implementation details
- Check retention enforcement service: `app/services/retention_enforcement_service.py`

## Safety Features
✅ **Dry run mode** - Test without deleting
✅ **Minimum threshold** - Keeps at least 100 records per tenant
✅ **Error isolation** - One tenant's error doesn't affect others
✅ **Batch processing** - Gentle on database
✅ **Plan-based** - Respects each tenant's limits

## When to Use

### Automatic (Default)
The job runs automatically every day - **no action needed**.

### Manual Trigger
Only needed for:
- Testing retention policies
- Running outside of schedule
- Debugging issues
- Admin operations

## Related Files
- **Scheduler**: `app/services/background_jobs/retention_job.py`
- **Core Logic**: `app/services/retention_enforcement_service.py`
- **Integration**: `app/main.py` (startup/shutdown)
- **Testing**: `app/services/background_jobs/test_retention_job.py`
