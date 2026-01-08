# Downgrade Grace Period Tracking

## Overview

The `downgrade_grace_periods` table tracks resources that exceed plan limits after a tenant downgrades to a lower-tier plan. This system provides a grace period before taking action (e.g., making resources read-only, disabling, or scheduling deletion).

## Database Schema

### Table: `downgrade_grace_periods`

Tracks individual resources in grace period after plan downgrades.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `tenant_id` | UUID | References `tenants(id)`, cascades on delete |
| `resource_type` | VARCHAR(50) | Type of resource: `environment`, `team_member`, `workflow`, `execution`, `audit_log`, or `snapshot` |
| `resource_id` | VARCHAR(255) | ID of the specific resource |
| `action` | VARCHAR(50) | Action to take when expired: `read_only`, `schedule_deletion`, `disable`, `immediate_delete`, `warn_only`, or `archive` |
| `status` | VARCHAR(50) | Current status: `active`, `warning`, `expired`, `resolved`, or `cancelled` |
| `starts_at` | TIMESTAMPTZ | When the grace period started |
| `expires_at` | TIMESTAMPTZ | When the grace period expires |
| `reason` | TEXT | Human-readable reason |
| `metadata` | JSONB | Additional metadata |
| `created_at` | TIMESTAMPTZ | Record creation time |
| `updated_at` | TIMESTAMPTZ | Last update time |

### Indexes

- `ix_downgrade_grace_periods_tenant_id`: Lookup by tenant
- `ix_downgrade_grace_periods_tenant_status`: Lookup by tenant + status
- `ix_downgrade_grace_periods_expires_at`: Find expiring grace periods (partial index on `status = 'active'`)
- `ix_downgrade_grace_periods_resource`: Lookup by tenant + resource type + resource ID
- `uix_downgrade_grace_periods_active_resource`: Unique constraint preventing duplicate active grace periods for same resource

## Usage Flow

### 1. Plan Downgrade Detected

When a Stripe webhook confirms a plan downgrade:

```python
from app.services.downgrade_service import downgrade_service

# Handle the downgrade
summary = await downgrade_service.handle_plan_downgrade(
    tenant_id="...",
    old_plan="pro",
    new_plan="free"
)
```

### 2. Grace Period Created

For each over-limit resource, a grace period record is created:

```python
grace_id = await downgrade_service.initiate_grace_period(
    tenant_id="...",
    resource_type=ResourceType.ENVIRONMENT,
    resource_id="env-123",
    reason="Plan downgrade from Pro to Free"
)
```

### 3. Grace Period Monitoring

A scheduled job checks for:
- **Expiring soon**: Grace periods expiring within 7 days (send warnings)
- **Expired**: Grace periods past expiry date (take action)

```python
# Find expiring soon (for warnings)
expiring = await downgrade_service.get_expiring_grace_periods(days_threshold=7)

# Find expired (for action)
expired = await downgrade_service.get_expired_grace_periods()
```

### 4. Action Execution

When grace period expires:

```python
for grace_period in expired:
    # Execute the action (read_only, disable, schedule_deletion, etc.)
    success = await downgrade_service.execute_downgrade_action(grace_period)

    if success:
        # Mark as expired
        await downgrade_service.mark_grace_period_expired(grace_period["id"])
```

### 5. Cancellation (Upgrade or Manual)

If user upgrades or manually removes resource:

```python
await downgrade_service.cancel_grace_period(
    tenant_id="...",
    resource_type=ResourceType.ENVIRONMENT,
    resource_id="env-123"
)
```

## Grace Period Policies

Default grace periods by resource type:

| Resource Type | Grace Period | Action |
|--------------|--------------|--------|
| Environment | 30 days | Read-only |
| Team Member | 14 days | Disable |
| Workflow | 30 days | Read-only |
| Snapshot | 7 days | Schedule deletion |
| Execution | 0 days | Schedule deletion (via retention) |
| Audit Log | 0 days | Schedule deletion (via retention) |

See `app/core/downgrade_policy.py` for full configuration.

## Integration Points

### Webhook Handler (`app/api/endpoints/billing.py`)

```python
# After subscription.updated event
if is_downgrade:
    await downgrade_service.handle_plan_downgrade(
        tenant_id, old_plan, new_plan
    )
```

### Scheduled Job (Background Worker)

```python
# Check for expired grace periods (runs daily)
expired = await downgrade_service.get_expired_grace_periods()
for grace_period in expired:
    await downgrade_service.execute_downgrade_action(grace_period)
```

### API Endpoints

Can query active grace periods for a tenant:

```python
grace_periods = await downgrade_service.get_active_grace_periods(
    tenant_id="...",
    resource_type=ResourceType.ENVIRONMENT  # Optional filter
)
```

## Status Transitions

```
active → warning   (approaching expiry, warnings sent)
active → resolved  (user upgraded or removed resource)
active → cancelled (manually cancelled)
active → expired   (grace period ended, action taken)
```

## Pydantic Models

See `app/schemas/downgrade.py`:

- `DowngradeGracePeriodCreate`: Create new grace period
- `DowngradeGracePeriodUpdate`: Update grace period
- `DowngradeGracePeriodResponse`: Response model
- `GracePeriodSummary`: Summary for tenant dashboard

## Migration

Migration: `380513d302f0_add_downgrade_grace_periods_table.py`

To apply:
```bash
alembic upgrade head
```

To rollback:
```bash
alembic downgrade -1
```

## Monitoring & Alerting

Key queries for monitoring:

```sql
-- Active grace periods by tenant
SELECT tenant_id, resource_type, COUNT(*)
FROM downgrade_grace_periods
WHERE status = 'active'
GROUP BY tenant_id, resource_type;

-- Grace periods expiring soon
SELECT * FROM downgrade_grace_periods
WHERE status = 'active'
  AND expires_at < NOW() + INTERVAL '7 days'
ORDER BY expires_at;

-- Expired grace periods needing action
SELECT * FROM downgrade_grace_periods
WHERE status = 'active'
  AND expires_at < NOW()
ORDER BY expires_at;
```

## Related Files

- **Schema**: `app/schemas/downgrade.py`
- **Service**: `app/services/downgrade_service.py`
- **Policy**: `app/core/downgrade_policy.py`
- **Migration**: `alembic/versions/380513d302f0_add_downgrade_grace_periods_table.py`
- **Webhook**: `app/api/endpoints/billing.py`
- **Scheduled Job**: `app/services/background_jobs/retention_job.py` (or separate downgrade job)
