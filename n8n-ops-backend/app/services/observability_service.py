from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import time
import logging

from app.services.database import db_service
from app.services.provider_registry import ProviderRegistry
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)
from app.schemas.observability import (
    TimeRange,
    EnvironmentStatus,
    DriftState,
    SystemHealthStatus,
    KPIMetrics,
    WorkflowPerformance,
    EnvironmentHealth,
    PromotionSyncStats,
    RecentDeployment,
    ObservabilityOverview,
    HealthCheckResponse,
    SystemStatus,
    SystemStatusInsight,
    SparklineDataPoint,
    ErrorGroup,
    ErrorIntelligence,
    CredentialHealth,
    ImpactedWorkflow,
)


def get_time_range_bounds(time_range: TimeRange) -> tuple[str, str]:
    """Convert TimeRange enum to datetime bounds"""
    now = datetime.now(timezone.utc)

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
    now = datetime.now(timezone.utc)

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

    def _get_sparkline_intervals(self, time_range: TimeRange) -> int:
        """Get the number of intervals for sparkline based on time range"""
        if time_range == TimeRange.ONE_HOUR:
            return 12  # 5-minute intervals
        elif time_range == TimeRange.SIX_HOURS:
            return 12  # 30-minute intervals
        elif time_range == TimeRange.TWENTY_FOUR_HOURS:
            return 24  # 1-hour intervals
        elif time_range == TimeRange.SEVEN_DAYS:
            return 14  # 12-hour intervals
        elif time_range == TimeRange.THIRTY_DAYS:
            return 30  # 1-day intervals
        return 12

    async def _get_sparkline_data(
        self,
        tenant_id: str,
        time_range: TimeRange,
        environment_id: Optional[str] = None
    ) -> Dict[str, List[SparklineDataPoint]]:
        """Get sparkline data for KPIs"""
        intervals = self._get_sparkline_intervals(time_range)
        now = datetime.now(timezone.utc)

        # Calculate interval duration
        if time_range == TimeRange.ONE_HOUR:
            interval_delta = timedelta(minutes=5)
        elif time_range == TimeRange.SIX_HOURS:
            interval_delta = timedelta(minutes=30)
        elif time_range == TimeRange.TWENTY_FOUR_HOURS:
            interval_delta = timedelta(hours=1)
        elif time_range == TimeRange.SEVEN_DAYS:
            interval_delta = timedelta(hours=12)
        elif time_range == TimeRange.THIRTY_DAYS:
            interval_delta = timedelta(days=1)
        else:
            interval_delta = timedelta(hours=1)

        executions_data = []
        success_rate_data = []
        duration_data = []
        failures_data = []

        for i in range(intervals):
            interval_end = now - (i * interval_delta)
            interval_start = interval_end - interval_delta

            try:
                stats = await db_service.get_execution_stats(
                    tenant_id,
                    interval_start.isoformat(),
                    interval_end.isoformat(),
                    environment_id=environment_id
                )

                executions_data.append(SparklineDataPoint(
                    timestamp=interval_start,
                    value=float(stats.get("total_executions", 0))
                ))
                success_rate_data.append(SparklineDataPoint(
                    timestamp=interval_start,
                    value=float(stats.get("success_rate", 0))
                ))
                duration_data.append(SparklineDataPoint(
                    timestamp=interval_start,
                    value=float(stats.get("avg_duration_ms", 0))
                ))
                failures_data.append(SparklineDataPoint(
                    timestamp=interval_start,
                    value=float(stats.get("failure_count", 0))
                ))
            except Exception as e:
                logger.warning(f"Error getting sparkline data for interval {i}: {e}")
                # Add zero values for failed intervals
                executions_data.append(SparklineDataPoint(timestamp=interval_start, value=0))
                success_rate_data.append(SparklineDataPoint(timestamp=interval_start, value=0))
                duration_data.append(SparklineDataPoint(timestamp=interval_start, value=0))
                failures_data.append(SparklineDataPoint(timestamp=interval_start, value=0))

        # Reverse to get chronological order
        return {
            "executions": list(reversed(executions_data)),
            "success_rate": list(reversed(success_rate_data)),
            "duration": list(reversed(duration_data)),
            "failures": list(reversed(failures_data))
        }

    async def get_kpi_metrics(
        self,
        tenant_id: str,
        time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS,
        include_delta: bool = True,
        include_sparklines: bool = True,
        environment_id: Optional[str] = None
    ) -> KPIMetrics:
        """Get KPI metrics for the specified time range"""
        since, until = get_time_range_bounds(time_range)
        logger.info(f"get_kpi_metrics: tenant_id={tenant_id}, time_range={time_range}, since={since}, until={until}, environment_id={environment_id}")

        # Get current period stats
        stats = await db_service.get_execution_stats(tenant_id, since, until, environment_id=environment_id)
        logger.info(f"get_kpi_metrics result: total_executions={stats.get('total_executions')}, success_count={stats.get('success_count')}, failure_count={stats.get('failure_count')}")

        # Get previous period stats for delta calculation
        delta_executions = None
        delta_success_rate = None

        if include_delta:
            prev_since, prev_until = get_previous_period_bounds(time_range)
            prev_stats = await db_service.get_execution_stats(tenant_id, prev_since, prev_until, environment_id=environment_id)

            if prev_stats["total_executions"] > 0:
                delta_executions = stats["total_executions"] - prev_stats["total_executions"]
                delta_success_rate = stats["success_rate"] - prev_stats["success_rate"]

        # Get sparkline data
        sparklines = None
        if include_sparklines:
            try:
                sparklines = await self._get_sparkline_data(tenant_id, time_range, environment_id)
            except Exception as e:
                logger.warning(f"Failed to get sparkline data: {e}")

        return KPIMetrics(
            total_executions=stats["total_executions"],
            success_count=stats["success_count"],
            failure_count=stats["failure_count"],
            success_rate=stats["success_rate"],
            avg_duration_ms=stats["avg_duration_ms"],
            p95_duration_ms=stats.get("p95_duration_ms"),
            delta_executions=delta_executions,
            delta_success_rate=delta_success_rate,
            executions_sparkline=sparklines.get("executions") if sparklines else None,
            success_rate_sparkline=sparklines.get("success_rate") if sparklines else None,
            duration_sparkline=sparklines.get("duration") if sparklines else None,
            failures_sparkline=sparklines.get("failures") if sparklines else None
        )

    async def get_workflow_performance(
        self,
        tenant_id: str,
        time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS,
        limit: int = 10,
        sort_by: str = "executions",
        environment_id: Optional[str] = None
    ) -> List[WorkflowPerformance]:
        """Get per-workflow performance metrics with risk scoring"""
        since, until = get_time_range_bounds(time_range)

        stats = await db_service.get_workflow_execution_stats(
            tenant_id, since, until, limit * 2, sort_by, environment_id=environment_id  # Get more to allow risk sorting
        )

        results = []
        for s in stats:
            # Calculate risk score: error_rate * log(execution_count + 1)
            # This weighs both failure rate and volume
            import math
            error_rate = s.get("error_rate", 0)
            exec_count = s.get("execution_count", 0)
            risk_score = error_rate * math.log(exec_count + 1) if exec_count > 0 else 0

            # Get last failure info
            last_failure_at = None
            primary_error_type = None
            try:
                last_failure = await db_service.get_last_workflow_failure(
                    tenant_id, s["workflow_id"], environment_id=environment_id
                )
                if last_failure:
                    last_failure_at = last_failure.get("started_at") or last_failure.get("finished_at")
                    # Try to extract error type from execution data
                    error_data = last_failure.get("data") or {}
                    if isinstance(error_data, dict):
                        error_msg = error_data.get("error", {}).get("message", "") or ""
                        primary_error_type, _ = self._classify_error(error_msg)
            except Exception as e:
                logger.warning(f"Failed to get last failure for workflow {s['workflow_id']}: {e}")

            results.append(WorkflowPerformance(
                workflow_id=s["workflow_id"],
                workflow_name=s["workflow_name"],
                execution_count=s["execution_count"],
                success_count=s["success_count"],
                failure_count=s["failure_count"],
                error_rate=s["error_rate"],
                avg_duration_ms=s["avg_duration_ms"],
                p95_duration_ms=s.get("p95_duration_ms"),
                risk_score=risk_score,
                last_failure_at=last_failure_at,
                primary_error_type=primary_error_type
            ))

        # Sort by risk if requested
        if sort_by == "risk":
            results.sort(key=lambda x: x.risk_score or 0, reverse=True)

        return results[:limit]

    def _classify_error(self, error_message: str) -> tuple[str, bool]:
        """Classify error message into error type categories.

        Returns:
            tuple: (error_type, is_classified) - is_classified is False if using fallback
        """
        if not error_message:
            return ("Unknown Error", False)

        error_lower = error_message.lower()

        # Credential / Auth errors
        if any(kw in error_lower for kw in ["credential", "authentication", "unauthorized", "auth", "api key", "token expired", "invalid token"]):
            return ("Credential Error", True)
        # Timeout errors
        elif any(kw in error_lower for kw in ["timeout", "timed out", "deadline exceeded", "request timeout"]):
            return ("Timeout", True)
        # Connection / Network errors
        elif any(kw in error_lower for kw in ["connection", "network", "econnrefused", "econnreset", "enotfound", "dns", "socket", "unreachable"]):
            return ("Connection Error", True)
        # HTTP 5xx errors
        elif any(kw in error_lower for kw in ["500", "502", "503", "504", "internal server error", "bad gateway", "service unavailable"]):
            return ("HTTP 5xx", True)
        # HTTP 4xx errors
        elif any(kw in error_lower for kw in ["404", "not found", "resource not found"]):
            return ("HTTP 404", True)
        elif any(kw in error_lower for kw in ["400", "bad request"]):
            return ("HTTP 400", True)
        # Rate limiting
        elif any(kw in error_lower for kw in ["rate limit", "429", "too many requests", "throttl"]):
            return ("Rate Limit", True)
        # Permission errors
        elif any(kw in error_lower for kw in ["permission", "forbidden", "403", "access denied"]):
            return ("Permission Error", True)
        # Validation errors
        elif any(kw in error_lower for kw in ["validation", "invalid", "required field", "missing field", "schema"]):
            return ("Validation Error", True)
        # Node-specific errors
        elif any(kw in error_lower for kw in ["node", "execution failed", "workflow error"]):
            return ("Node Error", True)
        # Data/parsing errors
        elif any(kw in error_lower for kw in ["json", "parse", "syntax", "undefined", "null"]):
            return ("Data Error", True)
        else:
            # Fallback - mark as unclassified so UI can show sample message
            return ("Execution Error", False)

    async def get_error_intelligence(
        self,
        tenant_id: str,
        time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS,
        environment_id: Optional[str] = None
    ) -> ErrorIntelligence:
        """Get error intelligence - grouped errors for diagnostics"""
        since, until = get_time_range_bounds(time_range)

        try:
            # Get failed executions
            failed_executions = await db_service.get_failed_executions(
                tenant_id, since, until, environment_id=environment_id
            )
        except Exception as e:
            logger.warning(f"Failed to get failed executions: {e}")
            failed_executions = []

        # Group errors by type
        error_groups: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "first_seen": None,
            "last_seen": None,
            "workflow_ids": set(),
            "sample_message": None,
            "is_classified": True
        })

        for execution in failed_executions:
            # Extract error info
            error_data = execution.get("data") or {}
            error_msg = ""
            if isinstance(error_data, dict):
                error_obj = error_data.get("error", {})
                if isinstance(error_obj, dict):
                    error_msg = error_obj.get("message", "")
                elif isinstance(error_obj, str):
                    error_msg = error_obj

            error_type, is_classified = self._classify_error(error_msg)
            exec_time = execution.get("started_at") or execution.get("finished_at")

            group = error_groups[error_type]
            group["count"] += 1
            group["workflow_ids"].add(execution.get("workflow_id", ""))
            # Track if any errors in this group are unclassified
            if not is_classified:
                group["is_classified"] = False

            if exec_time:
                if isinstance(exec_time, str):
                    exec_time = datetime.fromisoformat(exec_time.replace("Z", "+00:00"))
                if group["first_seen"] is None or exec_time < group["first_seen"]:
                    group["first_seen"] = exec_time
                if group["last_seen"] is None or exec_time > group["last_seen"]:
                    group["last_seen"] = exec_time

            if group["sample_message"] is None and error_msg:
                group["sample_message"] = error_msg[:200]  # Truncate

        # Convert to list of ErrorGroup
        errors = []
        for error_type, data in error_groups.items():
            workflow_ids = list(data["workflow_ids"])
            errors.append(ErrorGroup(
                error_type=error_type,
                count=data["count"],
                first_seen=data["first_seen"] or datetime.now(timezone.utc),
                last_seen=data["last_seen"] or datetime.now(timezone.utc),
                affected_workflow_count=len(workflow_ids),
                affected_workflow_ids=workflow_ids,
                sample_message=data["sample_message"],
                is_classified=data["is_classified"]
            ))

        # Sort by count descending
        errors.sort(key=lambda x: x.count, reverse=True)

        return ErrorIntelligence(
            errors=errors,
            total_error_count=sum(e.count for e in errors)
        )

    async def get_environment_health(
        self,
        tenant_id: str
    ) -> List[EnvironmentHealth]:
        """Get health status for all environments with credential health and drift"""
        environments = await db_service.get_environments(tenant_id)
        results = []

        # Calculate uptime since 24 hours ago
        since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

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
            last_deployment_status = last_deployment.get("status") if last_deployment else None

            snapshots = await db_service.get_snapshots(tenant_id, environment_id=env_id)
            last_snapshot = snapshots[0] if snapshots else None

            # Get active workflow count
            workflows = await db_service.get_workflows(tenant_id, env_id)
            active_workflows = sum(1 for w in workflows if w.get("active"))
            total_workflows = len(workflows)

            # Determine status
            api_reachable = True
            if latest_check:
                status = EnvironmentStatus(latest_check["status"])
                api_reachable = status != EnvironmentStatus.UNREACHABLE
            else:
                # No health check yet - assume healthy if environment is active
                status = EnvironmentStatus.HEALTHY if env.get("is_active") else EnvironmentStatus.UNREACHABLE
                api_reachable = env.get("is_active", False)

            # Get credential health
            credential_health = None
            try:
                credentials = await db_service.get_credentials(tenant_id, env_id)
                if credentials:
                    # For now, count all as valid (would need actual validation)
                    credential_health = CredentialHealth(
                        total_count=len(credentials),
                        valid_count=len(credentials),
                        invalid_count=0,
                        unknown_count=0
                    )
            except Exception as e:
                logger.warning(f"Failed to get credentials for env {env_id}: {e}")

            # Get drift state and count
            drift_state = DriftState.UNKNOWN
            drift_workflow_count = 0
            try:
                # Check if git is configured
                if env.get("git_repo_url"):
                    # Would need to implement actual drift detection
                    # For now, return unknown
                    drift_state = DriftState.UNKNOWN
            except Exception as e:
                logger.warning(f"Failed to check drift for env {env_id}: {e}")

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
                last_deployment_status=last_deployment_status,
                last_snapshot_at=last_snapshot.get("created_at") if last_snapshot else None,
                drift_state=drift_state,
                drift_workflow_count=drift_workflow_count,
                last_checked_at=latest_check.get("checked_at") if latest_check else None,
                credential_health=credential_health,
                api_reachable=api_reachable
            ))

        return results

    async def get_promotion_sync_stats(
        self,
        tenant_id: str,
        days: int = 7
    ) -> PromotionSyncStats:
        """Get promotion and sync statistics for the specified period"""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        # Get deployment stats
        deployment_stats = await db_service.get_deployment_stats(tenant_id, since)

        # Get snapshot stats
        snapshot_stats = await db_service.get_snapshot_stats(tenant_id, since)

        # Get recent deployments with details
        recent = await db_service.get_recent_deployments_with_details(tenant_id, limit=5)

        recent_deployments = []
        for d in recent:
            # Get impacted workflows for failed deployments
            impacted_workflows = None
            if d["status"] == "failed":
                try:
                    deployment_workflows = await db_service.get_deployment_workflows(d["id"])
                    if deployment_workflows:
                        impacted_workflows = [
                            ImpactedWorkflow(
                                workflow_id=dw.get("workflow_id", ""),
                                workflow_name=dw.get("workflow_name_at_time", "Unknown"),
                                change_type=dw.get("status", "failed")
                            )
                            for dw in deployment_workflows
                            if dw.get("status") == "failed"
                        ]
                except Exception as e:
                    logger.warning(f"Failed to get deployment workflows for {d['id']}: {e}")

            recent_deployments.append(RecentDeployment(
                id=d["id"],
                pipeline_name=d.get("pipeline_name"),
                source_environment_name=d["source_environment_name"],
                target_environment_name=d["target_environment_name"],
                status=d["status"],
                started_at=d["started_at"],
                finished_at=d.get("finished_at"),
                impacted_workflows=impacted_workflows
            ))

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

    async def get_system_status(
        self,
        tenant_id: str,
        time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS,
        environment_id: Optional[str] = None
    ) -> SystemStatus:
        """Compute system status with health verdict and insights"""
        insights = []

        # Get KPI metrics for failure analysis
        kpi = await self.get_kpi_metrics(
            tenant_id, time_range, include_sparklines=False, environment_id=environment_id
        )

        # Calculate failure delta percentage
        failure_delta_percent = None
        if kpi.delta_success_rate is not None:
            failure_delta_percent = -kpi.delta_success_rate  # Inverse of success rate delta

        # Get workflows with high failure rate
        workflows = await self.get_workflow_performance(
            tenant_id, time_range, limit=50, sort_by="failures", environment_id=environment_id
        )
        failing_workflows = [w for w in workflows if w.failure_count > 0 and w.error_rate >= 50]
        failing_workflows_count = len(failing_workflows)

        # Get recent failed deployments and count them
        last_failed_deployment = None
        failed_deployment_count = 0
        failed_deployment_routes: List[str] = []
        try:
            recent_deployments = await db_service.get_recent_deployments_with_details(tenant_id, limit=10)
            for d in recent_deployments:
                if d["status"] == "failed":
                    failed_deployment_count += 1
                    route = f"{d['source_environment_name']}→{d['target_environment_name']}"
                    if route not in failed_deployment_routes:
                        failed_deployment_routes.append(route)
                    if last_failed_deployment is None:
                        last_failed_deployment = route
        except Exception as e:
            logger.warning(f"Failed to get recent deployments: {e}")

        # Build insights
        if failure_delta_percent is not None and failure_delta_percent > 10:
            # Add context about deployment failures if correlated
            if failed_deployment_count > 0:
                routes_str = ", ".join(failed_deployment_routes[:2])
                insights.append(SystemStatusInsight(
                    message=f"Failures ↑ {failure_delta_percent:.1f}% — correlates with {failed_deployment_count} failed deployment(s) ({routes_str})",
                    severity="warning"
                ))
            else:
                insights.append(SystemStatusInsight(
                    message=f"Failures ↑ {failure_delta_percent:.1f}% vs previous period",
                    severity="warning"
                ))
        elif failed_deployment_count > 0:
            # Show deployment failures even if no failure delta
            routes_str = ", ".join(failed_deployment_routes[:2])
            insights.append(SystemStatusInsight(
                message=f"{failed_deployment_count} failed deployment(s) recently ({routes_str})",
                severity="warning",
                link_type="deployment"
            ))

        if failing_workflows_count > 0:
            insights.append(SystemStatusInsight(
                message=f"{failing_workflows_count} workflow(s) failing repeatedly",
                severity="warning" if failing_workflows_count < 3 else "critical",
                link_type="workflow"
            ))

        # Check environment health
        try:
            env_health = await self.get_environment_health(tenant_id)
            unreachable = [e for e in env_health if e.status == EnvironmentStatus.UNREACHABLE]
            degraded = [e for e in env_health if e.status == EnvironmentStatus.DEGRADED]

            if unreachable:
                insights.append(SystemStatusInsight(
                    message=f"{len(unreachable)} environment(s) unreachable",
                    severity="critical",
                    link_type="environment"
                ))
            if degraded:
                insights.append(SystemStatusInsight(
                    message=f"{len(degraded)} environment(s) degraded",
                    severity="warning",
                    link_type="environment"
                ))
        except Exception as e:
            logger.warning(f"Failed to get environment health for status: {e}")

        # Determine overall status
        critical_count = sum(1 for i in insights if i.severity == "critical")
        warning_count = sum(1 for i in insights if i.severity == "warning")

        if critical_count > 0 or failing_workflows_count >= 3:
            status = SystemHealthStatus.CRITICAL
        elif warning_count > 0 or failing_workflows_count > 0:
            status = SystemHealthStatus.DEGRADED
        else:
            status = SystemHealthStatus.HEALTHY
            if not insights:
                insights.append(SystemStatusInsight(
                    message="All systems operational",
                    severity="info"
                ))

        return SystemStatus(
            status=status,
            insights=insights,
            failure_delta_percent=failure_delta_percent,
            failing_workflows_count=failing_workflows_count,
            last_failed_deployment=last_failed_deployment
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

        # Create provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(env)

        # Measure latency and test connection
        start_time = time.time()
        try:
            is_connected = await adapter.test_connection()
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
        time_range: TimeRange = TimeRange.TWENTY_FOUR_HOURS,
        environment_id: Optional[str] = None
    ) -> ObservabilityOverview:
        """Get complete observability overview with all sections"""
        import asyncio

        # Fetch all data in parallel for better performance
        kpi_task = self.get_kpi_metrics(tenant_id, time_range, environment_id=environment_id)
        workflow_task = self.get_workflow_performance(
            tenant_id, time_range, limit=20, sort_by="risk", environment_id=environment_id
        )
        env_health_task = self.get_environment_health(tenant_id)
        sync_stats_task = self.get_promotion_sync_stats(tenant_id)
        error_intel_task = self.get_error_intelligence(tenant_id, time_range, environment_id=environment_id)
        system_status_task = self.get_system_status(tenant_id, time_range, environment_id=environment_id)

        # Await all tasks
        results = await asyncio.gather(
            kpi_task,
            workflow_task,
            env_health_task,
            sync_stats_task,
            error_intel_task,
            system_status_task,
            return_exceptions=True
        )

        kpi_metrics = results[0] if not isinstance(results[0], Exception) else None
        workflow_performance = results[1] if not isinstance(results[1], Exception) else []
        environment_health = results[2] if not isinstance(results[2], Exception) else []
        promotion_sync_stats = results[3] if not isinstance(results[3], Exception) else None
        error_intelligence = results[4] if not isinstance(results[4], Exception) else None
        system_status = results[5] if not isinstance(results[5], Exception) else None

        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                task_names = ["kpi_metrics", "workflow_performance", "environment_health",
                              "promotion_sync_stats", "error_intelligence", "system_status"]
                logger.error(f"Failed to get {task_names[i]}: {result}")

        # Fallback for KPI metrics if failed
        if kpi_metrics is None:
            kpi_metrics = KPIMetrics(
                total_executions=0,
                success_count=0,
                failure_count=0,
                success_rate=0.0,
                avg_duration_ms=0.0
            )

        return ObservabilityOverview(
            system_status=system_status,
            kpi_metrics=kpi_metrics,
            error_intelligence=error_intelligence,
            workflow_performance=workflow_performance,
            environment_health=environment_health,
            promotion_sync_stats=promotion_sync_stats
        )


# Global instance
observability_service = ObservabilityService()
