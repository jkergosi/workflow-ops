"""
Unit tests for atomic rollback behavior in promotion service.

This test suite verifies Task T012 requirements:
- Atomic rollback on promotion failure
- Complete restoration of workflows from pre-promotion snapshot
- Rollback result audit trail
- Best-effort error handling during rollback
"""
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from typing import List, Dict, Any

from app.services.promotion_service import PromotionService
from app.schemas.promotion import (
    PromotionStatus,
    WorkflowChangeType,
    WorkflowSelection,
    RollbackResult,
    PromotionExecutionResult,
)


# ============ Fixtures ============


@pytest.fixture
def promotion_service():
    """Create a PromotionService instance with mocked dependencies."""
    service = PromotionService()
    service.db = MagicMock()
    return service


@pytest.fixture
def mock_environment():
    """Create a mock target environment configuration."""
    return {
        "id": "env-target",
        "tenant_id": "tenant-1",
        "n8n_name": "Production",
        "n8n_type": "production",
        "n8n_base_url": "https://prod.n8n.example.com",
        "n8n_api_key": "test-api-key-prod",
        "git_repo_url": "https://github.com/test/repo",
        "git_pat": "test-token",
        "git_branch": "main",
        "is_active": True,
        "provider": "n8n",
    }


@pytest.fixture
def mock_snapshot():
    """Create a mock pre-promotion snapshot."""
    return {
        "id": "snap-pre-123",
        "environment_id": "env-target",
        "tenant_id": "tenant-1",
        "git_commit_sha": "abc123def456",
        "type": "pre_promotion",
        "metadata_json": {
            "type": "pre_promotion",
            "promotion_id": "promo-1",
            "workflows_count": 3,
            "workflows": [
                {"workflow_id": "wf-1", "workflow_name": "Workflow 1"},
                {"workflow_id": "wf-2", "workflow_name": "Workflow 2"},
                {"workflow_id": "wf-3", "workflow_name": "Workflow 3"},
            ]
        },
        "created_at": datetime(2024, 1, 15, 10, 0, 0).isoformat()
    }


@pytest.fixture
def mock_workflows_from_git():
    """Create mock workflow data from Git snapshot."""
    return {
        "wf-1": {
            "id": "wf-1",
            "name": "Workflow 1",
            "active": True,
            "nodes": [{"id": "node-1", "type": "n8n-nodes-base.start"}],
            "connections": {},
        },
        "wf-2": {
            "id": "wf-2",
            "name": "Workflow 2",
            "active": False,
            "nodes": [{"id": "node-2", "type": "n8n-nodes-base.httpRequest"}],
            "connections": {},
        },
        "wf-3": {
            "id": "wf-3",
            "name": "Workflow 3",
            "active": True,
            "nodes": [{"id": "node-3", "type": "n8n-nodes-base.webhook"}],
            "connections": {},
        },
    }


class FakeHttpError(Exception):
    """Lightweight HTTP-like error with a response.status_code for testing."""

    def __init__(self, status_code: int):
        super().__init__(f"HTTP {status_code}")
        self.response = MagicMock()
        self.response.status_code = status_code


# ============ Atomic Rollback Tests ============


class TestRollbackPromotion:
    """Tests for rollback_promotion method - atomic rollback implementation."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_loads_snapshot_from_database(self, promotion_service, mock_environment, mock_snapshot):
        """Rollback should load pre-promotion snapshot from database."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value={})
            mock_gh_service.return_value = mock_gh

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1"],
                promotion_id="promo-1"
            )

            # Verify snapshot was fetched
            promotion_service.db.get_snapshot.assert_called_once_with("snap-pre-123", "tenant-1")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_returns_error_when_snapshot_not_found(self, promotion_service):
        """Rollback should return error result when snapshot doesn't exist."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=None)

        result = await promotion_service.rollback_promotion(
            tenant_id="tenant-1",
            target_env_id="env-target",
            pre_promotion_snapshot_id="non-existent",
            promoted_workflow_ids=["wf-1"],
            promotion_id="promo-1"
        )

        # Verify error result is returned
        assert result.workflows_rolled_back == 0
        assert len(result.rollback_errors) > 0
        assert "snapshot" in result.rollback_errors[0].lower()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_returns_error_when_no_git_commit_sha(self, promotion_service, mock_snapshot):
        """Rollback should return error result when snapshot has no git commit SHA."""
        mock_snapshot["git_commit_sha"] = ""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)

        result = await promotion_service.rollback_promotion(
            tenant_id="tenant-1",
            target_env_id="env-target",
            pre_promotion_snapshot_id="snap-pre-123",
            promoted_workflow_ids=["wf-1"],
            promotion_id="promo-1"
        )

        # Verify error result is returned
        assert result.workflows_rolled_back == 0
        assert len(result.rollback_errors) > 0
        assert "git commit" in result.rollback_errors[0].lower()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_loads_workflows_from_git_at_snapshot_commit(
        self, promotion_service, mock_environment, mock_snapshot, mock_workflows_from_git
    ):
        """Rollback should load workflows from Git at the snapshot's commit SHA."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=mock_workflows_from_git)
            mock_gh_service.return_value = mock_gh

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1", "wf-2"],
                promotion_id="promo-1"
            )

            # Verify GitHub service was called with correct commit SHA
            # Note: Called twice because we have 2 workflows to restore
            assert mock_gh.get_all_workflows_from_github.call_count >= 1
            call_kwargs = mock_gh.get_all_workflows_from_github.call_args.kwargs
            assert call_kwargs["commit_sha"] == "abc123def456"
            assert call_kwargs["environment_type"] == "production"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_restores_all_promoted_workflows(
        self, promotion_service, mock_environment, mock_snapshot, mock_workflows_from_git
    ):
        """Rollback should restore all successfully promoted workflows."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=mock_workflows_from_git)
            mock_gh_service.return_value = mock_gh

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            promoted_ids = ["wf-1", "wf-2", "wf-3"]
            result = await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=promoted_ids,
                promotion_id="promo-1"
            )

            # Verify all workflows were restored
            assert mock_adapter.update_workflow.call_count == 3
            assert result.workflows_rolled_back == 3
            assert result.rollback_triggered is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_uses_correct_workflow_data(
        self, promotion_service, mock_environment, mock_snapshot, mock_workflows_from_git
    ):
        """Rollback should restore workflows with exact data from snapshot."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=mock_workflows_from_git)
            mock_gh_service.return_value = mock_gh

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1"],
                promotion_id="promo-1"
            )

            # Verify correct workflow data was used
            call_args = mock_adapter.update_workflow.call_args_list[0]
            workflow_id = call_args[0][0]
            workflow_data = call_args[0][1]

            assert workflow_id == "wf-1"
            assert workflow_data["name"] == "Workflow 1"
            assert workflow_data["active"] is True
            assert "_comment" not in workflow_data  # Metadata should be removed

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_creates_workflow_if_not_exists(
        self, promotion_service, mock_environment, mock_snapshot, mock_workflows_from_git
    ):
        """Rollback should create workflow if it was deleted in target."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=mock_workflows_from_git)
            mock_gh_service.return_value = mock_gh

            # Mock update_workflow to fail with 404, then create_workflow succeeds
            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock(side_effect=Exception("404 Not Found"))
            mock_adapter.create_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            result = await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1"],
                promotion_id="promo-1"
            )

            # Verify create was called
            mock_adapter.create_workflow.assert_called_once()
            assert result.workflows_rolled_back == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_handles_structured_not_found_error(
        self, promotion_service, mock_environment, mock_snapshot, mock_workflows_from_git
    ):
        """Rollback should treat HTTP errors with 404 status as not-found."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=mock_workflows_from_git)
            mock_gh_service.return_value = mock_gh

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock(side_effect=FakeHttpError(404))
            mock_adapter.create_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            result = await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1"],
                promotion_id="promo-1"
            )

            mock_adapter.update_workflow.assert_called_once()
            mock_adapter.create_workflow.assert_called_once()
            assert result.workflows_rolled_back == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_retries_transient_error_and_succeeds(
        self, promotion_service, mock_environment, mock_snapshot, mock_workflows_from_git
    ):
        """Rollback should retry transient provider errors before succeeding."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock), \
             patch('app.services.promotion_service.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=mock_workflows_from_git)
            mock_gh_service.return_value = mock_gh

            transient_error = FakeHttpError(502)
            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock(side_effect=[transient_error, {"id": "wf-1"}])
            mock_adapter.create_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            result = await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1"],
                promotion_id="promo-1"
            )

            assert mock_adapter.update_workflow.await_count == 2
            mock_sleep.assert_awaited()
            mock_adapter.create_workflow.assert_not_called()
            assert result.workflows_rolled_back == 1
            assert result.rollback_errors == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_stops_after_bounded_retries(
        self, promotion_service, mock_environment, mock_snapshot, mock_workflows_from_git
    ):
        """Rollback should surface errors after retry budget is exhausted."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock), \
             patch('app.services.promotion_service.asyncio.sleep', new_callable=AsyncMock) as mock_sleep:

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=mock_workflows_from_git)
            mock_gh_service.return_value = mock_gh

            transient_error = FakeHttpError(503)
            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock(side_effect=[transient_error, transient_error, transient_error])
            mock_adapter.create_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            result = await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1"],
                promotion_id="promo-1"
            )

            assert mock_adapter.update_workflow.await_count == 3
            mock_sleep.assert_awaited()
            mock_adapter.create_workflow.assert_not_called()
            assert result.workflows_rolled_back == 0
            assert any("wf-1" in err or "Workflow 1" in err for err in result.rollback_errors)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_continues_on_individual_workflow_failure(
        self, promotion_service, mock_environment, mock_snapshot, mock_workflows_from_git
    ):
        """Rollback should continue with remaining workflows if one fails (best-effort)."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=mock_workflows_from_git)
            mock_gh_service.return_value = mock_gh

            # Mock adapter to fail on wf-2, succeed on others
            async def mock_update(wf_id, wf_data):
                if wf_id == "wf-2":
                    raise Exception("Connection timeout")

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock(side_effect=mock_update)
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            result = await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1", "wf-2", "wf-3"],
                promotion_id="promo-1"
            )

            # Verify partial success
            assert result.workflows_rolled_back == 2  # wf-1 and wf-3 succeeded
            assert len(result.rollback_errors) == 1
            assert "wf-2" in result.rollback_errors[0] or "Workflow 2" in result.rollback_errors[0]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_returns_complete_result_structure(
        self, promotion_service, mock_environment, mock_snapshot, mock_workflows_from_git
    ):
        """Rollback should return RollbackResult with complete audit information."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=mock_workflows_from_git)
            mock_gh_service.return_value = mock_gh

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            result = await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1", "wf-2"],
                promotion_id="promo-1"
            )

            # Verify result structure
            assert isinstance(result, RollbackResult)
            assert result.rollback_triggered is True
            assert result.workflows_rolled_back == 2
            assert result.snapshot_id == "snap-pre-123"
            assert result.rollback_method == "git_restore"
            assert isinstance(result.rollback_timestamp, datetime)
            assert isinstance(result.rollback_errors, list)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_creates_audit_log(
        self, promotion_service, mock_environment, mock_snapshot, mock_workflows_from_git
    ):
        """Rollback should create audit log entry with complete context."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit:

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=mock_workflows_from_git)
            mock_gh_service.return_value = mock_gh

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1", "wf-2"],
                promotion_id="promo-1"
            )

            # Verify audit log was created
            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args.kwargs

            assert call_kwargs["tenant_id"] == "tenant-1"
            assert call_kwargs["promotion_id"] == "promo-1"
            assert call_kwargs["action"] == "rollback"
            assert call_kwargs["result"]["workflows_rolled_back"] == 2
            assert call_kwargs["result"]["snapshot_id"] == "snap-pre-123"
            assert call_kwargs["result"]["git_commit_sha"] == "abc123def456"
            assert call_kwargs["result"]["rollback_method"] == "git_restore"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rollback_returns_partial_result_on_critical_failure(
        self, promotion_service, mock_environment, mock_snapshot
    ):
        """Rollback should return partial result even on critical failure."""
        promotion_service.db.get_snapshot = AsyncMock(return_value=mock_snapshot)
        promotion_service.db.get_environment = AsyncMock(return_value=mock_environment)

        with patch.object(promotion_service, '_get_github_service') as mock_gh_service:
            # Simulate critical failure when accessing GitHub
            mock_gh_service.side_effect = Exception("GitHub service unavailable")

            result = await promotion_service.rollback_promotion(
                tenant_id="tenant-1",
                target_env_id="env-target",
                pre_promotion_snapshot_id="snap-pre-123",
                promoted_workflow_ids=["wf-1", "wf-2"],
                promotion_id="promo-1"
            )

            # Verify partial result returned
            assert isinstance(result, RollbackResult)
            assert result.rollback_triggered is True
            assert result.workflows_rolled_back == 0
            assert len(result.rollback_errors) > 0
            assert "Critical rollback failure" in result.rollback_errors[0]


# ============ Execute Promotion with Atomic Rollback Tests ============


class TestExecutePromotionWithRollback:
    """Tests for execute_promotion with atomic rollback on failure."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_promotion_triggers_rollback_on_first_failure(self, promotion_service):
        """Promotion should trigger rollback immediately on first workflow failure."""
        tenant_id = "00000000-0000-0000-0000-000000000001"

        mock_source_env = {
            "id": "env-source",
            "n8n_type": "staging",
            "git_repo_url": "https://github.com/test/repo",
            "git_pat": "token",
            "git_branch": "main"
        }
        mock_target_env = {
            "id": "env-target",
            "n8n_type": "production",
            "git_repo_url": "https://github.com/test/repo",
            "git_pat": "token",
            "git_branch": "main"
        }

        promotion_service.db.get_environment = AsyncMock(side_effect=[mock_source_env, mock_target_env])
        promotion_service.db.list_logical_credentials = AsyncMock(return_value=[])
        promotion_service.db.list_credential_mappings = AsyncMock(return_value=[])

        # Mock database service for onboarding check
        with patch('app.services.promotion_service.db_service') as mock_db_service:
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)

        workflow_selections = [
            WorkflowSelection(
                workflow_id="wf-1",
                workflow_name="Workflow 1",
                change_type=WorkflowChangeType.CHANGED,
                enabled_in_source=True,
                selected=True
            ),
            WorkflowSelection(
                workflow_id="wf-2",
                workflow_name="Workflow 2",
                change_type=WorkflowChangeType.CHANGED,
                enabled_in_source=True,
                selected=True
            ),
            WorkflowSelection(
                workflow_id="wf-3",
                workflow_name="Workflow 3",
                change_type=WorkflowChangeType.CHANGED,
                enabled_in_source=True,
                selected=True
            ),
        ]

        source_workflows = {
            "wf-1": {"id": "wf-1", "name": "Workflow 1", "active": True, "nodes": []},
            "wf-2": {"id": "wf-2", "name": "Workflow 2", "active": True, "nodes": []},
            "wf-3": {"id": "wf-3", "name": "Workflow 3", "active": True, "nodes": []},
        }

        with patch('app.services.promotion_service.db_service') as mock_db_service, \
             patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, 'rollback_promotion', new_callable=AsyncMock) as mock_rollback, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=source_workflows)
            mock_gh_service.return_value = mock_gh

            # Mock adapter to succeed on wf-1, fail on wf-2
            call_count = 0
            async def mock_update(wf_id, wf_data):
                nonlocal call_count
                call_count += 1
                if wf_id == "wf-2":
                    raise Exception("Deployment failed")

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock(side_effect=mock_update)
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            # Mock rollback result
            mock_rollback.return_value = RollbackResult(
                rollback_triggered=True,
                workflows_rolled_back=1,
                rollback_errors=[],
                snapshot_id="snap-pre-123",
                rollback_method="git_restore",
                rollback_timestamp=datetime.utcnow()
            )

            result = await promotion_service.execute_promotion(
                tenant_id=tenant_id,
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=workflow_selections,
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags={}
            )

            # Verify rollback was triggered with correct parameters
            mock_rollback.assert_called_once()
            call_kwargs = mock_rollback.call_args.kwargs
            assert call_kwargs["promoted_workflow_ids"] == ["wf-1"]
            assert call_kwargs["pre_promotion_snapshot_id"] == "snap-pre-123"
            assert call_kwargs["promotion_id"] == "promo-1"

            # Verify execution result reflects failure and rollback
            assert result.status == PromotionStatus.FAILED
            assert result.workflows_promoted == 1
            assert result.workflows_failed == 1
            assert result.rollback_result is not None
            assert result.rollback_result.workflows_rolled_back == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_promotion_includes_rollback_result_in_execution_result(self, promotion_service):
        """Failed promotion should include complete RollbackResult in execution result."""
        tenant_id = "00000000-0000-0000-0000-000000000001"
        mock_source_env = {"id": "env-source", "n8n_type": "staging", "git_repo_url": "repo", "git_pat": "token", "git_branch": "main"}
        mock_target_env = {"id": "env-target", "n8n_type": "production", "git_repo_url": "repo", "git_pat": "token", "git_branch": "main"}

        promotion_service.db.get_environment = AsyncMock(side_effect=[mock_source_env, mock_target_env])
        promotion_service.db.list_logical_credentials = AsyncMock(return_value=[])
        promotion_service.db.list_credential_mappings = AsyncMock(return_value=[])

        workflow_selections = [
            WorkflowSelection(
                workflow_id="wf-1",
                workflow_name="Workflow 1",
                change_type=WorkflowChangeType.CHANGED,
                enabled_in_source=True,
                selected=True
            ),
        ]

        with patch('app.services.promotion_service.db_service') as mock_db_service, \
             patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, 'rollback_promotion', new_callable=AsyncMock) as mock_rollback, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value={
                "wf-1": {"id": "wf-1", "name": "Workflow 1", "active": True, "nodes": []},
            })
            mock_gh_service.return_value = mock_gh

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock(side_effect=Exception("Failed"))
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            rollback_result = RollbackResult(
                rollback_triggered=True,
                workflows_rolled_back=0,
                rollback_errors=["Rollback error"],
                snapshot_id="snap-pre-123",
                rollback_method="git_restore",
                rollback_timestamp=datetime(2024, 1, 15, 12, 0, 0)
            )
            mock_rollback.return_value = rollback_result

            result = await promotion_service.execute_promotion(
                tenant_id=tenant_id,
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=workflow_selections,
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags={}
            )

            # Verify rollback result is included
            assert result.rollback_result is not None
            assert result.rollback_result.rollback_triggered is True
            assert result.rollback_result.snapshot_id == "snap-pre-123"
            assert result.rollback_result.rollback_method == "git_restore"
            assert len(result.rollback_result.rollback_errors) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_promotion_stops_processing_after_first_failure(self, promotion_service):
        """Promotion should stop processing remaining workflows after first failure."""
        tenant_id = "00000000-0000-0000-0000-000000000001"
        mock_source_env = {"id": "env-source", "n8n_type": "staging", "git_repo_url": "repo", "git_pat": "token", "git_branch": "main"}
        mock_target_env = {"id": "env-target", "n8n_type": "production", "git_repo_url": "repo", "git_pat": "token", "git_branch": "main"}

        promotion_service.db.get_environment = AsyncMock(side_effect=[mock_source_env, mock_target_env])
        promotion_service.db.list_logical_credentials = AsyncMock(return_value=[])
        promotion_service.db.list_credential_mappings = AsyncMock(return_value=[])

        workflow_selections = [
            WorkflowSelection(workflow_id="wf-1", workflow_name="WF1", change_type=WorkflowChangeType.CHANGED, enabled_in_source=True, selected=True),
            WorkflowSelection(workflow_id="wf-2", workflow_name="WF2", change_type=WorkflowChangeType.CHANGED, enabled_in_source=True, selected=True),
            WorkflowSelection(workflow_id="wf-3", workflow_name="WF3", change_type=WorkflowChangeType.CHANGED, enabled_in_source=True, selected=True),
            WorkflowSelection(workflow_id="wf-4", workflow_name="WF4", change_type=WorkflowChangeType.CHANGED, enabled_in_source=True, selected=True),
            WorkflowSelection(workflow_id="wf-5", workflow_name="WF5", change_type=WorkflowChangeType.CHANGED, enabled_in_source=True, selected=True),
        ]

        source_workflows = {f"wf-{i}": {"id": f"wf-{i}", "name": f"WF{i}", "active": True, "nodes": []} for i in range(1, 6)}

        with patch('app.services.promotion_service.db_service') as mock_db_service, \
             patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, 'rollback_promotion', new_callable=AsyncMock) as mock_rollback, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value=source_workflows)
            mock_gh_service.return_value = mock_gh

            # Fail on workflow 3
            call_count = 0
            async def mock_update(wf_id, wf_data):
                nonlocal call_count
                call_count += 1
                if wf_id == "wf-3":
                    raise Exception("Failed on wf-3")

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock(side_effect=mock_update)
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            mock_rollback.return_value = RollbackResult(
                rollback_triggered=True,
                workflows_rolled_back=2,
                rollback_errors=[],
                snapshot_id="snap-pre-123",
                rollback_method="git_restore",
                rollback_timestamp=datetime.utcnow()
            )

            result = await promotion_service.execute_promotion(
                tenant_id=tenant_id,
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=workflow_selections,
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags={}
            )

            # Verify only 3 workflows were attempted (wf-1, wf-2, wf-3)
            # wf-4 and wf-5 should NOT be attempted
            assert call_count == 3
            assert result.workflows_promoted == 2  # wf-1 and wf-2 succeeded
            assert result.workflows_failed == 1   # wf-3 failed
            assert mock_rollback.call_args.kwargs["promoted_workflow_ids"] == ["wf-1", "wf-2"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_promotion_creates_audit_log_with_rollback_info(self, promotion_service):
        """Failed promotion should create audit log with complete rollback information."""
        tenant_id = "00000000-0000-0000-0000-000000000001"
        mock_source_env = {"id": "env-source", "n8n_type": "staging", "git_repo_url": "repo", "git_pat": "token", "git_branch": "main"}
        mock_target_env = {"id": "env-target", "n8n_type": "production", "git_repo_url": "repo", "git_pat": "token", "git_branch": "main"}

        promotion_service.db.get_environment = AsyncMock(side_effect=[mock_source_env, mock_target_env])
        promotion_service.db.list_logical_credentials = AsyncMock(return_value=[])
        promotion_service.db.list_credential_mappings = AsyncMock(return_value=[])

        workflow_selections = [
            WorkflowSelection(workflow_id="wf-1", workflow_name="WF1", change_type=WorkflowChangeType.CHANGED, enabled_in_source=True, selected=True),
        ]

        with patch('app.services.promotion_service.db_service') as mock_db_service, \
             patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, 'rollback_promotion', new_callable=AsyncMock) as mock_rollback, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit:

            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value={"wf-1": {"id": "wf-1", "name": "WF1", "nodes": []}})
            mock_gh_service.return_value = mock_gh

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock(side_effect=Exception("Failed"))
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            mock_rollback.return_value = RollbackResult(
                rollback_triggered=True,
                workflows_rolled_back=0,
                rollback_errors=["Error 1", "Error 2"],
                snapshot_id="snap-pre-123",
                rollback_method="git_restore",
                rollback_timestamp=datetime.utcnow()
            )

            await promotion_service.execute_promotion(
                tenant_id=tenant_id,
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=workflow_selections,
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags={}
            )

            # Verify audit log was created with rollback info
            mock_audit.assert_called()
            call_kwargs = mock_audit.call_args.kwargs

            assert call_kwargs["action"] == "execute"
            assert call_kwargs["result"]["status"] == "failed_with_rollback"
            assert call_kwargs["result"]["rollback_triggered"] is True
            assert call_kwargs["result"]["rollback_result"]["workflows_rolled_back"] == 0
            assert len(call_kwargs["result"]["rollback_result"]["rollback_errors"]) == 2

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_successful_promotion_has_no_rollback_result(self, promotion_service):
        """Successful promotion should not have rollback result."""
        tenant_id = "00000000-0000-0000-0000-000000000001"
        mock_source_env = {"id": "env-source", "n8n_type": "staging", "git_repo_url": "repo", "git_pat": "token", "git_branch": "main"}
        mock_target_env = {"id": "env-target", "n8n_type": "production", "git_repo_url": "repo", "git_pat": "token", "git_branch": "main"}

        promotion_service.db.get_environment = AsyncMock(side_effect=[mock_source_env, mock_target_env])
        promotion_service.db.list_logical_credentials = AsyncMock(return_value=[])
        promotion_service.db.list_credential_mappings = AsyncMock(return_value=[])

        workflow_selections = [
            WorkflowSelection(workflow_id="wf-1", workflow_name="WF1", change_type=WorkflowChangeType.CHANGED, enabled_in_source=True, selected=True),
        ]

        with patch('app.services.promotion_service.db_service') as mock_db_service, \
             patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock):

            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)

            mock_gh = MagicMock()
            mock_gh.get_all_workflows_from_github = AsyncMock(return_value={"wf-1": {"id": "wf-1", "name": "WF1", "nodes": []}})
            mock_gh_service.return_value = mock_gh

            mock_adapter = MagicMock()
            mock_adapter.update_workflow = AsyncMock()
            mock_registry.get_adapter_for_environment.return_value = mock_adapter

            result = await promotion_service.execute_promotion(
                tenant_id=tenant_id,
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=workflow_selections,
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags={}
            )

            # Verify no rollback on success
            assert result.status == PromotionStatus.COMPLETED
            assert result.rollback_result is None
            assert result.workflows_promoted == 1
            assert result.workflows_failed == 0
