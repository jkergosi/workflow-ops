from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List
import logging

from app.schemas.observability import (
    TimeRange,
    KPIMetrics,
    WorkflowPerformance,
    EnvironmentHealth,
    PromotionSyncStats,
    ObservabilityOverview,
    HealthCheckResponse,
)
from app.services.observability_service import observability_service
from app.core.entitlements_gate import require_entitlement

router = APIRouter()
logger = logging.getLogger(__name__)

# Mock tenant ID for development (same as other endpoints)
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


@router.get("/overview", response_model=ObservabilityOverview)
async def get_observability_overview(
    time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS,
    environment_id: Optional[str] = None,
    _: dict = Depends(require_entitlement("observability_basic"))
):
    """
    Get complete observability overview including KPIs, workflow performance,
    environment health, and promotion/sync stats.

    - **time_range**: Time period to analyze (1h, 6h, 24h, 7d, 30d)
    - **environment_id**: Optional environment ID to filter by
    """
    try:
        logger.info(f"Getting observability overview: time_range={time_range}, environment_id={environment_id}, tenant_id={MOCK_TENANT_ID}")
        overview = await observability_service.get_observability_overview(
            MOCK_TENANT_ID,
            time_range,
            environment_id=environment_id
        )
        logger.info(f"Observability overview returned: kpi_total_executions={overview.kpi_metrics.total_executions}, workflow_count={len(overview.workflow_performance)}")
        return overview
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get observability overview: {str(e)}"
        )


@router.get("/kpi", response_model=KPIMetrics)
async def get_kpi_metrics(
    time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS,
    _: dict = Depends(require_entitlement("observability_basic"))
):
    """
    Get KPI metrics for the specified time range.
    Includes total executions, success rate, average duration, and failed count.
    """
    try:
        metrics = await observability_service.get_kpi_metrics(
            MOCK_TENANT_ID,
            time_range
        )
        return metrics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get KPI metrics: {str(e)}"
        )


@router.get("/workflow-performance", response_model=List[WorkflowPerformance])
async def get_workflow_performance(
    time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS,
    limit: int = 10,
    sort_by: str = "executions",
    _: dict = Depends(require_entitlement("observability_basic"))
):
    """
    Get per-workflow performance metrics.

    - **time_range**: Time period to analyze (1h, 6h, 24h, 7d, 30d)
    - **limit**: Maximum number of workflows to return
    - **sort_by**: Sort by 'executions' or 'failures'
    """
    if sort_by not in ["executions", "failures"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sort_by must be 'executions' or 'failures'"
        )

    try:
        performance = await observability_service.get_workflow_performance(
            MOCK_TENANT_ID,
            time_range,
            limit,
            sort_by
        )
        return performance
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow performance: {str(e)}"
        )


@router.get("/environment-health", response_model=List[EnvironmentHealth])
async def get_environment_health(
    _: dict = Depends(require_entitlement("environment_health"))
):
    """
    Get health status for all environments.
    Includes latency, uptime, workflow counts, and last deployment/snapshot info.
    """
    try:
        health = await observability_service.get_environment_health(MOCK_TENANT_ID)
        return health
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get environment health: {str(e)}"
        )


@router.get("/promotion-stats", response_model=PromotionSyncStats)
async def get_promotion_stats(
    days: int = 7,
    _: dict = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get promotion and sync statistics for the specified number of days.
    """
    if days < 1 or days > 90:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="days must be between 1 and 90"
        )

    try:
        stats = await observability_service.get_promotion_sync_stats(
            MOCK_TENANT_ID,
            days
        )
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get promotion stats: {str(e)}"
        )


@router.post("/health-check/{environment_id}", response_model=HealthCheckResponse)
async def trigger_health_check(
    environment_id: str,
    _: dict = Depends(require_entitlement("environment_health"))
):
    """
    Trigger a manual health check for an environment.
    Returns the health check result with latency and status.
    """
    try:
        result = await observability_service.check_environment_health(
            MOCK_TENANT_ID,
            environment_id
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform health check: {str(e)}"
        )
