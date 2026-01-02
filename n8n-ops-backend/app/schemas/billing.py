from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal


class SubscriptionPlanResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    price_monthly: Decimal
    price_yearly: Optional[Decimal] = None
    max_environments: Optional[int] = None
    max_team_members: Optional[int] = None
    max_workflows: Optional[int] = None
    features: Dict[str, Any]
    is_active: bool

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    id: str
    tenant_id: str
    plan: SubscriptionPlanResponse
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    status: str
    billing_cycle: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool
    canceled_at: Optional[datetime] = None
    trial_end: Optional[datetime] = None

    class Config:
        from_attributes = True


class CheckoutSessionCreate(BaseModel):
    price_id: str
    billing_cycle: str = Field(..., pattern="^(monthly|yearly)$")
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    session_id: str
    url: str


class PortalSessionResponse(BaseModel):
    url: str


class PaymentHistoryResponse(BaseModel):
    id: str
    amount: Decimal
    currency: str
    status: str
    payment_method: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    id: str
    number: Optional[str] = None
    amount_paid: float
    amount_paid_cents: Optional[int] = None
    currency: str
    status: str
    created: int
    invoice_pdf: Optional[str] = None
    hosted_invoice_url: Optional[str] = None


class UpcomingInvoiceResponse(BaseModel):
    amount_due: float
    currency: str
    period_start: int
    period_end: int
    next_payment_attempt: Optional[int] = None


class PaymentMethodResponse(BaseModel):
    brand: Optional[str] = None
    last4: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None


class BillingOverviewResponse(BaseModel):
    plan: Dict[str, Any]
    subscription: Dict[str, Any]
    usage: Dict[str, Any]
    entitlements: Dict[str, Any]
    payment_method: Optional[PaymentMethodResponse] = None
    invoices: List[InvoiceResponse]
    links: Dict[str, str]
