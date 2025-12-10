from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from datetime import datetime
from enum import Enum


# EnvironmentType enum removed - type is now optional and free-form
# Kept for backward compatibility but not enforced
class EnvironmentType(str, Enum):
    dev = "dev"
    staging = "staging"
    production = "production"


class EnvironmentBase(BaseModel):
    n8n_name: str = Field(..., min_length=1, max_length=255)
    n8n_type: Optional[str] = Field(None, max_length=50)  # Optional metadata for display/sorting only
    n8n_base_url: str = Field(..., min_length=1, max_length=500)
    n8n_api_key: Optional[str] = None
    n8n_encryption_key: Optional[str] = None
    is_active: bool = True
    allow_upload: bool = False  # Feature flag: true if workflows can be uploaded from this environment
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
    git_repo_url: Optional[str] = Field(None, max_length=500)
    git_branch: Optional[str] = Field(None, max_length=255)
    git_pat: Optional[str] = None


class EnvironmentResponse(BaseModel):
    """Response model for environments with n8n_ prefixed field names"""
    id: str
    tenant_id: str
    n8n_name: str
    n8n_type: Optional[str] = None  # Optional metadata for display/sorting only
    n8n_base_url: str
    n8n_api_key: Optional[str] = None
    n8n_encryption_key: Optional[str] = None
    is_active: bool = True
    allow_upload: bool = False  # Feature flag
    git_repo_url: Optional[str] = None
    git_branch: Optional[str] = None
    git_pat: Optional[str] = None
    last_connected: Optional[datetime] = None
    last_backup: Optional[datetime] = None
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
