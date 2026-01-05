from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class WorkflowMappingStatus(str, Enum):
    """Status for workflow environment mappings"""
    LINKED = "linked"
    IGNORED = "ignored"
    DELETED = "deleted"


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


class WorkflowEnvMapUpdate(BaseModel):
    n8n_workflow_id: Optional[str] = None
    env_content_hash: Optional[str] = None
    status: Optional[WorkflowMappingStatus] = None
    linked_at: Optional[datetime] = None
    linked_by_user_id: Optional[str] = None


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

