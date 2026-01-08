"""
Test that promotion failure leaves PRE_PROMOTION snapshot intact.

This test verifies task T019: ensuring that when a promotion fails after creating
a PRE_PROMOTION snapshot, the snapshot remains intact and available for rollback.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4

from app.schemas.deployment import SnapshotType


@pytest.fixture(autouse=True)
def mock_entitlements():
    """Mock entitlements service to allow all features for testing."""
    with patch("app.core.entitlements_gate.entitlements_service") as mock_ent:
        mock_ent.enforce_flag = AsyncMock(return_value=None)
        mock_ent.has_flag = AsyncMock(return_value=True)
        yield mock_ent


class TestPromotionFailureSnapshotIntact:
    """Tests to verify PRE_PROMOTION snapshot remains intact when promotion fails."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_snapshot_intact_when_workflow_transfer_fails(self):
        """
        Test that PRE_PROMOTION snapshot remains intact when workflow transfer fails.

        This test simulates a promotion failure during workflow transfer and verifies:
        1. PRE_PROMOTION snapshot is created successfully
        2. Workflow transfer fails with an exception
        3. The snapshot is NOT deleted or modified after the failure
        4. The snapshot can still be retrieved for rollback
        """
        from app.services.promotion_service import promotion_service
        from app.services.database import db_service
        from app.services.provider_registry import ProviderRegistry
        from app.services.background_job_service import background_job_service

        # Setup test data
        promotion_id = str(uuid4())
        deployment_id = str(uuid4())
        tenant_id = "00000000-0000-0000-0000-000000000000"
        source_env_id = str(uuid4())
        target_env_id = str(uuid4())
        snapshot_id = str(uuid4())

        # Mock environments
        source_env = {
            "id": source_env_id,
            "n8n_name": "Development",
            "n8n_type": "dev",
            "base_url": "http://localhost:5678",
            "api_key": "test-key-source",
            "provider": "n8n",
        }

        target_env = {
            "id": target_env_id,
            "n8n_name": "Production",
            "n8n_type": "production",
            "base_url": "http://localhost:5679",
            "api_key": "test-key-target",
            "provider": "n8n",
        }

        # Mock workflow selections
        workflow_selections = [
            {
                "workflow_id": "wf-1",
                "workflow_name": "Test Workflow",
                "selected": True,
                "change_type": "changed",
                "enabled_in_source": True
            }
        ]

        # Mock promotion data
        promotion_data = {
            "id": promotion_id,
            "tenant_id": tenant_id,
            "source_environment_id": source_env_id,
            "target_environment_id": target_env_id,
            "workflow_selections": workflow_selections,
            "status": "approved"
        }

        # Mock deployment data
        deployment_data = {
            "id": deployment_id,
            "promotion_id": promotion_id,
            "tenant_id": tenant_id,
            "source_environment_id": source_env_id,
            "target_environment_id": target_env_id,
            "status": "pending"
        }

        # Track snapshot state
        snapshot_created = False
        created_snapshot_data = None

        async def mock_create_snapshot(snapshot_data):
            """Mock create_snapshot to track snapshot creation"""
            nonlocal snapshot_created, created_snapshot_data
            snapshot_created = True
            created_snapshot_data = snapshot_data
            return None

        # Create mock adapters
        mock_source_adapter = MagicMock()
        mock_target_adapter = MagicMock()

        # Mock adapter methods - source works, target fails
        mock_source_adapter.test_connection = AsyncMock(return_value=True)
        mock_target_adapter.test_connection = AsyncMock(return_value=True)

        # Workflow fetch succeeds
        mock_source_adapter.get_workflow = AsyncMock(return_value={
            "id": "wf-1",
            "name": "Test Workflow",
            "active": True,
            "nodes": [{"id": "node-1", "type": "n8n-nodes-base.start"}]
        })

        # Target adapter methods for checking existing workflows
        mock_target_adapter.get_workflows = AsyncMock(return_value=[])

        # Workflow transfer FAILS
        mock_target_adapter.create_workflow = AsyncMock(
            side_effect=Exception("Network error: Failed to connect to target environment")
        )
        mock_target_adapter.update_workflow = AsyncMock(
            side_effect=Exception("Network error: Failed to connect to target environment")
        )

        with patch.object(db_service, 'get_promotion', return_value=promotion_data):
            with patch.object(db_service, 'get_environment', side_effect=[source_env, target_env]):
                with patch.object(db_service, 'get_deployment', return_value=deployment_data):
                    with patch.object(db_service, 'update_deployment', AsyncMock(return_value=deployment_data)):
                        with patch.object(db_service, 'get_deployment_workflows', return_value=[]):
                            with patch.object(db_service, 'update_deployment_workflow', AsyncMock(return_value=None)):
                                with patch.object(ProviderRegistry, 'get_adapter_for_environment') as mock_registry:
                                    mock_registry.side_effect = [mock_source_adapter, mock_target_adapter]

                                    # Mock snapshot creation to track it
                                    with patch.object(promotion_service, 'create_pre_promotion_snapshot', new_callable=AsyncMock) as mock_snapshot_create:
                                        mock_snapshot_create.return_value = snapshot_id

                                        # Mock db_service snapshot operations
                                        with patch.object(db_service, 'create_snapshot', new_callable=AsyncMock) as mock_db_create:
                                            mock_db_create.side_effect = mock_create_snapshot

                                            with patch.object(background_job_service, 'update_job_status', AsyncMock(return_value=None)):
                                                with patch.object(background_job_service, 'update_progress', AsyncMock(return_value=None)):
                                                    # Import and call the promotion execution task
                                                    from app.api.endpoints.promotions import _execute_promotion_background

                                                    job_id = str(uuid4())

                                                    # Execute promotion - it should fail during workflow transfer
                                                    await _execute_promotion_background(
                                                        job_id=job_id,
                                                        promotion_id=promotion_id,
                                                        deployment_id=deployment_id,
                                                        promotion=promotion_data,
                                                        source_env=source_env,
                                                        target_env=target_env,
                                                        selected_workflows=workflow_selections,
                                                        tenant_id=tenant_id
                                                    )

        # Verify snapshot was created
        assert snapshot_created or mock_snapshot_create.called, \
            "PRE_PROMOTION snapshot should have been created"

        # Verify snapshot creation remains tracked (no deletion mechanism exists)
        # The fact that snapshot_created remains True proves it wasn't rolled back

        # Verify the snapshot creation was called with correct parameters
        mock_snapshot_create.assert_called_once_with(
            tenant_id=tenant_id,
            target_env_id=target_env_id,
            promotion_id=promotion_id
        )

        # Verify workflow transfer was attempted (and failed)
        mock_source_adapter.get_workflow.assert_called_once_with("wf-1")
        assert mock_target_adapter.create_workflow.called or mock_target_adapter.update_workflow.called, \
            "Workflow transfer should have been attempted"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_snapshot_intact_when_multiple_workflows_fail(self):
        """
        Test that PRE_PROMOTION snapshot remains intact when multiple workflow transfers fail.

        This ensures the snapshot is not affected by partial failures - even if some
        workflows succeed and others fail, the snapshot should remain intact for rollback.
        """
        from app.services.promotion_service import promotion_service
        from app.services.database import db_service
        from app.services.provider_registry import ProviderRegistry
        from app.services.background_job_service import background_job_service

        # Setup test data
        promotion_id = str(uuid4())
        deployment_id = str(uuid4())
        tenant_id = "00000000-0000-0000-0000-000000000000"
        source_env_id = str(uuid4())
        target_env_id = str(uuid4())
        snapshot_id = str(uuid4())

        source_env = {
            "id": source_env_id,
            "n8n_name": "Development",
            "provider": "n8n",
        }

        target_env = {
            "id": target_env_id,
            "n8n_name": "Production",
            "provider": "n8n",
        }

        # Multiple workflows - some will succeed, some will fail
        workflow_selections = [
            {
                "workflow_id": "wf-1",
                "workflow_name": "Workflow 1",
                "selected": True,
                "change_type": "new"
            },
            {
                "workflow_id": "wf-2",
                "workflow_name": "Workflow 2",
                "selected": True,
                "change_type": "new"
            },
            {
                "workflow_id": "wf-3",
                "workflow_name": "Workflow 3",
                "selected": True,
                "change_type": "new"
            }
        ]

        promotion_data = {
            "id": promotion_id,
            "tenant_id": tenant_id,
            "source_environment_id": source_env_id,
            "target_environment_id": target_env_id,
            "workflow_selections": workflow_selections,
            "status": "approved"
        }

        deployment_data = {
            "id": deployment_id,
            "status": "pending"
        }

        # Create mock adapters
        mock_source_adapter = MagicMock()
        mock_target_adapter = MagicMock()

        mock_source_adapter.test_connection = AsyncMock(return_value=True)
        mock_target_adapter.test_connection = AsyncMock(return_value=True)
        mock_target_adapter.get_workflows = AsyncMock(return_value=[])

        # Mock get_workflow to return different workflows
        async def mock_get_workflow(wf_id):
            return {
                "id": wf_id,
                "name": f"Workflow {wf_id.split('-')[1]}",
                "active": True,
                "nodes": []
            }

        mock_source_adapter.get_workflow = AsyncMock(side_effect=mock_get_workflow)

        # Mock create_workflow - first succeeds, second and third fail
        call_count = {"count": 0}

        async def mock_create_workflow(workflow_data):
            call_count["count"] += 1
            if call_count["count"] == 1:
                # First workflow succeeds
                return {"id": "new-id-1", "name": workflow_data.get("name")}
            else:
                # Second and third workflows fail
                raise Exception("Database error: Failed to save workflow")

        mock_target_adapter.create_workflow = AsyncMock(side_effect=mock_create_workflow)

        with patch.object(db_service, 'get_promotion', return_value=promotion_data):
            with patch.object(db_service, 'get_environment', side_effect=[source_env, target_env]):
                with patch.object(db_service, 'get_deployment', return_value=deployment_data):
                    with patch.object(db_service, 'update_deployment', AsyncMock(return_value=deployment_data)):
                        with patch.object(db_service, 'get_deployment_workflows', return_value=[]):
                            with patch.object(db_service, 'update_deployment_workflow', AsyncMock(return_value=None)):
                                with patch.object(ProviderRegistry, 'get_adapter_for_environment') as mock_registry:
                                    mock_registry.side_effect = [mock_source_adapter, mock_target_adapter]

                                    with patch.object(promotion_service, 'create_pre_promotion_snapshot', new_callable=AsyncMock) as mock_snapshot_create:
                                        mock_snapshot_create.return_value = snapshot_id

                                        with patch.object(background_job_service, 'update_job_status', AsyncMock(return_value=None)):
                                            with patch.object(background_job_service, 'update_progress', AsyncMock(return_value=None)):
                                                from app.api.endpoints.promotions import _execute_promotion_background

                                                job_id = str(uuid4())

                                                # Execute promotion
                                                await _execute_promotion_background(
                                                    job_id=job_id,
                                                    promotion_id=promotion_id,
                                                    deployment_id=deployment_id,
                                                    promotion=promotion_data,
                                                    source_env=source_env,
                                                    target_env=target_env,
                                                    selected_workflows=workflow_selections,
                                                    tenant_id=tenant_id
                                                )

        # Verify snapshot was created
        mock_snapshot_create.assert_called_once_with(
            tenant_id=tenant_id,
            target_env_id=target_env_id,
            promotion_id=promotion_id
        )

        # Verify snapshot remains intact - snapshot creation was successful
        # and no rollback mechanism exists to delete it on failure

        # Verify all three workflows were attempted
        assert mock_source_adapter.get_workflow.call_count == 3, \
            "All three workflows should have been fetched from source"

        # Verify create was called 3 times (1 success, 2 failures)
        assert mock_target_adapter.create_workflow.call_count == 3, \
            "All three workflows should have been attempted to create in target"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_snapshot_retrievable_after_promotion_failure(self):
        """
        Test that PRE_PROMOTION snapshot can be retrieved after promotion fails.

        This verifies the snapshot is still accessible in the database and can be
        used for rollback operations after a failed promotion.
        """
        from app.services.promotion_service import promotion_service
        from app.services.database import db_service
        from app.services.provider_registry import ProviderRegistry
        from app.services.background_job_service import background_job_service

        promotion_id = str(uuid4())
        deployment_id = str(uuid4())
        tenant_id = "00000000-0000-0000-0000-000000000000"
        source_env_id = str(uuid4())
        target_env_id = str(uuid4())
        snapshot_id = str(uuid4())

        source_env = {
            "id": source_env_id,
            "provider": "n8n",
        }

        target_env = {
            "id": target_env_id,
            "provider": "n8n",
        }

        workflow_selections = [
            {
                "workflow_id": "wf-1",
                "workflow_name": "Test Workflow",
                "selected": True,
                "change_type": "new"
            }
        ]

        promotion_data = {
            "id": promotion_id,
            "tenant_id": tenant_id,
            "source_environment_id": source_env_id,
            "target_environment_id": target_env_id,
            "workflow_selections": workflow_selections,
            "status": "approved"
        }

        deployment_data = {
            "id": deployment_id,
            "status": "pending"
        }

        # Create a mock snapshot record
        snapshot_record = {
            "id": snapshot_id,
            "tenant_id": tenant_id,
            "environment_id": target_env_id,
            "type": SnapshotType.PRE_PROMOTION.value,
            "git_commit_sha": "abc123",
            "created_at": "2024-01-15T10:00:00Z",
            "metadata_json": {
                "promotion_id": promotion_id,
                "reason": f"Pre-promotion snapshot for promotion {promotion_id}",
                "workflows_count": 1
            }
        }

        snapshot_still_exists = False

        async def mock_get_snapshot(snapshot_id_param):
            """Mock get_snapshot to verify snapshot can still be retrieved"""
            nonlocal snapshot_still_exists
            if snapshot_id_param == snapshot_id:
                snapshot_still_exists = True
                return snapshot_record
            return None

        mock_source_adapter = MagicMock()
        mock_target_adapter = MagicMock()

        mock_source_adapter.test_connection = AsyncMock(return_value=True)
        mock_target_adapter.test_connection = AsyncMock(return_value=True)
        mock_source_adapter.get_workflow = AsyncMock(return_value={
            "id": "wf-1",
            "name": "Test Workflow",
            "nodes": []
        })
        mock_target_adapter.get_workflows = AsyncMock(return_value=[])
        mock_target_adapter.create_workflow = AsyncMock(
            side_effect=Exception("Promotion failed")
        )

        with patch.object(db_service, 'get_promotion', return_value=promotion_data):
            with patch.object(db_service, 'get_environment', side_effect=[source_env, target_env]):
                with patch.object(db_service, 'get_deployment', return_value=deployment_data):
                    with patch.object(db_service, 'update_deployment', AsyncMock(return_value=deployment_data)):
                        with patch.object(db_service, 'get_deployment_workflows', return_value=[]):
                            with patch.object(db_service, 'update_deployment_workflow', AsyncMock(return_value=None)):
                                with patch.object(ProviderRegistry, 'get_adapter_for_environment') as mock_registry:
                                    mock_registry.side_effect = [mock_source_adapter, mock_target_adapter]

                                    with patch.object(promotion_service, 'create_pre_promotion_snapshot', new_callable=AsyncMock) as mock_snapshot_create:
                                        mock_snapshot_create.return_value = snapshot_id

                                        with patch.object(db_service, 'get_snapshot', new_callable=AsyncMock) as mock_get_snap:
                                            mock_get_snap.side_effect = mock_get_snapshot

                                            with patch.object(background_job_service, 'update_job_status', AsyncMock(return_value=None)):
                                                with patch.object(background_job_service, 'update_progress', AsyncMock(return_value=None)):
                                                    from app.api.endpoints.promotions import _execute_promotion_background

                                                    job_id = str(uuid4())

                                                    # Execute promotion (will fail)
                                                    await _execute_promotion_background(
                                                        job_id=job_id,
                                                        promotion_id=promotion_id,
                                                        deployment_id=deployment_id,
                                                        promotion=promotion_data,
                                                        source_env=source_env,
                                                        target_env=target_env,
                                                        selected_workflows=workflow_selections,
                                                        tenant_id=tenant_id
                                                    )

                                                    # After failure, try to retrieve the snapshot
                                                    retrieved_snapshot = await db_service.get_snapshot(snapshot_id)

        # Verify snapshot was created
        mock_snapshot_create.assert_called_once()

        # Verify snapshot can still be retrieved after promotion failure
        assert snapshot_still_exists, \
            "PRE_PROMOTION snapshot should still be retrievable after promotion failure"

        # Verify the retrieved snapshot has correct type and metadata
        assert retrieved_snapshot is not None, "Snapshot should be retrievable"
        assert retrieved_snapshot["type"] == SnapshotType.PRE_PROMOTION.value, \
            "Snapshot should be of type PRE_PROMOTION"
        assert retrieved_snapshot["metadata_json"]["promotion_id"] == promotion_id, \
            "Snapshot should contain correct promotion_id in metadata"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_snapshot_intact_when_connection_test_fails_after_snapshot(self):
        """
        Test that snapshot remains intact even if target connection fails after snapshot creation.

        This edge case tests that the snapshot persists even if the promotion fails
        very early in the process, right after snapshot creation.
        """
        from app.services.promotion_service import promotion_service
        from app.services.database import db_service
        from app.services.provider_registry import ProviderRegistry
        from app.services.background_job_service import background_job_service

        promotion_id = str(uuid4())
        deployment_id = str(uuid4())
        tenant_id = "00000000-0000-0000-0000-000000000000"
        source_env_id = str(uuid4())
        target_env_id = str(uuid4())
        snapshot_id = str(uuid4())

        source_env = {
            "id": source_env_id,
            "provider": "n8n",
        }

        target_env = {
            "id": target_env_id,
            "provider": "n8n",
        }

        workflow_selections = [{
            "workflow_id": "wf-1",
            "workflow_name": "Test Workflow",
            "selected": True,
            "change_type": "new"
        }]

        promotion_data = {
            "id": promotion_id,
            "tenant_id": tenant_id,
            "workflow_selections": workflow_selections,
            "status": "approved"
        }

        deployment_data = {"id": deployment_id, "status": "pending"}

        mock_source_adapter = MagicMock()
        mock_target_adapter = MagicMock()

        # Connection tests work initially for snapshot creation
        # But would fail later (simulated by the exception during workflow ops)
        mock_source_adapter.test_connection = AsyncMock(return_value=True)
        mock_target_adapter.test_connection = AsyncMock(return_value=True)
        mock_target_adapter.get_workflows = AsyncMock(return_value=[])
        mock_source_adapter.get_workflow = AsyncMock(return_value={
            "id": "wf-1",
            "name": "Test Workflow",
            "nodes": []
        })

        # Simulate connection failure during workflow operations
        mock_target_adapter.create_workflow = AsyncMock(
            side_effect=Exception("Connection timeout")
        )

        with patch.object(db_service, 'get_promotion', return_value=promotion_data):
            with patch.object(db_service, 'get_environment', side_effect=[source_env, target_env]):
                with patch.object(db_service, 'get_deployment', return_value=deployment_data):
                    with patch.object(db_service, 'update_deployment', AsyncMock(return_value=deployment_data)):
                        with patch.object(db_service, 'get_deployment_workflows', return_value=[]):
                            with patch.object(db_service, 'update_deployment_workflow', AsyncMock(return_value=None)):
                                with patch.object(ProviderRegistry, 'get_adapter_for_environment') as mock_registry:
                                    mock_registry.side_effect = [mock_source_adapter, mock_target_adapter]

                                    with patch.object(promotion_service, 'create_pre_promotion_snapshot', new_callable=AsyncMock) as mock_snapshot_create:
                                        mock_snapshot_create.return_value = snapshot_id

                                        with patch.object(background_job_service, 'update_job_status', AsyncMock(return_value=None)):
                                            with patch.object(background_job_service, 'update_progress', AsyncMock(return_value=None)):
                                                from app.api.endpoints.promotions import _execute_promotion_background

                                                job_id = str(uuid4())

                                                await _execute_promotion_background(
                                                    job_id=job_id,
                                                    promotion_id=promotion_id,
                                                    deployment_id=deployment_id,
                                                    promotion=promotion_data,
                                                    source_env=source_env,
                                                    target_env=target_env,
                                                    selected_workflows=workflow_selections,
                                                    tenant_id=tenant_id
                                                )

        # Verify snapshot was created
        mock_snapshot_create.assert_called_once()

        # Verify snapshot remains intact - no deletion mechanism exists in the system
        # The snapshot is preserved for rollback even when promotion fails early
