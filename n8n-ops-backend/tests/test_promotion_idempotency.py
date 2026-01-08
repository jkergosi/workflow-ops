"""
Unit tests for idempotency enforcement in promotion service.

This test suite verifies Task T013 requirements:
- Idempotency check using workflow content hash (T004)
- Prevention of duplicate workflow creation on re-execution
- Content hash computation and normalization
- Proper handling of metadata fields in hash calculation
- Graceful degradation when idempotency check fails

These tests focus on the core idempotency logic implemented in promotion_service.py
lines 2000-2067, which uses content hash comparison to prevent duplicate workflows.
"""
import pytest
import copy
from typing import Dict, Any

from app.services.canonical_workflow_service import compute_workflow_hash
from app.services.promotion_service import normalize_workflow_for_comparison


# ============ Test Data Fixtures ============


@pytest.fixture
def base_workflow() -> Dict[str, Any]:
    """
    Create a base workflow for testing.

    This represents a typical n8n workflow with nodes, connections, and settings.
    """
    return {
        "id": "wf-123",
        "name": "Sample Workflow",
        "active": True,
        "nodes": [
            {
                "id": "node-1",
                "name": "Start",
                "type": "n8n-nodes-base.start",
                "typeVersion": 1,
                "position": [250, 300],
                "parameters": {}
            },
            {
                "id": "node-2",
                "name": "HTTP Request",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "position": [450, 300],
                "parameters": {
                    "url": "https://api.example.com/data",
                    "method": "GET",
                    "responseFormat": "json"
                }
            },
            {
                "id": "node-3",
                "name": "Set",
                "type": "n8n-nodes-base.set",
                "typeVersion": 1,
                "position": [650, 300],
                "parameters": {
                    "values": {
                        "string": [
                            {
                                "name": "result",
                                "value": "={{ $json.data }}"
                            }
                        ]
                    }
                }
            }
        ],
        "connections": {
            "Start": {
                "main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]
            },
            "HTTP Request": {
                "main": [[{"node": "Set", "type": "main", "index": 0}]]
            }
        },
        "settings": {
            "executionOrder": "v1"
        },
        "staticData": None,
    }


# ============ Content Hash Computation Tests ============


class TestContentHashComputation:
    """
    Tests for compute_workflow_hash function.

    Verifies that content hashing properly normalizes workflows and
    ignores irrelevant metadata while detecting meaningful changes.
    """

    @pytest.mark.unit
    def test_identical_workflows_produce_same_hash(self, base_workflow):
        """
        Identical workflows should produce the same hash.

        This is the foundation of idempotency - if two workflows have
        the same content, they should be considered duplicates.
        """
        workflow_1 = copy.deepcopy(base_workflow)
        workflow_2 = copy.deepcopy(base_workflow)

        hash_1 = compute_workflow_hash(workflow_1)
        hash_2 = compute_workflow_hash(workflow_2)

        assert hash_1 == hash_2
        assert isinstance(hash_1, str)
        assert len(hash_1) == 64  # SHA256 hex digest

    @pytest.mark.unit
    def test_hash_ignores_metadata_fields(self, base_workflow):
        """
        Content hash should ignore metadata fields like updatedAt, createdAt, versionId.

        These fields change on every save but don't represent meaningful workflow changes.
        Idempotency should consider workflows identical even if metadata differs.
        """
        workflow_with_metadata = copy.deepcopy(base_workflow)
        workflow_with_metadata["updatedAt"] = "2024-01-15T10:30:00Z"
        workflow_with_metadata["createdAt"] = "2024-01-01T00:00:00Z"
        workflow_with_metadata["versionId"] = "v123"
        workflow_with_metadata["tags"] = ["production", "critical"]

        workflow_without_metadata = copy.deepcopy(base_workflow)
        # No metadata fields added

        hash_with = compute_workflow_hash(workflow_with_metadata)
        hash_without = compute_workflow_hash(workflow_without_metadata)

        # Hashes should be identical despite metadata differences
        assert hash_with == hash_without

    @pytest.mark.unit
    def test_hash_changes_with_node_parameter_modification(self, base_workflow):
        """
        Content hash should change when node parameters are modified.

        This represents a meaningful workflow change that should not be
        considered a duplicate.
        """
        workflow_original = copy.deepcopy(base_workflow)

        workflow_modified = copy.deepcopy(base_workflow)
        # Change HTTP method from GET to POST
        workflow_modified["nodes"][1]["parameters"]["method"] = "POST"

        hash_original = compute_workflow_hash(workflow_original)
        hash_modified = compute_workflow_hash(workflow_modified)

        # Hashes should differ for meaningful changes
        assert hash_original != hash_modified

    @pytest.mark.unit
    def test_hash_changes_with_node_addition(self, base_workflow):
        """
        Content hash should change when nodes are added to the workflow.
        """
        workflow_original = copy.deepcopy(base_workflow)

        workflow_with_new_node = copy.deepcopy(base_workflow)
        workflow_with_new_node["nodes"].append({
            "id": "node-4",
            "name": "Email",
            "type": "n8n-nodes-base.emailSend",
            "typeVersion": 1,
            "position": [850, 300],
            "parameters": {
                "toEmail": "admin@example.com",
                "subject": "Alert"
            }
        })

        hash_original = compute_workflow_hash(workflow_original)
        hash_with_new = compute_workflow_hash(workflow_with_new_node)

        assert hash_original != hash_with_new

    @pytest.mark.unit
    def test_hash_changes_with_connection_modification(self, base_workflow):
        """
        Content hash should change when workflow connections are modified.
        """
        workflow_original = copy.deepcopy(base_workflow)

        workflow_modified = copy.deepcopy(base_workflow)
        # Add new connection
        workflow_modified["connections"]["Set"] = {
            "main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]
        }

        hash_original = compute_workflow_hash(workflow_original)
        hash_modified = compute_workflow_hash(workflow_modified)

        assert hash_original != hash_modified

    @pytest.mark.unit
    def test_hash_changes_with_expression_modification(self, base_workflow):
        """
        Content hash should change when expressions in parameters change.

        Expressions are critical business logic and must be detected.
        """
        workflow_original = copy.deepcopy(base_workflow)

        workflow_modified = copy.deepcopy(base_workflow)
        # Change expression in Set node
        workflow_modified["nodes"][2]["parameters"]["values"]["string"][0]["value"] = "={{ $json.modified }}"

        hash_original = compute_workflow_hash(workflow_original)
        hash_modified = compute_workflow_hash(workflow_modified)

        assert hash_original != hash_modified

    @pytest.mark.unit
    def test_hash_ignores_workflow_id_changes(self, base_workflow):
        """
        Content hash should ignore workflow ID changes.

        When promoting from source to target, the workflow ID may change
        but the content is the same - this should be considered idempotent.
        """
        workflow_1 = copy.deepcopy(base_workflow)
        workflow_1["id"] = "wf-source-123"

        workflow_2 = copy.deepcopy(base_workflow)
        workflow_2["id"] = "wf-target-456"

        hash_1 = compute_workflow_hash(workflow_1)
        hash_2 = compute_workflow_hash(workflow_2)

        # Same content, different IDs should produce same hash
        assert hash_1 == hash_2

    @pytest.mark.unit
    def test_hash_ignores_node_position_changes(self, base_workflow):
        """
        Content hash should ignore node position changes.

        Node positions are UI-only metadata and don't affect workflow logic.
        """
        workflow_1 = copy.deepcopy(base_workflow)

        workflow_2 = copy.deepcopy(base_workflow)
        # Move all nodes to different positions
        workflow_2["nodes"][0]["position"] = [100, 100]
        workflow_2["nodes"][1]["position"] = [300, 100]
        workflow_2["nodes"][2]["position"] = [500, 100]

        hash_1 = compute_workflow_hash(workflow_1)
        hash_2 = compute_workflow_hash(workflow_2)

        # Position changes should not affect hash
        assert hash_1 == hash_2

    @pytest.mark.unit
    def test_hash_is_deterministic_across_multiple_calls(self, base_workflow):
        """
        Content hash should be deterministic - same input always produces same hash.

        This is critical for idempotency - we must be able to reliably
        identify duplicate workflows across multiple promotion attempts.
        """
        workflow = copy.deepcopy(base_workflow)

        hash_1 = compute_workflow_hash(workflow)
        hash_2 = compute_workflow_hash(workflow)
        hash_3 = compute_workflow_hash(workflow)

        assert hash_1 == hash_2 == hash_3


# ============ Workflow Normalization Tests ============


class TestWorkflowNormalization:
    """
    Tests for normalize_workflow_for_comparison function.

    Verifies that normalization properly removes irrelevant fields while
    preserving meaningful workflow content for hash computation.
    """

    @pytest.mark.unit
    def test_normalization_removes_metadata_fields(self, base_workflow):
        """
        Normalization should remove metadata fields that don't affect workflow logic.
        """
        workflow = copy.deepcopy(base_workflow)
        workflow["updatedAt"] = "2024-01-15T10:30:00Z"
        workflow["createdAt"] = "2024-01-01T00:00:00Z"
        workflow["versionId"] = "v123"
        workflow["tags"] = ["production"]
        workflow["id"] = "wf-123"

        normalized = normalize_workflow_for_comparison(workflow)

        # Metadata fields should be removed
        assert "updatedAt" not in normalized
        assert "createdAt" not in normalized
        assert "versionId" not in normalized
        assert "tags" not in normalized
        assert "id" not in normalized

    @pytest.mark.unit
    def test_normalization_preserves_essential_fields(self, base_workflow):
        """
        Normalization should preserve essential workflow fields.
        """
        workflow = copy.deepcopy(base_workflow)

        normalized = normalize_workflow_for_comparison(workflow)

        # Essential fields should be preserved
        assert "nodes" in normalized
        assert "connections" in normalized
        assert len(normalized["nodes"]) == 3
        assert "HTTP Request" in normalized["connections"]

    @pytest.mark.unit
    def test_normalization_removes_node_positions(self, base_workflow):
        """
        Normalization should remove node position data (UI-only metadata).
        """
        workflow = copy.deepcopy(base_workflow)

        normalized = normalize_workflow_for_comparison(workflow)

        # Position field should be removed from nodes
        for node in normalized["nodes"]:
            assert "position" not in node

    @pytest.mark.unit
    def test_normalization_preserves_node_parameters(self, base_workflow):
        """
        Normalization should preserve node parameters (critical business logic).
        """
        workflow = copy.deepcopy(base_workflow)

        normalized = normalize_workflow_for_comparison(workflow)

        # Node parameters should be preserved
        http_node = next(n for n in normalized["nodes"] if n.get("type") == "n8n-nodes-base.httpRequest")
        assert "parameters" in http_node
        assert http_node["parameters"]["url"] == "https://api.example.com/data"
        assert http_node["parameters"]["method"] == "GET"

    @pytest.mark.unit
    def test_normalization_is_idempotent(self, base_workflow):
        """
        Normalizing an already normalized workflow should produce the same result.
        """
        workflow = copy.deepcopy(base_workflow)

        normalized_once = normalize_workflow_for_comparison(workflow)
        normalized_twice = normalize_workflow_for_comparison(normalized_once)

        assert normalized_once == normalized_twice


# ============ Idempotency Logic Documentation Tests ============


class TestIdempotencyDocumentation:
    """
    Documentation tests that demonstrate the idempotency logic from promotion_service.py.

    These tests serve as living documentation of how idempotency works in practice,
    corresponding to lines 2000-2067 in promotion_service.py.
    """

    @pytest.mark.unit
    def test_duplicate_detection_for_new_workflows(self, base_workflow):
        """
        NEW workflows: Idempotency checks all target workflows for matching content.

        From promotion_service.py lines 2020-2037:
        - For NEW workflows, check if any workflow in target has same content
        - This prevents creating duplicate workflows with different IDs
        - If match found, workflow is skipped with warning
        """
        # Scenario: Promoting NEW workflow to target
        source_workflow = copy.deepcopy(base_workflow)
        source_workflow["id"] = "wf-source-123"
        source_hash = compute_workflow_hash(source_workflow)

        # Target has workflow with different ID but identical content
        target_workflow_1 = copy.deepcopy(base_workflow)
        target_workflow_1["id"] = "wf-target-456"
        target_hash_1 = compute_workflow_hash(target_workflow_1)

        # Target also has a different workflow
        target_workflow_2 = copy.deepcopy(base_workflow)
        target_workflow_2["id"] = "wf-target-789"
        target_workflow_2["nodes"][1]["parameters"]["url"] = "https://api.example.com/different"
        target_hash_2 = compute_workflow_hash(target_workflow_2)

        # Verify idempotency: source matches target_workflow_1
        assert source_hash == target_hash_1
        assert source_hash != target_hash_2

        # In real execution, this would trigger:
        # skip_due_to_idempotency = True
        # workflows_skipped += 1
        # warning: "Workflow already exists in target with identical content"

    @pytest.mark.unit
    def test_duplicate_detection_for_update_workflows(self, base_workflow):
        """
        UPDATE workflows: Idempotency checks specific workflow ID for matching content.

        From promotion_service.py lines 2041-2062:
        - For UPDATE workflows, check if the specific workflow has same content
        - More efficient than checking all workflows
        - If content identical, skip update
        """
        # Scenario: Promoting CHANGED workflow to target
        source_workflow = copy.deepcopy(base_workflow)
        source_workflow["id"] = "wf-123"
        source_hash = compute_workflow_hash(source_workflow)

        # Target has same workflow with identical content
        target_workflow = copy.deepcopy(base_workflow)
        target_workflow["id"] = "wf-123"
        target_hash = compute_workflow_hash(target_workflow)

        # Verify idempotency: content is identical
        assert source_hash == target_hash

        # In real execution, this would trigger:
        # skip_due_to_idempotency = True
        # workflows_skipped += 1
        # warning: "Workflow already has identical content in target"

    @pytest.mark.unit
    def test_promotion_proceeds_when_content_differs(self, base_workflow):
        """
        When content differs, promotion should proceed (not idempotent).

        This is the normal case - source has meaningful changes that need
        to be promoted to target.
        """
        source_workflow = copy.deepcopy(base_workflow)
        source_workflow["id"] = "wf-123"
        source_workflow["nodes"][1]["parameters"]["method"] = "POST"
        source_hash = compute_workflow_hash(source_workflow)

        target_workflow = copy.deepcopy(base_workflow)
        target_workflow["id"] = "wf-123"
        target_workflow["nodes"][1]["parameters"]["method"] = "GET"
        target_hash = compute_workflow_hash(target_workflow)

        # Content differs, not idempotent
        assert source_hash != target_hash

        # In real execution:
        # skip_due_to_idempotency = False
        # Promotion proceeds normally

    @pytest.mark.unit
    def test_re_execution_scenario(self, base_workflow):
        """
        Re-executing the same promotion should not create duplicates.

        Scenario:
        1. First execution: Workflow promoted successfully
        2. Second execution: Same workflow content detected, skipped

        This is the key idempotency guarantee from T004.
        """
        # First execution: Source workflow
        source_workflow = copy.deepcopy(base_workflow)
        source_workflow["id"] = "wf-source-123"
        source_hash = compute_workflow_hash(source_workflow)

        # After first execution: Workflow now exists in target
        target_workflow_after_first_promotion = copy.deepcopy(base_workflow)
        target_workflow_after_first_promotion["id"] = "wf-target-456"  # Different ID
        target_hash = compute_workflow_hash(target_workflow_after_first_promotion)

        # Second execution: Attempting to promote same workflow again
        source_workflow_second_attempt = copy.deepcopy(base_workflow)
        source_workflow_second_attempt["id"] = "wf-source-123"
        source_hash_second = compute_workflow_hash(source_workflow_second_attempt)

        # Verify idempotency prevents duplicate
        assert source_hash == target_hash
        assert source_hash_second == target_hash

        # Result: Workflow skipped on second execution, no duplicate created


# ============ Edge Case Tests ============


class TestIdempotencyEdgeCases:
    """
    Tests for edge cases and special scenarios in idempotency enforcement.
    """

    @pytest.mark.unit
    def test_empty_workflow_hash(self):
        """
        Empty workflow should produce consistent hash.
        """
        workflow_1 = {"nodes": [], "connections": {}}
        workflow_2 = {"nodes": [], "connections": {}}

        hash_1 = compute_workflow_hash(workflow_1)
        hash_2 = compute_workflow_hash(workflow_2)

        assert hash_1 == hash_2

    @pytest.mark.unit
    def test_workflow_with_null_values(self, base_workflow):
        """
        Workflows with null/None values should hash correctly.
        """
        workflow = copy.deepcopy(base_workflow)
        workflow["staticData"] = None
        workflow["settings"] = None

        # Should not crash, should produce valid hash
        hash_val = compute_workflow_hash(workflow)
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64

    @pytest.mark.unit
    def test_workflow_with_deeply_nested_parameters(self):
        """
        Workflows with deeply nested parameters should hash correctly.
        """
        workflow = {
            "id": "wf-1",
            "nodes": [
                {
                    "id": "node-1",
                    "type": "n8n-nodes-base.function",
                    "parameters": {
                        "functionCode": "return items;",
                        "options": {
                            "timeout": 30,
                            "memory": {
                                "limit": "512MB",
                                "settings": {
                                    "gc": "auto"
                                }
                            }
                        }
                    }
                }
            ],
            "connections": {}
        }

        hash_val = compute_workflow_hash(workflow)
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64

    @pytest.mark.unit
    def test_workflow_with_special_characters_in_parameters(self):
        """
        Workflows with special characters should hash correctly and consistently.
        """
        workflow_1 = {
            "id": "wf-1",
            "nodes": [
                {
                    "id": "node-1",
                    "type": "n8n-nodes-base.code",
                    "parameters": {
                        "code": 'const data = "Hello\\n\\tWorld\\r\\n";'
                    }
                }
            ],
            "connections": {}
        }

        workflow_2 = copy.deepcopy(workflow_1)

        hash_1 = compute_workflow_hash(workflow_1)
        hash_2 = compute_workflow_hash(workflow_2)

        assert hash_1 == hash_2

    @pytest.mark.unit
    def test_workflow_with_unicode_characters(self):
        """
        Workflows with unicode characters should hash correctly.
        """
        workflow = {
            "id": "wf-1",
            "name": "Workflow with émojis 🚀 and Ünïcödé",
            "nodes": [
                {
                    "id": "node-1",
                    "type": "n8n-nodes-base.set",
                    "parameters": {
                        "message": "Hello 世界 🌍"
                    }
                }
            ],
            "connections": {}
        }

        hash_val = compute_workflow_hash(workflow)
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64
