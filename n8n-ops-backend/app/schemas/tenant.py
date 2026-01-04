from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class SubscriptionPlan(str, Enum):
    free = "free"
    pro = "pro"
    agency = "agency"
    enterprise = "enterprise"


class TenantStatus(str, Enum):
    active = "active"
    trial = "trial"
    suspended = "suspended"
    cancelled = "cancelled"
    archived = "archived"
    pending = "pending"


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    # subscription_plan removed - tenants now use provider-scoped subscriptions


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    # subscription_plan removed - tenants now use provider-scoped subscriptions
    status: Optional[TenantStatus] = None
    primary_contact_name: Optional[str] = None


class TenantProviderSubscriptionSummary(BaseModel):
    """Summary of provider subscription for tenant list."""
    id: str
    provider_id: str
    plan_id: str
    status: str
    stripe_subscription_id: Optional[str] = None
    provider: dict  # {id, name, display_name}
    plan: dict  # {id, name, display_name}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TenantResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: str
    name: str
    email: str
    status: TenantStatus
    workflow_count: int = 0
    environment_count: int = 0
    user_count: int = 0
    primary_contact_name: Optional[str] = None
    last_active_at: Optional[datetime] = None
    scheduled_deletion_at: Optional[datetime] = None
    stripe_customer_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    provider_subscriptions: List[TenantProviderSubscriptionSummary] = []
    provider_count: int = 0


class TenantListResponse(BaseModel):
    tenants: List[TenantResponse]
    total: int
    page: int
    page_size: int


class TenantStats(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    total: int
    active: int
    suspended: int
    pending: int
    trial: int = 0
    cancelled: int = 0
    with_providers: int = 0
    no_providers: int = 0
    by_plan: dict = {}  # Deprecated, kept for backward compatibility


class TenantNoteCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class TenantNoteResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    id: str
    tenant_id: str
    author_id: Optional[str] = None
    author_email: Optional[str] = None
    author_name: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime


class TenantNoteListResponse(BaseModel):
    notes: List[TenantNoteResponse]
    total: int


class ScheduleDeletionRequest(BaseModel):
    retention_days: int = Field(30, ge=30, le=90)
