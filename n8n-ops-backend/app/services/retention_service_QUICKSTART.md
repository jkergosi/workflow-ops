# Retention Service Quick Start Guide

## Import the Service

```python
from app.services.retention_service import retention_service
```

## Common Operations

### 1. Get Tenant's Retention Policy
```python
policy = await retention_service.get_retention_policy(tenant_id)
# Returns: {retention_days, is_enabled, min_executions_to_keep, last_cleanup_at, ...}
```

### 2. Create or Update Policy
```python
# Create new policy
await retention_service.create_retention_policy(
    tenant_id="uuid",
    retention_days=90,
    is_enabled=True,
    min_executions_to_keep=100
)

# Update existing policy
await retention_service.update_retention_policy(
    tenant_id="uuid",
    retention_days=30  # Change retention period
)
```

### 3. Preview Cleanup Impact (Safe - No Deletion)
```python
preview = await retention_service.get_cleanup_preview(tenant_id)
print(f"Would delete {preview['executions_to_delete']} executions")
```

### 4. Cleanup Single Tenant
```python
result = await retention_service.cleanup_tenant_executions(tenant_id)
print(f"Deleted {result['deleted_count']} executions")
```

### 5. Cleanup All Tenants (Scheduled Job)
```python
summary = await retention_service.cleanup_all_tenants()
print(f"Total: {summary['total_deleted']} executions deleted")
```

## API Endpoint Usage (for T004)

```python
from fastapi import APIRouter, Depends
from app.services.retention_service import retention_service
from app.services.auth_service import get_current_user

router = APIRouter()

@router.get("/retention/policy")
async def get_policy(user_info: dict = Depends(get_current_user)):
    tenant_id = user_info["tenant"]["id"]
    return await retention_service.get_retention_policy(tenant_id)

@router.post("/retention/policy")
async def update_policy(
    retention_days: int,
    is_enabled: bool,
    user_info: dict = Depends(get_current_user)
):
    tenant_id = user_info["tenant"]["id"]
    return await retention_service.update_retention_policy(
        tenant_id, retention_days=retention_days, is_enabled=is_enabled
    )

@router.get("/retention/preview")
async def preview_cleanup(user_info: dict = Depends(get_current_user)):
    tenant_id = user_info["tenant"]["id"]
    return await retention_service.get_cleanup_preview(tenant_id)

@router.post("/retention/cleanup")
async def trigger_cleanup(user_info: dict = Depends(get_current_user)):
    tenant_id = user_info["tenant"]["id"]
    return await retention_service.cleanup_tenant_executions(tenant_id)
```

## Configuration (from settings.py)

The service reads these values from `app/core/config.py`:
- `EXECUTION_RETENTION_ENABLED` (bool) - Default: True
- `EXECUTION_RETENTION_DAYS` (int) - Default: 90
- `RETENTION_JOB_BATCH_SIZE` (int) - Default: 1000
- `RETENTION_JOB_SCHEDULE_CRON` (str) - Default: "0 2 * * *" (daily at 2 AM)

## Database Integration

The service uses tables/functions from the T002 migration:
- Table: `execution_retention_policies`
- Function: `cleanup_old_executions(tenant_id, retention_days, min_keep, batch_size)`

## Error Handling

All methods handle errors gracefully:
- Returns error information in results (doesn't raise)
- Falls back to system defaults on policy lookup failures
- Logs all errors with context for debugging

## Safety Features

✅ Respects `is_enabled` flag (can override with `force=True`)
✅ Never deletes below `min_executions_to_keep` threshold
✅ Batch processing to avoid long database locks
✅ Preview mode for testing impact before enabling
✅ Comprehensive logging at all stages
