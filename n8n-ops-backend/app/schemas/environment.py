from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from datetime import datetime
from enum import Enum


# Legacy EnvironmentType enum - deprecated, use EnvironmentClass instead
# Kept for backward compatibility but not enforced
class EnvironmentType(str, Enum):
    dev = "dev"
    staging = "staging"
    production = "production"


# NEW: Deterministic environment class for policy enforcement
# This is the ONLY source of truth for workflow action policies
class EnvironmentClass(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentBase(BaseModel):
    n8n_name: str = Field(..., min_length=1, max_length=255)
    n8n_type: Optional[str] = Field(None, max_length=50)  # Optional metadata for display/sorting only
    n8n_base_url: str = Field(..., min_length=1, max_length=500)
    n8n_api_key: Optional[str] = None
    n8n_encryption_key: Optional[str] = None
    is_active: bool = True
    allow_upload: bool = False  # Feature flag: true if workflows can be uploaded from this environment
    environment_class: EnvironmentClass = EnvironmentClass.DEV  # Deterministic class for policy enforcement
    git_repo_url: Optional[str] = Field(None, max_length=500)
    git_branch: Optional[str] = Field(None, max_length=255)
    git_pat: Optional[str] = None


class EnvironmentCreate(EnvironmentBase):
    pass


class EnvironmentUpdate(BaseModel):
    n8n_name: Optional[str] = Field(None, min_length=1, max_length=255)
    n8n_type: Optional[str] = Field(None, max_length=50)  # Optional metadata for display/sorting only
    n8n_base_url: Optional[str] = Field(None, min_length=1, max_length=500)
    n8n_api_key: Optional[str] = None
    n8n_encryption_key: Optional[str] = None
    is_active: Optional[bool] = None
    allow_upload: Optional[bool] = None  # Feature flag
    environment_class: Optional[EnvironmentClass] = None  # Deterministic class for policy enforcement
    git_repo_url: Optional[str] = Field(None, max_length=500)
    git_branch: Optional[str] = Field(None, max_length=255)
    git_pat: Optional[str] = None
    drift_handling_mode: Optional[str] = Field(None, max_length=50)


class EnvironmentResponse(BaseModel):
    """Response model for environments with n8n_ prefixed field names"""
    # Migration: 53259882566d - add_drift_fields_and_incidents
    # See: alembic/versions/53259882566d_add_drift_fields_and_incidents.py
    # Migration: 76c6e9c7f4fe - add_drift_handling_mode_to_environments
    # See: alembic/versions/76c6e9c7f4fe_add_drift_handling_mode_to_environments.py
    # Migration: add_environment_class - workflow governance policy enforcement
    id: str
    tenant_id: str
    n8n_name: str
    n8n_type: Optional[str] = None  # Optional metadata for display/sorting only
    n8n_base_url: str
    n8n_api_key: Optional[str] = None
    n8n_encryption_key: Optional[str] = None
    is_active: bool = True
    allow_upload: bool = False  # Feature flag
    environment_class: EnvironmentClass = EnvironmentClass.DEV  # Deterministic class for policy
    git_repo_url: Optional[str] = None
    git_branch: Optional[str] = None
    git_pat: Optional[str] = None
    last_connected: Optional[datetime] = None
    last_backup: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    last_drift_check_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    drift_status: str = "IN_SYNC"
    last_drift_detected_at: Optional[datetime] = None
    active_drift_incident_id: Optional[str] = None
    drift_handling_mode: str = "warn_only"
    workflow_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EnvironmentTestConnection(BaseModel):
    n8n_base_url: str
    n8n_api_key: str


class GitTestConnection(BaseModel):
    git_repo_url: str
    git_branch: str = "main"
    git_pat: Optional[str] = None
