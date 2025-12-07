from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class EnvironmentType(str, Enum):
    dev = "dev"
    staging = "staging"
    production = "production"


class EnvironmentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: EnvironmentType
    base_url: str = Field(..., min_length=1, max_length=500)
    api_key: Optional[str] = None
    is_active: bool = True
    git_repo_url: Optional[str] = Field(None, max_length=500)
    git_branch: Optional[str] = Field(None, max_length=255)
    git_pat: Optional[str] = None
    n8n_encryption_key: Optional[str] = None


class EnvironmentCreate(EnvironmentBase):
    pass


class EnvironmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    base_url: Optional[str] = Field(None, min_length=1, max_length=500)
    api_key: Optional[str] = None
    is_active: Optional[bool] = None
    git_repo_url: Optional[str] = Field(None, max_length=500)
    git_branch: Optional[str] = Field(None, max_length=255)
    git_pat: Optional[str] = None
    n8n_encryption_key: Optional[str] = None


class EnvironmentResponse(EnvironmentBase):
    id: str
    tenant_id: str
    last_connected: Optional[datetime] = None
    last_backup: Optional[datetime] = None
    workflow_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EnvironmentTestConnection(BaseModel):
    base_url: str
    api_key: str


class GitTestConnection(BaseModel):
    git_repo_url: str
    git_branch: str = "main"
    git_pat: Optional[str] = None
