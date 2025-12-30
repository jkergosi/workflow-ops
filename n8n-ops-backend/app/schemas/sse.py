"""
SSE Event Schemas for real-time deployment updates.

Defines the event payload structures for SSE streaming.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


# === Snapshot Payloads (sent on connect) ===

class DeploymentsListSnapshotPayload(BaseModel):
    """Payload for deployments list snapshot (sent on initial SSE connect)."""
    deployments: List[Dict[str, Any]]  # List of deployment objects
    total: int
    page: int
    page_size: int
    this_week_success_count: int
    running_count: int


class DeploymentDetailSnapshotPayload(BaseModel):
    """Payload for single deployment snapshot (detail page)."""
    deployment: Dict[str, Any]  # Full deployment with workflows, snapshots


# === Incremental Event Payloads ===

class DeploymentUpsertPayload(BaseModel):
    """
    Payload for deployment create/update events.
    Contains full deployment data for UI to replace/merge.
    """
    id: str
    tenant_id: str
    pipeline_id: Optional[str] = None
    source_environment_id: str
    target_environment_id: str
    status: str  # pending, running, success, failed, canceled
    triggered_by_user_id: str
    approved_by_user_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    pre_snapshot_id: Optional[str] = None
    post_snapshot_id: Optional[str] = None
    summary_json: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str
    # UI helper fields
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None
    current_workflow_name: Optional[str] = None


class DeploymentProgressPayload(BaseModel):
    """
    Lightweight payload for frequent progress updates.
    Used during deployment execution to show workflow-by-workflow progress.
    """
    deployment_id: str
    status: str  # always "running"
    progress_current: int
    progress_total: int
    current_workflow_name: Optional[str] = None


class CountsUpdatePayload(BaseModel):
    """
    Payload for counter updates on deployments page.
    Sent when deployment completes to update summary cards.
    """
    this_week_success_count: int
    running_count: int


# === Helper functions for building payloads ===

def build_deployment_upsert_payload(deployment: Dict[str, Any]) -> DeploymentUpsertPayload:
    """Convert a deployment dict to a DeploymentUpsertPayload."""
    summary = deployment.get("summary_json") or {}
    status = deployment.get("status", "pending")

    # Calculate progress fields (same logic as deployments.py:_attach_progress_fields)
    total = summary.get("total", 0)
    if status in ["success", "failed"]:
        current = (summary.get("created", 0) or 0) + (summary.get("updated", 0) or 0)
    elif status == "running":
        current = min((summary.get("processed", 0) or 0), total)
    else:
        current = 0

    current_workflow = summary.get("current_workflow")

    # Handle datetime serialization
    def serialize_dt(val):
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.isoformat()
        return str(val)

    return DeploymentUpsertPayload(
        id=deployment["id"],
        tenant_id=deployment["tenant_id"],
        pipeline_id=deployment.get("pipeline_id"),
        source_environment_id=deployment["source_environment_id"],
        target_environment_id=deployment["target_environment_id"],
        status=status,
        triggered_by_user_id=deployment["triggered_by_user_id"],
        approved_by_user_id=deployment.get("approved_by_user_id"),
        started_at=serialize_dt(deployment.get("started_at")),
        finished_at=serialize_dt(deployment.get("finished_at")),
        pre_snapshot_id=deployment.get("pre_snapshot_id"),
        post_snapshot_id=deployment.get("post_snapshot_id"),
        summary_json=summary,
        created_at=serialize_dt(deployment.get("created_at")),
        updated_at=serialize_dt(deployment.get("updated_at")),
        progress_current=current,
        progress_total=total,
        current_workflow_name=current_workflow
    )


def build_progress_payload(
    deployment_id: str,
    progress_current: int,
    progress_total: int,
    current_workflow_name: Optional[str] = None
) -> DeploymentProgressPayload:
    """Build a lightweight progress update payload."""
    return DeploymentProgressPayload(
        deployment_id=deployment_id,
        status="running",
        progress_current=progress_current,
        progress_total=progress_total,
        current_workflow_name=current_workflow_name
    )


# === Background Job Progress Payloads ===

class SyncProgressPayload(BaseModel):
    """Payload for environment sync progress updates."""
    job_id: str
    environment_id: str
    status: str  # running, completed, failed
    current_step: str  # workflows, executions, credentials, users, tags, github_backup
    current: int
    total: int
    message: Optional[str] = None
    errors: Optional[Dict[str, Any]] = None


class BackupProgressPayload(BaseModel):
    """Payload for GitHub backup progress updates."""
    job_id: str
    environment_id: str
    status: str  # running, completed, failed
    current: int
    total: int
    current_workflow_name: Optional[str] = None
    message: Optional[str] = None
    errors: Optional[List[str]] = None


class RestoreProgressPayload(BaseModel):
    """Payload for GitHub restore progress updates."""
    job_id: str
    environment_id: str
    status: str  # running, completed, failed
    current: int
    total: int
    current_workflow_name: Optional[str] = None
    message: Optional[str] = None
    errors: Optional[List[str]] = None