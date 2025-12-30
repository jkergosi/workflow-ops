from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"


class SnapshotType(str, Enum):
    AUTO_BACKUP = "auto_backup"
    PRE_PROMOTION = "pre_promotion"
    POST_PROMOTION = "post_promotion"
    MANUAL_BACKUP = "manual_backup"


class WorkflowChangeType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    SKIPPED = "skipped"
    UNCHANGED = "unchanged"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNCHANGED = "unchanged"


# Snapshot schemas
class SnapshotBase(BaseModel):
    environment_id: str
    git_commit_sha: str
    type: SnapshotType
    created_by_user_id: Optional[str] = None
    related_deployment_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class SnapshotCreate(SnapshotBase):
    tenant_id: str


class SnapshotResponse(SnapshotBase):
    id: str
    tenant_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# Deployment schemas
class DeploymentBase(BaseModel):
    pipeline_id: Optional[str] = None
    source_environment_id: str
    target_environment_id: str
    status: DeploymentStatus = DeploymentStatus.PENDING
    triggered_by_user_id: str
    approved_by_user_id: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    pre_snapshot_id: Optional[str] = None
    post_snapshot_id: Optional[str] = None
    summary_json: Optional[Dict[str, Any]] = None
    deleted_at: Optional[datetime] = None
    deleted_by_user_id: Optional[str] = None


class DeploymentCreate(DeploymentBase):
    tenant_id: str


class DeploymentUpdate(BaseModel):
    status: Optional[DeploymentStatus] = None
    finished_at: Optional[datetime] = None
    pre_snapshot_id: Optional[str] = None
    post_snapshot_id: Optional[str] = None
    summary_json: Optional[Dict[str, Any]] = None


class DeploymentResponse(DeploymentBase):
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime
    # Progress helpers for UI (derived from summary_json)
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None
    current_workflow_name: Optional[str] = None

    class Config:
        from_attributes = True


# DeploymentWorkflow schemas
class DeploymentWorkflowBase(BaseModel):
    workflow_id: str
    workflow_name_at_time: str
    change_type: WorkflowChangeType
    status: WorkflowStatus = WorkflowStatus.PENDING
    error_message: Optional[str] = None


class DeploymentWorkflowCreate(DeploymentWorkflowBase):
    deployment_id: str


class DeploymentWorkflowResponse(DeploymentWorkflowBase):
    id: str
    deployment_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# Response models with related data
class DeploymentDetailResponse(DeploymentResponse):
    workflows: List[DeploymentWorkflowResponse] = []
    pre_snapshot: Optional[SnapshotResponse] = None
    post_snapshot: Optional[SnapshotResponse] = None


class DeploymentListResponse(BaseModel):
    deployments: List[DeploymentResponse]
    total: int
    page: int
    page_size: int
    this_week_success_count: int
    pending_approvals_count: int

