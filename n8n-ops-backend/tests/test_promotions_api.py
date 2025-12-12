"""
API tests for the promotions endpoint.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


# Mock entitlements for all promotions tests
@pytest.fixture(autouse=True)
def mock_entitlements():
    """Mock entitlements service to allow all features for testing."""
    with patch("app.core.entitlements_gate.entitlements_service") as mock_ent:
        mock_ent.enforce_flag = AsyncMock(return_value=None)
        mock_ent.has_flag = AsyncMock(return_value=True)
        yield mock_ent


class TestPromotionsAPIGet:
    """Tests for GET /api/v1/promotions endpoints."""

    @pytest.mark.api
    def test_get_promotions_success(self, client: TestClient, auth_headers):
        """GET /promotions should return PromotionListResponse with data and total."""
        mock_promotions = [
            {
                "id": "promo-1",
                "tenant_id": "tenant-1",
                "pipeline_id": "pipeline-1",
                "status": "completed",
                "source_environment_id": "env-1",
                "target_environment_id": "env-2",
                "created_at": "2024-01-15T10:00:00Z",
            }
        ]

        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotions = AsyncMock(return_value=mock_promotions)

            response = client.get("/api/v1/promotions", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            # Response is PromotionListResponse with data and total
            assert "data" in data
            assert "total" in data

    @pytest.mark.api
    def test_get_promotions_empty_list(self, client: TestClient, auth_headers):
        """GET /promotions with no promotions should return empty data."""
        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotions = AsyncMock(return_value=[])

            response = client.get("/api/v1/promotions", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["data"] == []
            assert data["total"] == 0

    @pytest.mark.api
    def test_get_promotion_by_id_success(self, client: TestClient, auth_headers):
        """GET /promotions/{id} should return specific promotion."""
        mock_promotion = {
            "id": "promo-1",
            "tenant_id": "tenant-1",
            "pipeline_id": "pipeline-1",
            "status": "pending_approval",
            "source_environment_id": "env-1",
            "target_environment_id": "env-2",
            "workflows": [{"id": "wf-1", "name": "Test Workflow"}],
            "gate_results": [],
            "created_at": "2024-01-15T10:00:00Z",
        }

        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotion = AsyncMock(return_value=mock_promotion)
            # Also mock the pipeline lookup
            mock_db.get_pipeline = AsyncMock(return_value={
                "id": "pipeline-1",
                "name": "Test Pipeline",
                "stages": []
            })

            response = client.get("/api/v1/promotions/promo-1", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "promo-1"

    @pytest.mark.api
    def test_get_promotion_not_found(self, client: TestClient, auth_headers):
        """GET /promotions/{id} should return 404 for non-existent promotion."""
        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotion = AsyncMock(return_value=None)

            response = client.get("/api/v1/promotions/non-existent", headers=auth_headers)

            assert response.status_code == 404


class TestPromotionsAPIInitiate:
    """Tests for POST /api/v1/promotions/initiate endpoint."""

    @pytest.mark.api
    def test_initiate_promotion_pipeline_not_found(self, client: TestClient, auth_headers):
        """POST /promotions/initiate with invalid pipeline should return 404."""
        # Request body must match PromotionInitiateRequest schema
        initiate_request = {
            "pipeline_id": "00000000-0000-0000-0000-000000000001",
            "source_environment_id": "00000000-0000-0000-0000-000000000002",
            "target_environment_id": "00000000-0000-0000-0000-000000000003",
            "workflow_selections": [
                {
                    "workflow_id": "wf-1",
                    "workflow_name": "Test Workflow",
                    "change_type": "changed",
                    "enabled_in_source": True
                }
            ],
        }

        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_pipeline = AsyncMock(return_value=None)

            response = client.post(
                "/api/v1/promotions/initiate",
                json=initiate_request,
                headers=auth_headers
            )

            assert response.status_code == 404


class TestPromotionsAPIApproval:
    """Tests for promotion approval endpoints."""

    @pytest.mark.api
    def test_approve_promotion_success(self, client: TestClient, auth_headers):
        """POST /promotions/approvals/{id}/approve should approve promotion."""
        mock_promotion = {
            "id": "promo-1",
            "tenant_id": "tenant-1",
            "status": "pending_approval",
            "pipeline_id": "pipeline-1",
        }

        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotion = AsyncMock(return_value=mock_promotion)
            mock_db.get_pipeline = AsyncMock(return_value={
                "id": "pipeline-1",
                "stages": [{
                    "approvals": {"approval_type": "1 of N"}
                }]
            })
            mock_db.update_promotion = AsyncMock(return_value={
                **mock_promotion,
                "status": "approved",
            })

            with patch("app.api.endpoints.promotions.notification_service") as mock_notify:
                mock_notify.emit_event = AsyncMock(return_value=None)

                with patch("app.api.endpoints.promotions.promotion_service") as mock_promo_svc:
                    mock_promo_svc._create_audit_log = AsyncMock(return_value=None)

                    # Request body must include action
                    response = client.post(
                        "/api/v1/promotions/approvals/promo-1/approve",
                        json={"action": "approve"},
                        headers=auth_headers
                    )

                    assert response.status_code == 200

    @pytest.mark.api
    def test_approve_promotion_not_found(self, client: TestClient, auth_headers):
        """POST /promotions/approvals/{id}/approve for non-existent should return 404."""
        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotion = AsyncMock(return_value=None)

            response = client.post(
                "/api/v1/promotions/approvals/non-existent/approve",
                json={"action": "approve"},
                headers=auth_headers
            )

            assert response.status_code == 404

    @pytest.mark.api
    def test_approve_promotion_wrong_status(self, client: TestClient, auth_headers):
        """POST /promotions/approvals/{id}/approve on completed promotion should fail."""
        mock_promotion = {
            "id": "promo-1",
            "tenant_id": "tenant-1",
            "status": "completed",  # Already completed
        }

        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotion = AsyncMock(return_value=mock_promotion)

            response = client.post(
                "/api/v1/promotions/approvals/promo-1/approve",
                json={"action": "approve"},
                headers=auth_headers
            )

            assert response.status_code == 400


class TestPromotionsAPIExecute:
    """Tests for POST /api/v1/promotions/execute/{id} endpoint."""

    @pytest.mark.api
    def test_execute_promotion_not_approved(self, client: TestClient, auth_headers):
        """POST /promotions/execute/{id} on pending promotion should fail."""
        mock_promotion = {
            "id": "promo-1",
            "tenant_id": "tenant-1",
            "status": "pending_approval",  # Not approved yet
        }

        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotion = AsyncMock(return_value=mock_promotion)

            response = client.post(
                "/api/v1/promotions/execute/promo-1",
                headers=auth_headers
            )

            assert response.status_code == 400

    @pytest.mark.api
    def test_execute_promotion_not_found(self, client: TestClient, auth_headers):
        """POST /promotions/execute/{id} for non-existent should return 404."""
        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotion = AsyncMock(return_value=None)

            response = client.post(
                "/api/v1/promotions/execute/non-existent",
                headers=auth_headers
            )

            assert response.status_code == 404


class TestPromotionsAPIFiltering:
    """Tests for promotion filtering and pagination."""

    @pytest.mark.api
    def test_get_promotions_filter_by_status(self, client: TestClient, auth_headers):
        """GET /promotions with status filter should return filtered results."""
        mock_promotions = [
            {"id": "promo-1", "status": "pending_approval"},
        ]

        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotions = AsyncMock(return_value=mock_promotions)

            response = client.get(
                "/api/v1/promotions",
                params={"status": "pending_approval"},
                headers=auth_headers
            )

            assert response.status_code == 200

    @pytest.mark.api
    def test_get_promotions_filter_by_pipeline(self, client: TestClient, auth_headers):
        """GET /promotions with pipeline filter should return filtered results."""
        mock_promotions = [
            {"id": "promo-1", "pipeline_id": "pipeline-1"},
        ]

        with patch("app.api.endpoints.promotions.db_service") as mock_db:
            mock_db.get_promotions = AsyncMock(return_value=mock_promotions)

            response = client.get(
                "/api/v1/promotions",
                params={"pipeline_id": "pipeline-1"},
                headers=auth_headers
            )

            assert response.status_code == 200
