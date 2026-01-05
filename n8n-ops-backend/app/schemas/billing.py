from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
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


class PlanMetadataResponse(BaseModel):
    name: str
    display_name: str
    icon: Optional[str] = None
    color_class: Optional[str] = None
    precedence: int
    sort_order: int


class PlanLimitsResponse(BaseModel):
    plan_name: str
    max_workflows: int
    max_environments: int
    max_users: int
    max_executions_daily: int


class PlanRetentionDefaultsResponse(BaseModel):
    plan_name: str
    drift_checks: int
    closed_incidents: int
    reconciliation_artifacts: int
    approvals: int


class PlanFeatureRequirementResponse(BaseModel):
    feature_name: str
    required_plan: Optional[str] = None


class PlanConfigurationsResponse(BaseModel):
    metadata: List[PlanMetadataResponse]
    limits: List[PlanLimitsResponse]
    retention_defaults: List[PlanRetentionDefaultsResponse]
    feature_requirements: List[PlanFeatureRequirementResponse]


class PlanMetadataUpdate(BaseModel):
    icon: Optional[str] = None
    color_class: Optional[str] = None
    precedence: Optional[int] = None
    sort_order: Optional[int] = None


class PlanLimitsUpdate(BaseModel):
    max_workflows: Optional[int] = None
    max_environments: Optional[int] = None
    max_users: Optional[int] = None
    max_executions_daily: Optional[int] = None


class PlanRetentionDefaultsUpdate(BaseModel):
    drift_checks: Optional[int] = None
    closed_incidents: Optional[int] = None
    reconciliation_artifacts: Optional[int] = None
    approvals: Optional[int] = None


class PlanFeatureRequirementUpdate(BaseModel):
    required_plan: Optional[str] = None


class WorkflowPolicyMatrixResponse(BaseModel):
    environment_class: str
    can_view_details: bool
    can_open_in_n8n: bool
    can_create_deployment: bool
    can_edit_directly: bool
    can_soft_delete: bool
    can_hard_delete: bool
    can_create_drift_incident: bool
    drift_incident_required: bool
    edit_requires_confirmation: bool
    edit_requires_admin: bool


class PlanPolicyOverrideResponse(BaseModel):
    plan_name: str
    environment_class: Optional[str] = None
    can_edit_directly: Optional[bool] = None
    can_soft_delete: Optional[bool] = None
    can_hard_delete: Optional[bool] = None
    can_create_drift_incident: Optional[bool] = None
    drift_incident_required: Optional[bool] = None
    edit_requires_confirmation: Optional[bool] = None
    edit_requires_admin: Optional[bool] = None


class WorkflowPolicyMatrixUpdate(BaseModel):
    can_view_details: Optional[bool] = None
    can_open_in_n8n: Optional[bool] = None
    can_create_deployment: Optional[bool] = None
    can_edit_directly: Optional[bool] = None
    can_soft_delete: Optional[bool] = None
    can_hard_delete: Optional[bool] = None
    can_create_drift_incident: Optional[bool] = None
    drift_incident_required: Optional[bool] = None
    edit_requires_confirmation: Optional[bool] = None
    edit_requires_admin: Optional[bool] = None


class PlanPolicyOverrideUpdate(BaseModel):
    can_edit_directly: Optional[bool] = None
    can_soft_delete: Optional[bool] = None
    can_hard_delete: Optional[bool] = None
    can_create_drift_incident: Optional[bool] = None
    drift_incident_required: Optional[bool] = None
    edit_requires_confirmation: Optional[bool] = None
    edit_requires_admin: Optional[bool] = None
