"""
Unit tests for execution retention service.

Tests the RetentionService class to ensure:
- Retention policies are retrieved correctly with proper fallback to defaults
- Policy creation and updates work as expected
- Cleanup operations respect retention periods and safety thresholds
- Preview functionality accurately predicts cleanup impact
- Cleanup is properly skipped when retention is disabled
- Batch processing and error handling work correctly

Related Tasks:
- T009: Add retention policy unit tests (THIS FILE)
- T003: Retention service implementation
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from typing import Dict, Any

from app.services.retention_service import RetentionService, retention_service
from app.core.config import settings


class TestRetentionPolicyRetrieval:
    """Tests for getting retention policies."""

    @pytest.mark.asyncio
    async def test_get_retention_policy_with_existing_policy(self, monkeypatch):
        """
        GIVEN a tenant with a custom retention policy in the database
        WHEN get_retention_policy is called
        THEN the tenant's custom policy should be returned
        """
        mock_policy_data = {
            "tenant_id": "test-tenant-id",
            "retention_days": 60,
            "is_enabled": True,
            "min_executions_to_keep": 200,
            "last_cleanup_at": "2024-04-01T12:00:00",
            "last_cleanup_deleted_count": 5000,
        }

        service = RetentionService()

        # Mock the database client
        mock_response = MagicMock()
        mock_response.data = mock_policy_data

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            result = await service.get_retention_policy("test-tenant-id")

        assert result["retention_days"] == 60
        assert result["is_enabled"] is True
        assert result["min_executions_to_keep"] == 200
        assert result["last_cleanup_at"] == "2024-04-01T12:00:00"
        assert result["last_cleanup_deleted_count"] == 5000

    @pytest.mark.asyncio
    async def test_get_retention_policy_fallback_to_defaults(self, monkeypatch):
        """
        GIVEN a tenant with no custom retention policy in the database
        WHEN get_retention_policy is called
        THEN system default values should be returned
        """
        service = RetentionService()

        # Mock database to raise an exception (policy not found)
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = Exception("Policy not found")

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            result = await service.get_retention_policy("test-tenant-id")

        # Should return system defaults
        assert result["retention_days"] == settings.EXECUTION_RETENTION_DAYS
        assert result["is_enabled"] == settings.EXECUTION_RETENTION_ENABLED
        assert result["min_executions_to_keep"] == 100
        assert result["last_cleanup_at"] is None
        assert result["last_cleanup_deleted_count"] == 0

    @pytest.mark.asyncio
    async def test_get_retention_policy_partial_data(self, monkeypatch):
        """
        GIVEN a tenant policy with missing fields
        WHEN get_retention_policy is called
        THEN missing fields should fallback to defaults
        """
        mock_policy_data = {
            "tenant_id": "test-tenant-id",
            "retention_days": 45,
            # Missing is_enabled, should default
        }

        service = RetentionService()

        mock_response = MagicMock()
        mock_response.data = mock_policy_data

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = mock_response

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            result = await service.get_retention_policy("test-tenant-id")

        assert result["retention_days"] == 45
        assert result["is_enabled"] == settings.EXECUTION_RETENTION_ENABLED  # Default


class TestRetentionPolicyCreation:
    """Tests for creating and updating retention policies."""

    @pytest.mark.asyncio
    async def test_create_retention_policy_success(self, monkeypatch):
        """
        GIVEN valid retention policy parameters
        WHEN create_retention_policy is called
        THEN a new policy should be created in the database
        """
        service = RetentionService()

        mock_response = MagicMock()
        mock_response.data = [{
            "tenant_id": "test-tenant-id",
            "retention_days": 60,
            "is_enabled": True,
            "min_executions_to_keep": 150,
            "created_by": "user-123",
        }]

        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value = mock_response

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            result = await service.create_retention_policy(
                tenant_id="test-tenant-id",
                retention_days=60,
                is_enabled=True,
                min_executions_to_keep=150,
                created_by="user-123"
            )

        assert result["retention_days"] == 60
        assert result["is_enabled"] is True
        assert result["min_executions_to_keep"] == 150
        assert result["created_by"] == "user-123"

    @pytest.mark.asyncio
    async def test_create_retention_policy_without_created_by(self, monkeypatch):
        """
        GIVEN policy parameters without created_by
        WHEN create_retention_policy is called
        THEN policy should be created without audit trail
        """
        service = RetentionService()

        mock_response = MagicMock()
        mock_response.data = [{
            "tenant_id": "test-tenant-id",
            "retention_days": 90,
            "is_enabled": False,
            "min_executions_to_keep": 100,
        }]

        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value = mock_response

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            result = await service.create_retention_policy(
                tenant_id="test-tenant-id",
                retention_days=90,
                is_enabled=False,
                min_executions_to_keep=100,
                created_by=None
            )

        assert result["retention_days"] == 90
        assert result["is_enabled"] is False

    @pytest.mark.asyncio
    async def test_create_retention_policy_database_error(self, monkeypatch):
        """
        GIVEN a database error during policy creation
        WHEN create_retention_policy is called
        THEN the exception should be raised
        """
        service = RetentionService()

        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.side_effect = Exception("Database error")

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            with pytest.raises(Exception, match="Database error"):
                await service.create_retention_policy(
                    tenant_id="test-tenant-id",
                    retention_days=60,
                    is_enabled=True,
                    min_executions_to_keep=100
                )


class TestRetentionPolicyUpdate:
    """Tests for updating retention policies."""

    @pytest.mark.asyncio
    async def test_update_retention_policy_single_field(self, monkeypatch):
        """
        GIVEN an existing policy and a single field to update
        WHEN update_retention_policy is called
        THEN only that field should be updated
        """
        service = RetentionService()

        mock_response = MagicMock()
        mock_response.data = [{
            "tenant_id": "test-tenant-id",
            "retention_days": 90,
            "is_enabled": False,  # Changed
            "min_executions_to_keep": 100,
        }]

        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_response

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            result = await service.update_retention_policy(
                tenant_id="test-tenant-id",
                is_enabled=False
            )

        assert result["is_enabled"] is False

    @pytest.mark.asyncio
    async def test_update_retention_policy_multiple_fields(self, monkeypatch):
        """
        GIVEN an existing policy and multiple fields to update
        WHEN update_retention_policy is called
        THEN all specified fields should be updated
        """
        service = RetentionService()

        mock_response = MagicMock()
        mock_response.data = [{
            "tenant_id": "test-tenant-id",
            "retention_days": 120,
            "is_enabled": False,
            "min_executions_to_keep": 500,
        }]

        mock_client = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_response

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            result = await service.update_retention_policy(
                tenant_id="test-tenant-id",
                retention_days=120,
                is_enabled=False,
                min_executions_to_keep=500
            )

        assert result["retention_days"] == 120
        assert result["is_enabled"] is False
        assert result["min_executions_to_keep"] == 500

    @pytest.mark.asyncio
    async def test_update_retention_policy_no_fields(self, monkeypatch):
        """
        GIVEN no fields to update (all None)
        WHEN update_retention_policy is called
        THEN it should return the current policy without making database changes
        """
        service = RetentionService()

        # Mock get_retention_policy
        mock_policy = {
            "retention_days": 90,
            "is_enabled": True,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            result = await service.update_retention_policy(
                tenant_id="test-tenant-id",
                retention_days=None,
                is_enabled=None,
                min_executions_to_keep=None
            )

        assert result == mock_policy


class TestCleanupTenantExecutions:
    """Tests for cleanup_tenant_executions method."""

    @pytest.mark.asyncio
    async def test_cleanup_executions_when_enabled(self, monkeypatch):
        """
        GIVEN a tenant with retention enabled
        WHEN cleanup_tenant_executions is called
        THEN old executions should be deleted
        """
        service = RetentionService()

        # Mock policy retrieval
        mock_policy = {
            "retention_days": 90,
            "is_enabled": True,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        # Mock database cleanup RPC call
        mock_cleanup_response = MagicMock()
        mock_cleanup_response.data = [{
            "deleted_count": 5000,
            "execution_summary": {
                "before_count": 105000,
                "after_count": 100000,
            }
        }]

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value = mock_cleanup_response

        # Mock policy update
        mock_update_response = MagicMock()
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_update_response

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            with patch("app.services.retention_service.db_service") as mock_db:
                mock_db.client = mock_client

                result = await service.cleanup_tenant_executions("test-tenant-id")

        assert result["deleted_count"] == 5000
        assert result["retention_days"] == 90
        assert result["is_enabled"] is True
        assert "timestamp" in result
        assert result["summary"]["before_count"] == 105000

    @pytest.mark.asyncio
    async def test_cleanup_skipped_when_disabled(self, monkeypatch):
        """
        GIVEN a tenant with retention disabled
        WHEN cleanup_tenant_executions is called without force
        THEN cleanup should be skipped
        """
        service = RetentionService()

        mock_policy = {
            "retention_days": 90,
            "is_enabled": False,  # Disabled
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            result = await service.cleanup_tenant_executions("test-tenant-id", force=False)

        assert result["deleted_count"] == 0
        assert result["skipped"] is True
        assert result["is_enabled"] is False
        assert result["reason"] == "Retention disabled for tenant"

    @pytest.mark.asyncio
    async def test_cleanup_forced_when_disabled(self, monkeypatch):
        """
        GIVEN a tenant with retention disabled
        WHEN cleanup_tenant_executions is called with force=True
        THEN cleanup should execute anyway
        """
        service = RetentionService()

        mock_policy = {
            "retention_days": 90,
            "is_enabled": False,  # Disabled
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        mock_cleanup_response = MagicMock()
        mock_cleanup_response.data = [{
            "deleted_count": 1000,
            "execution_summary": {}
        }]

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value = mock_cleanup_response
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            with patch("app.services.retention_service.db_service") as mock_db:
                mock_db.client = mock_client

                result = await service.cleanup_tenant_executions("test-tenant-id", force=True)

        assert result["deleted_count"] == 1000
        assert result.get("skipped") is None or result.get("skipped") is False

    @pytest.mark.asyncio
    async def test_cleanup_handles_database_error(self, monkeypatch):
        """
        GIVEN a database error during cleanup
        WHEN cleanup_tenant_executions is called
        THEN the error should be caught and returned in the result
        """
        service = RetentionService()

        mock_policy = {
            "retention_days": 90,
            "is_enabled": True,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.side_effect = Exception("Database connection failed")

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            with patch("app.services.retention_service.db_service") as mock_db:
                mock_db.client = mock_client

                result = await service.cleanup_tenant_executions("test-tenant-id")

        assert result["deleted_count"] == 0
        assert "error" in result
        assert "Database connection failed" in result["error"]


class TestCleanupAllTenants:
    """Tests for cleanup_all_tenants method."""

    @pytest.mark.asyncio
    async def test_cleanup_all_tenants_success(self, monkeypatch):
        """
        GIVEN multiple tenants in the system
        WHEN cleanup_all_tenants is called
        THEN all tenants should be processed
        """
        service = RetentionService()

        # Mock tenants list
        mock_tenants_response = MagicMock()
        mock_tenants_response.data = [
            {"id": "tenant-1"},
            {"id": "tenant-2"},
            {"id": "tenant-3"},
        ]

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.execute.return_value = mock_tenants_response

        # Mock cleanup results
        cleanup_results = [
            {"tenant_id": "tenant-1", "deleted_count": 1000, "is_enabled": True},
            {"tenant_id": "tenant-2", "deleted_count": 500, "is_enabled": True},
            {"tenant_id": "tenant-3", "deleted_count": 0, "skipped": True, "is_enabled": False},
        ]

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            with patch.object(service, "cleanup_tenant_executions") as mock_cleanup:
                mock_cleanup.side_effect = cleanup_results

                result = await service.cleanup_all_tenants()

        assert result["total_deleted"] == 1500  # 1000 + 500 + 0
        assert result["tenants_processed"] == 3
        assert result["tenants_with_deletions"] == 2
        assert result["tenants_skipped"] == 1
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_cleanup_all_tenants_with_errors(self, monkeypatch):
        """
        GIVEN some tenants fail during cleanup
        WHEN cleanup_all_tenants is called
        THEN errors should be tracked and other tenants should still be processed
        """
        service = RetentionService()

        mock_tenants_response = MagicMock()
        mock_tenants_response.data = [
            {"id": "tenant-1"},
            {"id": "tenant-2"},
        ]

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.execute.return_value = mock_tenants_response

        cleanup_results = [
            {"tenant_id": "tenant-1", "deleted_count": 1000, "is_enabled": True},
            {"tenant_id": "tenant-2", "deleted_count": 0, "error": "Connection timeout", "is_enabled": True},
        ]

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            with patch.object(service, "cleanup_tenant_executions") as mock_cleanup:
                mock_cleanup.side_effect = cleanup_results

                result = await service.cleanup_all_tenants()

        assert result["total_deleted"] == 1000
        assert result["tenants_processed"] == 2
        assert len(result["errors"]) == 1
        assert "tenant-2" in result["errors"]

    @pytest.mark.asyncio
    async def test_cleanup_all_tenants_handles_exception(self, monkeypatch):
        """
        GIVEN a tenant that raises an exception during cleanup
        WHEN cleanup_all_tenants is called
        THEN the exception should be caught and processing should continue
        """
        service = RetentionService()

        mock_tenants_response = MagicMock()
        mock_tenants_response.data = [
            {"id": "tenant-1"},
            {"id": "tenant-2"},
        ]

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.execute.return_value = mock_tenants_response

        def cleanup_side_effect(tenant_id):
            if tenant_id == "tenant-1":
                return {"tenant_id": "tenant-1", "deleted_count": 500, "is_enabled": True}
            else:
                raise Exception("Unexpected error")

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            with patch.object(service, "cleanup_tenant_executions") as mock_cleanup:
                mock_cleanup.side_effect = cleanup_side_effect

                result = await service.cleanup_all_tenants()

        assert result["total_deleted"] == 500
        assert result["tenants_processed"] == 2
        assert len(result["errors"]) == 1
        assert "tenant-2" in result["errors"]


class TestCleanupPreview:
    """Tests for cleanup preview functionality."""

    @pytest.mark.asyncio
    async def test_get_cleanup_preview_with_deletions(self, monkeypatch):
        """
        GIVEN a tenant with old executions
        WHEN get_cleanup_preview is called
        THEN it should show what would be deleted without deleting
        """
        service = RetentionService()

        mock_policy = {
            "retention_days": 90,
            "is_enabled": True,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        # Mock total count
        mock_total_response = MagicMock()
        mock_total_response.count = 150000

        # Mock old count
        mock_old_response = MagicMock()
        mock_old_response.count = 50000

        mock_client = MagicMock()

        call_count = [0]

        def mock_query_chain(*args, **kwargs):
            """Mock the fluent query chain."""
            mock_chain = MagicMock()
            mock_chain.select.return_value = mock_chain
            mock_chain.eq.return_value = mock_chain
            mock_chain.lt.return_value = mock_chain

            call_count[0] += 1
            if call_count[0] == 1:
                mock_chain.execute.return_value = mock_total_response
            else:
                mock_chain.execute.return_value = mock_old_response

            return mock_chain

        mock_client.table.side_effect = mock_query_chain

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            with patch("app.services.retention_service.db_service") as mock_db:
                mock_db.client = mock_client

                result = await service.get_cleanup_preview("test-tenant-id")

        assert result["total_executions"] == 150000
        assert result["old_executions_count"] == 50000
        assert result["executions_to_delete"] == 50000  # would delete since total > min_executions
        assert result["would_delete"] is True
        assert result["retention_days"] == 90

    @pytest.mark.asyncio
    async def test_get_cleanup_preview_respects_min_threshold(self, monkeypatch):
        """
        GIVEN a tenant with executions below the min_executions_to_keep threshold
        WHEN get_cleanup_preview is called
        THEN it should show no deletions would occur
        """
        service = RetentionService()

        mock_policy = {
            "retention_days": 90,
            "is_enabled": True,
            "min_executions_to_keep": 1000,  # High threshold
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        # Mock total count (below threshold)
        mock_total_response = MagicMock()
        mock_total_response.count = 500  # Less than min_executions_to_keep

        # Mock old count
        mock_old_response = MagicMock()
        mock_old_response.count = 400

        mock_client = MagicMock()

        call_count = [0]

        def mock_query_chain(*args, **kwargs):
            """Mock the fluent query chain."""
            mock_chain = MagicMock()
            mock_chain.select.return_value = mock_chain
            mock_chain.eq.return_value = mock_chain
            mock_chain.lt.return_value = mock_chain

            call_count[0] += 1
            if call_count[0] == 1:
                mock_chain.execute.return_value = mock_total_response
            else:
                mock_chain.execute.return_value = mock_old_response

            return mock_chain

        mock_client.table.side_effect = mock_query_chain

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            with patch("app.services.retention_service.db_service") as mock_db:
                mock_db.client = mock_client

                result = await service.get_cleanup_preview("test-tenant-id")

        assert result["total_executions"] == 500
        assert result["old_executions_count"] == 400
        assert result["executions_to_delete"] == 0  # No deletion due to threshold
        assert result["would_delete"] is False  # total <= min_executions_to_keep

    @pytest.mark.asyncio
    async def test_get_cleanup_preview_handles_error(self, monkeypatch):
        """
        GIVEN a database error during preview
        WHEN get_cleanup_preview is called
        THEN the error should be returned in the result
        """
        service = RetentionService()

        mock_policy = {
            "retention_days": 90,
            "is_enabled": True,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        mock_client = MagicMock()
        mock_client.table.side_effect = Exception("Database query failed")

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            with patch("app.services.retention_service.db_service") as mock_db:
                mock_db.client = mock_client

                result = await service.get_cleanup_preview("test-tenant-id")

        assert "error" in result
        assert "Database query failed" in result["error"]


class TestGetAllRetentionPolicies:
    """Tests for retrieving all retention policies."""

    @pytest.mark.asyncio
    async def test_get_all_retention_policies_success(self, monkeypatch):
        """
        GIVEN multiple tenants with retention policies
        WHEN get_all_retention_policies is called
        THEN all policies should be returned
        """
        service = RetentionService()

        mock_policies = [
            {
                "tenant_id": "tenant-1",
                "retention_days": 90,
                "is_enabled": True,
                "min_executions_to_keep": 100,
            },
            {
                "tenant_id": "tenant-2",
                "retention_days": 60,
                "is_enabled": False,
                "min_executions_to_keep": 200,
            },
        ]

        mock_response = MagicMock()
        mock_response.data = mock_policies

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.order.return_value.execute.return_value = mock_response

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            result = await service.get_all_retention_policies()

        assert len(result) == 2
        assert result[0]["tenant_id"] == "tenant-1"
        assert result[1]["tenant_id"] == "tenant-2"

    @pytest.mark.asyncio
    async def test_get_all_retention_policies_empty(self, monkeypatch):
        """
        GIVEN no retention policies in the database
        WHEN get_all_retention_policies is called
        THEN an empty list should be returned
        """
        service = RetentionService()

        mock_response = MagicMock()
        mock_response.data = None  # No data

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.order.return_value.execute.return_value = mock_response

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            result = await service.get_all_retention_policies()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_retention_policies_handles_error(self, monkeypatch):
        """
        GIVEN a database error
        WHEN get_all_retention_policies is called
        THEN an empty list should be returned
        """
        service = RetentionService()

        mock_client = MagicMock()
        mock_client.table.side_effect = Exception("Database error")

        with patch("app.services.retention_service.db_service") as mock_db:
            mock_db.client = mock_client

            result = await service.get_all_retention_policies()

        assert result == []


class TestRetentionServiceConfiguration:
    """Tests for retention service configuration."""

    def test_retention_service_initialization(self):
        """
        GIVEN the retention service is initialized
        WHEN checking configuration values
        THEN they should match system settings
        """
        service = RetentionService()

        assert service.default_retention_days == settings.EXECUTION_RETENTION_DAYS
        assert service.default_enabled == settings.EXECUTION_RETENTION_ENABLED
        assert service.batch_size == settings.RETENTION_JOB_BATCH_SIZE

    def test_retention_service_singleton(self):
        """
        GIVEN the global retention_service instance
        WHEN accessing it
        THEN it should be an instance of RetentionService
        """
        assert isinstance(retention_service, RetentionService)
        assert retention_service.default_retention_days == settings.EXECUTION_RETENTION_DAYS


class TestRetentionEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_cleanup_with_zero_deletions(self, monkeypatch):
        """
        GIVEN a tenant with no old executions
        WHEN cleanup is triggered
        THEN no executions should be deleted
        """
        service = RetentionService()

        mock_policy = {
            "retention_days": 90,
            "is_enabled": True,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        mock_cleanup_response = MagicMock()
        mock_cleanup_response.data = [{
            "deleted_count": 0,  # No deletions
            "execution_summary": {
                "before_count": 5000,
                "after_count": 5000,
            }
        }]

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value = mock_cleanup_response
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            with patch("app.services.retention_service.db_service") as mock_db:
                mock_db.client = mock_client

                result = await service.cleanup_tenant_executions("test-tenant-id")

        assert result["deleted_count"] == 0
        assert result["summary"]["before_count"] == result["summary"]["after_count"]

    @pytest.mark.asyncio
    async def test_cleanup_with_very_short_retention_period(self, monkeypatch):
        """
        GIVEN a tenant with a very short retention period (1 day)
        WHEN cleanup is triggered
        THEN the cleanup should use the 1-day period correctly
        """
        service = RetentionService()

        mock_policy = {
            "retention_days": 1,  # Very short
            "is_enabled": True,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        mock_cleanup_response = MagicMock()
        mock_cleanup_response.data = [{
            "deleted_count": 95000,
            "execution_summary": {}
        }]

        mock_client = MagicMock()
        mock_client.rpc.return_value.execute.return_value = mock_cleanup_response
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            with patch("app.services.retention_service.db_service") as mock_db:
                mock_db.client = mock_client

                result = await service.cleanup_tenant_executions("test-tenant-id")

        assert result["retention_days"] == 1
        assert result["deleted_count"] == 95000

    @pytest.mark.asyncio
    async def test_preview_with_no_executions(self, monkeypatch):
        """
        GIVEN a tenant with no executions
        WHEN preview is requested
        THEN it should show zero executions and no deletions
        """
        service = RetentionService()

        mock_policy = {
            "retention_days": 90,
            "is_enabled": True,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        mock_response = MagicMock()
        mock_response.count = 0

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        mock_client.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = mock_response

        with patch.object(service, "get_retention_policy", return_value=mock_policy):
            with patch("app.services.retention_service.db_service") as mock_db:
                mock_db.client = mock_client

                result = await service.get_cleanup_preview("test-tenant-id")

        assert result["total_executions"] == 0
        assert result["old_executions_count"] == 0
        assert result["would_delete"] is False
