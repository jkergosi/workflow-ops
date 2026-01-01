from fastapi import APIRouter, HTTPException, status, Request, Depends
from typing import List, Any, Optional, Dict
from datetime import datetime

from app.schemas.billing import (
    SubscriptionPlanResponse,
    SubscriptionResponse,
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    PortalSessionResponse,
    PaymentHistoryResponse,
    InvoiceResponse,
    UpcomingInvoiceResponse
)
from app.services.database import db_service
from app.services.stripe_service import stripe_service
from app.services.tenant_plan_service import set_tenant_plan
from app.services.auth_service import get_current_user
from app.services.agency_billing_service import upsert_subscription_items

router = APIRouter()


def _obj_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _obj_metadata(obj: Any) -> Dict[str, Any]:
    md = _obj_get(obj, "metadata", {}) or {}
    if isinstance(md, dict):
        return md
    try:
        return dict(md)
    except Exception:
        return {}


def _extract_first_price_id(subscription: Any) -> Optional[str]:
    # dict shape from stripe_service.get_subscription()
    items = _obj_get(subscription, "items")
    if isinstance(subscription, dict):
        try:
            return subscription["items"]["data"][0]["price"]["id"]
        except Exception:
            return None

    # Stripe object shape from webhooks
    try:
        data = items.data if hasattr(items, "data") else None
        if not data:
            return None
        first = data[0]
        price = first.price
        return price.id
    except Exception:
        return None


def _plan_from_status(status_value: Optional[str], cancel_at_period_end: bool, paid_plan: str) -> str:
    status_norm = (status_value or "").lower()
    if status_norm in {"trialing", "active"}:
        return paid_plan
    if status_norm in {"canceled", "unpaid", "incomplete_expired"}:
        return "free"
    # If we don't recognize the status but it's set to cancel later, keep paid plan until it ends.
    if cancel_at_period_end:
        return paid_plan
    return "free"


@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def get_subscription_plans():
    """Get all available subscription plans"""
    try:
        response = db_service.client.table("subscription_plans").select("*").eq("is_active", True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription plans: {str(e)}"
        )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_current_subscription(user_info: dict = Depends(get_current_user)):
    """Get current subscription for tenant"""
    try:
        tenant_id = user_info["tenant"]["id"]
        # Get subscription with plan details
        response = db_service.client.table("subscriptions").select(
            "*, plan:plan_id(*)"
        ).eq("tenant_id", tenant_id).single().execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found"
            )

        return response.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription: {str(e)}"
        )


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(checkout: CheckoutSessionCreate, user_info: dict = Depends(get_current_user)):
    """Create a Stripe checkout session for subscription"""
    try:
        tenant_id = user_info["tenant"]["id"]
        # Get tenant info
        tenant_response = db_service.client.table("tenants").select("*").eq("id", tenant_id).single().execute()
        tenant = tenant_response.data

        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )

        # Check if tenant has existing subscription
        sub_response = db_service.client.table("subscriptions").select("*").eq("tenant_id", tenant_id).execute()

        customer_id = None
        if sub_response.data and len(sub_response.data) > 0:
            customer_id = sub_response.data[0].get("stripe_customer_id")

        # Create Stripe customer if not exists
        if not customer_id:
            customer = await stripe_service.create_customer(
                email=tenant.get("email"),
                name=tenant.get("name"),
                tenant_id=tenant_id
            )
            customer_id = customer["id"]

        # Create checkout session
        session = await stripe_service.create_checkout_session(
            customer_id=customer_id,
            price_id=checkout.price_id,
            success_url=checkout.success_url,
            cancel_url=checkout.cancel_url,
            tenant_id=tenant_id,
            billing_cycle=checkout.billing_cycle,
        )

        return session

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}"
        )


@router.post("/portal", response_model=PortalSessionResponse)
async def create_portal_session(return_url: str, user_info: dict = Depends(get_current_user)):
    """Create a Stripe customer portal session"""
    try:
        tenant_id = user_info["tenant"]["id"]
        # Get subscription with customer ID
        response = db_service.client.table("subscriptions").select("stripe_customer_id").eq("tenant_id", tenant_id).single().execute()

        if not response.data or not response.data.get("stripe_customer_id"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )

        customer_id = response.data["stripe_customer_id"]

        # Create portal session
        session = await stripe_service.create_portal_session(
            customer_id=customer_id,
            return_url=return_url
        )

        return session

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create portal session: {str(e)}"
        )


@router.post("/cancel")
async def cancel_subscription(at_period_end: bool = True, user_info: dict = Depends(get_current_user)):
    """Cancel current subscription"""
    try:
        tenant_id = user_info["tenant"]["id"]
        # Get subscription
        response = db_service.client.table("subscriptions").select("*").eq("tenant_id", tenant_id).single().execute()

        if not response.data or not response.data.get("stripe_subscription_id"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )

        subscription_id = response.data["stripe_subscription_id"]

        # Cancel in Stripe
        result = await stripe_service.cancel_subscription(
            subscription_id=subscription_id,
            at_period_end=at_period_end
        )

        # Update database
        db_service.client.table("subscriptions").update({
            "cancel_at_period_end": result["cancel_at_period_end"],
            "canceled_at": datetime.fromtimestamp(result["canceled_at"]).isoformat() if result.get("canceled_at") else None,
            "status": result["status"]
        }).eq("tenant_id", tenant_id).execute()

        return {"message": "Subscription canceled successfully", "cancel_at_period_end": at_period_end}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}"
        )


@router.post("/reactivate")
async def reactivate_subscription(user_info: dict = Depends(get_current_user)):
    """Reactivate a canceled subscription"""
    try:
        tenant_id = user_info["tenant"]["id"]
        # Get subscription
        response = db_service.client.table("subscriptions").select("*").eq("tenant_id", tenant_id).single().execute()

        if not response.data or not response.data.get("stripe_subscription_id"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found"
            )

        subscription_id = response.data["stripe_subscription_id"]

        # Reactivate in Stripe
        result = await stripe_service.reactivate_subscription(subscription_id)

        # Update database
        db_service.client.table("subscriptions").update({
            "cancel_at_period_end": False,
            "status": result["status"]
        }).eq("tenant_id", tenant_id).execute()

        return {"message": "Subscription reactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reactivate subscription: {str(e)}"
        )


@router.get("/invoices", response_model=List[InvoiceResponse])
async def get_invoices(limit: int = 10, user_info: dict = Depends(get_current_user)):
    """Get invoices for current tenant"""
    try:
        tenant_id = user_info["tenant"]["id"]
        # Get subscription with customer ID
        response = db_service.client.table("subscriptions").select("stripe_customer_id").eq("tenant_id", tenant_id).single().execute()

        if not response.data or not response.data.get("stripe_customer_id"):
            return []

        customer_id = response.data["stripe_customer_id"]

        # Get invoices from Stripe
        invoices = await stripe_service.list_invoices(customer_id, limit)
        return invoices

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch invoices: {str(e)}"
        )


@router.get("/upcoming-invoice", response_model=UpcomingInvoiceResponse)
async def get_upcoming_invoice(user_info: dict = Depends(get_current_user)):
    """Get upcoming invoice for current tenant"""
    try:
        tenant_id = user_info["tenant"]["id"]
        # Get subscription with customer ID
        response = db_service.client.table("subscriptions").select("stripe_customer_id").eq("tenant_id", tenant_id).single().execute()

        if not response.data or not response.data.get("stripe_customer_id"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )

        customer_id = response.data["stripe_customer_id"]

        # Get upcoming invoice from Stripe
        invoice = await stripe_service.get_upcoming_invoice(customer_id)

        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No upcoming invoice found"
            )

        return invoice

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch upcoming invoice: {str(e)}"
        )


@router.get("/payment-history", response_model=List[PaymentHistoryResponse])
async def get_payment_history(limit: int = 10, user_info: dict = Depends(get_current_user)):
    """Get payment history from database"""
    try:
        tenant_id = user_info["tenant"]["id"]
        response = db_service.client.table("payment_history").select("*").eq(
            "tenant_id", tenant_id
        ).order("created_at", desc=True).limit(limit).execute()

        return response.data

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch payment history: {str(e)}"
        )


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        if not sig_header:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing stripe-signature header"
            )

        # Verify webhook signature
        event = stripe_service.construct_webhook_event(payload, sig_header)

        # Handle different event types
        if event.type == "checkout.session.completed":
            session = event.data.object
            await handle_checkout_completed(session)

        elif event.type == "customer.subscription.updated":
            subscription = event.data.object
            await handle_subscription_updated(subscription)

        elif event.type == "customer.subscription.deleted":
            subscription = event.data.object
            await handle_subscription_deleted(subscription)

        elif event.type == "invoice.payment_succeeded":
            invoice = event.data.object
            await handle_payment_succeeded(invoice)

        elif event.type == "invoice.payment_failed":
            invoice = event.data.object
            await handle_payment_failed(invoice)

        return {"status": "success"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook error: {str(e)}"
        )


# Webhook handlers
async def handle_checkout_completed(session):
    """Handle successful checkout"""
    md = _obj_metadata(session)
    tenant_id = md.get("tenant_id")
    billing_cycle = md.get("billing_cycle", "monthly")
    if not tenant_id:
        return

    # Get subscription from Stripe
    stripe_subscription_id = _obj_get(session, "subscription")
    subscription = await stripe_service.get_subscription(stripe_subscription_id)

    # Get plan ID from price
    price_id = _extract_first_price_id(subscription)
    if not price_id:
        return

    plan_response = db_service.client.table("subscription_plans").select("id, name").or_(
        f"stripe_price_id_monthly.eq.{price_id},stripe_price_id_yearly.eq.{price_id}"
    ).single().execute()
    if not plan_response.data:
        return

    # Update or create subscription in database
    db_service.client.table("subscriptions").upsert({
        "tenant_id": tenant_id,
        "plan_id": plan_response.data["id"],
        "stripe_customer_id": _obj_get(session, "customer"),
        "stripe_subscription_id": stripe_subscription_id,
        "status": subscription["status"],
        "billing_cycle": billing_cycle,
        "current_period_start": datetime.fromtimestamp(subscription["current_period_start"]).isoformat(),
        "current_period_end": datetime.fromtimestamp(subscription["current_period_end"]).isoformat(),
        "cancel_at_period_end": bool(subscription.get("cancel_at_period_end", False)),
        "canceled_at": datetime.fromtimestamp(subscription["canceled_at"]).isoformat() if subscription.get("canceled_at") else None,
    }).execute()

    await upsert_subscription_items(tenant_id, stripe_subscription_id, subscription)

    paid_plan_name = (plan_response.data.get("name") or "free").lower()
    next_plan = _plan_from_status(
        subscription.get("status"),
        bool(subscription.get("cancel_at_period_end", False)),
        paid_plan_name,
    )
    await set_tenant_plan(tenant_id, next_plan)  # type: ignore[arg-type]
    
    # Activate tenant if it's still pending (important for onboarding flow)
    tenant_response = db_service.client.table("tenants").select("status").eq("id", tenant_id).single().execute()
    if tenant_response.data and tenant_response.data.get("status") == "pending":
        db_service.client.table("tenants").update({
            "status": "active"
        }).eq("id", tenant_id).execute()


async def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    subscription_id = _obj_get(subscription, "id")
    md = _obj_metadata(subscription)
    tenant_id = md.get("tenant_id")
    if not tenant_id and subscription_id:
        existing = (
            db_service.client.table("subscriptions")
            .select("tenant_id")
            .eq("stripe_subscription_id", subscription_id)
            .single()
            .execute()
        )
        tenant_id = existing.data.get("tenant_id") if existing.data else None
    if not tenant_id or not subscription_id:
        return

    price_id = _extract_first_price_id(subscription)
    plan_name: str = "free"
    plan_id: Optional[str] = None
    if price_id:
        plan_resp = (
            db_service.client.table("subscription_plans")
            .select("id, name")
            .or_(f"stripe_price_id_monthly.eq.{price_id},stripe_price_id_yearly.eq.{price_id}")
            .single()
            .execute()
        )
        if plan_resp.data:
            plan_id = plan_resp.data.get("id")
            plan_name = (plan_resp.data.get("name") or "free").lower()

    status_value = _obj_get(subscription, "status")
    cancel_at_period_end = bool(_obj_get(subscription, "cancel_at_period_end", False))
    canceled_at = _obj_get(subscription, "canceled_at")

    # Update subscription in database (billing mirror)
    update_data: Dict[str, Any] = {
        "status": status_value,
        "cancel_at_period_end": cancel_at_period_end,
        "canceled_at": datetime.fromtimestamp(canceled_at).isoformat() if canceled_at else None,
        "current_period_start": datetime.fromtimestamp(_obj_get(subscription, "current_period_start")).isoformat() if _obj_get(subscription, "current_period_start") else None,
        "current_period_end": datetime.fromtimestamp(_obj_get(subscription, "current_period_end")).isoformat() if _obj_get(subscription, "current_period_end") else None,
    }
    if plan_id:
        update_data["plan_id"] = plan_id

    db_service.client.table("subscriptions").update(update_data).eq(
        "stripe_subscription_id", subscription_id
    ).execute()

    await upsert_subscription_items(tenant_id, subscription_id, subscription)

    next_plan = _plan_from_status(status_value, cancel_at_period_end, plan_name)
    await set_tenant_plan(tenant_id, next_plan)  # type: ignore[arg-type]


async def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    subscription_id = _obj_get(subscription, "id")
    md = _obj_metadata(subscription)
    tenant_id = md.get("tenant_id")
    if not tenant_id and subscription_id:
        existing = (
            db_service.client.table("subscriptions")
            .select("tenant_id")
            .eq("stripe_subscription_id", subscription_id)
            .single()
            .execute()
        )
        tenant_id = existing.data.get("tenant_id") if existing.data else None
    if not subscription_id:
        return

    free_plan = db_service.client.table("subscription_plans").select("id").eq("name", "free").single().execute()
    free_plan_id = free_plan.data.get("id") if free_plan.data else None

    update_data: Dict[str, Any] = {
        "status": "canceled",
        "canceled_at": datetime.now().isoformat(),
    }
    if free_plan_id:
        update_data["plan_id"] = free_plan_id

    db_service.client.table("subscriptions").update(update_data).eq(
        "stripe_subscription_id", subscription_id
    ).execute()

    if tenant_id:
        await set_tenant_plan(tenant_id, "free")  # type: ignore[arg-type]


async def handle_payment_succeeded(invoice):
    """Handle successful payment"""
    # Get tenant from customer
    sub_response = db_service.client.table("subscriptions").select("id, tenant_id").eq(
        "stripe_customer_id", invoice["customer"]
    ).single().execute()

    if sub_response.data:
        # Record payment in history
        db_service.client.table("payment_history").insert({
            "tenant_id": sub_response.data["tenant_id"],
            "subscription_id": sub_response.data["id"],
            "stripe_payment_intent_id": invoice.get("payment_intent"),
            "stripe_invoice_id": invoice["id"],
            "amount": invoice["amount_paid"] / 100,
            "currency": invoice["currency"].upper(),
            "status": "succeeded",
            "description": "Subscription payment"
        }).execute()


async def handle_payment_failed(invoice):
    """Handle failed payment"""
    # Get tenant from customer
    sub_response = db_service.client.table("subscriptions").select("id, tenant_id").eq(
        "stripe_customer_id", invoice["customer"]
    ).single().execute()

    if sub_response.data:
        # Record failed payment
        db_service.client.table("payment_history").insert({
            "tenant_id": sub_response.data["tenant_id"],
            "subscription_id": sub_response.data["id"],
            "stripe_invoice_id": invoice["id"],
            "amount": invoice["amount_due"] / 100,
            "currency": invoice["currency"].upper(),
            "status": "failed",
            "description": "Failed subscription payment"
        }).execute()

        # Update subscription status
        db_service.client.table("subscriptions").update({
            "status": "past_due"
        }).eq("id", sub_response.data["id"]).execute()
