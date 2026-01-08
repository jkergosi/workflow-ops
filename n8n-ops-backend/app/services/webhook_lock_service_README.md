# Webhook Lock Service

## Overview

The Webhook Lock Service provides distributed locking for Stripe webhook processing to prevent race conditions when multiple webhook events are received concurrently for the same tenant.

## Problem Statement

When Stripe sends multiple webhook events concurrently (e.g., subscription.updated and invoice.payment_succeeded), these events can create race conditions that lead to:

- Inconsistent plan assignments
- Duplicate database updates
- Data corruption in subscription state
- Incorrect entitlement calculations

## Solution

This service implements distributed locks using **PostgreSQL Advisory Locks**, which provide:

- ✅ Database-native locking (no Redis required)
- ✅ Automatic cleanup on connection termination
- ✅ Session-level isolation
- ✅ High performance (in-memory locks)

## Architecture

### Components

1. **Lock Key Generation**: Deterministic hashing of `tenant_id` + `lock_type` to create numeric lock identifiers
2. **Lock Acquisition**: Non-blocking attempts with exponential backoff retry
3. **Lock Release**: Explicit release with automatic cleanup on context exit
4. **Context Manager**: Safe lock management with guaranteed release

### PostgreSQL Advisory Locks

PostgreSQL advisory locks are:
- Session-level locks stored in shared memory
- Automatically released when the connection/session closes
- Available in two forms: `pg_advisory_lock` (blocking) and `pg_try_advisory_lock` (non-blocking)
- Identified by a 64-bit integer key

## Usage

### Basic Usage

```python
from app.services.webhook_lock_service import webhook_lock_service

async def process_webhook(tenant_id: str, webhook_data: dict):
    """Process a webhook with locking to prevent race conditions"""

    # Acquire lock for tenant's webhook processing
    async with webhook_lock_service.acquire_webhook_lock(tenant_id) as locked:
        if locked:
            # Lock acquired - safe to process webhook
            await handle_subscription_update(tenant_id, webhook_data)
        else:
            # Lock timeout - another webhook is still processing
            logger.warning(f"Webhook lock timeout for tenant {tenant_id}")
            # Could retry later or return error
```

### Custom Lock Types

Use different lock types for different operations:

```python
# Lock for subscription updates
async with webhook_lock_service.acquire_webhook_lock(
    tenant_id,
    lock_type="subscription"
) as locked:
    if locked:
        await update_subscription(tenant_id)

# Lock for invoice processing
async with webhook_lock_service.acquire_webhook_lock(
    tenant_id,
    lock_type="invoice"
) as locked:
    if locked:
        await process_invoice(tenant_id)
```

### Custom Timeout

Adjust timeout for different operations:

```python
# Short timeout for quick operations
async with webhook_lock_service.acquire_webhook_lock(
    tenant_id,
    timeout_seconds=10
) as locked:
    if locked:
        await quick_operation()

# Longer timeout for complex operations
async with webhook_lock_service.acquire_webhook_lock(
    tenant_id,
    timeout_seconds=60
) as locked:
    if locked:
        await complex_operation()
```

### Integration with Stripe Webhooks

```python
@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks with distributed locking"""
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        # Verify webhook signature
        event = stripe_service.construct_webhook_event(payload, sig_header)

        # Extract tenant_id from event metadata
        tenant_id = extract_tenant_id(event)

        if not tenant_id:
            return {"status": "error", "message": "No tenant_id in event"}

        # Acquire lock before processing
        async with webhook_lock_service.acquire_webhook_lock(tenant_id) as locked:
            if not locked:
                # Lock timeout - log and return retry status
                logger.error(f"Webhook lock timeout for tenant {tenant_id}, event {event.type}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Webhook processing locked, please retry"
                )

            # Process webhook with lock held
            if event.type == "customer.subscription.updated":
                await handle_subscription_updated(event.data.object)
            elif event.type == "customer.subscription.deleted":
                await handle_subscription_deleted(event.data.object)
            # ... other event types

        return {"status": "success"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook error: {str(e)}"
        )
```

## API Reference

### `WebhookLockService`

#### `acquire_webhook_lock(tenant_id, lock_type="webhook", timeout_seconds=None)`

Context manager for acquiring a webhook lock.

**Parameters:**
- `tenant_id` (str): The tenant to lock for
- `lock_type` (str, optional): Lock namespace (default: "webhook")
- `timeout_seconds` (int, optional): Lock acquisition timeout (default: 30s)

**Returns:**
- AsyncContextManager[bool]: Yields True if lock acquired, False if timeout

**Example:**
```python
async with webhook_lock_service.acquire_webhook_lock("tenant-123") as locked:
    if locked:
        # Process with lock held
        pass
```

#### `check_lock_status(tenant_id, lock_type="webhook")`

Check if a lock is currently held.

**Parameters:**
- `tenant_id` (str): The tenant to check
- `lock_type` (str, optional): Lock type to check (default: "webhook")

**Returns:**
- dict: Lock status information

**Example:**
```python
status = await webhook_lock_service.check_lock_status("tenant-123")
# {'tenant_id': 'tenant-123', 'lock_type': 'webhook', 'is_locked': False, 'available': True}
```

#### `force_release_lock(tenant_id, lock_type="webhook")`

Force release a lock (emergency use only).

**Parameters:**
- `tenant_id` (str): The tenant whose lock to release
- `lock_type` (str, optional): Lock type to release (default: "webhook")

**Returns:**
- bool: True if released, False otherwise

**Note:** Only works within the same session that acquired the lock.

## Configuration

### Constants

```python
# Default timeout for lock acquisition (seconds)
DEFAULT_LOCK_TIMEOUT = 30

# Maximum time a lock can be held (seconds)
MAX_LOCK_HOLD_TIME = 120
```

### Customization

To customize default behavior, modify the class constants:

```python
from app.services.webhook_lock_service import webhook_lock_service

# Change default timeout
webhook_lock_service.DEFAULT_LOCK_TIMEOUT = 60
```

## Monitoring & Debugging

### Logging

The service logs all lock operations:

```
INFO: Acquired advisory lock 1234567890
INFO: Webhook lock acquired for tenant tenant-123 (lock_type=webhook, key=1234567890)
INFO: Released advisory lock 1234567890
WARNING: Webhook lock timeout for tenant tenant-123 after 30.0s
ERROR: Failed to acquire lock 1234567890
```

### Health Checks

Check lock status for monitoring:

```python
status = await webhook_lock_service.check_lock_status(tenant_id)
if status.get("is_locked"):
    logger.warning(f"Lock still held for tenant {tenant_id}")
```

### Debugging Stuck Locks

If a lock appears stuck:

1. **Check Session Status**: Query PostgreSQL for active sessions
   ```sql
   SELECT * FROM pg_stat_activity WHERE state = 'active';
   ```

2. **View Advisory Locks**: Check currently held locks
   ```sql
   SELECT * FROM pg_locks WHERE locktype = 'advisory';
   ```

3. **Force Release**: Emergency release (use with caution)
   ```python
   await webhook_lock_service.force_release_lock(tenant_id)
   ```

## Testing

### Unit Tests

Run unit tests with mocked database:

```bash
pytest tests/test_webhook_lock_service.py -v
```

### Integration Tests

Run integration tests with real database:

```bash
pytest tests/test_webhook_lock_service.py -v -m integration
```

## Performance Considerations

### Lock Overhead

- **Acquisition Time**: ~1-5ms for uncontended locks
- **Release Time**: ~1-3ms
- **Memory**: Minimal (advisory locks stored in shared memory)

### Scalability

- PostgreSQL advisory locks scale well to thousands of concurrent locks
- Each lock uses minimal memory (just the 64-bit key)
- No external dependencies (Redis, etc.)

### Retry Strategy

The service uses exponential backoff for lock acquisition:
- Initial delay: 100ms
- Max delay: 2000ms
- Growth factor: 1.5x

## Error Handling

### Lock Acquisition Timeout

```python
async with webhook_lock_service.acquire_webhook_lock(tenant_id) as locked:
    if not locked:
        # Handle timeout
        logger.warning("Could not acquire lock")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
```

### Lock Release Failure

Lock release failures are logged but don't raise exceptions. PostgreSQL automatically cleans up locks when:
- Session closes
- Connection terminates
- Process crashes

### Database Errors

Database errors during lock operations are caught and logged, returning False for failed operations.

## Best Practices

1. **Always use context manager**: Ensures lock is released even on exceptions
2. **Keep critical sections short**: Release locks as soon as possible
3. **Use specific lock types**: Different operations should use different lock namespaces
4. **Set appropriate timeouts**: Balance between waiting and failing fast
5. **Log lock operations**: Track lock acquisition/release for debugging
6. **Monitor for deadlocks**: Though rare with advisory locks, monitor for unusual patterns

## Troubleshooting

### Problem: Lock timeout on valid operations

**Solution**: Increase timeout or investigate slow operations

```python
async with webhook_lock_service.acquire_webhook_lock(
    tenant_id,
    timeout_seconds=60  # Increase from default 30s
) as locked:
    pass
```

### Problem: Locks not being released

**Solution**: Verify context manager is being used correctly and check for exceptions

### Problem: Different sessions getting same lock

**Solution**: Verify lock_type and tenant_id are unique per operation

## Migration Notes

### From Redis-based Locks

If migrating from Redis-based locks:

1. Replace Redis connection with database connection
2. Update lock acquisition code to use new API
3. Update monitoring/alerting for PostgreSQL advisory locks
4. Test thoroughly in staging environment

### Database Requirements

- PostgreSQL 9.2+ (advisory locks introduced in 9.2)
- No additional extensions required
- Works with Supabase/RDS/self-hosted PostgreSQL

## Future Enhancements

Potential improvements:

- [ ] Distributed tracing integration
- [ ] Metrics/monitoring dashboard
- [ ] Automatic deadlock detection
- [ ] Lock queue visibility
- [ ] Priority-based lock acquisition

## Support

For issues or questions:
1. Check logs for error messages
2. Verify database connectivity
3. Test with `check_lock_status()`
4. Review PostgreSQL advisory lock documentation
