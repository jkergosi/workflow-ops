"""Tenant plan assignment helpers (entitlements are canonical).

# Migration: 7c71b22483d5 - add_tenant_hierarchy_and_billing_items
# See: alembic/versions/7c71b22483d5_add_tenant_hierarchy_and_billing_items.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Literal

from app.services.database import db_service


PlanName = Literal["free", "pro", "agency", "enterprise"]


@dataclass(frozen=True)
class TenantPlanAssignment:
    tenant_id: str
    plan_id: str
    plan_name: PlanName
    entitlements_version: int


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_tenant_parent_id(tenant_id: str) -> Optional[str]:
    resp = (
        db_service.client.table("tenants")
        .select("parent_tenant_id")
        .eq("id", tenant_id)
        .single()
        .execute()
    )
    if not resp.data:
        return None
    return resp.data.get("parent_tenant_id")


async def list_child_tenant_ids(parent_tenant_id: str) -> list[str]:
    resp = (
        db_service.client.table("tenants")
        .select("id")
        .eq("parent_tenant_id", parent_tenant_id)
        .execute()
    )
    return [row["id"] for row in (resp.data or []) if row.get("id")]


async def resolve_plan_id(plan_name: PlanName) -> Optional[str]:
    resp = (
        db_service.client.table("plans")
        .select("id")
        .eq("name", plan_name)
        .eq("is_active", True)
        .single()
        .execute()
    )
    return resp.data.get("id") if resp.data else None


async def get_current_active_plan(tenant_id: str) -> Optional[TenantPlanAssignment]:
    now = _now_iso()
    resp = (
        db_service.client.table("tenant_plans")
        .select("tenant_id, plan_id, entitlements_version, plan:plan_id(name)")
        .eq("tenant_id", tenant_id)
        .eq("is_active", True)
        .lte("effective_from", now)
        .or_(f"effective_until.is.null,effective_until.gt.{now}")
        .order("effective_from", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    row = resp.data[0]
    plan = row.get("plan") or {}
    plan_name = plan.get("name")
    if not plan_name:
        return None
    return TenantPlanAssignment(
        tenant_id=row["tenant_id"],
        plan_id=row["plan_id"],
        plan_name=plan_name,
        entitlements_version=int(row.get("entitlements_version") or 1),
    )


async def _set_plan_for_tenant(
    tenant_id: str,
    plan_name: PlanName,
    *,
    allow_child_override: bool,
) -> bool:
    parent_id = await get_tenant_parent_id(tenant_id)
    if parent_id and not allow_child_override:
        raise ValueError("Client tenants may not have independent plan assignment")

    desired_plan_id = await resolve_plan_id(plan_name)
    if not desired_plan_id:
        raise ValueError(f"Plan not found or inactive: {plan_name}")

    current = await get_current_active_plan(tenant_id)
    if current and current.plan_name == plan_name:
        return False

    now = _now_iso()
    next_version = (current.entitlements_version + 1) if current else 1

    # Deactivate any active plan rows first (unique partial index enforces one active).
    (
        db_service.client.table("tenant_plans")
        .update(
            {
                "is_active": False,
                "effective_until": now,
                "updated_at": now,
            }
        )
        .eq("tenant_id", tenant_id)
        .eq("is_active", True)
        .execute()
    )

    db_service.client.table("tenant_plans").insert(
        {
            "tenant_id": tenant_id,
            "plan_id": desired_plan_id,
            "entitlements_version": next_version,
            "effective_from": now,
            "effective_until": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
    ).execute()

    # Keep legacy mirror field aligned for admin/UI reporting.
    db_service.client.table("tenants").update(
        {"subscription_tier": plan_name}
    ).eq("id", tenant_id).execute()

    return True


async def set_tenant_plan(tenant_id: str, plan_name: PlanName) -> bool:
    """
    Set the canonical entitlements plan for a tenant.

    Billing.md rules implemented:
    - Agency tenants are parents (parent_tenant_id is NULL).
    - Client tenants inherit via propagation (no independent assignment).
    - Downgrading an agency to non-agency plans downgrades clients to free.
    """
    parent_id = await get_tenant_parent_id(tenant_id)
    is_agency_tenant = parent_id is None

    changed = await _set_plan_for_tenant(
        tenant_id,
        plan_name,
        allow_child_override=False,
    )

    if not is_agency_tenant:
        # Client tenants do not have independent plan assignment.
        return changed

    child_ids = await list_child_tenant_ids(tenant_id)
    if not child_ids:
        return changed

    child_plan: PlanName = plan_name if plan_name in ("agency", "enterprise") else "free"
    for child_id in child_ids:
        await _set_plan_for_tenant(child_id, child_plan, allow_child_override=True)

    return True


