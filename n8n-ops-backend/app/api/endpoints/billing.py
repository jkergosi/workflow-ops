from fastapi import APIRouter, HTTPException, status, Request, Depends
from typing import List, Any, Optional, Dict
from datetime import datetime
import logging

from app.schemas.pagination import PaginatedResponse, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.schemas.billing import (
    SubscriptionPlanResponse,
    SubscriptionResponse,
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    PortalSessionResponse,
    PaymentHistoryResponse,
    InvoiceResponse,
    UpcomingInvoiceResponse,
    BillingOverviewResponse,
    PaymentMethodResponse,
    PlanConfigurationsResponse,
    PlanMetadataResponse,
    PlanLimitsResponse,
    PlanRetentionDefaultsResponse,
    PlanFeatureRequirementResponse
)
from app.services.database import db_service
from app.services.stripe_service import stripe_service
from app.services.tenant_plan_service import set_tenant_plan
from app.services.auth_service import get_current_user
from app.services.agency_billing_service import upsert_subscription_items
from app.services.entitlements_service import entitlements_service
from app.services.feature_service import feature_service
from app.services.plan_resolver import resolve_effective_plan
from app.services.webhook_lock_service import webhook_lock_service
from app.services.downgrade_service import downgrade_service
from app.core.rbac import require_tenant_admin

router = APIRouter()
logger = logging.getLogger(__name__)


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


async def _get_plan_precedence(plan_name: str) -> int:
    """
    Get the precedence/rank for a plan name.
    Higher values indicate higher-tier plans.

    Args:
        plan_name: The plan name (normalized to lowercase)

    Returns:
        Precedence value (0 for free, higher for paid plans)
    """
    try:
        normalized = (plan_name or "free").lower().strip()
        response = db_service.client.table("plans").select("precedence").eq(
            "name", normalized
        ).maybe_single().execute()

        if response and response.data:
            return response.data.get("precedence", 0)
    except Exception as e:
        logger.warning(f"Failed to get precedence for plan {plan_name}: {e}")

    # Fallback defaults
    return 0 if plan_name == "free" else 0


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


@router.get("/plan-features/all")
async def get_all_plan_features_public():
    """
    Get all plan features in format suitable for frontend PLAN_FEATURES object.
    Public endpoint (no auth required) for frontend to load plan features.
    """
    try:
        # Get all plans
        plans_response = db_service.client.table("plans").select("id, name").eq("is_active", True).execute()
        plans = {p["id"]: p["name"] for p in (plans_response.data or [])}
        
        # Get all features
        features_response = db_service.client.table("features").select("id, name, type, display_name").execute()
        features = {f["id"]: f for f in (features_response.data or [])}
        
        # Get all plan-feature mappings
        plan_features_response = db_service.client.table("plan_features").select(
            "plan_id, feature_id, value"
        ).execute()
        
        # Build result structure
        result: Dict[str, Dict[str, Any]] = {}
        
        # Initialize all plans with empty dicts
        for plan_name in plans.values():
            result[plan_name] = {}
        
        # Populate with plan-feature values
        for pf in (plan_features_response.data or []):
            plan_id = pf.get("plan_id")
            feature_id = pf.get("feature_id")
            value = pf.get("value", {})
            
            if plan_id in plans and feature_id in features:
                plan_name = plans[plan_id]
                feature = features[feature_id]
                feature_name = feature["name"]
                feature_type = feature["type"]
                
                # Convert value based on type
                if feature_type == "flag":
                    result[plan_name][feature_name] = value.get("enabled", False)
                elif feature_type == "limit":
                    result[plan_name][feature_name] = value.get("value", 0)
                else:
                    result[plan_name][feature_name] = value
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch plan features: {str(e)}"
        )


@router.get("/feature-display-names")
async def get_feature_display_names():
    """
    Get all feature display names from database.
    Public endpoint for frontend to load feature display names.
    """
    try:
        response = db_service.client.table("features").select("name, display_name").execute()
        result = {}
        for feature in (response.data or []):
            result[feature["name"]] = feature.get("display_name") or feature["name"]
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch feature display names: {str(e)}"
        )


@router.get("/plan-configurations", response_model=PlanConfigurationsResponse)
async def get_plan_configurations():
    """Get all plan configurations (metadata, limits, retention defaults, feature requirements)"""
    try:
        # Fetch plan metadata
        plans_response = db_service.client.table("plans").select(
            "name, display_name, icon, color_class, precedence, sort_order"
        ).eq("is_active", True).order("sort_order").execute()
        
        metadata = [
            PlanMetadataResponse(
                name=row["name"],
                display_name=row["display_name"],
                icon=row.get("icon"),
                color_class=row.get("color_class"),
                precedence=row.get("precedence", 0),
                sort_order=row.get("sort_order", 0)
            )
            for row in (plans_response.data or [])
        ]
        
        # Fetch plan limits
        limits_response = db_service.client.table("plan_limits").select("*").execute()
        limits = [
            PlanLimitsResponse(
                plan_name=row["plan_name"],
                max_workflows=row["max_workflows"],
                max_environments=row["max_environments"],
                max_users=row["max_users"],
                max_executions_daily=row["max_executions_daily"]
            )
            for row in (limits_response.data or [])
        ]
        
        # Fetch retention defaults
        retention_response = db_service.client.table("plan_retention_defaults").select("*").execute()
        retention_defaults = [
            PlanRetentionDefaultsResponse(
                plan_name=row["plan_name"],
                drift_checks=row["drift_checks"],
                closed_incidents=row["closed_incidents"],
                reconciliation_artifacts=row["reconciliation_artifacts"],
                approvals=row["approvals"]
            )
            for row in (retention_response.data or [])
        ]
        
        # Fetch feature requirements
        feature_req_response = db_service.client.table("plan_feature_requirements").select("*").execute()
        feature_requirements = [
            PlanFeatureRequirementResponse(
                feature_name=row["feature_name"],
                required_plan=row.get("required_plan")
            )
            for row in (feature_req_response.data or [])
        ]
        
        return PlanConfigurationsResponse(
            metadata=metadata,
            limits=limits,
            retention_defaults=retention_defaults,
            feature_requirements=feature_requirements
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch plan configurations: {str(e)}"
        )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_current_subscription(
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
):
    """Get current subscription for tenant"""
    try:
        tenant_id = user_info["tenant"]["id"]

        # Use tenant_provider_subscriptions as single source of truth
        # Get the effective plan and subscription details
        resolved = await resolve_effective_plan(tenant_id)
        plan_name = resolved.get("plan_name", "free")
        highest_sub_id = resolved.get("highest_subscription_id")

        if highest_sub_id:
            # Get subscription details from tenant_provider_subscriptions
            sub_response = db_service.client.table("tenant_provider_subscriptions").select(
                "id, tenant_id, provider_id, plan_id, status, billing_cycle, "
                "current_period_start, current_period_end, cancel_at_period_end, "
                "stripe_subscription_id, created_at, updated_at, "
                "plan:plan_id(id, name, display_name, features, max_environments, max_workflows)"
            ).eq("id", highest_sub_id).maybe_single().execute()

            if sub_response and sub_response.data:
                sub_data = sub_response.data
                plan_data = sub_data.get("plan", {})
                
                # Get Stripe customer ID if available (may be in old subscriptions table as fallback)
                stripe_customer_id = None
                try:
                    old_sub = db_service.client.table("subscriptions").select(
                        "stripe_customer_id"
                    ).eq("tenant_id", tenant_id).maybe_single().execute()
                    if old_sub and old_sub.data:
                        stripe_customer_id = old_sub.data.get("stripe_customer_id")
                except Exception:
                    pass

                return {
                    "id": sub_data.get("id"),
                    "tenant_id": tenant_id,
                    "plan_id": plan_data.get("id"),
                    "plan": plan_data,
                    "stripe_customer_id": stripe_customer_id,
                    "stripe_subscription_id": sub_data.get("stripe_subscription_id"),
                    "status": sub_data.get("status", "active"),
                    "billing_cycle": sub_data.get("billing_cycle", "monthly"),
                    "current_period_start": sub_data.get("current_period_start"),
                    "current_period_end": sub_data.get("current_period_end"),
                    "cancel_at_period_end": sub_data.get("cancel_at_period_end", False),
                    "canceled_at": None,
                    "trial_end": None
                }

        # No active subscription - fall back to free plan
        # Look up the free plan from subscription_plans table
        plan_response = db_service.client.table("subscription_plans").select("*").eq(
            "name", "free"
        ).maybe_single().execute()

        if not plan_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription plan found"
            )

        # Return a synthetic subscription for free plan
        return {
            "id": f"{tenant_id}_free",
            "tenant_id": tenant_id,
            "plan": plan_response.data,
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "status": "active",
            "billing_cycle": "monthly",
            "current_period_start": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
            "canceled_at": None,
            "trial_end": None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription: {str(e)}"
        )


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    checkout: CheckoutSessionCreate,
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
):
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
async def create_portal_session(
    return_url: str,
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
):
    """Create a Stripe customer portal session (on-demand, short-lived)"""
    try:
        tenant_id = user_info["tenant"]["id"]
        # Get subscription with customer ID
        response = db_service.client.table("subscriptions").select("stripe_customer_id").eq("tenant_id", tenant_id).maybe_single().execute()

        if not response.data or not response.data.get("stripe_customer_id"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found. Please create a subscription first."
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
async def cancel_subscription(
    at_period_end: bool = True,
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
):
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
async def reactivate_subscription(
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
):
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


@router.get("/invoices", response_model=PaginatedResponse[InvoiceResponse])
async def get_invoices(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
):
    """
    Get invoices for current tenant with server-side pagination.

    This endpoint returns paginated invoices from Stripe with date-based ordering.
    Stripe automatically orders invoices by creation date (newest first), providing
    deterministic ordering.

    Query params:
        page: Page number (1-indexed, default 1)
        page_size: Items per page (default 50, max 100)

    Returns:
        PaginatedResponse with invoices and pagination metadata
    """
    try:
        tenant_id = user_info["tenant"]["id"]
        
        # Ensure page_size is within bounds
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        page = max(1, page)
        
        # Get subscription with customer ID
        response = db_service.client.table("subscriptions").select("stripe_customer_id").eq("tenant_id", tenant_id).maybe_single().execute()

        if not response or not response.data or not response.data.get("stripe_customer_id"):
            # No customer, return empty paginated response
            return PaginatedResponse.create(
                items=[],
                page=page,
                page_size=page_size,
                total=0
            )

        customer_id = response.data["stripe_customer_id"]

        # Stripe uses cursor-based pagination. To support page numbers, we need to:
        # 1. For page 1: fetch directly
        # 2. For page > 1: fetch all items up to the requested page (not efficient for large pages,
        #    but necessary due to Stripe's cursor-based approach)
        # Note: For production with many invoices, consider caching or switching to cursor-based pagination
        
        all_invoices = []
        starting_after = None
        items_to_fetch = page * page_size
        
        # Fetch invoices in batches until we have enough for the requested page
        while len(all_invoices) < items_to_fetch:
            batch_size = min(100, items_to_fetch - len(all_invoices))  # Stripe max is 100
            result = await stripe_service.list_invoices(customer_id, batch_size, starting_after)
            batch_invoices = result["data"]
            
            if not batch_invoices:
                break
                
            all_invoices.extend(batch_invoices)
            
            # If there are no more invoices, stop
            if not result["has_more"]:
                break
                
            # Set cursor for next batch
            starting_after = batch_invoices[-1]["id"]
        
        # Calculate pagination metadata
        total = len(all_invoices)  # Note: This is a lower bound, actual total may be higher
        
        # If we got exactly the amount we requested and has_more is True, fetch one more to get accurate total
        if len(all_invoices) == items_to_fetch and result.get("has_more", False):
            # There are more invoices, so total is at least items_to_fetch + 1
            # For simplicity, we'll just indicate has_more in the response
            total = items_to_fetch + 1  # Minimum total
        
        # Extract the page of items
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_items = all_invoices[start_idx:end_idx]
        
        return PaginatedResponse.create(
            items=page_items,
            page=page,
            page_size=page_size,
            total=total
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch invoices: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch invoices: {str(e)}"
        )


@router.get("/upcoming-invoice", response_model=UpcomingInvoiceResponse)
async def get_upcoming_invoice(
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
):
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


@router.get("/payment-history", response_model=PaginatedResponse[PaymentHistoryResponse])
async def get_payment_history(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
):
    """
    Get payment history for current tenant with server-side pagination.

    This endpoint returns paginated payment history from the database with date-based ordering.
    Payments are ordered by creation date (newest first), providing deterministic ordering.

    Query params:
        page: Page number (1-indexed, default 1)
        page_size: Items per page (default 50, max 100)

    Returns:
        PaginatedResponse with payment history records and pagination metadata
    """
    try:
        tenant_id = user_info["tenant"]["id"]

        # Ensure page_size is within bounds
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        page = max(1, page)

        # Calculate offset
        offset = (page - 1) * page_size

        # Get total count
        count_response = db_service.client.table("payment_history").select(
            "*", count="exact"
        ).eq("tenant_id", tenant_id).execute()

        total = count_response.count if count_response.count is not None else 0

        # Get paginated data with date-based ordering (newest first)
        response = db_service.client.table("payment_history").select("*").eq(
            "tenant_id", tenant_id
        ).order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

        return PaginatedResponse.create(
            items=response.data or [],
            page=page,
            page_size=page_size,
            total=total
        )

    except Exception as e:
        logger.error(f"Failed to fetch payment history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch payment history: {str(e)}"
        )


@router.get("/overview", response_model=BillingOverviewResponse)
async def get_billing_overview(
    user_info: dict = Depends(get_current_user),
    _admin_guard: dict = Depends(require_tenant_admin()),
):
    """Get complete billing overview for the billing page"""
    try:
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant information not found"
            )
        tenant_id = tenant.get("id")
        if not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant ID not found"
            )
        
        # Get subscription
        subscription_data = None
        try:
            sub_response = db_service.client.table("subscriptions").select(
                "*, plan:plan_id(*)"
            ).eq("tenant_id", tenant_id).maybe_single().execute()
            subscription_data = sub_response.data if sub_response else None
        except Exception as e:
            # Table might not exist or query failed - fall back to tenant tier
            print(f"Subscription query failed: {e}")
            subscription_data = None

        if not subscription_data:
            # Fall back to tenant tier
            subscription_tier = user_info["tenant"].get("subscription_tier", "free")
            plan = {}
            try:
                plan_response = db_service.client.table("subscription_plans").select("*").eq(
                    "name", subscription_tier
                ).maybe_single().execute()

                if not (plan_response and plan_response.data):
                    plan_response = db_service.client.table("subscription_plans").select("*").eq(
                        "name", "free"
                    ).maybe_single().execute()

                plan = plan_response.data if (plan_response and plan_response.data) else {}
            except Exception as e:
                print(f"Plan query failed: {e}")
                plan = {"name": subscription_tier, "display_name": subscription_tier.capitalize()}

            subscription_data = {
                "id": f"{tenant_id}_tier",
                "tenant_id": tenant_id,
                "plan": plan,
                "status": "active",
                "billing_cycle": "monthly",
                "current_period_end": None,
                "cancel_at_period_end": False,
                "stripe_customer_id": None,
                "stripe_subscription_id": None
            }
        
        plan_data = subscription_data.get("plan", {})
        plan_name = plan_data.get("name", "free")
        plan_display = plan_data.get("display_name", plan_name.capitalize())
        
        # Get usage
        env_count = db_service.client.table("environments").select("id", count="exact").eq("tenant_id", tenant_id).execute()
        team_count = db_service.client.table("users").select("id", count="exact").eq("tenant_id", tenant_id).execute()
        
        # Get entitlements
        try:
            entitlements = await entitlements_service.get_tenant_entitlements(tenant_id)
            features = entitlements.get("features", {})
        except Exception:
            features = plan_data.get("features", {})
        
        # Determine if plan is custom (before normalizing entitlements)
        plan_is_custom = plan_name not in ["free", "pro", "agency", "enterprise"]
        
        # Format entitlements with proper values - normalize to prevent undefined
        def normalize_entitlement(value, is_custom: bool = False):
            """Normalize entitlement values: null/undefined -> Custom or —, -1 -> Unlimited"""
            if value is None or value == "undefined":
                # If plan is custom and value is missing, it's likely a custom limit
                if is_custom:
                    return "Custom"
                # Otherwise, it's not configured
                return "—"
            if isinstance(value, str):
                value_lower = value.lower()
                if value_lower in ["unlimited", "inf", "-1", "null", "undefined"]:
                    return "Unlimited"
                # Try to parse as number
                try:
                    num_val = float(value)
                    if num_val == -1 or num_val >= 9999:
                        return "Unlimited"
                    return int(num_val) if num_val.is_integer() else num_val
                except (ValueError, TypeError):
                    return value
            if isinstance(value, (int, float)):
                if value == -1 or value >= 9999:
                    return "Unlimited"
                return int(value) if isinstance(value, float) and value.is_integer() else value
            return value
        
        # Get invoices and payment method
        invoices = []
        payment_method = None
        
        if subscription_data.get("stripe_customer_id"):
            customer_id = subscription_data["stripe_customer_id"]
            try:
                result = await stripe_service.list_invoices(customer_id, 10)
                invoices = result["data"]
                payment_method = await stripe_service.get_default_payment_method(customer_id)
            except Exception:
                pass
        
        # Get upcoming invoice amount
        next_amount_cents = None
        if subscription_data.get("stripe_subscription_id") and subscription_data.get("status") in ["active", "trialing"]:
            try:
                upcoming = await stripe_service.get_upcoming_invoice(subscription_data["stripe_customer_id"])
                if upcoming:
                    next_amount_cents = int(upcoming["amount_due"] * 100)
            except Exception:
                pass
        
        # Format subscription response
        subscription_status = subscription_data.get("status", "active")
        billing_cycle = subscription_data.get("billing_cycle", "monthly")
        current_period_end = subscription_data.get("current_period_end")
        cancel_at_period_end = subscription_data.get("cancel_at_period_end", False)
        
        # Format current_period_end - handle both datetime objects and strings
        formatted_period_end = None
        if current_period_end:
            if isinstance(current_period_end, str):
                formatted_period_end = current_period_end
            elif hasattr(current_period_end, 'isoformat'):
                formatted_period_end = current_period_end.isoformat()
            else:
                formatted_period_end = str(current_period_end)
        
        return {
            "plan": {
                "key": plan_name,
                "name": plan_display,
                "is_custom": plan_is_custom
            },
            "subscription": {
                "status": subscription_status,
                "interval": "month" if billing_cycle == "monthly" else "year",
                "current_period_end": formatted_period_end,
                "cancel_at_period_end": cancel_at_period_end,
                "next_amount_cents": next_amount_cents,
                "currency": "USD"
            },
            "usage": {
                "environments_used": env_count.count or 0,
                "team_members_used": team_count.count or 0
            },
            "entitlements": {
                "environments_limit": normalize_entitlement(features.get("max_environments") or plan_data.get("max_environments"), plan_is_custom),
                "team_members_limit": normalize_entitlement(features.get("max_team_members") or plan_data.get("max_team_members"), plan_is_custom),
                "promotions_monthly_limit": normalize_entitlement(features.get("max_promotions_per_month"), plan_is_custom),
                "snapshots_monthly_limit": normalize_entitlement(features.get("max_snapshots_per_month") or "Unlimited" if features.get("snapshots_enabled") else None, plan_is_custom),
            },
            "payment_method": payment_method,
            "invoices": invoices,
            "links": {
                "stripe_portal_url": "",
                "change_plan_url": "/billing/change-plan",
                "usage_limits_url": "/admin/usage",
                "entitlements_audit_url": "/admin/entitlements-audit"
            }
        }
        
    except HTTPException:
        raise
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Missing required data: {str(e)}"
        )
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        error_details = traceback.format_exc()
        logger.error(f"Billing overview error: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch billing overview: {str(e)}"
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
        logger.warning("Checkout completed webhook received without tenant_id")
        return

    # Acquire webhook lock to prevent race conditions
    async with webhook_lock_service.acquire_webhook_lock(tenant_id, "checkout") as locked:
        if not locked:
            logger.error(f"Failed to acquire webhook lock for tenant {tenant_id} in checkout.session.completed")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another webhook is currently processing for this tenant. Please retry."
            )

        logger.info(f"Processing checkout.session.completed for tenant {tenant_id}")

        # Get subscription from Stripe
        stripe_subscription_id = _obj_get(session, "subscription")
        subscription = await stripe_service.get_subscription(stripe_subscription_id)

        # Get plan ID from price
        price_id = _extract_first_price_id(subscription)
        if not price_id:
            logger.warning(f"No price_id found in subscription for tenant {tenant_id}")
            return

        plan_response = db_service.client.table("subscription_plans").select("id, name").or_(
            f"stripe_price_id_monthly.eq.{price_id},stripe_price_id_yearly.eq.{price_id}"
        ).single().execute()
        if not plan_response.data:
            logger.warning(f"No plan found for price_id {price_id} for tenant {tenant_id}")
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

        logger.info(f"Successfully processed checkout.session.completed for tenant {tenant_id}, plan: {next_plan}")


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
        logger.warning(f"Subscription updated webhook missing tenant_id or subscription_id: {subscription_id}")
        return

    # Acquire webhook lock to prevent race conditions
    async with webhook_lock_service.acquire_webhook_lock(tenant_id, "subscription") as locked:
        if not locked:
            logger.error(f"Failed to acquire webhook lock for tenant {tenant_id} in customer.subscription.updated")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another webhook is currently processing for this tenant. Please retry."
            )

        logger.info(f"Processing customer.subscription.updated for tenant {tenant_id}, subscription {subscription_id}")

        # Get the current plan before updating
        old_plan_name = "free"
        try:
            old_sub_response = db_service.client.table("subscriptions").select(
                "plan:plan_id(name)"
            ).eq("stripe_subscription_id", subscription_id).maybe_single().execute()

            if old_sub_response and old_sub_response.data:
                plan_data = old_sub_response.data.get("plan") or {}
                old_plan_name = (plan_data.get("name") or "free").lower()
        except Exception as e:
            logger.warning(f"Could not retrieve old plan for tenant {tenant_id}: {e}")

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

        # Check if this is a downgrade and handle it
        old_precedence = await _get_plan_precedence(old_plan_name)
        new_precedence = await _get_plan_precedence(next_plan)

        if new_precedence < old_precedence:
            logger.info(
                f"Downgrade detected for tenant {tenant_id}: {old_plan_name} "
                f"(precedence {old_precedence}) -> {next_plan} (precedence {new_precedence})"
            )

            try:
                # Handle the downgrade using the downgrade service
                downgrade_summary = await downgrade_service.handle_plan_downgrade(
                    tenant_id=tenant_id,
                    old_plan=old_plan_name,
                    new_plan=next_plan
                )

                logger.info(
                    f"Downgrade handling completed for tenant {tenant_id}. "
                    f"Summary: {downgrade_summary.get('actions_taken', [])} | "
                    f"Grace periods created: {len(downgrade_summary.get('grace_periods_created', []))} | "
                    f"Errors: {downgrade_summary.get('errors', [])}"
                )

                if downgrade_summary.get("errors"):
                    logger.error(
                        f"Errors during downgrade handling for tenant {tenant_id}: "
                        f"{downgrade_summary['errors']}"
                    )

            except Exception as e:
                logger.error(
                    f"Failed to handle downgrade for tenant {tenant_id} "
                    f"from {old_plan_name} to {next_plan}: {e}",
                    exc_info=True
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Downgrade handling failed; please retry webhook."
                )
        elif new_precedence > old_precedence:
            logger.info(
                f"Upgrade detected for tenant {tenant_id}: {old_plan_name} "
                f"(precedence {old_precedence}) -> {next_plan} (precedence {new_precedence})"
            )

            try:
                # Handle the upgrade - cancel grace periods for now-compliant resources
                upgrade_summary = await downgrade_service.handle_plan_upgrade(
                    tenant_id=tenant_id,
                    old_plan=old_plan_name,
                    new_plan=next_plan
                )

                logger.info(
                    f"Upgrade handling completed for tenant {tenant_id}. "
                    f"Summary: {upgrade_summary.get('actions_taken', [])} | "
                    f"Grace periods cancelled: {upgrade_summary.get('grace_periods_cancelled', 0)} | "
                    f"Errors: {upgrade_summary.get('errors', [])}"
                )

                if upgrade_summary.get("errors"):
                    logger.error(
                        f"Errors during upgrade handling for tenant {tenant_id}: "
                        f"{upgrade_summary['errors']}"
                    )

            except Exception as e:
                logger.error(
                    f"Failed to handle upgrade for tenant {tenant_id} "
                    f"from {old_plan_name} to {next_plan}: {e}",
                    exc_info=True
                )
                # Don't raise HTTPException for upgrade failures - log and continue
                # Upgrades should not block webhook processing
        else:
            logger.debug(f"No plan tier change for tenant {tenant_id}, plan remains: {next_plan}")

        logger.info(f"Successfully processed customer.subscription.updated for tenant {tenant_id}, new plan: {next_plan}")


async def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    subscription_id = _obj_get(subscription, "id")
    md = _obj_metadata(subscription)
    tenant_id = md.get("tenant_id")
    if not tenant_id and subscription_id:
        existing = (
            db_service.client.table("subscriptions")
            .select("tenant_id, plan:plan_id(name)")
            .eq("stripe_subscription_id", subscription_id)
            .single()
            .execute()
        )
        if existing.data:
            tenant_id = existing.data.get("tenant_id")
    if not subscription_id:
        logger.warning("Subscription deleted webhook missing subscription_id")
        return

    # Acquire webhook lock to prevent race conditions
    # Use a generic lock key even if tenant_id is missing, based on subscription_id
    lock_key = tenant_id if tenant_id else f"sub_{subscription_id}"
    async with webhook_lock_service.acquire_webhook_lock(lock_key, "subscription_deleted") as locked:
        if not locked:
            logger.error(f"Failed to acquire webhook lock for {lock_key} in customer.subscription.deleted")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another webhook is currently processing for this tenant. Please retry."
            )

        logger.info(f"Processing customer.subscription.deleted for subscription {subscription_id}, tenant {tenant_id}")

        # Get the old plan before updating
        old_plan_name = "free"
        if tenant_id:
            try:
                old_sub_response = db_service.client.table("subscriptions").select(
                    "plan:plan_id(name)"
                ).eq("stripe_subscription_id", subscription_id).maybe_single().execute()

                if old_sub_response and old_sub_response.data:
                    plan_data = old_sub_response.data.get("plan") or {}
                    old_plan_name = (plan_data.get("name") or "free").lower()
            except Exception as e:
                logger.warning(f"Could not retrieve old plan for tenant {tenant_id}: {e}")

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

            # Handle downgrade to free plan if they had a paid plan
            if old_plan_name != "free":
                logger.info(
                    f"Subscription deleted - downgrade from {old_plan_name} to free "
                    f"for tenant {tenant_id}"
                )

                try:
                    # Handle the downgrade using the downgrade service
                    downgrade_summary = await downgrade_service.handle_plan_downgrade(
                        tenant_id=tenant_id,
                        old_plan=old_plan_name,
                        new_plan="free"
                    )

                    logger.info(
                        f"Downgrade handling completed for tenant {tenant_id}. "
                        f"Summary: {downgrade_summary.get('actions_taken', [])} | "
                        f"Grace periods created: {len(downgrade_summary.get('grace_periods_created', []))} | "
                        f"Errors: {downgrade_summary.get('errors', [])}"
                    )

                    if downgrade_summary.get("errors"):
                        logger.error(
                            f"Errors during downgrade handling for tenant {tenant_id}: "
                            f"{downgrade_summary['errors']}"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to handle downgrade for tenant {tenant_id} "
                        f"from {old_plan_name} to free: {e}",
                        exc_info=True
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Downgrade handling failed; please retry webhook."
                    )

            logger.info(f"Successfully processed customer.subscription.deleted for tenant {tenant_id}, downgraded to free")
        else:
            logger.warning(f"Subscription {subscription_id} deleted but no tenant_id found")


async def handle_payment_succeeded(invoice):
    """Handle successful payment"""
    # Get tenant from customer
    customer_id = invoice.get("customer")
    if not customer_id:
        logger.warning("Payment succeeded webhook missing customer_id")
        return

    sub_response = db_service.client.table("subscriptions").select("id, tenant_id").eq(
        "stripe_customer_id", customer_id
    ).single().execute()

    if sub_response.data:
        tenant_id = sub_response.data["tenant_id"]

        # Acquire webhook lock to prevent race conditions on payment history
        async with webhook_lock_service.acquire_webhook_lock(tenant_id, "payment") as locked:
            if not locked:
                logger.error(f"Failed to acquire webhook lock for tenant {tenant_id} in invoice.payment_succeeded")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Another webhook is currently processing for this tenant. Please retry."
                )

            logger.info(f"Processing invoice.payment_succeeded for tenant {tenant_id}, invoice {invoice['id']}")

            # Record payment in history
            db_service.client.table("payment_history").insert({
                "tenant_id": tenant_id,
                "subscription_id": sub_response.data["id"],
                "stripe_payment_intent_id": invoice.get("payment_intent"),
                "stripe_invoice_id": invoice["id"],
                "amount": invoice["amount_paid"] / 100,
                "currency": invoice["currency"].upper(),
                "status": "succeeded",
                "description": "Subscription payment"
            }).execute()

            logger.info(f"Successfully recorded payment for tenant {tenant_id}, amount: {invoice['amount_paid'] / 100}")


async def handle_payment_failed(invoice):
    """Handle failed payment"""
    # Get tenant from customer
    customer_id = invoice.get("customer")
    if not customer_id:
        logger.warning("Payment failed webhook missing customer_id")
        return

    sub_response = db_service.client.table("subscriptions").select("id, tenant_id").eq(
        "stripe_customer_id", customer_id
    ).single().execute()

    if sub_response.data:
        tenant_id = sub_response.data["tenant_id"]

        # Acquire webhook lock to prevent race conditions on payment failure handling
        async with webhook_lock_service.acquire_webhook_lock(tenant_id, "payment_failed") as locked:
            if not locked:
                logger.error(f"Failed to acquire webhook lock for tenant {tenant_id} in invoice.payment_failed")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Another webhook is currently processing for this tenant. Please retry."
                )

            logger.info(f"Processing invoice.payment_failed for tenant {tenant_id}, invoice {invoice['id']}")

            # Record failed payment
            db_service.client.table("payment_history").insert({
                "tenant_id": tenant_id,
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

            logger.warning(f"Payment failed for tenant {tenant_id}, subscription marked as past_due")
