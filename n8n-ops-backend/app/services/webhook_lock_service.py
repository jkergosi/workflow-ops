"""
Webhook Lock Service

Provides distributed locking mechanism for Stripe webhook processing
to prevent race conditions from concurrent webhook events.

Uses PostgreSQL advisory locks for distributed synchronization without
requiring Redis. Advisory locks are automatically released on connection
close or transaction commit/rollback.
"""
import logging
import asyncio
from typing import Optional, AsyncContextManager
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from app.services.database import db_service

logger = logging.getLogger(__name__)


class WebhookLockService:
    """
    Service for managing distributed locks during webhook processing.

    Prevents race conditions when processing concurrent Stripe webhooks
    for the same tenant by using PostgreSQL advisory locks.
    """

    # Lock timeout in seconds (how long to wait for a lock)
    DEFAULT_LOCK_TIMEOUT = 30

    # Maximum lock hold time in seconds (safety limit)
    MAX_LOCK_HOLD_TIME = 120

    def __init__(self):
        self.db_service = db_service

    def _generate_lock_key(self, tenant_id: str, lock_type: str = "webhook") -> int:
        """
        Generate a numeric lock key from tenant_id and lock_type.

        PostgreSQL advisory locks require a 64-bit integer key.
        We use a hash of the combined string to generate this.

        Args:
            tenant_id: The tenant identifier
            lock_type: Type of lock (e.g., "webhook", "subscription")

        Returns:
            A 64-bit integer lock key
        """
        # Create a stable hash from tenant_id and lock_type
        combined = f"{lock_type}:{tenant_id}"
        # Use Python's hash() but ensure it's within PostgreSQL's bigint range
        # PostgreSQL bigint: -9223372036854775808 to 9223372036854775807
        hash_value = hash(combined)
        # Ensure the value is within PostgreSQL's bigint range
        lock_key = hash_value % (2**63 - 1)
        return lock_key

    async def _acquire_lock(
        self,
        lock_key: int,
        timeout_seconds: int = DEFAULT_LOCK_TIMEOUT
    ) -> bool:
        """
        Attempt to acquire an advisory lock with timeout.

        Uses pg_try_advisory_lock for non-blocking lock acquisition with retry logic.

        Args:
            lock_key: The numeric lock identifier
            timeout_seconds: How long to wait for the lock

        Returns:
            True if lock was acquired, False if timeout
        """
        start_time = datetime.now()
        retry_delay = 0.1  # Start with 100ms delay
        max_retry_delay = 2.0  # Cap at 2 seconds

        while True:
            try:
                # Try to acquire the lock (non-blocking)
                result = self.db_service.client.rpc(
                    'pg_try_advisory_lock',
                    {'key': lock_key}
                ).execute()

                if result.data:
                    logger.info(f"Acquired advisory lock {lock_key}")
                    return True

                # Check if we've exceeded timeout
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= timeout_seconds:
                    logger.warning(
                        f"Failed to acquire lock {lock_key} after {elapsed:.2f}s timeout"
                    )
                    return False

                # Wait before retrying with exponential backoff
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, max_retry_delay)

            except Exception as e:
                logger.error(f"Error acquiring lock {lock_key}: {str(e)}")
                return False

    async def _release_lock(self, lock_key: int) -> bool:
        """
        Release an advisory lock.

        Args:
            lock_key: The numeric lock identifier

        Returns:
            True if lock was released, False if error
        """
        try:
            result = self.db_service.client.rpc(
                'pg_advisory_unlock',
                {'key': lock_key}
            ).execute()

            if result.data:
                logger.info(f"Released advisory lock {lock_key}")
                return True
            else:
                logger.warning(f"Lock {lock_key} was not held by this session")
                return False

        except Exception as e:
            logger.error(f"Error releasing lock {lock_key}: {str(e)}")
            return False

    @asynccontextmanager
    async def acquire_webhook_lock(
        self,
        tenant_id: str,
        lock_type: str = "webhook",
        timeout_seconds: Optional[int] = None
    ) -> AsyncContextManager[bool]:
        """
        Context manager for acquiring a webhook lock.

        Usage:
            async with webhook_lock_service.acquire_webhook_lock(tenant_id) as locked:
                if locked:
                    # Process webhook safely
                    pass
                else:
                    # Handle lock timeout
                    pass

        Args:
            tenant_id: The tenant to lock for
            lock_type: Type of lock (allows different lock namespaces)
            timeout_seconds: How long to wait for the lock (uses default if None)

        Yields:
            bool: True if lock was acquired, False if timeout
        """
        timeout = timeout_seconds or self.DEFAULT_LOCK_TIMEOUT
        lock_key = self._generate_lock_key(tenant_id, lock_type)
        lock_acquired = False

        try:
            # Attempt to acquire the lock
            lock_acquired = await self._acquire_lock(lock_key, timeout)

            if lock_acquired:
                logger.info(
                    f"Webhook lock acquired for tenant {tenant_id} "
                    f"(lock_type={lock_type}, key={lock_key})"
                )
            else:
                logger.warning(
                    f"Webhook lock timeout for tenant {tenant_id} "
                    f"after {timeout}s (lock_type={lock_type}, key={lock_key})"
                )

            # Yield control to the caller
            yield lock_acquired

        finally:
            # Always attempt to release the lock if we acquired it
            if lock_acquired:
                released = await self._release_lock(lock_key)
                if released:
                    logger.info(
                        f"Webhook lock released for tenant {tenant_id} "
                        f"(lock_type={lock_type}, key={lock_key})"
                    )
                else:
                    logger.error(
                        f"Failed to release webhook lock for tenant {tenant_id} "
                        f"(lock_type={lock_type}, key={lock_key})"
                    )

    async def check_lock_status(
        self,
        tenant_id: str,
        lock_type: str = "webhook"
    ) -> dict:
        """
        Check if a lock is currently held (for debugging/monitoring).

        Args:
            tenant_id: The tenant to check
            lock_type: Type of lock to check

        Returns:
            Dict with lock status information
        """
        lock_key = self._generate_lock_key(tenant_id, lock_type)

        try:
            # Try to acquire the lock (non-blocking)
            result = self.db_service.client.rpc(
                'pg_try_advisory_lock',
                {'key': lock_key}
            ).execute()

            if result.data:
                # Lock was available, release it immediately
                await self._release_lock(lock_key)
                return {
                    "tenant_id": tenant_id,
                    "lock_type": lock_type,
                    "lock_key": lock_key,
                    "is_locked": False,
                    "available": True
                }
            else:
                # Lock is held by another session
                return {
                    "tenant_id": tenant_id,
                    "lock_type": lock_type,
                    "lock_key": lock_key,
                    "is_locked": True,
                    "available": False
                }

        except Exception as e:
            logger.error(f"Error checking lock status for {lock_key}: {str(e)}")
            return {
                "tenant_id": tenant_id,
                "lock_type": lock_type,
                "lock_key": lock_key,
                "error": str(e)
            }

    async def force_release_lock(
        self,
        tenant_id: str,
        lock_type: str = "webhook"
    ) -> bool:
        """
        Force release a lock (emergency use only).

        Note: This only works if called from the same database session
        that acquired the lock. For stuck locks from terminated sessions,
        PostgreSQL will automatically clean them up.

        Args:
            tenant_id: The tenant whose lock to release
            lock_type: Type of lock to release

        Returns:
            True if released, False otherwise
        """
        lock_key = self._generate_lock_key(tenant_id, lock_type)
        logger.warning(
            f"Force releasing lock for tenant {tenant_id} "
            f"(lock_type={lock_type}, key={lock_key})"
        )
        return await self._release_lock(lock_key)


# Global service instance
webhook_lock_service = WebhookLockService()
