#!/usr/bin/env python3
"""
Admin reconciliation command for Billing.md.

- Recompute client counts
- Verify/repair Stripe quantities (agency per-client item)
- Verify/repair tenant_plans (canonical entitlements) based on billing mirror
- Persist Stripe subscription items into subscription_items

Safe to re-run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import asyncio


def _plan_from_status(status_value: Optional[str], cancel_at_period_end: bool, paid_plan: str) -> str:
    status_norm = (status_value or "").lower()
    if status_norm in {"trialing", "active"}:
        return paid_plan
    if status_norm in {"canceled", "unpaid", "incomplete_expired"}:
        return "free"
    if cancel_at_period_end:
        return paid_plan
    return "free"

async def _run(dry_run: bool, tenant_id: Optional[str]) -> int:
    from app.services.database import db_service
    from app.services.stripe_service import stripe_service
    from app.services.tenant_plan_service import set_tenant_plan
    from app.services.agency_billing_service import (
        upsert_subscription_items,
        update_agency_per_client_quantity,
    )

    # Cache subscription_plans.id -> name
    plan_name_by_id: Dict[str, str] = {}
    plans_resp = db_service.client.table("subscription_plans").select("id, name").execute()
    for row in plans_resp.data or []:
        if row.get("id") and row.get("name"):
            plan_name_by_id[row["id"]] = str(row["name"]).lower()

    subs_query = db_service.client.table("subscriptions").select(
        "tenant_id, plan_id, status, cancel_at_period_end, stripe_subscription_id"
    )
    if tenant_id:
        subs_query = subs_query.eq("tenant_id", tenant_id)
    subs_resp = subs_query.execute()
    subscriptions = subs_resp.data or []

    print(f"Found {len(subscriptions)} subscription records")

    # 1) Sync tenant_plans to billing mirror and persist subscription items
    for sub in subscriptions:
        tenant_id = sub.get("tenant_id")
        if not tenant_id:
            continue

        plan_id = sub.get("plan_id")
        paid_plan = plan_name_by_id.get(plan_id, "free") if plan_id else "free"
        desired_plan = _plan_from_status(sub.get("status"), bool(sub.get("cancel_at_period_end")), paid_plan)

        if dry_run:
            print(f"[dry-run] set_tenant_plan tenant={tenant_id} -> {desired_plan}")
        else:
            await set_tenant_plan(tenant_id, desired_plan)  # type: ignore[arg-type]

        stripe_subscription_id = sub.get("stripe_subscription_id")
        if stripe_subscription_id:
            try:
                if dry_run:
                    print(f"[dry-run] fetch+upsert subscription_items tenant={tenant_id} sub={stripe_subscription_id}")
                else:
                    stripe_sub = await stripe_service.get_subscription(stripe_subscription_id)
                    await upsert_subscription_items(tenant_id, stripe_subscription_id, stripe_sub)
            except Exception as e:
                print(f"⚠️  Failed syncing subscription_items for tenant={tenant_id}: {e}")

    # 2) Reconcile agency per-client quantities
    try:
        parent_ids = set()
        child_resp = db_service.client.table("tenants").select("parent_tenant_id").neq("parent_tenant_id", None).execute()
        for row in child_resp.data or []:
            if row.get("parent_tenant_id"):
                parent_ids.add(row["parent_tenant_id"])
    except Exception:
        parent_ids = set()

    if tenant_id:
        parent_ids = {tenant_id} if tenant_id in parent_ids else set()

    if parent_ids:
        print(f"Reconciling agency per-client quantities for {len(parent_ids)} parent tenants")

    for agency_tenant_id in sorted(parent_ids):
        if dry_run:
            print(f"[dry-run] update_agency_per_client_quantity tenant={agency_tenant_id}")
            continue
        try:
            await update_agency_per_client_quantity(agency_tenant_id)
        except Exception as e:
            print(f"⚠️  Failed updating per-client quantity for agency tenant={agency_tenant_id}: {e}")

    print("Reconciliation complete")
    return 0


if __name__ == "__main__":
    argp = argparse.ArgumentParser(description="Reconcile billing + entitlements drift (Billing.md).")
    argp.add_argument("--dry-run", action="store_true", help="Compute actions but do not write to DB or Stripe")
    argp.add_argument("--tenant-id", help="Limit reconciliation to a single tenant id")
    _args = argp.parse_args()
    raise SystemExit(asyncio.run(_run(_args.dry_run, _args.tenant_id)))


