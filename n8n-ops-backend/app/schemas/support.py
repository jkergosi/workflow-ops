from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class IntentKind(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    TASK = "task"


class Severity(str, Enum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"


class Frequency(str, Enum):
    ONCE = "once"
    INTERMITTENT = "intermittent"
    ALWAYS = "always"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Issue Contract v1 - canonical payload for n8n
class IssueContractApp(BaseModel):
    app_id: str = "workflow-ops"
    app_env: str
    app_version: Optional[str] = None
    git_sha: Optional[str] = None


class IssueContractActor(BaseModel):
    user_id: Optional[str] = None
    email: str


class IssueContractSource(BaseModel):
    channel: str = "in_app"
    actor_type: str = "user"
    actor: IssueContractActor


class IssueContractIntent(BaseModel):
    kind: IntentKind
    title: str
    description: str
    requested_outcome: Optional[str] = None
    acceptance_criteria: Optional[List[str]] = None


class IssueContractContext(BaseModel):
    tenant_id: str
    workspace_id: Optional[str] = None
    route: Optional[str] = None
    environment: str
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None


class IssueContractImpact(BaseModel):
    severity: Optional[Severity] = None
    scope: Optional[str] = None
    frequency: Optional[Frequency] = None


class IssueContractFullStory(BaseModel):
    session_url: Optional[str] = None
    session_id: Optional[str] = None


class IssueContractLogEntry(BaseModel):
    kind: str
    url: Optional[str] = None
    excerpt: Optional[str] = None


class IssueContractAttachment(BaseModel):
    name: str
    url: str
    content_type: str


class IssueContractEvidence(BaseModel):
    fullstory: Optional[IssueContractFullStory] = None
    logs: Optional[List[IssueContractLogEntry]] = None
    attachments: Optional[List[IssueContractAttachment]] = None


class IssueContractAutomation(BaseModel):
    ai_autonomy: str = "approval_required"
    risk: str = "low"
    constraints: Optional[List[str]] = None


class IssueContractLinkage(BaseModel):
    jsm_request_key: Optional[str] = None
    jira_issue_key: Optional[str] = None
    github_repo: Optional[str] = None


class IssueContractV1(BaseModel):
    schema_version: str = "1.0"
    event_id: str
    created_at: str
    app: IssueContractApp
    source: IssueContractSource
    intent: IssueContractIntent
    context: IssueContractContext
    impact: Optional[IssueContractImpact] = None
    evidence: Optional[IssueContractEvidence] = None
    automation: Optional[IssueContractAutomation] = None
    linkage: Optional[IssueContractLinkage] = None


# Request models for API endpoints
class BugReportCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    what_happened: str = Field(..., min_length=1, max_length=5000)
    expected_behavior: str = Field(..., min_length=1, max_length=5000)
    steps_to_reproduce: Optional[str] = Field(None, max_length=5000)
    severity: Optional[Severity] = None
    frequency: Optional[Frequency] = None
    include_diagnostics: bool = True
    attachments: Optional[List[IssueContractAttachment]] = None


class FeatureRequestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    problem_goal: str = Field(..., min_length=1, max_length=5000)
    desired_outcome: str = Field(..., min_length=1, max_length=5000)
    priority: Optional[Priority] = None
    acceptance_criteria: Optional[List[str]] = None
    who_is_this_for: Optional[str] = Field(None, max_length=1000)


class HelpRequestCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    details: str = Field(..., min_length=1, max_length=5000)
    include_diagnostics: bool = True
    attachments: Optional[List[IssueContractAttachment]] = None


class SupportRequestCreate(BaseModel):
    intent_kind: IntentKind
    bug_report: Optional[BugReportCreate] = None
    feature_request: Optional[FeatureRequestCreate] = None
    help_request: Optional[HelpRequestCreate] = None

    # Diagnostics data (collected from frontend)
    diagnostics: Optional[Dict[str, Any]] = None


class SupportRequestResponse(BaseModel):
    jsm_request_key: str


# Upload URL models
class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str


class UploadUrlResponse(BaseModel):
    upload_url: str
    public_url: str


# Admin config models
class SupportConfigBase(BaseModel):
    n8n_webhook_url: Optional[str] = None
    n8n_api_key: Optional[str] = None
    jsm_portal_url: Optional[str] = None
    jsm_cloud_instance: Optional[str] = None
    jsm_api_token: Optional[str] = None
    jsm_project_key: Optional[str] = None
    jsm_bug_request_type_id: Optional[str] = None
    jsm_feature_request_type_id: Optional[str] = None
    jsm_help_request_type_id: Optional[str] = None
    jsm_widget_embed_code: Optional[str] = None


class SupportConfigUpdate(SupportConfigBase):
    pass


class SupportConfigResponse(SupportConfigBase):
    tenant_id: str
    updated_at: Optional[datetime] = None
