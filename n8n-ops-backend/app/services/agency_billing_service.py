"""Agency billing helpers (core billing mirror, entitlements are canonical).

# Migration: 7c71b22483d5 - add_tenant_hierarchy_and_billing_items
# See: alembic/versions/7c71b22483d5_add_tenant_hierarchy_and_billing_items.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Literal

from app.services.database import db_service
from app.services.stripe_service import stripe_service


UsageType = Literal["base", "per_client"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _obj_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _extract_subscription_items(subscription: Any) -> list[Dict[str, Any]]:
    """
    Returns list of {stripe_subscription_item_id, stripe_price_id, quantity}.
    Works for both dict-shaped subscriptions and Stripe webhook objects.
    """
    if isinstance(subscription, dict):
        items = (subscription.get("items") or {}).get("data") or []
        result = []
        for item in items:
            price = item.get("price") or {}
            result.append(
                {
                    "stripe_subscription_item_id": item.get("id"),
                    "stripe_price_id": (price.get("id") if isinstance(price, dict) else None),
                    "quantity": item.get("quantity"),
                }
            )
        return [r for r in result if r.get("stripe_subscription_item_id") and r.get("stripe_price_id")]

    items = _obj_get(subscription, "items")
    data = getattr(items, "data", None) if items is not None else None
    if not data:
        return []
    out = []
    for item in data:
        price = getattr(item, "price", None)
        out.append(
            {
                "stripe_subscription_item_id": getattr(item, "id", None),
                "stripe_price_id": getattr(price, "id", None) if price else None,
                "quantity": getattr(item, "quantity", None),
            }
        )
    return [r for r in out if r.get("stripe_subscription_item_id") and r.get("stripe_price_id")]


async def get_active_client_count(agency_tenant_id: str) -> int:
    # Billing.md authoritative definition: child tenants with status=active.
    try:
        resp = (
            db_service.client.table("tenants")
            .select("id", count="exact")
            .eq("parent_tenant_id", agency_tenant_id)
            .eq("status", "active")
            .execute()
        )
        return resp.count or 0
    except Exception:
        resp = (
            db_service.client.table("tenants")
            .select("id", count="exact")
            .eq("parent_tenant_id", agency_tenant_id)
            .execute()
        )
        return resp.count or 0


async def resolve_usage_type_from_price_id(price_id: str) -> Optional[UsageType]:
    resp = (
        db_service.client.table("subscription_plan_price_items")
        .select("usage_type")
        .or_(f"stripe_price_id_monthly.eq.{price_id},stripe_price_id_yearly.eq.{price_id}")
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    usage_type = (resp.data[0].get("usage_type") or "").lower()
    if usage_type in ("base", "per_client"):
        return usage_type  # type: ignore[return-value]
    return None


async def upsert_subscription_items(
    tenant_id: str,
    stripe_subscription_id: str,
    subscription: Any,
) -> None:
    now = _now_iso()
    for item in _extract_subscription_items(subscription):
        usage_type: UsageType = (await resolve_usage_type_from_price_id(item["stripe_price_id"])) or "base"
        db_service.client.table("subscription_items").upsert(
            {
                "tenant_id": tenant_id,
                "stripe_subscription_id": stripe_subscription_id,
                "stripe_subscription_item_id": item["stripe_subscription_item_id"],
                "stripe_price_id": item["stripe_price_id"],
                "usage_type": usage_type,
                "updated_at": now,
            },
            on_conflict="stripe_subscription_item_id",
        ).execute()


async def get_agency_subscription_id(agency_tenant_id: str) -> Optional[str]:
    resp = (
        db_service.client.table("subscriptions")
        .select("stripe_subscription_id")
        .eq("tenant_id", agency_tenant_id)
        .single()
        .execute()
    )
    if not resp.data:
        return None
    return resp.data.get("stripe_subscription_id")


async def get_per_client_subscription_item_id(
    agency_tenant_id: str,
    stripe_subscription_id: str,
) -> Optional[str]:
    resp = (
        db_service.client.table("subscription_items")
        .select("stripe_subscription_item_id")
        .eq("tenant_id", agency_tenant_id)
        .eq("stripe_subscription_id", stripe_subscription_id)
        .eq("usage_type", "per_client")
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0].get("stripe_subscription_item_id")
    return None


async def update_agency_per_client_quantity(agency_tenant_id: str) -> None:
    stripe_subscription_id = await get_agency_subscription_id(agency_tenant_id)
    if not stripe_subscription_id:
        return

    # Ensure we have subscription items persisted (in case webhooks were missed).
    subscription = await stripe_service.get_subscription(stripe_subscription_id)
    await upsert_subscription_items(agency_tenant_id, stripe_subscription_id, subscription)

    per_client_item_id = await get_per_client_subscription_item_id(agency_tenant_id, stripe_subscription_id)
    if not per_client_item_id:
        return

    qty = await get_active_client_count(agency_tenant_id)
    await stripe_service.update_subscription_item_quantity(per_client_item_id, qty)


