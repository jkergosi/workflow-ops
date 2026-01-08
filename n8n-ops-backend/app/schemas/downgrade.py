"""
Downgrade Grace Period Schema Models

Pydantic models for downgrade grace period tracking.
These models represent resources that are over-limit after a plan downgrade
and are in a grace period before action is taken.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class GracePeriodStatus(str, Enum):
    """Status of a resource in grace period."""
    ACTIVE = "active"
    WARNING = "warning"
    EXPIRED = "expired"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class ResourceType(str, Enum):
    """Types of resources that can be affected by downgrades."""
    ENVIRONMENT = "environment"
    TEAM_MEMBER = "team_member"
    WORKFLOW = "workflow"
    EXECUTION = "execution"
    AUDIT_LOG = "audit_log"
    SNAPSHOT = "snapshot"


class DowngradeAction(str, Enum):
    """Actions that can be taken when a resource exceeds plan limits."""
    READ_ONLY = "read_only"
    SCHEDULE_DELETION = "schedule_deletion"
    DISABLE = "disable"
    IMMEDIATE_DELETE = "immediate_delete"
    WARN_ONLY = "warn_only"
    ARCHIVE = "archive"


class DowngradeGracePeriodBase(BaseModel):
    """Base model for downgrade grace period records."""
    tenant_id: str = Field(..., description="Tenant ID that owns the resource")
    resource_type: ResourceType = Field(..., description="Type of resource in grace period")
    resource_id: str = Field(..., description="ID of the specific resource")
    action: DowngradeAction = Field(..., description="Action to take when grace period expires")
    status: GracePeriodStatus = Field(default=GracePeriodStatus.ACTIVE, description="Current status")
    starts_at: datetime = Field(..., description="When the grace period started")
    expires_at: datetime = Field(..., description="When the grace period expires")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for grace period")
    metadata: Optional[dict] = Field(None, description="Additional metadata (JSON)")


class DowngradeGracePeriodCreate(DowngradeGracePeriodBase):
    """Model for creating a new grace period record."""
    pass


class DowngradeGracePeriodUpdate(BaseModel):
    """Model for updating a grace period record."""
    status: Optional[GracePeriodStatus] = None
    expires_at: Optional[datetime] = None
    reason: Optional[str] = Field(None, max_length=500)
    metadata: Optional[dict] = None


class DowngradeGracePeriodResponse(DowngradeGracePeriodBase):
    """Response model for grace period records."""
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GracePeriodSummary(BaseModel):
    """Summary of grace periods for a tenant."""
    tenant_id: str
    active_count: int = 0
    expired_count: int = 0
    by_resource_type: dict = Field(default_factory=dict)
    expiring_soon: list = Field(default_factory=list)  # List of grace periods expiring within 7 days
