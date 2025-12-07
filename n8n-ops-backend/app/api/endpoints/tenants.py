from fastapi import APIRouter, HTTPException, status
from typing import List

from app.schemas.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantStats
)
from app.services.database import db_service

router = APIRouter()


@router.get("/", response_model=List[TenantResponse])
async def get_tenants():
    """Get all tenants (admin only)"""
    try:
        # Get all tenants
        response = db_service.client.table("tenants").select("*").order("created_at", desc=True).execute()
        tenants = response.data or []

        # Enrich with counts
        enriched_tenants = []
        for tenant in tenants:
            tenant_id = tenant["id"]

            # Get workflow count
            workflow_response = db_service.client.table("workflows").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).eq("is_deleted", False).execute()
            workflow_count = workflow_response.count or 0

            # Get environment count
            env_response = db_service.client.table("environments").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            environment_count = env_response.count or 0

            # Get user count
            user_response = db_service.client.table("users").select(
                "id", count="exact"
            ).eq("tenant_id", tenant_id).execute()
            user_count = user_response.count or 0

            enriched_tenants.append({
                **tenant,
                # Map subscription_tier to subscription_plan for API response
                "subscription_plan": tenant.get("subscription_tier") or tenant.get("subscription_plan", "free"),
                "workflow_count": workflow_count,
                "environment_count": environment_count,
                "user_count": user_count,
                "status": tenant.get("status", "active"),
            })

        return enriched_tenants

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenants: {str(e)}"
        )


@router.get("/stats", response_model=TenantStats)
async def get_tenant_stats():
    """Get tenant statistics"""
    try:
        # Get all tenants for stats (subscription_tier is the actual db column)
        # Note: status column may not exist in db, so we just get id and subscription_tier
        response = db_service.client.table("tenants").select("id, subscription_tier").execute()
        tenants = response.data or []

        total = len(tenants)
        # Since status column doesn't exist, all tenants are considered active
        active = total
        suspended = 0
        pending = 0

        # Use subscription_tier from db
        by_plan = {
            "free": sum(1 for t in tenants if t.get("subscription_tier") == "free"),
            "pro": sum(1 for t in tenants if t.get("subscription_tier") == "pro"),
            "enterprise": sum(1 for t in tenants if t.get("subscription_tier") == "enterprise"),
        }

        return {
            "total": total,
            "active": active,
            "suspended": suspended,
            "pending": pending,
            "by_plan": by_plan
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tenant stats: {str(e)}"
        )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str):
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

        # Get counts
        workflow_response = db_service.client.table("workflows").select(
            "id", count="exact"
        ).eq("tenant_id", tenant_id).eq("is_deleted", False).execute()

        env_response = db_service.client.table("environments").select(
            "id", count="exact"
        ).eq("tenant_id", tenant_id).execute()

        user_response = db_service.client.table("users").select(
            "id", count="exact"
        ).eq("tenant_id", tenant_id).execute()

        return {
            **tenant,
            # Map subscription_tier to subscription_plan for API response
            "subscription_plan": tenant.get("subscription_tier") or tenant.get("subscription_plan", "free"),
            "workflow_count": workflow_response.count or 0,
            "environment_count": env_response.count or 0,
            "user_count": user_response.count or 0,
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
async def create_tenant(tenant: TenantCreate):
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

        # Create tenant (use subscription_tier for db column)
        tenant_data = {
            "name": tenant.name,
            "email": tenant.email,
            "subscription_tier": tenant.subscription_plan.value,
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
            # Map subscription_tier to subscription_plan for API response
            "subscription_plan": created_tenant.get("subscription_tier", "free"),
            "workflow_count": 0,
            "environment_count": 0,
            "user_count": 0,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant: {str(e)}"
        )


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(tenant_id: str, tenant: TenantUpdate):
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

        # Build update data (use subscription_tier for db column)
        update_data = {}
        if tenant.name is not None:
            update_data["name"] = tenant.name
        if tenant.email is not None:
            update_data["email"] = tenant.email
        if tenant.subscription_plan is not None:
            update_data["subscription_tier"] = tenant.subscription_plan.value
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
async def delete_tenant(tenant_id: str):
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
        # Delete executions
        db_service.client.table("executions").delete().eq("tenant_id", tenant_id).execute()

        # Delete workflows
        db_service.client.table("workflows").delete().eq("tenant_id", tenant_id).execute()

        # Delete workflow snapshots
        db_service.client.table("workflow_snapshots").delete().eq("tenant_id", tenant_id).execute()

        # Delete credentials
        db_service.client.table("credentials").delete().eq("tenant_id", tenant_id).execute()

        # Delete tags
        db_service.client.table("tags").delete().eq("tenant_id", tenant_id).execute()

        # Delete n8n_users
        db_service.client.table("n8n_users").delete().eq("tenant_id", tenant_id).execute()

        # Delete environments
        db_service.client.table("environments").delete().eq("tenant_id", tenant_id).execute()

        # Delete users (team members)
        db_service.client.table("users").delete().eq("tenant_id", tenant_id).execute()

        # Delete deployments
        db_service.client.table("deployments").delete().eq("tenant_id", tenant_id).execute()

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
