# Execution Retention API Documentation

## Overview

The Execution Retention API provides tenant-level management of execution data retention policies. These endpoints allow tenants to configure automatic cleanup of old execution data to prevent unbounded database growth and maintain optimal query performance.

**Base URL:** `/api/v1/retention`

**Authentication:** All endpoints require authentication via bearer token (Supabase JWT).

---

## Endpoints

### 1. Get Retention Policy

**GET** `/policy`

Retrieves the current execution retention policy for the authenticated tenant.

#### Request

```http
GET /api/v1/retention/policy
Authorization: Bearer <token>
```

#### Response (200 OK)

```json
{
  "retention_days": 90,
  "is_enabled": true,
  "min_executions_to_keep": 100,
  "last_cleanup_at": "2024-03-15T02:00:00.000Z",
  "last_cleanup_deleted_count": 45000
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `retention_days` | integer | Number of days to retain executions (1-365) |
| `is_enabled` | boolean | Whether automatic retention cleanup is enabled |
| `min_executions_to_keep` | integer | Minimum executions to preserve (safety threshold) |
| `last_cleanup_at` | string (ISO 8601) | Timestamp of last cleanup operation (null if never run) |
| `last_cleanup_deleted_count` | integer | Number of executions deleted in last cleanup |

#### Error Responses

- **401 Unauthorized:** Missing or invalid authentication token
- **500 Internal Server Error:** Database or service error

---

### 2. Create Retention Policy

**POST** `/policy`

Creates or updates the execution retention policy for the authenticated tenant.

#### Request

```http
POST /api/v1/retention/policy
Authorization: Bearer <token>
Content-Type: application/json

{
  "retention_days": 60,
  "is_enabled": true,
  "min_executions_to_keep": 200
}
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `retention_days` | integer | Yes | Retention period in days (1-365) |
| `is_enabled` | boolean | Yes | Enable automatic cleanup |
| `min_executions_to_keep` | integer | Yes | Safety threshold (≥0) |

#### Response (200 OK)

```json
{
  "retention_days": 60,
  "is_enabled": true,
  "min_executions_to_keep": 200,
  "last_cleanup_at": null,
  "last_cleanup_deleted_count": 0
}
```

#### Error Responses

- **400 Bad Request:** Invalid request body
- **401 Unauthorized:** Missing or invalid authentication token
- **422 Unprocessable Entity:** Validation error (e.g., retention_days out of range)
- **500 Internal Server Error:** Database or service error

---

### 3. Update Retention Policy

**PATCH** `/policy`

Updates specific fields of the retention policy for the authenticated tenant.

#### Request

```http
PATCH /api/v1/retention/policy
Authorization: Bearer <token>
Content-Type: application/json

{
  "is_enabled": false
}
```

#### Request Body (all fields optional, at least one required)

| Field | Type | Description |
|-------|------|-------------|
| `retention_days` | integer | New retention period (1-365) |
| `is_enabled` | boolean | Enable/disable automatic cleanup |
| `min_executions_to_keep` | integer | New safety threshold (≥0) |

#### Response (200 OK)

```json
{
  "retention_days": 90,
  "is_enabled": false,
  "min_executions_to_keep": 100,
  "last_cleanup_at": "2024-03-15T02:00:00.000Z",
  "last_cleanup_deleted_count": 45000
}
```

#### Error Responses

- **400 Bad Request:** Empty request body or validation error
- **401 Unauthorized:** Missing or invalid authentication token
- **422 Unprocessable Entity:** Validation error
- **500 Internal Server Error:** Database or service error

---

### 4. Preview Cleanup

**GET** `/preview`

Previews what would be deleted by a retention cleanup operation without actually deleting anything.

#### Request

```http
GET /api/v1/retention/preview
Authorization: Bearer <token>
```

#### Response (200 OK)

```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_executions": 150000,
  "old_executions_count": 50000,
  "executions_to_delete": 49900,
  "cutoff_date": "2024-01-01T00:00:00.000Z",
  "retention_days": 90,
  "min_executions_to_keep": 100,
  "would_delete": true,
  "is_enabled": true
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `tenant_id` | string (UUID) | Tenant identifier |
| `total_executions` | integer | Current total execution count |
| `old_executions_count` | integer | Executions older than retention period |
| `executions_to_delete` | integer | Actual count that would be deleted (respects min_executions_to_keep) |
| `cutoff_date` | string (ISO 8601) | Retention cutoff timestamp |
| `retention_days` | integer | Current retention period |
| `min_executions_to_keep` | integer | Current safety threshold |
| `would_delete` | boolean | Whether any deletions would occur |
| `is_enabled` | boolean | Current enabled status |

#### Use Cases

- Understanding impact before enabling retention
- Verifying retention settings are correct
- Planning cleanup operations
- Monitoring execution growth trends

#### Error Responses

- **401 Unauthorized:** Missing or invalid authentication token
- **500 Internal Server Error:** Database or service error

---

### 5. Trigger Cleanup

**POST** `/cleanup`

Manually triggers execution retention cleanup for the authenticated tenant.

⚠️ **Warning:** This operation permanently deletes old execution data. Use `/preview` first to understand the impact.

#### Request

```http
POST /api/v1/retention/cleanup?force=false
Authorization: Bearer <token>
```

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `force` | boolean | false | Force cleanup even if retention is disabled |

#### Response (200 OK)

```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "deleted_count": 45000,
  "retention_days": 90,
  "is_enabled": true,
  "timestamp": "2024-04-01T12:00:00.000Z",
  "summary": {
    "before_count": 150000,
    "after_count": 105000,
    "oldest_execution": "2023-01-01T00:00:00.000Z",
    "newest_execution": "2024-04-01T11:59:59.000Z"
  },
  "skipped": false,
  "reason": null
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `tenant_id` | string (UUID) | Tenant identifier |
| `deleted_count` | integer | Number of executions deleted |
| `retention_days` | integer | Retention period used |
| `is_enabled` | boolean | Whether retention was enabled |
| `timestamp` | string (ISO 8601) | Cleanup completion timestamp |
| `summary` | object | Detailed execution statistics (optional) |
| `skipped` | boolean | Whether cleanup was skipped |
| `reason` | string | Reason for skipping (if skipped) |

#### Skipped Cleanup Response

When retention is disabled and `force=false`:

```json
{
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
  "deleted_count": 0,
  "retention_days": 90,
  "is_enabled": false,
  "timestamp": "2024-04-01T12:00:00.000Z",
  "summary": null,
  "skipped": true,
  "reason": "Retention disabled for tenant"
}
```

#### Error Responses

- **401 Unauthorized:** Missing or invalid authentication token
- **500 Internal Server Error:** Database or service error

#### Notes

- Cleanup is typically run automatically on a schedule (daily at 2 AM by default)
- Manual triggers are useful for:
  - Immediate cleanup after policy changes
  - Testing retention configuration
  - On-demand database optimization
- Deleted executions cannot be recovered
- The operation processes data in batches to avoid database locks
- The `min_executions_to_keep` safety threshold is always respected

---

## Common Workflows

### Initial Setup

1. **Get current policy** to see defaults
2. **Create policy** with desired settings
3. **Preview cleanup** to verify impact
4. **Enable policy** if preview looks correct

```bash
# 1. Check current policy
curl -X GET https://api.example.com/api/v1/retention/policy \
  -H "Authorization: Bearer $TOKEN"

# 2. Create custom policy
curl -X POST https://api.example.com/api/v1/retention/policy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "retention_days": 60,
    "is_enabled": false,
    "min_executions_to_keep": 200
  }'

# 3. Preview impact
curl -X GET https://api.example.com/api/v1/retention/preview \
  -H "Authorization: Bearer $TOKEN"

# 4. Enable if preview is acceptable
curl -X PATCH https://api.example.com/api/v1/retention/policy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_enabled": true}'
```

### Emergency Cleanup

Immediately clean up old data when storage is critical:

```bash
# Force cleanup even if disabled
curl -X POST https://api.example.com/api/v1/retention/cleanup?force=true \
  -H "Authorization: Bearer $TOKEN"
```

### Adjust Retention Period

Change retention period while keeping other settings:

```bash
curl -X PATCH https://api.example.com/api/v1/retention/policy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 120}'
```

---

## Configuration

Default retention settings are defined in the backend configuration:

```python
# app/core/config.py
EXECUTION_RETENTION_ENABLED: bool = True
EXECUTION_RETENTION_DAYS: int = 90
RETENTION_JOB_BATCH_SIZE: int = 1000
RETENTION_JOB_SCHEDULE_CRON: str = "0 2 * * *"  # Daily at 2 AM
```

These defaults are used when a tenant hasn't created a custom policy.

---

## Security

- All endpoints require authentication via Supabase JWT
- Each tenant can only access their own retention policy
- Tenant ID is extracted from the authenticated user's context
- Manual cleanup operations are logged for audit purposes

---

## Related

- **Service:** `app/services/retention_service.py`
- **Migration:** `migrations/xxx_add_retention_policy.sql`
- **Config:** `app/core/config.py`
- **Tests:** `tests/test_retention_api.py`
- **Admin API:** `/api/v1/admin/retention` (platform admin endpoints for drift retention)
