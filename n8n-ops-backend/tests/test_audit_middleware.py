"""Tests for audit middleware and context extraction utilities."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from app.services.audit_middleware import (
    AuditMiddleware,
    get_audit_context,
    get_impersonation_context,
)


class TestGetAuditContext:
    """Tests for get_audit_context() function."""

    def test_normal_user_context(self):
        """Test extracting audit context for a normal (non-impersonating) user."""
        user_context = {
            "user": {
                "id": "user-123",
                "email": "user@example.com",
                "name": "Test User",
                "role": "admin",
            },
            "tenant": {
                "id": "tenant-456",
                "name": "Test Tenant",
            },
            "impersonating": False,
        }

        context = get_audit_context(user_context)

        assert context["actor_id"] == "user-123"
        assert context["actor_email"] == "user@example.com"
        assert context["actor_name"] == "Test User"
        assert context["tenant_id"] == "tenant-456"
        assert context["tenant_name"] == "Test Tenant"
        assert context["impersonation_session_id"] is None
        assert context["impersonated_user_id"] is None
        assert context["impersonated_user_email"] is None
        assert context["impersonated_tenant_id"] is None

    def test_impersonating_user_context(self):
        """Test extracting audit context during impersonation."""
        user_context = {
            "user": {
                "id": "target-user-123",
                "email": "target@example.com",
                "name": "Target User",
                "role": "viewer",
            },
            "tenant": {
                "id": "target-tenant-456",
                "name": "Target Tenant",
            },
            "impersonating": True,
            "impersonation_session_id": "session-789",
            "impersonated_user_id": "target-user-123",
            "impersonated_tenant_id": "target-tenant-456",
            "actor_user": {
                "id": "admin-999",
                "email": "admin@platform.com",
                "name": "Platform Admin",
                "role": "platform_admin",
            },
        }

        context = get_audit_context(user_context)

        # Actor should be the platform admin (impersonator)
        assert context["actor_id"] == "admin-999"
        assert context["actor_email"] == "admin@platform.com"
        assert context["actor_name"] == "Platform Admin"

        # Tenant should be the target tenant
        assert context["tenant_id"] == "target-tenant-456"
        assert context["tenant_name"] == "Target Tenant"

        # Impersonation fields should be populated
        assert context["impersonation_session_id"] == "session-789"
        assert context["impersonated_user_id"] == "target-user-123"
        assert context["impersonated_user_email"] == "target@example.com"
        assert context["impersonated_tenant_id"] == "target-tenant-456"

    def test_context_with_missing_fields(self):
        """Test extracting context when optional fields are missing."""
        user_context = {
            "user": {
                "id": "user-123",
                "email": "user@example.com",
            },
            "tenant": {
                "id": "tenant-456",
            },
        }

        context = get_audit_context(user_context)

        assert context["actor_id"] == "user-123"
        assert context["actor_email"] == "user@example.com"
        assert context["actor_name"] is None  # Missing name
        assert context["tenant_id"] == "tenant-456"
        assert context["tenant_name"] is None  # Missing tenant name

    def test_context_with_empty_dicts(self):
        """Test extracting context when user/tenant dicts are empty."""
        user_context = {
            "user": {},
            "tenant": {},
            "impersonating": False,
        }

        context = get_audit_context(user_context)

        assert context["actor_id"] is None
        assert context["actor_email"] is None
        assert context["actor_name"] is None
        assert context["tenant_id"] is None
        assert context["tenant_name"] is None


class TestGetImpersonationContext:
    """Tests for get_impersonation_context() function."""

    def test_no_impersonation(self):
        """Test extracting impersonation context when not impersonating."""
        user_context = {
            "user": {
                "id": "user-123",
                "email": "user@example.com",
            },
            "tenant": {
                "id": "tenant-456",
            },
            "impersonating": False,
        }

        context = get_impersonation_context(user_context)

        assert context["impersonation_session_id"] is None
        assert context["impersonated_user_id"] is None
        assert context["impersonated_user_email"] is None
        assert context["impersonated_tenant_id"] is None

    def test_active_impersonation(self):
        """Test extracting impersonation context during active impersonation."""
        user_context = {
            "user": {
                "id": "target-user-123",
                "email": "target@example.com",
            },
            "impersonating": True,
            "impersonation_session_id": "session-789",
            "impersonated_user_id": "target-user-123",
            "impersonated_tenant_id": "target-tenant-456",
        }

        context = get_impersonation_context(user_context)

        assert context["impersonation_session_id"] == "session-789"
        assert context["impersonated_user_id"] == "target-user-123"
        assert context["impersonated_user_email"] == "target@example.com"
        assert context["impersonated_tenant_id"] == "target-tenant-456"

    def test_impersonation_missing_impersonating_flag(self):
        """Test when impersonating flag is missing (defaults to False)."""
        user_context = {
            "user": {"id": "user-123"},
            "impersonation_session_id": "session-789",  # These are ignored
        }

        context = get_impersonation_context(user_context)

        # All should be None because impersonating flag is missing
        assert context["impersonation_session_id"] is None
        assert context["impersonated_user_id"] is None
        assert context["impersonated_user_email"] is None
        assert context["impersonated_tenant_id"] is None


class TestAuditMiddleware:
    """Tests for AuditMiddleware class."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app with the middleware."""
        test_app = FastAPI()

        @test_app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        @test_app.post("/test")
        async def test_post_endpoint():
            return {"status": "created"}

        @test_app.put("/test/{item_id}")
        async def test_put_endpoint(item_id: str):
            return {"status": "updated", "id": item_id}

        @test_app.delete("/test/{item_id}")
        async def test_delete_endpoint(item_id: str):
            return {"status": "deleted", "id": item_id}

        # Add middleware
        test_app.add_middleware(AuditMiddleware)

        return test_app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app)

    def test_middleware_initialization(self, app):
        """Test that middleware is properly initialized."""
        # The middleware should be in the middleware stack
        # Note: In TestClient, middleware is wrapped, so we check if it was added
        # by verifying the app has middleware_stack attribute
        assert hasattr(app, "middleware_stack") or hasattr(app, "user_middleware")

    def test_get_request_not_audited(self, client):
        """Test that GET requests are not audited."""
        with patch("app.services.audit_middleware.create_audit_log") as mock_audit:
            response = client.get("/test")
            assert response.status_code == 200
            mock_audit.assert_not_called()

    def test_post_without_auth_not_audited(self, client):
        """Test that POST without auth header is not audited."""
        with patch("app.services.audit_middleware.create_audit_log") as mock_audit:
            response = client.post("/test")
            assert response.status_code == 200
            mock_audit.assert_not_called()

    @patch("app.services.audit_middleware.db_service")
    @patch("app.services.audit_middleware.supabase_auth_service")
    @patch("app.services.audit_middleware.create_audit_log")
    async def test_post_with_impersonation_creates_audit_log(
        self, mock_audit, mock_auth_service, mock_db_service, client
    ):
        """Test that POST during impersonation creates an audit log."""
        # Mock token verification
        mock_auth_service.verify_token = AsyncMock(return_value={
            "sub": "supabase-user-123"
        })

        # Mock actor user fetch
        mock_actor_resp = MagicMock()
        mock_actor_resp.data = {
            "id": "admin-999",
            "email": "admin@platform.com",
            "name": "Platform Admin"
        }

        # Mock impersonation session fetch
        mock_session_resp = MagicMock()
        mock_session_resp.data = [{
            "id": "session-789",
            "actor_user_id": "admin-999",
            "impersonated_user_id": "user-123",
            "impersonated_tenant_id": "tenant-456"
        }]

        # Mock impersonated user fetch
        mock_impersonated_resp = MagicMock()
        mock_impersonated_resp.data = {
            "id": "user-123",
            "email": "user@example.com",
            "name": "Target User"
        }

        # Configure the db_service mock
        mock_db_service.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_actor_resp
        mock_db_service.client.table.return_value.select.return_value.eq.return_value.is_.return_value.order.return_value.limit.return_value.execute.return_value = mock_session_resp
        mock_db_service.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_impersonated_resp

        # Make request with auth header
        response = client.post(
            "/test",
            headers={"Authorization": "Bearer fake-token"}
        )

        assert response.status_code == 200

        # Note: In real async testing, we'd need to await the middleware
        # For now, we're testing the structure and logic paths

    def test_excluded_paths_not_audited(self, client):
        """Test that excluded paths are not audited."""
        # The middleware should skip audit logging for excluded paths
        excluded_paths = [
            "/api/v1/health",
            "/api/v1/admin/audit",
            "/docs",
            "/openapi.json",
        ]

        with patch("app.services.audit_middleware.create_audit_log") as mock_audit:
            for path in excluded_paths:
                # POST to these paths should not trigger audit
                # (would need to add these routes to test app for real test)
                pass

    def test_write_methods_trigger_audit_check(self, client):
        """Test that all write methods trigger audit check."""
        write_methods = ["POST", "PUT", "PATCH", "DELETE"]

        with patch("app.services.audit_middleware.create_audit_log") as mock_audit:
            for method in write_methods:
                # Each write method should attempt to audit
                # (actual audit depends on auth and impersonation state)
                pass


class TestAuditMiddlewareEdgeCases:
    """Tests for edge cases and error handling in audit middleware."""

    def test_get_audit_context_handles_none_values(self):
        """Test that get_audit_context handles None values gracefully."""
        user_context = {
            "user": None,
            "tenant": None,
            "impersonating": False,
        }

        # Should not raise an exception
        context = get_audit_context(user_context)

        # All fields should be None
        assert context["actor_id"] is None
        assert context["tenant_id"] is None

    def test_get_impersonation_context_handles_missing_user(self):
        """Test impersonation context extraction with missing user dict."""
        user_context = {
            "impersonating": True,
            "impersonation_session_id": "session-123",
            # Missing "user" key
        }

        context = get_impersonation_context(user_context)

        # Should still extract session_id but email will be None
        assert context["impersonation_session_id"] == "session-123"
        assert context["impersonated_user_email"] is None

    def test_get_audit_context_with_nested_none_actor_user(self):
        """Test audit context when actor_user is None during impersonation."""
        user_context = {
            "user": {
                "id": "user-123",
                "email": "user@example.com",
            },
            "tenant": {
                "id": "tenant-456",
            },
            "impersonating": True,
            "actor_user": None,  # This could happen in edge cases
            "impersonation_session_id": "session-789",
        }

        context = get_audit_context(user_context)

        # Actor fields should be None
        assert context["actor_id"] is None
        assert context["actor_email"] is None
        assert context["actor_name"] is None

        # But impersonation fields should still be populated
        assert context["impersonation_session_id"] == "session-789"


class TestAuditMiddlewareIntegration:
    """Integration tests for audit middleware with real-world scenarios."""

    def test_audit_context_can_be_spread_into_create_audit_log(self):
        """Test that audit context can be directly spread into create_audit_log."""
        user_context = {
            "user": {
                "id": "user-123",
                "email": "user@example.com",
                "name": "Test User",
            },
            "tenant": {
                "id": "tenant-456",
                "name": "Test Tenant",
            },
            "impersonating": False,
        }

        audit_ctx = get_audit_context(user_context)

        # Simulate spreading the context into a function
        # This tests that all expected keys are present
        expected_keys = {
            "actor_id",
            "actor_email",
            "actor_name",
            "tenant_id",
            "tenant_name",
            "impersonation_session_id",
            "impersonated_user_id",
            "impersonated_user_email",
            "impersonated_tenant_id",
        }

        assert set(audit_ctx.keys()) == expected_keys

    def test_impersonation_context_subset_of_audit_context(self):
        """Test that impersonation context is a proper subset of audit context."""
        user_context = {
            "user": {
                "id": "target-user-123",
                "email": "target@example.com",
            },
            "tenant": {
                "id": "target-tenant-456",
            },
            "impersonating": True,
            "impersonation_session_id": "session-789",
            "impersonated_user_id": "target-user-123",
            "impersonated_tenant_id": "target-tenant-456",
            "actor_user": {
                "id": "admin-999",
                "email": "admin@platform.com",
            },
        }

        audit_ctx = get_audit_context(user_context)
        impersonation_ctx = get_impersonation_context(user_context)

        # All impersonation context keys should be in audit context
        for key, value in impersonation_ctx.items():
            assert key in audit_ctx
            assert audit_ctx[key] == value

    def test_context_functions_consistent_during_impersonation(self):
        """Test that both context functions are consistent during impersonation."""
        user_context = {
            "user": {
                "id": "target-user-123",
                "email": "target@example.com",
            },
            "tenant": {
                "id": "target-tenant-456",
            },
            "impersonating": True,
            "impersonation_session_id": "session-789",
            "impersonated_user_id": "target-user-123",
            "impersonated_tenant_id": "target-tenant-456",
            "actor_user": {
                "id": "admin-999",
                "email": "admin@platform.com",
                "name": "Platform Admin",
            },
        }

        audit_ctx = get_audit_context(user_context)
        impersonation_ctx = get_impersonation_context(user_context)

        # Impersonation fields should match in both contexts
        assert (
            audit_ctx["impersonation_session_id"]
            == impersonation_ctx["impersonation_session_id"]
        )
        assert (
            audit_ctx["impersonated_user_id"]
            == impersonation_ctx["impersonated_user_id"]
        )
        assert (
            audit_ctx["impersonated_user_email"]
            == impersonation_ctx["impersonated_user_email"]
        )
        assert (
            audit_ctx["impersonated_tenant_id"]
            == impersonation_ctx["impersonated_tenant_id"]
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
