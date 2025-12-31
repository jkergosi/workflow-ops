"""
Unit tests for the Drift Incident Service.
Tests the full lifecycle management of drift incidents.
"""
import pytest
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException

from app.services.drift_incident_service import (
    DriftIncidentService,
    drift_incident_service,
    VALID_TRANSITIONS,
)
from app.schemas.drift_incident import (
    DriftIncidentStatus,
    DriftSeverity,
    ResolutionType,
    AffectedWorkflow,
)


# Test fixtures
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001"
MOCK_USER_ID = "00000000-0000-0000-0000-000000000002"
MOCK_ENVIRONMENT_ID = "env-001"
MOCK_INCIDENT_ID = "incident-001"


@pytest.fixture
def mock_incident():
    """Create a mock drift incident."""
    return {
        "id": MOCK_INCIDENT_ID,
        "tenant_id": MOCK_TENANT_ID,
        "environment_id": MOCK_ENVIRONMENT_ID,
        "status": DriftIncidentStatus.detected.value,
        "title": "Test Drift Incident",
        "detected_at": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "affected_workflows": [],
        "drift_snapshot": None,
    }


@pytest.fixture
def mock_acknowledged_incident(mock_incident):
    """Create a mock acknowledged incident."""
    return {
        **mock_incident,
        "status": DriftIncidentStatus.acknowledged.value,
        "acknowledged_at": datetime.utcnow().isoformat(),
        "acknowledged_by": MOCK_USER_ID,
    }


@pytest.fixture
def mock_stabilized_incident(mock_acknowledged_incident):
    """Create a mock stabilized incident."""
    return {
        **mock_acknowledged_incident,
        "status": DriftIncidentStatus.stabilized.value,
        "stabilized_at": datetime.utcnow().isoformat(),
        "stabilized_by": MOCK_USER_ID,
    }


class TestDriftIncidentServiceValidTransitions:
    """Test status transition validation."""

    def test_valid_transitions_from_detected(self):
        """Test valid transitions from detected status."""
        service = DriftIncidentService()

        assert service._validate_transition("detected", DriftIncidentStatus.acknowledged) is True
        assert service._validate_transition("detected", DriftIncidentStatus.closed) is True
        assert service._validate_transition("detected", DriftIncidentStatus.stabilized) is False
        assert service._validate_transition("detected", DriftIncidentStatus.reconciled) is False

    def test_valid_transitions_from_acknowledged(self):
        """Test valid transitions from acknowledged status."""
        service = DriftIncidentService()

        assert service._validate_transition("acknowledged", DriftIncidentStatus.stabilized) is True
        assert service._validate_transition("acknowledged", DriftIncidentStatus.reconciled) is True
        assert service._validate_transition("acknowledged", DriftIncidentStatus.closed) is True
        assert service._validate_transition("acknowledged", DriftIncidentStatus.detected) is False

    def test_valid_transitions_from_stabilized(self):
        """Test valid transitions from stabilized status."""
        service = DriftIncidentService()

        assert service._validate_transition("stabilized", DriftIncidentStatus.reconciled) is True
        assert service._validate_transition("stabilized", DriftIncidentStatus.closed) is True
        assert service._validate_transition("stabilized", DriftIncidentStatus.acknowledged) is False

    def test_valid_transitions_from_reconciled(self):
        """Test valid transitions from reconciled status."""
        service = DriftIncidentService()

        assert service._validate_transition("reconciled", DriftIncidentStatus.closed) is True
        assert service._validate_transition("reconciled", DriftIncidentStatus.acknowledged) is False
        assert service._validate_transition("reconciled", DriftIncidentStatus.stabilized) is False

    def test_no_transitions_from_closed(self):
        """Test that closed is a terminal state."""
        service = DriftIncidentService()

        for status in DriftIncidentStatus:
            assert service._validate_transition("closed", status) is False


class TestGetIncidents:
    """Tests for get_incidents method."""

    @pytest.mark.asyncio
    async def test_get_incidents_success(self):
        """Test successful retrieval of incidents."""
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "inc-1", "payload_purged_at": None},
            {"id": "inc-2", "payload_purged_at": None}
        ]
        mock_response.count = 2

        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.neq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.range.return_value = mock_query
            mock_query.execute.return_value = mock_response
            mock_db.client.table.return_value = mock_query

            service = DriftIncidentService()
            result = await service.get_incidents(MOCK_TENANT_ID)

            # Verify enriched items with payload_available and is_deleted
            assert len(result["items"]) == 2
            assert result["items"][0]["id"] == "inc-1"
            assert result["items"][0]["payload_available"] is True
            assert result["items"][0]["is_deleted"] is False
            assert result["total"] == 2
            assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_get_incidents_with_filters(self):
        """Test getting incidents with environment and status filters."""
        mock_response = MagicMock()
        mock_response.data = [{"id": "inc-1"}]
        mock_response.count = 1

        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.range.return_value = mock_query
            mock_query.execute.return_value = mock_response
            mock_db.client.table.return_value = mock_query

            service = DriftIncidentService()
            result = await service.get_incidents(
                MOCK_TENANT_ID,
                environment_id=MOCK_ENVIRONMENT_ID,
                status_filter="detected",
            )

            assert len(result["items"]) == 1


class TestGetIncident:
    """Tests for get_incident method."""

    @pytest.mark.asyncio
    async def test_get_incident_success(self, mock_incident):
        """Test successful retrieval of single incident."""
        mock_response = MagicMock()
        mock_response.data = mock_incident

        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.single.return_value = mock_query
            mock_query.execute.return_value = mock_response
            mock_db.client.table.return_value = mock_query

            service = DriftIncidentService()
            result = await service.get_incident(MOCK_TENANT_ID, MOCK_INCIDENT_ID)

            assert result == mock_incident

    @pytest.mark.asyncio
    async def test_get_incident_not_found(self):
        """Test getting non-existent incident returns None."""
        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.single.return_value = mock_query
            mock_query.execute.side_effect = Exception("Not found")
            mock_db.client.table.return_value = mock_query

            service = DriftIncidentService()
            result = await service.get_incident(MOCK_TENANT_ID, "non-existent")

            assert result is None


class TestCreateIncident:
    """Tests for create_incident method."""

    @pytest.mark.asyncio
    async def test_create_incident_success(self, mock_incident):
        """Test successful incident creation."""
        service = DriftIncidentService()

        with patch.object(service, "get_active_incident_for_environment", new_callable=AsyncMock) as mock_active:
            mock_active.return_value = None

            with patch("app.services.drift_incident_service.db_service") as mock_db:
                # Mock insert response
                mock_insert_response = MagicMock()
                mock_insert_response.data = [mock_incident]

                mock_insert_query = MagicMock()
                mock_insert_query.insert.return_value = mock_insert_query
                mock_insert_query.execute.return_value = mock_insert_response

                # Mock update response for environment update
                mock_update_query = MagicMock()
                mock_update_query.update.return_value = mock_update_query
                mock_update_query.eq.return_value = mock_update_query
                mock_update_query.execute.return_value = MagicMock(data=[{}])

                def table_side_effect(name):
                    if name == "drift_incidents":
                        return mock_insert_query
                    elif name == "environments":
                        return mock_update_query
                    return MagicMock()

                mock_db.client.table.side_effect = table_side_effect

                result = await service.create_incident(
                    tenant_id=MOCK_TENANT_ID,
                    environment_id=MOCK_ENVIRONMENT_ID,
                    user_id=MOCK_USER_ID,
                    title="Test Incident",
                )

                assert result["id"] == mock_incident["id"]
                assert result["status"] == mock_incident["status"]

    @pytest.mark.asyncio
    async def test_create_incident_conflict(self, mock_incident):
        """Test creating incident when one already exists."""
        service = DriftIncidentService()

        with patch.object(service, "get_active_incident_for_environment", new_callable=AsyncMock) as mock_active:
            mock_active.return_value = mock_incident

            with pytest.raises(HTTPException) as exc_info:
                await service.create_incident(
                    tenant_id=MOCK_TENANT_ID,
                    environment_id=MOCK_ENVIRONMENT_ID,
                )

            assert exc_info.value.status_code == 409
            assert "active_incident_exists" in str(exc_info.value.detail)


class TestAcknowledgeIncident:
    """Tests for acknowledge_incident method."""

    @pytest.mark.asyncio
    async def test_acknowledge_incident_success(self, mock_incident):
        """Test successful incident acknowledgment."""
        acknowledged_incident = {
            **mock_incident,
            "status": DriftIncidentStatus.acknowledged.value,
        }

        service = DriftIncidentService()

        with patch.object(service, "get_incident", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_incident

            with patch("app.services.drift_incident_service.db_service") as mock_db:
                mock_query = MagicMock()
                mock_query.update.return_value = mock_query
                mock_query.eq.return_value = mock_query
                mock_query.execute.return_value = MagicMock(data=[acknowledged_incident])
                mock_db.client.table.return_value = mock_query

                result = await service.acknowledge_incident(
                    tenant_id=MOCK_TENANT_ID,
                    incident_id=MOCK_INCIDENT_ID,
                    user_id=MOCK_USER_ID,
                    reason="Investigating",
                )

                assert result["status"] == DriftIncidentStatus.acknowledged.value

    @pytest.mark.asyncio
    async def test_acknowledge_incident_not_found(self):
        """Test acknowledging non-existent incident."""
        service = DriftIncidentService()

        with patch.object(service, "get_incident", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await service.acknowledge_incident(
                    tenant_id=MOCK_TENANT_ID,
                    incident_id="non-existent",
                    user_id=MOCK_USER_ID,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_acknowledge_incident_invalid_transition(self, mock_incident):
        """Test acknowledging already acknowledged incident."""
        already_acknowledged = {
            **mock_incident,
            "status": DriftIncidentStatus.closed.value,
        }

        service = DriftIncidentService()

        with patch.object(service, "get_incident", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = already_acknowledged

            with pytest.raises(HTTPException) as exc_info:
                await service.acknowledge_incident(
                    tenant_id=MOCK_TENANT_ID,
                    incident_id=MOCK_INCIDENT_ID,
                    user_id=MOCK_USER_ID,
                )

            assert exc_info.value.status_code == 400


class TestStabilizeIncident:
    """Tests for stabilize_incident method."""

    @pytest.mark.asyncio
    async def test_stabilize_incident_success(self, mock_acknowledged_incident):
        """Test successful incident stabilization."""
        stabilized_incident = {
            **mock_acknowledged_incident,
            "status": DriftIncidentStatus.stabilized.value,
        }

        service = DriftIncidentService()

        with patch.object(service, "get_incident", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_acknowledged_incident

            with patch("app.services.drift_incident_service.db_service") as mock_db:
                mock_query = MagicMock()
                mock_query.update.return_value = mock_query
                mock_query.eq.return_value = mock_query
                mock_query.execute.return_value = MagicMock(data=[stabilized_incident])
                mock_db.client.table.return_value = mock_query

                result = await service.stabilize_incident(
                    tenant_id=MOCK_TENANT_ID,
                    incident_id=MOCK_INCIDENT_ID,
                    user_id=MOCK_USER_ID,
                )

                assert result["status"] == DriftIncidentStatus.stabilized.value

    @pytest.mark.asyncio
    async def test_stabilize_from_detected_fails(self, mock_incident):
        """Test that stabilizing from detected status fails."""
        service = DriftIncidentService()

        with patch.object(service, "get_incident", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_incident

            with pytest.raises(HTTPException) as exc_info:
                await service.stabilize_incident(
                    tenant_id=MOCK_TENANT_ID,
                    incident_id=MOCK_INCIDENT_ID,
                    user_id=MOCK_USER_ID,
                )

            assert exc_info.value.status_code == 400


class TestReconcileIncident:
    """Tests for reconcile_incident method."""

    @pytest.mark.asyncio
    async def test_reconcile_incident_success(self, mock_acknowledged_incident):
        """Test successful incident reconciliation."""
        reconciled_incident = {
            **mock_acknowledged_incident,
            "status": DriftIncidentStatus.reconciled.value,
            "resolution_type": ResolutionType.promote.value,
        }

        service = DriftIncidentService()

        with patch.object(service, "get_incident", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_acknowledged_incident

            with patch("app.services.drift_incident_service.db_service") as mock_db:
                mock_query = MagicMock()
                mock_query.update.return_value = mock_query
                mock_query.eq.return_value = mock_query
                mock_query.execute.return_value = MagicMock(data=[reconciled_incident])
                mock_db.client.table.return_value = mock_query

                result = await service.reconcile_incident(
                    tenant_id=MOCK_TENANT_ID,
                    incident_id=MOCK_INCIDENT_ID,
                    user_id=MOCK_USER_ID,
                    resolution_type=ResolutionType.promote,
                )

                assert result["status"] == DriftIncidentStatus.reconciled.value
                assert result["resolution_type"] == ResolutionType.promote.value


class TestCloseIncident:
    """Tests for close_incident method."""

    @pytest.mark.asyncio
    async def test_close_incident_success(self, mock_incident):
        """Test successful incident closure."""
        closed_incident = {
            **mock_incident,
            "status": DriftIncidentStatus.closed.value,
        }

        service = DriftIncidentService()

        with patch.object(service, "get_incident", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_incident

            with patch("app.services.drift_incident_service.db_service") as mock_db:
                mock_query = MagicMock()
                mock_query.update.return_value = mock_query
                mock_query.eq.return_value = mock_query
                mock_query.execute.return_value = MagicMock(data=[closed_incident])
                mock_db.client.table.return_value = mock_query

                result = await service.close_incident(
                    tenant_id=MOCK_TENANT_ID,
                    incident_id=MOCK_INCIDENT_ID,
                    user_id=MOCK_USER_ID,
                    reason="Issue resolved",
                )

                assert result["status"] == DriftIncidentStatus.closed.value

    @pytest.mark.asyncio
    async def test_close_already_closed_fails(self, mock_incident):
        """Test that closing an already closed incident fails."""
        closed_incident = {**mock_incident, "status": DriftIncidentStatus.closed.value}

        service = DriftIncidentService()

        with patch.object(service, "get_incident", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = closed_incident

            with pytest.raises(HTTPException) as exc_info:
                await service.close_incident(
                    tenant_id=MOCK_TENANT_ID,
                    incident_id=MOCK_INCIDENT_ID,
                    user_id=MOCK_USER_ID,
                )

            assert exc_info.value.status_code == 400


class TestGetIncidentStats:
    """Tests for get_incident_stats method."""

    @pytest.mark.asyncio
    async def test_get_stats_success(self):
        """Test getting incident statistics."""
        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.execute.return_value = MagicMock(count=2)
            mock_db.client.table.return_value = mock_query

            service = DriftIncidentService()
            result = await service.get_incident_stats(MOCK_TENANT_ID)

            assert "total" in result
            assert "by_status" in result
            assert "open" in result

    @pytest.mark.asyncio
    async def test_get_stats_handles_error(self):
        """Test that stats return empty on error."""
        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_db.client.table.side_effect = Exception("DB error")

            service = DriftIncidentService()
            result = await service.get_incident_stats(MOCK_TENANT_ID)

            assert result["total"] == 0
            assert result["open"] == 0


class TestRefreshIncidentDrift:
    """Tests for refresh_incident_drift method."""

    @pytest.mark.asyncio
    async def test_refresh_drift_success(self, mock_incident):
        """Test refreshing incident drift data."""
        updated_incident = {
            **mock_incident,
            "affected_workflows": [{"workflow_id": "wf-1", "workflow_name": "Test"}],
        }

        service = DriftIncidentService()

        with patch.object(service, "get_incident", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_incident

            with patch("app.services.drift_incident_service.db_service") as mock_db:
                mock_query = MagicMock()
                mock_query.update.return_value = mock_query
                mock_query.eq.return_value = mock_query
                mock_query.execute.return_value = MagicMock(data=[updated_incident])
                mock_db.client.table.return_value = mock_query

                affected = [
                    AffectedWorkflow(
                        workflow_id="wf-1",
                        workflow_name="Test",
                        drift_type="modified",
                    )
                ]

                result = await service.refresh_incident_drift(
                    tenant_id=MOCK_TENANT_ID,
                    incident_id=MOCK_INCIDENT_ID,
                    affected_workflows=affected,
                )

                assert len(result["affected_workflows"]) == 1

    @pytest.mark.asyncio
    async def test_refresh_closed_incident_fails(self, mock_incident):
        """Test that refreshing a closed incident fails."""
        closed_incident = {**mock_incident, "status": DriftIncidentStatus.closed.value}

        service = DriftIncidentService()

        with patch.object(service, "get_incident", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = closed_incident

            with pytest.raises(HTTPException) as exc_info:
                await service.refresh_incident_drift(
                    tenant_id=MOCK_TENANT_ID,
                    incident_id=MOCK_INCIDENT_ID,
                    affected_workflows=[],
                )

            assert exc_info.value.status_code == 400


class TestEnrichIncident:
    """Tests for _enrich_incident method (retention support)."""

    def test_enrich_incident_with_none(self):
        """Test that enriching None returns None."""
        service = DriftIncidentService()
        result = service._enrich_incident(None)
        assert result is None

    def test_enrich_incident_payload_available_true(self):
        """Test payload_available is True when payload_purged_at is None."""
        service = DriftIncidentService()
        incident = {
            "id": "inc-1",
            "payload_purged_at": None,
        }
        result = service._enrich_incident(incident)
        assert result["payload_available"] is True

    def test_enrich_incident_payload_available_false(self):
        """Test payload_available is False when payload_purged_at is set."""
        service = DriftIncidentService()
        incident = {
            "id": "inc-1",
            "payload_purged_at": "2024-01-01T00:00:00Z",
        }
        result = service._enrich_incident(incident)
        assert result["payload_available"] is False

    def test_enrich_incident_is_deleted_default(self):
        """Test is_deleted defaults to False when not present."""
        service = DriftIncidentService()
        incident = {
            "id": "inc-1",
            "payload_purged_at": None,
        }
        result = service._enrich_incident(incident)
        assert result["is_deleted"] is False

    def test_enrich_incident_preserves_is_deleted(self):
        """Test is_deleted is preserved when already present."""
        service = DriftIncidentService()
        incident = {
            "id": "inc-1",
            "payload_purged_at": None,
            "is_deleted": True,
        }
        result = service._enrich_incident(incident)
        assert result["is_deleted"] is True


class TestEnrichIncidents:
    """Tests for _enrich_incidents method (batch enrichment)."""

    def test_enrich_incidents_empty_list(self):
        """Test enriching empty list returns empty list."""
        service = DriftIncidentService()
        result = service._enrich_incidents([])
        assert result == []

    def test_enrich_incidents_multiple(self):
        """Test enriching multiple incidents."""
        service = DriftIncidentService()
        incidents = [
            {"id": "inc-1", "payload_purged_at": None},
            {"id": "inc-2", "payload_purged_at": "2024-01-01T00:00:00Z"},
            {"id": "inc-3", "payload_purged_at": None, "is_deleted": True},
        ]
        result = service._enrich_incidents(incidents)

        assert len(result) == 3
        assert result[0]["payload_available"] is True
        assert result[0]["is_deleted"] is False
        assert result[1]["payload_available"] is False
        assert result[1]["is_deleted"] is False
        assert result[2]["payload_available"] is True
        assert result[2]["is_deleted"] is True


class TestGetIncidentsWithDeleted:
    """Tests for get_incidents with include_deleted parameter."""

    @pytest.mark.asyncio
    async def test_get_incidents_excludes_deleted_by_default(self):
        """Test that deleted incidents are excluded by default."""
        mock_response = MagicMock()
        mock_response.data = [{"id": "inc-1", "payload_purged_at": None}]
        mock_response.count = 1

        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.neq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.range.return_value = mock_query
            mock_query.execute.return_value = mock_response
            mock_db.client.table.return_value = mock_query

            service = DriftIncidentService()
            result = await service.get_incidents(MOCK_TENANT_ID)

            # Verify is_deleted=False filter was applied
            eq_calls = mock_query.eq.call_args_list
            assert any("is_deleted" in str(c) for c in eq_calls)

    @pytest.mark.asyncio
    async def test_get_incidents_includes_deleted_when_requested(self):
        """Test that deleted incidents are included when include_deleted=True."""
        mock_response = MagicMock()
        mock_response.data = [
            {"id": "inc-1", "payload_purged_at": None, "is_deleted": False},
            {"id": "inc-2", "payload_purged_at": "2024-01-01T00:00:00Z", "is_deleted": True},
        ]
        mock_response.count = 2

        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.neq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.range.return_value = mock_query
            mock_query.execute.return_value = mock_response
            mock_db.client.table.return_value = mock_query

            service = DriftIncidentService()
            result = await service.get_incidents(MOCK_TENANT_ID, include_deleted=True)

            # Should include both incidents
            assert len(result["items"]) == 2
            assert result["items"][0]["payload_available"] is True
            assert result["items"][1]["payload_available"] is False


class TestGetActiveIncidentForEnvironment:
    """Tests for get_active_incident_for_environment with soft-delete support."""

    @pytest.mark.asyncio
    async def test_get_active_excludes_deleted(self):
        """Test that deleted incidents are excluded from active query."""
        mock_response = MagicMock()
        mock_response.data = [{"id": "inc-1", "payload_purged_at": None, "status": "detected"}]

        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.neq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.execute.return_value = mock_response
            mock_db.client.table.return_value = mock_query

            service = DriftIncidentService()
            result = await service.get_active_incident_for_environment(
                MOCK_TENANT_ID, MOCK_ENVIRONMENT_ID
            )

            # Verify is_deleted=False filter was applied
            eq_calls = mock_query.eq.call_args_list
            assert any("is_deleted" in str(c) for c in eq_calls)
            assert result is not None
            assert result["payload_available"] is True

    @pytest.mark.asyncio
    async def test_get_active_returns_none_when_no_active(self):
        """Test that None is returned when no active incident exists."""
        mock_response = MagicMock()
        mock_response.data = []

        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.neq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_query.execute.return_value = mock_response
            mock_db.client.table.return_value = mock_query

            service = DriftIncidentService()
            result = await service.get_active_incident_for_environment(
                MOCK_TENANT_ID, MOCK_ENVIRONMENT_ID
            )

            assert result is None


class TestGetIncidentEnrichment:
    """Tests for get_incident enrichment."""

    @pytest.mark.asyncio
    async def test_get_incident_returns_enriched_data(self, mock_incident):
        """Test that get_incident returns enriched data with payload_available."""
        incident_with_purge = {
            **mock_incident,
            "payload_purged_at": "2024-01-01T00:00:00Z",
        }

        mock_response = MagicMock()
        mock_response.data = incident_with_purge

        with patch("app.services.drift_incident_service.db_service") as mock_db:
            mock_query = MagicMock()
            mock_query.select.return_value = mock_query
            mock_query.eq.return_value = mock_query
            mock_query.single.return_value = mock_query
            mock_query.execute.return_value = mock_response
            mock_db.client.table.return_value = mock_query

            service = DriftIncidentService()
            result = await service.get_incident(MOCK_TENANT_ID, MOCK_INCIDENT_ID)

            assert result["payload_available"] is False
            assert result["is_deleted"] is False
