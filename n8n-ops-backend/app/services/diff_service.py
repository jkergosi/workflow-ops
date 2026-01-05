"""
Diff Service - JSON comparison utility for workflow drift detection and promotion comparison
"""
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
import hashlib
import json
import re

from app.schemas.promotion import ChangeCategory, RiskLevel


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


# =============================================================================
# NEW: Semantic Category Detection for Promotion Compare
# =============================================================================

# Node types that indicate specific change categories
HTTP_NODE_TYPES = {
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.webhook",
    "@n8n/n8n-nodes-langchain.httpRequest",
}

TRIGGER_NODE_TYPES = {
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.cronTrigger",
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.emailTrigger",
    "n8n-nodes-base.intervalTrigger",
}

ROUTING_NODE_TYPES = {
    "n8n-nodes-base.if",
    "n8n-nodes-base.switch",
    "n8n-nodes-base.splitInBatches",
    "n8n-nodes-base.merge",
    "n8n-nodes-base.filter",
}

CODE_NODE_TYPES = {
    "n8n-nodes-base.code",
    "n8n-nodes-base.function",
    "n8n-nodes-base.functionItem",
    "n8n-nodes-base.executeCommand",
    "@n8n/n8n-nodes-langchain.code",
}

ERROR_HANDLING_NODE_TYPES = {
    "n8n-nodes-base.errorTrigger",
    "n8n-nodes-base.stopAndError",
}

# Risk category mapping
HIGH_RISK_CATEGORIES: Set[ChangeCategory] = {
    ChangeCategory.CREDENTIALS_CHANGED,
    ChangeCategory.EXPRESSIONS_CHANGED,
    ChangeCategory.TRIGGER_CHANGED,
    ChangeCategory.HTTP_CHANGED,
    ChangeCategory.ROUTING_CHANGED,
    ChangeCategory.CODE_CHANGED,
}

MEDIUM_RISK_CATEGORIES: Set[ChangeCategory] = {
    ChangeCategory.ERROR_HANDLING_CHANGED,
    ChangeCategory.SETTINGS_CHANGED,
    ChangeCategory.NODE_TYPE_CHANGED,
}

LOW_RISK_CATEGORIES: Set[ChangeCategory] = {
    ChangeCategory.RENAME_ONLY,
    ChangeCategory.NODE_ADDED,
    ChangeCategory.NODE_REMOVED,
}


def compute_diff_hash(source_workflow: Dict[str, Any], target_workflow: Optional[Dict[str, Any]]) -> str:
    """
    Compute a hash for the diff between source and target workflows.
    Used for caching AI summaries.
    """
    source_str = json.dumps(source_workflow, sort_keys=True) if source_workflow else ""
    target_str = json.dumps(target_workflow, sort_keys=True) if target_workflow else ""
    combined = f"{source_str}|{target_str}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def _contains_expression(value: Any) -> bool:
    """Check if a value contains n8n expressions ({{ ... }})."""
    if isinstance(value, str):
        return "{{" in value and "}}" in value
    if isinstance(value, dict):
        return any(_contains_expression(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_expression(v) for v in value)
    return False


def _get_node_type_category(node_type: str) -> Optional[ChangeCategory]:
    """Map a node type to its change category if it's a special type."""
    if node_type in HTTP_NODE_TYPES:
        return ChangeCategory.HTTP_CHANGED
    if node_type in TRIGGER_NODE_TYPES:
        return ChangeCategory.TRIGGER_CHANGED
    if node_type in ROUTING_NODE_TYPES:
        return ChangeCategory.ROUTING_CHANGED
    if node_type in CODE_NODE_TYPES:
        return ChangeCategory.CODE_CHANGED
    if node_type in ERROR_HANDLING_NODE_TYPES:
        return ChangeCategory.ERROR_HANDLING_CHANGED
    return None


def compute_change_categories(
    source_workflow: Dict[str, Any],
    target_workflow: Optional[Dict[str, Any]],
    differences: List[DriftDifference]
) -> List[ChangeCategory]:
    """
    Analyze diff to determine semantic change categories.

    Args:
        source_workflow: The source (dev) workflow
        target_workflow: The target (prod) workflow, or None if new
        differences: List of DriftDifference objects from comparison

    Returns:
        List of ChangeCategory enum values (deduplicated)
    """
    categories: Set[ChangeCategory] = set()

    # If no target, this is a new workflow - no change categories needed
    if not target_workflow:
        return []

    source_nodes = {n.get("name"): n for n in source_workflow.get("nodes", [])}
    target_nodes = {n.get("name"): n for n in target_workflow.get("nodes", [])}

    # Check for node additions/removals
    added_nodes = set(source_nodes.keys()) - set(target_nodes.keys())
    removed_nodes = set(target_nodes.keys()) - set(source_nodes.keys())

    if added_nodes:
        categories.add(ChangeCategory.NODE_ADDED)
        # Check if added nodes are special types
        for node_name in added_nodes:
            node = source_nodes.get(node_name, {})
            node_type = node.get("type", "")
            category = _get_node_type_category(node_type)
            if category:
                categories.add(category)

    if removed_nodes:
        categories.add(ChangeCategory.NODE_REMOVED)
        # Check if removed nodes are special types
        for node_name in removed_nodes:
            node = target_nodes.get(node_name, {})
            node_type = node.get("type", "")
            category = _get_node_type_category(node_type)
            if category:
                categories.add(category)

    # Analyze differences for semantic categories
    credentials_changed = False
    expressions_changed = False
    settings_changed = False
    type_changed = False
    name_changed = False

    for diff in differences:
        path = diff.path

        # Check for credential changes
        if "credentials" in path:
            credentials_changed = True

        # Check for expression changes ({{ ... }} syntax)
        if _contains_expression(diff.git_value) or _contains_expression(diff.runtime_value):
            expressions_changed = True

        # Check for settings changes
        if path.startswith("settings."):
            settings_changed = True

        # Check for node type changes
        if ".type" in path and "nodes[" in path:
            type_changed = True
            # Determine which type of node changed
            source_type = diff.git_value if diff.git_value else diff.runtime_value
            if source_type:
                category = _get_node_type_category(source_type)
                if category:
                    categories.add(category)

        # Check for name-only change
        if path == "name":
            name_changed = True

        # Check for parameter changes on specific node types
        if "parameters" in path and "nodes[" in path:
            # Extract node name from path like "nodes[NodeName].parameters.url"
            match = re.search(r"nodes\[([^\]]+)\]", path)
            if match:
                node_name = match.group(1)
                # Check source node type
                node = source_nodes.get(node_name) or target_nodes.get(node_name)
                if node:
                    node_type = node.get("type", "")
                    category = _get_node_type_category(node_type)
                    if category:
                        categories.add(category)

    # Add categories based on detected changes
    if credentials_changed:
        categories.add(ChangeCategory.CREDENTIALS_CHANGED)
    if expressions_changed:
        categories.add(ChangeCategory.EXPRESSIONS_CHANGED)
    if settings_changed:
        categories.add(ChangeCategory.SETTINGS_CHANGED)
    if type_changed:
        categories.add(ChangeCategory.NODE_TYPE_CHANGED)

    # Check if it's only a rename (name changed but nothing else significant)
    if name_changed and len(categories) == 0:
        categories.add(ChangeCategory.RENAME_ONLY)

    return list(categories)


def compute_risk_level(categories: List[ChangeCategory]) -> RiskLevel:
    """
    Compute risk level based on change categories.

    Risk levels:
    - HIGH: credentials, expressions, triggers, HTTP, code, routing changes
    - MEDIUM: error handling, settings, node type changes
    - LOW: rename only, node additions/removals without high-risk types
    """
    if not categories:
        return RiskLevel.LOW

    category_set = set(categories)

    if category_set & HIGH_RISK_CATEGORIES:
        return RiskLevel.HIGH

    if category_set & MEDIUM_RISK_CATEGORIES:
        return RiskLevel.MEDIUM

    return RiskLevel.LOW


def compute_workflow_comparison(
    source_workflow: Dict[str, Any],
    target_workflow: Optional[Dict[str, Any]]
) -> Tuple[List[DriftDifference], DriftSummary, List[ChangeCategory], RiskLevel, str]:
    """
    Comprehensive workflow comparison that returns all needed data for promotion compare.

    Args:
        source_workflow: The source environment workflow
        target_workflow: The target environment workflow (or None if new)

    Returns:
        Tuple of (differences, summary, change_categories, risk_level, diff_hash)
    """
    # Compute diff hash first
    diff_hash = compute_diff_hash(source_workflow, target_workflow)

    # If no target, this is a new workflow
    if not target_workflow:
        summary = DriftSummary(
            nodes_added=len(source_workflow.get("nodes", [])),
            nodes_removed=0,
            nodes_modified=0,
            connections_changed=False,
            settings_changed=False
        )
        return [], summary, [], RiskLevel.LOW, diff_hash

    # Use existing compare_workflows function for the diff
    drift_result = compare_workflows(source_workflow, target_workflow)

    # Compute semantic categories
    categories = compute_change_categories(source_workflow, target_workflow, drift_result.differences)

    # Compute risk level
    risk_level = compute_risk_level(categories)

    return (
        drift_result.differences,
        drift_result.summary,
        categories,
        risk_level,
        diff_hash
    )
