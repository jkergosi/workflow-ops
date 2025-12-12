"""
API tests for the workflows endpoint.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


# Mock entitlements for all workflow tests
@pytest.fixture(autouse=True)
def mock_entitlements():
    """Mock entitlements service to allow all features for testing."""
    with patch("app.core.entitlements_gate.entitlements_service") as mock_ent:
        mock_ent.enforce_flag = AsyncMock(return_value=None)
        mock_ent.has_flag = AsyncMock(return_value=True)
        mock_ent.can_create_workflow = AsyncMock(return_value=(True, "", 0, 100))
        yield mock_ent


class TestWorkflowsAPIGet:
    """Tests for GET /api/v1/workflows endpoints."""

    @pytest.mark.api
    def test_get_workflows_success(self, client: TestClient, mock_workflows, auth_headers):
        """GET /workflows should return list of workflows from cache."""
        with patch("app.api.endpoints.workflows.db_service") as mock_db:
            mock_db.get_environment = AsyncMock(return_value={
                "id": "env-1",
                "n8n_base_url": "https://n8n.example.com",
                "n8n_api_key": "test-key",
            })
            mock_db.get_workflows = AsyncMock(return_value=mock_workflows)

            response = client.get(
                "/api/v1/workflows",
                params={"environment_id": "env-1"},
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    @pytest.mark.api
    def test_get_workflows_empty_list(self, client: TestClient, auth_headers):
        """GET /workflows with no workflows should return empty list."""
        with patch("app.api.endpoints.workflows.db_service") as mock_db:
            mock_db.get_environment = AsyncMock(return_value={
                "id": "env-1",
                "n8n_base_url": "https://n8n.example.com",
            })
            mock_db.get_workflows = AsyncMock(return_value=[])

            response = client.get(
                "/api/v1/workflows",
                params={"environment_id": "env-1"},
                headers=auth_headers
            )

            assert response.status_code == 200
            assert response.json() == []

    @pytest.mark.api
    def test_get_workflows_requires_environment(self, client: TestClient, auth_headers):
        """GET /workflows without environment should return 400."""
        response = client.get("/api/v1/workflows", headers=auth_headers)

        assert response.status_code == 400
        assert "environment" in response.json()["detail"].lower()

    @pytest.mark.api
    def test_get_workflows_environment_not_found(self, client: TestClient, auth_headers):
        """GET /workflows with non-existent environment should return 404."""
        with patch("app.api.endpoints.workflows.db_service") as mock_db:
            mock_db.get_environment = AsyncMock(return_value=None)

            response = client.get(
                "/api/v1/workflows",
                params={"environment_id": "non-existent"},
                headers=auth_headers
            )

            assert response.status_code == 404


class TestWorkflowsAPIActivation:
    """Tests for workflow activation/deactivation endpoints."""

    @pytest.mark.api
    def test_activate_workflow_success(self, client: TestClient, mock_workflows, auth_headers):
        """POST /workflows/{id}/activate should activate workflow."""
        workflow = mock_workflows[0]

        with patch("app.api.endpoints.workflows.db_service") as mock_db:
            mock_db.get_environment = AsyncMock(return_value={
                "id": "env-1",
                "n8n_base_url": "https://n8n.example.com",
                "n8n_api_key": "test-key",
            })
            with patch("app.api.endpoints.workflows.ProviderRegistry") as mock_registry:
                mock_adapter = MagicMock()
                mock_adapter.activate_workflow = AsyncMock(return_value={
                    "id": workflow["n8n_workflow_id"],
                    "active": True
                })
                mock_registry.get_adapter_for_environment.return_value = mock_adapter

                mock_db.update_workflow_active_status = AsyncMock(return_value=None)

                response = client.post(
                    f"/api/v1/workflows/{workflow['n8n_workflow_id']}/activate",
                    params={"environment_id": "env-1"},
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert data.get("active") is True or data.get("success") is True

    @pytest.mark.api
    def test_deactivate_workflow_success(self, client: TestClient, mock_workflows, auth_headers):
        """POST /workflows/{id}/deactivate should deactivate workflow."""
        workflow = mock_workflows[0]

        with patch("app.api.endpoints.workflows.db_service") as mock_db:
            mock_db.get_environment = AsyncMock(return_value={
                "id": "env-1",
                "n8n_base_url": "https://n8n.example.com",
                "n8n_api_key": "test-key",
            })
            with patch("app.api.endpoints.workflows.ProviderRegistry") as mock_registry:
                mock_adapter = MagicMock()
                mock_adapter.deactivate_workflow = AsyncMock(return_value={
                    "id": workflow["n8n_workflow_id"],
                    "active": False
                })
                mock_registry.get_adapter_for_environment.return_value = mock_adapter

                mock_db.update_workflow_active_status = AsyncMock(return_value=None)

                response = client.post(
                    f"/api/v1/workflows/{workflow['n8n_workflow_id']}/deactivate",
                    params={"environment_id": "env-1"},
                    headers=auth_headers
                )

                assert response.status_code == 200


class TestWorkflowsAPIDelete:
    """Tests for DELETE /api/v1/workflows/{id} endpoint."""

    @pytest.mark.api
    def test_delete_workflow_success(self, client: TestClient, mock_workflows, auth_headers):
        """DELETE /workflows/{id} should delete workflow."""
        workflow = mock_workflows[0]

        with patch("app.api.endpoints.workflows.db_service") as mock_db:
            mock_db.get_environment = AsyncMock(return_value={
                "id": "env-1",
                "n8n_base_url": "https://n8n.example.com",
                "n8n_api_key": "test-key",
            })
            with patch("app.api.endpoints.workflows.ProviderRegistry") as mock_registry:
                mock_adapter = MagicMock()
                mock_adapter.delete_workflow = AsyncMock(return_value=None)
                mock_registry.get_adapter_for_environment.return_value = mock_adapter

                mock_db.delete_workflow = AsyncMock(return_value=None)

                response = client.delete(
                    f"/api/v1/workflows/{workflow['n8n_workflow_id']}",
                    params={"environment_id": "env-1"},
                    headers=auth_headers
                )

                # Delete can return 200 or 204
                assert response.status_code in [200, 204]
