"""
Unit tests for the diff service - workflow drift detection.
"""
import pytest
from app.services.diff_service import (
    normalize_value,
    compare_nodes,
    compare_node,
    compare_connections,
    compare_settings,
    compare_workflows,
    DriftDifference,
    DriftSummary,
    DriftResult,
    IGNORED_FIELDS,
    IGNORED_NODE_FIELDS,
)


class TestNormalizeValue:
    """Tests for normalize_value function."""

    @pytest.mark.unit
    def test_normalize_none_value(self):
        """None values should return None."""
        assert normalize_value(None) is None

    @pytest.mark.unit
    def test_normalize_primitive_values(self):
        """Primitive values should pass through unchanged."""
        assert normalize_value("string") == "string"
        assert normalize_value(123) == 123
        assert normalize_value(True) is True
        assert normalize_value(3.14) == 3.14

    @pytest.mark.unit
    def test_normalize_dict_removes_none_values(self):
        """Dicts should have None values removed."""
        input_dict = {"a": 1, "b": None, "c": "value"}
        result = normalize_value(input_dict)
        assert result == {"a": 1, "c": "value"}
        assert "b" not in result

    @pytest.mark.unit
    def test_normalize_nested_dict(self):
        """Nested dicts should be normalized recursively."""
        input_dict = {
            "level1": {
                "level2": {"value": 1, "empty": None},
                "empty": None,
            }
        }
        result = normalize_value(input_dict)
        assert result == {"level1": {"level2": {"value": 1}}}

    @pytest.mark.unit
    def test_normalize_list(self):
        """Lists should have elements normalized."""
        input_list = [1, None, {"a": 1, "b": None}, "string"]
        result = normalize_value(input_list)
        assert result == [1, None, {"a": 1}, "string"]

    @pytest.mark.unit
    def test_normalize_empty_structures(self):
        """Empty structures should return empty."""
        assert normalize_value({}) == {}
        assert normalize_value([]) == []


class TestCompareNode:
    """Tests for comparing individual nodes."""

    @pytest.mark.unit
    def test_identical_nodes_have_no_differences(self):
        """Identical nodes should produce no differences."""
        node = {
            "name": "Test Node",
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {"url": "https://api.example.com"},
            "position": [100, 200],
        }
        differences = compare_node("Test Node", node, node)
        assert differences == []

    @pytest.mark.unit
    def test_type_change_detected(self):
        """Node type changes should be detected."""
        git_node = {"name": "Test", "type": "n8n-nodes-base.httpRequest"}
        runtime_node = {"name": "Test", "type": "n8n-nodes-base.set"}

        differences = compare_node("Test", git_node, runtime_node)

        assert len(differences) == 1
        assert differences[0].path == "nodes[Test].type"
        assert differences[0].git_value == "n8n-nodes-base.httpRequest"
        assert differences[0].runtime_value == "n8n-nodes-base.set"
        assert differences[0].diff_type == "modified"

    @pytest.mark.unit
    def test_parameter_change_detected(self):
        """Parameter changes should be detected."""
        git_node = {
            "name": "HTTP",
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {"url": "https://old.api.com", "method": "GET"},
        }
        runtime_node = {
            "name": "HTTP",
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {"url": "https://new.api.com", "method": "GET"},
        }

        differences = compare_node("HTTP", git_node, runtime_node)

        # Should detect the URL parameter change
        url_diff = next((d for d in differences if "url" in d.path), None)
        assert url_diff is not None
        assert url_diff.git_value == "https://old.api.com"
        assert url_diff.runtime_value == "https://new.api.com"

    @pytest.mark.unit
    def test_position_change_detected(self):
        """Position changes should be detected."""
        git_node = {
            "name": "Test",
            "type": "n8n-nodes-base.start",
            "position": [0, 0],
        }
        runtime_node = {
            "name": "Test",
            "type": "n8n-nodes-base.start",
            "position": [100, 200],
        }

        differences = compare_node("Test", git_node, runtime_node)

        position_diff = next((d for d in differences if "position" in d.path), None)
        assert position_diff is not None
        assert position_diff.git_value == [0, 0]
        assert position_diff.runtime_value == [100, 200]

    @pytest.mark.unit
    def test_added_parameter_detected(self):
        """New parameters in runtime should be detected as added."""
        git_node = {
            "name": "Test",
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {"url": "https://api.com"},
        }
        runtime_node = {
            "name": "Test",
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {"url": "https://api.com", "timeout": 5000},
        }

        differences = compare_node("Test", git_node, runtime_node)

        timeout_diff = next((d for d in differences if "timeout" in d.path), None)
        assert timeout_diff is not None
        assert timeout_diff.diff_type == "added"


class TestCompareNodes:
    """Tests for comparing lists of nodes."""

    @pytest.mark.unit
    def test_no_drift_for_identical_lists(self):
        """Identical node lists should have no drift."""
        nodes = [
            {"name": "Start", "type": "n8n-nodes-base.start"},
            {"name": "HTTP", "type": "n8n-nodes-base.httpRequest"},
        ]

        differences, summary = compare_nodes(nodes, nodes)

        assert differences == []
        assert summary.nodes_added == 0
        assert summary.nodes_removed == 0
        assert summary.nodes_modified == 0

    @pytest.mark.unit
    def test_removed_node_detected(self):
        """Nodes in git but not runtime should be marked as removed."""
        git_nodes = [
            {"name": "Start", "type": "n8n-nodes-base.start"},
            {"name": "HTTP", "type": "n8n-nodes-base.httpRequest"},
        ]
        runtime_nodes = [
            {"name": "Start", "type": "n8n-nodes-base.start"},
        ]

        differences, summary = compare_nodes(git_nodes, runtime_nodes)

        assert summary.nodes_removed == 1
        removed_diff = next((d for d in differences if d.diff_type == "removed"), None)
        assert removed_diff is not None
        assert "HTTP" in removed_diff.path

    @pytest.mark.unit
    def test_added_node_detected(self):
        """Nodes in runtime but not git should be marked as added."""
        git_nodes = [
            {"name": "Start", "type": "n8n-nodes-base.start"},
        ]
        runtime_nodes = [
            {"name": "Start", "type": "n8n-nodes-base.start"},
            {"name": "New Node", "type": "n8n-nodes-base.set"},
        ]

        differences, summary = compare_nodes(git_nodes, runtime_nodes)

        assert summary.nodes_added == 1
        added_diff = next((d for d in differences if d.diff_type == "added"), None)
        assert added_diff is not None
        assert "New Node" in added_diff.path

    @pytest.mark.unit
    def test_modified_node_detected(self):
        """Modified nodes should be counted and have differences listed."""
        git_nodes = [
            {"name": "HTTP", "type": "n8n-nodes-base.httpRequest", "parameters": {"url": "old.com"}},
        ]
        runtime_nodes = [
            {"name": "HTTP", "type": "n8n-nodes-base.httpRequest", "parameters": {"url": "new.com"}},
        ]

        differences, summary = compare_nodes(git_nodes, runtime_nodes)

        assert summary.nodes_modified == 1


class TestCompareConnections:
    """Tests for comparing workflow connections."""

    @pytest.mark.unit
    def test_identical_connections_no_drift(self):
        """Identical connections should have no drift."""
        connections = {
            "Start": {"main": [[{"node": "HTTP", "type": "main", "index": 0}]]},
        }

        differences, changed = compare_connections(connections, connections)

        assert differences == []
        assert changed is False

    @pytest.mark.unit
    def test_different_connections_detected(self):
        """Different connections should be detected."""
        git_connections = {
            "Start": {"main": [[{"node": "HTTP", "type": "main", "index": 0}]]},
        }
        runtime_connections = {
            "Start": {"main": [[{"node": "Set", "type": "main", "index": 0}]]},
        }

        differences, changed = compare_connections(git_connections, runtime_connections)

        assert changed is True
        assert len(differences) == 1
        assert differences[0].path == "connections"

    @pytest.mark.unit
    def test_empty_connections_no_drift(self):
        """Empty connections on both sides should have no drift."""
        differences, changed = compare_connections({}, {})
        assert changed is False

    @pytest.mark.unit
    def test_none_connections_no_drift(self):
        """None connections on both sides should have no drift."""
        differences, changed = compare_connections(None, None)
        assert changed is False


class TestCompareSettings:
    """Tests for comparing workflow settings."""

    @pytest.mark.unit
    def test_identical_settings_no_drift(self):
        """Identical settings should have no drift."""
        settings = {"saveExecutionProgress": True, "saveManualExecutions": False}

        differences, changed = compare_settings(settings, settings)

        assert differences == []
        assert changed is False

    @pytest.mark.unit
    def test_different_settings_detected(self):
        """Changed settings should be detected."""
        git_settings = {"saveExecutionProgress": True}
        runtime_settings = {"saveExecutionProgress": False}

        differences, changed = compare_settings(git_settings, runtime_settings)

        assert changed is True
        assert len(differences) == 1
        assert "saveExecutionProgress" in differences[0].path

    @pytest.mark.unit
    def test_added_setting_detected(self):
        """New settings in runtime should be detected."""
        git_settings = {"existingSetting": True}
        runtime_settings = {"existingSetting": True, "newSetting": "value"}

        differences, changed = compare_settings(git_settings, runtime_settings)

        assert changed is True
        new_diff = next((d for d in differences if "newSetting" in d.path), None)
        assert new_diff is not None


class TestCompareWorkflows:
    """Tests for the main compare_workflows function."""

    @pytest.mark.unit
    def test_no_git_version_returns_no_drift(self):
        """If no git version exists, should return no drift."""
        runtime = {"name": "Test", "active": True, "nodes": [], "connections": {}}

        result = compare_workflows(None, runtime)

        assert result.has_drift is False
        assert result.git_version is None
        assert result.runtime_version == runtime
        assert result.differences == []

    @pytest.mark.unit
    def test_identical_workflows_no_drift(self):
        """Identical workflows should have no drift."""
        workflow = {
            "name": "Test Workflow",
            "active": True,
            "nodes": [{"name": "Start", "type": "n8n-nodes-base.start"}],
            "connections": {},
            "settings": {},
        }

        result = compare_workflows(workflow, workflow)

        assert result.has_drift is False
        assert result.differences == []
        assert result.summary.nodes_added == 0
        assert result.summary.nodes_removed == 0
        assert result.summary.nodes_modified == 0
        assert result.summary.connections_changed is False
        assert result.summary.settings_changed is False

    @pytest.mark.unit
    def test_name_change_detected(self):
        """Workflow name changes should be detected."""
        git = {"name": "Old Name", "active": True, "nodes": [], "connections": {}}
        runtime = {"name": "New Name", "active": True, "nodes": [], "connections": {}}

        result = compare_workflows(git, runtime)

        assert result.has_drift is True
        name_diff = next((d for d in result.differences if d.path == "name"), None)
        assert name_diff is not None
        assert name_diff.git_value == "Old Name"
        assert name_diff.runtime_value == "New Name"

    @pytest.mark.unit
    def test_active_state_change_detected(self):
        """Active state changes should be detected."""
        git = {"name": "Test", "active": False, "nodes": [], "connections": {}}
        runtime = {"name": "Test", "active": True, "nodes": [], "connections": {}}

        result = compare_workflows(git, runtime)

        assert result.has_drift is True
        active_diff = next((d for d in result.differences if d.path == "active"), None)
        assert active_diff is not None
        assert active_diff.git_value is False
        assert active_diff.runtime_value is True

    @pytest.mark.unit
    def test_commit_info_preserved(self):
        """Commit SHA and date should be preserved in result."""
        git = {"name": "Test", "active": True, "nodes": [], "connections": {}}
        runtime = {"name": "Test", "active": True, "nodes": [], "connections": {}}

        result = compare_workflows(
            git, runtime,
            last_commit_sha="abc123",
            last_commit_date="2024-01-15T10:00:00Z"
        )

        assert result.last_commit_sha == "abc123"
        assert result.last_commit_date == "2024-01-15T10:00:00Z"

    @pytest.mark.unit
    def test_to_dict_serialization(self):
        """DriftResult.to_dict should serialize correctly."""
        git = {"name": "Test", "active": True, "nodes": [], "connections": {}}
        runtime = {"name": "New", "active": True, "nodes": [], "connections": {}}

        result = compare_workflows(git, runtime, "sha123", "2024-01-15")
        dict_result = result.to_dict()

        assert dict_result["hasDrift"] is True
        assert dict_result["lastCommitSha"] == "sha123"
        assert dict_result["lastCommitDate"] == "2024-01-15"
        assert isinstance(dict_result["differences"], list)
        assert isinstance(dict_result["summary"], dict)


class TestIgnoredFields:
    """Tests for field ignoring behavior."""

    @pytest.mark.unit
    def test_ignored_fields_are_defined(self):
        """Verify expected fields are in IGNORED_FIELDS."""
        expected_ignored = ["id", "createdAt", "updatedAt", "versionId", "meta", "staticData"]
        for field in expected_ignored:
            assert field in IGNORED_FIELDS

    @pytest.mark.unit
    def test_ignored_node_fields_are_defined(self):
        """Verify expected node fields are in IGNORED_NODE_FIELDS."""
        expected_ignored = ["id", "webhookId", "notesInFlow"]
        for field in expected_ignored:
            assert field in IGNORED_NODE_FIELDS


# =============================================================================
# NEW: Tests for semantic change categories and risk levels
# =============================================================================

from app.services.diff_service import (
    compute_change_categories,
    compute_risk_level,
    compute_diff_hash,
    DriftDifference,
)
from app.schemas.promotion import ChangeCategory, RiskLevel


def _make_diff(path: str, diff_type: str = "modified", git_value=None, runtime_value=None) -> DriftDifference:
    """Helper to create DriftDifference objects for testing."""
    return DriftDifference(
        path=path,
        diff_type=diff_type,
        git_value=git_value,
        runtime_value=runtime_value
    )


class TestComputeChangeCategories:
    """Tests for compute_change_categories function."""

    @pytest.mark.unit
    def test_node_added_category(self):
        """Adding nodes should result in NODE_ADDED category."""
        source_wf = {
            "nodes": [
                {"name": "Start", "type": "n8n-nodes-base.start"},
                {"name": "HTTP", "type": "n8n-nodes-base.httpRequest"},
            ]
        }
        target_wf = {
            "nodes": [
                {"name": "Start", "type": "n8n-nodes-base.start"},
            ]
        }
        differences = [_make_diff("nodes[HTTP]", "added")]

        categories = compute_change_categories(source_wf, target_wf, differences)

        assert ChangeCategory.NODE_ADDED in categories

    @pytest.mark.unit
    def test_node_removed_category(self):
        """Removing nodes should result in NODE_REMOVED category."""
        source_wf = {
            "nodes": [
                {"name": "Start", "type": "n8n-nodes-base.start"},
            ]
        }
        target_wf = {
            "nodes": [
                {"name": "Start", "type": "n8n-nodes-base.start"},
                {"name": "HTTP", "type": "n8n-nodes-base.httpRequest"},
            ]
        }
        differences = [_make_diff("nodes[HTTP]", "removed")]

        categories = compute_change_categories(source_wf, target_wf, differences)

        assert ChangeCategory.NODE_REMOVED in categories

    @pytest.mark.unit
    def test_credentials_changed_category(self):
        """Credential changes should result in CREDENTIALS_CHANGED category."""
        source_wf = {
            "nodes": [
                {"name": "HTTP", "type": "n8n-nodes-base.httpRequest", "credentials": {"httpBasicAuth": {"id": "new-cred"}}},
            ]
        }
        target_wf = {
            "nodes": [
                {"name": "HTTP", "type": "n8n-nodes-base.httpRequest", "credentials": {"httpBasicAuth": {"id": "old-cred"}}},
            ]
        }
        differences = [_make_diff("nodes[HTTP].credentials", "modified")]

        categories = compute_change_categories(source_wf, target_wf, differences)

        assert ChangeCategory.CREDENTIALS_CHANGED in categories

    @pytest.mark.unit
    def test_http_changed_category(self):
        """HTTP node changes should result in HTTP_CHANGED category."""
        source_wf = {
            "nodes": [
                {"name": "HTTP", "type": "n8n-nodes-base.httpRequest", "parameters": {"url": "https://new.api.com"}},
            ]
        }
        target_wf = {
            "nodes": [
                {"name": "HTTP", "type": "n8n-nodes-base.httpRequest", "parameters": {"url": "https://old.api.com"}},
            ]
        }
        differences = [_make_diff("nodes[HTTP].parameters.url", "modified")]

        categories = compute_change_categories(source_wf, target_wf, differences)

        assert ChangeCategory.HTTP_CHANGED in categories

    @pytest.mark.unit
    def test_trigger_changed_category(self):
        """Trigger node changes should result in TRIGGER_CHANGED category."""
        # Note: webhook is in HTTP_NODE_TYPES (higher priority), so use scheduleTrigger
        source_wf = {
            "nodes": [
                {"name": "Schedule", "type": "n8n-nodes-base.scheduleTrigger", "parameters": {"rule": "0 * * * *"}},
            ]
        }
        target_wf = {
            "nodes": [
                {"name": "Schedule", "type": "n8n-nodes-base.scheduleTrigger", "parameters": {"rule": "0 0 * * *"}},
            ]
        }
        differences = [_make_diff("nodes[Schedule].parameters.rule", "modified")]

        categories = compute_change_categories(source_wf, target_wf, differences)

        assert ChangeCategory.TRIGGER_CHANGED in categories

    @pytest.mark.unit
    def test_code_changed_category(self):
        """Code/Function node changes should result in CODE_CHANGED category."""
        source_wf = {
            "nodes": [
                {"name": "Function", "type": "n8n-nodes-base.function", "parameters": {"functionCode": "return items;"}},
            ]
        }
        target_wf = {
            "nodes": [
                {"name": "Function", "type": "n8n-nodes-base.function", "parameters": {"functionCode": "return [];"}},
            ]
        }
        differences = [_make_diff("nodes[Function].parameters.functionCode", "modified")]

        categories = compute_change_categories(source_wf, target_wf, differences)

        assert ChangeCategory.CODE_CHANGED in categories

    @pytest.mark.unit
    def test_settings_changed_category(self):
        """Settings changes should result in SETTINGS_CHANGED category."""
        source_wf = {
            "settings": {"saveExecutionProgress": True},
            "nodes": []
        }
        target_wf = {
            "settings": {"saveExecutionProgress": False},
            "nodes": []
        }
        differences = [_make_diff("settings.saveExecutionProgress", "modified")]

        categories = compute_change_categories(source_wf, target_wf, differences)

        assert ChangeCategory.SETTINGS_CHANGED in categories

    @pytest.mark.unit
    def test_rename_only_category(self):
        """Name-only changes should result in RENAME_ONLY category."""
        source_wf = {
            "name": "New Workflow Name",
            "nodes": [{"name": "Start", "type": "n8n-nodes-base.start"}]
        }
        target_wf = {
            "name": "Old Workflow Name",
            "nodes": [{"name": "Start", "type": "n8n-nodes-base.start"}]
        }
        # Only name changed, no other differences
        differences = [_make_diff("name", "modified")]

        categories = compute_change_categories(source_wf, target_wf, differences)

        # When only name changes, should include RENAME_ONLY
        assert ChangeCategory.RENAME_ONLY in categories

    @pytest.mark.unit
    def test_multiple_categories(self):
        """Multiple changes should result in multiple categories."""
        source_wf = {
            "nodes": [
                {"name": "HTTP", "type": "n8n-nodes-base.httpRequest", "parameters": {"url": "https://new.api.com"}},
                {"name": "Function", "type": "n8n-nodes-base.function"},
            ]
        }
        target_wf = {
            "nodes": [
                {"name": "HTTP", "type": "n8n-nodes-base.httpRequest", "parameters": {"url": "https://old.api.com"}},
            ]
        }
        differences = [
            _make_diff("nodes[HTTP].parameters.url", "modified"),
            _make_diff("nodes[Function]", "added"),
        ]

        categories = compute_change_categories(source_wf, target_wf, differences)

        assert ChangeCategory.HTTP_CHANGED in categories
        assert ChangeCategory.NODE_ADDED in categories


class TestComputeRiskLevel:
    """Tests for compute_risk_level function."""

    @pytest.mark.unit
    def test_high_risk_for_credentials(self):
        """Credential changes should be high risk."""
        categories = [ChangeCategory.CREDENTIALS_CHANGED]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.HIGH

    @pytest.mark.unit
    def test_high_risk_for_expressions(self):
        """Expression changes should be high risk."""
        categories = [ChangeCategory.EXPRESSIONS_CHANGED]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.HIGH

    @pytest.mark.unit
    def test_high_risk_for_code(self):
        """Code changes should be high risk."""
        categories = [ChangeCategory.CODE_CHANGED]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.HIGH

    @pytest.mark.unit
    def test_high_risk_for_http(self):
        """HTTP changes should be high risk."""
        categories = [ChangeCategory.HTTP_CHANGED]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.HIGH

    @pytest.mark.unit
    def test_high_risk_for_trigger(self):
        """Trigger changes should be high risk."""
        categories = [ChangeCategory.TRIGGER_CHANGED]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.HIGH

    @pytest.mark.unit
    def test_medium_risk_for_error_handling(self):
        """Error handling changes should be medium risk."""
        categories = [ChangeCategory.ERROR_HANDLING_CHANGED]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.MEDIUM

    @pytest.mark.unit
    def test_medium_risk_for_settings(self):
        """Settings changes should be medium risk."""
        categories = [ChangeCategory.SETTINGS_CHANGED]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.MEDIUM

    @pytest.mark.unit
    def test_low_risk_for_rename(self):
        """Rename-only changes should be low risk."""
        categories = [ChangeCategory.RENAME_ONLY]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.LOW

    @pytest.mark.unit
    def test_low_risk_for_node_added(self):
        """Node additions should be low risk."""
        categories = [ChangeCategory.NODE_ADDED]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.LOW

    @pytest.mark.unit
    def test_empty_categories_is_low_risk(self):
        """Empty categories should be low risk."""
        categories = []
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.LOW

    @pytest.mark.unit
    def test_high_overrides_medium(self):
        """High risk categories should override medium."""
        categories = [ChangeCategory.SETTINGS_CHANGED, ChangeCategory.CREDENTIALS_CHANGED]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.HIGH

    @pytest.mark.unit
    def test_medium_overrides_low(self):
        """Medium risk categories should override low."""
        categories = [ChangeCategory.RENAME_ONLY, ChangeCategory.SETTINGS_CHANGED]
        risk = compute_risk_level(categories)
        assert risk == RiskLevel.MEDIUM


class TestComputeDiffHash:
    """Tests for compute_diff_hash function."""

    @pytest.mark.unit
    def test_hash_for_two_workflows(self):
        """Computing hash for two workflows should return a string."""
        source_wf = {"name": "Test", "nodes": []}
        target_wf = {"name": "Test", "nodes": [{"name": "Node1"}]}

        hash_result = compute_diff_hash(source_wf, target_wf)

        assert hash_result is not None
        assert isinstance(hash_result, str)
        assert len(hash_result) > 0  # Hash should have some length

    @pytest.mark.unit
    def test_same_workflows_same_hash(self):
        """Same workflows should produce same hash."""
        wf = {"name": "Test", "nodes": [{"name": "Node1"}]}

        hash1 = compute_diff_hash(wf, wf)
        hash2 = compute_diff_hash(wf, wf)

        assert hash1 == hash2

    @pytest.mark.unit
    def test_different_workflows_different_hash(self):
        """Different workflows should produce different hashes."""
        wf1 = {"name": "Test1", "nodes": []}
        wf2 = {"name": "Test2", "nodes": []}

        hash1 = compute_diff_hash(wf1, wf2)
        hash2 = compute_diff_hash(wf2, wf1)

        # Order matters for diff hash
        assert hash1 != hash2

    @pytest.mark.unit
    def test_hash_with_none_source(self):
        """Hash with None source should still work."""
        target_wf = {"name": "Test", "nodes": []}

        hash_result = compute_diff_hash(None, target_wf)

        assert hash_result is not None
        assert isinstance(hash_result, str)

    @pytest.mark.unit
    def test_hash_with_none_target(self):
        """Hash with None target should still work."""
        source_wf = {"name": "Test", "nodes": []}

        hash_result = compute_diff_hash(source_wf, None)

        assert hash_result is not None
        assert isinstance(hash_result, str)
