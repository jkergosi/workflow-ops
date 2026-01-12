"""
Service for computing workflow sync status between N8N runtime and GitHub

This service uses the canonical normalization function from promotion_service
to ensure consistent comparisons across the entire sync pipeline.
"""
from typing import Dict, Any, Optional
import json
from datetime import datetime
from enum import Enum

from app.services.promotion_service import normalize_workflow_for_comparison


class SyncStatus(str, Enum):
    IN_SYNC = "in_sync"
    LOCAL_CHANGES = "local_changes"
    UPDATE_AVAILABLE = "update_available"
    CONFLICT = "conflict"


def compute_sync_status(
    n8n_workflow: Dict[str, Any],
    github_workflow: Optional[Dict[str, Any]],
    last_synced_at: Optional[str] = None,
    n8n_updated_at: Optional[str] = None,
    github_updated_at: Optional[str] = None
) -> str:
    """
    Compute sync status for a workflow by comparing N8N runtime with GitHub.

    Uses the canonical normalize_workflow_for_comparison function to ensure
    consistent normalization with the rest of the sync pipeline.

    Args:
        n8n_workflow: Workflow data from N8N runtime
        github_workflow: Workflow data from GitHub (None if not in GitHub)
        last_synced_at: ISO timestamp of last successful sync (optional)
        n8n_updated_at: ISO timestamp when N8N workflow was last updated (optional)
        github_updated_at: ISO timestamp when GitHub workflow was last updated (optional)

    Returns:
        Sync status: 'in_sync', 'local_changes', 'update_available', or 'conflict'
    """
    # Use canonical normalization function for consistent comparison
    n8n_json = normalize_workflow_for_comparison(n8n_workflow)

    # If workflow doesn't exist in GitHub
    if github_workflow is None:
        # If it was never synced, treat as local changes
        if not last_synced_at:
            return SyncStatus.LOCAL_CHANGES.value
        # If it was synced before but no longer in GitHub, treat as local changes
        return SyncStatus.LOCAL_CHANGES.value

    github_json = normalize_workflow_for_comparison(github_workflow)

    # Compare normalized JSON
    n8n_json_str = json.dumps(n8n_json, sort_keys=True)
    github_json_str = json.dumps(github_json, sort_keys=True)

    # If JSON is identical
    if n8n_json_str == github_json_str:
        return SyncStatus.IN_SYNC.value

    # If JSON differs, determine the cause using timestamps if available
    if last_synced_at and n8n_updated_at and github_updated_at:
        try:
            last_sync = datetime.fromisoformat(last_synced_at.replace('Z', '+00:00'))
            n8n_updated = datetime.fromisoformat(n8n_updated_at.replace('Z', '+00:00'))
            github_updated = datetime.fromisoformat(github_updated_at.replace('Z', '+00:00'))
            
            # Check if N8N changed since last sync
            n8n_changed = n8n_updated > last_sync
            # Check if GitHub changed since last sync
            github_changed = github_updated > last_sync
            
            if n8n_changed and not github_changed:
                return SyncStatus.LOCAL_CHANGES.value
            elif github_changed and not n8n_changed:
                return SyncStatus.UPDATE_AVAILABLE.value
            elif n8n_changed and github_changed:
                return SyncStatus.CONFLICT.value
        except (ValueError, AttributeError):
            # If timestamp parsing fails, fall through to conflict
            pass
    
    # If we can't determine from timestamps, check if both have different updated times
    if n8n_updated_at and github_updated_at:
        try:
            n8n_updated = datetime.fromisoformat(n8n_updated_at.replace('Z', '+00:00'))
            github_updated = datetime.fromisoformat(github_updated_at.replace('Z', '+00:00'))

            # Compare timestamps to determine which version is newer
            if n8n_updated > github_updated:
                return SyncStatus.LOCAL_CHANGES.value
            elif github_updated > n8n_updated:
                return SyncStatus.UPDATE_AVAILABLE.value
            else:
                # Same timestamp but different content - treat as local changes
                # (likely minor normalization differences)
                return SyncStatus.LOCAL_CHANGES.value
        except (ValueError, AttributeError):
            pass

    # Default to local_changes when we can't determine status
    # This is safer than "conflict" which implies both sides changed independently
    # In most cases, the N8N runtime is the authoritative source
    return SyncStatus.LOCAL_CHANGES.value


# Note: The _normalize_workflow_json function has been removed.
# We now use the canonical normalize_workflow_for_comparison function
# from promotion_service.py to ensure consistent normalization across
# the entire sync pipeline. This eliminates potential hash mismatches
# caused by different normalization logic.

