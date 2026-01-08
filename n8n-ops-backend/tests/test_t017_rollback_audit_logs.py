"""
Test suite for T017: Verify audit logs are created for rollback actions.

This test verifies that the snapshot restore/rollback endpoint creates appropriate
audit log entries for tracking rollback operations.

Test Coverage:
- Audit log created when rollback starts (GITHUB_RESTORE_STARTED)
- Audit log created when rollback completes successfully (GITHUB_RESTORE_COMPLETED)
- Audit log created when rollback fails (GITHUB_RESTORE_FAILED)
- Audit logs contain required metadata (snapshot_id, environment_id, user_id, timestamp)
- Audit logs include environment name and commit SHA
- Multiple audit logs created during rollback lifecycle (start, end)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from fastapi.testclient import TestClient


# Mock data - must match conftest.py fixtures
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001"
MOCK_USER_ID = "00000000-0000-0000-0000-000000000002"
MOCK_USER_EMAIL = "admin@example.com"
MOCK_USER_NAME = "Admin User"

MOCK_ENVIRONMENT = {
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
    "policy_flags": {"allow_rollback_in_prod": True},
}

MOCK_SNAPSHOT = {
    "id": "snap-123",
    "tenant_id": MOCK_TENANT_ID,
    "environment_id": "env-prod",
    "git_commit_sha": "abc123def456",
    "type": "pre_promotion",
    "created_by_user_id": MOCK_USER_ID,
    "related_deployment_id": "deploy-1",
    "created_at": "2024-01-10T10:00:00Z",
    "metadata_json": {
        "promotion_id": "promo-123",
        "reason": "Pre-promotion snapshot for promotion promo-123",
        "workflows_count": 2,
    }
}

MOCK_WORKFLOWS = {
    "workflow-1": {
        "id": "workflow-1",
        "name": "Test Workflow 1",
        "nodes": [],
        "connections": {},
        "active": True,
    },
    "workflow-2": {
        "id": "workflow-2",
        "name": "Test Workflow 2",
        "nodes": [],
        "connections": {},
        "active": True,
    },
}


# Mock entitlements for all tests
@pytest.fixture(autouse=True)
def mock_entitlements():
    """Mock entitlements service to allow all features for testing."""
    with patch("app.core.entitlements_gate.entitlements_service") as mock_ent:
        mock_ent.enforce_flag = AsyncMock(return_value=None)
        mock_ent.has_flag = AsyncMock(return_value=True)
        yield mock_ent


class TestRollbackAuditLogs:
    """Tests verifying audit logs are created for rollback actions."""

    @pytest.mark.api
    def test_audit_log_created_when_rollback_starts(self, client: TestClient, auth_headers):
        """
        Test that an audit log is created when rollback operation starts.

        Scenario:
        - User initiates a rollback via snapshot restore endpoint
        - System creates GITHUB_RESTORE_STARTED audit log before performing rollback
        - Audit log includes snapshot_id, user_id, environment_id, timestamp

        Verification:
        - create_audit_log is called with GITHUB_RESTORE_STARTED action type
        - Audit log includes snapshot metadata
        - Audit log includes actor information (user_id, email, name)
        - Audit log includes environment information
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.environment_action_guard") as mock_guard, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.ProviderRegistry") as mock_registry, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists
            mock_db.get_environment = AsyncMock(return_value=MOCK_ENVIRONMENT)

            # Mock action guard allows restore
            mock_guard.assert_can_perform_action = MagicMock(return_value=None)

            # Mock GitHub service returns workflows
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(return_value=MOCK_WORKFLOWS)
            MockGitHubService.return_value = mock_github

            # Mock adapter
            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            # Mock audit logging
            mock_audit.return_value = AsyncMock()

            # Mock notification service
            mock_notify.emit_event = AsyncMock()

            # Perform rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT['id']}/restore",
                headers=auth_headers
            )

            # Verify response is successful
            assert response.status_code == 200

            # Verify create_audit_log was called
            assert mock_audit.called, "create_audit_log should be called during rollback"

            # Find the GITHUB_RESTORE_STARTED audit log call
            audit_calls = mock_audit.call_args_list
            started_call = None
            for call_obj in audit_calls:
                kwargs = call_obj[1] if len(call_obj) > 1 else call_obj.kwargs
                if kwargs.get("action_type") == "GITHUB_RESTORE_STARTED":
                    started_call = kwargs
                    break

            assert started_call is not None, "GITHUB_RESTORE_STARTED audit log should be created"

            # Verify audit log contains required fields
            assert started_call["action_type"] == "GITHUB_RESTORE_STARTED"
            assert started_call["resource_type"] == "snapshot"
            assert started_call["resource_id"] == MOCK_SNAPSHOT["id"]
            assert started_call["tenant_id"] == MOCK_TENANT_ID

            # Verify actor information is included
            assert started_call["actor_id"] == MOCK_USER_ID
            assert started_call["actor_email"] == MOCK_USER_EMAIL
            assert started_call["actor_name"] == MOCK_USER_NAME

            # Verify metadata includes snapshot details
            metadata = started_call["metadata"]
            assert metadata is not None
            assert metadata["snapshot_id"] == MOCK_SNAPSHOT["id"]
            assert metadata["environment_id"] == MOCK_SNAPSHOT["environment_id"]
            assert metadata["commit_sha"] == MOCK_SNAPSHOT["git_commit_sha"]
            assert metadata["snapshot_type"] == MOCK_SNAPSHOT["type"]
            assert "timestamp" in metadata

    @pytest.mark.api
    def test_audit_log_created_when_rollback_completes_successfully(self, client: TestClient, auth_headers):
        """
        Test that an audit log is created when rollback completes successfully.

        Scenario:
        - User initiates rollback
        - Rollback executes and restores all workflows successfully
        - System creates GITHUB_RESTORE_COMPLETED audit log after rollback

        Verification:
        - create_audit_log is called with GITHUB_RESTORE_COMPLETED action type
        - Audit log includes restored_count in metadata
        - Audit log confirms successful completion
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.environment_action_guard") as mock_guard, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.ProviderRegistry") as mock_registry, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists
            mock_db.get_environment = AsyncMock(return_value=MOCK_ENVIRONMENT)

            # Mock action guard
            mock_guard.assert_can_perform_action = MagicMock(return_value=None)

            # Mock GitHub service
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(return_value=MOCK_WORKFLOWS)
            MockGitHubService.return_value = mock_github

            # Mock adapter - all workflows restore successfully
            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            mock_audit.return_value = AsyncMock()
            mock_notify.emit_event = AsyncMock()

            # Perform rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT['id']}/restore",
                headers=auth_headers
            )

            # Verify successful response
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["restored"] == 2  # Two workflows restored

            # Find the GITHUB_RESTORE_COMPLETED audit log call
            audit_calls = mock_audit.call_args_list
            completed_call = None
            for call_obj in audit_calls:
                kwargs = call_obj[1] if len(call_obj) > 1 else call_obj.kwargs
                if kwargs.get("action_type") == "GITHUB_RESTORE_COMPLETED":
                    completed_call = kwargs
                    break

            assert completed_call is not None, "GITHUB_RESTORE_COMPLETED audit log should be created"

            # Verify audit log details
            assert completed_call["action_type"] == "GITHUB_RESTORE_COMPLETED"
            assert completed_call["resource_type"] == "snapshot"
            assert completed_call["resource_id"] == MOCK_SNAPSHOT["id"]
            assert completed_call["tenant_id"] == MOCK_TENANT_ID

            # Verify metadata includes restore details
            metadata = completed_call["metadata"]
            assert metadata is not None
            assert metadata["snapshot_id"] == MOCK_SNAPSHOT["id"]
            assert metadata["environment_id"] == MOCK_SNAPSHOT["environment_id"]
            assert metadata["restored_count"] == 2
            assert "timestamp" in metadata

    @pytest.mark.api
    def test_audit_log_created_when_rollback_fails(self, client: TestClient, auth_headers):
        """
        Test that an audit log is created when rollback fails.

        Scenario:
        - User initiates rollback
        - Rollback fails during workflow restoration
        - System creates GITHUB_RESTORE_FAILED audit log

        Verification:
        - create_audit_log is called with GITHUB_RESTORE_FAILED action type
        - Audit log includes error details in metadata
        - Audit log includes failed_count
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.environment_action_guard") as mock_guard, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.ProviderRegistry") as mock_registry, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists
            mock_db.get_environment = AsyncMock(return_value=MOCK_ENVIRONMENT)

            # Mock action guard
            mock_guard.assert_can_perform_action = MagicMock(return_value=None)

            # Mock GitHub service
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(return_value=MOCK_WORKFLOWS)
            MockGitHubService.return_value = mock_github

            # Mock adapter - workflows fail to restore
            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock(side_effect=Exception("Workflow restore failed"))
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            mock_audit.return_value = AsyncMock()
            mock_notify.emit_event = AsyncMock()

            # Perform rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT['id']}/restore",
                headers=auth_headers
            )

            # Verify response indicates failure
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert data["failed"] == 2  # Two workflows failed

            # Find the GITHUB_RESTORE_FAILED audit log call
            audit_calls = mock_audit.call_args_list
            failed_call = None
            for call_obj in audit_calls:
                kwargs = call_obj[1] if len(call_obj) > 1 else call_obj.kwargs
                if kwargs.get("action_type") == "GITHUB_RESTORE_FAILED":
                    failed_call = kwargs
                    break

            assert failed_call is not None, "GITHUB_RESTORE_FAILED audit log should be created"

            # Verify audit log details
            assert failed_call["action_type"] == "GITHUB_RESTORE_FAILED"
            assert failed_call["resource_type"] == "snapshot"
            assert failed_call["resource_id"] == MOCK_SNAPSHOT["id"]
            assert failed_call["tenant_id"] == MOCK_TENANT_ID

            # Verify metadata includes failure details
            metadata = failed_call["metadata"]
            assert metadata is not None
            assert metadata["snapshot_id"] == MOCK_SNAPSHOT["id"]
            assert metadata["environment_id"] == MOCK_SNAPSHOT["environment_id"]
            assert metadata["failed_count"] == 2
            assert "errors" in metadata
            assert len(metadata["errors"]) > 0

    @pytest.mark.api
    def test_multiple_audit_logs_created_during_rollback_lifecycle(self, client: TestClient, auth_headers):
        """
        Test that multiple audit logs are created throughout rollback lifecycle.

        Scenario:
        - User initiates rollback
        - System creates STARTED audit log at beginning
        - System creates COMPLETED audit log at end
        - Both audit logs are created during single rollback operation

        Verification:
        - At least 2 audit log calls made (start and completion)
        - Both STARTED and COMPLETED action types are present
        - Audit logs are created in correct order
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.environment_action_guard") as mock_guard, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.ProviderRegistry") as mock_registry, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists
            mock_db.get_environment = AsyncMock(return_value=MOCK_ENVIRONMENT)

            # Mock action guard
            mock_guard.assert_can_perform_action = MagicMock(return_value=None)

            # Mock GitHub service
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(return_value=MOCK_WORKFLOWS)
            MockGitHubService.return_value = mock_github

            # Mock adapter
            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            mock_audit.return_value = AsyncMock()
            mock_notify.emit_event = AsyncMock()

            # Perform rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT['id']}/restore",
                headers=auth_headers
            )

            # Verify successful response
            assert response.status_code == 200

            # Verify multiple audit logs created
            audit_calls = mock_audit.call_args_list
            assert len(audit_calls) >= 2, "At least 2 audit logs should be created (start and completion)"

            # Extract action types
            action_types = []
            for call_obj in audit_calls:
                kwargs = call_obj[1] if len(call_obj) > 1 else call_obj.kwargs
                action_types.append(kwargs.get("action_type"))

            # Verify both STARTED and COMPLETED are present
            assert "GITHUB_RESTORE_STARTED" in action_types, "STARTED audit log should be created"
            assert "GITHUB_RESTORE_COMPLETED" in action_types, "COMPLETED audit log should be created"

            # Verify STARTED comes before COMPLETED
            started_index = action_types.index("GITHUB_RESTORE_STARTED")
            completed_index = action_types.index("GITHUB_RESTORE_COMPLETED")
            assert started_index < completed_index, "STARTED should be created before COMPLETED"

    @pytest.mark.api
    def test_audit_log_includes_environment_name_and_commit_sha(self, client: TestClient, auth_headers):
        """
        Test that audit logs include environment name and commit SHA for debugging.

        Scenario:
        - User initiates rollback
        - Audit logs are created with full context

        Verification:
        - Audit log metadata includes environment_name
        - Audit log metadata includes commit_sha
        - Both fields help with debugging and audit trail
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.environment_action_guard") as mock_guard, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.ProviderRegistry") as mock_registry, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists
            mock_db.get_environment = AsyncMock(return_value=MOCK_ENVIRONMENT)

            # Mock action guard
            mock_guard.assert_can_perform_action = MagicMock(return_value=None)

            # Mock GitHub service
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(return_value=MOCK_WORKFLOWS)
            MockGitHubService.return_value = mock_github

            # Mock adapter
            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            mock_audit.return_value = AsyncMock()
            mock_notify.emit_event = AsyncMock()

            # Perform rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT['id']}/restore",
                headers=auth_headers
            )

            # Verify successful response
            assert response.status_code == 200

            # Check STARTED audit log
            audit_calls = mock_audit.call_args_list
            started_call = None
            for call_obj in audit_calls:
                kwargs = call_obj[1] if len(call_obj) > 1 else call_obj.kwargs
                if kwargs.get("action_type") == "GITHUB_RESTORE_STARTED":
                    started_call = kwargs
                    break

            assert started_call is not None

            # Verify metadata includes environment_name and commit_sha
            metadata = started_call["metadata"]
            assert "environment_name" in metadata
            assert metadata["environment_name"] == MOCK_ENVIRONMENT["n8n_name"]
            assert "commit_sha" in metadata
            assert metadata["commit_sha"] == MOCK_SNAPSHOT["git_commit_sha"]

    @pytest.mark.api
    def test_audit_log_created_on_exception_during_rollback(self, client: TestClient, auth_headers):
        """
        Test that audit log is created even when rollback fails with exception.

        Scenario:
        - User initiates rollback
        - Unexpected exception occurs during rollback
        - System creates GITHUB_RESTORE_FAILED audit log with exception details

        Verification:
        - FAILED audit log is created even on exception
        - Audit log includes error_message and error_type
        - Exception is still raised to caller
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.environment_action_guard") as mock_guard, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT

            # First call for initial snapshot lookup
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists
            mock_db.get_environment = AsyncMock(return_value=MOCK_ENVIRONMENT)

            # Mock action guard
            mock_guard.assert_can_perform_action = MagicMock(return_value=None)

            # Mock GitHub service throws exception
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(side_effect=Exception("GitHub API error"))
            MockGitHubService.return_value = mock_github

            mock_audit.return_value = AsyncMock()
            mock_notify.emit_event = AsyncMock()

            # Perform rollback - should fail with exception
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT['id']}/restore",
                headers=auth_headers
            )

            # Verify error response
            assert response.status_code == 500

            # Verify audit log was created for the failure
            audit_calls = mock_audit.call_args_list

            # Should have at least STARTED and FAILED
            assert len(audit_calls) >= 2

            # Find FAILED audit log
            failed_call = None
            for call_obj in audit_calls:
                kwargs = call_obj[1] if len(call_obj) > 1 else call_obj.kwargs
                if kwargs.get("action_type") == "GITHUB_RESTORE_FAILED":
                    failed_call = kwargs
                    break

            assert failed_call is not None, "GITHUB_RESTORE_FAILED audit log should be created on exception"

            # Verify metadata includes exception details
            metadata = failed_call["metadata"]
            assert "error_message" in metadata
            assert "error_type" in metadata
            assert metadata["error_message"] == "GitHub API error"
            assert metadata["error_type"] == "Exception"

    @pytest.mark.api
    def test_audit_log_contains_user_context_for_accountability(self, client: TestClient, auth_headers):
        """
        Test that audit logs contain complete user context for accountability.

        Scenario:
        - User initiates rollback
        - Audit log is created with full user information

        Verification:
        - Audit log includes actor_id (user ID)
        - Audit log includes actor_email
        - Audit log includes actor_name
        - User context enables accountability and investigation
        """
        with patch("app.api.endpoints.snapshots.db_service") as mock_db, \
             patch("app.api.endpoints.snapshots.environment_action_guard") as mock_guard, \
             patch("app.api.endpoints.snapshots.GitHubService") as MockGitHubService, \
             patch("app.api.endpoints.snapshots.ProviderRegistry") as mock_registry, \
             patch("app.api.endpoints.snapshots.create_audit_log") as mock_audit, \
             patch("app.api.endpoints.snapshots.notification_service") as mock_notify:

            # Mock snapshot exists
            mock_snapshot_result = MagicMock()
            mock_snapshot_result.data = MOCK_SNAPSHOT
            mock_db.client.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = mock_snapshot_result

            # Mock environment exists
            mock_db.get_environment = AsyncMock(return_value=MOCK_ENVIRONMENT)

            # Mock action guard
            mock_guard.assert_can_perform_action = MagicMock(return_value=None)

            # Mock GitHub service
            mock_github = MagicMock()
            mock_github.get_all_workflows_from_github = AsyncMock(return_value=MOCK_WORKFLOWS)
            MockGitHubService.return_value = mock_github

            # Mock adapter
            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            mock_audit.return_value = AsyncMock()
            mock_notify.emit_event = AsyncMock()

            # Perform rollback
            response = client.post(
                f"/api/v1/snapshots/{MOCK_SNAPSHOT['id']}/restore",
                headers=auth_headers
            )

            # Verify successful response
            assert response.status_code == 200

            # Verify all audit logs contain user context
            audit_calls = mock_audit.call_args_list
            assert len(audit_calls) >= 1, "At least one audit log should be created"

            for call_obj in audit_calls:
                kwargs = call_obj[1] if len(call_obj) > 1 else call_obj.kwargs

                # Verify actor information is present
                assert "actor_id" in kwargs
                assert "actor_email" in kwargs
                assert "actor_name" in kwargs

                # Verify values match expected user
                assert kwargs["actor_id"] == MOCK_USER_ID
                assert kwargs["actor_email"] == MOCK_USER_EMAIL
                assert kwargs["actor_name"] == MOCK_USER_NAME
