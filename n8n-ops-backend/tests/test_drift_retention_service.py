"""
Unit tests for the Drift Retention Service.
Tests plan-based retention defaults and cleanup logic.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.drift_retention_service import (
    DriftRetentionService,
    drift_retention_service,
)


# Test fixtures
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001"


class TestRetentionDefaults:
    """Test plan-based retention default values."""

    def test_free_plan_defaults(self):
        """Test retention defaults for free plan."""
        service = DriftRetentionService()
        defaults = service.RETENTION_DEFAULTS["free"]

        assert defaults["drift_checks"] == 7
        assert defaults["closed_incidents"] == 0  # N/A for free
        assert defaults["reconciliation_artifacts"] == 0  # N/A for free
        assert defaults["approvals"] == 0  # N/A for free

    def test_pro_plan_defaults(self):
        """Test retention defaults for pro plan."""
        service = DriftRetentionService()
        defaults = service.RETENTION_DEFAULTS["pro"]

        assert defaults["drift_checks"] == 30
        assert defaults["closed_incidents"] == 180
        assert defaults["reconciliation_artifacts"] == 180
        assert defaults["approvals"] == 180

    def test_agency_plan_defaults(self):
        """Test retention defaults for agency plan."""
        service = DriftRetentionService()
        defaults = service.RETENTION_DEFAULTS["agency"]

        assert defaults["drift_checks"] == 90
        assert defaults["closed_incidents"] == 365
        assert defaults["reconciliation_artifacts"] == 365
        assert defaults["approvals"] == 365

    def test_enterprise_plan_defaults(self):
        """Test retention defaults for enterprise plan."""
        service = DriftRetentionService()
        defaults = service.RETENTION_DEFAULTS["enterprise"]

        assert defaults["drift_checks"] == 180
        assert defaults["closed_incidents"] == 2555  # 7 years
        assert defaults["reconciliation_artifacts"] == 2555
        assert defaults["approvals"] == 2555


class TestGetRetentionPolicy:
    """Tests for get_retention_policy method."""

    @pytest.mark.asyncio
    async def test_get_policy_with_plan_defaults(self):
        """Test getting policy falls back to plan defaults."""
        service = DriftRetentionService()

        with patch("app.services.drift_retention_service.feature_service") as mock_feature:
            mock_feature.get_tenant_subscription = AsyncMock(return_value={
                "plan": {"name": "pro"}
            })

            with patch("app.services.drift_retention_service.db_service") as mock_db:
                mock_response = MagicMock()
                mock_response.data = []  # No policy record
                mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

                policy = await service.get_retention_policy(MOCK_TENANT_ID)

                assert policy["plan"] == "pro"
                assert policy["retention_enabled"] is True
                assert policy["retention_days_drift_checks"] == 30
                assert policy["retention_days_closed_incidents"] == 180
                assert policy["retention_days_approvals"] == 180

    @pytest.mark.asyncio
    async def test_get_policy_with_custom_values(self):
        """Test getting policy with custom tenant values."""
        service = DriftRetentionService()

        with patch("app.services.drift_retention_service.feature_service") as mock_feature:
            mock_feature.get_tenant_subscription = AsyncMock(return_value={
                "plan": {"name": "agency"}
            })

            with patch("app.services.drift_retention_service.db_service") as mock_db:
                mock_response = MagicMock()
                mock_response.data = [{
                    "retention_enabled": True,
                    "retention_days_drift_checks": 60,  # Custom override
                    "retention_days_closed_incidents": None,  # Use default
                    "retention_days_reconciliation_artifacts": 180,
                    "retention_days_approvals": 180,
                }]
                mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

                policy = await service.get_retention_policy(MOCK_TENANT_ID)

                assert policy["retention_days_drift_checks"] == 60  # Custom
                assert policy["retention_days_closed_incidents"] == 365  # Default

    @pytest.mark.asyncio
    async def test_get_policy_retention_disabled(self):
        """Test getting policy when retention is disabled."""
        service = DriftRetentionService()

        with patch("app.services.drift_retention_service.feature_service") as mock_feature:
            mock_feature.get_tenant_subscription = AsyncMock(return_value={
                "plan": {"name": "enterprise"}
            })

            with patch("app.services.drift_retention_service.db_service") as mock_db:
                mock_response = MagicMock()
                mock_response.data = [{
                    "retention_enabled": False,
                }]
                mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

                policy = await service.get_retention_policy(MOCK_TENANT_ID)

                assert policy["retention_enabled"] is False

    @pytest.mark.asyncio
    async def test_get_policy_handles_error(self):
        """Test getting policy handles errors gracefully."""
        service = DriftRetentionService()

        with patch("app.services.drift_retention_service.feature_service") as mock_feature:
            mock_feature.get_tenant_subscription = AsyncMock(side_effect=Exception("DB error"))

            policy = await service.get_retention_policy(MOCK_TENANT_ID)

            # Should return safe free tier defaults
            assert policy["plan"] == "free"
            assert policy["retention_enabled"] is True
            assert policy["retention_days_drift_checks"] == 7


class TestCleanupTenantData:
    """Tests for cleanup_tenant_data method."""

    @pytest.mark.asyncio
    async def test_cleanup_skips_when_disabled(self):
        """Test cleanup is skipped when retention is disabled."""
        service = DriftRetentionService()

        with patch.object(service, "get_retention_policy", new_callable=AsyncMock) as mock_policy:
            mock_policy.return_value = {
                "retention_enabled": False,
                "retention_days_drift_checks": 30,
                "retention_days_closed_incidents": 180,
                "retention_days_reconciliation_artifacts": 180,
                "retention_days_approvals": 180,
                "plan": "pro",
            }

            result = await service.cleanup_tenant_data(MOCK_TENANT_ID)

            assert result["drift_checks_deleted"] == 0
            assert result["incident_payloads_purged"] == 0
            assert result["reconciliation_artifacts_deleted"] == 0
            assert result["approvals_deleted"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_skips_zero_retention(self):
        """Test cleanup skips entities with 0 retention (never delete)."""
        service = DriftRetentionService()

        with patch.object(service, "get_retention_policy", new_callable=AsyncMock) as mock_policy:
            mock_policy.return_value = {
                "retention_enabled": True,
                "retention_days_drift_checks": 0,  # Never delete
                "retention_days_closed_incidents": 0,
                "retention_days_reconciliation_artifacts": 0,
                "retention_days_approvals": 0,
                "plan": "free",
            }

            result = await service.cleanup_tenant_data(MOCK_TENANT_ID)

            # Nothing should be deleted
            assert result["drift_checks_deleted"] == 0
            assert result["incident_payloads_purged"] == 0
            assert result["reconciliation_artifacts_deleted"] == 0
            assert result["approvals_deleted"] == 0


class TestCleanupDriftChecks:
    """Tests for _cleanup_drift_checks method."""

    @pytest.mark.asyncio
    async def test_cleanup_preserves_latest_check(self):
        """Test that the most recent drift check per environment is preserved."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            # Mock environments query
            env_response = MagicMock()
            env_response.data = [{"id": "env-1"}, {"id": "env-2"}]

            # Mock latest check per env
            latest_check_response = MagicMock()
            latest_check_response.data = [{"id": "check-latest"}]

            # Mock old checks query
            old_checks_response = MagicMock()
            old_checks_response.data = [
                {"id": "check-old-1"},
                {"id": "check-old-2"},
                {"id": "check-latest"},  # Should be filtered out
            ]

            def table_side_effect(name):
                mock_query = MagicMock()
                if name == "environments":
                    mock_query.select.return_value.eq.return_value.execute.return_value = env_response
                elif name == "drift_check_history":
                    mock_query.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = latest_check_response
                    mock_query.select.return_value.eq.return_value.lt.return_value.execute.return_value = old_checks_response
                    mock_query.delete.return_value.eq.return_value.execute.return_value = MagicMock()
                return mock_query

            mock_db.client.table.side_effect = table_side_effect

            count = await service._cleanup_drift_checks(MOCK_TENANT_ID, 30, now)

            # Should delete 2 old checks (excluding the latest)
            assert count == 2


class TestPurgeIncidentPayloads:
    """Tests for _purge_incident_payloads method."""

    @pytest.mark.asyncio
    async def test_purge_only_closed_incidents(self):
        """Test that only closed incidents are purged."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            # Mock finding closed incidents
            incidents_response = MagicMock()
            incidents_response.data = [
                {"id": "incident-closed-1"},
                {"id": "incident-closed-2"},
            ]

            def table_side_effect(name):
                mock_query = MagicMock()
                if name == "drift_incidents":
                    mock_query.select.return_value.eq.return_value.eq.return_value.is_.return_value.lt.return_value.execute.return_value = incidents_response
                    mock_query.update.return_value.eq.return_value.execute.return_value = MagicMock()
                elif name == "incident_payloads":
                    mock_query.delete.return_value.eq.return_value.execute.return_value = MagicMock()
                return mock_query

            mock_db.client.table.side_effect = table_side_effect

            count = await service._purge_incident_payloads(MOCK_TENANT_ID, 180, now)

            assert count == 2

    @pytest.mark.asyncio
    async def test_purge_skips_already_purged(self):
        """Test that already purged incidents are skipped."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            # No incidents to purge (already purged)
            incidents_response = MagicMock()
            incidents_response.data = []

            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.lt.return_value.execute.return_value = incidents_response

            count = await service._purge_incident_payloads(MOCK_TENANT_ID, 180, now)

            assert count == 0


class TestCleanupArtifacts:
    """Tests for _cleanup_artifacts method."""

    @pytest.mark.asyncio
    async def test_cleanup_artifacts_success(self):
        """Test successful cleanup of reconciliation artifacts."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            count_response = MagicMock()
            count_response.count = 5
            count_response.data = [{"id": f"artifact-{i}"} for i in range(5)]

            mock_query = MagicMock()
            mock_query.select.return_value.eq.return_value.lt.return_value.execute.return_value = count_response
            mock_query.delete.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock()
            mock_db.client.table.return_value = mock_query

            count = await service._cleanup_artifacts(MOCK_TENANT_ID, 180, now)

            assert count == 5


class TestCleanupApprovals:
    """Tests for _cleanup_approvals method."""

    @pytest.mark.asyncio
    async def test_cleanup_approvals_success(self):
        """Test successful cleanup of approval records."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            count_response = MagicMock()
            count_response.count = 3
            count_response.data = [{"id": f"approval-{i}"} for i in range(3)]

            mock_query = MagicMock()
            mock_query.select.return_value.eq.return_value.lt.return_value.execute.return_value = count_response
            mock_query.delete.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock()
            mock_db.client.table.return_value = mock_query

            count = await service._cleanup_approvals(MOCK_TENANT_ID, 180, now)

            assert count == 3


class TestCleanupAllTenants:
    """Tests for cleanup_all_tenants method."""

    @pytest.mark.asyncio
    async def test_cleanup_all_tenants_success(self):
        """Test cleaning up all tenants."""
        service = DriftRetentionService()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            # Mock tenants list
            tenants_response = MagicMock()
            tenants_response.data = [
                {"id": "tenant-1"},
                {"id": "tenant-2"},
            ]
            mock_db.client.table.return_value.select.return_value.execute.return_value = tenants_response

            with patch.object(service, "cleanup_tenant_data", new_callable=AsyncMock) as mock_cleanup:
                mock_cleanup.side_effect = [
                    {
                        "drift_checks_deleted": 5,
                        "incident_payloads_purged": 2,
                        "reconciliation_artifacts_deleted": 1,
                        "approvals_deleted": 0,
                    },
                    {
                        "drift_checks_deleted": 3,
                        "incident_payloads_purged": 0,
                        "reconciliation_artifacts_deleted": 0,
                        "approvals_deleted": 1,
                    },
                ]

                result = await service.cleanup_all_tenants()

                assert result["drift_checks_deleted"] == 8
                assert result["incident_payloads_purged"] == 2
                assert result["reconciliation_artifacts_deleted"] == 1
                assert result["approvals_deleted"] == 1
                assert result["tenants_processed"] == 2
                assert result["tenants_with_changes"] == 2

    @pytest.mark.asyncio
    async def test_cleanup_all_tenants_handles_error(self):
        """Test that cleanup_all_tenants handles errors gracefully."""
        service = DriftRetentionService()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            mock_db.client.table.return_value.select.return_value.execute.side_effect = Exception("DB error")

            result = await service.cleanup_all_tenants()

            assert "error" in result
            assert result["tenants_processed"] == 0


class TestOpenIncidentsNeverPurged:
    """Test that open incidents are never purged."""

    @pytest.mark.asyncio
    async def test_open_incidents_excluded_from_purge(self):
        """Test that the query correctly filters out non-closed incidents."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            # Mock query that filters by status='closed'
            incidents_response = MagicMock()
            incidents_response.data = []

            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.is_.return_value = mock_query
            mock_query.lt.return_value = mock_query
            mock_query.execute.return_value = incidents_response

            mock_db.client.table.return_value = mock_query

            count = await service._purge_incident_payloads(MOCK_TENANT_ID, 180, now)

            # Verify that the query filtered by status='closed'
            eq_calls = [str(c) for c in mock_query.eq.call_args_list]
            assert any("closed" in str(c) for c in mock_query.eq.call_args_list)


class TestGetRetentionPolicyEdgeCases:
    """Additional edge case tests for get_retention_policy."""

    @pytest.mark.asyncio
    async def test_unknown_plan_defaults_to_free(self):
        """Test that unknown plan names default to free tier."""
        service = DriftRetentionService()

        with patch("app.services.drift_retention_service.feature_service") as mock_feature:
            mock_feature.get_tenant_subscription = AsyncMock(return_value={
                "plan": {"name": "unknown_plan_xyz"}
            })

            with patch("app.services.drift_retention_service.db_service") as mock_db:
                mock_response = MagicMock()
                mock_response.data = []
                mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

                policy = await service.get_retention_policy(MOCK_TENANT_ID)

                # Should use free tier defaults
                assert policy["retention_days_drift_checks"] == 7
                assert policy["retention_days_closed_incidents"] == 0

    @pytest.mark.asyncio
    async def test_null_subscription_defaults_to_free(self):
        """Test that null subscription defaults to free tier."""
        service = DriftRetentionService()

        with patch("app.services.drift_retention_service.feature_service") as mock_feature:
            mock_feature.get_tenant_subscription = AsyncMock(return_value=None)

            with patch("app.services.drift_retention_service.db_service") as mock_db:
                mock_response = MagicMock()
                mock_response.data = []
                mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

                policy = await service.get_retention_policy(MOCK_TENANT_ID)

                assert policy["plan"] == "free"
                assert policy["retention_days_drift_checks"] == 7


class TestCleanupDriftChecksEdgeCases:
    """Additional edge case tests for _cleanup_drift_checks."""

    @pytest.mark.asyncio
    async def test_cleanup_no_environments(self):
        """Test cleanup returns 0 when tenant has no environments."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            # Mock empty environments
            env_response = MagicMock()
            env_response.data = []
            mock_db.client.table.return_value.select.return_value.eq.return_value.execute.return_value = env_response

            count = await service._cleanup_drift_checks(MOCK_TENANT_ID, 30, now)

            assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_drift_checks_handles_error(self):
        """Test that _cleanup_drift_checks handles errors gracefully."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            mock_db.client.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")

            count = await service._cleanup_drift_checks(MOCK_TENANT_ID, 30, now)

            assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_no_old_checks(self):
        """Test cleanup when no checks are older than retention period."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            # Mock environments
            env_response = MagicMock()
            env_response.data = [{"id": "env-1"}]

            # Mock latest check
            latest_response = MagicMock()
            latest_response.data = [{"id": "check-1"}]

            # Mock old checks - only contains the latest (which should be excluded)
            old_checks_response = MagicMock()
            old_checks_response.data = [{"id": "check-1"}]

            def table_side_effect(name):
                mock_query = MagicMock()
                if name == "environments":
                    mock_query.select.return_value.eq.return_value.execute.return_value = env_response
                elif name == "drift_check_history":
                    mock_query.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = latest_response
                    mock_query.select.return_value.eq.return_value.lt.return_value.execute.return_value = old_checks_response
                return mock_query

            mock_db.client.table.side_effect = table_side_effect

            count = await service._cleanup_drift_checks(MOCK_TENANT_ID, 30, now)

            # No checks should be deleted (latest is preserved)
            assert count == 0


class TestPurgeIncidentPayloadsEdgeCases:
    """Additional edge case tests for _purge_incident_payloads."""

    @pytest.mark.asyncio
    async def test_purge_handles_individual_incident_error(self):
        """Test that errors on individual incidents don't stop the batch."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            # Mock finding 3 incidents
            incidents_response = MagicMock()
            incidents_response.data = [
                {"id": "incident-1"},
                {"id": "incident-2"},
                {"id": "incident-3"},
            ]

            call_count = [0]

            def table_side_effect(name):
                mock_query = MagicMock()
                if name == "drift_incidents":
                    mock_query.select.return_value.eq.return_value.eq.return_value.is_.return_value.lt.return_value.execute.return_value = incidents_response
                    # Make second update fail
                    def update_side_effect(*args, **kwargs):
                        call_count[0] += 1
                        if call_count[0] == 2:
                            raise Exception("Individual error")
                        return mock_query
                    mock_query.update.return_value.eq.return_value.execute.side_effect = update_side_effect
                elif name == "incident_payloads":
                    mock_query.delete.return_value.eq.return_value.execute.return_value = MagicMock()
                return mock_query

            mock_db.client.table.side_effect = table_side_effect

            count = await service._purge_incident_payloads(MOCK_TENANT_ID, 180, now)

            # Should have purged 2 out of 3 (one failed)
            assert count == 2

    @pytest.mark.asyncio
    async def test_purge_handles_db_error(self):
        """Test that _purge_incident_payloads handles DB errors gracefully."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.lt.return_value.execute.side_effect = Exception("DB error")

            count = await service._purge_incident_payloads(MOCK_TENANT_ID, 180, now)

            assert count == 0


class TestCleanupArtifactsEdgeCases:
    """Additional edge case tests for _cleanup_artifacts."""

    @pytest.mark.asyncio
    async def test_cleanup_artifacts_none_to_delete(self):
        """Test cleanup when no artifacts are older than retention."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            count_response = MagicMock()
            count_response.count = 0
            count_response.data = []

            mock_query = MagicMock()
            mock_query.select.return_value.eq.return_value.lt.return_value.execute.return_value = count_response
            mock_db.client.table.return_value = mock_query

            count = await service._cleanup_artifacts(MOCK_TENANT_ID, 180, now)

            assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_artifacts_handles_error(self):
        """Test that _cleanup_artifacts handles errors gracefully."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            mock_db.client.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.side_effect = Exception("DB error")

            count = await service._cleanup_artifacts(MOCK_TENANT_ID, 180, now)

            assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_artifacts_uses_data_length_fallback(self):
        """Test cleanup uses len(data) when count attribute missing."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            # Response without count attribute
            count_response = MagicMock(spec=[])  # No count attribute
            count_response.data = [{"id": "artifact-1"}, {"id": "artifact-2"}]

            mock_query = MagicMock()
            mock_query.select.return_value.eq.return_value.lt.return_value.execute.return_value = count_response
            mock_query.delete.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock()
            mock_db.client.table.return_value = mock_query

            count = await service._cleanup_artifacts(MOCK_TENANT_ID, 180, now)

            assert count == 2


class TestCleanupApprovalsEdgeCases:
    """Additional edge case tests for _cleanup_approvals."""

    @pytest.mark.asyncio
    async def test_cleanup_approvals_none_to_delete(self):
        """Test cleanup when no approvals are older than retention."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            count_response = MagicMock()
            count_response.count = 0
            count_response.data = []

            mock_query = MagicMock()
            mock_query.select.return_value.eq.return_value.lt.return_value.execute.return_value = count_response
            mock_db.client.table.return_value = mock_query

            count = await service._cleanup_approvals(MOCK_TENANT_ID, 180, now)

            assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_approvals_handles_error(self):
        """Test that _cleanup_approvals handles errors gracefully."""
        service = DriftRetentionService()
        now = datetime.utcnow()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            mock_db.client.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.side_effect = Exception("DB error")

            count = await service._cleanup_approvals(MOCK_TENANT_ID, 180, now)

            assert count == 0


class TestCleanupTenantDataEdgeCases:
    """Additional edge case tests for cleanup_tenant_data."""

    @pytest.mark.asyncio
    async def test_cleanup_handles_exception_during_cleanup(self):
        """Test that cleanup_tenant_data handles exceptions during cleanup."""
        service = DriftRetentionService()

        with patch.object(service, "get_retention_policy", new_callable=AsyncMock) as mock_policy:
            mock_policy.return_value = {
                "retention_enabled": True,
                "retention_days_drift_checks": 30,
                "retention_days_closed_incidents": 180,
                "retention_days_reconciliation_artifacts": 180,
                "retention_days_approvals": 180,
                "plan": "pro",
            }

            with patch.object(service, "_cleanup_drift_checks", new_callable=AsyncMock) as mock_drift:
                mock_drift.side_effect = Exception("Cleanup error")

                result = await service.cleanup_tenant_data(MOCK_TENANT_ID)

                # Should return zeros due to exception
                assert result["drift_checks_deleted"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_calls_all_cleanup_methods(self):
        """Test that cleanup_tenant_data calls all cleanup methods with correct args."""
        service = DriftRetentionService()

        with patch.object(service, "get_retention_policy", new_callable=AsyncMock) as mock_policy:
            mock_policy.return_value = {
                "retention_enabled": True,
                "retention_days_drift_checks": 30,
                "retention_days_closed_incidents": 180,
                "retention_days_reconciliation_artifacts": 90,
                "retention_days_approvals": 60,
                "plan": "pro",
            }

            with patch.object(service, "_cleanup_drift_checks", new_callable=AsyncMock) as mock_drift, \
                 patch.object(service, "_purge_incident_payloads", new_callable=AsyncMock) as mock_purge, \
                 patch.object(service, "_cleanup_artifacts", new_callable=AsyncMock) as mock_artifacts, \
                 patch.object(service, "_cleanup_approvals", new_callable=AsyncMock) as mock_approvals:

                mock_drift.return_value = 5
                mock_purge.return_value = 3
                mock_artifacts.return_value = 2
                mock_approvals.return_value = 1

                result = await service.cleanup_tenant_data(MOCK_TENANT_ID)

                # Verify all methods were called
                mock_drift.assert_called_once()
                mock_purge.assert_called_once()
                mock_artifacts.assert_called_once()
                mock_approvals.assert_called_once()

                # Verify correct retention days were passed
                assert mock_drift.call_args[0][1] == 30
                assert mock_purge.call_args[0][1] == 180
                assert mock_artifacts.call_args[0][1] == 90
                assert mock_approvals.call_args[0][1] == 60

                # Verify results
                assert result["drift_checks_deleted"] == 5
                assert result["incident_payloads_purged"] == 3
                assert result["reconciliation_artifacts_deleted"] == 2
                assert result["approvals_deleted"] == 1


class TestCleanupAllTenantsEdgeCases:
    """Additional edge case tests for cleanup_all_tenants."""

    @pytest.mark.asyncio
    async def test_cleanup_all_tenants_no_changes(self):
        """Test cleanup_all_tenants when no tenant has changes."""
        service = DriftRetentionService()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            tenants_response = MagicMock()
            tenants_response.data = [{"id": "tenant-1"}, {"id": "tenant-2"}]
            mock_db.client.table.return_value.select.return_value.execute.return_value = tenants_response

            with patch.object(service, "cleanup_tenant_data", new_callable=AsyncMock) as mock_cleanup:
                mock_cleanup.return_value = {
                    "drift_checks_deleted": 0,
                    "incident_payloads_purged": 0,
                    "reconciliation_artifacts_deleted": 0,
                    "approvals_deleted": 0,
                }

                result = await service.cleanup_all_tenants()

                assert result["tenants_processed"] == 2
                assert result["tenants_with_changes"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_all_tenants_empty_list(self):
        """Test cleanup_all_tenants with no tenants."""
        service = DriftRetentionService()

        with patch("app.services.drift_retention_service.db_service") as mock_db:
            tenants_response = MagicMock()
            tenants_response.data = []
            mock_db.client.table.return_value.select.return_value.execute.return_value = tenants_response

            result = await service.cleanup_all_tenants()

            assert result["tenants_processed"] == 0
            assert result["tenants_with_changes"] == 0
            assert "error" not in result
