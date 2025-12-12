"""
Unit tests for the N8N API client.
"""
import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock

from app.services.n8n_client import N8NClient


class TestN8NClientInit:
    """Tests for N8NClient initialization."""

    @pytest.mark.unit
    def test_init_with_explicit_params(self):
        """Should accept explicit base_url and api_key."""
        client = N8NClient(
            base_url="https://custom.n8n.io",
            api_key="custom-key"
        )

        assert client.base_url == "https://custom.n8n.io"
        assert client.api_key == "custom-key"

    @pytest.mark.unit
    def test_init_sets_headers(self):
        """Should set proper headers with API key."""
        client = N8NClient(base_url="https://n8n.io", api_key="test-key")

        assert client.headers["X-N8N-API-KEY"] == "test-key"
        assert client.headers["Content-Type"] == "application/json"

    @pytest.mark.unit
    def test_init_falls_back_to_settings(self):
        """Should fall back to settings when params not provided."""
        with patch("app.services.n8n_client.settings") as mock_settings:
            mock_settings.N8N_API_URL = "https://settings.n8n.io"
            mock_settings.N8N_API_KEY = "settings-key"

            client = N8NClient()

            assert client.base_url == "https://settings.n8n.io"
            assert client.api_key == "settings-key"


class TestGetWorkflows:
    """Tests for get_workflows method."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_workflows_returns_list(self, client):
        """Should return list of workflows from API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "wf-1", "name": "Workflow 1"},
                {"id": "wf-2", "name": "Workflow 2"}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.get_workflows()

        assert len(result) == 2
        assert result[0]["id"] == "wf-1"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_workflows_handles_array_response(self, client):
        """Should handle API returning array directly."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "wf-1", "name": "Workflow 1"}
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.get_workflows()

        assert len(result) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_workflows_raises_on_error(self, client):
        """Should raise HTTPStatusError on API error."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await client.get_workflows()


class TestGetWorkflow:
    """Tests for get_workflow method."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_workflow_returns_workflow(self, client):
        """Should return single workflow by ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "wf-1",
            "name": "Test Workflow",
            "nodes": [],
            "connections": {}
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.get_workflow("wf-1")

        assert result["id"] == "wf-1"
        assert result["name"] == "Test Workflow"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_workflow_uses_correct_url(self, client):
        """Should call correct API endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "wf-123"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await client.get_workflow("wf-123")

            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            assert "wf-123" in call_args[0][0]


class TestCreateWorkflow:
    """Tests for create_workflow method."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_create_workflow_posts_data(self, client):
        """Should POST workflow data to create endpoint."""
        workflow_data = {"name": "New Workflow", "nodes": [], "connections": {}}

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "wf-new", **workflow_data}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.create_workflow(workflow_data)

        assert result["id"] == "wf-new"
        mock_client.post.assert_called_once()


class TestUpdateWorkflow:
    """Tests for update_workflow method."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_update_workflow_cleans_data(self, client):
        """Should only send allowed fields (name, nodes, connections, settings)."""
        workflow_data = {
            "name": "Updated",
            "nodes": [{"id": "1"}],
            "connections": {},
            "settings": {"executionOrder": "v1"},
            "shared": {"should": "be removed"},
            "id": "should-be-removed",
            "updatedAt": "should-be-removed"
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "wf-1", "name": "Updated"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.put = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await client.update_workflow("wf-1", workflow_data)

            call_args = mock_client.put.call_args
            sent_data = call_args.kwargs["json"]

            assert "name" in sent_data
            assert "nodes" in sent_data
            assert "connections" in sent_data
            assert "settings" in sent_data
            assert "shared" not in sent_data
            assert "id" not in sent_data
            assert "updatedAt" not in sent_data


class TestDeleteWorkflow:
    """Tests for delete_workflow method."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_delete_workflow_returns_true(self, client):
        """Should return True on successful delete."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.delete_workflow("wf-1")

        assert result is True


class TestUpdateWorkflowTags:
    """Tests for update_workflow_tags method."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_update_tags_sends_tag_objects(self, client):
        """Should send tag objects with IDs."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"tags": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.put = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await client.update_workflow_tags("wf-1", ["tag-1", "tag-2"])

            call_args = mock_client.put.call_args
            sent_data = call_args.kwargs["json"]

            assert sent_data == [{"id": "tag-1"}, {"id": "tag-2"}]


class TestActivateDeactivateWorkflow:
    """Tests for activate/deactivate workflow methods."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_activate_workflow(self, client):
        """Should POST to activate endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "wf-1", "active": True}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.activate_workflow("wf-1")

            assert result["active"] is True
            call_url = mock_client.post.call_args[0][0]
            assert "activate" in call_url

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_deactivate_workflow(self, client):
        """Should POST to deactivate endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "wf-1", "active": False}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.deactivate_workflow("wf-1")

            assert result["active"] is False
            call_url = mock_client.post.call_args[0][0]
            assert "deactivate" in call_url


class TestTestConnection:
    """Tests for test_connection method."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_connection_returns_true_on_success(self, client):
        """Should return True when API is reachable."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.test_connection()

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_connection_returns_false_on_error(self, client):
        """Should return False when API is not reachable."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.test_connection()

        assert result is False


class TestGetExecutions:
    """Tests for get_executions method."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_executions_with_limit(self, client):
        """Should pass limit parameter to API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await client.get_executions(limit=50)

            call_args = mock_client.get.call_args
            assert call_args.kwargs["params"]["limit"] == 50


class TestGetCredentials:
    """Tests for get_credentials method."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_credentials_enriches_with_workflow_usage(self, client):
        """Should enrich credentials with workflow usage info."""
        credentials_response = MagicMock()
        credentials_response.json.return_value = {
            "data": [
                {"id": "cred-1", "name": "API Key", "type": "apiKey"}
            ]
        }
        credentials_response.raise_for_status = MagicMock()

        workflows_response = MagicMock()
        workflows_response.json.return_value = {
            "data": [
                {
                    "id": "wf-1",
                    "name": "Workflow 1",
                    "nodes": [
                        {
                            "type": "n8n-nodes-base.httpRequest",
                            "credentials": {
                                "apiKey": {"id": "cred-1", "name": "API Key"}
                            }
                        }
                    ]
                }
            ]
        }
        workflows_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[credentials_response, workflows_response])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.get_credentials()

        assert len(result) == 1
        assert "used_by_workflows" in result[0]
        assert len(result[0]["used_by_workflows"]) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_credentials_falls_back_to_workflow_extraction(self, client):
        """Should fall back to extracting credentials from workflows if API fails."""
        credentials_error = MagicMock()
        credentials_error.status_code = 403
        credentials_error.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden",
            request=MagicMock(),
            response=credentials_error
        )

        workflows_response = MagicMock()
        workflows_response.json.return_value = {
            "data": [
                {
                    "id": "wf-1",
                    "name": "Workflow 1",
                    "nodes": [
                        {
                            "type": "n8n-nodes-base.httpRequest",
                            "credentials": {
                                "apiKey": {"id": "cred-1", "name": "My API Key"}
                            }
                        }
                    ]
                }
            ]
        }
        workflows_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[credentials_error, workflows_response])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.get_credentials()

        assert len(result) == 1
        assert result[0]["name"] == "My API Key"


class TestExtractCredentialUsageFromWorkflows:
    """Tests for _extract_credential_usage_from_workflows helper."""

    @pytest.mark.unit
    def test_extracts_credential_ids(self):
        """Should extract credential IDs from workflow nodes."""
        client = N8NClient(base_url="https://n8n.io", api_key="test-key")

        workflows = [
            {
                "id": "wf-1",
                "name": "Workflow 1",
                "nodes": [
                    {
                        "type": "n8n-nodes-base.httpRequest",
                        "credentials": {
                            "httpBasicAuth": {"id": "cred-1", "name": "Basic Auth"}
                        }
                    }
                ]
            }
        ]

        result = client._extract_credential_usage_from_workflows(workflows)

        assert "cred-1" in result
        assert len(result["cred-1"]) == 1
        assert result["cred-1"][0]["name"] == "Workflow 1"

    @pytest.mark.unit
    def test_handles_multiple_credentials_per_node(self):
        """Should handle nodes with multiple credentials."""
        client = N8NClient(base_url="https://n8n.io", api_key="test-key")

        workflows = [
            {
                "id": "wf-1",
                "name": "Workflow 1",
                "nodes": [
                    {
                        "type": "n8n-nodes-base.someNode",
                        "credentials": {
                            "oauth2Api": {"id": "cred-oauth", "name": "OAuth"},
                            "apiKey": {"id": "cred-api", "name": "API Key"}
                        }
                    }
                ]
            }
        ]

        result = client._extract_credential_usage_from_workflows(workflows)

        assert "cred-oauth" in result
        assert "cred-api" in result


class TestCredentialCRUD:
    """Tests for credential CRUD operations."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_credential(self, client):
        """Should get single credential by ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "cred-1", "name": "Test", "type": "apiKey"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.get_credential("cred-1")

        assert result["id"] == "cred-1"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_create_credential(self, client):
        """Should create new credential."""
        credential_data = {
            "name": "New Credential",
            "type": "apiKey",
            "data": {"apiKey": "secret"}
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "cred-new", **credential_data}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.create_credential(credential_data)

        assert result["id"] == "cred-new"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_delete_credential(self, client):
        """Should delete credential."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.delete_credential("cred-1")

        assert result is True


class TestGetUsersAndTags:
    """Tests for get_users and get_tags methods."""

    @pytest.fixture
    def client(self):
        return N8NClient(base_url="https://n8n.io", api_key="test-key")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_users_returns_empty_on_forbidden(self, client):
        """Should return empty list if users endpoint returns 403."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden",
            request=MagicMock(),
            response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.get_users()

        assert result == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_tags_returns_list(self, client):
        """Should return list of tags."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "tag-1", "name": "Production"},
                {"id": "tag-2", "name": "Development"}
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.get_tags()

        assert len(result) == 2
        assert result[0]["name"] == "Production"
