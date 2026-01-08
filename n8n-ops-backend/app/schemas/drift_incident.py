"""Drift Incident schemas for lifecycle management."""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class DriftIncidentStatus(str, Enum):
    """Drift incident lifecycle states."""
    detected = "detected"
    acknowledged = "acknowledged"
    stabilized = "stabilized"
    reconciled = "reconciled"
    closed = "closed"


class DriftSeverity(str, Enum):
    """Drift severity levels (Agency+ feature)."""
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ResolutionType(str, Enum):
    """How drift was resolved."""
    promote = "promote"      # Runtime changes promoted to Git
    revert = "revert"        # Runtime reverted to match Git
    replace = "replace"      # Git updated via external process
    acknowledge = "acknowledge"  # Drift accepted (no reconciliation)


class AffectedWorkflow(BaseModel):
    """Workflow affected by drift."""
    workflow_id: str
    workflow_name: str
    drift_type: str  # 'modified', 'missing_in_git', 'missing_in_runtime'
    n8n_workflow_id: Optional[str] = None
    change_summary: Optional[str] = None


class DriftIncidentCreate(BaseModel):
    """Create a new drift incident."""
    environment_id: str = Field(..., min_length=1)
    title: Optional[str] = Field(None, max_length=255)
    affected_workflows: List[AffectedWorkflow] = Field(default_factory=list)
    drift_snapshot: Optional[Dict[str, Any]] = None
    severity: Optional[DriftSeverity] = None


class DriftIncidentUpdate(BaseModel):
    """Update drift incident fields."""
    title: Optional[str] = Field(None, max_length=255)
    owner_user_id: Optional[str] = None
    reason: Optional[str] = None
    ticket_ref: Optional[str] = None
    expires_at: Optional[datetime] = None
    severity: Optional[DriftSeverity] = None


class DriftIncidentTransition(BaseModel):
    """Transition incident to a new status."""
    status: DriftIncidentStatus
    reason: Optional[str] = None
    ticket_ref: Optional[str] = None
    admin_override: bool = Field(
        default=False,
        description="Admin-only flag to bypass state transition validation rules. "
                    "Allows admins to force transitions that would normally be invalid "
                    "(e.g., skipping required states or reopening closed incidents)."
    )


class DriftIncidentAcknowledge(BaseModel):
    """Acknowledge a drift incident."""
    reason: Optional[str] = None
    owner_user_id: Optional[str] = None
    ticket_ref: Optional[str] = None
    expires_at: Optional[datetime] = None  # Agency+ TTL
    admin_override: bool = Field(
        default=False,
        description="Admin-only flag to bypass state transition validation rules."
    )


class DriftIncidentStabilize(BaseModel):
    """Stabilize a drift incident."""
    reason: Optional[str] = None
    admin_override: bool = Field(
        default=False,
        description="Admin-only flag to bypass state transition validation rules."
    )


class DriftIncidentResolve(BaseModel):
    """Resolve/reconcile a drift incident."""
    resolution_type: ResolutionType
    reason: Optional[str] = None
    resolution_details: Optional[Dict[str, Any]] = None
    admin_override: bool = Field(
        default=False,
        description="Admin-only flag to bypass state transition validation rules."
    )


class DriftIncidentClose(BaseModel):
    """Close a drift incident.

    Validation requirements depend on current incident status:
    - Closing from detected/acknowledged/stabilized: requires resolution_type AND reason
    - Closing from reconciled: requires reason (resolution notes)
    """
    reason: Optional[str] = Field(
        None,
        description="Resolution notes explaining the closure. Required for all closures."
    )
    resolution_type: Optional[ResolutionType] = Field(
        None,
        description="How the incident was resolved. Required when closing from pre-reconciliation states (detected/acknowledged/stabilized)."
    )
    admin_override: bool = Field(
        default=False,
        description="Admin-only flag to bypass state transition validation rules."
    )


class DriftIncidentResponse(BaseModel):
    """Full drift incident response."""
    id: str
    tenant_id: str
    environment_id: str
    status: DriftIncidentStatus = DriftIncidentStatus.detected
    title: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None

    # Lifecycle timestamps
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    detected_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    stabilized_at: Optional[datetime] = None
    stabilized_by: Optional[str] = None
    reconciled_at: Optional[datetime] = None
    reconciled_by: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None

    # Ownership
    owner_user_id: Optional[str] = None
    reason: Optional[str] = None
    ticket_ref: Optional[str] = None

    # Agency+ fields
    expires_at: Optional[datetime] = None
    severity: Optional[DriftSeverity] = None

    # Drift data (may be null if purged per retention policy)
    affected_workflows: List[Dict[str, Any]] = Field(default_factory=list)
    drift_snapshot: Optional[Dict[str, Any]] = None

    # Resolution tracking
    resolution_type: Optional[ResolutionType] = None
    resolution_details: Optional[Dict[str, Any]] = None

    # Retention/soft-delete fields
    payload_purged_at: Optional[datetime] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    # Computed property-like field for UI convenience
    payload_available: bool = True

    model_config = {"from_attributes": True}


class DriftIncidentListResponse(BaseModel):
    """List response with pagination info."""
    items: List[DriftIncidentResponse]
    total: int
    has_more: bool


# Reconciliation Artifact Schemas
class ReconciliationStatus(str, Enum):
    """Status of a reconciliation artifact."""
    pending = "pending"
    in_progress = "in_progress"
    success = "success"
    failed = "failed"


class ReconciliationArtifactCreate(BaseModel):
    """Create a reconciliation artifact."""
    incident_id: str
    type: ResolutionType
    affected_workflows: List[str] = Field(default_factory=list)  # List of workflow IDs


class ReconciliationArtifactResponse(BaseModel):
    """Reconciliation artifact response."""
    id: str
    tenant_id: str
    incident_id: str
    type: ResolutionType
    status: ReconciliationStatus = ReconciliationStatus.pending
    started_at: Optional[datetime] = None
    started_by: Optional[str] = None
    finished_at: Optional[datetime] = None
    affected_workflows: List[Dict[str, Any]] = Field(default_factory=list)
    external_refs: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
