"""Admin billing endpoints for system-wide billing management."""
from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
from enum import Enum
import stripe

from app.services.database import db_service
from app.services.stripe_service import stripe_service
from app.core.config import settings
from app.api.endpoints.admin_audit import create_audit_log
from app.core.platform_admin import require_platform_admin

router = APIRouter()


class BillingMetricsResponse(BaseModel):
    mrr: float  # Monthly Recurring Revenue
    arr: float  # Annual Recurring Revenue
    active_subscriptions: int
    active_trials: int
    new_subscriptions_30d: int
    churned_subscriptions_30d: int
    paying_tenants: int
    free_tenants: int


class PlanDistributionItem(BaseModel):
    plan_name: str
    count: int
    percentage: float
    revenue: float


class RecentChargeResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    amount: float
    currency: str
    status: str
    plan_name: Optional[str] = None
    created_at: datetime


class FailedPaymentResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    amount: float
    currency: str
    failure_reason: Optional[str] = None
    retry_date: Optional[datetime] = None
    created_at: datetime


class DunningTenantResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    plan_name: str
    status: str
    last_payment_attempt: Optional[datetime] = None
    amount_due: float
    failed_attempts: int


class TenantSubscriptionResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    plan_name: str
    status: str
    billing_cycle: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


class TenantInvoiceResponse(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    created_at: datetime
    invoice_pdf: Optional[str] = None
    hosted_invoice_url: Optional[str] = None


@router.get("/metrics", response_model=BillingMetricsResponse)
async def get_billing_metrics(_: dict = Depends(require_platform_admin())):
    """Get system-wide billing metrics."""
    try:
        # Get subscription data from database
        subscriptions_response = db_service.client.table("subscriptions").select(
            "*, tenant:tenant_id(id, name, subscription_tier)"
        ).execute()
        subscriptions = subscriptions_response.data or []

        # Get tenant counts by plan
        tenants_response = db_service.client.table("tenants").select(
            "id, subscription_tier, status"
        ).execute()
        tenants = tenants_response.data or []

        # Calculate metrics
        active_subs = [s for s in subscriptions if s.get("status") == "active"]
        trial_subs = [s for s in subscriptions if s.get("status") == "trialing"]

        # Calculate MRR from payment history or subscription plans
        mrr = 0.0
        for sub in active_subs:
            # Get plan price from subscription_plans table
            plan_id = sub.get("plan_id")
            if plan_id:
                plan_response = db_service.client.table("subscription_plans").select(
                    "price_monthly"
                ).eq("id", plan_id).single().execute()
                if plan_response.data:
                    mrr += float(plan_response.data.get("price_monthly", 0))

        arr = mrr * 12

        # Count new subscriptions in last 30 days
        thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
        new_subs_response = db_service.client.table("subscriptions").select(
            "id", count="exact"
        ).gte("created_at", thirty_days_ago).execute()
        new_subscriptions_30d = new_subs_response.count or 0

        # Count churned subscriptions (canceled in last 30 days)
        churned_response = db_service.client.table("subscriptions").select(
            "id", count="exact"
        ).eq("status", "canceled").gte("updated_at", thirty_days_ago).execute()
        churned_subscriptions_30d = churned_response.count or 0

        # Count paying vs free tenants
        paying_tenants = len([t for t in tenants if t.get("subscription_tier") not in ["free", None]])
        free_tenants = len([t for t in tenants if t.get("subscription_tier") in ["free", None]])

        return BillingMetricsResponse(
            mrr=mrr,
            arr=arr,
            active_subscriptions=len(active_subs),
            active_trials=len(trial_subs),
            new_subscriptions_30d=new_subscriptions_30d,
            churned_subscriptions_30d=churned_subscriptions_30d,
            paying_tenants=paying_tenants,
            free_tenants=free_tenants,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch billing metrics: {str(e)}"
        )


@router.get("/plan-distribution", response_model=List[PlanDistributionItem])
async def get_plan_distribution(_: dict = Depends(require_platform_admin())):
    """Get tenant distribution by plan."""
    try:
        # Get all tenants with their plans
        tenants_response = db_service.client.table("tenants").select(
            "subscription_tier"
        ).execute()
        tenants = tenants_response.data or []

        # Get plan pricing
        plans_response = db_service.client.table("subscription_plans").select(
            "name, price_monthly"
        ).execute()
        plans = {p["name"]: p.get("price_monthly", 0) for p in (plans_response.data or [])}

        # Count by plan
        plan_counts = {}
        for tenant in tenants:
            plan = tenant.get("subscription_tier") or "free"
            plan_counts[plan] = plan_counts.get(plan, 0) + 1

        total = len(tenants) or 1  # Avoid division by zero

        distribution = []
        for plan_name, count in plan_counts.items():
            price = plans.get(plan_name, 0)
            distribution.append(PlanDistributionItem(
                plan_name=plan_name,
                count=count,
                percentage=round((count / total) * 100, 1),
                revenue=count * price,
            ))

        # Sort by count descending
        distribution.sort(key=lambda x: x.count, reverse=True)

        return distribution
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch plan distribution: {str(e)}"
        )


@router.get("/recent-charges", response_model=List[RecentChargeResponse])
async def get_recent_charges(limit: int = Query(50, ge=1, le=100), _: dict = Depends(require_platform_admin())):
    """Get recent successful charges."""
    try:
        # Get from payment_history table
        response = db_service.client.table("payment_history").select(
            "*, tenant:tenant_id(id, name, subscription_tier)"
        ).eq("status", "succeeded").order("created_at", desc=True).limit(limit).execute()

        charges = []
        for payment in (response.data or []):
            tenant = payment.get("tenant", {}) or {}
            charges.append(RecentChargeResponse(
                id=payment["id"],
                tenant_id=payment.get("tenant_id"),
                tenant_name=tenant.get("name"),
                amount=payment.get("amount", 0) / 100,  # Convert cents
                currency=payment.get("currency", "usd"),
                status=payment.get("status", "succeeded"),
                plan_name=tenant.get("subscription_tier"),
                created_at=payment.get("created_at"),
            ))

        return charges
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recent charges: {str(e)}"
        )


@router.get("/failed-payments", response_model=List[FailedPaymentResponse])
async def get_failed_payments(limit: int = Query(50, ge=1, le=100), _: dict = Depends(require_platform_admin())):
    """Get recent failed payments."""
    try:
        response = db_service.client.table("payment_history").select(
            "*, tenant:tenant_id(id, name)"
        ).eq("status", "failed").order("created_at", desc=True).limit(limit).execute()

        failures = []
        for payment in (response.data or []):
            tenant = payment.get("tenant", {}) or {}
            failures.append(FailedPaymentResponse(
                id=payment["id"],
                tenant_id=payment.get("tenant_id"),
                tenant_name=tenant.get("name"),
                amount=payment.get("amount", 0) / 100,
                currency=payment.get("currency", "usd"),
                failure_reason=payment.get("failure_reason"),
                retry_date=payment.get("retry_date"),
                created_at=payment.get("created_at"),
            ))

        return failures
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch failed payments: {str(e)}"
        )


@router.get("/dunning", response_model=List[DunningTenantResponse])
async def get_dunning_tenants(_: dict = Depends(require_platform_admin())):
    """Get tenants in dunning state (past_due or incomplete)."""
    try:
        response = db_service.client.table("subscriptions").select(
            "*, tenant:tenant_id(id, name, subscription_tier)"
        ).in_("status", ["past_due", "incomplete"]).execute()

        dunning = []
        for sub in (response.data or []):
            tenant = sub.get("tenant", {}) or {}

            # Count failed payment attempts
            failed_response = db_service.client.table("payment_history").select(
                "id", count="exact"
            ).eq("tenant_id", sub.get("tenant_id")).eq("status", "failed").execute()

            dunning.append(DunningTenantResponse(
                tenant_id=sub.get("tenant_id"),
                tenant_name=tenant.get("name", "Unknown"),
                plan_name=tenant.get("subscription_tier", "unknown"),
                status=sub.get("status"),
                last_payment_attempt=sub.get("updated_at"),
                amount_due=0,  # Would come from Stripe
                failed_attempts=failed_response.count or 0,
            ))

        return dunning
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dunning tenants: {str(e)}"
        )


# =============================================================================
# Per-Tenant Billing Endpoints (Admin)
# =============================================================================

@router.get("/tenants/{tenant_id}/subscription", response_model=TenantSubscriptionResponse)
async def get_tenant_subscription(tenant_id: str, _: dict = Depends(require_platform_admin())):
    """Get subscription details for a specific tenant (admin)."""
    try:
        # Get tenant info
        tenant_response = db_service.client.table("tenants").select(
            "id, name, subscription_tier, stripe_customer_id"
        ).eq("id", tenant_id).single().execute()

        if not tenant_response.data:
            raise HTTPException(status_code=404, detail="Tenant not found")

        tenant = tenant_response.data

        # Get subscription
        sub_response = db_service.client.table("subscriptions").select("*").eq(
            "tenant_id", tenant_id
        ).single().execute()

        sub = sub_response.data or {}

        return TenantSubscriptionResponse(
            tenant_id=tenant_id,
            tenant_name=tenant.get("name", ""),
            plan_name=tenant.get("subscription_tier", "free"),
            status=sub.get("status", "none"),
            billing_cycle=sub.get("billing_cycle", "monthly"),
            current_period_start=sub.get("current_period_start"),
            current_period_end=sub.get("current_period_end"),
            trial_end=sub.get("trial_end"),
            cancel_at_period_end=sub.get("cancel_at_period_end", False),
            stripe_customer_id=tenant.get("stripe_customer_id"),
            stripe_subscription_id=sub.get("stripe_subscription_id"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant subscription: {str(e)}"
        )


@router.get("/tenants/{tenant_id}/invoices", response_model=List[TenantInvoiceResponse])
async def get_tenant_invoices(tenant_id: str, limit: int = Query(20, ge=1, le=100), _: dict = Depends(require_platform_admin())):
    """Get invoices for a specific tenant (admin)."""
    try:
        # Get tenant's Stripe customer ID
        tenant_response = db_service.client.table("tenants").select(
            "stripe_customer_id"
        ).eq("id", tenant_id).single().execute()

        if not tenant_response.data:
            raise HTTPException(status_code=404, detail="Tenant not found")

        customer_id = tenant_response.data.get("stripe_customer_id")

        if not customer_id:
            return []  # No Stripe customer, no invoices

        # Fetch from Stripe
        result = await stripe_service.list_invoices(customer_id, limit)
        invoices = result["data"]

        return [
            TenantInvoiceResponse(
                id=inv["id"],
                amount=inv["amount_paid"],
                currency=inv["currency"],
                status=inv["status"],
                created_at=datetime.fromtimestamp(inv["created"]),
                invoice_pdf=inv.get("invoice_pdf"),
                hosted_invoice_url=inv.get("hosted_invoice_url"),
            )
            for inv in invoices
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant invoices: {str(e)}"
        )


@router.post("/tenants/{tenant_id}/change-plan")
async def change_tenant_plan(
    tenant_id: str,
    new_plan: str,
    reason: Optional[str] = None,
    user_info: dict = Depends(require_platform_admin()),
):
    """Change a tenant's subscription plan (admin)."""
    try:
        # Get current tenant info
        tenant_response = db_service.client.table("tenants").select(
            "id, name, subscription_tier, stripe_customer_id"
        ).eq("id", tenant_id).single().execute()

        if not tenant_response.data:
            raise HTTPException(status_code=404, detail="Tenant not found")

        tenant = tenant_response.data
        old_plan = tenant.get("subscription_tier")

        # Update tenant plan
        db_service.client.table("tenants").update({
            "subscription_tier": new_plan
        }).eq("id", tenant_id).execute()

        # Create audit log
        await create_audit_log(
            action_type="TENANT_PLAN_CHANGED",
            action=f"Changed plan from {old_plan} to {new_plan}",
            tenant_id=tenant_id,
            tenant_name=tenant.get("name"),
            resource_type="tenant",
            resource_id=tenant_id,
            old_value={"plan": old_plan},
            new_value={"plan": new_plan},
            reason=reason,
        )

        return {"success": True, "old_plan": old_plan, "new_plan": new_plan}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change tenant plan: {str(e)}"
        )


@router.post("/tenants/{tenant_id}/extend-trial")
async def extend_tenant_trial(
    tenant_id: str,
    days: int = Query(14, ge=1, le=90),
    reason: Optional[str] = None,
    user_info: dict = Depends(require_platform_admin()),
):
    """Extend a tenant's trial period (admin)."""
    try:
        # Get subscription
        sub_response = db_service.client.table("subscriptions").select("*").eq(
            "tenant_id", tenant_id
        ).single().execute()

        if not sub_response.data:
            raise HTTPException(status_code=404, detail="Subscription not found")

        sub = sub_response.data
        current_trial_end = sub.get("trial_end")

        # Calculate new trial end
        if current_trial_end:
            new_trial_end = datetime.fromisoformat(current_trial_end.replace("Z", "+00:00")) + timedelta(days=days)
        else:
            new_trial_end = datetime.utcnow() + timedelta(days=days)

        # Update subscription
        db_service.client.table("subscriptions").update({
            "trial_end": new_trial_end.isoformat(),
            "status": "trialing"
        }).eq("tenant_id", tenant_id).execute()

        # Audit log
        await create_audit_log(
            action_type="TRIAL_EXTENDED",
            action=f"Extended trial by {days} days",
            tenant_id=tenant_id,
            resource_type="subscription",
            resource_id=sub.get("id"),
            old_value={"trial_end": current_trial_end},
            new_value={"trial_end": new_trial_end.isoformat()},
            reason=reason,
        )

        return {"success": True, "new_trial_end": new_trial_end.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extend trial: {str(e)}"
        )


@router.post("/tenants/{tenant_id}/cancel-subscription")
async def cancel_tenant_subscription(
    tenant_id: str,
    at_period_end: bool = True,
    reason: Optional[str] = None,
    user_info: dict = Depends(require_platform_admin()),
):
    """Cancel a tenant's subscription (admin)."""
    try:
        # Get subscription
        sub_response = db_service.client.table("subscriptions").select("*").eq(
            "tenant_id", tenant_id
        ).single().execute()

        if not sub_response.data:
            raise HTTPException(status_code=404, detail="Subscription not found")

        sub = sub_response.data
        stripe_sub_id = sub.get("stripe_subscription_id")

        # Cancel in Stripe if exists
        if stripe_sub_id:
            await stripe_service.cancel_subscription(stripe_sub_id, at_period_end)

        # Update local subscription
        update_data = {
            "cancel_at_period_end": at_period_end,
            "canceled_at": datetime.utcnow().isoformat(),
        }
        if not at_period_end:
            update_data["status"] = "canceled"

        db_service.client.table("subscriptions").update(update_data).eq(
            "tenant_id", tenant_id
        ).execute()

        # If immediate cancel, update tenant status
        if not at_period_end:
            db_service.client.table("tenants").update({
                "subscription_tier": "free",
                "status": "cancelled"
            }).eq("id", tenant_id).execute()

        # Audit log
        await create_audit_log(
            action_type="SUBSCRIPTION_CANCELLED",
            action=f"Cancelled subscription (at_period_end={at_period_end})",
            tenant_id=tenant_id,
            resource_type="subscription",
            resource_id=sub.get("id"),
            reason=reason,
        )

        return {"success": True, "at_period_end": at_period_end}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}"
        )
