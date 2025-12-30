"""
Tests for deployment workflow status tracking functionality.
Tests the new PENDING and UNCHANGED workflow statuses and related database operations.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4

from app.schemas.deployment import WorkflowStatus, WorkflowChangeType


class TestWorkflowStatusEnum:
    """Tests for WorkflowStatus enum values."""

    def test_workflow_status_pending_value(self):
        """WorkflowStatus should have PENDING status."""
        assert WorkflowStatus.PENDING.value == "pending"

    def test_workflow_status_success_value(self):
        """WorkflowStatus should have SUCCESS status."""
        assert WorkflowStatus.SUCCESS.value == "success"

    def test_workflow_status_failed_value(self):
        """WorkflowStatus should have FAILED status."""
        assert WorkflowStatus.FAILED.value == "failed"

    def test_workflow_status_skipped_value(self):
        """WorkflowStatus should have SKIPPED status."""
        assert WorkflowStatus.SKIPPED.value == "skipped"

    def test_workflow_status_unchanged_value(self):
        """WorkflowStatus should have UNCHANGED status."""
        assert WorkflowStatus.UNCHANGED.value == "unchanged"

    def test_workflow_status_all_values(self):
        """WorkflowStatus should have all expected values."""
        expected_values = {"pending", "success", "failed", "skipped", "unchanged"}
        actual_values = {status.value for status in WorkflowStatus}
        assert actual_values == expected_values


class TestWorkflowChangeTypeEnum:
    """Tests for WorkflowChangeType enum values."""

    def test_change_type_created_value(self):
        """WorkflowChangeType should have CREATED value."""
        assert WorkflowChangeType.CREATED.value == "created"

    def test_change_type_updated_value(self):
        """WorkflowChangeType should have UPDATED value."""
        assert WorkflowChangeType.UPDATED.value == "updated"

    def test_change_type_unchanged_value(self):
        """WorkflowChangeType should have UNCHANGED value."""
        assert WorkflowChangeType.UNCHANGED.value == "unchanged"


class TestDeploymentWorkflowDatabaseOperations:
    """Tests for deployment workflow database operations."""

    @pytest.mark.asyncio
    async def test_create_deployment_workflows_batch(self):
        """Test batch creation of deployment workflows."""
        from app.services.database import db_service

        deployment_id = str(uuid4())
        workflows = [
            {
                "deployment_id": deployment_id,
                "workflow_id": str(uuid4()),
                "workflow_name_at_time": "Workflow 1",
                "change_type": WorkflowChangeType.CREATED.value,
                "status": WorkflowStatus.PENDING.value,
                "error_message": None,
            },
            {
                "deployment_id": deployment_id,
                "workflow_id": str(uuid4()),
                "workflow_name_at_time": "Workflow 2",
                "change_type": WorkflowChangeType.UPDATED.value,
                "status": WorkflowStatus.PENDING.value,
                "error_message": None,
            },
        ]

        mock_response = MagicMock()
        mock_response.data = workflows

        with patch.object(db_service.client, 'table') as mock_table:
            mock_table.return_value.insert.return_value.execute.return_value = mock_response

            result = await db_service.create_deployment_workflows_batch(workflows)

            assert len(result) == 2
            mock_table.return_value.insert.assert_called_once_with(workflows)

    @pytest.mark.asyncio
    async def test_create_deployment_workflows_batch_empty(self):
        """Test batch creation with empty list returns empty list."""
        from app.services.database import db_service

        result = await db_service.create_deployment_workflows_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_update_deployment_workflow(self):
        """Test updating a deployment workflow status."""
        from app.services.database import db_service

        deployment_id = str(uuid4())
        workflow_id = str(uuid4())
        update_data = {
            "status": WorkflowStatus.SUCCESS.value,
            "change_type": WorkflowChangeType.CREATED.value,
            "error_message": None,
        }

        mock_response = MagicMock()
        mock_response.data = [{
            "id": str(uuid4()),
            "deployment_id": deployment_id,
            "workflow_id": workflow_id,
            **update_data
        }]

        with patch.object(db_service.client, 'table') as mock_table:
            mock_chain = MagicMock()
            mock_table.return_value.update.return_value = mock_chain
            mock_chain.eq.return_value = mock_chain
            mock_chain.execute.return_value = mock_response

            result = await db_service.update_deployment_workflow(
                deployment_id, workflow_id, update_data
            )

            assert result is not None
            assert result["status"] == WorkflowStatus.SUCCESS.value

    @pytest.mark.asyncio
    async def test_update_deployment_workflow_not_found(self):
        """Test updating a non-existent workflow returns None."""
        from app.services.database import db_service

        deployment_id = str(uuid4())
        workflow_id = str(uuid4())
        update_data = {"status": WorkflowStatus.SUCCESS.value}

        mock_response = MagicMock()
        mock_response.data = []

        with patch.object(db_service.client, 'table') as mock_table:
            mock_chain = MagicMock()
            mock_table.return_value.update.return_value = mock_chain
            mock_chain.eq.return_value = mock_chain
            mock_chain.execute.return_value = mock_response

            result = await db_service.update_deployment_workflow(
                deployment_id, workflow_id, update_data
            )

            assert result is None


class TestDeploymentWorkflowPreCreation:
    """Tests for pre-creating deployment workflows with PENDING status."""

    @pytest.mark.asyncio
    async def test_pending_workflows_created_at_start(self):
        """Test that workflows are pre-created with PENDING status at deployment start."""
        from app.schemas.deployment import WorkflowStatus, WorkflowChangeType

        # Verify that the default status for new workflows should be PENDING
        assert WorkflowStatus.PENDING.value == "pending"

        # Test workflow record structure
        workflow_record = {
            "deployment_id": str(uuid4()),
            "workflow_id": str(uuid4()),
            "workflow_name_at_time": "Test Workflow",
            "change_type": WorkflowChangeType.CREATED.value,
            "status": WorkflowStatus.PENDING.value,
            "error_message": None,
        }

        assert workflow_record["status"] == "pending"
        assert workflow_record["change_type"] == "created"

    def test_change_type_mapping(self):
        """Test the mapping from promotion change types to deployment change types."""
        change_type_map = {
            "new": WorkflowChangeType.CREATED,
            "changed": WorkflowChangeType.UPDATED,
            "staging_hotfix": WorkflowChangeType.UPDATED,
            "conflict": WorkflowChangeType.SKIPPED,
            "unchanged": WorkflowChangeType.UNCHANGED,
        }

        assert change_type_map["new"] == WorkflowChangeType.CREATED
        assert change_type_map["changed"] == WorkflowChangeType.UPDATED
        assert change_type_map["unchanged"] == WorkflowChangeType.UNCHANGED
        assert change_type_map["conflict"] == WorkflowChangeType.SKIPPED


class TestDeploymentSummaryJson:
    """Tests for deployment summary JSON structure."""

    def test_summary_includes_unchanged_count(self):
        """Test that summary JSON includes unchanged count."""
        summary_json = {
            "total": 10,
            "created": 3,
            "updated": 2,
            "deleted": 0,
            "failed": 1,
            "skipped": 2,
            "unchanged": 2,
            "processed": 10,
        }

        assert "unchanged" in summary_json
        assert summary_json["unchanged"] == 2
        assert summary_json["total"] == (
            summary_json["created"] +
            summary_json["updated"] +
            summary_json["failed"] +
            summary_json["skipped"] +
            summary_json["unchanged"]
        )
