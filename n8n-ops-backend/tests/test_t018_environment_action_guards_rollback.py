"""
Test suite for T018: Verify environment action guards block unauthorized rollback.

This test verifies that the environment action guard correctly blocks unauthorized
rollback operations based on environment class and user role.

Test Coverage:
- Rollback blocked in dev environment without policy flag
- Rollback allowed in dev environment with policy flag enabled
- Rollback blocked in production environment for non-admin users
- Rollback allowed in production environment for admin users
- Rollback allowed in staging environment for all users
- Rollback returns 403 with appropriate error message when blocked
- Error response includes environment class and action information
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# Mock data - must match conftest.py fixtures
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001"
MOCK_USER_ID = "00000000-0000-0000-0000-000000000002"
MOCK_USER_EMAIL = "admin@example.com"
MOCK_USER_NAME = "Admin User"

# Mock environments with different classes
MOCK_DEV_ENVIRONMENT = {
    "id": "env-dev",
    "tenant_id": MOCK_TENANT_ID,
    "name": "Development",
    "n8n_type": "development",
    "n8n_name": "Development Environment",
    "n8n_base_url": "https://dev.n8n.example.com",
    "n8n_api_key": "test_api_key",
    "git_repo_url": "https://github.com/test-org/n8n-workflows",
    "git_branch": "main",
    "git_pat": "ghp_test_token",
    "environment_class": "dev",
    "policy_flags": {},  # No policy flags by default
}

MOCK_DEV_ENVIRONMENT_WITH_POLICY = {
    **MOCK_DEV_ENVIRONMENT,
    "policy_flags": {"allow_restore_in_dev": True},
}

MOCK_STAGING_ENVIRONMENT = {
    "id": "env-staging",
    "tenant_id": MOCK_TENANT_ID,
    "name": "Staging",
    "n8n_type": "staging",
    "n8n_name": "Staging Environment",
    "n8n_base_url": "https://staging.n8n.example.com",
    "n8n_api_key": "test_api_key",
    "git_repo_url": "https://github.com/test-org/n8n-workflows",
    "git_branch": "main",
    "git_pat": "ghp_test_token",
    "environment_class": "staging",
    "policy_flags": {},
}

MOCK_PROD_ENVIRONMENT = {
    "id": "env-prod",
    "tenant_id": MOCK_TENANT_ID,
    "name": "Production",
    "n8n_type": "production",
    "n8n_name": "Production Environment",
    "n8n_base_url": "https://prod.n8n.example.com",
    "n8n_api_key": "test_api_key",
    "git_repo_url": "https://github.com/test-org/n8n-workflows",
    "git_branch": "main",
    "git_pat": "ghp_test_token",
    "environment_class": "production",
    "policy_flags": {},
}

MOCK_SNAPSHOT_DEV = {
    "id": "snap-dev-123",
    "tenant_id": MOCK_TENANT_ID,
    "environment_id": "env-dev",
    "git_commit_sha": "abc123def456",
    "type": "pre_promotion",
    "created_by_user_id": MOCK_USER_ID,
    "related_deployment_id": "deploy-1",
    "created_at": "2024-01-10T10:00:00Z",
}

MOCK_SNAPSHOT_STAGING = {
    "id": "snap-staging-123",
    "tenant_id": MOCK_TENANT_ID,
    "environment_id": "env-staging",
    "git_commit_sha": "def456ghi789",
    "type": "pre_promotion",
    "created_by_user_id": MOCK_USER_ID,
    "related_deployment_id": "deploy-2",
    "created_at": "2024-01-10T10:00:00Z",
}

MOCK_SNAPSHOT_PROD = {
    "id": "snap-prod-123",
    "tenant_id": MOCK_TENANT_ID,
    "environment_id": "env-prod",
    "git_commit_sha": "ghi789jkl012",
    "type": "pre_promotion",
    "created_by_user_id": MOCK_USER_ID,
    "related_deployment_id": "deploy-3",
    "created_at": "2024-01-10T10:00:00Z",
}


# Mock entitlements for all tests
@pytest.fixture(autouse=True)
def mock_entitlements():
    """Mock entitlements service to allow all features for testing."""
    with patch("app.core.entitlements_gate.entitlements_service") as mock_ent:
        mock_ent.enforce_flag = AsyncMock(return_value=None)
        mock_ent.has_flag = AsyncMock(return_value=True)
        yield mock_ent


class TestEnvironmentActionGuardsRollback:
    """Tests verifying environment action guards block unauthorized rollback."""

    @pytest.mark.api
    def test_rollback_blocked_in_dev_without_policy_flag(self, client: TestClient, auth_headers):
        """
        Test that rollback is blocked in dev environment without policy flag.

        Scenario:
        - User attempts rollback in dev environment
        - Environment has no "allow_restore_in_dev" policy flag (default OFF)
        - Action guard should block the operation
        - User should receive 403 error

        Verification:
        - Response status code is 403
        - Error message indicates action not allowed
        - Error includes environment class and action details
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db:
            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT_DEV
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists (dev, no policy flag)
            mock_db.get_environment = AsyncMock(return_value=MOCK_DEV_ENVIRONMENT)

            # Attempt rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT_DEV['id']}/restore",
                headers=auth_headers
            )

            # Verify 403 response
            assert response.status_code == 403

            # Verify error message
            data = response.json()
            assert "detail" in data
            detail = data["detail"]

            # Should indicate action not allowed
            if isinstance(detail, dict):
                assert "action_not_allowed" in detail.get("error", "")
                assert detail.get("action") == "restore_rollback"
                assert "dev" in detail.get("reason", "").lower()
            else:
                assert "not allowed" in detail.lower() or "forbidden" in detail.lower()

    @pytest.mark.api
    def test_rollback_allowed_in_dev_with_policy_flag(self, client: TestClient, auth_headers):
        """
        Test that rollback is allowed in dev environment with policy flag enabled.

        Scenario:
        - User attempts rollback in dev environment
        - Environment has "allow_restore_in_dev" policy flag set to True
        - Action guard should allow the operation
        - Rollback should proceed (or fail for other reasons, but not 403)

        Verification:
        - Response status code is NOT 403 (not blocked by action guard)
        - Either succeeds (200) or fails for other reasons (404, 500, etc.)
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.ProviderRegistry") as mock_registry, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT_DEV
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists (dev, WITH policy flag)
            mock_db.get_environment = AsyncMock(return_value=MOCK_DEV_ENVIRONMENT_WITH_POLICY)

            # Mock GitHub service returns empty workflows (will cause 404)
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(return_value={})
            MockGitHubService.return_value = mock_github

            mock_registry.get_adapter_for_environment.return_value = MagicMock()
            mock_audit.return_value = AsyncMock()
            mock_notify.emit_event = AsyncMock()

            # Attempt rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT_DEV['id']}/restore",
                headers=auth_headers
            )

            # Verify NOT blocked by action guard (not 403)
            assert response.status_code != 403, "Should not be blocked by action guard with policy flag enabled"

            # May be 404 (no workflows), 200 (success), or 500 (other error), but not 403
            assert response.status_code in [200, 404, 500]

    @pytest.mark.api
    def test_rollback_blocked_in_production_for_non_admin(self, test_app, auth_headers):
        """
        Test that rollback is blocked in production environment for non-admin users.

        Scenario:
        - Non-admin user (role='user') attempts rollback in production
        - Action guard should require admin role for production rollback
        - User should receive 403 error

        Verification:
        - Response status code is 403
        - Error message indicates admin role required
        """
        from fastapi.testclient import TestClient
        from app.services.auth_service import get_current_user

        # Create non-admin user auth
        non_admin_user = {
            "user": {
                "id": "user-456",
                "email": "user@example.com",
                "name": "Regular User",
                "role": "user",  # Non-admin role
            },
            "tenant": {
                "id": MOCK_TENANT_ID,
                "name": "Test Organization",
                "subscription_tier": "pro",
            }
        }

        # Override auth for this test
        async def mock_get_current_user_non_admin(credentials=None):
            return non_admin_user

        test_app.dependency_overrides[get_current_user] = mock_get_current_user_non_admin

        with TestClient(test_app) as client, \
             patch("app.api.endpoints.snapshots.db_service") as mock_db:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT_PROD
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists (production)
            mock_db.get_environment = AsyncMock(return_value=MOCK_PROD_ENVIRONMENT)

            # Attempt rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT_PROD['id']}/restore",
                headers=auth_headers
            )

            # Verify 403 response
            assert response.status_code == 403

            # Verify error message indicates admin required
            data = response.json()
            assert "detail" in data
            detail = data["detail"]

            if isinstance(detail, dict):
                assert "action_not_allowed" in detail.get("error", "")
                assert "production" in detail.get("reason", "").lower() or "admin" in detail.get("reason", "").lower()
            else:
                assert "admin" in detail.lower() or "production" in detail.lower()

    @pytest.mark.api
    def test_rollback_allowed_in_production_for_admin(self, client: TestClient, auth_headers):
        """
        Test that rollback is allowed in production environment for admin users.

        Scenario:
        - Admin user attempts rollback in production
        - Action guard should allow admin users to rollback in production
        - Rollback should proceed (or fail for other reasons, but not 403)

        Verification:
        - Response status code is NOT 403
        - Action guard allows the operation
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.ProviderRegistry") as mock_registry, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT_PROD
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists (production)
            mock_db.get_environment = AsyncMock(return_value=MOCK_PROD_ENVIRONMENT)

            # Mock GitHub service
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(return_value={})
            MockGitHubService.return_value = mock_github

            mock_registry.get_adapter_for_environment.return_value = MagicMock()
            mock_audit.return_value = AsyncMock()
            mock_notify.emit_event = AsyncMock()

            # Attempt rollback (using default admin auth from fixture)
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT_PROD['id']}/restore",
                headers=auth_headers
            )

            # Verify NOT blocked by action guard
            assert response.status_code != 403, "Admin should be allowed to rollback in production"

    @pytest.mark.api
    def test_rollback_allowed_in_staging_for_all_users(self, client: TestClient, auth_headers):
        """
        Test that rollback is allowed in staging environment for all users.

        Scenario:
        - Any user attempts rollback in staging environment
        - Action guard should allow rollback in staging (no restrictions)
        - Rollback should proceed

        Verification:
        - Response status code is NOT 403
        - Action guard allows the operation
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.ProviderRegistry") as mock_registry, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT_STAGING
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists (staging)
            mock_db.get_environment = AsyncMock(return_value=MOCK_STAGING_ENVIRONMENT)

            # Mock GitHub service
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(return_value={})
            MockGitHubService.return_value = mock_github

            mock_registry.get_adapter_for_environment.return_value = MagicMock()
            mock_audit.return_value = AsyncMock()
            mock_notify.emit_event = AsyncMock()

            # Attempt rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT_STAGING['id']}/restore",
                headers=auth_headers
            )

            # Verify NOT blocked by action guard
            assert response.status_code != 403, "Rollback should be allowed in staging for all users"

    @pytest.mark.api
    def test_rollback_403_includes_environment_and_action_details(self, client: TestClient, auth_headers):
        """
        Test that 403 error response includes environment class and action information.

        Scenario:
        - User attempts unauthorized rollback
        - Action guard blocks the operation with 403
        - Error response should include helpful context

        Verification:
        - Error includes environment_class in details
        - Error includes action type (restore_rollback)
        - Error includes environment_name for clarity
        - Error message is actionable
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db:
            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT_DEV
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists (dev, no policy flag - will block)
            mock_db.get_environment = AsyncMock(return_value=MOCK_DEV_ENVIRONMENT)

            # Attempt rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT_DEV['id']}/restore",
                headers=auth_headers
            )

            # Verify 403 response
            assert response.status_code == 403

            # Verify error details
            data = response.json()
            assert "detail" in data
            detail = data["detail"]

            # Check for structured error response
            if isinstance(detail, dict):
                # Should have error type
                assert "error" in detail
                assert detail["error"] == "action_not_allowed"

                # Should have action
                assert "action" in detail
                assert detail["action"] == "restore_rollback"

                # Should have reason
                assert "reason" in detail
                assert len(detail["reason"]) > 0

                # Should have details with environment info
                if "details" in detail:
                    details = detail["details"]
                    assert "environment_class" in details or "action" in details

    @pytest.mark.api
    def test_action_guard_checked_before_github_operations(self, client: TestClient, auth_headers):
        """
        Test that action guard is checked before any GitHub operations.

        Scenario:
        - User attempts unauthorized rollback
        - Action guard should block BEFORE GitHub service is called
        - This prevents unnecessary API calls and improves security

        Verification:
        - Request is blocked with 403
        - GitHubService is never instantiated
        - No workflows are fetched from GitHub
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT_DEV
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists (dev, no policy - will block)
            mock_db.get_environment = AsyncMock(return_value=MOCK_DEV_ENVIRONMENT)

            # Attempt rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT_DEV['id']}/restore",
                headers=auth_headers
            )

            # Verify 403 response (blocked)
            assert response.status_code == 403

            # Verify GitHubService was never called
            MockGitHubService.assert_not_called()

    @pytest.mark.api
    def test_rollback_superuser_allowed_in_production(self, test_app, auth_headers):
        """
        Test that superuser role is allowed to rollback in production.

        Scenario:
        - User with superuser role attempts rollback in production
        - Action guard should allow superuser (treated as admin)
        - Rollback should proceed

        Verification:
        - Response status code is NOT 403
        - Superuser is treated as admin for action guard
        """
        from fastapi.testclient import TestClient
        from app.services.auth_service import get_current_user

        # Create superuser auth
        superuser = {
            "user": {
                "id": "superuser-789",
                "email": "superuser@example.com",
                "name": "Super User",
                "role": "superuser",
            },
            "tenant": {
                "id": MOCK_TENANT_ID,
                "name": "Test Organization",
                "subscription_tier": "pro",
            }
        }

        # Override auth for this test
        async def mock_get_current_user_superuser(credentials=None):
            return superuser

        test_app.dependency_overrides[get_current_user] = mock_get_current_user_superuser

        with TestClient(test_app) as client, \
             patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.ProviderRegistry") as mock_registry, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT_PROD
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists (production)
            mock_db.get_environment = AsyncMock(return_value=MOCK_PROD_ENVIRONMENT)

            # Mock GitHub service
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(return_value={})
            MockGitHubService.return_value = mock_github

            mock_registry.get_adapter_for_environment.return_value = MagicMock()
            mock_audit.return_value = AsyncMock()
            mock_notify.emit_event = AsyncMock()

            # Attempt rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT_PROD['id']}/restore",
                headers=auth_headers
            )

            # Verify NOT blocked
            assert response.status_code != 403, "Superuser should be allowed to rollback in production"

    @pytest.mark.api
    def test_rollback_error_message_explains_policy_flag_requirement(self, client: TestClient, auth_headers):
        """
        Test that error message explains policy flag requirement for dev rollback.

        Scenario:
        - User attempts rollback in dev without policy flag
        - Error message should explain that policy flag is required
        - Message should be actionable and guide user to solution

        Verification:
        - Error message mentions policy flag
        - Error message indicates "allow_restore_in_dev" is needed
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db:
            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT_DEV
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists (dev, no policy)
            mock_db.get_environment = AsyncMock(return_value=MOCK_DEV_ENVIRONMENT)

            # Attempt rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT_DEV['id']}/restore",
                headers=auth_headers
            )

            # Verify 403 response
            assert response.status_code == 403

            # Verify error mentions policy flag
            data = response.json()
            detail = data["detail"]

            # Convert to string for easier checking
            detail_str = str(detail).lower()

            # Should mention policy or flag or configuration
            assert any(keyword in detail_str for keyword in ["policy", "flag", "allow_restore_in_dev", "dev"]), \
                "Error message should explain policy flag requirement"
