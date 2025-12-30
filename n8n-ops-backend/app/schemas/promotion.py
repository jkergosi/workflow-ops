from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class PromotionStatus(str, Enum):
    PENDING = "pending"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowChangeType(str, Enum):
    NEW = "new"
    CHANGED = "changed"
    STAGING_HOTFIX = "staging_hotfix"
    CONFLICT = "conflict"
    UNCHANGED = "unchanged"


class WorkflowSelection(BaseModel):
    workflow_id: str
    workflow_name: str
    change_type: WorkflowChangeType
    enabled_in_source: bool
    enabled_in_target: Optional[bool] = None
    selected: bool = False
    requires_overwrite: bool = False


class GateResult(BaseModel):
    require_clean_drift: bool
    drift_detected: bool
    drift_resolved: bool = False
    run_pre_flight_validation: bool
    credentials_exist: bool = True
    nodes_supported: bool = True
    webhooks_available: bool = True
    target_environment_healthy: bool = True
    risk_level_allowed: bool = True
    errors: List[str] = []
    warnings: List[str] = []
    credential_issues: List[Dict[str, Any]] = []


class PromotionInitiateRequest(BaseModel):
    pipeline_id: str
    source_environment_id: str
    target_environment_id: str
    workflow_selections: List[WorkflowSelection]


class DependencyWarning(BaseModel):
    workflow_id: str
    workflow_name: str
    reason: str  # "differs_in_target" | "missing_in_target"
    message: str


class PromotionInitiateResponse(BaseModel):
    promotion_id: str
    status: PromotionStatus
    gate_results: GateResult
    requires_approval: bool
    approval_id: Optional[str] = None
    dependency_warnings: Dict[str, List[DependencyWarning]] = {}  # workflow_id -> list of missing deps
    preflight: Optional[Dict[str, Any]] = None
    message: str


class PromotionApprovalRequest(BaseModel):
    action: str  # "approve" or "reject"
    comment: Optional[str] = None


class PromotionExecuteRequest(BaseModel):
    scheduled_at: Optional[datetime] = None  # If provided, schedule deployment for this time. If None, execute immediately.


class PromotionExecutionResult(BaseModel):
    promotion_id: str
    status: PromotionStatus
    workflows_promoted: int
    workflows_failed: int
    workflows_skipped: int
    source_snapshot_id: str
    target_pre_snapshot_id: str
    target_post_snapshot_id: str
    errors: List[str] = []
    warnings: List[str] = []
    created_placeholders: List[str] = []


class ApprovalRecord(BaseModel):
    approver_id: str
    approved_at: str
    comment: Optional[str] = None


class PromotionDetail(BaseModel):
    id: str
    tenant_id: str
    pipeline_id: str
    pipeline_name: str
    source_environment_id: str
    source_environment_name: str
    target_environment_id: str
    target_environment_name: str
    status: PromotionStatus
    source_snapshot_id: Optional[str] = None
    target_pre_snapshot_id: Optional[str] = None
    target_post_snapshot_id: Optional[str] = None
    workflow_selections: List[WorkflowSelection]
    gate_results: Optional[GateResult] = None
    dependency_warnings: Optional[Dict[str, List[DependencyWarning]]] = None
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approvals: List[ApprovalRecord] = []  # List of all approvals
    rejection_reason: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    execution_result: Optional[PromotionExecutionResult] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class PromotionListResponse(BaseModel):
    data: List[PromotionDetail]
    total: int


class PromotionSnapshotRequest(BaseModel):
    environment_id: str
    reason: str
    metadata: Optional[Dict[str, Any]] = None


class PromotionSnapshotResponse(BaseModel):
    snapshot_id: str
    commit_sha: str
    workflows_count: int
    created_at: datetime


class PromotionDriftCheck(BaseModel):
    has_drift: bool
    drift_details: List[Dict[str, Any]] = []
    can_proceed: bool = False
    requires_sync: bool = False

