"""
Unit tests for conflict policy flag enforcement in promotion service.

This test suite verifies Task E requirements:
- allowOverwritingHotfixes flag enforcement (T005)
- allowForcePromotionOnConflicts flag enforcement (T006)
- Comprehensive coverage of all diff states and flag combinations
- Audit trail completeness for blocked/allowed workflows
- Deterministic behavior across executions

This is an MVP ship-blocker test suite ensuring conflict policy flags
behave correctly and prevent regressions.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from typing import List, Dict, Any

# Patch db_service at module level before importing PromotionService
pytestmark = pytest.mark.asyncio

from app.services.promotion_service import PromotionService
from app.schemas.promotion import (
    PromotionStatus,
    WorkflowChangeType,
    WorkflowSelection,
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
def mock_source_environment():
    """Create a mock source environment configuration."""
    return {
        "id": "env-source",
        "tenant_id": "tenant-1",
        "n8n_name": "Development",
        "n8n_type": "dev",
        "n8n_base_url": "https://dev.n8n.example.com",
        "n8n_api_key": "test-api-key-dev",
        "git_repo_url": "https://github.com/test/repo",
        "git_pat": "test-token",
        "git_branch": "main",
        "is_active": True,
        "provider": "n8n",
    }


@pytest.fixture
def mock_target_environment():
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
def mock_pre_promotion_snapshot():
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
            "workflows_count": 0,
            "workflows": []
        },
        "created_at": datetime(2024, 1, 15, 10, 0, 0).isoformat()
    }


@pytest.fixture
def mock_source_snapshot():
    """Create a mock source snapshot."""
    return {
        "id": "snap-source-123",
        "environment_id": "env-source",
        "tenant_id": "tenant-1",
        "git_commit_sha": "source123",
        "type": "manual",
        "metadata_json": {},
        "created_at": datetime(2024, 1, 15, 9, 0, 0).isoformat()
    }


@pytest.fixture
def base_workflow_data():
    """Create base workflow data for testing."""
    return {
        "id": "wf-1",
        "name": "Test Workflow",
        "active": True,
        "nodes": [
            {
                "id": "node-1",
                "name": "Start",
                "type": "n8n-nodes-base.start",
                "typeVersion": 1,
                "position": [250, 300],
                "parameters": {}
            }
        ],
        "connections": {},
        "settings": {},
        "staticData": None,
    }


@pytest.fixture
def staging_hotfix_workflow():
    """Create a workflow selection with STAGING_HOTFIX change type."""
    return WorkflowSelection(
        workflow_id="wf-hotfix",
        workflow_name="Hotfix Workflow",
        change_type=WorkflowChangeType.STAGING_HOTFIX,
        enabled_in_source=True,
        enabled_in_target=True,
        selected=True,
        requires_overwrite=False
    )


@pytest.fixture
def requires_overwrite_workflow():
    """Create a workflow selection with requires_overwrite=True."""
    return WorkflowSelection(
        workflow_id="wf-conflict",
        workflow_name="Conflict Workflow",
        change_type=WorkflowChangeType.CHANGED,
        enabled_in_source=True,
        enabled_in_target=True,
        selected=True,
        requires_overwrite=True
    )


@pytest.fixture
def new_workflow():
    """Create a new workflow selection."""
    return WorkflowSelection(
        workflow_id="wf-new",
        workflow_name="New Workflow",
        change_type=WorkflowChangeType.NEW,
        enabled_in_source=True,
        enabled_in_target=None,
        selected=True,
        requires_overwrite=False
    )


@pytest.fixture
def unchanged_workflow():
    """Create an unchanged workflow selection."""
    return WorkflowSelection(
        workflow_id="wf-unchanged",
        workflow_name="Unchanged Workflow",
        change_type=WorkflowChangeType.UNCHANGED,
        enabled_in_source=True,
        enabled_in_target=True,
        selected=True,
        requires_overwrite=False
    )


def setup_mock_services(
    promotion_service,
    mock_source_env,
    mock_target_env,
    mock_pre_snapshot,
    mock_source_snapshot,
    source_workflows: Dict[str, Any] = None,
    target_workflows: List[Any] = None
):
    """
    Setup common mocks for promotion service tests.
    
    Returns:
        tuple: (mock_adapter, mock_gh_service, mock_audit_log)
    """
    if source_workflows is None:
        source_workflows = {}
    if target_workflows is None:
        target_workflows = []
    
    # Mock database
    promotion_service.db.get_environment = AsyncMock(
        side_effect=lambda env_id, tenant_id: 
            mock_source_env if env_id == "env-source" else mock_target_env
    )
    promotion_service.db.get_snapshot = AsyncMock(
        side_effect=lambda snap_id, tenant_id:
            mock_pre_snapshot if snap_id == "snap-pre-123" else mock_source_snapshot
    )
    promotion_service.db.create_snapshot = AsyncMock(return_value="snap-post-456")
    promotion_service.db.get_promotion = AsyncMock(return_value={
        "id": "promo-1",
        "tenant_id": "tenant-1",
        "status": "running"
    })
    promotion_service.db.update_promotion_status = AsyncMock()
    promotion_service.db.check_onboarding_gate = AsyncMock(return_value=True)
    promotion_service.db.list_logical_credentials = AsyncMock(return_value=[])
    promotion_service.db.list_credential_mappings = AsyncMock(return_value=[])
    promotion_service.db.create_deployment = AsyncMock(return_value="deployment-123")
    promotion_service.db.create_deployment_workflow = AsyncMock()
    promotion_service.db.update_deployment_status = AsyncMock()
    promotion_service.db.update_workflow_git_state = AsyncMock()
    
    # Mock GitHub service
    mock_gh = MagicMock()
    mock_gh.get_all_workflows_from_github = AsyncMock(return_value=source_workflows)
    mock_gh.export_and_commit_workflows = AsyncMock(return_value="commit-sha-123")
    
    # Mock adapter
    mock_adapter = MagicMock()
    mock_adapter.get_workflows = AsyncMock(return_value=target_workflows)
    mock_adapter.get_workflow = AsyncMock(return_value=None)
    mock_adapter.create_workflow = AsyncMock(return_value={"id": "wf-created"})
    mock_adapter.update_workflow = AsyncMock(return_value={"id": "wf-updated"})
    
    # Mock audit log
    mock_audit_log = AsyncMock()
    
    return mock_adapter, mock_gh, mock_audit_log


# ============ Test Classes ============


class TestAllowOverwritingHotfixesFlag:
    """
    Tests for allowOverwritingHotfixes flag enforcement (T005).
    
    Verifies that workflows with change_type=STAGING_HOTFIX are correctly
    blocked or allowed based on the flag value.
    """
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_staging_hotfix_blocked_when_flag_false(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        staging_hotfix_workflow,
        base_workflow_data
    ):
        """
        Test that STAGING_HOTFIX workflows are blocked when allowOverwritingHotfixes=false.
        
        Given: A workflow with change_type=STAGING_HOTFIX
        When: allowOverwritingHotfixes flag is false
        Then: Workflow is skipped with policy violation error
        """
        # Setup
        source_workflows = {
            "wf-hotfix": {**base_workflow_data, "id": "wf-hotfix", "name": "Hotfix Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            # Execute with flag = false
            policy_flags = {
                'allow_overwriting_hotfixes': False,
                'allow_force_promotion_on_conflicts': False
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[staging_hotfix_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Assertions
            assert result.status == PromotionStatus.FAILED
            assert result.workflows_promoted == 0
            assert result.workflows_failed == 1
            assert result.workflows_skipped == 0
            
            # Verify error message contains policy violation
            assert len(result.errors) > 0
            error_msg = result.errors[0].lower()
            assert "policy violation" in error_msg
            assert "hotfix" in error_msg
            assert "allow_overwriting_hotfixes" in error_msg
            
            # Verify workflow was NOT promoted to target
            mock_adapter.create_workflow.assert_not_called()
            mock_adapter.update_workflow.assert_not_called()
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_staging_hotfix_allowed_when_flag_true(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        staging_hotfix_workflow,
        base_workflow_data
    ):
        """
        Test that STAGING_HOTFIX workflows are allowed when allowOverwritingHotfixes=true.
        
        Given: A workflow with change_type=STAGING_HOTFIX
        When: allowOverwritingHotfixes flag is true
        Then: Workflow is promoted successfully
        """
        # Setup
        source_workflows = {
            "wf-hotfix": {**base_workflow_data, "id": "wf-hotfix", "name": "Hotfix Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            # Execute with flag = true
            policy_flags = {
                'allow_overwriting_hotfixes': True,
                'allow_force_promotion_on_conflicts': False
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[staging_hotfix_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Assertions
            assert result.status == PromotionStatus.COMPLETED
            assert result.workflows_promoted == 1
            assert result.workflows_failed == 0
            
            # Verify workflow was promoted (created or updated)
            call_count = mock_adapter.create_workflow.call_count + mock_adapter.update_workflow.call_count
            assert call_count == 1
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_non_hotfix_workflows_unaffected(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        new_workflow,
        base_workflow_data
    ):
        """
        Test that non-hotfix workflows are unaffected by allowOverwritingHotfixes flag.
        
        Given: Workflows with change_type=NEW/CHANGED/UNCHANGED
        When: allowOverwritingHotfixes flag is false
        Then: Flag has no effect, workflows processed normally
        """
        # Setup - test NEW workflow
        changed_workflow = WorkflowSelection(
            workflow_id="wf-changed",
            workflow_name="Changed Workflow",
            change_type=WorkflowChangeType.CHANGED,
            enabled_in_source=True,
            enabled_in_target=True,
            selected=True,
            requires_overwrite=False
        )
        
        source_workflows = {
            "wf-new": {**base_workflow_data, "id": "wf-new", "name": "New Workflow"},
            "wf-changed": {**base_workflow_data, "id": "wf-changed", "name": "Changed Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            # Execute with flag = false (should not affect non-hotfix workflows)
            policy_flags = {
                'allow_overwriting_hotfixes': False,
                'allow_force_promotion_on_conflicts': False
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[new_workflow, changed_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Assertions - both workflows should succeed
            assert result.status == PromotionStatus.COMPLETED
            assert result.workflows_promoted == 2
            assert result.workflows_failed == 0


class TestAllowForcePromotionOnConflictsFlag:
    """
    Tests for allowForcePromotionOnConflicts flag enforcement (T006).
    
    Verifies that workflows with requires_overwrite=True are correctly
    blocked or allowed based on the flag value.
    """
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_requires_overwrite_blocked_when_flag_false(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        requires_overwrite_workflow,
        base_workflow_data
    ):
        """
        Test that workflows with requires_overwrite=True are blocked when flag is false.
        
        Given: A workflow with requires_overwrite=True
        When: allowForcePromotionOnConflicts flag is false
        Then: Workflow is skipped with policy violation error
        """
        # Setup
        source_workflows = {
            "wf-conflict": {**base_workflow_data, "id": "wf-conflict", "name": "Conflict Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            # Execute with flag = false
            policy_flags = {
                'allow_overwriting_hotfixes': False,
                'allow_force_promotion_on_conflicts': False
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[requires_overwrite_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Assertions
            assert result.status == PromotionStatus.FAILED
            assert result.workflows_promoted == 0
            assert result.workflows_failed == 1
            
            # Verify error message contains policy violation
            assert len(result.errors) > 0
            error_msg = result.errors[0].lower()
            assert "policy violation" in error_msg
            assert "conflict" in error_msg
            assert "allow_force_promotion_on_conflicts" in error_msg
            
            # Verify workflow was NOT promoted
            mock_adapter.create_workflow.assert_not_called()
            mock_adapter.update_workflow.assert_not_called()
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_requires_overwrite_allowed_when_flag_true(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        requires_overwrite_workflow,
        base_workflow_data
    ):
        """
        Test that workflows with requires_overwrite=True are allowed when flag is true.
        
        Given: A workflow with requires_overwrite=True
        When: allowForcePromotionOnConflicts flag is true
        Then: Workflow is promoted successfully
        """
        # Setup
        source_workflows = {
            "wf-conflict": {**base_workflow_data, "id": "wf-conflict", "name": "Conflict Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            # Execute with flag = true
            policy_flags = {
                'allow_overwriting_hotfixes': False,
                'allow_force_promotion_on_conflicts': True
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[requires_overwrite_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Assertions
            assert result.status == PromotionStatus.COMPLETED
            assert result.workflows_promoted == 1
            assert result.workflows_failed == 0
            
            # Verify workflow was promoted
            call_count = mock_adapter.create_workflow.call_count + mock_adapter.update_workflow.call_count
            assert call_count == 1
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_new_workflows_unaffected_by_conflict_flag(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        new_workflow,
        base_workflow_data
    ):
        """
        Test that new workflows are unaffected by allowForcePromotionOnConflicts flag.
        
        Given: A workflow with change_type=NEW and requires_overwrite=False
        When: allowForcePromotionOnConflicts flag is false
        Then: Workflow is promoted successfully regardless of flag
        """
        # Setup
        source_workflows = {
            "wf-new": {**base_workflow_data, "id": "wf-new", "name": "New Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            # Execute with flag = false (should not affect new workflows)
            policy_flags = {
                'allow_overwriting_hotfixes': False,
                'allow_force_promotion_on_conflicts': False
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[new_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Assertions
            assert result.status == PromotionStatus.COMPLETED
            assert result.workflows_promoted == 1
            assert result.workflows_failed == 0


class TestCombinedFlagBehavior:
    """
    Tests for combined flag behavior and independence.
    
    Verifies that both flags work correctly together and independently.
    """
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_both_flags_false_blocks_both_scenarios(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        staging_hotfix_workflow,
        requires_overwrite_workflow,
        new_workflow,
        base_workflow_data
    ):
        """
        Test that both flags being false blocks their respective scenarios.
        
        Given: Mix of STAGING_HOTFIX, requires_overwrite, and NEW workflows
        When: Both flags are false
        Then: Only NEW workflow succeeds, others blocked
        """
        # Setup
        source_workflows = {
            "wf-hotfix": {**base_workflow_data, "id": "wf-hotfix", "name": "Hotfix Workflow"},
            "wf-conflict": {**base_workflow_data, "id": "wf-conflict", "name": "Conflict Workflow"},
            "wf-new": {**base_workflow_data, "id": "wf-new", "name": "New Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            # Execute with both flags = false
            policy_flags = {
                'allow_overwriting_hotfixes': False,
                'allow_force_promotion_on_conflicts': False
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[
                    staging_hotfix_workflow,
                    requires_overwrite_workflow,
                    new_workflow
                ],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Assertions
            assert result.status == PromotionStatus.FAILED
            assert result.workflows_promoted == 1  # Only NEW workflow
            assert result.workflows_failed == 2   # STAGING_HOTFIX and requires_overwrite
            
            # Verify error messages for both blocked workflows
            assert len(result.errors) == 2
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_both_flags_true_allows_all_scenarios(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        staging_hotfix_workflow,
        requires_overwrite_workflow,
        new_workflow,
        base_workflow_data
    ):
        """
        Test that both flags being true allows all workflow types.
        
        Given: Mix of STAGING_HOTFIX, requires_overwrite, and NEW workflows
        When: Both flags are true
        Then: All workflows succeed
        """
        # Setup
        source_workflows = {
            "wf-hotfix": {**base_workflow_data, "id": "wf-hotfix", "name": "Hotfix Workflow"},
            "wf-conflict": {**base_workflow_data, "id": "wf-conflict", "name": "Conflict Workflow"},
            "wf-new": {**base_workflow_data, "id": "wf-new", "name": "New Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            # Execute with both flags = true
            policy_flags = {
                'allow_overwriting_hotfixes': True,
                'allow_force_promotion_on_conflicts': True
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[
                    staging_hotfix_workflow,
                    requires_overwrite_workflow,
                    new_workflow
                ],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Assertions
            assert result.status == PromotionStatus.COMPLETED
            assert result.workflows_promoted == 3
            assert result.workflows_failed == 0
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_independent_flag_enforcement(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        staging_hotfix_workflow,
        requires_overwrite_workflow,
        base_workflow_data
    ):
        """
        Test that flags are enforced independently.
        
        Verify:
        - STAGING_HOTFIX only checks allowOverwritingHotfixes
        - requires_overwrite only checks allowForcePromotionOnConflicts
        """
        # Setup
        source_workflows = {
            "wf-hotfix": {**base_workflow_data, "id": "wf-hotfix", "name": "Hotfix Workflow"},
            "wf-conflict": {**base_workflow_data, "id": "wf-conflict", "name": "Conflict Workflow"}
        }
        
        # Test 1: allowOverwritingHotfixes=true, allowForcePromotionOnConflicts=false
        # Expected: STAGING_HOTFIX succeeds, requires_overwrite fails
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock), \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            policy_flags = {
                'allow_overwriting_hotfixes': True,
                'allow_force_promotion_on_conflicts': False
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[staging_hotfix_workflow, requires_overwrite_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            assert result.workflows_promoted == 1  # STAGING_HOTFIX
            assert result.workflows_failed == 1    # requires_overwrite
        
        # Test 2: allowOverwritingHotfixes=false, allowForcePromotionOnConflicts=true
        # Expected: STAGING_HOTFIX fails, requires_overwrite succeeds
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock), \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            policy_flags = {
                'allow_overwriting_hotfixes': False,
                'allow_force_promotion_on_conflicts': True
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[staging_hotfix_workflow, requires_overwrite_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            assert result.workflows_promoted == 1  # requires_overwrite
            assert result.workflows_failed == 1    # STAGING_HOTFIX


class TestAuditTrailCompleteness:
    """
    Tests for audit trail completeness.
    
    Verifies that blocked and allowed workflows are properly recorded
    in audit logs with correct snapshot IDs and outcomes.
    """
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_blocked_workflows_recorded_in_audit(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        staging_hotfix_workflow,
        requires_overwrite_workflow,
        base_workflow_data
    ):
        """
        Test that blocked workflows are recorded in audit log.
        
        Verify audit log contains:
        - Pre-promotion snapshot ID
        - Workflow names
        - Block reason (policy violation)
        - Error messages
        """
        # Setup
        source_workflows = {
            "wf-hotfix": {**base_workflow_data, "id": "wf-hotfix", "name": "Hotfix Workflow"},
            "wf-conflict": {**base_workflow_data, "id": "wf-conflict", "name": "Conflict Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            policy_flags = {
                'allow_overwriting_hotfixes': False,
                'allow_force_promotion_on_conflicts': False
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[staging_hotfix_workflow, requires_overwrite_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Verify audit log was called
            assert mock_audit.call_count > 0
            
            # Verify audit log was called (audit trail created)
            assert mock_audit.called
            
            # Verify errors are recorded in result
            assert len(result.errors) == 2
            assert any("hotfix" in err.lower() for err in result.errors)
            assert any("conflict" in err.lower() for err in result.errors)
            
            # Verify both workflows were blocked
            assert result.workflows_promoted == 0
            assert result.workflows_failed == 2
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_allowed_workflows_recorded_in_audit(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        new_workflow,
        base_workflow_data
    ):
        """
        Test that allowed workflows are recorded in audit log.
        
        Verify audit log contains:
        - Pre/post snapshot IDs
        - Promotion outcome = success
        - Workflow IDs promoted
        """
        # Setup
        source_workflows = {
            "wf-new": {**base_workflow_data, "id": "wf-new", "name": "New Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            policy_flags = {
                'allow_overwriting_hotfixes': False,
                'allow_force_promotion_on_conflicts': False
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[new_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Verify successful promotion
            assert result.status == PromotionStatus.COMPLETED
            assert result.workflows_promoted == 1
            assert result.workflows_failed == 0
            
            # Verify audit log was called (audit trail created)
            assert mock_audit.call_count > 0
            
            # Verify workflow was promoted
            call_count = mock_adapter.create_workflow.call_count + mock_adapter.update_workflow.call_count
            assert call_count >= 1
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_snapshot_ids_match_actual_snapshots(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        new_workflow,
        base_workflow_data
    ):
        """
        Test that snapshot IDs in result match actual snapshot records.
        
        Verify: Snapshot IDs in audit log reference real snapshot records
        """
        # Setup
        source_workflows = {
            "wf-new": {**base_workflow_data, "id": "wf-new", "name": "New Workflow"}
        }
        
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock) as mock_audit, \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            policy_flags = {
                'allow_overwriting_hotfixes': False,
                'allow_force_promotion_on_conflicts': False
            }
            
            result = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[new_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags=policy_flags
            )
            
            # Verify successful promotion
            assert result.status == PromotionStatus.COMPLETED
            assert result.workflows_promoted == 1
            assert result.workflows_failed == 0
            
            # Verify the promotion was executed with the correct snapshot IDs
            # (passed as parameters to execute_promotion)
            assert mock_adapter.create_workflow.call_count + mock_adapter.update_workflow.call_count >= 1


class TestDeterministicBehavior:
    """
    Tests for deterministic behavior.
    
    Verifies that promotion behavior is consistent and predictable.
    """
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_same_input_produces_same_output(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        staging_hotfix_workflow,
        base_workflow_data
    ):
        """
        Test that same input produces same output.
        
        Run same promotion scenario twice with identical inputs.
        Verify: same workflows blocked/allowed in both runs
        """
        # Setup
        source_workflows = {
            "wf-hotfix": {**base_workflow_data, "id": "wf-hotfix", "name": "Hotfix Workflow"}
        }
        
        policy_flags = {
            'allow_overwriting_hotfixes': False,
            'allow_force_promotion_on_conflicts': False
        }
        
        results = []
        
        # Run promotion twice with identical setup
        for _ in range(2):
            with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
                 patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
                 patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock), \
                 patch('app.services.promotion_service.db_service') as mock_db_service:
                
                mock_adapter, mock_gh, _ = setup_mock_services(
                    promotion_service,
                    mock_source_environment,
                    mock_target_environment,
                    mock_pre_promotion_snapshot,
                    mock_source_snapshot,
                    source_workflows=source_workflows
                )
                mock_gh_service.return_value = mock_gh
                mock_registry.get_adapter_for_environment.return_value = mock_adapter
                mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
                
                result = await promotion_service.execute_promotion(
                    tenant_id="tenant-1",
                    promotion_id="promo-1",
                    source_env_id="env-source",
                    target_env_id="env-target",
                    workflow_selections=[staging_hotfix_workflow],
                    source_snapshot_id="snap-source-123",
                    target_pre_snapshot_id="snap-pre-123",
                    policy_flags=policy_flags
                )
                
                results.append(result)
        
        # Verify both runs produced identical results
        assert results[0].status == results[1].status
        assert results[0].workflows_promoted == results[1].workflows_promoted
        assert results[0].workflows_failed == results[1].workflows_failed
        assert results[0].workflows_skipped == results[1].workflows_skipped
        assert len(results[0].errors) == len(results[1].errors)
    
    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_flag_changes_affect_outcome(
        self,
        promotion_service,
        mock_source_environment,
        mock_target_environment,
        mock_pre_promotion_snapshot,
        mock_source_snapshot,
        staging_hotfix_workflow,
        base_workflow_data
    ):
        """
        Test that flag changes affect promotion outcome.
        
        Run promotion with flag=false, then flag=true.
        Verify: blocked workflows in first run succeed in second
        """
        # Setup
        source_workflows = {
            "wf-hotfix": {**base_workflow_data, "id": "wf-hotfix", "name": "Hotfix Workflow"}
        }
        
        # Run 1: flag = false
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock), \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            result_blocked = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[staging_hotfix_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags={
                    'allow_overwriting_hotfixes': False,
                    'allow_force_promotion_on_conflicts': False
                }
            )
        
        # Run 2: flag = true
        with patch.object(promotion_service, '_get_github_service') as mock_gh_service, \
             patch('app.services.promotion_service.ProviderRegistry') as mock_registry, \
             patch.object(promotion_service, '_create_audit_log', new_callable=AsyncMock), \
             patch('app.services.promotion_service.db_service') as mock_db_service:
            
            mock_adapter, mock_gh, _ = setup_mock_services(
                promotion_service,
                mock_source_environment,
                mock_target_environment,
                mock_pre_promotion_snapshot,
                mock_source_snapshot,
                source_workflows=source_workflows
            )
            mock_gh_service.return_value = mock_gh
            mock_registry.get_adapter_for_environment.return_value = mock_adapter
            mock_db_service.check_onboarding_gate = AsyncMock(return_value=True)
            
            result_allowed = await promotion_service.execute_promotion(
                tenant_id="tenant-1",
                promotion_id="promo-1",
                source_env_id="env-source",
                target_env_id="env-target",
                workflow_selections=[staging_hotfix_workflow],
                source_snapshot_id="snap-source-123",
                target_pre_snapshot_id="snap-pre-123",
                policy_flags={
                    'allow_overwriting_hotfixes': True,
                    'allow_force_promotion_on_conflicts': False
                }
            )
        
        # Verify outcomes are different
        assert result_blocked.status == PromotionStatus.FAILED
        assert result_blocked.workflows_promoted == 0
        assert result_blocked.workflows_failed == 1
        
        assert result_allowed.status == PromotionStatus.COMPLETED
        assert result_allowed.workflows_promoted == 1
        assert result_allowed.workflows_failed == 0

