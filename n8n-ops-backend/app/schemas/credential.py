from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class WorkflowReference(BaseModel):
    """Reference to a workflow that uses this credential"""
    id: str
    name: str
    n8n_workflow_id: Optional[str] = None


class CredentialBase(BaseModel):
    """Base credential model with common fields"""
    name: str = Field(..., description="Credential name")
    type: str = Field(..., description="Credential type (e.g., 'slackApi', 'githubApi')")


class CredentialCreate(CredentialBase):
    """Schema for creating a new credential"""
    data: Dict[str, Any] = Field(..., description="The credential data/secrets (encrypted by N8N)")
    environment_id: str = Field(..., description="Environment to create the credential in")


class CredentialUpdate(BaseModel):
    """Schema for updating an existing credential"""
    name: Optional[str] = Field(None, description="New credential name")
    data: Optional[Dict[str, Any]] = Field(None, description="New credential data/secrets")


class CredentialResponse(CredentialBase):
    """Response model for a credential (metadata only, no secrets)"""
    id: str
    n8n_credential_id: Optional[str] = None
    tenant_id: Optional[str] = None
    environment_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    used_by_workflows: List[WorkflowReference] = []
    environment: Optional[Dict[str, Any]] = None  # Environment info for display

    class Config:
        from_attributes = True


class CredentialTypeField(BaseModel):
    """Schema field for a credential type"""
    displayName: str
    name: str
    type: str
    default: Optional[Any] = None
    required: Optional[bool] = False
    description: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None


class CredentialTypeSchema(BaseModel):
    """Schema for a credential type (used for building forms)"""
    name: str
    displayName: str
    properties: List[CredentialTypeField] = []
    documentationUrl: Optional[str] = None


class CredentialSyncResult(BaseModel):
    """Result of syncing credentials from N8N"""
    success: bool
    synced: int
    errors: List[str] = []
    message: str
