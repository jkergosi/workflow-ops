from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EnvironmentStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"


class DriftState(str, Enum):
    IN_SYNC = "in_sync"
    DRIFT = "drift"
    UNKNOWN = "unknown"


class SystemHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class TimeRange(str, Enum):
    ONE_HOUR = "1h"
    SIX_HOURS = "6h"
    TWENTY_FOUR_HOURS = "24h"
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"


# Health Check Models
class HealthCheckCreate(BaseModel):
    environment_id: str
    status: EnvironmentStatus
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None


class HealthCheckResponse(BaseModel):
    id: str
    tenant_id: str
    environment_id: str
    status: EnvironmentStatus
    latency_ms: Optional[int] = None
    checked_at: datetime
    error_message: Optional[str] = None


# System Status (Section 1 - Immediate Health Verdict)
class SystemStatusInsight(BaseModel):
    """Individual insight for system status"""
    message: str
    severity: str  # info, warning, critical
    link_type: Optional[str] = None  # workflow, deployment, error, etc.
    link_id: Optional[str] = None


class SystemStatus(BaseModel):
    """Overall system health verdict"""
    status: SystemHealthStatus
    insights: List[SystemStatusInsight]
    failure_delta_percent: Optional[float] = None
    failing_workflows_count: int = 0
    last_failed_deployment: Optional[str] = None


# KPI/Metrics Models with Sparklines
class SparklineDataPoint(BaseModel):
    """Single point for sparkline chart"""
    timestamp: datetime
    value: float


class KPIMetrics(BaseModel):
    total_executions: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_duration_ms: float
    p95_duration_ms: Optional[float] = None
    delta_executions: Optional[int] = None
    delta_success_rate: Optional[float] = None
    # Sparkline data for each KPI
    executions_sparkline: Optional[List[SparklineDataPoint]] = None
    success_rate_sparkline: Optional[List[SparklineDataPoint]] = None
    duration_sparkline: Optional[List[SparklineDataPoint]] = None
    failures_sparkline: Optional[List[SparklineDataPoint]] = None


# Error Intelligence (Section 3)
class ErrorGroup(BaseModel):
    """Grouped error for Error Intelligence section"""
    error_type: str
    count: int
    first_seen: datetime
    last_seen: datetime
    affected_workflow_count: int
    affected_workflow_ids: List[str]
    sample_message: Optional[str] = None
    is_classified: bool = True  # False if error type is a fallback, UI should show sample_message


class ErrorIntelligence(BaseModel):
    """Error Intelligence data for diagnostics"""
    errors: List[ErrorGroup]
    total_error_count: int


# Workflow Performance with Risk
class WorkflowPerformance(BaseModel):
    workflow_id: str
    workflow_name: str
    execution_count: int
    success_count: int
    failure_count: int
    error_rate: float
    avg_duration_ms: float
    p95_duration_ms: Optional[float] = None
    # New fields for Workflow Risk Table (Section 4)
    risk_score: Optional[float] = None  # failure_rate * volume
    last_failure_at: Optional[datetime] = None
    primary_error_type: Optional[str] = None


# Environment Health with Credential Status
class CredentialHealth(BaseModel):
    """Credential health status for an environment"""
    total_count: int
    valid_count: int
    invalid_count: int
    unknown_count: int


class EnvironmentHealth(BaseModel):
    environment_id: str
    environment_name: str
    environment_type: Optional[str] = None
    status: EnvironmentStatus
    latency_ms: Optional[int] = None
    uptime_percent: float
    active_workflows: int
    total_workflows: int
    last_deployment_at: Optional[datetime] = None
    last_deployment_status: Optional[str] = None  # success, failed
    last_snapshot_at: Optional[datetime] = None
    drift_state: DriftState
    drift_workflow_count: int = 0  # Number of workflows with drift
    last_checked_at: Optional[datetime] = None
    # New: credential health (Section 5)
    credential_health: Optional[CredentialHealth] = None
    api_reachable: bool = True


# Recent Deployment with Impact
class ImpactedWorkflow(BaseModel):
    """Workflow impacted by a deployment"""
    workflow_id: str
    workflow_name: str
    change_type: str  # created, updated, failed


class RecentDeployment(BaseModel):
    id: str
    pipeline_name: Optional[str] = None
    source_environment_name: str
    target_environment_name: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    # New: impacted workflows for failed deployments (Section 6b)
    impacted_workflows: Optional[List[ImpactedWorkflow]] = None


class PromotionSyncStats(BaseModel):
    promotions_total: int
    promotions_success: int
    promotions_failed: int
    promotions_blocked: int
    snapshots_created: int
    snapshots_restored: int
    drift_count: int
    recent_deployments: List[RecentDeployment]


class ObservabilityOverview(BaseModel):
    # Section 1: System Status
    system_status: Optional[SystemStatus] = None
    # Section 2: KPI Metrics with sparklines
    kpi_metrics: KPIMetrics
    # Section 3: Error Intelligence
    error_intelligence: Optional[ErrorIntelligence] = None
    # Section 4: Workflow Performance (Risk Table)
    workflow_performance: List[WorkflowPerformance]
    # Section 5: Environment Health
    environment_health: List[EnvironmentHealth]
    # Section 6: Promotion & Sync Stats
    promotion_sync_stats: Optional[PromotionSyncStats] = None
