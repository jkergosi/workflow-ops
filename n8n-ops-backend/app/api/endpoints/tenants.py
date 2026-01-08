from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.schemas.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantStats,
    TenantListResponse,
    TenantNoteCreate,
    TenantNoteResponse,
    TenantNoteListResponse,
    ScheduleDeletionRequest,
)
from app.schemas.entitlements import (
    TenantFeatureOverrideCreate,
    TenantFeatureOverrideUpdate,
    TenantFeatureOverrideResponse,
    TenantFeatureOverrideListResponse,
    FeatureConfigAuditListResponse,
    FeatureAccessLogListResponse,
    AuditEntityType,
    AccessResult,
    AuditAction,
)
from app.services.database import db_service
from app.services.audit_service import audit_service
from app.services.entitlements_service import entitlements_service
from app.services.stripe_service import stripe_service
from app.core.platform_admin import require_platform_admin
from app.schemas.provider import (
    TenantProviderSubscriptionResponse,
    TenantProviderSubscriptionSimple,
    ProviderSubscriptionUpdate,
)

router = APIRouter()


@router.get("/", response_model=TenantListResponse)
async def get_tenants(
    search: Optional[str] = Query(None, description="Search by name or email"),
    provider_key: Optional[str] = Query(None, description="Filter by provider key (n8n, make, etc.)"),
    plan_key: Optional[str] = Query(None, description="Filter by provider plan key (free, pro, agency)"),
    subscription_state: Optional[str] = Query(None, description="Filter by subscription state (none, active, past_due, canceled)"),
    tenant_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    created_from: Optional[datetime] = Query(None, description="Filter by created date from"),
    created_to: Optional[datetime] = Query(None, description="Filter by created date to"),
    sort_by: Optional[str] = Query("created_at", description="Sort by: name, email, status, workflow_count, environment_count, user_count, created_at"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: dict = Depends(require_platform_admin()),
):
    """Get all tenants with pagination and filters (platform admin only)"""
    try:
        # Migration: 119481472460 - create_tenant_admin_list_view
        # See: alembic/versions/119481472460_create_tenant_admin_list_view.py
        # Build query
        query = db_service.client.table("tenant_admin_list").select("*", count="exact")

        # Apply filters
        if search:
            query = query.or_(f"name.ilike.%{search}%,email.ilike.%{search}%")
        if tenant_status:
            query = query.eq("status", tenant_status)
        if created_from:
            query = query.gte("created_at", created_from.isoformat())
        if created_to:
            query = query.lte("created_at", created_to.isoformat())

        # Apply sorting
        valid_sort_columns = ["name", "email", "status", "workflow_count", "environment_count", "user_count", "created_at"]
        sort_column = sort_by if sort_by in valid_sort_columns else "created_at"
        is_desc = sort_order.lower() == "desc" if sort_order else True

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order(sort_column, desc=is_desc).range(offset, offset + page_size - 1)

        response = query.execute()
        tenants = response.data or []
        total = response.count or 0

        # Get all provider subscriptions for these tenants
        tenant_ids = [t["id"] for t in tenants]
        subscriptions_map = {}
        if tenant_ids:
            subs_response = db_service.client.table("tenant_provider_subscriptions").select(
                "id, tenant_id, provider_id, plan_id, status, stripe_subscription_id, created_at, updated_at"
            ).in_("tenant_id", tenant_ids).execute()
            
            # Get unique provider and plan IDs
            provider_ids = set()
            plan_ids = set()
            for sub in subs_response.data or []:
                if sub.get("provider_id"):
                    provider_ids.add(sub["provider_id"])
                if sub.get("plan_id"):
                    plan_ids.add(sub["plan_id"])
            
            # Fetch providers and plans
            providers_map = {}
            if provider_ids:
                providers_resp = db_service.client.table("providers").select("id, name, display_name").in_("id", list(provider_ids)).execute()
                for p in providers_resp.data or []:
                    providers_map[p["id"]] = p
            
            plans_map = {}
            if plan_ids:
                plans_resp = db_service.client.table("provider_plans").select("id, name, display_name").in_("id", list(plan_ids)).execute()
                for p in plans_resp.data or []:
                    plans_map[p["id"]] = p
            
            # Build subscriptions map
            for sub in subs_response.data or []:
                tenant_id = sub["tenant_id"]
                if tenant_id not in subscriptions_map:
                    subscriptions_map[tenant_id] = []
                
                provider = providers_map.get(sub["provider_id"], {})
                plan = plans_map.get(sub["plan_id"], {})
                
                subscriptions_map[tenant_id].append({
                    "id": sub["id"],
                    "provider_id": sub["provider_id"],
                    "plan_id": sub["plan_id"],
                    "status": sub["status"],
                    "stripe_subscription_id": sub.get("stripe_subscription_id"),
                    "provider": {
                        "id": sub["provider_id"],
                        "name": provider.get("name"),
                        "display_name": provider.get("display_name"),
                    },
                    "plan": {
                        "id": sub["plan_id"],
                        "name": plan.get("name"),
                        "display_name": plan.get("display_name"),
                    },
                    "created_at": sub.get("created_at"),
                    "updated_at": sub.get("updated_at"),
                })

        enriched_tenants = []
        for tenant in tenants:
            tenant_id = tenant["id"]
            provider_subs = subscriptions_map.get(tenant_id, [])
            
            # Apply provider/plan/state filters
            if provider_key or plan_key or subscription_state:
                filtered_subs = provider_subs
                
                if provider_key:
                    filtered_subs = [s for s in filtered_subs if s["provider"].get("name") == provider_key]
                
                if plan_key:
                    filtered_subs = [s for s in filtered_subs if s["plan"].get("name") == plan_key]
                
                if subscription_state:
                    if subscription_state == "none":
                        # Only include tenants with no subscriptions
                        if len(provider_subs) > 0:
                            continue
                    else:
                        # Filter by subscription status
                        filtered_subs = [s for s in filtered_subs if s["status"] == subscription_state]
                        if len(filtered_subs) == 0 and subscription_state != "none":
                            continue
                
                # If filtering by provider/plan/state and no matches, skip this tenant
                if (provider_key or plan_key or (subscription_state and subscription_state != "none")) and len(filtered_subs) == 0:
                    continue

            enriched_tenants.append({
                **tenant,
                "workflow_count": tenant.get("workflow_count") or 0,
                "environment_count": tenant.get("environment_count") or 0,
                "user_count": tenant.get("user_count") or 0,
                "status": tenant.get("status", "active"),
                "provider_subscriptions": provider_subs,
                "provider_count": len(provider_subs),
            })

        # Recalculate total if filters were applied
        if provider_key or plan_key or subscription_state:
            total = len(enriched_tenants)

        return TenantListResponse(
            tenants=enriched_tenants,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenants: {str(e)}"
        )


@router.get("/stats", response_model=TenantStats)
async def get_tenant_stats(_: dict = Depends(require_platform_admin())):
    """Get tenant statistics"""
    try:
        # Get all tenants
        response = db_service.client.table("tenants").select("id, status").execute()
        tenants = response.data or []
        tenant_ids = [t["id"] for t in tenants]

        total = len(tenants)
        
        # Count by status
        active = sum(1 for t in tenants if t.get("status") == "active" or not t.get("status"))
        suspended = sum(1 for t in tenants if t.get("status") == "suspended")
        pending = sum(1 for t in tenants if t.get("status") == "pending")
        trial = sum(1 for t in tenants if t.get("status") == "trial")
        cancelled = sum(1 for t in tenants if t.get("status") == "cancelled")

        # Count tenants with/without provider subscriptions
        with_providers = 0
        no_providers = 0
        
        if tenant_ids:
            # Get unique tenant_ids that have subscriptions
            subs_response = db_service.client.table("tenant_provider_subscriptions").select(
                "tenant_id"
            ).in_("tenant_id", tenant_ids).execute()
            
            tenants_with_subs = set(s["tenant_id"] for s in subs_response.data or [])
            with_providers = len(tenants_with_subs)
            no_providers = total - with_providers
        else:
            no_providers = total

        return {
            "total": total,
            "active": active,
            "suspended": suspended,
            "pending": pending,
            "trial": trial,
            "cancelled": cancelled,
            "with_providers": with_providers,
            "no_providers": no_providers,
            "by_plan": {}  # Deprecated, kept for backward compatibility
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant stats: {str(e)}"
        )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str, _: dict = Depends(require_platform_admin())):
    """Get a specific tenant"""
    try:
        response = db_service.client.table("tenants").select("*").eq(
            "id", tenant_id
        ).single().execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )

        tenant = response.data

        # Get counts from canonical system (count unique canonical workflows)
        workflow_mappings = await db_service.client.table("workflow_env_map").select("canonical_id").eq("tenant_id", tenant_id).execute()
        unique_canonical_ids = set()
        for mapping in (workflow_mappings.data or []):
            cid = mapping.get("canonical_id")
            if cid:
                unique_canonical_ids.add(cid)
        workflow_count = len(unique_canonical_ids)
        workflow_response = type('obj', (object,), {'count': workflow_count})()

        env_response = db_service.client.table("environments").select(
            "id", count="exact"
        ).eq("tenant_id", tenant_id).execute()

        user_response = db_service.client.table("users").select(
            "id", count="exact"
        ).eq("tenant_id", tenant_id).execute()

        # Get provider subscriptions
        subs_response = db_service.client.table("tenant_provider_subscriptions").select(
            "id, provider_id, plan_id, status, stripe_subscription_id, created_at, updated_at"
        ).eq("tenant_id", tenant_id).execute()
        
        provider_subs = []
        if subs_response.data:
            provider_ids = set(s["provider_id"] for s in subs_response.data if s.get("provider_id"))
            plan_ids = set(s["plan_id"] for s in subs_response.data if s.get("plan_id"))
            
            providers_map = {}
            if provider_ids:
                providers_resp = db_service.client.table("providers").select("id, name, display_name").in_("id", list(provider_ids)).execute()
                for p in providers_resp.data or []:
                    providers_map[p["id"]] = p
            
            plans_map = {}
            if plan_ids:
                plans_resp = db_service.client.table("provider_plans").select("id, name, display_name").in_("id", list(plan_ids)).execute()
                for p in plans_resp.data or []:
                    plans_map[p["id"]] = p
            
            for sub in subs_response.data:
                provider = providers_map.get(sub["provider_id"], {})
                plan = plans_map.get(sub["plan_id"], {})
                
                provider_subs.append({
                    "id": sub["id"],
                    "provider_id": sub["provider_id"],
                    "plan_id": sub["plan_id"],
                    "status": sub["status"],
                    "stripe_subscription_id": sub.get("stripe_subscription_id"),
                    "provider": {
                        "id": sub["provider_id"],
                        "name": provider.get("name"),
                        "display_name": provider.get("display_name"),
                    },
                    "plan": {
                        "id": sub["plan_id"],
                        "name": plan.get("name"),
                        "display_name": plan.get("display_name"),
                    },
                    "created_at": sub.get("created_at"),
                    "updated_at": sub.get("updated_at"),
                })

        return {
            **tenant,
            "workflow_count": workflow_response.count or 0,
            "environment_count": env_response.count or 0,
            "user_count": user_response.count or 0,
            "provider_subscriptions": provider_subs,
            "provider_count": len(provider_subs),
            "status": tenant.get("status", "active"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant: {str(e)}"
        )


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(tenant: TenantCreate, user_info: dict = Depends(require_platform_admin())):
    """Create a new tenant"""
    try:
        # Check if email already exists
        existing = db_service.client.table("tenants").select("id").eq(
            "email", tenant.email
        ).execute()

        if existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A tenant with this email already exists"
            )

        # Create tenant
        tenant_data = {
            "name": tenant.name,
            "email": tenant.email,
            "status": "active"
        }

        response = db_service.client.table("tenants").insert(tenant_data).execute()

        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create tenant"
            )

        created_tenant = response.data[0]
        return {
            **created_tenant,
            "workflow_count": 0,
            "environment_count": 0,
            "user_count": 0,
            "provider_subscriptions": [],
            "provider_count": 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant: {str(e)}"
        )


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(tenant_id: str, tenant: TenantUpdate, user_info: dict = Depends(require_platform_admin())):
    """Update a tenant"""
    try:
        # Check if tenant exists
        existing = db_service.client.table("tenants").select("*").eq(
            "id", tenant_id
        ).single().execute()

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )

        # Build update data
        update_data = {}
        if tenant.name is not None:
            update_data["name"] = tenant.name
        if tenant.email is not None:
            update_data["email"] = tenant.email
        if tenant.status is not None:
            update_data["status"] = tenant.status.value

        if not update_data:
            # No changes, return existing tenant with counts
            return await get_tenant(tenant_id)

        # Update tenant
        response = db_service.client.table("tenants").update(update_data).eq(
            "id", tenant_id
        ).execute()

        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )

        # Return updated tenant with counts
        return await get_tenant(tenant_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tenant: {str(e)}"
        )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: str, user_info: dict = Depends(require_platform_admin())):
    """Delete a tenant and all associated data"""
    try:
        # Check if tenant exists
        existing = db_service.client.table("tenants").select("*").eq(
            "id", tenant_id
        ).single().execute()

        if not existing.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found"
            )

        # Delete associated data in order (respecting foreign keys)

        # First, get user IDs for this tenant (needed for FK cleanup)
        user_response = db_service.client.table("users").select("id").eq("tenant_id", tenant_id).execute()
        user_ids = [u["id"] for u in (user_response.data or [])]

        # Clear all FK references to users before deleting them
        # These tables have columns that reference users.id
        fk_cleanup = [
            ("workflow_snapshots", "created_by"),
            ("promotions", "created_by"),
            ("promotions", "approved_by"),
            ("promotions", "rejected_by"),
            ("deployments", "created_by"),
            ("deployments", "deleted_by_user_id"),
            ("deployments", "initiated_by"),
            ("pipelines", "created_by"),
            ("tenant_notes", "author_id"),
            ("tenant_feature_overrides", "created_by"),
            ("drift_incidents", "acknowledged_by"),
            ("drift_incidents", "resolved_by"),
            ("drift_approvals", "requested_by"),
            ("drift_approvals", "approved_by"),
        ]

        if user_ids:
            for table, column in fk_cleanup:
                for user_id in user_ids:
                    try:
                        db_service.client.table(table).update(
                            {column: None}
                        ).eq(column, user_id).execute()
                    except Exception:
                        pass  # Table/column might not exist

        # Delete tenant-owned data in dependency order

        # Delete workflow snapshots
        db_service.client.table("workflow_snapshots").delete().eq("tenant_id", tenant_id).execute()

        # Delete promotions
        db_service.client.table("promotions").delete().eq("tenant_id", tenant_id).execute()

        # Delete deployments
        db_service.client.table("deployments").delete().eq("tenant_id", tenant_id).execute()

        # Delete pipelines
        db_service.client.table("pipelines").delete().eq("tenant_id", tenant_id).execute()

        # Delete executions
        db_service.client.table("executions").delete().eq("tenant_id", tenant_id).execute()

        # Delete canonical workflows (cascades to workflow_env_map, workflow_diff_state, etc. via foreign keys)
        db_service.client.table("canonical_workflows").delete().eq("tenant_id", tenant_id).execute()

        # Delete credentials
        db_service.client.table("credentials").delete().eq("tenant_id", tenant_id).execute()

        # Delete tags
        db_service.client.table("tags").delete().eq("tenant_id", tenant_id).execute()

        # Delete n8n_users
        db_service.client.table("n8n_users").delete().eq("tenant_id", tenant_id).execute()

        # Delete environments
        db_service.client.table("environments").delete().eq("tenant_id", tenant_id).execute()

        # Delete drift-related data
        try:
            db_service.client.table("drift_incidents").delete().eq("tenant_id", tenant_id).execute()
        except Exception:
            pass
        try:
            db_service.client.table("drift_approvals").delete().eq("tenant_id", tenant_id).execute()
        except Exception:
            pass

        # Delete tenant notes
        try:
            db_service.client.table("tenant_notes").delete().eq("tenant_id", tenant_id).execute()
        except Exception:
            pass

        # Delete tenant feature overrides
        try:
            db_service.client.table("tenant_feature_overrides").delete().eq("tenant_id", tenant_id).execute()
        except Exception:
            pass

        # Delete users (team members) - now safe since all FK refs are cleared
        db_service.client.table("users").delete().eq("tenant_id", tenant_id).execute()

        # Finally delete the tenant
        db_service.client.table("tenants").delete().eq("id", tenant_id).execute()

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete tenant: {str(e)}"
        )


# =============================================================================
# Phase 3: Tenant Feature Overrides
# =============================================================================

@router.get("/{tenant_id}/overrides", response_model=TenantFeatureOverrideListResponse)
async def get_tenant_overrides(tenant_id: str, _: dict = Depends(require_platform_admin())):
    """Get all feature overrides for a tenant (admin only)"""
    try:
        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id").eq(
            "id", tenant_id
        ).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Get overrides with feature details
        response = db_service.client.table("tenant_feature_overrides").select(
            "*, feature:feature_id(id, name, display_name), created_by_user:created_by(email)"
        ).eq("tenant_id", tenant_id).order("created_at", desc=True).execute()

        overrides = []
        for row in response.data or []:
            feature = row.get("feature", {}) or {}
            created_by_user = row.get("created_by_user", {}) or {}
            overrides.append(TenantFeatureOverrideResponse(
                id=row["id"],
                tenant_id=row["tenant_id"],
                feature_id=row["feature_id"],
                feature_key=feature.get("name", ""),
                feature_display_name=feature.get("display_name", ""),
                value=row["value"],
                reason=row.get("reason"),
                created_by=row.get("created_by"),
                created_by_email=created_by_user.get("email"),
                expires_at=row.get("expires_at"),
                is_active=row.get("is_active", True),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            ))

        return TenantFeatureOverrideListResponse(
            overrides=overrides,
            total=len(overrides)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch overrides: {str(e)}"
        )


@router.post("/{tenant_id}/overrides", response_model=TenantFeatureOverrideResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_override(tenant_id: str, override: TenantFeatureOverrideCreate, user_info: dict = Depends(require_platform_admin())):
    """Create a feature override for a tenant (admin only)"""
    try:
        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id").eq(
            "id", tenant_id
        ).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Find feature by key
        feature_response = db_service.client.table("features").select(
            "id, name, display_name, type"
        ).eq("name", override.feature_key).single().execute()
        if not feature_response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Feature '{override.feature_key}' not found"
            )
        feature = feature_response.data

        # Check if override already exists for this tenant+feature
        existing = db_service.client.table("tenant_feature_overrides").select("id").eq(
            "tenant_id", tenant_id
        ).eq("feature_id", feature["id"]).execute()
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Override for feature '{override.feature_key}' already exists. Use PATCH to update."
            )

        # Create override
        override_data = {
            "tenant_id": tenant_id,
            "feature_id": feature["id"],
            "value": override.value,
            "reason": override.reason,
            "expires_at": override.expires_at.isoformat() if override.expires_at else None,
            "is_active": True,
        }

        response = db_service.client.table("tenant_feature_overrides").insert(override_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create override"
            )

        created = response.data[0]

        # Clear entitlements cache for this tenant
        entitlements_service.clear_cache(tenant_id)

        return TenantFeatureOverrideResponse(
            id=created["id"],
            tenant_id=created["tenant_id"],
            feature_id=created["feature_id"],
            feature_key=feature["name"],
            feature_display_name=feature["display_name"],
            value=created["value"],
            reason=created.get("reason"),
            created_by=created.get("created_by"),
            created_by_email=None,
            expires_at=created.get("expires_at"),
            is_active=created.get("is_active", True),
            created_at=created["created_at"],
            updated_at=created["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create override: {str(e)}"
        )


@router.patch("/{tenant_id}/overrides/{override_id}", response_model=TenantFeatureOverrideResponse)
async def update_tenant_override(
    tenant_id: str,
    override_id: str,
    override: TenantFeatureOverrideUpdate,
    user_info: dict = Depends(require_platform_admin()),
):
    """Update a feature override for a tenant (admin only)"""
    try:
        # Get existing override
        existing = db_service.client.table("tenant_feature_overrides").select(
            "*, feature:feature_id(id, name, display_name)"
        ).eq("id", override_id).eq("tenant_id", tenant_id).single().execute()

        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")

        # Build update data
        update_data = {}
        if override.value is not None:
            update_data["value"] = override.value
        if override.reason is not None:
            update_data["reason"] = override.reason
        if override.expires_at is not None:
            update_data["expires_at"] = override.expires_at.isoformat()
        if override.is_active is not None:
            update_data["is_active"] = override.is_active

        if not update_data:
            # No changes
            feature = existing.data.get("feature", {}) or {}
            return TenantFeatureOverrideResponse(
                id=existing.data["id"],
                tenant_id=existing.data["tenant_id"],
                feature_id=existing.data["feature_id"],
                feature_key=feature.get("name", ""),
                feature_display_name=feature.get("display_name", ""),
                value=existing.data["value"],
                reason=existing.data.get("reason"),
                created_by=existing.data.get("created_by"),
                created_by_email=None,
                expires_at=existing.data.get("expires_at"),
                is_active=existing.data.get("is_active", True),
                created_at=existing.data["created_at"],
                updated_at=existing.data["updated_at"],
            )

        response = db_service.client.table("tenant_feature_overrides").update(
            update_data
        ).eq("id", override_id).execute()

        if not response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")

        # Clear entitlements cache for this tenant
        entitlements_service.clear_cache(tenant_id)

        # Fetch updated record with feature details
        updated = db_service.client.table("tenant_feature_overrides").select(
            "*, feature:feature_id(id, name, display_name)"
        ).eq("id", override_id).single().execute()

        feature = updated.data.get("feature", {}) or {}
        return TenantFeatureOverrideResponse(
            id=updated.data["id"],
            tenant_id=updated.data["tenant_id"],
            feature_id=updated.data["feature_id"],
            feature_key=feature.get("name", ""),
            feature_display_name=feature.get("display_name", ""),
            value=updated.data["value"],
            reason=updated.data.get("reason"),
            created_by=updated.data.get("created_by"),
            created_by_email=None,
            expires_at=updated.data.get("expires_at"),
            is_active=updated.data.get("is_active", True),
            created_at=updated.data["created_at"],
            updated_at=updated.data["updated_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update override: {str(e)}"
        )


@router.delete("/{tenant_id}/overrides/{override_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_override(tenant_id: str, override_id: str, user_info: dict = Depends(require_platform_admin())):
    """Delete a feature override for a tenant (admin only)"""
    try:
        # Check if override exists
        existing = db_service.client.table("tenant_feature_overrides").select("id").eq(
            "id", override_id
        ).eq("tenant_id", tenant_id).execute()

        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")

        # Delete override
        db_service.client.table("tenant_feature_overrides").delete().eq(
            "id", override_id
        ).execute()

        # Clear entitlements cache for this tenant
        entitlements_service.clear_cache(tenant_id)

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete override: {str(e)}"
        )


# =============================================================================
# Phase 3: Audit Logs
# =============================================================================

@router.get("/{tenant_id}/audit-logs", response_model=FeatureConfigAuditListResponse)
async def get_tenant_config_audit_logs(
    tenant_id: str,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    feature_key: Optional[str] = Query(None, description="Filter by feature key"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: dict = Depends(require_platform_admin()),
):
    """Get configuration audit logs for a tenant (admin only)"""
    try:
        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id").eq(
            "id", tenant_id
        ).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Convert entity_type string to enum if provided
        entity_type_enum = None
        if entity_type:
            try:
                entity_type_enum = AuditEntityType(entity_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid entity_type. Must be one of: {[e.value for e in AuditEntityType]}"
                )

        logs, total = await audit_service.get_config_audit_logs(
            tenant_id=tenant_id,
            entity_type=entity_type_enum,
            feature_key=feature_key,
            page=page,
            page_size=page_size,
        )

        return FeatureConfigAuditListResponse(
            audits=logs,
            total=total,
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch audit logs: {str(e)}"
        )


@router.get("/{tenant_id}/access-logs", response_model=FeatureAccessLogListResponse)
async def get_tenant_access_logs(
    tenant_id: str,
    feature_key: Optional[str] = Query(None, description="Filter by feature key"),
    result: Optional[str] = Query(None, description="Filter by result (allowed, denied, limit_exceeded)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: dict = Depends(require_platform_admin()),
):
    """Get feature access logs for a tenant (admin only)"""
    try:
        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id").eq(
            "id", tenant_id
        ).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Convert result string to enum if provided
        result_enum = None
        if result:
            try:
                result_enum = AccessResult(result)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid result. Must be one of: {[e.value for e in AccessResult]}"
                )

        logs, total = await audit_service.get_access_logs(
            tenant_id=tenant_id,
            feature_key=feature_key,
            result=result_enum,
            page=page,
            page_size=page_size,
        )

        return FeatureAccessLogListResponse(
            logs=logs,
            total=total,
            page=page,
            page_size=page_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch access logs: {str(e)}"
        )


# =============================================================================
# Phase 1: Tenant Actions
# =============================================================================

@router.post("/{tenant_id}/suspend", response_model=TenantResponse)
async def suspend_tenant(tenant_id: str, reason: Optional[str] = None, user_info: dict = Depends(require_platform_admin())):
    """Suspend a tenant (soft lock access, preserve data)"""
    try:
        # Get current tenant
        existing = db_service.client.table("tenants").select("*").eq(
            "id", tenant_id
        ).single().execute()

        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        tenant = existing.data
        old_status = tenant.get("status", "active")

        if old_status == "suspended":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant is already suspended")

        # Update status
        db_service.client.table("tenants").update({
            "status": "suspended"
        }).eq("id", tenant_id).execute()

        # Create audit log
        try:
            from app.api.endpoints.admin_audit import create_audit_log
            await create_audit_log(
                action_type="TENANT_SUSPENDED",
                action=f"Suspended tenant",
                tenant_id=tenant_id,
                tenant_name=tenant.get("name"),
                resource_type="tenant",
                resource_id=tenant_id,
                old_value={"status": old_status},
                new_value={"status": "suspended"},
                reason=reason,
            )
        except Exception:
            pass  # Don't fail if audit logging fails

        return await get_tenant(tenant_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to suspend tenant: {str(e)}"
        )


@router.post("/{tenant_id}/reactivate", response_model=TenantResponse)
async def reactivate_tenant(tenant_id: str, reason: Optional[str] = None, user_info: dict = Depends(require_platform_admin())):
    """Reactivate a suspended tenant"""
    try:
        # Get current tenant
        existing = db_service.client.table("tenants").select("*").eq(
            "id", tenant_id
        ).single().execute()

        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        tenant = existing.data
        old_status = tenant.get("status", "active")

        if old_status != "suspended":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant is not suspended")

        # Update status
        db_service.client.table("tenants").update({
            "status": "active"
        }).eq("id", tenant_id).execute()

        # Create audit log
        try:
            from app.api.endpoints.admin_audit import create_audit_log
            await create_audit_log(
                action_type="TENANT_REACTIVATED",
                action=f"Reactivated tenant",
                tenant_id=tenant_id,
                tenant_name=tenant.get("name"),
                resource_type="tenant",
                resource_id=tenant_id,
                old_value={"status": old_status},
                new_value={"status": "active"},
                reason=reason,
            )
        except Exception:
            pass

        return await get_tenant(tenant_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reactivate tenant: {str(e)}"
        )


@router.post("/{tenant_id}/schedule-deletion")
async def schedule_tenant_deletion(
    tenant_id: str,
    request: ScheduleDeletionRequest,
    reason: Optional[str] = None,
    user_info: dict = Depends(require_platform_admin()),
):
    """Schedule tenant for deletion after retention period"""
    try:
        # Get current tenant
        existing = db_service.client.table("tenants").select("*").eq(
            "id", tenant_id
        ).single().execute()

        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        tenant = existing.data

        # Calculate deletion date
        deletion_date = datetime.utcnow() + timedelta(days=request.retention_days)

        # Update tenant
        db_service.client.table("tenants").update({
            "status": "archived",
            "scheduled_deletion_at": deletion_date.isoformat()
        }).eq("id", tenant_id).execute()

        # Create audit log
        try:
            from app.api.endpoints.admin_audit import create_audit_log
            await create_audit_log(
                action_type="TENANT_DELETION_SCHEDULED",
                action=f"Scheduled deletion in {request.retention_days} days",
                tenant_id=tenant_id,
                tenant_name=tenant.get("name"),
                resource_type="tenant",
                resource_id=tenant_id,
                new_value={
                    "status": "archived",
                    "scheduled_deletion_at": deletion_date.isoformat(),
                    "retention_days": request.retention_days
                },
                reason=reason,
            )
        except Exception:
            pass

        return {
            "success": True,
            "scheduled_deletion_at": deletion_date.isoformat(),
            "retention_days": request.retention_days
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule deletion: {str(e)}"
        )


@router.delete("/{tenant_id}/cancel-deletion")
async def cancel_tenant_deletion(tenant_id: str, user_info: dict = Depends(require_platform_admin())):
    """Cancel scheduled tenant deletion"""
    try:
        # Get current tenant
        existing = db_service.client.table("tenants").select("*").eq(
            "id", tenant_id
        ).single().execute()

        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        tenant = existing.data

        if not tenant.get("scheduled_deletion_at"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No deletion scheduled")

        # Update tenant
        db_service.client.table("tenants").update({
            "status": "active",
            "scheduled_deletion_at": None
        }).eq("id", tenant_id).execute()

        return {"success": True, "message": "Deletion cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel deletion: {str(e)}"
        )


# =============================================================================
# Tenant Notes
# =============================================================================

@router.get("/{tenant_id}/notes", response_model=TenantNoteListResponse)
async def get_tenant_notes(tenant_id: str, _: dict = Depends(require_platform_admin())):
    """Get all notes for a tenant (admin only)"""
    try:
        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id").eq(
            "id", tenant_id
        ).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Get notes
        response = db_service.client.table("tenant_notes").select("*").eq(
            "tenant_id", tenant_id
        ).order("created_at", desc=True).execute()

        notes = [TenantNoteResponse(**note) for note in (response.data or [])]

        return TenantNoteListResponse(
            notes=notes,
            total=len(notes)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant notes: {str(e)}"
        )


@router.post("/{tenant_id}/notes", response_model=TenantNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_note(tenant_id: str, note: TenantNoteCreate, user_info: dict = Depends(require_platform_admin())):
    """Create a note for a tenant (admin only)"""
    try:
        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id").eq(
            "id", tenant_id
        ).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Create note
        note_data = {
            "tenant_id": tenant_id,
            "content": note.content,
            # In production, get these from auth context
            # "author_id": current_user.id,
            # "author_email": current_user.email,
            # "author_name": current_user.name,
        }

        response = db_service.client.table("tenant_notes").insert(note_data).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create note"
            )

        return TenantNoteResponse(**response.data[0])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create note: {str(e)}"
        )


@router.delete("/{tenant_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_note(tenant_id: str, note_id: str, user_info: dict = Depends(require_platform_admin())):
    """Delete a tenant note (admin only)"""
    try:
        # Verify note exists and belongs to tenant
        existing = db_service.client.table("tenant_notes").select("id").eq(
            "id", note_id
        ).eq("tenant_id", tenant_id).single().execute()

        if not existing.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

        # Delete note
        db_service.client.table("tenant_notes").delete().eq("id", note_id).execute()

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete note: {str(e)}"
        )


# =============================================================================
# Tenant Usage
# =============================================================================

@router.get("/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: str,
    provider: Optional[str] = Query(None, description="Filter by provider: n8n, make, or all"),
    _: dict = Depends(require_platform_admin()),
):
    """Get usage metrics for a tenant (admin only)"""
    try:
        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select(
            "id, name, subscription_tier"
        ).eq("id", tenant_id).single().execute()

        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        tenant = tenant_response.data
        plan = tenant.get("subscription_tier", "free")
        provider_filter = provider or "all"  # Default to "all" for aggregate

        # Get plan limits from entitlements
        try:
            limits = await entitlements_service.get_tenant_entitlements(tenant_id)
            features = limits.get("features", {})
        except Exception:
            features = {}

        # Define default limits by plan
        default_limits = {
            "free": {"workflows": 10, "environments": 1, "users": 3, "executions": 1000},
            "pro": {"workflows": 200, "environments": 3, "users": 25, "executions": 50000},
            "agency": {"workflows": 500, "environments": -1, "users": 100, "executions": 200000},
            "enterprise": {"workflows": -1, "environments": -1, "users": -1, "executions": -1},
        }

        plan_limits = default_limits.get(plan, default_limits["free"])

        def calculate_percentage(current, limit):
            if limit == -1:
                return 0  # Unlimited
            if limit == 0:
                return 100 if current > 0 else 0
            return min(round((current / limit) * 100, 1), 100)

        # Helper to apply provider filter
        def apply_provider_filter_local(query, table_has_provider: bool = True):
            if not table_has_provider or not provider_filter or provider_filter == "all":
                return query
            return query.eq("provider", provider_filter)

        # Get counts from canonical system (count unique canonical workflows)
        # Note: Provider filtering not directly supported in canonical system
        workflow_mappings = await db_service.client.table("workflow_env_map").select("canonical_id").eq("tenant_id", tenant_id).execute()
        unique_canonical_ids = set()
        for mapping in (workflow_mappings.data or []):
            cid = mapping.get("canonical_id")
            if cid:
                unique_canonical_ids.add(cid)
        workflow_count = len(unique_canonical_ids)

        env_query = db_service.client.table("environments").select("id, provider", count="exact")
        env_query = env_query.eq("tenant_id", tenant_id)
        env_query = apply_provider_filter_local(env_query)
        env_response = await env_query.execute()
        environment_count = env_response.count or 0

        # Users are platform-scoped (no provider filter)
        user_response = db_service.client.table("users").select(
            "id", count="exact"
        ).eq("tenant_id", tenant_id).execute()
        user_count = user_response.count or 0

        # Get execution count for current month
        first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        exec_query = db_service.client.table("executions").select("id, provider", count="exact")
        exec_query = exec_query.eq("tenant_id", tenant_id).gte("started_at", first_of_month.isoformat())
        exec_query = apply_provider_filter_local(exec_query)
        exec_response = await exec_query.execute()
        execution_count = exec_response.count or 0

        # Build response
        response = {
            "tenant_id": tenant_id,
            "plan": plan,
            "provider": provider_filter,
            "metrics": {
                "workflows": {
                    "current": workflow_count,
                    "limit": plan_limits.get("workflows", -1),
                    "percentage": calculate_percentage(workflow_count, plan_limits.get("workflows", -1)),
                },
                "environments": {
                    "current": environment_count,
                    "limit": plan_limits.get("environments", -1),
                    "percentage": calculate_percentage(environment_count, plan_limits.get("environments", -1)),
                },
                "users": {
                    "current": user_count,
                    "limit": plan_limits.get("users", -1),
                    "percentage": calculate_percentage(user_count, plan_limits.get("users", -1)),
                },
                "executions": {
                    "current": execution_count,
                    "limit": plan_limits.get("executions", -1),
                    "percentage": calculate_percentage(execution_count, plan_limits.get("executions", -1)),
                    "period": "current_month",
                },
            },
        }

        # If provider="all", include breakdown by provider
        if provider_filter == "all":
            # Get provider breakdown for workflows
            workflow_by_provider = {}
            workflow_data = workflow_response.data or []
            for wf in workflow_data:
                prov = wf.get("provider", "n8n")
                workflow_by_provider[prov] = workflow_by_provider.get(prov, 0) + 1

            # Get provider breakdown for environments
            env_by_provider = {}
            env_data = env_response.data or []
            for env in env_data:
                prov = env.get("provider", "n8n")
                env_by_provider[prov] = env_by_provider.get(prov, 0) + 1

            # Get provider breakdown for executions
            exec_by_provider = {}
            exec_data = exec_response.data or []
            for exec_item in exec_data:
                prov = exec_item.get("provider", "n8n")
                exec_by_provider[prov] = exec_by_provider.get(prov, 0) + 1

            # Build byProvider breakdown
            by_provider = {}
            all_providers = set(list(workflow_by_provider.keys()) + list(env_by_provider.keys()) + list(exec_by_provider.keys()))
            for prov in all_providers:
                by_provider[prov] = {
                    "workflows": {
                        "current": workflow_by_provider.get(prov, 0),
                        "limit": plan_limits.get("workflows", -1),
                        "percentage": calculate_percentage(workflow_by_provider.get(prov, 0), plan_limits.get("workflows", -1)),
                    },
                    "environments": {
                        "current": env_by_provider.get(prov, 0),
                        "limit": plan_limits.get("environments", -1),
                        "percentage": calculate_percentage(env_by_provider.get(prov, 0), plan_limits.get("environments", -1)),
                    },
                    "users": {
                        "current": user_count,  # Users are platform-scoped, same for all providers
                        "limit": plan_limits.get("users", -1),
                        "percentage": calculate_percentage(user_count, plan_limits.get("users", -1)),
                    },
                    "executions": {
                        "current": exec_by_provider.get(prov, 0),
                        "limit": plan_limits.get("executions", -1),
                        "percentage": calculate_percentage(exec_by_provider.get(prov, 0), plan_limits.get("executions", -1)),
                        "period": "current_month",
                    },
                }
            response["byProvider"] = by_provider

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant usage: {str(e)}"
        )


# =============================================================================
# Platform Tenant Users & Roles Management
# =============================================================================

@router.get("/{tenant_id}/users")
async def get_tenant_users(
    tenant_id: str,
    search: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[str] = Query(None, description="Filter by role"),
    status: Optional[str] = Query(None, description="Filter by status"),
    sort_by: Optional[str] = Query("joined", description="Sort by: name, role, status, joined, last_activity"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: dict = Depends(require_platform_admin()),
):
    """Get all users for a tenant (platform admin only)"""
    try:
        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id, name, subscription_tier, status").eq(
            "id", tenant_id
        ).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Build query - select columns (users table doesn't have last_login_at)
        query = db_service.client.table("users").select(
            "id, email, name, role, status, tenant_id, created_at"
        ).eq("tenant_id", tenant_id)

        # Apply filters
        if search:
            query = query.or_(f"name.ilike.%{search}%,email.ilike.%{search}%")
        if role:
            query = query.eq("role", role)
        if status:
            query = query.eq("status", status)

        # Apply sorting
        # Map frontend sort keys to database columns
        sort_column_map = {
            "name": "name",
            "role": "role",
            "status": "status",
            "joined": "created_at",
            "last_activity": "created_at",  # Use created_at as fallback (last_login_at may not exist)
        }
        sort_column = sort_column_map.get(sort_by, "created_at")
        is_desc = sort_order.lower() == "desc"
        
        # Apply pagination
        offset = (page - 1) * page_size
        # Supabase order method: desc=True for descending, omit desc for ascending
        try:
            if is_desc:
                query = query.order(sort_column, desc=True).range(offset, offset + page_size - 1)
            else:
                query = query.order(sort_column).range(offset, offset + page_size - 1)
            response = query.execute()
            users = response.data or []
        except Exception as query_error:
            import logging
            import traceback
            from fastapi import status as http_status
            logger = logging.getLogger(__name__)
            error_trace = traceback.format_exc()
            logger.error(f"Query execution failed: {error_trace}")
            # Return more detailed error in response for debugging
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Query execution failed: {str(query_error)}. Sort column: {sort_column}, Desc: {is_desc}"
            )

        # Check which users are platform admins
        user_ids = [u.get("id") for u in users if u.get("id")]
        platform_admin_ids = set()
        if user_ids:
            try:
                pa_resp = db_service.client.table("platform_admins").select("user_id").in_("user_id", user_ids).execute()
                platform_admin_ids = {row.get("user_id") for row in (pa_resp.data or []) if row.get("user_id")}
            except Exception as pa_error:
                # If platform_admins query fails, log but continue (users might not be platform admins)
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to check platform admin status: {pa_error}")
                platform_admin_ids = set()

        # Format response
        formatted_users = []
        for u in users:
            formatted_users.append({
                "user_id": u.get("id"),
                "name": u.get("name"),
                "email": u.get("email"),
                "role_in_tenant": u.get("role", "viewer"),
                "status_in_tenant": u.get("status", "active"),
                "joined_at": u.get("created_at"),
                "last_activity_at": None,  # users table doesn't have last_login_at column
                "is_platform_admin": u.get("id") in platform_admin_ids,
            })

        # Get total count
        count_query = db_service.client.table("users").select("id", count="exact").eq("tenant_id", tenant_id)
        if search:
            count_query = count_query.or_(f"name.ilike.%{search}%,email.ilike.%{search}%")
        if role:
            count_query = count_query.eq("role", role)
        if status:
            count_query = count_query.eq("status", status)
        count_response = count_query.execute()
        total = count_response.count or 0

        return {
            "users": formatted_users,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    except HTTPException:
        raise
    except Exception as e:
        import logging
        import traceback
        from fastapi import status as http_status
        logger = logging.getLogger(__name__)
        error_details = traceback.format_exc()
        logger.error(f"Failed to fetch tenant users: {error_details}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant users: {str(e)}"
        )


@router.post("/{tenant_id}/users/{user_id}/impersonate")
async def impersonate_tenant_user(
    tenant_id: str,
    user_id: str,
    user_info: dict = Depends(require_platform_admin(allow_when_impersonating=True)),
):
    """Impersonate a user in a tenant (platform admin only)"""
    try:
        # When impersonating, use the original platform admin (actor_user_id from require_platform_admin)
        # Otherwise use the current user
        actor_id = user_info.get("actor_user_id")
        if not actor_id:
            actor = (user_info or {}).get("user") or {}
            actor_id = actor.get("id")
        if not actor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        # Get actor details for audit logging
        actor = (user_info or {}).get("actor_user") or (user_info or {}).get("user") or {}

        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id, name").eq("id", tenant_id).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Verify user exists and belongs to tenant
        user_response = db_service.client.table("users").select("id, email, name, role, tenant_id").eq("id", user_id).eq("tenant_id", tenant_id).maybe_single().execute()
        if not user_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this tenant")

        target = user_response.data

        # Guardrail: never impersonate another platform admin
        from app.core.platform_admin import is_platform_admin
        if is_platform_admin(user_id):
            from app.api.endpoints.admin_audit import create_audit_log
            await create_audit_log(
                action_type="IMPERSONATION_BLOCKED",
                action=f"Blocked impersonation attempt for platform admin user_id={user_id}",
                actor_id=actor_id,
                actor_email=actor.get("email"),
                actor_name=actor.get("name"),
                tenant_id=tenant_id,
                resource_type="impersonation",
                resource_id=user_id,
                metadata={"target_user_id": user_id, "reason": "target_is_platform_admin"},
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot impersonate another Platform Admin")

        # End any existing active session for this actor
        from datetime import datetime
        import uuid
        db_service.client.table("platform_impersonation_sessions").update(
            {"ended_at": datetime.utcnow().isoformat()}
        ).eq("actor_user_id", actor_id).is_("ended_at", "null").execute()

        # Create new impersonation session
        session_id = str(uuid.uuid4())
        db_service.client.table("platform_impersonation_sessions").insert(
            {
                "id": session_id,
                "actor_user_id": actor_id,
                "impersonated_user_id": user_id,
                "impersonated_tenant_id": tenant_id,
            }
        ).execute()

        # Audit log
        from app.api.endpoints.admin_audit import create_audit_log
        await create_audit_log(
            action_type="impersonation.start",
            action=f"Started impersonation for user_id={user_id} in tenant_id={tenant_id}",
            actor_id=actor_id,
            actor_email=actor.get("email"),
            actor_name=actor.get("name"),
            tenant_id=tenant_id,
            resource_type="impersonation",
            resource_id=session_id,
            metadata={"target_user_id": user_id, "tenant_id": tenant_id},
        )

        return {
            "success": True,
            "impersonating": True,
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to impersonate user: {str(e)}"
        )


@router.post("/{tenant_id}/users/{user_id}/suspend")
async def suspend_tenant_user(
    tenant_id: str,
    user_id: str,
    user_info: dict = Depends(require_platform_admin()),
):
    """Suspend a user in a tenant (platform admin only)"""
    try:
        actor = (user_info or {}).get("user") or {}
        actor_id = actor.get("id")
        if not actor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id, name").eq("id", tenant_id).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Get current user state
        user_response = db_service.client.table("users").select("id, email, name, role, status, tenant_id").eq("id", user_id).eq("tenant_id", tenant_id).maybe_single().execute()
        if not user_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this tenant")

        user = user_response.data
        old_status = user.get("status", "active")

        if old_status == "inactive":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already suspended")

        # Update status
        db_service.client.table("users").update({"status": "inactive"}).eq("id", user_id).execute()

        # Audit log
        from app.api.endpoints.admin_audit import create_audit_log
        await create_audit_log(
            action_type="user.suspend",
            action=f"Suspended user {user.get('email')} in tenant",
            actor_id=actor_id,
            actor_email=actor.get("email"),
            actor_name=actor.get("name"),
            tenant_id=tenant_id,
            resource_type="user",
            resource_id=user_id,
            resource_name=user.get("email"),
            old_value={"status": old_status},
            new_value={"status": "inactive"},
        )

        return {"success": True, "message": "User suspended"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to suspend user: {str(e)}"
        )


@router.post("/{tenant_id}/users/{user_id}/unsuspend")
async def unsuspend_tenant_user(
    tenant_id: str,
    user_id: str,
    user_info: dict = Depends(require_platform_admin()),
):
    """Unsuspend a user in a tenant (platform admin only)"""
    try:
        actor = (user_info or {}).get("user") or {}
        actor_id = actor.get("id")
        if not actor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id, name").eq("id", tenant_id).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Get current user state
        user_response = db_service.client.table("users").select("id, email, name, role, status, tenant_id").eq("id", user_id).eq("tenant_id", tenant_id).maybe_single().execute()
        if not user_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this tenant")

        user = user_response.data
        old_status = user.get("status", "active")

        if old_status != "inactive":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is not suspended")

        # Update status
        db_service.client.table("users").update({"status": "active"}).eq("id", user_id).execute()

        # Audit log
        from app.api.endpoints.admin_audit import create_audit_log
        await create_audit_log(
            action_type="user.unsuspend",
            action=f"Unsuspended user {user.get('email')} in tenant",
            actor_id=actor_id,
            actor_email=actor.get("email"),
            actor_name=actor.get("name"),
            tenant_id=tenant_id,
            resource_type="user",
            resource_id=user_id,
            resource_name=user.get("email"),
            old_value={"status": old_status},
            new_value={"status": "active"},
        )

        return {"success": True, "message": "User unsuspended"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to unsuspend user: {str(e)}"
        )


class UserRoleUpdate(BaseModel):
    role: str


@router.patch("/{tenant_id}/users/{user_id}/role")
async def change_tenant_user_role(
    tenant_id: str,
    user_id: str,
    role_update: UserRoleUpdate,
    user_info: dict = Depends(require_platform_admin()),
):
    """Change a user's role in a tenant (platform admin only)"""
    try:
        actor = (user_info or {}).get("user") or {}
        actor_id = actor.get("id")
        if not actor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        new_role = role_update.role
        if new_role not in ["admin", "developer", "viewer"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role. Must be admin, developer, or viewer")

        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id, name").eq("id", tenant_id).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Get current user state
        user_response = db_service.client.table("users").select("id, email, name, role, tenant_id").eq("id", user_id).eq("tenant_id", tenant_id).maybe_single().execute()
        if not user_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this tenant")

        user = user_response.data
        old_role = user.get("role", "viewer")

        if old_role == new_role:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has this role")

        # Update role
        db_service.client.table("users").update({"role": new_role}).eq("id", user_id).execute()

        # Audit log
        from app.api.endpoints.admin_audit import create_audit_log
        await create_audit_log(
            action_type="user.role_change",
            action=f"Changed role for user {user.get('email')} from {old_role} to {new_role}",
            actor_id=actor_id,
            actor_email=actor.get("email"),
            actor_name=actor.get("name"),
            tenant_id=tenant_id,
            resource_type="user",
            resource_id=user_id,
            resource_name=user.get("email"),
            old_value={"role": old_role},
            new_value={"role": new_role},
        )

        return {"success": True, "message": f"User role changed to {new_role}"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change user role: {str(e)}"
        )


@router.delete("/{tenant_id}/users/{user_id}")
async def remove_tenant_user(
    tenant_id: str,
    user_id: str,
    user_info: dict = Depends(require_platform_admin()),
):
    """Remove a user from a tenant (platform admin only)"""
    try:
        actor = (user_info or {}).get("user") or {}
        actor_id = actor.get("id")
        if not actor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id, name").eq("id", tenant_id).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Get current user state
        user_response = db_service.client.table("users").select("id, email, name, role, tenant_id").eq("id", user_id).eq("tenant_id", tenant_id).maybe_single().execute()
        if not user_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this tenant")

        user = user_response.data

        # Delete user
        db_service.client.table("users").delete().eq("id", user_id).execute()

        # Audit log
        from app.api.endpoints.admin_audit import create_audit_log
        await create_audit_log(
            action_type="user.remove",
            action=f"Removed user {user.get('email')} from tenant",
            actor_id=actor_id,
            actor_email=actor.get("email"),
            actor_name=actor.get("name"),
            tenant_id=tenant_id,
            resource_type="user",
            resource_id=user_id,
            resource_name=user.get("email"),
            old_value={"tenant_id": tenant_id, "role": user.get("role")},
            new_value=None,
        )

        return {"success": True, "message": "User removed from tenant"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove user: {str(e)}"
        )


# =============================================================================
# Tenant Provider Subscriptions (Admin)
# =============================================================================

class TenantProviderSubscriptionCreateRequest(BaseModel):
    provider_id: str
    plan_id: str
    billing_cycle: str = "monthly"


@router.post("/{tenant_id}/provider-subscriptions", response_model=TenantProviderSubscriptionSimple)
async def create_tenant_provider_subscription(
    tenant_id: str,
    request: TenantProviderSubscriptionCreateRequest,
    user_info: dict = Depends(require_platform_admin()),
):
    """Create a provider subscription for a tenant (platform admin only)."""
    try:
        actor = (user_info or {}).get("user") or {}
        actor_id = actor.get("id")
        if not actor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id, name").eq("id", tenant_id).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        tenant = tenant_response.data
        provider_id = request.provider_id
        plan_id = request.plan_id
        billing_cycle = request.billing_cycle

        # Verify provider exists
        provider = await db_service.get_provider(provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        # Verify plan exists and belongs to provider
        plan = await db_service.get_provider_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
        if plan.get("provider_id") != provider_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan does not belong to this provider")

        # Check if tenant already has a subscription for this provider
        existing_sub = await db_service.get_tenant_provider_subscription(tenant_id, provider_id)
        if existing_sub:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant already has a subscription for this provider"
            )

        # Create subscription
        subscription_data = {
            "tenant_id": tenant_id,
            "provider_id": provider_id,
            "plan_id": plan_id,
            "status": "active",
            "billing_cycle": billing_cycle,
        }

        subscription = await db_service.create_tenant_provider_subscription(subscription_data)

        # Audit log
        from app.api.endpoints.admin_audit import create_audit_log
        await create_audit_log(
            action_type="tenant.subscription.created",
            action=f"Created {provider.get('display_name')} subscription with {plan.get('display_name')} plan for tenant",
            actor_id=actor_id,
            actor_email=actor.get("email"),
            actor_name=actor.get("name"),
            tenant_id=tenant_id,
            tenant_name=tenant.get("name"),
            resource_type="subscription",
            resource_id=subscription.get("id"),
            new_value={"provider_id": provider_id, "plan_id": plan_id, "billing_cycle": billing_cycle},
        )

        return subscription

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create subscription: {str(e)}"
        )


@router.patch("/{tenant_id}/provider-subscriptions/{provider_id}", response_model=TenantProviderSubscriptionSimple)
async def update_tenant_provider_subscription(
    tenant_id: str,
    provider_id: str,
    update: ProviderSubscriptionUpdate,
    user_info: dict = Depends(require_platform_admin()),
):
    """Update a tenant's provider subscription (platform admin only)."""
    try:
        actor = (user_info or {}).get("user") or {}
        actor_id = actor.get("id")
        if not actor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id, name").eq("id", tenant_id).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        tenant = tenant_response.data

        # Get existing subscription
        subscription = await db_service.get_tenant_provider_subscription(tenant_id, provider_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found for this provider"
            )

        update_data = {}
        old_values = {}

        # Handle cancellation
        if update.cancel_at_period_end is not None:
            old_values["cancel_at_period_end"] = subscription.get("cancel_at_period_end", False)
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
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
            if new_plan["provider_id"] != provider_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Plan does not belong to this provider"
                )
            old_values["plan_id"] = subscription.get("plan_id")
            update_data["plan_id"] = update.plan_id

        if update_data:
            result = await db_service.update_tenant_provider_subscription_by_provider(
                tenant_id, provider_id, update_data
            )

            # Audit log
            from app.api.endpoints.admin_audit import create_audit_log
            await create_audit_log(
                action_type="tenant.subscription.updated",
                action=f"Updated provider subscription for tenant",
                actor_id=actor_id,
                actor_email=actor.get("email"),
                actor_name=actor.get("name"),
                tenant_id=tenant_id,
                tenant_name=tenant.get("name"),
                resource_type="subscription",
                resource_id=subscription.get("id"),
                old_value=old_values,
                new_value=update_data,
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


@router.delete("/{tenant_id}/provider-subscriptions/{provider_id}")
async def cancel_tenant_provider_subscription(
    tenant_id: str,
    provider_id: str,
    at_period_end: bool = True,
    user_info: dict = Depends(require_platform_admin()),
):
    """Cancel a tenant's provider subscription (platform admin only)."""
    try:
        actor = (user_info or {}).get("user") or {}
        actor_id = actor.get("id")
        if not actor_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

        # Verify tenant exists
        tenant_response = db_service.client.table("tenants").select("id, name").eq("id", tenant_id).single().execute()
        if not tenant_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        tenant = tenant_response.data

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
                at_period_end=at_period_end
            )

        # Update database
        update_data = {"cancel_at_period_end": True}
        if not at_period_end:
            # Find free plan for this provider
            plans = await db_service.get_provider_plans(provider_id, active_only=True)
            free_plan = next((p for p in plans if p.get("name") == "free" or p.get("price_monthly", 0) == 0), None)
            if free_plan:
                update_data["plan_id"] = free_plan["id"]
                update_data["status"] = "active"
            else:
                update_data["status"] = "canceled"

        await db_service.update_tenant_provider_subscription_by_provider(
            tenant_id, provider_id, update_data
        )

        # Audit log
        from app.api.endpoints.admin_audit import create_audit_log
        await create_audit_log(
            action_type="tenant.subscription.canceled",
            action=f"Canceled provider subscription for tenant (at_period_end={at_period_end})",
            actor_id=actor_id,
            actor_email=actor.get("email"),
            actor_name=actor.get("name"),
            tenant_id=tenant_id,
            tenant_name=tenant.get("name"),
            resource_type="subscription",
            resource_id=subscription.get("id"),
            old_value={"status": subscription.get("status"), "cancel_at_period_end": subscription.get("cancel_at_period_end", False)},
            new_value=update_data,
        )

        return {"success": True, "message": f"Subscription will be {'canceled at period end' if at_period_end else 'canceled immediately'}"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}"
        )