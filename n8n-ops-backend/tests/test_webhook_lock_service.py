"""
Tests for Webhook Lock Service

Tests the distributed locking mechanism for webhook processing.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from app.services.webhook_lock_service import WebhookLockService, webhook_lock_service


class TestWebhookLockService:
    """Test suite for WebhookLockService"""

    @pytest.fixture
    def service(self):
        """Create a WebhookLockService instance for testing"""
        return WebhookLockService()

    @pytest.fixture
    def mock_db_service(self):
        """Mock database service"""
        mock_db = MagicMock()
        mock_db.client = MagicMock()
        return mock_db

    def test_generate_lock_key_consistency(self, service):
        """Test that lock key generation is consistent for same inputs"""
        tenant_id = "tenant-123"
        lock_type = "webhook"

        key1 = service._generate_lock_key(tenant_id, lock_type)
        key2 = service._generate_lock_key(tenant_id, lock_type)

        assert key1 == key2, "Lock keys should be consistent for same inputs"
        assert isinstance(key1, int), "Lock key should be an integer"

    def test_generate_lock_key_different_tenants(self, service):
        """Test that different tenants get different lock keys"""
        tenant_id1 = "tenant-123"
        tenant_id2 = "tenant-456"
        lock_type = "webhook"

        key1 = service._generate_lock_key(tenant_id1, lock_type)
        key2 = service._generate_lock_key(tenant_id2, lock_type)

        assert key1 != key2, "Different tenants should have different lock keys"

    def test_generate_lock_key_different_lock_types(self, service):
        """Test that different lock types get different keys for same tenant"""
        tenant_id = "tenant-123"
        lock_type1 = "webhook"
        lock_type2 = "subscription"

        key1 = service._generate_lock_key(tenant_id, lock_type1)
        key2 = service._generate_lock_key(tenant_id, lock_type2)

        assert key1 != key2, "Different lock types should have different keys"

    def test_generate_lock_key_within_bigint_range(self, service):
        """Test that generated lock keys are within PostgreSQL bigint range"""
        tenant_id = "tenant-123"
        lock_type = "webhook"

        key = service._generate_lock_key(tenant_id, lock_type)

        # PostgreSQL bigint range: -9223372036854775808 to 9223372036854775807
        min_bigint = -(2**63)
        max_bigint = 2**63 - 1

        assert min_bigint <= key <= max_bigint, \
            "Lock key must be within PostgreSQL bigint range"

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, service, mock_db_service):
        """Test successful lock acquisition"""
        with patch.object(service, 'db_service', mock_db_service):
            # Mock successful lock acquisition
            mock_result = MagicMock()
            mock_result.data = True
            mock_db_service.client.rpc.return_value.execute.return_value = mock_result

            lock_key = 12345
            result = await service._acquire_lock(lock_key, timeout_seconds=5)

            assert result is True, "Lock should be acquired successfully"
            mock_db_service.client.rpc.assert_called_with(
                'pg_try_advisory_lock',
                {'key': lock_key}
            )

    @pytest.mark.asyncio
    async def test_acquire_lock_timeout(self, service, mock_db_service):
        """Test lock acquisition timeout"""
        with patch.object(service, 'db_service', mock_db_service):
            # Mock lock always unavailable
            mock_result = MagicMock()
            mock_result.data = False
            mock_db_service.client.rpc.return_value.execute.return_value = mock_result

            lock_key = 12345
            # Use very short timeout for test
            result = await service._acquire_lock(lock_key, timeout_seconds=0.5)

            assert result is False, "Lock acquisition should timeout"

    @pytest.mark.asyncio
    async def test_release_lock_success(self, service, mock_db_service):
        """Test successful lock release"""
        with patch.object(service, 'db_service', mock_db_service):
            # Mock successful lock release
            mock_result = MagicMock()
            mock_result.data = True
            mock_db_service.client.rpc.return_value.execute.return_value = mock_result

            lock_key = 12345
            result = await service._release_lock(lock_key)

            assert result is True, "Lock should be released successfully"
            mock_db_service.client.rpc.assert_called_with(
                'pg_advisory_unlock',
                {'key': lock_key}
            )

    @pytest.mark.asyncio
    async def test_release_lock_not_held(self, service, mock_db_service):
        """Test releasing a lock that wasn't held"""
        with patch.object(service, 'db_service', mock_db_service):
            # Mock lock not held
            mock_result = MagicMock()
            mock_result.data = False
            mock_db_service.client.rpc.return_value.execute.return_value = mock_result

            lock_key = 12345
            result = await service._release_lock(lock_key)

            assert result is False, "Should return False when lock wasn't held"

    @pytest.mark.asyncio
    async def test_acquire_webhook_lock_context_manager_success(self, service, mock_db_service):
        """Test webhook lock context manager with successful acquisition"""
        with patch.object(service, 'db_service', mock_db_service):
            # Mock successful lock acquisition and release
            mock_result = MagicMock()
            mock_result.data = True
            mock_db_service.client.rpc.return_value.execute.return_value = mock_result

            tenant_id = "tenant-123"
            lock_acquired = False

            async with service.acquire_webhook_lock(tenant_id) as locked:
                lock_acquired = locked
                assert locked is True, "Lock should be acquired"

            assert lock_acquired is True, "Lock should have been acquired in context"

    @pytest.mark.asyncio
    async def test_acquire_webhook_lock_context_manager_timeout(self, service, mock_db_service):
        """Test webhook lock context manager with timeout"""
        with patch.object(service, 'db_service', mock_db_service):
            # Mock lock acquisition failure (timeout)
            mock_result = MagicMock()
            mock_result.data = False
            mock_db_service.client.rpc.return_value.execute.return_value = mock_result

            tenant_id = "tenant-123"
            lock_acquired = None

            async with service.acquire_webhook_lock(tenant_id, timeout_seconds=0.5) as locked:
                lock_acquired = locked
                assert locked is False, "Lock should timeout"

            assert lock_acquired is False, "Lock should have timed out"

    @pytest.mark.asyncio
    async def test_acquire_webhook_lock_releases_on_exception(self, service, mock_db_service):
        """Test that lock is released even if exception occurs in context"""
        with patch.object(service, 'db_service', mock_db_service):
            # Mock successful lock acquisition and release
            mock_result = MagicMock()
            mock_result.data = True
            mock_db_service.client.rpc.return_value.execute.return_value = mock_result

            tenant_id = "tenant-123"

            with pytest.raises(ValueError):
                async with service.acquire_webhook_lock(tenant_id) as locked:
                    assert locked is True
                    raise ValueError("Test exception")

            # Verify release was called (should be called twice: once for lock, once for unlock)
            assert mock_db_service.client.rpc.call_count >= 2

    @pytest.mark.asyncio
    async def test_check_lock_status_available(self, service, mock_db_service):
        """Test checking lock status when lock is available"""
        with patch.object(service, 'db_service', mock_db_service):
            # Mock lock available
            mock_result = MagicMock()
            mock_result.data = True
            mock_db_service.client.rpc.return_value.execute.return_value = mock_result

            tenant_id = "tenant-123"
            status = await service.check_lock_status(tenant_id)

            assert status["is_locked"] is False
            assert status["available"] is True
            assert status["tenant_id"] == tenant_id

    @pytest.mark.asyncio
    async def test_check_lock_status_locked(self, service, mock_db_service):
        """Test checking lock status when lock is held"""
        with patch.object(service, 'db_service', mock_db_service):
            # Mock lock held
            mock_result = MagicMock()
            mock_result.data = False
            mock_db_service.client.rpc.return_value.execute.return_value = mock_result

            tenant_id = "tenant-123"
            status = await service.check_lock_status(tenant_id)

            assert status["is_locked"] is True
            assert status["available"] is False
            assert status["tenant_id"] == tenant_id

    @pytest.mark.asyncio
    async def test_force_release_lock(self, service, mock_db_service):
        """Test force releasing a lock"""
        with patch.object(service, 'db_service', mock_db_service):
            # Mock successful release
            mock_result = MagicMock()
            mock_result.data = True
            mock_db_service.client.rpc.return_value.execute.return_value = mock_result

            tenant_id = "tenant-123"
            result = await service.force_release_lock(tenant_id)

            assert result is True, "Force release should succeed"

    @pytest.mark.asyncio
    async def test_concurrent_lock_attempts(self, service, mock_db_service):
        """Test that concurrent lock attempts are serialized"""
        with patch.object(service, 'db_service', mock_db_service):
            # Track state: lock is held after first acquisition
            lock_held = False

            def mock_rpc_call(func_name, params):
                nonlocal lock_held
                mock_result = MagicMock()

                if func_name == 'pg_try_advisory_lock':
                    # First attempt acquires, subsequent attempts fail
                    if not lock_held:
                        lock_held = True
                        mock_result.data = True
                    else:
                        mock_result.data = False
                elif func_name == 'pg_advisory_unlock':
                    # Release the lock
                    lock_held = False
                    mock_result.data = True

                return MagicMock(execute=lambda: mock_result)

            mock_db_service.client.rpc = mock_rpc_call

            tenant_id = "tenant-123"
            lock_key = service._generate_lock_key(tenant_id)

            # Try to acquire lock twice sequentially (simulating concurrent attempts)
            result1 = await service._acquire_lock(lock_key, timeout_seconds=0.5)
            result2 = await service._acquire_lock(lock_key, timeout_seconds=0.5)

            # First should succeed, second should fail (timeout)
            assert result1 is True, "First lock attempt should succeed"
            assert result2 is False, "Second lock attempt should fail (lock held)"

    def test_global_service_instance(self):
        """Test that global service instance is available"""
        assert webhook_lock_service is not None
        assert isinstance(webhook_lock_service, WebhookLockService)


class TestWebhookLockIntegration:
    """Integration tests for webhook lock service (require real database)"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_acquire_and_release_real_lock(self):
        """
        Integration test: Acquire and release a real lock

        Note: This requires a real database connection with advisory lock support.
        Mark with @pytest.mark.integration and skip in unit test runs.
        """
        pytest.skip("Integration test - requires real database connection")

        tenant_id = "integration-test-tenant"
        service = webhook_lock_service

        async with service.acquire_webhook_lock(tenant_id) as locked:
            assert locked is True, "Should acquire lock in integration test"

            # Try to acquire same lock from another "session" - should timeout quickly
            status = await service.check_lock_status(tenant_id)
            # Note: check_lock_status might show available if it's the same session

        # After context exit, lock should be released
        status = await service.check_lock_status(tenant_id)
        assert status["available"] is True, "Lock should be released after context exit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
