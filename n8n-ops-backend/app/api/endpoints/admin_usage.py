"""
Admin Usage Endpoints

Provides global usage overview, top tenants by metric, and tenants at/near limits.
Supports provider filtering for provider-scoped metrics (workflows, executions, environments).
"""
from fastapi import APIRouter, Query, Depends, HTTPException, status
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.services.database import db_service
from app.services.auth_service import get_current_user
from app.core.platform_admin import require_platform_admin
from app.services.entitlements_service import entitlements_service

router = APIRouter()


# ============================================================================
# Provider Filter Helper
# ============================================================================

def apply_provider_filter(query, provider: Optional[str], table_has_provider: bool = True):
    """
    Apply provider filter to a Supabase query.

    Args:
        query: Supabase query builder
        provider: Provider filter value (n8n, make, all, or None)
        table_has_provider: Whether the table has a provider column

    Returns:
        Modified query with provider filter applied
    """
    if not table_has_provider or not provider or provider == "all":
        return query
    return query.eq("provider", provider)


# ============================================================================
# Schemas
# ============================================================================

class UsageMetric(BaseModel):
    """Single usage metric with current/limit values."""
    name: str
    current: int
    limit: int
    percentage: float
    status: str  # ok, warning, critical, over_limit


class TenantUsageSummary(BaseModel):
    """Tenant with usage metrics."""
    tenant_id: str
    tenant_name: str
    plan: str
    status: str
    metrics: List[UsageMetric]
    total_usage_percentage: float


class TopTenant(BaseModel):
    """Tenant ranked by a specific metric."""
    rank: int
    tenant_id: str
    tenant_name: str
    plan: str
    provider: Optional[str] = None  # Present when querying "all" providers
    value: int
    limit: Optional[int]
    percentage: Optional[float]
    trend: Optional[str]  # up, down, stable


class GlobalUsageStats(BaseModel):
    """Global usage statistics."""
    total_tenants: int
    total_workflows: int
    total_environments: int
    total_users: int
    total_executions_today: int
    total_executions_month: int
    tenants_at_limit: int
    tenants_over_limit: int
    tenants_near_limit: int


class GlobalUsageResponse(BaseModel):
    """Global usage response."""
    stats: GlobalUsageStats
    usage_by_plan: dict
    recent_growth: dict


class UsageHistoryPoint(BaseModel):
    date: str  # YYYY-MM-DD (UTC)
    value: int


class UsageHistoryResponse(BaseModel):
    metric: str
    provider: Optional[str] = None
    days: int
    points: List[UsageHistoryPoint]


class TopTenantsResponse(BaseModel):
    """Response for top tenants by metric."""
    metric: str
    period: str
    tenants: List[TopTenant]


class TenantsAtLimitResponse(BaseModel):
    """Response for tenants at/near limits."""
    total: int
    tenants: List[TenantUsageSummary]


# ============================================================================
# Plan Limits Configuration
# ============================================================================

# Cache for plan limits
_plan_limits_cache: Dict[str, Dict[str, int]] = {}


async def get_limit(plan: str, metric: str) -> int:
    """Get limit for a plan and metric from database. Returns -1 for unlimited."""
    plan = plan.lower()
    
    # Check cache first
    if plan not in _plan_limits_cache:
        # Fetch from database
        try:
            response = db_service.client.table("plan_limits").select(
                "max_workflows, max_environments, max_users, max_executions_daily"
            ).eq("plan_name", plan).single().execute()
            
            if response.data:
                _plan_limits_cache[plan] = {
                    "max_workflows": response.data.get("max_workflows", 10),
                    "max_environments": response.data.get("max_environments", 1),
                    "max_users": response.data.get("max_users", 2),
                    "max_executions_daily": response.data.get("max_executions_daily", 100),
                }
            else:
                # Fallback to free plan defaults
                _plan_limits_cache[plan] = {
                    "max_workflows": 10,
                    "max_environments": 1,
                    "max_users": 2,
                    "max_executions_daily": 100,
                }
        except Exception:
            # Fallback to free plan defaults on error
            _plan_limits_cache[plan] = {
                "max_workflows": 10,
                "max_environments": 1,
                "max_users": 2,
                "max_executions_daily": 100,
            }
    
    return _plan_limits_cache[plan].get(metric, 0)


def calculate_usage_percentage(current: int, limit: int) -> float:
    """Calculate usage percentage. Returns 0 for unlimited."""
    if limit <= 0:  # Unlimited
        return 0
    return min(round((current / limit) * 100, 1), 999)  # Cap at 999%


def get_usage_status(percentage: float, limit: int) -> str:
    """Get usage status based on percentage."""
    if limit <= 0:  # Unlimited
        return "ok"
    if percentage >= 100:
        return "over_limit"
    if percentage >= 90:
        return "critical"
    if percentage >= 75:
        return "warning"
    return "ok"


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=GlobalUsageResponse)
async def get_global_usage(
    provider: Optional[str] = Query(None, description="Filter by provider: n8n, make, or all"),
    user_info: dict = Depends(require_platform_admin())
):
    """
    Get global usage statistics across all tenants.

    Returns aggregate metrics, usage by plan, and growth trends.

    Provider filter applies to provider-scoped metrics (workflows, environments, executions).
    Users are platform-scoped and not affected by provider filter.
    """
    try:
        # Get all tenants with their stats
        tenants_result = await db_service.client.table("tenants").select("*").execute()
        tenants = tenants_result.data or []

        # Get workflow counts (provider-scoped)
        workflows_query = db_service.client.table("workflows").select("id, tenant_id")
        workflows_query = apply_provider_filter(workflows_query, provider)
        workflows_result = await workflows_query.execute()
        workflows = workflows_result.data or []

        # Get environment counts (provider-scoped)
        envs_query = db_service.client.table("environments").select("id, tenant_id")
        envs_query = apply_provider_filter(envs_query, provider)
        envs_result = await envs_query.execute()
        environments = envs_result.data or []

        # Get user counts (platform-scoped - no provider filter)
        users_result = await db_service.client.table("users").select("id, tenant_id").execute()
        users = users_result.data or []

        # Get execution counts (provider-scoped)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        execs_today_query = db_service.client.table("executions").select("id")
        execs_today_query = execs_today_query.gte("started_at", today_start.isoformat())
        execs_today_query = apply_provider_filter(execs_today_query, provider)
        execs_today_result = await execs_today_query.execute()
        executions_today = len(execs_today_result.data or [])

        execs_month_query = db_service.client.table("executions").select("id")
        execs_month_query = execs_month_query.gte("started_at", month_start.isoformat())
        execs_month_query = apply_provider_filter(execs_month_query, provider)
        execs_month_result = await execs_month_query.execute()
        executions_month = len(execs_month_result.data or [])

        # Aggregate by tenant and plan
        tenant_workflows = {}
        tenant_envs = {}
        tenant_users = {}

        for w in workflows:
            tid = w.get("tenant_id")
            tenant_workflows[tid] = tenant_workflows.get(tid, 0) + 1

        for e in environments:
            tid = e.get("tenant_id")
            tenant_envs[tid] = tenant_envs.get(tid, 0) + 1

        for u in users:
            tid = u.get("tenant_id")
            tenant_users[tid] = tenant_users.get(tid, 0) + 1

        # Calculate tenants at/near/over limits
        tenants_at_limit = 0
        tenants_over_limit = 0
        tenants_near_limit = 0

        for t in tenants:
            tid = t.get("id")
            plan = t.get("subscription_tier", "free") or "free"
            if plan == "enterprise":
                continue  # Skip unlimited plans

            wf_count = tenant_workflows.get(tid, 0)
            env_count = tenant_envs.get(tid, 0)
            user_count = tenant_users.get(tid, 0)

            wf_limit = await get_limit(plan, "max_workflows")
            env_limit = await get_limit(plan, "max_environments")
            user_limit = await get_limit(plan, "max_users")

            wf_pct = calculate_usage_percentage(wf_count, wf_limit)
            env_pct = calculate_usage_percentage(env_count, env_limit)
            user_pct = calculate_usage_percentage(user_count, user_limit)

            max_pct = max(wf_pct, env_pct, user_pct)

            if max_pct >= 100:
                tenants_over_limit += 1
            elif max_pct >= 90:
                tenants_at_limit += 1
            elif max_pct >= 75:
                tenants_near_limit += 1

        # Usage by plan
        usage_by_plan = {}
        for t in tenants:
            plan = t.get("subscription_tier", "free") or "free"
            if plan not in usage_by_plan:
                usage_by_plan[plan] = {"tenants": 0, "workflows": 0, "environments": 0, "users": 0}
            usage_by_plan[plan]["tenants"] += 1
            tid = t.get("id")
            usage_by_plan[plan]["workflows"] += tenant_workflows.get(tid, 0)
            usage_by_plan[plan]["environments"] += tenant_envs.get(tid, 0)
            usage_by_plan[plan]["users"] += tenant_users.get(tid, 0)

        # Recent growth (simplified - would need historical data for real trends)
        recent_growth = {
            "tenants_7d": 0,
            "workflows_7d": 0,
            "environments_7d": 0,
        }

        return GlobalUsageResponse(
            stats=GlobalUsageStats(
                total_tenants=len(tenants),
                total_workflows=len(workflows),
                total_environments=len(environments),
                total_users=len(users),
                total_executions_today=executions_today,
                total_executions_month=executions_month,
                tenants_at_limit=tenants_at_limit,
                tenants_over_limit=tenants_over_limit,
                tenants_near_limit=tenants_near_limit,
            ),
            usage_by_plan=usage_by_plan,
            recent_growth=recent_growth,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get global usage: {str(e)}"
        )


@router.get("/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    metric: str = Query("executions", description="Metric to chart: executions"),
    days: int = Query(30, ge=7, le=90, description="Number of days (UTC)"),
    provider: Optional[str] = Query(None, description="Filter by provider: n8n, make, or all"),
    user_info: dict = Depends(require_platform_admin()),
):
    """
    Time-series usage data for admin charts.
    """
    try:
        if metric != "executions":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported metric")

        end_dt = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        start_dt = end_dt - timedelta(days=days)

        query = db_service.client.table("executions").select("started_at, provider")
        query = query.gte("started_at", start_dt.isoformat()).lt("started_at", end_dt.isoformat())
        query = apply_provider_filter(query, provider)
        result = await query.execute()

        counts: Dict[str, int] = {}
        for row in (result.data or []):
            ts = row.get("started_at")
            if not ts:
                continue
            day = str(ts)[:10]
            counts[day] = counts.get(day, 0) + 1

        points: List[UsageHistoryPoint] = []
        for i in range(days):
            day_dt = start_dt + timedelta(days=i)
            day_str = day_dt.strftime("%Y-%m-%d")
            points.append(UsageHistoryPoint(date=day_str, value=counts.get(day_str, 0)))

        return UsageHistoryResponse(metric=metric, provider=provider, days=days, points=points)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get usage history: {str(e)}"
        )


@router.get("/top-tenants", response_model=TopTenantsResponse)
async def get_top_tenants(
    metric: str = Query("workflows", description="Metric to rank by: workflows, users, environments, executions"),
    period: str = Query("all", description="Time period: today, week, month, all"),
    provider: Optional[str] = Query(None, description="Filter by provider: n8n, make, or all (users metric ignores this)"),
    limit: int = Query(10, ge=1, le=50),
    user_info: dict = Depends(require_platform_admin())
):
    """
    Get top tenants ranked by a specific metric.

    Provider filter applies to provider-scoped metrics (workflows, environments, executions).
    The 'users' metric is platform-scoped and ignores the provider filter.
    """
    try:
        # Get all tenants
        tenants_result = await db_service.client.table("tenants").select("*").execute()
        tenants = {t["id"]: t for t in (tenants_result.data or [])}

        tenant_values = []

        if metric == "workflows":
            # Workflows are provider-scoped
            if provider == "all":
                # When querying all providers, group by provider
                query = db_service.client.table("workflows").select("tenant_id, provider")
                result = await query.execute()
                counts_by_provider = {}
                for item in (result.data or []):
                    tid = item.get("tenant_id")
                    prov = item.get("provider", "n8n")
                    if tid not in counts_by_provider:
                        counts_by_provider[tid] = {}
                    counts_by_provider[tid][prov] = counts_by_provider[tid].get(prov, 0) + 1
                
                # Aggregate counts and include provider breakdown
                for tid, prov_counts in counts_by_provider.items():
                    if tid in tenants:
                        t = tenants[tid]
                        plan = t.get("subscription_tier", "free") or "free"
                        limit_val = await get_limit(plan, "max_workflows")
                        # For "all" providers, create separate entries per provider
                        for prov, count in prov_counts.items():
                            tenant_values.append({
                                "tenant_id": tid,
                                "tenant_name": t.get("name", "Unknown"),
                                "plan": plan,
                                "provider": prov,
                                "value": count,
                                "limit": limit_val if limit_val > 0 else None,
                            })
            else:
                query = db_service.client.table("workflows").select("tenant_id")
                query = apply_provider_filter(query, provider)
                result = await query.execute()
                counts = {}
                for item in (result.data or []):
                    tid = item.get("tenant_id")
                    counts[tid] = counts.get(tid, 0) + 1

                for tid, count in counts.items():
                    if tid in tenants:
                        t = tenants[tid]
                        plan = t.get("subscription_tier", "free") or "free"
                        limit_val = await get_limit(plan, "max_workflows")
                        tenant_values.append({
                            "tenant_id": tid,
                            "tenant_name": t.get("name", "Unknown"),
                            "plan": plan,
                            "value": count,
                            "limit": limit_val if limit_val > 0 else None,
                        })

        elif metric == "users":
            result = await db_service.client.table("users").select("tenant_id").execute()
            counts = {}
            for item in (result.data or []):
                tid = item.get("tenant_id")
                counts[tid] = counts.get(tid, 0) + 1

            for tid, count in counts.items():
                if tid in tenants:
                    t = tenants[tid]
                    plan = t.get("subscription_tier", "free") or "free"
                    limit_val = await get_limit(plan, "max_users")
                    tenant_values.append({
                        "tenant_id": tid,
                        "tenant_name": t.get("name", "Unknown"),
                        "plan": plan,
                        "value": count,
                        "limit": limit_val if limit_val > 0 else None,
                    })

        elif metric == "environments":
            # Environments are provider-scoped
            if provider == "all":
                # When querying all providers, group by provider
                query = db_service.client.table("environments").select("tenant_id, provider")
                result = await query.execute()
                counts_by_provider = {}
                for item in (result.data or []):
                    tid = item.get("tenant_id")
                    prov = item.get("provider", "n8n")
                    if tid not in counts_by_provider:
                        counts_by_provider[tid] = {}
                    counts_by_provider[tid][prov] = counts_by_provider[tid].get(prov, 0) + 1
                
                # Aggregate counts and include provider breakdown
                for tid, prov_counts in counts_by_provider.items():
                    if tid in tenants:
                        t = tenants[tid]
                        plan = t.get("subscription_tier", "free") or "free"
                        limit_val = await get_limit(plan, "max_environments")
                        # For "all" providers, create separate entries per provider
                        for prov, count in prov_counts.items():
                            tenant_values.append({
                                "tenant_id": tid,
                                "tenant_name": t.get("name", "Unknown"),
                                "plan": plan,
                                "provider": prov,
                                "value": count,
                                "limit": limit_val if limit_val > 0 else None,
                            })
            else:
                query = db_service.client.table("environments").select("tenant_id")
                query = apply_provider_filter(query, provider)
                result = await query.execute()
                counts = {}
                for item in (result.data or []):
                    tid = item.get("tenant_id")
                    counts[tid] = counts.get(tid, 0) + 1

                for tid, count in counts.items():
                    if tid in tenants:
                        t = tenants[tid]
                        plan = t.get("subscription_tier", "free") or "free"
                        limit_val = await get_limit(plan, "max_environments")
                        tenant_values.append({
                            "tenant_id": tid,
                            "tenant_name": t.get("name", "Unknown"),
                            "plan": plan,
                            "value": count,
                            "limit": limit_val if limit_val > 0 else None,
                        })

        elif metric == "executions":
            # Filter by period
            date_filter = None
            if period == "today":
                date_filter = str(datetime.utcnow().date())
            elif period == "week":
                date_filter = str((datetime.utcnow() - timedelta(days=7)).date())
            elif period == "month":
                date_filter = str((datetime.utcnow() - timedelta(days=30)).date())

            # Executions are provider-scoped
            if provider == "all":
                # When querying all providers, group by provider
                query = db_service.client.table("executions").select("tenant_id, provider, started_at")
                result = await query.execute()
                counts_by_provider = {}
                for item in (result.data or []):
                    if date_filter and item.get("started_at", "")[:10] < date_filter:
                        continue
                    tid = item.get("tenant_id")
                    prov = item.get("provider", "n8n")
                    if tid not in counts_by_provider:
                        counts_by_provider[tid] = {}
                    counts_by_provider[tid][prov] = counts_by_provider[tid].get(prov, 0) + 1
                
                # Aggregate counts and include provider breakdown
                for tid, prov_counts in counts_by_provider.items():
                    if tid in tenants:
                        t = tenants[tid]
                        plan = t.get("subscription_tier", "free") or "free"
                        # For "all" providers, create separate entries per provider
                        for prov, count in prov_counts.items():
                            tenant_values.append({
                                "tenant_id": tid,
                                "tenant_name": t.get("name", "Unknown"),
                                "plan": plan,
                                "provider": prov,
                                "value": count,
                                "limit": None,
                            })
            else:
                query = db_service.client.table("executions").select("tenant_id, started_at")
                query = apply_provider_filter(query, provider)
                result = await query.execute()
                counts = {}
                for item in (result.data or []):
                    if date_filter and item.get("started_at", "")[:10] < date_filter:
                        continue
                    tid = item.get("tenant_id")
                    counts[tid] = counts.get(tid, 0) + 1

                for tid, count in counts.items():
                    if tid in tenants:
                        t = tenants[tid]
                        plan = t.get("subscription_tier", "free") or "free"
                        tenant_values.append({
                            "tenant_id": tid,
                            "tenant_name": t.get("name", "Unknown"),
                            "plan": plan,
                            "value": count,
                            "limit": None,
                        })

        # Sort by value descending
        tenant_values.sort(key=lambda x: x["value"], reverse=True)

        # Take top N and add rank
        top_tenants = []
        for i, tv in enumerate(tenant_values[:limit]):
            pct = None
            if tv["limit"]:
                pct = round((tv["value"] / tv["limit"]) * 100, 1)

            top_tenants.append(TopTenant(
                rank=i + 1,
                tenant_id=tv["tenant_id"],
                tenant_name=tv["tenant_name"],
                plan=tv["plan"],
                provider=tv.get("provider"),  # Include provider when querying "all"
                value=tv["value"],
                limit=tv["limit"],
                percentage=pct,
                trend="stable",  # Would need historical data for real trends
            ))

        return TopTenantsResponse(
            metric=metric,
            period=period,
            tenants=top_tenants,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get top tenants: {str(e)}"
        )


@router.get("/tenants-at-limit", response_model=TenantsAtLimitResponse)
async def get_tenants_at_limit(
    threshold: int = Query(75, ge=50, le=100, description="Percentage threshold for 'near limit'"),
    provider: Optional[str] = Query(None, description="Filter by provider: n8n, make, or all (users metric ignores this)"),
    user_info: dict = Depends(require_platform_admin())
):
    """
    Get tenants that are at, near, or over their plan limits.

    Provider filter applies to provider-scoped metrics (workflows, environments).
    Users are platform-scoped and not affected by provider filter.
    """
    try:
        # Get all tenants
        tenants_result = await db_service.client.table("tenants").select("*").execute()
        tenants = tenants_result.data or []

        # Get counts (with provider filter for provider-scoped resources)
        workflows_query = db_service.client.table("workflows").select("id, tenant_id")
        workflows_query = apply_provider_filter(workflows_query, provider)
        workflows_result = await workflows_query.execute()

        envs_query = db_service.client.table("environments").select("id, tenant_id")
        envs_query = apply_provider_filter(envs_query, provider)
        envs_result = await envs_query.execute()

        # Users are platform-scoped (no provider filter)
        users_result = await db_service.client.table("users").select("id, tenant_id").execute()

        workflow_counts = {}
        env_counts = {}
        user_counts = {}

        for w in (workflows_result.data or []):
            tid = w.get("tenant_id")
            workflow_counts[tid] = workflow_counts.get(tid, 0) + 1

        for e in (envs_result.data or []):
            tid = e.get("tenant_id")
            env_counts[tid] = env_counts.get(tid, 0) + 1

        for u in (users_result.data or []):
            tid = u.get("tenant_id")
            user_counts[tid] = user_counts.get(tid, 0) + 1

        # Find tenants at/near/over limits
        at_limit_tenants = []

        for t in tenants:
            tid = t.get("id")
            plan = t.get("subscription_tier", "free") or "free"

            if plan == "enterprise":
                continue  # Skip unlimited plans

            metrics = []
            max_pct = 0

            # Check workflows
            wf_current = workflow_counts.get(tid, 0)
            wf_limit = await get_limit(plan, "max_workflows")
            wf_pct = calculate_usage_percentage(wf_current, wf_limit)
            wf_status = get_usage_status(wf_pct, wf_limit)
            max_pct = max(max_pct, wf_pct)

            metrics.append(UsageMetric(
                name="workflows",
                current=wf_current,
                limit=wf_limit,
                percentage=wf_pct,
                status=wf_status,
            ))

            # Check environments
            env_current = env_counts.get(tid, 0)
            env_limit = await get_limit(plan, "max_environments")
            env_pct = calculate_usage_percentage(env_current, env_limit)
            env_status = get_usage_status(env_pct, env_limit)
            max_pct = max(max_pct, env_pct)

            metrics.append(UsageMetric(
                name="environments",
                current=env_current,
                limit=env_limit,
                percentage=env_pct,
                status=env_status,
            ))

            # Check users
            user_current = user_counts.get(tid, 0)
            user_limit = await get_limit(plan, "max_users")
            user_pct = calculate_usage_percentage(user_current, user_limit)
            user_status = get_usage_status(user_pct, user_limit)
            max_pct = max(max_pct, user_pct)

            metrics.append(UsageMetric(
                name="users",
                current=user_current,
                limit=user_limit,
                percentage=user_pct,
                status=user_status,
            ))

            # Only include if at/near/over limit
            if max_pct >= threshold:
                at_limit_tenants.append(TenantUsageSummary(
                    tenant_id=tid,
                    tenant_name=t.get("name", "Unknown"),
                    plan=plan,
                    status=t.get("status", "active"),
                    metrics=metrics,
                    total_usage_percentage=max_pct,
                ))

        at_limit_tenants.sort(key=lambda x: x.total_usage_percentage, reverse=True)

        return TenantsAtLimitResponse(
            total=len(at_limit_tenants),
            tenants=at_limit_tenants,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenants at limit: {str(e)}"
        )


@router.get("/tenants/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: str,
    provider: Optional[str] = Query(None, description="Filter by provider: n8n, make, or all"),
    user_info: dict = Depends(require_platform_admin())
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

        # Get counts with provider filtering
        workflow_query = db_service.client.table("workflows").select("id, provider", count="exact")
        workflow_query = workflow_query.eq("tenant_id", tenant_id).eq("is_deleted", False)
        workflow_query = apply_provider_filter_local(workflow_query)
        workflow_response = await workflow_query.execute()
        workflow_count = workflow_response.count or 0

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
