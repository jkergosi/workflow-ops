from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class WorkflowMappingStatus(str, Enum):
    """
    Status for workflow environment mappings.

    Each workflow-environment mapping has exactly one status that represents its
    current state in the canonical workflow system.

    Status Definitions:
    -------------------
    LINKED: Workflow is canonically mapped and tracked. Has both a canonical_id
            and n8n_workflow_id. Represents normal operational state.

    UNTRACKED: Workflow exists in n8n but lacks a canonical mapping. Has an
               n8n_workflow_id but canonical_id is NULL. Requires manual linking
               or can be auto-linked if matching canonical workflow is found.

    MISSING: Workflow was previously mapped (LINKED or UNTRACKED) but disappeared
             from n8n during environment sync. Indicates workflow was deleted or
             deactivated in n8n but mapping record is retained for audit trail.

    IGNORED: Workflow is explicitly marked to be ignored by the system. User has
             indicated this workflow should not be tracked or managed canonically.

    DELETED: Workflow mapping has been soft-deleted. The canonical workflow or
             mapping was deleted but record is retained for historical tracking.

    Status Precedence Rules:
    ------------------------
    When multiple status conditions could theoretically apply to a single workflow,
    the system applies the following precedence (highest to lowest priority):

    1. DELETED - Takes precedence over all other states. Once deleted, a workflow
                 mapping is considered inactive regardless of other conditions.

    2. IGNORED - Takes precedence over operational states. User-explicit ignore
                 overrides system-computed states like MISSING or UNTRACKED.

    3. MISSING - Takes precedence over LINKED/UNTRACKED. If a workflow disappears
                 from n8n during sync, it transitions to MISSING regardless of
                 previous state. Reappearance triggers transition back to LINKED
                 (if has canonical_id) or UNTRACKED (if no canonical_id).

    4. UNTRACKED - Takes precedence over LINKED. If a workflow has no canonical_id,
                   it must be UNTRACKED even if it was previously linked.

    5. LINKED - Default operational state when workflow has both canonical_id and
                n8n_workflow_id and is present in n8n.

    State Transitions:
    ------------------
    - New workflow detected: → UNTRACKED (if no match) or LINKED (if auto-linked)
    - User links untracked workflow: UNTRACKED → LINKED
    - Workflow disappears from n8n: LINKED/UNTRACKED → MISSING
    - Missing workflow reappears: MISSING → LINKED (if canonical_id) or UNTRACKED
    - User marks workflow as ignored: any state → IGNORED
    - Workflow/mapping deleted: any state → DELETED

    UI Display Precedence:
    ----------------------
    In the workflow matrix view, when computing cell status for display, additional
    derived statuses may be shown based on content hash comparisons:
    - DRIFT: LINKED but env_content_hash ≠ git_content_hash (local changes)
    - OUT_OF_DATE: LINKED but git is newer than env (canonical ahead of env)

    These are computed display states, not persisted database statuses. The underlying
    database status remains LINKED while drift/out-of-date conditions are detected
    by comparing content hashes at query time.
    """
    LINKED = "linked"
    IGNORED = "ignored"
    DELETED = "deleted"
    UNTRACKED = "untracked"
    MISSING = "missing"


class LinkSuggestionStatus(str, Enum):
    """Status for workflow link suggestions"""
    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class WorkflowDiffStatus(str, Enum):
    """Diff status for workflow comparisons"""
    UNCHANGED = "unchanged"
    MODIFIED = "modified"
    ADDED = "added"
    TARGET_ONLY = "target_only"
    TARGET_HOTFIX = "target_hotfix"


# Canonical Workflow Models

class CanonicalWorkflowBase(BaseModel):
    canonical_id: str
    display_name: Optional[str] = None


class CanonicalWorkflowCreate(BaseModel):
    canonical_id: str
    created_by_user_id: Optional[str] = None
    display_name: Optional[str] = None


class CanonicalWorkflowResponse(BaseModel):
    tenant_id: str
    canonical_id: str
    created_at: datetime
    created_by_user_id: Optional[str] = None
    display_name: Optional[str] = None
    deleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# Canonical Workflow Git State Models

class CanonicalWorkflowGitStateBase(BaseModel):
    canonical_id: str
    git_path: str
    git_commit_sha: Optional[str] = None
    git_content_hash: str
    last_repo_sync_at: datetime


class CanonicalWorkflowGitStateResponse(BaseModel):
    tenant_id: str
    environment_id: str
    canonical_id: str
    git_path: str
    git_commit_sha: Optional[str] = None
    git_content_hash: str
    last_repo_sync_at: datetime

    model_config = {"from_attributes": True}


# Workflow Environment Mapping Models

class WorkflowEnvMapBase(BaseModel):
    canonical_id: str
    n8n_workflow_id: Optional[str] = None
    env_content_hash: str
    status: Optional[WorkflowMappingStatus] = None


class WorkflowEnvMapCreate(BaseModel):
    canonical_id: str
    n8n_workflow_id: Optional[str] = None
    env_content_hash: str
    linked_by_user_id: Optional[str] = None
    status: Optional[WorkflowMappingStatus] = None
    n8n_updated_at: Optional[datetime] = None


class WorkflowEnvMapUpdate(BaseModel):
    n8n_workflow_id: Optional[str] = None
    env_content_hash: Optional[str] = None
    status: Optional[WorkflowMappingStatus] = None
    linked_at: Optional[datetime] = None
    linked_by_user_id: Optional[str] = None
    n8n_updated_at: Optional[datetime] = None


class WorkflowEnvMapResponse(BaseModel):
    tenant_id: str
    environment_id: str
    canonical_id: str
    n8n_workflow_id: Optional[str] = None
    env_content_hash: str
    last_env_sync_at: datetime
    linked_at: Optional[datetime] = None
    linked_by_user_id: Optional[str] = None
    status: Optional[WorkflowMappingStatus] = None
    n8n_updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# Workflow Link Suggestion Models

class WorkflowLinkSuggestionBase(BaseModel):
    n8n_workflow_id: str
    canonical_id: str
    score: float
    reason: Optional[str] = None


class WorkflowLinkSuggestionCreate(BaseModel):
    n8n_workflow_id: str
    canonical_id: str
    score: float
    reason: Optional[str] = None


class WorkflowLinkSuggestionUpdate(BaseModel):
    status: LinkSuggestionStatus
    resolved_by_user_id: Optional[str] = None


class WorkflowLinkSuggestionResponse(BaseModel):
    id: str
    tenant_id: str
    environment_id: str
    n8n_workflow_id: str
    canonical_id: str
    score: float
    reason: Optional[str] = None
    status: LinkSuggestionStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by_user_id: Optional[str] = None

    model_config = {"from_attributes": True}


# Workflow Diff State Models

class WorkflowDiffStateBase(BaseModel):
    canonical_id: str
    diff_status: WorkflowDiffStatus
    computed_at: datetime


class WorkflowDiffStateResponse(BaseModel):
    id: str
    tenant_id: str
    source_env_id: str
    target_env_id: str
    canonical_id: str
    diff_status: WorkflowDiffStatus
    computed_at: datetime

    model_config = {"from_attributes": True}


# Onboarding Models

class OnboardingPreflightResponse(BaseModel):
    is_pre_canonical: bool
    has_legacy_workflows: bool
    has_legacy_git_layout: bool
    environments: List[Dict[str, Any]]


class OnboardingInventoryRequest(BaseModel):
    anchor_environment_id: str
    environment_configs: List[Dict[str, str]] = Field(
        ...,
        description="List of {environment_id, git_repo_url, git_folder} configs"
    )


class OnboardingInventoryResponse(BaseModel):
    job_id: str
    status: str
    message: str


class MigrationPRRequest(BaseModel):
    tenant_slug: str = Field(..., description="Validated tenant slug for branch name")


class MigrationPRResponse(BaseModel):
    pr_url: Optional[str] = None
    branch_name: str
    commit_sha: Optional[str] = None
    error: Optional[str] = None


class OnboardingCompleteCheck(BaseModel):
    is_complete: bool
    missing_repo_syncs: List[str] = Field(default_factory=list)
    missing_env_syncs: List[str] = Field(default_factory=list)
    untracked_workflows: int = 0
    unresolved_suggestions: int = 0
    message: str


# Enhanced Onboarding Inventory Result Models

class WorkflowInventoryResult(BaseModel):
    """Individual workflow result from inventory operation"""
    environment_id: str
    environment_name: str
    workflow_id: Optional[str] = None
    workflow_name: Optional[str] = None
    canonical_id: Optional[str] = None
    status: str = Field(..., description="Status: success, error, skipped")
    error: Optional[str] = None
    is_new_untracked: Optional[bool] = None


class EnvironmentInventoryResult(BaseModel):
    """Per-environment summary from inventory operation"""
    environment_id: str
    environment_name: str
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    created_count: Optional[int] = None
    linked_count: Optional[int] = None
    untracked_count: Optional[int] = None


class OnboardingInventoryResults(BaseModel):
    """
    Comprehensive results from onboarding inventory phase.

    Provides both aggregated counts (backwards compatible) and detailed
    per-workflow/per-environment tracking for UI display and debugging.
    """
    # Aggregated counts (backwards compatible)
    workflows_inventoried: int = 0
    canonical_ids_generated: int = 0
    auto_links: int = 0
    suggested_links: int = 0
    untracked_workflows: int = 0

    # Error summary
    errors: List[str] = Field(default_factory=list)
    has_errors: bool = Field(False, description="True if any errors occurred")

    # Detailed per-workflow results
    workflow_results: List[WorkflowInventoryResult] = Field(
        default_factory=list,
        description="Per-workflow status tracking for detailed UI display"
    )

    # Per-environment summaries
    environment_results: Dict[str, EnvironmentInventoryResult] = Field(
        default_factory=dict,
        description="Per-environment operation summaries"
    )

