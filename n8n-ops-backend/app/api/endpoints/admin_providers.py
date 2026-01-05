"""
Admin Provider Endpoints

Provides provider detection and provider-related admin operations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
from app.services.database import db_service
from app.services.auth_service import get_current_user
from app.core.platform_admin import require_platform_admin

router = APIRouter()


class ActiveProvider(BaseModel):
    """Provider with usage statistics."""
    provider: str
    environment_count: int
    workflow_count: int
    tenant_count: int


class ActiveProvidersResponse(BaseModel):
    """Response for active providers endpoint."""
    providers: List[ActiveProvider]
    total_providers: int
    is_multi_provider: bool  # True if more than one provider is active


@router.get("/active", response_model=ActiveProvidersResponse)
async def get_active_providers(
    user_info: dict = Depends(require_platform_admin())
):
    """
    Get list of active providers in the system.

    Returns providers that have at least one environment configured.
    Used by frontend to determine whether to show provider filters/columns.

    If is_multi_provider is False, frontend should hide provider UI elements.
    """
    try:
        # Get distinct providers from environments table
        envs_result = await db_service.client.table("environments").select(
            "provider, tenant_id"
        ).execute()
        environments = envs_result.data or []

        # Get workflow counts from canonical system (provider not directly available, use default)
        # Count unique canonical workflows per tenant
        mappings_result = await db_service.client.table("workflow_env_map").select("tenant_id, canonical_id").execute()
        tenant_workflow_counts = {}
        for mapping in (mappings_result.data or []):
            tid = mapping.get("tenant_id")
            if tid:
                if tid not in tenant_workflow_counts:
                    tenant_workflow_counts[tid] = set()
                tenant_workflow_counts[tid].add(mapping.get("canonical_id"))
        # Convert to list format with default provider for compatibility
        workflows = [{"tenant_id": tid, "provider": "n8n"} for tid, cids in tenant_workflow_counts.items() for _ in cids]

        # Aggregate by provider
        provider_stats = {}

        for env in environments:
            provider = env.get("provider", "n8n") or "n8n"
            tenant_id = env.get("tenant_id")

            if provider not in provider_stats:
                provider_stats[provider] = {
                    "environment_count": 0,
                    "workflow_count": 0,
                    "tenant_ids": set()
                }

            provider_stats[provider]["environment_count"] += 1
            if tenant_id:
                provider_stats[provider]["tenant_ids"].add(tenant_id)

        for wf in workflows:
            provider = wf.get("provider", "n8n") or "n8n"
            tenant_id = wf.get("tenant_id")

            if provider not in provider_stats:
                provider_stats[provider] = {
                    "environment_count": 0,
                    "workflow_count": 0,
                    "tenant_ids": set()
                }

            provider_stats[provider]["workflow_count"] += 1
            if tenant_id:
                provider_stats[provider]["tenant_ids"].add(tenant_id)

        # Build response
        providers = []
        for provider, stats in provider_stats.items():
            providers.append(ActiveProvider(
                provider=provider,
                environment_count=stats["environment_count"],
                workflow_count=stats["workflow_count"],
                tenant_count=len(stats["tenant_ids"])
            ))

        # Sort by environment count descending
        providers.sort(key=lambda p: p.environment_count, reverse=True)

        return ActiveProvidersResponse(
            providers=providers,
            total_providers=len(providers),
            is_multi_provider=len(providers) > 1
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active providers: {str(e)}"
        )


@router.get("/")
async def list_supported_providers(
    user_info: dict = Depends(require_platform_admin())
):
    """
    Get list of all supported providers (not just active ones).

    This is a static list of providers the platform supports.
    """
    return {
        "providers": [
            {
                "id": "n8n",
                "name": "n8n",
                "description": "Open-source workflow automation platform",
                "status": "supported"
            },
            {
                "id": "make",
                "name": "Make.com",
                "description": "Visual automation platform (formerly Integromat)",
                "status": "planned"
            }
        ]
    }
