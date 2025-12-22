"""Provider API endpoints for automation platform subscriptions."""

from fastapi import APIRouter, HTTPException, status, Request, Depends
from typing import List, Optional
from datetime import datetime

from app.schemas.provider import (
    ProviderResponse,
    ProviderPlanResponse,
    ProviderWithPlans,
    TenantProviderSubscriptionResponse,
    TenantProviderSubscriptionSimple,
    ProviderCheckoutRequest,
    ProviderCheckoutResponse,
    ProviderSubscriptionUpdate,
    AdminProviderUpdate,
    AdminProviderPlanUpdate,
    AdminProviderPlanCreate,
)
from app.services.database import db_service
from app.services.stripe_service import stripe_service
from app.api.endpoints.auth import get_current_user

router = APIRouter()


@router.get("", response_model=List[ProviderWithPlans])
async def get_providers():
    """Get all available providers with their plans."""
    try:
        providers = await db_service.get_providers_with_plans(active_only=True)
        return providers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch providers: {str(e)}"
        )


@router.get("/{provider_id}", response_model=ProviderWithPlans)
async def get_provider(provider_id: str):
    """Get a specific provider with its plans."""
    try:
        provider = await db_service.get_provider(provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        provider["plans"] = await db_service.get_provider_plans(provider_id, active_only=True)
        return provider
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch provider: {str(e)}"
        )


@router.get("/{provider_id}/plans", response_model=List[ProviderPlanResponse])
async def get_provider_plans(provider_id: str):
    """Get all plans for a specific provider."""
    try:
        provider = await db_service.get_provider(provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )
        plans = await db_service.get_provider_plans(provider_id, active_only=True)
        return plans
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch provider plans: {str(e)}"
        )


@router.get("/subscriptions/list", response_model=List[TenantProviderSubscriptionResponse])
async def get_tenant_subscriptions(user_info: dict = Depends(get_current_user)):
    """Get all provider subscriptions for the current tenant."""
    try:
        tenant = user_info.get("tenant", {})
        tenant_id = tenant.get("id")

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant not found"
            )

        subscriptions = await db_service.get_tenant_provider_subscriptions(tenant_id)
        return subscriptions
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscriptions: {str(e)}"
        )


@router.get("/subscriptions/active", response_model=List[TenantProviderSubscriptionResponse])
async def get_active_subscriptions(user_info: dict = Depends(get_current_user)):
    """Get only active provider subscriptions for the current tenant."""
    try:
        tenant = user_info.get("tenant", {})
        tenant_id = tenant.get("id")

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant not found"
            )

        subscriptions = await db_service.get_active_provider_subscriptions(tenant_id)
        return subscriptions
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch active subscriptions: {str(e)}"
        )


@router.post("/checkout", response_model=ProviderCheckoutResponse)
async def create_provider_checkout(
    checkout: ProviderCheckoutRequest,
    user_info: dict = Depends(get_current_user)
):
    """Create a Stripe checkout session for a provider plan."""
    try:
        tenant = user_info.get("tenant", {})
        tenant_id = tenant.get("id")

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant not found"
            )

        # Verify provider exists
        provider = await db_service.get_provider(checkout.provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        # Verify plan exists and belongs to provider
        plan = await db_service.get_provider_plan(checkout.plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found"
            )
        if plan["provider_id"] != checkout.provider_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Plan does not belong to this provider"
            )

        # Check if tenant already has a subscription for this provider
        existing_sub = await db_service.get_tenant_provider_subscription(tenant_id, checkout.provider_id)
        if existing_sub and existing_sub.get("status") == "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already subscribed to this provider. Use the manage subscription endpoint to change plans."
            )

        # Get the appropriate Stripe price ID
        if checkout.billing_cycle == "yearly":
            price_id = plan.get("stripe_price_id_yearly")
        else:
            price_id = plan.get("stripe_price_id_monthly")

        if not price_id:
            # Free plan - create subscription directly without Stripe
            if plan.get("price_monthly", 0) == 0 and plan.get("price_yearly", 0) == 0:
                subscription_data = {
                    "tenant_id": tenant_id,
                    "provider_id": checkout.provider_id,
                    "plan_id": checkout.plan_id,
                    "status": "active",
                    "billing_cycle": checkout.billing_cycle,
                }
                await db_service.create_tenant_provider_subscription(subscription_data)
                return ProviderCheckoutResponse(
                    checkout_url=checkout.success_url,
                    session_id="free_plan"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Stripe price not configured for this plan"
                )

        # Get or create Stripe customer
        customer_id = tenant.get("stripe_customer_id")
        if not customer_id:
            customer = await stripe_service.create_customer(
                email=tenant.get("email"),
                name=tenant.get("name"),
                tenant_id=tenant_id
            )
            customer_id = customer["id"]
            # Update tenant with customer ID
            db_service.client.table("tenants").update({
                "stripe_customer_id": customer_id
            }).eq("id", tenant_id).execute()

        # Create checkout session
        session = await stripe_service.create_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            success_url=checkout.success_url,
            cancel_url=checkout.cancel_url,
            tenant_id=tenant_id,
            billing_cycle=checkout.billing_cycle,
            metadata={
                "provider_id": checkout.provider_id,
                "plan_id": checkout.plan_id,
                "subscription_type": "provider"
            }
        )

        return ProviderCheckoutResponse(
            checkout_url=session["url"],
            session_id=session["id"]
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}"
        )


@router.post("/{provider_id}/subscribe-free")
async def subscribe_to_free_plan(
    provider_id: str,
    user_info: dict = Depends(get_current_user)
):
    """Subscribe to a provider's free plan without going through Stripe."""
    try:
        tenant = user_info.get("tenant", {})
        tenant_id = tenant.get("id")

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant not found"
            )

        # Verify provider exists
        provider = await db_service.get_provider(provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        # Check if tenant already has a subscription for this provider
        existing_sub = await db_service.get_tenant_provider_subscription(tenant_id, provider_id)
        if existing_sub and existing_sub.get("status") == "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already subscribed to this provider"
            )

        # Find the free plan for this provider
        plans = await db_service.get_provider_plans(provider_id, active_only=True)
        free_plan = next((p for p in plans if p.get("name") == "free" or p.get("price_monthly", 0) == 0), None)

        if not free_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No free plan available for this provider"
            )

        # Create subscription
        subscription_data = {
            "tenant_id": tenant_id,
            "provider_id": provider_id,
            "plan_id": free_plan["id"],
            "status": "active",
            "billing_cycle": "monthly",
        }

        if existing_sub:
            # Reactivate existing subscription
            await db_service.update_tenant_provider_subscription_by_provider(
                tenant_id, provider_id, {"status": "active", "plan_id": free_plan["id"]}
            )
        else:
            await db_service.create_tenant_provider_subscription(subscription_data)

        return {"message": "Successfully subscribed to free plan", "provider": provider["display_name"]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to subscribe: {str(e)}"
        )


@router.patch("/{provider_id}/subscription", response_model=TenantProviderSubscriptionSimple)
async def update_provider_subscription(
    provider_id: str,
    update: ProviderSubscriptionUpdate,
    user_info: dict = Depends(get_current_user)
):
    """Update a provider subscription (change plan or cancel)."""
    try:
        tenant = user_info.get("tenant", {})
        tenant_id = tenant.get("id")

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant not found"
            )

        # Get existing subscription
        subscription = await db_service.get_tenant_provider_subscription(tenant_id, provider_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found for this provider"
            )

        update_data = {}

        # Handle cancellation
        if update.cancel_at_period_end is not None:
            update_data["cancel_at_period_end"] = update.cancel_at_period_end

            # If Stripe subscription exists, update it
            if subscription.get("stripe_subscription_id"):
                if update.cancel_at_period_end:
                    await stripe_service.cancel_subscription(
                        subscription["stripe_subscription_id"],
                        at_period_end=True
                    )
                else:
                    await stripe_service.reactivate_subscription(
                        subscription["stripe_subscription_id"]
                    )

        # Handle plan change
        if update.plan_id:
            new_plan = await db_service.get_provider_plan(update.plan_id)
            if not new_plan:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Plan not found"
                )
            if new_plan["provider_id"] != provider_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Plan does not belong to this provider"
                )
            update_data["plan_id"] = update.plan_id

        if update_data:
            result = await db_service.update_tenant_provider_subscription_by_provider(
                tenant_id, provider_id, update_data
            )
            return result

        return subscription

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update subscription: {str(e)}"
        )


@router.delete("/{provider_id}/subscription")
async def cancel_provider_subscription(
    provider_id: str,
    user_info: dict = Depends(get_current_user)
):
    """Cancel a provider subscription (sets cancel_at_period_end)."""
    try:
        tenant = user_info.get("tenant", {})
        tenant_id = tenant.get("id")

        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant not found"
            )

        # Get existing subscription
        subscription = await db_service.get_tenant_provider_subscription(tenant_id, provider_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found for this provider"
            )

        # If Stripe subscription exists, cancel it
        if subscription.get("stripe_subscription_id"):
            await stripe_service.cancel_subscription(
                subscription["stripe_subscription_id"],
                at_period_end=True
            )

        # Update database
        await db_service.update_tenant_provider_subscription_by_provider(
            tenant_id, provider_id, {"cancel_at_period_end": True}
        )

        return {"message": "Subscription will be canceled at the end of the billing period"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}"
        )


@router.post("/webhook", include_in_schema=False)
async def provider_webhook(request: Request):
    """Handle Stripe webhooks for provider subscriptions."""
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

        # Only handle provider-specific subscriptions
        metadata = {}
        if hasattr(event.data.object, 'metadata'):
            metadata = event.data.object.metadata or {}

        if metadata.get("subscription_type") != "provider":
            # Not a provider subscription, let the main billing webhook handle it
            return {"status": "skipped"}

        # Handle different event types
        if event.type == "checkout.session.completed":
            session = event.data.object
            await handle_provider_checkout_completed(session)

        elif event.type == "customer.subscription.updated":
            subscription = event.data.object
            await handle_provider_subscription_updated(subscription)

        elif event.type == "customer.subscription.deleted":
            subscription = event.data.object
            await handle_provider_subscription_deleted(subscription)

        return {"status": "success"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook error: {str(e)}"
        )


# Webhook handlers
async def handle_provider_checkout_completed(session):
    """Handle successful provider checkout."""
    metadata = session.metadata or {}
    tenant_id = metadata.get("tenant_id")
    provider_id = metadata.get("provider_id")
    plan_id = metadata.get("plan_id")
    billing_cycle = metadata.get("billing_cycle", "monthly")

    if not all([tenant_id, provider_id, plan_id]):
        return

    # Get subscription from Stripe
    subscription = await stripe_service.get_subscription(session.subscription)

    # Create or update provider subscription
    subscription_data = {
        "tenant_id": tenant_id,
        "provider_id": provider_id,
        "plan_id": plan_id,
        "stripe_subscription_id": session.subscription,
        "status": subscription["status"],
        "billing_cycle": billing_cycle,
        "current_period_start": datetime.fromtimestamp(subscription["current_period_start"]).isoformat(),
        "current_period_end": datetime.fromtimestamp(subscription["current_period_end"]).isoformat(),
    }

    # Check if subscription already exists
    existing = await db_service.get_tenant_provider_subscription(tenant_id, provider_id)
    if existing:
        await db_service.update_tenant_provider_subscription_by_provider(
            tenant_id, provider_id, subscription_data
        )
    else:
        await db_service.create_tenant_provider_subscription(subscription_data)


async def handle_provider_subscription_updated(subscription):
    """Handle provider subscription updates."""
    # Find subscription by Stripe ID
    sub = await db_service.get_tenant_provider_subscription_by_stripe_id(subscription["id"])
    if not sub:
        return

    # Update subscription in database
    await db_service.update_tenant_provider_subscription(
        sub["id"],
        sub["tenant_id"],
        {
            "status": subscription["status"],
            "current_period_start": datetime.fromtimestamp(subscription["current_period_start"]).isoformat(),
            "current_period_end": datetime.fromtimestamp(subscription["current_period_end"]).isoformat(),
            "cancel_at_period_end": subscription["cancel_at_period_end"],
        }
    )


async def handle_provider_subscription_deleted(subscription):
    """Handle provider subscription deletion."""
    # Find subscription by Stripe ID
    sub = await db_service.get_tenant_provider_subscription_by_stripe_id(subscription["id"])
    if not sub:
        return

    # Update status to canceled
    await db_service.update_tenant_provider_subscription(
        sub["id"],
        sub["tenant_id"],
        {
            "status": "canceled",
        }
    )


# ============== ADMIN ENDPOINTS ==============

@router.get("/admin/all", response_model=List[ProviderWithPlans])
async def admin_get_all_providers(user_info: dict = Depends(get_current_user)):
    """Admin: Get all providers with all plans (including inactive)."""
    try:
        # Get all providers including inactive
        providers = await db_service.get_providers(active_only=False)
        for provider in providers:
            provider["plans"] = await db_service.get_all_provider_plans(provider["id"])
        return providers
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch providers: {str(e)}"
        )


@router.patch("/admin/{provider_id}", response_model=ProviderResponse)
async def admin_update_provider(
    provider_id: str,
    update: AdminProviderUpdate,
    user_info: dict = Depends(get_current_user)
):
    """Admin: Update a provider's settings."""
    try:
        provider = await db_service.get_provider(provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        update_data = update.model_dump(exclude_unset=True)
        if not update_data:
            return provider

        result = await db_service.update_provider(provider_id, update_data)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update provider: {str(e)}"
        )


@router.get("/admin/{provider_id}/plans", response_model=List[ProviderPlanResponse])
async def admin_get_provider_plans(
    provider_id: str,
    user_info: dict = Depends(get_current_user)
):
    """Admin: Get all plans for a provider (including inactive)."""
    try:
        provider = await db_service.get_provider(provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        plans = await db_service.get_all_provider_plans(provider_id)
        return plans

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch plans: {str(e)}"
        )


@router.post("/admin/plans", response_model=ProviderPlanResponse)
async def admin_create_plan(
    plan: AdminProviderPlanCreate,
    user_info: dict = Depends(get_current_user)
):
    """Admin: Create a new provider plan."""
    try:
        provider = await db_service.get_provider(plan.provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        plan_data = plan.model_dump()
        plan_data["is_active"] = True
        result = await db_service.create_provider_plan(plan_data)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create plan: {str(e)}"
        )


@router.patch("/admin/plans/{plan_id}", response_model=ProviderPlanResponse)
async def admin_update_plan(
    plan_id: str,
    update: AdminProviderPlanUpdate,
    user_info: dict = Depends(get_current_user)
):
    """Admin: Update a provider plan."""
    try:
        plan = await db_service.get_provider_plan(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found"
            )

        update_data = update.model_dump(exclude_unset=True)
        if not update_data:
            return plan

        result = await db_service.update_provider_plan(plan_id, update_data)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update plan: {str(e)}"
        )


@router.delete("/admin/plans/{plan_id}")
async def admin_delete_plan(
    plan_id: str,
    user_info: dict = Depends(get_current_user)
):
    """Admin: Delete a provider plan."""
    try:
        plan = await db_service.get_provider_plan(plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found"
            )

        await db_service.delete_provider_plan(plan_id)
        return {"message": "Plan deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete plan: {str(e)}"
        )
