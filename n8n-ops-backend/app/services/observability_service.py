from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import time
import logging

from app.services.database import db_service
from app.services.n8n_client import N8NClient
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)
from app.schemas.observability import (
    TimeRange,
    EnvironmentStatus,
    DriftState,
    KPIMetrics,
    WorkflowPerformance,
    EnvironmentHealth,
    PromotionSyncStats,
    RecentDeployment,
    ObservabilityOverview,
    HealthCheckResponse,
)


def get_time_range_bounds(time_range: TimeRange) -> tuple[str, str]:
    """Convert TimeRange enum to datetime bounds"""
    now = datetime.utcnow()

    if time_range == TimeRange.ONE_HOUR:
        since = now - timedelta(hours=1)
    elif time_range == TimeRange.SIX_HOURS:
        since = now - timedelta(hours=6)
    elif time_range == TimeRange.TWENTY_FOUR_HOURS:
        since = now - timedelta(hours=24)
    elif time_range == TimeRange.SEVEN_DAYS:
        since = now - timedelta(days=7)
    elif time_range == TimeRange.THIRTY_DAYS:
        since = now - timedelta(days=30)
    else:
        since = now - timedelta(hours=24)

    return since.isoformat(), now.isoformat()


def get_previous_period_bounds(time_range: TimeRange) -> tuple[str, str]:
    """Get the previous period for delta calculations"""
    now = datetime.utcnow()

    if time_range == TimeRange.ONE_HOUR:
        delta = timedelta(hours=1)
    elif time_range == TimeRange.SIX_HOURS:
        delta = timedelta(hours=6)
    elif time_range == TimeRange.TWENTY_FOUR_HOURS:
        delta = timedelta(hours=24)
    elif time_range == TimeRange.SEVEN_DAYS:
        delta = timedelta(days=7)
    elif time_range == TimeRange.THIRTY_DAYS:
        delta = timedelta(days=30)
    else:
        delta = timedelta(hours=24)

    period_end = now - delta
    period_start = period_end - delta

    return period_start.isoformat(), period_end.isoformat()


class ObservabilityService:
    """Service for computing observability metrics and health data"""

    async def get_kpi_metrics(
        self,
        tenant_id: str,
        time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS,
        include_delta: bool = True
    ) -> KPIMetrics:
        """Get KPI metrics for the specified time range"""
        since, until = get_time_range_bounds(time_range)

        # Get current period stats
        stats = await db_service.get_execution_stats(tenant_id, since, until)

        # Get previous period stats for delta calculation
        delta_executions = None
        delta_success_rate = None

        if include_delta:
            prev_since, prev_until = get_previous_period_bounds(time_range)
            prev_stats = await db_service.get_execution_stats(tenant_id, prev_since, prev_until)

            if prev_stats["total_executions"] > 0:
                delta_executions = stats["total_executions"] - prev_stats["total_executions"]
                delta_success_rate = stats["success_rate"] - prev_stats["success_rate"]

        return KPIMetrics(
            total_executions=stats["total_executions"],
            success_count=stats["success_count"],
            failure_count=stats["failure_count"],
            success_rate=stats["success_rate"],
            avg_duration_ms=stats["avg_duration_ms"],
            p95_duration_ms=stats.get("p95_duration_ms"),
            delta_executions=delta_executions,
            delta_success_rate=delta_success_rate
        )

    async def get_workflow_performance(
        self,
        tenant_id: str,
        time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS,
        limit: int = 10,
        sort_by: str = "executions"
    ) -> List[WorkflowPerformance]:
        """Get per-workflow performance metrics"""
        since, until = get_time_range_bounds(time_range)

        stats = await db_service.get_workflow_execution_stats(
            tenant_id, since, until, limit, sort_by
        )

        return [
            WorkflowPerformance(
                workflow_id=s["workflow_id"],
                workflow_name=s["workflow_name"],
                execution_count=s["execution_count"],
                success_count=s["success_count"],
                failure_count=s["failure_count"],
                error_rate=s["error_rate"],
                avg_duration_ms=s["avg_duration_ms"],
                p95_duration_ms=s.get("p95_duration_ms")
            )
            for s in stats
        ]

    async def get_environment_health(
        self,
        tenant_id: str
    ) -> List[EnvironmentHealth]:
        """Get health status for all environments"""
        environments = await db_service.get_environments(tenant_id)
        results = []

        # Calculate uptime since 24 hours ago
        since_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        since_7d = (datetime.utcnow() - timedelta(days=7)).isoformat()

        for env in environments:
            env_id = env["id"]

            # Get latest health check
            latest_check = await db_service.get_latest_health_check(tenant_id, env_id)

            # Get uptime stats
            uptime_stats = await db_service.get_uptime_stats(tenant_id, env_id, since_24h)

            # Get latest deployment and snapshot for this environment
            deployments = await db_service.get_deployments(tenant_id)
            env_deployments = [d for d in deployments if d.get("target_environment_id") == env_id]
            last_deployment = env_deployments[0] if env_deployments else None

            snapshots = await db_service.get_snapshots(tenant_id, environment_id=env_id)
            last_snapshot = snapshots[0] if snapshots else None

            # Get active workflow count
            workflows = await db_service.get_workflows(tenant_id, env_id)
            active_workflows = sum(1 for w in workflows if w.get("active"))
            total_workflows = len(workflows)

            # Determine status
            if latest_check:
                status = EnvironmentStatus(latest_check["status"])
            else:
                # No health check yet - assume healthy if environment is active
                status = EnvironmentStatus.HEALTHY if env.get("is_active") else EnvironmentStatus.UNREACHABLE

            # Determine drift state (simplified - would need full drift check implementation)
            drift_state = DriftState.UNKNOWN

            results.append(EnvironmentHealth(
                environment_id=env_id,
                environment_name=env.get("n8n_name", "Unknown"),
                environment_type=env.get("n8n_type"),
                status=status,
                latency_ms=latest_check.get("latency_ms") if latest_check else None,
                uptime_percent=uptime_stats["uptime_percent"],
                active_workflows=active_workflows,
                total_workflows=total_workflows,
                last_deployment_at=last_deployment.get("started_at") if last_deployment else None,
                last_snapshot_at=last_snapshot.get("created_at") if last_snapshot else None,
                drift_state=drift_state,
                last_checked_at=latest_check.get("checked_at") if latest_check else None
            ))

        return results

    async def get_promotion_sync_stats(
        self,
        tenant_id: str,
        days: int = 7
    ) -> PromotionSyncStats:
        """Get promotion and sync statistics for the specified period"""
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Get deployment stats
        deployment_stats = await db_service.get_deployment_stats(tenant_id, since)

        # Get snapshot stats
        snapshot_stats = await db_service.get_snapshot_stats(tenant_id, since)

        # Get recent deployments with details
        recent = await db_service.get_recent_deployments_with_details(tenant_id, limit=5)

        recent_deployments = [
            RecentDeployment(
                id=d["id"],
                pipeline_name=d.get("pipeline_name"),
                source_environment_name=d["source_environment_name"],
                target_environment_name=d["target_environment_name"],
                status=d["status"],
                started_at=d["started_at"],
                finished_at=d.get("finished_at")
            )
            for d in recent
        ]

        # TODO: Calculate actual drift count by checking workflows across environments
        drift_count = 0

        return PromotionSyncStats(
            promotions_total=deployment_stats["total"],
            promotions_success=deployment_stats["success"],
            promotions_failed=deployment_stats["failed"],
            promotions_blocked=deployment_stats["blocked"],
            snapshots_created=snapshot_stats["created"],
            snapshots_restored=snapshot_stats["restored"],
            drift_count=drift_count,
            recent_deployments=recent_deployments
        )

    async def check_environment_health(
        self,
        tenant_id: str,
        environment_id: str
    ) -> HealthCheckResponse:
        """Perform a health check on an environment"""
        # Get environment details
        env = await db_service.get_environment(environment_id, tenant_id)
        if not env:
            raise ValueError(f"Environment {environment_id} not found")

        # Create N8N client
        n8n_client = N8NClient(
            base_url=env.get("n8n_base_url"),
            api_key=env.get("n8n_api_key")
        )

        # Measure latency and test connection
        start_time = time.time()
        try:
            is_connected = await n8n_client.test_connection()
            latency_ms = int((time.time() - start_time) * 1000)

            if is_connected:
                status = EnvironmentStatus.HEALTHY
                error_message = None
            else:
                status = EnvironmentStatus.UNREACHABLE
                error_message = "Connection test failed"
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            status = EnvironmentStatus.UNREACHABLE
            error_message = str(e)

        # Get previous health check status for recovery detection
        previous_check = await db_service.get_latest_health_check(tenant_id, environment_id)
        previous_status = None
        if previous_check:
            previous_status = EnvironmentStatus(previous_check.get("status")) if previous_check.get("status") else None

        # Store health check result
        health_check_data = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "status": status.value,
            "latency_ms": latency_ms,
            "error_message": error_message
        }
        result = await db_service.create_health_check(health_check_data)

        # Emit environment health events
        try:
            # Check for status changes and emit appropriate events
            if status == EnvironmentStatus.UNREACHABLE:
                await notification_service.emit_event(
                    tenant_id=tenant_id,
                    event_type="environment.connection_lost",
                    environment_id=environment_id,
                    metadata={
                        "environment_id": environment_id,
                        "status": status.value,
                        "latency_ms": latency_ms,
                        "error_message": error_message,
                        "previous_status": previous_status.value if previous_status else None
                    }
                )
            elif status == EnvironmentStatus.DEGRADED:
                await notification_service.emit_event(
                    tenant_id=tenant_id,
                    event_type="environment.unhealthy",
                    environment_id=environment_id,
                    metadata={
                        "environment_id": environment_id,
                        "status": status.value,
                        "latency_ms": latency_ms,
                        "error_message": error_message,
                        "previous_status": previous_status.value if previous_status else None
                    }
                )
            elif status == EnvironmentStatus.HEALTHY and previous_status and previous_status != EnvironmentStatus.HEALTHY:
                # Environment recovered from unhealthy/unreachable state
                await notification_service.emit_event(
                    tenant_id=tenant_id,
                    event_type="environment.recovered",
                    environment_id=environment_id,
                    metadata={
                        "environment_id": environment_id,
                        "status": status.value,
                        "latency_ms": latency_ms,
                        "previous_status": previous_status.value
                    }
                )
        except Exception as e:
            logger.error(f"Failed to emit environment health event: {str(e)}")

        return HealthCheckResponse(
            id=result["id"],
            tenant_id=tenant_id,
            environment_id=environment_id,
            status=status,
            latency_ms=latency_ms,
            checked_at=result["checked_at"],
            error_message=error_message
        )

    async def get_observability_overview(
        self,
        tenant_id: str,
        time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS
    ) -> ObservabilityOverview:
        """Get complete observability overview"""
        # Fetch all data in parallel (would benefit from asyncio.gather)
        kpi_metrics = await self.get_kpi_metrics(tenant_id, time_range)
        workflow_performance = await self.get_workflow_performance(tenant_id, time_range)
        environment_health = await self.get_environment_health(tenant_id)
        promotion_sync_stats = await self.get_promotion_sync_stats(tenant_id)

        return ObservabilityOverview(
            kpi_metrics=kpi_metrics,
            workflow_performance=workflow_performance,
            environment_health=environment_health,
            promotion_sync_stats=promotion_sync_stats
        )


# Global instance
observability_service = ObservabilityService()
