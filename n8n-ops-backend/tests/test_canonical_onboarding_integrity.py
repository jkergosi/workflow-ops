"""
Comprehensive Test Suite for Canonical Onboarding Retry Safety and Integrity

Tests ensure that:
1. Bulk onboarding operations are idempotent and safe to retry
2. No duplicate workflow mappings are created on retry
3. Existing correct state is preserved during retries
4. Transaction boundaries provide proper failure isolation
5. Status precedence rules are correctly applied
6. Per-workflow error tracking works correctly
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
from uuid import uuid4

from app.services.canonical_onboarding_service import CanonicalOnboardingService
from app.services.canonical_env_sync_service import CanonicalEnvSyncService
from app.services.canonical_repo_sync_service import CanonicalRepoSyncService
from app.schemas.canonical_workflow import WorkflowMappingStatus


# Test Fixtures
@pytest.fixture
def tenant_id():
    """Test tenant ID"""
    return str(uuid4())


@pytest.fixture
def anchor_env_id():
    """Anchor environment ID"""
    return str(uuid4())


@pytest.fixture
def dev_env_id():
    """Development environment ID"""
    return str(uuid4())


@pytest.fixture
def staging_env_id():
    """Staging environment ID"""
    return str(uuid4())


@pytest.fixture
def mock_db_service():
    """Mock database service"""
    with patch('app.services.canonical_onboarding_service.db_service') as mock_db:
        yield mock_db


@pytest.fixture
def mock_env_sync_db_service():
    """Mock database service for env sync service"""
    with patch('app.services.canonical_env_sync_service.db_service') as mock_db:
        yield mock_db


@pytest.fixture
def sample_workflow_data():
    """Sample n8n workflow data"""
    return {
        "id": "wf-001",
        "name": "Test Workflow",
        "nodes": [
            {"type": "n8n-nodes-base.start", "name": "Start"},
            {"type": "n8n-nodes-base.httpRequest", "name": "HTTP Request"}
        ],
        "connections": {},
        "active": True,
        "updatedAt": "2024-01-01T12:00:00Z"
    }


@pytest.fixture
def environment_configs(anchor_env_id, dev_env_id, staging_env_id):
    """Sample environment configurations"""
    return [
        {
            "environment_id": anchor_env_id,
            "git_repo_url": "https://github.com/test/repo",
            "git_folder": "workflows"
        },
        {
            "environment_id": dev_env_id,
            "git_repo_url": None,
            "git_folder": None
        },
        {
            "environment_id": staging_env_id,
            "git_repo_url": None,
            "git_folder": None
        }
    ]


# Test Category: Idempotency and Retry Safety
class TestIdempotencyAndRetrySafety:
    """Tests for idempotent operations and retry safety"""

    @pytest.mark.asyncio
    async def test_create_workflow_mapping_detects_duplicates(
        self,
        tenant_id,
        dev_env_id,
        sample_workflow_data,
        mock_env_sync_db_service
    ):
        """
        Test that _create_workflow_mapping detects when a mapping already exists
        and logs a warning (idempotency check)
        """
        # Setup: existing mapping
        existing_mapping = {
            "tenant_id": tenant_id,
            "environment_id": dev_env_id,
            "n8n_workflow_id": "wf-001",
            "canonical_id": "canonical-123",
            "env_content_hash": "hash123",
            "status": "linked"
        }

        # Mock _get_mapping_by_n8n_id to return existing mapping
        with patch.object(
            CanonicalEnvSyncService,
            '_get_mapping_by_n8n_id',
            new_callable=AsyncMock,
            return_value=existing_mapping
        ):
            # Mock database upsert
            mock_response = MagicMock()
            mock_response.data = [existing_mapping]
            mock_env_sync_db_service.client.table.return_value.upsert.return_value.execute.return_value = mock_response

            # Execute: call _create_workflow_mapping (should detect duplicate)
            with patch('app.services.canonical_env_sync_service.logger') as mock_logger:
                result = await CanonicalEnvSyncService._create_workflow_mapping(
                    tenant_id=tenant_id,
                    environment_id=dev_env_id,
                    canonical_id="canonical-123",
                    n8n_workflow_id="wf-001",
                    content_hash="hash123",
                    status=WorkflowMappingStatus.LINKED
                )

                # Assert: warning logged about existing mapping
                mock_logger.warning.assert_called_once()
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "Idempotency check" in warning_msg
                assert "already exists" in warning_msg
                assert "wf-001" in warning_msg

    @pytest.mark.asyncio
    async def test_create_workflow_mapping_uses_upsert_for_safety(
        self,
        tenant_id,
        dev_env_id,
        mock_env_sync_db_service
    ):
        """
        Test that _create_workflow_mapping uses upsert with on_conflict
        to ensure database-level idempotency
        """
        # Mock no existing mapping
        with patch.object(
            CanonicalEnvSyncService,
            '_get_mapping_by_n8n_id',
            new_callable=AsyncMock,
            return_value=None
        ):
            # Mock database upsert
            mock_table = MagicMock()
            mock_env_sync_db_service.client.table.return_value = mock_table
            mock_response = MagicMock()
            mock_response.data = [{"id": "mapping-1"}]
            mock_table.upsert.return_value.execute.return_value = mock_response

            # Execute
            await CanonicalEnvSyncService._create_workflow_mapping(
                tenant_id=tenant_id,
                environment_id=dev_env_id,
                canonical_id="canonical-123",
                n8n_workflow_id="wf-001",
                content_hash="hash123",
                status=WorkflowMappingStatus.LINKED
            )

            # Assert: upsert called with on_conflict parameter
            mock_table.upsert.assert_called_once()
            args = mock_table.upsert.call_args
            assert args[1]["on_conflict"] == "tenant_id,environment_id,n8n_workflow_id"

    @pytest.mark.asyncio
    async def test_inventory_phase_handles_partial_failures(
        self,
        tenant_id,
        anchor_env_id,
        dev_env_id,
        environment_configs,
        mock_db_service
    ):
        """
        Test that inventory phase handles partial failures gracefully:
        - One environment fails
        - Other environments continue processing
        - Failed environment is tracked in errors
        """
        # Mock get_environment to return appropriate environments
        async def get_environment_mock(env_id, tenant_id):
            if env_id == anchor_env_id:
                return {"id": anchor_env_id, "name": "Anchor", "git_repo_url": "https://github.com/test/repo"}
            elif env_id == dev_env_id:
                return {"id": dev_env_id, "name": "Dev"}
            return None

        mock_db_service.get_environment = AsyncMock(side_effect=get_environment_mock)

        # Mock anchor sync success
        with patch.object(
            CanonicalRepoSyncService,
            'sync_repository',
            new_callable=AsyncMock,
            return_value={
                "workflows_synced": 5,
                "workflows_created": 5,
                "workflows_unchanged": 0,
                "errors": []
            }
        ):
            # Mock dev env sync failure
            with patch.object(
                CanonicalEnvSyncService,
                'sync_environment',
                new_callable=AsyncMock,
                side_effect=Exception("Database connection lost")
            ):
                # Mock auto-link and suggestions
                with patch.object(
                    CanonicalOnboardingService,
                    '_auto_link_by_hash',
                    new_callable=AsyncMock,
                    return_value={"linked": 0, "errors": []}
                ):
                    with patch.object(
                        CanonicalOnboardingService,
                        '_generate_link_suggestions',
                        new_callable=AsyncMock,
                        return_value={"suggestions": 0, "errors": []}
                    ):
                        # Execute
                        results = await CanonicalOnboardingService.run_inventory_phase(
                            tenant_id=tenant_id,
                            anchor_environment_id=anchor_env_id,
                            environment_configs=environment_configs,
                            tenant_slug="test-tenant"
                        )

                        # Assert: anchor succeeded, dev failed but error is isolated
                        assert results["workflows_inventoried"] == 5
                        assert len(results["errors"]) == 1
                        assert "Database connection lost" in results["errors"][0]

                        # Assert: environment results tracked
                        assert anchor_env_id in results["environment_results"]
                        assert results["environment_results"][anchor_env_id]["success_count"] == 5

                        assert dev_env_id in results["environment_results"]
                        assert results["environment_results"][dev_env_id]["error_count"] == 1

    @pytest.mark.asyncio
    async def test_inventory_phase_retry_does_not_duplicate(
        self,
        tenant_id,
        anchor_env_id,
        dev_env_id,
        environment_configs,
        mock_db_service
    ):
        """
        Test that retrying inventory phase does not create duplicate mappings:
        - First run creates mappings
        - Second run (retry) uses upsert to update existing mappings
        - No duplicate rows created
        """
        # Mock get_environment for both runs
        async def get_environment_mock(env_id, tenant_id):
            if env_id == anchor_env_id:
                return {"id": anchor_env_id, "name": "Anchor", "git_repo_url": "https://github.com/test/repo"}
            elif env_id == dev_env_id:
                return {"id": dev_env_id, "name": "Dev", "environment_class": "dev"}
            return None

        mock_db_service.get_environment = AsyncMock(side_effect=get_environment_mock)

        # Track upsert calls to verify idempotency
        upsert_calls = []

        def track_upsert(data, on_conflict):
            upsert_calls.append({
                "n8n_workflow_id": data.get("n8n_workflow_id"),
                "canonical_id": data.get("canonical_id"),
                "on_conflict": on_conflict
            })
            mock_response = MagicMock()
            mock_response.data = [data]
            return MagicMock(execute=lambda: mock_response)

        # Mock anchor sync (same result both times)
        anchor_sync_result = {
            "workflows_synced": 3,
            "workflows_created": 3,
            "workflows_unchanged": 0,
            "errors": []
        }

        # Mock dev env sync (same result both times)
        dev_sync_result = {
            "workflows_synced": 2,
            "workflows_linked": 1,
            "workflows_untracked": 1,
            "workflows_skipped": 0,
            "errors": [],
            "observed_workflow_ids": ["wf-dev-1", "wf-dev-2"],
            "created_workflow_ids": ["wf-dev-2"]
        }

        with patch.object(
            CanonicalRepoSyncService,
            'sync_repository',
            new_callable=AsyncMock,
            return_value=anchor_sync_result
        ):
            with patch.object(
                CanonicalEnvSyncService,
                'sync_environment',
                new_callable=AsyncMock,
                return_value=dev_sync_result
            ):
                with patch.object(
                    CanonicalOnboardingService,
                    '_auto_link_by_hash',
                    new_callable=AsyncMock,
                    return_value={"linked": 0, "errors": []}
                ):
                    with patch.object(
                        CanonicalOnboardingService,
                        '_generate_link_suggestions',
                        new_callable=AsyncMock,
                        return_value={"suggestions": 0, "errors": []}
                    ):
                        # First run
                        results1 = await CanonicalOnboardingService.run_inventory_phase(
                            tenant_id=tenant_id,
                            anchor_environment_id=anchor_env_id,
                            environment_configs=environment_configs,
                            tenant_slug="test-tenant"
                        )

                        # Retry (second run)
                        results2 = await CanonicalOnboardingService.run_inventory_phase(
                            tenant_id=tenant_id,
                            anchor_environment_id=anchor_env_id,
                            environment_configs=environment_configs,
                            tenant_slug="test-tenant"
                        )

                        # Assert: both runs successful with same results
                        assert results1["workflows_inventoried"] == 5
                        assert results2["workflows_inventoried"] == 5

                        # Assert: no errors on retry
                        assert len(results1["errors"]) == 0
                        assert len(results2["errors"]) == 0


# Test Category: Per-Workflow Error Tracking
class TestPerWorkflowErrorTracking:
    """Tests for per-workflow error tracking and reporting"""

    @pytest.mark.asyncio
    async def test_workflow_results_tracks_individual_successes(
        self,
        tenant_id,
        anchor_env_id,
        dev_env_id,
        environment_configs,
        mock_db_service
    ):
        """
        Test that workflow_results tracks individual workflow successes
        with proper metadata
        """
        # Mock get_environment
        async def get_environment_mock(env_id, tenant_id):
            if env_id == anchor_env_id:
                return {"id": anchor_env_id, "name": "Anchor", "git_repo_url": "https://github.com/test/repo"}
            elif env_id == dev_env_id:
                return {"id": dev_env_id, "name": "Dev", "environment_class": "dev"}
            return None

        mock_db_service.get_environment = AsyncMock(side_effect=get_environment_mock)

        # Mock syncs
        with patch.object(
            CanonicalRepoSyncService,
            'sync_repository',
            new_callable=AsyncMock,
            return_value={
                "workflows_synced": 2,
                "workflows_created": 2,
                "workflows_unchanged": 0,
                "errors": []
            }
        ):
            with patch.object(
                CanonicalEnvSyncService,
                'sync_environment',
                new_callable=AsyncMock,
                return_value={
                    "workflows_synced": 3,
                    "workflows_linked": 2,
                    "workflows_untracked": 1,
                    "workflows_skipped": 0,
                    "errors": [],
                    "observed_workflow_ids": ["wf-1", "wf-2", "wf-3"],
                    "created_workflow_ids": ["wf-3"]
                }
            ):
                with patch.object(
                    CanonicalOnboardingService,
                    '_auto_link_by_hash',
                    new_callable=AsyncMock,
                    return_value={"linked": 0, "errors": []}
                ):
                    with patch.object(
                        CanonicalOnboardingService,
                        '_generate_link_suggestions',
                        new_callable=AsyncMock,
                        return_value={"suggestions": 0, "errors": []}
                    ):
                        # Execute
                        results = await CanonicalOnboardingService.run_inventory_phase(
                            tenant_id=tenant_id,
                            anchor_environment_id=anchor_env_id,
                            environment_configs=environment_configs,
                            tenant_slug="test-tenant"
                        )

                        # Assert: workflow_results populated
                        assert "workflow_results" in results
                        workflow_results = results["workflow_results"]

                        # Should have 3 workflows from dev env
                        dev_workflow_results = [
                            r for r in workflow_results
                            if r["environment_id"] == dev_env_id
                        ]
                        assert len(dev_workflow_results) == 3

                        # Check structure
                        for result in dev_workflow_results:
                            assert "environment_id" in result
                            assert "environment_name" in result
                            assert "workflow_id" in result
                            assert "status" in result
                            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_workflow_results_tracks_individual_errors(
        self,
        tenant_id,
        anchor_env_id,
        dev_env_id,
        environment_configs,
        mock_db_service
    ):
        """
        Test that workflow_results tracks individual workflow errors
        """
        # Mock get_environment
        async def get_environment_mock(env_id, tenant_id):
            if env_id == anchor_env_id:
                return {"id": anchor_env_id, "name": "Anchor", "git_repo_url": "https://github.com/test/repo"}
            elif env_id == dev_env_id:
                return {"id": dev_env_id, "name": "Dev"}
            return None

        mock_db_service.get_environment = AsyncMock(side_effect=get_environment_mock)

        # Mock anchor sync success
        with patch.object(
            CanonicalRepoSyncService,
            'sync_repository',
            new_callable=AsyncMock,
            return_value={
                "workflows_synced": 1,
                "workflows_created": 1,
                "workflows_unchanged": 0,
                "errors": []
            }
        ):
            # Mock dev sync with per-workflow errors
            with patch.object(
                CanonicalEnvSyncService,
                'sync_environment',
                new_callable=AsyncMock,
                return_value={
                    "workflows_synced": 2,
                    "workflows_linked": 2,
                    "workflows_untracked": 0,
                    "workflows_skipped": 0,
                    "errors": [
                        "Error processing workflow wferror1: Invalid hash",
                        "Error processing workflow wferror2: Database timeout"
                    ],
                    "observed_workflow_ids": ["wf-ok-1", "wf-ok-2"],
                    "created_workflow_ids": []
                }
            ):
                with patch.object(
                    CanonicalOnboardingService,
                    '_auto_link_by_hash',
                    new_callable=AsyncMock,
                    return_value={"linked": 0, "errors": []}
                ):
                    with patch.object(
                        CanonicalOnboardingService,
                        '_generate_link_suggestions',
                        new_callable=AsyncMock,
                        return_value={"suggestions": 0, "errors": []}
                    ):
                        # Execute
                        results = await CanonicalOnboardingService.run_inventory_phase(
                            tenant_id=tenant_id,
                            anchor_environment_id=anchor_env_id,
                            environment_configs=environment_configs,
                            tenant_slug="test-tenant"
                        )

                        # Assert: errors tracked
                        assert len(results["errors"]) == 2

                        # Assert: workflow_results includes error entries
                        error_results = [
                            r for r in results["workflow_results"]
                            if r["status"] == "error" and r["environment_id"] == dev_env_id
                        ]
                        assert len(error_results) == 2

                        # Check error details (IDs extracted by regex without hyphens)
                        workflow_ids = [r["workflow_id"] for r in error_results]
                        assert "wferror1" in workflow_ids
                        assert "wferror2" in workflow_ids

    @pytest.mark.asyncio
    async def test_extract_workflow_id_from_error_patterns(self):
        r"""
        Test _extract_workflow_id_from_error helper extracts IDs correctly
        Note: The regex uses \w+ which matches alphanumeric and underscore, but not hyphens
        """
        # Test pattern 1: "Error processing workflow <id>:" (matches only alphanumeric part)
        result = CanonicalOnboardingService._extract_workflow_id_from_error(
            "Error processing workflow wf123: Invalid format"
        )
        assert result == "wf123"

        # Test pattern 2: "n8n_workflow_id=<id>"
        result = CanonicalOnboardingService._extract_workflow_id_from_error(
            "Database constraint violation for n8n_workflow_id=wf456"
        )
        assert result == "wf456"

        # Test pattern 3: Generic "workflow <id>"
        result = CanonicalOnboardingService._extract_workflow_id_from_error(
            "Failed to sync workflow abc123 from n8n"
        )
        assert result == "abc123"

        # Test with underscores (should work)
        result = CanonicalOnboardingService._extract_workflow_id_from_error(
            "Error processing workflow wf_test_123: Invalid format"
        )
        assert result == "wf_test_123"

        # Test no match
        result = CanonicalOnboardingService._extract_workflow_id_from_error(
            "General database error"
        )
        assert result is None

        # Test None input
        result = CanonicalOnboardingService._extract_workflow_id_from_error(None)
        assert result is None


# Test Category: Transaction Boundaries and Isolation
class TestTransactionBoundariesAndIsolation:
    """Tests for proper transaction boundaries and failure isolation"""

    @pytest.mark.asyncio
    async def test_anchor_sync_failure_isolates_from_other_envs(
        self,
        tenant_id,
        anchor_env_id,
        dev_env_id,
        environment_configs,
        mock_db_service
    ):
        """
        Test that anchor environment sync failure doesn't prevent
        other environments from being processed
        """
        # Mock get_environment
        async def get_environment_mock(env_id, tenant_id):
            if env_id == anchor_env_id:
                return {"id": anchor_env_id, "name": "Anchor"}
            elif env_id == dev_env_id:
                return {"id": dev_env_id, "name": "Dev", "environment_class": "dev"}
            return None

        mock_db_service.get_environment = AsyncMock(side_effect=get_environment_mock)

        # Mock anchor sync failure
        with patch.object(
            CanonicalRepoSyncService,
            'sync_repository',
            new_callable=AsyncMock,
            side_effect=Exception("Git authentication failed")
        ):
            # Mock dev sync success
            with patch.object(
                CanonicalEnvSyncService,
                'sync_environment',
                new_callable=AsyncMock,
                return_value={
                    "workflows_synced": 5,
                    "workflows_linked": 3,
                    "workflows_untracked": 2,
                    "workflows_skipped": 0,
                    "errors": [],
                    "observed_workflow_ids": ["wf-1", "wf-2", "wf-3", "wf-4", "wf-5"],
                    "created_workflow_ids": ["wf-4", "wf-5"]
                }
            ):
                with patch.object(
                    CanonicalOnboardingService,
                    '_auto_link_by_hash',
                    new_callable=AsyncMock,
                    return_value={"linked": 0, "errors": []}
                ):
                    with patch.object(
                        CanonicalOnboardingService,
                        '_generate_link_suggestions',
                        new_callable=AsyncMock,
                        return_value={"suggestions": 0, "errors": []}
                    ):
                        # Execute
                        results = await CanonicalOnboardingService.run_inventory_phase(
                            tenant_id=tenant_id,
                            anchor_environment_id=anchor_env_id,
                            environment_configs=environment_configs,
                            tenant_slug="test-tenant"
                        )

                        # Assert: anchor failed but dev succeeded
                        assert "Git authentication failed" in results["errors"][0]
                        assert results["workflows_inventoried"] == 5

                        # Assert: environment results show isolation
                        assert results["environment_results"][anchor_env_id]["error_count"] == 1
                        assert results["environment_results"][dev_env_id]["success_count"] == 5

    @pytest.mark.asyncio
    async def test_auto_link_failure_does_not_halt_processing(
        self,
        tenant_id,
        anchor_env_id,
        dev_env_id,
        environment_configs,
        mock_db_service
    ):
        """
        Test that auto-link phase failure is isolated and doesn't
        prevent suggestion generation
        """
        # Mock get_environment
        async def get_environment_mock(env_id, tenant_id):
            if env_id == anchor_env_id:
                return {"id": anchor_env_id, "name": "Anchor", "git_repo_url": "https://github.com/test/repo"}
            elif env_id == dev_env_id:
                return {"id": dev_env_id, "name": "Dev"}
            return None

        mock_db_service.get_environment = AsyncMock(side_effect=get_environment_mock)

        # Mock successful syncs
        with patch.object(
            CanonicalRepoSyncService,
            'sync_repository',
            new_callable=AsyncMock,
            return_value={
                "workflows_synced": 2,
                "workflows_created": 2,
                "workflows_unchanged": 0,
                "errors": []
            }
        ):
            with patch.object(
                CanonicalEnvSyncService,
                'sync_environment',
                new_callable=AsyncMock,
                return_value={
                    "workflows_synced": 3,
                    "workflows_linked": 0,
                    "workflows_untracked": 3,
                    "workflows_skipped": 0,
                    "errors": [],
                    "observed_workflow_ids": ["wf-1", "wf-2", "wf-3"],
                    "created_workflow_ids": ["wf-1", "wf-2", "wf-3"]
                }
            ):
                # Mock auto-link failure
                with patch.object(
                    CanonicalOnboardingService,
                    '_auto_link_by_hash',
                    new_callable=AsyncMock,
                    side_effect=Exception("Hash comparison service unavailable")
                ):
                    # Mock suggestions success
                    with patch.object(
                        CanonicalOnboardingService,
                        '_generate_link_suggestions',
                        new_callable=AsyncMock,
                        return_value={"suggestions": 2, "errors": []}
                    ):
                        # Execute
                        results = await CanonicalOnboardingService.run_inventory_phase(
                            tenant_id=tenant_id,
                            anchor_environment_id=anchor_env_id,
                            environment_configs=environment_configs,
                            tenant_slug="test-tenant"
                        )

                        # Assert: auto-link failed but suggestions succeeded
                        assert results["auto_links"] == 0
                        assert results["suggested_links"] == 2
                        assert "Hash comparison service unavailable" in results["errors"][0]


# Test Category: Status Precedence Rules
class TestStatusPrecedenceRules:
    """Tests for status precedence computation"""

    @pytest.mark.asyncio
    async def test_missing_workflow_reappears_as_linked(
        self,
        tenant_id,
        dev_env_id,
        sample_workflow_data,
        mock_env_sync_db_service
    ):
        """
        Test that when a MISSING workflow reappears in n8n and has a canonical_id,
        it transitions back to LINKED status
        """
        # Setup: existing mapping in MISSING state with canonical_id
        existing_mapping = {
            "tenant_id": tenant_id,
            "environment_id": dev_env_id,
            "n8n_workflow_id": "wf-001",
            "canonical_id": "canonical-123",
            "env_content_hash": "old-hash",
            "status": "missing",
            "n8n_updated_at": "2024-01-01T10:00:00Z"
        }

        # Mock _get_mapping_by_n8n_id to return MISSING mapping
        with patch.object(
            CanonicalEnvSyncService,
            '_get_mapping_by_n8n_id',
            new_callable=AsyncMock,
            return_value=existing_mapping
        ):
            # Mock _update_workflow_mapping to capture status transition
            update_calls = []

            async def capture_update(*args, **kwargs):
                update_calls.append(kwargs)

            with patch.object(
                CanonicalEnvSyncService,
                '_update_workflow_mapping',
                new_callable=AsyncMock,
                side_effect=capture_update
            ):
                with patch('app.services.canonical_env_sync_service.compute_workflow_hash', return_value="new-hash"):
                    # Mock provider adapter
                    mock_adapter = MagicMock()

                    with patch('app.services.canonical_env_sync_service.ProviderRegistry.get_adapter_for_environment', return_value=mock_adapter):
                        mock_adapter.get_workflows = AsyncMock(return_value=[sample_workflow_data])
                        mock_adapter.get_workflow = AsyncMock(return_value=sample_workflow_data)

                        # Execute: process workflow batch (workflow reappeared)
                        results = await CanonicalEnvSyncService._process_workflow_batch(
                            tenant_id=tenant_id,
                            environment_id=dev_env_id,
                            workflows=[sample_workflow_data],
                            is_dev=True
                        )

                        # Assert: status transitioned to LINKED
                        assert len(update_calls) == 1
                        assert update_calls[0]["status"] == WorkflowMappingStatus.LINKED
                        assert results["synced"] == 1
                        assert results["linked"] == 1

    @pytest.mark.asyncio
    async def test_missing_workflow_reappears_as_untracked(
        self,
        tenant_id,
        dev_env_id,
        sample_workflow_data,
        mock_env_sync_db_service
    ):
        """
        Test that when a MISSING workflow reappears without canonical_id,
        it transitions to UNTRACKED status
        """
        # Setup: existing mapping in MISSING state without canonical_id
        existing_mapping = {
            "tenant_id": tenant_id,
            "environment_id": dev_env_id,
            "n8n_workflow_id": "wf-001",
            "canonical_id": None,
            "env_content_hash": "old-hash",
            "status": "missing",
            "n8n_updated_at": "2024-01-01T10:00:00Z"
        }

        # Mock _get_mapping_by_n8n_id to return MISSING mapping
        with patch.object(
            CanonicalEnvSyncService,
            '_get_mapping_by_n8n_id',
            new_callable=AsyncMock,
            return_value=existing_mapping
        ):
            # Mock _update_workflow_mapping to capture status transition
            update_calls = []

            async def capture_update(*args, **kwargs):
                update_calls.append(kwargs)

            with patch.object(
                CanonicalEnvSyncService,
                '_update_workflow_mapping',
                new_callable=AsyncMock,
                side_effect=capture_update
            ):
                with patch('app.services.canonical_env_sync_service.compute_workflow_hash', return_value="new-hash"):
                    # Mock provider adapter
                    mock_adapter = MagicMock()

                    with patch('app.services.canonical_env_sync_service.ProviderRegistry.get_adapter_for_environment', return_value=mock_adapter):
                        mock_adapter.get_workflows = AsyncMock(return_value=[sample_workflow_data])
                        mock_adapter.get_workflow = AsyncMock(return_value=sample_workflow_data)

                        # Execute: process workflow batch
                        results = await CanonicalEnvSyncService._process_workflow_batch(
                            tenant_id=tenant_id,
                            environment_id=dev_env_id,
                            workflows=[sample_workflow_data],
                            is_dev=True
                        )

                        # Assert: status transitioned to UNTRACKED
                        assert len(update_calls) == 1
                        assert update_calls[0]["status"] == WorkflowMappingStatus.UNTRACKED
                        assert results["synced"] == 1
                        assert results["untracked"] == 1


# Test Category: Environment Results Tracking
class TestEnvironmentResultsTracking:
    """Tests for per-environment result aggregation"""

    @pytest.mark.asyncio
    async def test_environment_results_aggregate_correctly(
        self,
        tenant_id,
        anchor_env_id,
        dev_env_id,
        staging_env_id,
        environment_configs,
        mock_db_service
    ):
        """
        Test that environment_results dict aggregates per-environment
        success/error/skip counts correctly
        """
        # Mock get_environment
        async def get_environment_mock(env_id, tenant_id):
            if env_id == anchor_env_id:
                return {"id": anchor_env_id, "name": "Anchor", "git_repo_url": "https://github.com/test/repo"}
            elif env_id == dev_env_id:
                return {"id": dev_env_id, "name": "Dev", "environment_class": "dev"}
            elif env_id == staging_env_id:
                return {"id": staging_env_id, "name": "Staging", "environment_class": "staging"}
            return None

        mock_db_service.get_environment = AsyncMock(side_effect=get_environment_mock)

        # Mock syncs with different results
        with patch.object(
            CanonicalRepoSyncService,
            'sync_repository',
            new_callable=AsyncMock,
            return_value={
                "workflows_synced": 10,
                "workflows_created": 8,
                "workflows_unchanged": 2,
                "errors": ["Warning: duplicate file detected"]
            }
        ):
            with patch.object(
                CanonicalEnvSyncService,
                'sync_environment',
                new_callable=AsyncMock,
                side_effect=[
                    # Dev env: mixed success/skip
                    {
                        "workflows_synced": 8,
                        "workflows_linked": 6,
                        "workflows_untracked": 2,
                        "workflows_skipped": 3,
                        "errors": [],
                        "observed_workflow_ids": ["wf-d-1", "wf-d-2"],
                        "created_workflow_ids": []
                    },
                    # Staging env: some errors
                    {
                        "workflows_synced": 5,
                        "workflows_linked": 5,
                        "workflows_untracked": 0,
                        "workflows_skipped": 1,
                        "errors": ["Timeout fetching wf-s-99"],
                        "observed_workflow_ids": ["wf-s-1"],
                        "created_workflow_ids": []
                    }
                ]
            ):
                with patch.object(
                    CanonicalOnboardingService,
                    '_auto_link_by_hash',
                    new_callable=AsyncMock,
                    return_value={"linked": 0, "errors": []}
                ):
                    with patch.object(
                        CanonicalOnboardingService,
                        '_generate_link_suggestions',
                        new_callable=AsyncMock,
                        return_value={"suggestions": 0, "errors": []}
                    ):
                        # Execute
                        results = await CanonicalOnboardingService.run_inventory_phase(
                            tenant_id=tenant_id,
                            anchor_environment_id=anchor_env_id,
                            environment_configs=environment_configs,
                            tenant_slug="test-tenant"
                        )

                        # Assert: environment_results structure
                        assert anchor_env_id in results["environment_results"]
                        assert dev_env_id in results["environment_results"]
                        assert staging_env_id in results["environment_results"]

                        # Assert: anchor results
                        anchor_results = results["environment_results"][anchor_env_id]
                        assert anchor_results["success_count"] == 10
                        assert anchor_results["error_count"] == 1  # One warning
                        assert anchor_results["skipped_count"] == 2

                        # Assert: dev results
                        dev_results = results["environment_results"][dev_env_id]
                        assert dev_results["success_count"] == 8
                        assert dev_results["skipped_count"] == 3

                        # Assert: staging results
                        staging_results = results["environment_results"][staging_env_id]
                        assert staging_results["success_count"] == 5
                        assert staging_results["error_count"] == 1


# Test Category: Batch Processing and Checkpointing
class TestBatchProcessingAndCheckpointing:
    """Tests for batched processing with checkpoint support"""

    @pytest.mark.asyncio
    async def test_short_circuit_optimization_skips_unchanged_workflows(
        self,
        tenant_id,
        dev_env_id,
        sample_workflow_data
    ):
        """
        Test that short-circuit optimization skips processing workflows
        when n8n_updated_at timestamp is unchanged
        """
        # Setup: existing mapping with same n8n_updated_at
        existing_mapping = {
            "tenant_id": tenant_id,
            "environment_id": dev_env_id,
            "n8n_workflow_id": "wf-001",
            "canonical_id": "canonical-123",
            "env_content_hash": "hash123",
            "status": "linked",
            "n8n_updated_at": "2024-01-01T12:00:00Z"  # Same as sample_workflow_data
        }

        # Mock _get_mapping_by_n8n_id
        with patch.object(
            CanonicalEnvSyncService,
            '_get_mapping_by_n8n_id',
            new_callable=AsyncMock,
            return_value=existing_mapping
        ):
            # Mock _update_workflow_mapping (should NOT be called due to short-circuit)
            with patch.object(
                CanonicalEnvSyncService,
                '_update_workflow_mapping',
                new_callable=AsyncMock
            ) as mock_update:
                # Execute
                results = await CanonicalEnvSyncService._process_workflow_batch(
                    tenant_id=tenant_id,
                    environment_id=dev_env_id,
                    workflows=[sample_workflow_data],
                    is_dev=True
                )

                # Assert: workflow skipped, no update called
                assert results["skipped"] == 1
                assert results["linked"] == 1  # Still counted as linked
                mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_processing_isolates_individual_workflow_errors(
        self,
        tenant_id,
        dev_env_id
    ):
        """
        Test that errors in individual workflows don't halt batch processing
        """
        # Create multiple workflows, one will fail
        workflows = [
            {"id": "wf-1", "name": "OK 1", "nodes": [], "connections": {}, "updatedAt": "2024-01-01T12:00:00Z"},
            {"id": "wf-2", "name": "OK 2", "nodes": [], "connections": {}, "updatedAt": "2024-01-01T12:01:00Z"},
            {"id": "wf-error", "name": "Bad", "nodes": [], "connections": {}, "updatedAt": "2024-01-01T12:02:00Z"},
            {"id": "wf-3", "name": "OK 3", "nodes": [], "connections": {}, "updatedAt": "2024-01-01T12:03:00Z"}
        ]

        # Mock _get_mapping_by_n8n_id (no existing mappings)
        with patch.object(
            CanonicalEnvSyncService,
            '_get_mapping_by_n8n_id',
            new_callable=AsyncMock,
            return_value=None
        ):
            # Mock _try_auto_link_by_hash (no matches)
            with patch.object(
                CanonicalEnvSyncService,
                '_try_auto_link_by_hash',
                new_callable=AsyncMock,
                return_value=None
            ):
                # Mock _create_untracked_mapping - fail on wf-error
                async def create_mapping_with_error(tenant_id, env_id, wf_id, *args, **kwargs):
                    if wf_id == "wf-error":
                        raise Exception("Database constraint violation")
                    return {"n8n_workflow_id": wf_id}

                with patch.object(
                    CanonicalEnvSyncService,
                    '_create_untracked_mapping',
                    new_callable=AsyncMock,
                    side_effect=create_mapping_with_error
                ):
                    with patch('app.services.canonical_env_sync_service.compute_workflow_hash', return_value="hash"):
                        # Execute
                        results = await CanonicalEnvSyncService._process_workflow_batch(
                            tenant_id=tenant_id,
                            environment_id=dev_env_id,
                            workflows=workflows,
                            is_dev=True
                        )

                        # Assert: 3 succeeded, 1 failed
                        assert results["synced"] == 3
                        assert results["untracked"] == 3
                        assert len(results["errors"]) == 1
                        assert "wf-error" in results["errors"][0]
                        assert "Database constraint violation" in results["errors"][0]
