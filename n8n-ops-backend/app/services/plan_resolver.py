"""
Plan Resolver - Single Source of Truth for Tenant Plans

This module provides the canonical resolver for determining a tenant's effective plan.
The ONLY source of truth is `tenant_provider_subscriptions` table.

Precedence rules:
- enterprise = 30 (highest)
- agency = 20
- pro = 10
- free = 0 (default when no active subscriptions)

A subscription is considered active when:
- status IN ('active', 'trialing')
- starts_at IS NULL OR starts_at <= now()
- ends_at IS NULL OR ends_at > now()

Multiple subscriptions per tenant are supported; highest-tier wins.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from app.services.database import db_service


# Valid active statuses
ACTIVE_STATUSES = ("active", "trialing")

# Cache for plan precedence (loaded from database)
_plan_precedence_cache: dict[str, int] = {}


def _normalize_plan_name(plan_name: Optional[str]) -> str:
    """Normalize plan name to lowercase, defaulting to 'free'."""
    if not plan_name:
        return "free"
    return plan_name.lower().strip()


async def _get_plan_rank(plan_name: str, db: Any = None) -> int:
    """Get the precedence rank for a plan name from database."""
    if db is None:
        db = db_service
    
    normalized = _normalize_plan_name(plan_name)
    
    # Check cache first
    if normalized in _plan_precedence_cache:
        return _plan_precedence_cache[normalized]
    
    # Fetch from database
    try:
        response = db.client.table("plans").select("precedence").eq("name", normalized).single().execute()
        if response.data:
            precedence = response.data.get("precedence", 0)
            _plan_precedence_cache[normalized] = precedence
            return precedence
    except Exception:
        pass
    
    # Fallback to default (0 for free, or unknown plans)
    default = 0 if normalized == "free" else 0
    _plan_precedence_cache[normalized] = default
    return default


def _is_subscription_active(subscription: dict, now: datetime) -> bool:
    """
    Check if a subscription is currently active.

    Active criteria:
    - status in ('active', 'trialing')
    - starts_at is null OR starts_at <= now
    - ends_at is null OR ends_at > now (using current_period_end as ends_at)
    """
    status = subscription.get("status", "").lower()
    if status not in ACTIVE_STATUSES:
        return False

    # Check starts_at (if present)
    starts_at = subscription.get("starts_at") or subscription.get("current_period_start")
    if starts_at:
        try:
            if isinstance(starts_at, str):
                # Parse ISO format datetime
                starts_dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
            else:
                starts_dt = starts_at
            if starts_dt > now:
                return False
        except (ValueError, TypeError):
            pass  # If we can't parse, assume it's valid

    # Check ends_at (using current_period_end as the effective end date)
    ends_at = subscription.get("ends_at") or subscription.get("current_period_end")
    if ends_at:
        try:
            if isinstance(ends_at, str):
                ends_dt = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
            else:
                ends_dt = ends_at
            if ends_dt <= now:
                return False
        except (ValueError, TypeError):
            pass  # If we can't parse, assume it's valid

    return True


async def resolve_effective_plan(
    tenant_id: UUID | str,
    db: Any = None  # Optional db parameter for future flexibility
) -> dict:
    """
    Resolve the effective plan for a tenant from tenant_provider_subscriptions.

    This is the SINGLE SOURCE OF TRUTH for plan determination.

    Args:
        tenant_id: The tenant UUID
        db: Optional database service (uses default db_service if not provided)

    Returns:
        dict with keys:
            - plan_name: str (lowercase, e.g., "pro", "enterprise", "free")
            - source: str (always "provider_subscriptions")
            - contributing_subscriptions: list of subscription IDs that were considered
            - highest_subscription_id: UUID of the subscription providing the effective plan (or None)
            - plan_rank: int (precedence rank of the effective plan)
    """
    if db is None:
        db = db_service

    tenant_id_str = str(tenant_id)
    now = datetime.now(timezone.utc)

    # Query all subscriptions for this tenant with plan details
    # Join to provider_plans to get the plan name
    # Note: starts_at/ends_at columns may not exist; we rely on current_period_start/end
    response = db.client.table("tenant_provider_subscriptions").select(
        "id, tenant_id, provider_id, plan_id, status, "
        "current_period_start, current_period_end, "
        "plan:plan_id(id, name, display_name)"
    ).eq("tenant_id", tenant_id_str).execute()

    subscriptions = response.data or []

    # Filter to active subscriptions and find highest-tier
    active_subs = []
    highest_plan = "free"
    highest_rank = 0
    highest_sub_id = None
    contributing_ids = []

    for sub in subscriptions:
        if not _is_subscription_active(sub, now):
            continue

        # Get plan name from joined plan data
        plan_data = sub.get("plan") or {}
        plan_name = _normalize_plan_name(plan_data.get("name"))
        plan_rank = await _get_plan_rank(plan_name, db)

        active_subs.append({
            "id": sub.get("id"),
            "plan_name": plan_name,
            "plan_rank": plan_rank,
            "provider_id": sub.get("provider_id"),
        })
        contributing_ids.append(sub.get("id"))

        # Track highest tier
        if plan_rank > highest_rank:
            highest_rank = plan_rank
            highest_plan = plan_name
            highest_sub_id = sub.get("id")

    return {
        "plan_name": highest_plan,
        "source": "provider_subscriptions",
        "contributing_subscriptions": contributing_ids,
        "highest_subscription_id": highest_sub_id,
        "plan_rank": highest_rank,
        "active_subscriptions": active_subs,
    }


async def get_effective_plan_name(tenant_id: UUID | str) -> str:
    """
    Convenience function to get just the plan name.

    Args:
        tenant_id: The tenant UUID

    Returns:
        str: The effective plan name (lowercase)
    """
    result = await resolve_effective_plan(tenant_id)
    return result["plan_name"]


async def sync_legacy_fields(tenant_id: UUID | str, plan_name: str) -> None:
    """
    Sync the resolved plan to legacy fields for backwards compatibility.

    This updates:
    - tenants.subscription_tier
    - tenant_plans (if keeping for cache/history)

    Note: This is optional and for backwards compatibility during migration.
    These fields should NOT be used for gating decisions.

    Args:
        tenant_id: The tenant UUID
        plan_name: The resolved plan name
    """
    tenant_id_str = str(tenant_id)

    # Update tenants.subscription_tier
    try:
        db_service.client.table("tenants").update({
            "subscription_tier": plan_name
        }).eq("id", tenant_id_str).execute()
    except Exception:
        pass  # Non-critical, legacy field
