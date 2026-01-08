"""
API tests for the retention endpoints.

Tests the execution retention management API endpoints to ensure:
- Policy CRUD operations work correctly
- Preview functionality returns expected data
- Cleanup operations are properly validated
- Authentication and authorization are enforced
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


class TestRetentionPolicyAPI:
    """Tests for retention policy management endpoints."""

    @pytest.mark.api
    def test_get_retention_policy_success(self, client: TestClient, auth_headers):
        """GET /retention/policy should return the tenant's retention policy."""
        mock_policy = {
            "retention_days": 90,
            "is_enabled": True,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        with patch("app.api.endpoints.retention.retention_service.get_retention_policy") as mock_get:
            mock_get.return_value = mock_policy

            response = client.get("/api/v1/retention/policy", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["retention_days"] == 90
            assert data["is_enabled"] is True
            assert data["min_executions_to_keep"] == 100

    @pytest.mark.api
    def test_get_retention_policy_unauthorized(self, client: TestClient):
        """GET /retention/policy should return 401 without auth."""
        response = client.get("/api/v1/retention/policy")
        assert response.status_code == 401

    @pytest.mark.api
    def test_create_retention_policy_success(self, client: TestClient, auth_headers):
        """POST /retention/policy should create a new retention policy."""
        policy_request = {
            "retention_days": 60,
            "is_enabled": True,
            "min_executions_to_keep": 200,
        }

        mock_created_policy = {
            "retention_days": 60,
            "is_enabled": True,
            "min_executions_to_keep": 200,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        with patch("app.api.endpoints.retention.retention_service.create_retention_policy") as mock_create:
            mock_create.return_value = mock_created_policy

            response = client.post(
                "/api/v1/retention/policy",
                json=policy_request,
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["retention_days"] == 60
            assert data["is_enabled"] is True
            assert data["min_executions_to_keep"] == 200

    @pytest.mark.api
    def test_create_retention_policy_validation(self, client: TestClient, auth_headers):
        """POST /retention/policy should validate retention_days range."""
        # Test retention_days > 365 (should fail)
        invalid_request = {
            "retention_days": 400,
            "is_enabled": True,
            "min_executions_to_keep": 100,
        }

        response = client.post(
            "/api/v1/retention/policy",
            json=invalid_request,
            headers=auth_headers
        )

        # Should fail validation
        assert response.status_code == 422

    @pytest.mark.api
    def test_update_retention_policy_success(self, client: TestClient, auth_headers):
        """PATCH /retention/policy should update specific fields."""
        update_request = {
            "is_enabled": False,
        }

        mock_updated_policy = {
            "retention_days": 90,
            "is_enabled": False,
            "min_executions_to_keep": 100,
            "last_cleanup_at": None,
            "last_cleanup_deleted_count": 0,
        }

        with patch("app.api.endpoints.retention.retention_service.update_retention_policy") as mock_update:
            mock_update.return_value = mock_updated_policy

            response = client.patch(
                "/api/v1/retention/policy",
                json=update_request,
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["is_enabled"] is False
            assert data["retention_days"] == 90  # Unchanged

    @pytest.mark.api
    def test_update_retention_policy_empty_request(self, client: TestClient, auth_headers):
        """PATCH /retention/policy should reject empty updates."""
        empty_request = {}

        response = client.patch(
            "/api/v1/retention/policy",
            json=empty_request,
            headers=auth_headers
        )

        # Should reject empty update
        assert response.status_code == 400


class TestRetentionPreviewAPI:
    """Tests for retention cleanup preview endpoint."""

    @pytest.mark.api
    def test_get_cleanup_preview_success(self, client: TestClient, auth_headers):
        """GET /retention/preview should return cleanup preview data."""
        mock_preview = {
            "tenant_id": "test-tenant-id",
            "total_executions": 150000,
            "old_executions_count": 50000,
            "executions_to_delete": 49900,
            "cutoff_date": "2024-01-01T00:00:00",
            "retention_days": 90,
            "min_executions_to_keep": 100,
            "would_delete": True,
            "is_enabled": True,
        }

        with patch("app.api.endpoints.retention.retention_service.get_cleanup_preview") as mock_preview_fn:
            mock_preview_fn.return_value = mock_preview

            response = client.get("/api/v1/retention/preview", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["total_executions"] == 150000
            assert data["old_executions_count"] == 50000
            assert data["executions_to_delete"] == 49900
            assert data["would_delete"] is True

    @pytest.mark.api
    def test_get_cleanup_preview_with_error(self, client: TestClient, auth_headers):
        """GET /retention/preview should handle service errors."""
        mock_preview_error = {
            "tenant_id": "test-tenant-id",
            "error": "Database connection failed",
        }

        with patch("app.api.endpoints.retention.retention_service.get_cleanup_preview") as mock_preview_fn:
            mock_preview_fn.return_value = mock_preview_error

            response = client.get("/api/v1/retention/preview", headers=auth_headers)

            # Should return 500 when service returns error
            assert response.status_code == 500


class TestRetentionCleanupAPI:
    """Tests for manual retention cleanup endpoint."""

    @pytest.mark.api
    def test_trigger_cleanup_success(self, client: TestClient, auth_headers):
        """POST /retention/cleanup should trigger cleanup and return results."""
        mock_cleanup_result = {
            "tenant_id": "test-tenant-id",
            "deleted_count": 45000,
            "retention_days": 90,
            "is_enabled": True,
            "timestamp": "2024-04-01T12:00:00",
            "summary": {
                "before_count": 150000,
                "after_count": 105000,
            },
            "skipped": False,
        }

        with patch("app.api.endpoints.retention.retention_service.cleanup_tenant_executions") as mock_cleanup:
            mock_cleanup.return_value = mock_cleanup_result

            response = client.post("/api/v1/retention/cleanup", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["deleted_count"] == 45000
            assert data["skipped"] is False
            assert data["tenant_id"] == "test-tenant-id"

    @pytest.mark.api
    def test_trigger_cleanup_with_force(self, client: TestClient, auth_headers):
        """POST /retention/cleanup?force=true should force cleanup even if disabled."""
        mock_cleanup_result = {
            "tenant_id": "test-tenant-id",
            "deleted_count": 10000,
            "retention_days": 90,
            "is_enabled": False,
            "timestamp": "2024-04-01T12:00:00",
            "summary": {},
            "skipped": False,
        }

        with patch("app.api.endpoints.retention.retention_service.cleanup_tenant_executions") as mock_cleanup:
            mock_cleanup.return_value = mock_cleanup_result

            response = client.post(
                "/api/v1/retention/cleanup?force=true",
                headers=auth_headers
            )

            assert response.status_code == 200
            # Verify force parameter was passed to service
            mock_cleanup.assert_called_once()
            call_kwargs = mock_cleanup.call_args.kwargs
            assert call_kwargs.get("force") is True

    @pytest.mark.api
    def test_trigger_cleanup_skipped(self, client: TestClient, auth_headers):
        """POST /retention/cleanup should handle skipped cleanups."""
        mock_cleanup_result = {
            "tenant_id": "test-tenant-id",
            "deleted_count": 0,
            "retention_days": 90,
            "is_enabled": False,
            "timestamp": "2024-04-01T12:00:00",
            "skipped": True,
            "reason": "Retention disabled for tenant",
        }

        with patch("app.api.endpoints.retention.retention_service.cleanup_tenant_executions") as mock_cleanup:
            mock_cleanup.return_value = mock_cleanup_result

            response = client.post("/api/v1/retention/cleanup", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["skipped"] is True
            assert data["deleted_count"] == 0
            assert data["reason"] == "Retention disabled for tenant"

    @pytest.mark.api
    def test_trigger_cleanup_unauthorized(self, client: TestClient):
        """POST /retention/cleanup should return 401 without auth."""
        response = client.post("/api/v1/retention/cleanup")
        assert response.status_code == 401


class TestRetentionAPIIntegration:
    """Integration tests for retention API workflows."""

    @pytest.mark.api
    def test_retention_workflow(self, client: TestClient, auth_headers):
        """Test complete retention management workflow."""
        # Step 1: Get current policy
        with patch("app.api.endpoints.retention.retention_service.get_retention_policy") as mock_get:
            mock_get.return_value = {
                "retention_days": 90,
                "is_enabled": True,
                "min_executions_to_keep": 100,
                "last_cleanup_at": None,
                "last_cleanup_deleted_count": 0,
            }

            response = client.get("/api/v1/retention/policy", headers=auth_headers)
            assert response.status_code == 200
            initial_policy = response.json()
            assert initial_policy["retention_days"] == 90

        # Step 2: Preview cleanup
        with patch("app.api.endpoints.retention.retention_service.get_cleanup_preview") as mock_preview:
            mock_preview.return_value = {
                "tenant_id": "test-tenant-id",
                "total_executions": 100000,
                "old_executions_count": 30000,
                "executions_to_delete": 29900,
                "cutoff_date": "2024-01-01T00:00:00",
                "retention_days": 90,
                "min_executions_to_keep": 100,
                "would_delete": True,
                "is_enabled": True,
            }

            response = client.get("/api/v1/retention/preview", headers=auth_headers)
            assert response.status_code == 200
            preview = response.json()
            assert preview["would_delete"] is True

        # Step 3: Update policy to disable
        with patch("app.api.endpoints.retention.retention_service.update_retention_policy") as mock_update:
            mock_update.return_value = {
                "retention_days": 90,
                "is_enabled": False,
                "min_executions_to_keep": 100,
                "last_cleanup_at": None,
                "last_cleanup_deleted_count": 0,
            }

            response = client.patch(
                "/api/v1/retention/policy",
                json={"is_enabled": False},
                headers=auth_headers
            )
            assert response.status_code == 200
            updated_policy = response.json()
            assert updated_policy["is_enabled"] is False
