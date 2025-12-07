from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class SubscriptionPlan(str, Enum):
    free = "free"
    pro = "pro"
    enterprise = "enterprise"


class TenantStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    pending = "pending"


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    subscription_plan: SubscriptionPlan = SubscriptionPlan.free


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    subscription_plan: Optional[SubscriptionPlan] = None
    status: Optional[TenantStatus] = None


class TenantResponse(BaseModel):
    id: str
    name: str
    email: str
    subscription_plan: SubscriptionPlan
    status: TenantStatus
    workflow_count: int = 0
    environment_count: int = 0
    user_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantStats(BaseModel):
    total: int
    active: int
    suspended: int
    pending: int
    by_plan: dict
