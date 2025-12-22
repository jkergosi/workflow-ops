"""Provider schemas for automation platform subscriptions."""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


class ProviderBase(BaseModel):
    """Base provider schema."""
    name: str
    display_name: str
    icon: Optional[str] = None
    description: Optional[str] = None


class ProviderResponse(ProviderBase):
    """Provider response schema."""
    id: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProviderPlanBase(BaseModel):
    """Base provider plan schema."""
    name: str
    display_name: str
    description: Optional[str] = None
    price_monthly: float = 0
    price_yearly: float = 0
    features: Dict[str, Any] = {}
    max_environments: int = 1
    max_workflows: int = 10


class ProviderPlanResponse(ProviderPlanBase):
    """Provider plan response schema."""
    id: str
    provider_id: str
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_yearly: Optional[str] = None
    is_active: bool
    sort_order: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProviderWithPlans(ProviderResponse):
    """Provider with its available plans."""
    plans: List[ProviderPlanResponse] = []


class TenantProviderSubscriptionBase(BaseModel):
    """Base subscription schema."""
    provider_id: str
    plan_id: str
    billing_cycle: str = "monthly"


class TenantProviderSubscriptionCreate(TenantProviderSubscriptionBase):
    """Create subscription schema."""
    stripe_subscription_id: Optional[str] = None
    status: str = "active"


class TenantProviderSubscriptionResponse(BaseModel):
    """Subscription response schema."""
    id: str
    tenant_id: str
    provider_id: str
    provider: ProviderResponse
    plan_id: str
    plan: ProviderPlanResponse
    stripe_subscription_id: Optional[str] = None
    status: str
    billing_cycle: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TenantProviderSubscriptionSimple(BaseModel):
    """Simple subscription response without nested objects."""
    id: str
    tenant_id: str
    provider_id: str
    plan_id: str
    stripe_subscription_id: Optional[str] = None
    status: str
    billing_cycle: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProviderCheckoutRequest(BaseModel):
    """Request to create a checkout session for a provider plan."""
    provider_id: str
    plan_id: str
    billing_cycle: str = "monthly"
    success_url: str
    cancel_url: str


class ProviderCheckoutResponse(BaseModel):
    """Response with checkout session URL."""
    checkout_url: str
    session_id: str


class ProviderSubscriptionUpdate(BaseModel):
    """Update subscription (e.g., change plan, cancel)."""
    plan_id: Optional[str] = None
    cancel_at_period_end: Optional[bool] = None


# Admin schemas for provider management
class AdminProviderUpdate(BaseModel):
    """Admin update for provider."""
    display_name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None


class AdminProviderPlanUpdate(BaseModel):
    """Admin update for provider plan."""
    display_name: Optional[str] = None
    description: Optional[str] = None
    price_monthly: Optional[float] = None
    price_yearly: Optional[float] = None
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_yearly: Optional[str] = None
    features: Optional[Dict[str, Any]] = None
    max_environments: Optional[int] = None
    max_workflows: Optional[int] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class AdminProviderPlanCreate(BaseModel):
    """Admin create for provider plan."""
    provider_id: str
    name: str
    display_name: str
    description: Optional[str] = None
    price_monthly: float = 0
    price_yearly: float = 0
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_yearly: Optional[str] = None
    features: Dict[str, Any] = {}
    max_environments: int = 1
    max_workflows: int = 10
    sort_order: int = 0
