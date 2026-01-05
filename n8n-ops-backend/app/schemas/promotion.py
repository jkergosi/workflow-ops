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


# =============================================================================
# NEW: Authoritative Diff Status (Azure-aligned)
# =============================================================================

class DiffStatus(str, Enum):
    """
    Canonical diff status for workflow comparison.
    Frontend must use these values directly - no local computation.
    """
    ADDED = "added"              # Exists only in source
    MODIFIED = "modified"        # Exists in both, content differs, source newer
    DELETED = "deleted"          # Exists only in target (target-only)
    UNCHANGED = "unchanged"      # Normalized content identical
    TARGET_HOTFIX = "target_hotfix"  # Content differs, target newer


class ChangeCategory(str, Enum):
    """
    Semantic change categories for understanding what changed.
    Computed from structured diff facts, not from raw JSON inspection.
    """
    NODE_ADDED = "node_added"
    NODE_REMOVED = "node_removed"
    NODE_TYPE_CHANGED = "node_type_changed"
    CREDENTIALS_CHANGED = "credentials_changed"
    EXPRESSIONS_CHANGED = "expressions_changed"
    HTTP_CHANGED = "http_changed"
    TRIGGER_CHANGED = "trigger_changed"
    ROUTING_CHANGED = "routing_changed"
    ERROR_HANDLING_CHANGED = "error_handling_changed"
    SETTINGS_CHANGED = "settings_changed"
    RENAME_ONLY = "rename_only"
    CODE_CHANGED = "code_changed"  # Code/Function node changes


class RiskLevel(str, Enum):
    """
    Risk level based on change categories.
    High: credentials, expressions, triggers, HTTP, code, routing
    Medium: error handling, settings
    Low: rename only, metadata
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# =============================================================================
# NEW: Compare Response Schemas
# =============================================================================

class WorkflowCompareResult(BaseModel):
    """
    Per-workflow comparison result.
    This is the authoritative source for diff status - frontend must not compute this.
    """
    workflow_id: str
    name: str
    diff_status: DiffStatus
    risk_level: RiskLevel
    change_categories: List[ChangeCategory] = []
    diff_hash: Optional[str] = None  # For caching AI summaries
    details_available: bool = True
    source_updated_at: Optional[datetime] = None
    target_updated_at: Optional[datetime] = None
    enabled_in_source: bool = False
    enabled_in_target: Optional[bool] = None


class CompareSummary(BaseModel):
    """Summary counts for the promotion compare result."""
    total: int
    added: int
    modified: int
    deleted: int  # target-only workflows
    unchanged: int
    target_hotfix: int


class PromotionCompareResult(BaseModel):
    """
    Complete comparison result for a pipeline stage.
    Frontend calls this once per stage selection - never computes diff locally.
    """
    pipeline_id: str
    stage_id: str
    source_env_id: str
    target_env_id: str
    summary: CompareSummary
    workflows: List[WorkflowCompareResult]


# =============================================================================
# LEGACY: WorkflowChangeType (to be removed in Phase 6)
# =============================================================================

class WorkflowChangeType(str, Enum):
    """
    DEPRECATED: Use DiffStatus instead.
    Kept temporarily for backward compatibility during migration.
    """
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


# =============================================================================
# NEW: Diff Summary Response (AI-generated)
# =============================================================================

class DiffSummaryResponse(BaseModel):
    """
    AI-generated summary of workflow differences.
    Generated from structured diff facts, cached by diff_hash.
    """
    bullets: List[str]  # 3-6 summary bullet points
    risk_level: RiskLevel
    risk_explanation: str
    evidence_map: Dict[str, List[str]] = {}  # bullet -> supporting facts
    change_categories: List[ChangeCategory] = []
    is_new_workflow: bool = False
    cached: bool = False

