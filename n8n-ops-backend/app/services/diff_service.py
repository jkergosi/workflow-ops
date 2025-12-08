"""
Diff Service - JSON comparison utility for workflow drift detection
"""
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, asdict


@dataclass
class DriftDifference:
    """Represents a single difference between two workflow versions"""
    path: str
    git_value: Any
    runtime_value: Any
    diff_type: str  # 'added', 'removed', 'modified'


@dataclass
class DriftSummary:
    """Summary of differences between workflow versions"""
    nodes_added: int = 0
    nodes_removed: int = 0
    nodes_modified: int = 0
    connections_changed: bool = False
    settings_changed: bool = False


@dataclass
class DriftResult:
    """Complete drift detection result"""
    has_drift: bool
    git_version: Optional[Dict[str, Any]]
    runtime_version: Optional[Dict[str, Any]]
    last_commit_sha: Optional[str]
    last_commit_date: Optional[str]
    differences: List[DriftDifference]
    summary: DriftSummary

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "hasDrift": self.has_drift,
            "gitVersion": self.git_version,
            "runtimeVersion": self.runtime_version,
            "lastCommitSha": self.last_commit_sha,
            "lastCommitDate": self.last_commit_date,
            "differences": [
                {
                    "path": d.path,
                    "gitValue": d.git_value,
                    "runtimeValue": d.runtime_value,
                    "type": d.diff_type
                }
                for d in self.differences
            ],
            "summary": {
                "nodesAdded": self.summary.nodes_added,
                "nodesRemoved": self.summary.nodes_removed,
                "nodesModified": self.summary.nodes_modified,
                "connectionsChanged": self.summary.connections_changed,
                "settingsChanged": self.summary.settings_changed
            }
        }


# Fields to ignore when comparing workflows
IGNORED_FIELDS: Set[str] = {
    "id",
    "createdAt",
    "updatedAt",
    "versionId",
    "meta",
    "staticData",
    "triggerCount",
    "shared",
    "homeProject",
    "sharedWithProjects",
    "_comment"  # Added by our GitHub sync
}

# Fields to ignore within nodes
IGNORED_NODE_FIELDS: Set[str] = {
    "id",
    "webhookId",
    "notesInFlow"
}


def normalize_value(value: Any) -> Any:
    """Normalize a value for comparison (handle None vs missing, etc.)"""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: normalize_value(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [normalize_value(v) for v in value]
    return value


def compare_nodes(git_nodes: List[Dict], runtime_nodes: List[Dict]) -> tuple[List[DriftDifference], DriftSummary]:
    """Compare node lists between Git and runtime versions"""
    differences: List[DriftDifference] = []
    summary = DriftSummary()

    # Create maps by node name (more stable than id)
    git_by_name = {node.get("name", node.get("id")): node for node in git_nodes}
    runtime_by_name = {node.get("name", node.get("id")): node for node in runtime_nodes}

    all_names = set(git_by_name.keys()) | set(runtime_by_name.keys())

    for name in all_names:
        git_node = git_by_name.get(name)
        runtime_node = runtime_by_name.get(name)

        if git_node and not runtime_node:
            # Node removed from runtime
            summary.nodes_removed += 1
            differences.append(DriftDifference(
                path=f"nodes[{name}]",
                git_value={"type": git_node.get("type"), "name": name},
                runtime_value=None,
                diff_type="removed"
            ))
        elif runtime_node and not git_node:
            # Node added in runtime
            summary.nodes_added += 1
            differences.append(DriftDifference(
                path=f"nodes[{name}]",
                git_value=None,
                runtime_value={"type": runtime_node.get("type"), "name": name},
                diff_type="added"
            ))
        else:
            # Node exists in both - check for modifications
            node_diffs = compare_node(name, git_node, runtime_node)
            if node_diffs:
                summary.nodes_modified += 1
                differences.extend(node_diffs)

    return differences, summary


def compare_node(name: str, git_node: Dict, runtime_node: Dict) -> List[DriftDifference]:
    """Compare a single node between versions"""
    differences: List[DriftDifference] = []

    # Compare type
    if git_node.get("type") != runtime_node.get("type"):
        differences.append(DriftDifference(
            path=f"nodes[{name}].type",
            git_value=git_node.get("type"),
            runtime_value=runtime_node.get("type"),
            diff_type="modified"
        ))

    # Compare parameters (the most important part)
    git_params = normalize_value(git_node.get("parameters", {}))
    runtime_params = normalize_value(runtime_node.get("parameters", {}))

    if git_params != runtime_params:
        # Find specific parameter differences
        all_keys = set(git_params.keys()) | set(runtime_params.keys())
        for key in all_keys:
            git_val = git_params.get(key)
            runtime_val = runtime_params.get(key)
            if git_val != runtime_val:
                differences.append(DriftDifference(
                    path=f"nodes[{name}].parameters.{key}",
                    git_value=git_val,
                    runtime_value=runtime_val,
                    diff_type="modified" if git_val and runtime_val else ("added" if runtime_val else "removed")
                ))

    # Compare position (minor change)
    git_pos = git_node.get("position", [0, 0])
    runtime_pos = runtime_node.get("position", [0, 0])
    if git_pos != runtime_pos:
        differences.append(DriftDifference(
            path=f"nodes[{name}].position",
            git_value=git_pos,
            runtime_value=runtime_pos,
            diff_type="modified"
        ))

    return differences


def compare_connections(git_connections: Dict, runtime_connections: Dict) -> tuple[List[DriftDifference], bool]:
    """Compare connections between versions"""
    differences: List[DriftDifference] = []

    git_normalized = normalize_value(git_connections or {})
    runtime_normalized = normalize_value(runtime_connections or {})

    if git_normalized == runtime_normalized:
        return [], False

    # Connections are different
    differences.append(DriftDifference(
        path="connections",
        git_value=f"{len(git_connections or {})} source nodes",
        runtime_value=f"{len(runtime_connections or {})} source nodes",
        diff_type="modified"
    ))

    return differences, True


def compare_settings(git_settings: Dict, runtime_settings: Dict) -> tuple[List[DriftDifference], bool]:
    """Compare workflow settings between versions"""
    differences: List[DriftDifference] = []

    git_normalized = normalize_value(git_settings or {})
    runtime_normalized = normalize_value(runtime_settings or {})

    if git_normalized == runtime_normalized:
        return [], False

    all_keys = set(git_normalized.keys()) | set(runtime_normalized.keys())
    for key in all_keys:
        git_val = git_normalized.get(key)
        runtime_val = runtime_normalized.get(key)
        if git_val != runtime_val:
            differences.append(DriftDifference(
                path=f"settings.{key}",
                git_value=git_val,
                runtime_value=runtime_val,
                diff_type="modified" if git_val and runtime_val else ("added" if runtime_val else "removed")
            ))

    return differences, True


def compare_workflows(
    git_workflow: Optional[Dict[str, Any]],
    runtime_workflow: Dict[str, Any],
    last_commit_sha: Optional[str] = None,
    last_commit_date: Optional[str] = None
) -> DriftResult:
    """
    Compare a workflow between Git and runtime versions.

    Args:
        git_workflow: Workflow JSON from GitHub (None if not found)
        runtime_workflow: Workflow JSON from N8N runtime
        last_commit_sha: SHA of the last Git commit for this workflow
        last_commit_date: Date of the last Git commit

    Returns:
        DriftResult with full comparison details
    """
    # If no Git version, can't compare
    if git_workflow is None:
        return DriftResult(
            has_drift=False,  # Not really drift, just not tracked in Git
            git_version=None,
            runtime_version=runtime_workflow,
            last_commit_sha=None,
            last_commit_date=None,
            differences=[],
            summary=DriftSummary()
        )

    all_differences: List[DriftDifference] = []
    summary = DriftSummary()

    # Compare name
    if git_workflow.get("name") != runtime_workflow.get("name"):
        all_differences.append(DriftDifference(
            path="name",
            git_value=git_workflow.get("name"),
            runtime_value=runtime_workflow.get("name"),
            diff_type="modified"
        ))

    # Compare active state
    if git_workflow.get("active") != runtime_workflow.get("active"):
        all_differences.append(DriftDifference(
            path="active",
            git_value=git_workflow.get("active"),
            runtime_value=runtime_workflow.get("active"),
            diff_type="modified"
        ))

    # Compare nodes
    git_nodes = git_workflow.get("nodes", [])
    runtime_nodes = runtime_workflow.get("nodes", [])
    node_diffs, node_summary = compare_nodes(git_nodes, runtime_nodes)
    all_differences.extend(node_diffs)
    summary.nodes_added = node_summary.nodes_added
    summary.nodes_removed = node_summary.nodes_removed
    summary.nodes_modified = node_summary.nodes_modified

    # Compare connections
    connection_diffs, connections_changed = compare_connections(
        git_workflow.get("connections"),
        runtime_workflow.get("connections")
    )
    all_differences.extend(connection_diffs)
    summary.connections_changed = connections_changed

    # Compare settings
    settings_diffs, settings_changed = compare_settings(
        git_workflow.get("settings"),
        runtime_workflow.get("settings")
    )
    all_differences.extend(settings_diffs)
    summary.settings_changed = settings_changed

    has_drift = len(all_differences) > 0

    return DriftResult(
        has_drift=has_drift,
        git_version=git_workflow,
        runtime_version=runtime_workflow,
        last_commit_sha=last_commit_sha,
        last_commit_date=last_commit_date,
        differences=all_differences,
        summary=summary
    )
