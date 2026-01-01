"""Drift Compliance Reporting API endpoints."""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.services.auth_service import get_current_user
from app.services.database import db_service
from app.core.entitlements_gate import require_entitlement

router = APIRouter()


class ComplianceReportResponse(BaseModel):
    """Drift compliance report response."""
    period_start: str
    period_end: str
    total_incidents: int
    incidents_by_status: Dict[str, int]
    incidents_over_time: List[Dict[str, Any]]
    average_resolution_time_hours: float
    sla_compliance_percentage: float
    override_decisions: List[Dict[str, Any]]
    resolution_types: Dict[str, int]
    expired_incidents_count: int
    expired_incidents: List[Dict[str, Any]]


@router.get("/drift-compliance", response_model=ComplianceReportResponse)
async def get_drift_compliance_report(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    environment_id: Optional[str] = Query(None, description="Filter by environment"),
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("drift_policies")),
):
    """
    Get drift compliance report.
    
    Returns comprehensive compliance metrics including:
    - Incidents by status over time
    - Average resolution time
    - Override decisions audit
    - SLA compliance percentage
    - Resolution type distribution
    """
    tenant_id = user_info["tenant"]["id"]

    # Parse dates or use defaults (last 30 days)
    if end_date:
        period_end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    else:
        period_end = datetime.utcnow()

    if start_date:
        period_start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    else:
        period_start = period_end - timedelta(days=30)

    # Get all incidents in the period
    incidents_query = (
        db_service.client.table("drift_incidents")
        .select("*")
        .eq("tenant_id", tenant_id)
        .gte("created_at", period_start.isoformat())
        .lte("created_at", period_end.isoformat())
    )

    if environment_id:
        incidents_query = incidents_query.eq("environment_id", environment_id)

    incidents_response = incidents_query.execute()
    incidents = incidents_response.data or []

    # Calculate incidents by status
    incidents_by_status: Dict[str, int] = {}
    for incident in incidents:
        status = incident.get("status", "unknown")
        incidents_by_status[status] = incidents_by_status.get(status, 0) + 1

    # Calculate incidents over time (daily buckets)
    incidents_over_time: List[Dict[str, Any]] = []
    current_date = period_start
    while current_date <= period_end:
        day_start = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        day_incidents = [
            inc
            for inc in incidents
            if day_start.isoformat() <= inc.get("created_at", "") < day_end.isoformat()
        ]

        incidents_over_time.append({
            "date": day_start.isoformat(),
            "count": len(day_incidents),
            "by_status": {
                status: len([i for i in day_incidents if i.get("status") == status])
                for status in set(i.get("status") for i in day_incidents)
            },
        })

        current_date = day_start + timedelta(days=1)

    # Calculate average resolution time (for closed incidents)
    closed_incidents = [inc for inc in incidents if inc.get("status") == "closed"]
    resolution_times = []
    for incident in closed_incidents:
        detected_at = incident.get("detected_at")
        closed_at = incident.get("closed_at")
        if detected_at and closed_at:
            try:
                detected = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
                closed = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                hours = (closed - detected).total_seconds() / 3600
                resolution_times.append(hours)
            except (ValueError, TypeError):
                pass

    average_resolution_time = (
        sum(resolution_times) / len(resolution_times) if resolution_times else 0.0
    )

    # Get drift policy for SLA calculation
    policy_response = (
        db_service.client.table("drift_policies")
        .select("*")
        .eq("tenant_id", tenant_id)
        .execute()
    )

    policy = policy_response.data[0] if policy_response.data else None
    default_ttl_hours = policy.get("default_ttl_hours", 72) if policy else 72

    # Calculate SLA compliance (incidents closed within TTL)
    sla_compliant = 0
    sla_total = 0
    for incident in closed_incidents:
        detected_at = incident.get("detected_at")
        closed_at = incident.get("closed_at")
        expires_at = incident.get("expires_at")
        
        if detected_at and closed_at:
            try:
                detected = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))
                closed = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                
                # Use incident TTL if available, otherwise policy default
                if expires_at:
                    expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    ttl_hours = (expires - detected).total_seconds() / 3600
                else:
                    ttl_hours = default_ttl_hours
                
                resolution_hours = (closed - detected).total_seconds() / 3600
                sla_total += 1
                if resolution_hours <= ttl_hours:
                    sla_compliant += 1
            except (ValueError, TypeError):
                pass

    sla_compliance_percentage = (
        (sla_compliant / sla_total * 100) if sla_total > 0 else 0.0
    )

    # Get override decisions (from audit log or drift_overrides table if exists)
    override_decisions: List[Dict[str, Any]] = []
    try:
        # Check if drift_overrides table exists
        overrides_response = (
            db_service.client.table("drift_overrides")
            .select("*")
            .eq("tenant_id", tenant_id)
            .gte("created_at", period_start.isoformat())
            .lte("created_at", period_end.isoformat())
            .execute()
        )
        override_decisions = overrides_response.data or []
    except Exception:
        # Table doesn't exist, try audit log
        try:
            audit_response = (
                db_service.client.table("audit_logs")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("action_type", "drift_override")
                .gte("created_at", period_start.isoformat())
                .lte("created_at", period_end.isoformat())
                .execute()
            )
            override_decisions = audit_response.data or []
        except Exception:
            pass

    # Calculate resolution types
    resolution_types: Dict[str, int] = {}
    for incident in closed_incidents:
        resolution_type = incident.get("resolution_type")
        if resolution_type:
            resolution_types[resolution_type] = resolution_types.get(resolution_type, 0) + 1

    # Get expired incidents
    now = datetime.utcnow()
    expired_incidents = [
        inc
        for inc in incidents
        if inc.get("expires_at")
        and datetime.fromisoformat(inc.get("expires_at", "").replace('Z', '+00:00')) < now
        and inc.get("status") != "closed"
    ]

    return ComplianceReportResponse(
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        total_incidents=len(incidents),
        incidents_by_status=incidents_by_status,
        incidents_over_time=incidents_over_time,
        average_resolution_time_hours=round(average_resolution_time, 2),
        sla_compliance_percentage=round(sla_compliance_percentage, 2),
        override_decisions=override_decisions,
        resolution_types=resolution_types,
        expired_incidents_count=len(expired_incidents),
        expired_incidents=[
            {
                "id": inc.get("id"),
                "environment_id": inc.get("environment_id"),
                "title": inc.get("title"),
                "status": inc.get("status"),
                "expires_at": inc.get("expires_at"),
                "detected_at": inc.get("detected_at"),
            }
            for inc in expired_incidents
        ],
    )


@router.get("/drift-compliance/export")
async def export_drift_compliance_report(
    format: str = Query("csv", description="Export format: csv or json"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    environment_id: Optional[str] = Query(None, description="Filter by environment"),
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("drift_policies")),
):
    """
    Export drift compliance report.
    
    Supports CSV and JSON formats.
    """
    from fastapi.responses import Response

    tenant_id = user_info["tenant"]["id"]

    # Get report data
    report = await get_drift_compliance_report(
        start_date=start_date,
        end_date=end_date,
        environment_id=environment_id,
        user_info=user_info,
    )

    if format.lower() == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            "Period Start",
            "Period End",
            "Total Incidents",
            "Average Resolution Time (hours)",
            "SLA Compliance %",
            "Expired Incidents Count",
        ])

        # Write data
        writer.writerow([
            report.period_start,
            report.period_end,
            report.total_incidents,
            report.average_resolution_time_hours,
            report.sla_compliance_percentage,
            report.expired_incidents_count,
        ])

        # Write incidents by status
        writer.writerow([])
        writer.writerow(["Incidents by Status"])
        for status, count in report.incidents_by_status.items():
            writer.writerow([status, count])

        # Write resolution types
        writer.writerow([])
        writer.writerow(["Resolution Types"])
        for res_type, count in report.resolution_types.items():
            writer.writerow([res_type, count])

        csv_content = output.getvalue()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="drift-compliance-{datetime.utcnow().strftime("%Y%m%d")}.csv"'
            },
        )

    else:  # JSON
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content=report.model_dump(),
            headers={
                "Content-Disposition": f'attachment; filename="drift-compliance-{datetime.utcnow().strftime("%Y%m%d")}.json"'
            },
        )

