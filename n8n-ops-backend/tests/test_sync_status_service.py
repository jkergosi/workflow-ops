"""
Unit tests for the sync status service - workflow sync status computation.

NOTE: The sync_status_service now uses normalize_workflow_for_comparison
from promotion_service.py for consistent normalization across the sync pipeline.
Tests for normalization behavior are in test_promotion_service.py.
"""
import pytest
import json
from datetime import datetime, timezone, timedelta

from app.services.sync_status_service import (
    SyncStatus,
    compute_sync_status,
)
from app.services.promotion_service import normalize_workflow_for_comparison


class TestSyncStatusEnum:
    """Tests for SyncStatus enum."""

    @pytest.mark.unit
    def test_enum_values(self):
        """Should have expected enum values."""
        assert SyncStatus.IN_SYNC.value == "in_sync"
        assert SyncStatus.LOCAL_CHANGES.value == "local_changes"
        assert SyncStatus.UPDATE_AVAILABLE.value == "update_available"
        assert SyncStatus.CONFLICT.value == "conflict"


class TestNormalizeWorkflowForComparison:
    """Tests for normalize_workflow_for_comparison used by sync status service.

    NOTE: This function is defined in promotion_service.py but is the canonical
    normalization function used across the sync pipeline. These tests verify
    the behavior relevant to sync status computation.
    """

    @pytest.mark.unit
    def test_removes_id_field(self):
        """Should remove id field from workflow."""
        workflow = {"id": "wf-1", "name": "Test", "nodes": []}
        result = normalize_workflow_for_comparison(workflow)
        assert "id" not in result
        assert result["name"] == "Test"

    @pytest.mark.unit
    def test_removes_timestamp_fields(self):
        """Should remove timestamp fields."""
        workflow = {
            "name": "Test",
            "updatedAt": "2024-01-15T10:00:00Z",
            "createdAt": "2024-01-01T10:00:00Z",
            "nodes": []
        }
        result = normalize_workflow_for_comparison(workflow)
        assert "updatedAt" not in result
        assert "createdAt" not in result

    @pytest.mark.unit
    def test_removes_version_id(self):
        """Should remove versionId field."""
        workflow = {"name": "Test", "versionId": "v123", "nodes": []}
        result = normalize_workflow_for_comparison(workflow)
        assert "versionId" not in result

    @pytest.mark.unit
    def test_removes_node_position_fields(self):
        """Should remove position fields from nodes."""
        workflow = {
            "name": "Test",
            "nodes": [
                {
                    "id": "1",
                    "name": "Node",
                    "type": "n8n-nodes-base.set",
                    "position": [100, 200],
                    "positionAbsolute": [100, 200],
                    "selected": True
                }
            ]
        }
        result = normalize_workflow_for_comparison(workflow)
        # Nodes are sorted by name, so we can access by index
        node = result["nodes"][0]
        assert "position" not in node
        assert "positionAbsolute" not in node
        assert "selected" not in node

    @pytest.mark.unit
    def test_preserves_functional_fields(self):
        """Should preserve fields that affect functionality."""
        workflow = {
            "name": "Test Workflow",
            "nodes": [
                {
                    "id": "1",
                    "name": "Set",
                    "type": "n8n-nodes-base.set",
                    "parameters": {"values": {"key": "value"}}
                }
            ],
            "connections": {"1": {"main": []}}
        }
        result = normalize_workflow_for_comparison(workflow)
        assert result["name"] == "Test Workflow"
        assert result["nodes"][0]["parameters"] == {"values": {"key": "value"}}
        assert result["connections"] == {"1": {"main": []}}

    @pytest.mark.unit
    def test_does_not_modify_original(self):
        """Should not modify the original workflow object."""
        workflow = {"id": "wf-1", "name": "Test", "nodes": []}
        normalize_workflow_for_comparison(workflow)
        assert "id" in workflow  # Original should still have id


class TestComputeSyncStatus:
    """Tests for compute_sync_status function."""

    @pytest.mark.unit
    def test_local_changes_when_github_is_none(self):
        """Should return local_changes when workflow not in GitHub."""
        n8n_workflow = {"name": "Test", "nodes": []}
        result = compute_sync_status(n8n_workflow, github_workflow=None)
        assert result == SyncStatus.LOCAL_CHANGES.value

    @pytest.mark.unit
    def test_local_changes_when_synced_but_github_deleted(self):
        """Should return local_changes when workflow was synced but now missing in GitHub."""
        n8n_workflow = {"name": "Test", "nodes": []}
        result = compute_sync_status(
            n8n_workflow,
            github_workflow=None,
            last_synced_at="2024-01-15T10:00:00Z"
        )
        assert result == SyncStatus.LOCAL_CHANGES.value

    @pytest.mark.unit
    def test_in_sync_when_identical(self):
        """Should return in_sync when workflows are identical."""
        workflow = {
            "name": "Test",
            "nodes": [{"name": "Set", "type": "n8n-nodes-base.set", "parameters": {}}],
            "connections": {}
        }
        result = compute_sync_status(workflow, workflow)
        assert result == SyncStatus.IN_SYNC.value

    @pytest.mark.unit
    def test_in_sync_ignores_metadata_differences(self):
        """Should return in_sync when only metadata differs."""
        n8n_workflow = {
            "id": "n8n-id-1",
            "name": "Test",
            "nodes": [],
            "updatedAt": "2024-01-20T10:00:00Z"
        }
        github_workflow = {
            "id": "github-id-2",
            "name": "Test",
            "nodes": [],
            "updatedAt": "2024-01-15T10:00:00Z"
        }
        result = compute_sync_status(n8n_workflow, github_workflow)
        assert result == SyncStatus.IN_SYNC.value

    @pytest.mark.unit
    def test_in_sync_ignores_position_differences(self):
        """Should return in_sync when only node positions differ."""
        n8n_workflow = {
            "name": "Test",
            "nodes": [
                {"name": "Set", "type": "n8n-nodes-base.set", "position": [100, 100]}
            ]
        }
        github_workflow = {
            "name": "Test",
            "nodes": [
                {"name": "Set", "type": "n8n-nodes-base.set", "position": [200, 200]}
            ]
        }
        result = compute_sync_status(n8n_workflow, github_workflow)
        assert result == SyncStatus.IN_SYNC.value

    @pytest.mark.unit
    def test_local_changes_when_n8n_modified_after_sync(self):
        """Should return local_changes when N8N was modified after last sync."""
        n8n_workflow = {"name": "Modified Name", "nodes": []}
        github_workflow = {"name": "Original Name", "nodes": []}

        # N8N modified after sync, GitHub not modified
        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            last_synced_at="2024-01-10T10:00:00Z",
            n8n_updated_at="2024-01-15T10:00:00Z",
            github_updated_at="2024-01-05T10:00:00Z"
        )
        assert result == SyncStatus.LOCAL_CHANGES.value

    @pytest.mark.unit
    def test_update_available_when_github_modified_after_sync(self):
        """Should return update_available when GitHub was modified after last sync."""
        n8n_workflow = {"name": "Original Name", "nodes": []}
        github_workflow = {"name": "Updated Name", "nodes": []}

        # GitHub modified after sync, N8N not modified
        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            last_synced_at="2024-01-10T10:00:00Z",
            n8n_updated_at="2024-01-05T10:00:00Z",
            github_updated_at="2024-01-15T10:00:00Z"
        )
        assert result == SyncStatus.UPDATE_AVAILABLE.value

    @pytest.mark.unit
    def test_conflict_when_both_modified_after_sync(self):
        """Should return conflict when both N8N and GitHub modified after sync."""
        n8n_workflow = {"name": "N8N Changes", "nodes": []}
        github_workflow = {"name": "GitHub Changes", "nodes": []}

        # Both modified after sync
        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            last_synced_at="2024-01-10T10:00:00Z",
            n8n_updated_at="2024-01-15T10:00:00Z",
            github_updated_at="2024-01-15T12:00:00Z"
        )
        assert result == SyncStatus.CONFLICT.value

    @pytest.mark.unit
    def test_update_available_when_github_slightly_newer(self):
        """Should return update_available when GitHub is slightly newer."""
        n8n_workflow = {"name": "N8N", "nodes": []}
        github_workflow = {"name": "GitHub", "nodes": []}

        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            n8n_updated_at="2024-01-15T10:00:30Z",
            github_updated_at="2024-01-15T10:00:45Z"  # GitHub is more recent
        )
        # When GitHub is newer, it's an update available
        assert result == SyncStatus.UPDATE_AVAILABLE.value

    @pytest.mark.unit
    def test_local_changes_when_n8n_more_recent(self):
        """Should return local_changes when N8N is more recent (no last_synced_at)."""
        n8n_workflow = {"name": "N8N", "nodes": []}
        github_workflow = {"name": "GitHub", "nodes": []}

        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            n8n_updated_at="2024-01-20T10:00:00Z",
            github_updated_at="2024-01-15T10:00:00Z"
        )
        assert result == SyncStatus.LOCAL_CHANGES.value

    @pytest.mark.unit
    def test_update_available_when_github_more_recent(self):
        """Should return update_available when GitHub is more recent (no last_synced_at)."""
        n8n_workflow = {"name": "N8N", "nodes": []}
        github_workflow = {"name": "GitHub", "nodes": []}

        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            n8n_updated_at="2024-01-10T10:00:00Z",
            github_updated_at="2024-01-20T10:00:00Z"
        )
        assert result == SyncStatus.UPDATE_AVAILABLE.value

    @pytest.mark.unit
    def test_defaults_to_local_changes_without_timestamps(self):
        """Should default to local_changes when workflows differ and no timestamps.

        The implementation treats N8N as the authoritative source when we can't
        determine sync status from timestamps, so it returns local_changes.
        """
        n8n_workflow = {"name": "N8N Version", "nodes": []}
        github_workflow = {"name": "GitHub Version", "nodes": []}

        result = compute_sync_status(n8n_workflow, github_workflow)
        assert result == SyncStatus.LOCAL_CHANGES.value

    @pytest.mark.unit
    def test_handles_invalid_timestamp_format(self):
        """Should handle invalid timestamp formats gracefully."""
        n8n_workflow = {"name": "N8N", "nodes": []}
        github_workflow = {"name": "GitHub", "nodes": []}

        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            last_synced_at="invalid-date",
            n8n_updated_at="also-invalid",
            github_updated_at="nope"
        )
        # Falls through to local_changes (N8N as authoritative source)
        assert result == SyncStatus.LOCAL_CHANGES.value

    @pytest.mark.unit
    def test_handles_none_timestamps(self):
        """Should handle None timestamps."""
        n8n_workflow = {"name": "N8N", "nodes": []}
        github_workflow = {"name": "GitHub", "nodes": []}

        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            last_synced_at=None,
            n8n_updated_at=None,
            github_updated_at=None
        )
        # With no timestamps, defaults to local_changes (N8N as authoritative)
        assert result == SyncStatus.LOCAL_CHANGES.value

    @pytest.mark.unit
    def test_detects_node_content_changes(self):
        """Should detect changes in node parameters."""
        n8n_workflow = {
            "name": "Test",
            "nodes": [{"name": "Set", "type": "n8n-nodes-base.set", "parameters": {"value": "new"}}]
        }
        github_workflow = {
            "name": "Test",
            "nodes": [{"name": "Set", "type": "n8n-nodes-base.set", "parameters": {"value": "old"}}]
        }

        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            n8n_updated_at="2024-01-20T10:00:00Z",
            github_updated_at="2024-01-10T10:00:00Z"
        )
        assert result == SyncStatus.LOCAL_CHANGES.value

    @pytest.mark.unit
    def test_detects_connection_changes(self):
        """Should detect changes in connections."""
        n8n_workflow = {
            "name": "Test",
            "nodes": [],
            "connections": {"Node1": {"main": [[{"node": "Node2"}]]}}
        }
        github_workflow = {
            "name": "Test",
            "nodes": [],
            "connections": {"Node1": {"main": [[{"node": "Node3"}]]}}
        }

        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            n8n_updated_at="2024-01-20T10:00:00Z",
            github_updated_at="2024-01-10T10:00:00Z"
        )
        assert result == SyncStatus.LOCAL_CHANGES.value

    @pytest.mark.unit
    def test_timezone_aware_timestamps(self):
        """Should handle timezone-aware timestamps."""
        n8n_workflow = {"name": "N8N", "nodes": []}
        github_workflow = {"name": "GitHub", "nodes": []}

        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            last_synced_at="2024-01-10T10:00:00+00:00",
            n8n_updated_at="2024-01-15T10:00:00+00:00",
            github_updated_at="2024-01-05T10:00:00+00:00"
        )
        assert result == SyncStatus.LOCAL_CHANGES.value


class TestSyncStatusEdgeCases:
    """Edge case tests for sync status computation."""

    @pytest.mark.unit
    def test_empty_workflows_are_in_sync(self):
        """Should consider empty workflows as in sync."""
        result = compute_sync_status({}, {})
        assert result == SyncStatus.IN_SYNC.value

    @pytest.mark.unit
    def test_workflows_with_only_metadata_in_sync(self):
        """Workflows with only differing metadata should be in sync."""
        n8n_workflow = {
            "id": "id-1",
            "versionId": "v1",
            "updatedAt": "2024-01-20T10:00:00Z",
            "createdAt": "2024-01-01T10:00:00Z"
        }
        github_workflow = {
            "id": "id-2",
            "versionId": "v2",
            "updatedAt": "2024-01-15T10:00:00Z",
            "createdAt": "2024-01-01T08:00:00Z"
        }
        result = compute_sync_status(n8n_workflow, github_workflow)
        assert result == SyncStatus.IN_SYNC.value

    @pytest.mark.unit
    def test_deep_nested_parameter_changes(self):
        """Should detect changes in deeply nested parameters."""
        n8n_workflow = {
            "name": "Test",
            "nodes": [{
                "name": "Code",
                "type": "n8n-nodes-base.code",
                "parameters": {
                    "code": {
                        "nested": {
                            "deep": {"value": "changed"}
                        }
                    }
                }
            }]
        }
        github_workflow = {
            "name": "Test",
            "nodes": [{
                "name": "Code",
                "type": "n8n-nodes-base.code",
                "parameters": {
                    "code": {
                        "nested": {
                            "deep": {"value": "original"}
                        }
                    }
                }
            }]
        }

        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            n8n_updated_at="2024-01-20T10:00:00Z",
            github_updated_at="2024-01-10T10:00:00Z"
        )
        assert result == SyncStatus.LOCAL_CHANGES.value

    @pytest.mark.unit
    def test_node_order_normalized(self):
        """Should normalize node order by sorting by name.

        The canonical normalize_workflow_for_comparison function sorts nodes
        by name for consistent comparison, so different node ordering should
        result in IN_SYNC status.
        """
        n8n_workflow = {
            "name": "Test",
            "nodes": [
                {"name": "A", "type": "a"},
                {"name": "B", "type": "b"}
            ]
        }
        github_workflow = {
            "name": "Test",
            "nodes": [
                {"name": "B", "type": "b"},
                {"name": "A", "type": "a"}
            ]
        }

        result = compute_sync_status(
            n8n_workflow,
            github_workflow,
            n8n_updated_at="2024-01-20T10:00:00Z",
            github_updated_at="2024-01-10T10:00:00Z"
        )
        # Node order is normalized by sorting, so these are considered in sync
        assert result == SyncStatus.IN_SYNC.value
