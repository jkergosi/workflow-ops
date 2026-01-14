"""
Drift Detection Scheduler Service

Periodically runs drift detection for environments with Git configured,
checks for TTL expirations, and handles automated incident creation.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from app.services.database import db_service
from app.services.drift_detection_service import drift_detection_service, DriftStatus
from app.services.feature_service import feature_service
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# Global flags to control schedulers
_drift_scheduler_running = False
_drift_scheduler_task: Optional[asyncio.Task] = None
_ttl_checker_running = False
_ttl_checker_task: Optional[asyncio.Task] = None
_retention_cleanup_running = False
_retention_cleanup_task: Optional[asyncio.Task] = None

# Configuration
DRIFT_CHECK_INTERVAL_SECONDS = 300  # 5 minutes
TTL_CHECK_INTERVAL_SECONDS = 60  # 1 minute
RETENTION_CLEANUP_INTERVAL_SECONDS = 86400  # 24 hours (daily)


async def _get_environments_for_drift_check() -> List[Dict[str, Any]]:
    """
    Get all non-DEV environments that have Git configured and belong to tenants
    with drift detection enabled.

    DEV environments are excluded because n8n is the source of truth for DEV,
    so there's no concept of "drift" - changes in n8n ARE the canonical state.
    """
    try:
        # Get environments with Git configured, excluding DEV environments
        # DEV environments use n8n as source of truth, so drift detection doesn't apply
        response = db_service.client.table("environments").select(
            "id, tenant_id, n8n_name, git_repo_url, git_pat, n8n_type, environment_class"
        ).not_.is_("git_repo_url", "null").not_.is_("git_pat", "null").neq(
            "environment_class", "dev"
        ).execute()

        environments = response.data or []

        # Filter to environments where tenant has drift_detection feature
        eligible = []
        for env in environments:
            tenant_id = env.get("tenant_id")
            if not tenant_id:
                continue

            can_use, _ = await feature_service.can_use_feature(tenant_id, "drift_detection")
            if can_use:
                eligible.append(env)

        return eligible

    except Exception as e:
        logger.error(f"Failed to get environments for drift check: {e}")
        return []


async def _process_drift_detection():
    """
    Periodically run drift detection for all eligible environments.
    Runs every 5 minutes.
    """
    global _drift_scheduler_running

    while _drift_scheduler_running:
        try:
            logger.debug("Running scheduled drift detection...")

            environments = await _get_environments_for_drift_check()

            if environments:
                logger.info(f"Checking drift for {len(environments)} environment(s)")

            for env in environments:
                env_id = env.get("id")
                tenant_id = env.get("tenant_id")
                env_name = env.get("n8n_name", "Unknown")

                try:
                    # Run drift detection
                    summary = await drift_detection_service.detect_drift(
                        tenant_id=tenant_id,
                        environment_id=env_id,
                        update_status=True
                    )

                    # Check if drift was detected and auto-incident creation is enabled
                    if summary.with_drift > 0 or summary.not_in_git > 0:
                        await _handle_drift_detected(
                            tenant_id=tenant_id,
                            environment_id=env_id,
                            environment_name=env_name,
                            summary=summary.to_dict()
                        )

                except Exception as e:
                    logger.error(f"Drift detection failed for environment {env_id}: {e}")

            # Wait before next check
            await asyncio.sleep(DRIFT_CHECK_INTERVAL_SECONDS)

        except Exception as e:
            logger.error(f"Error in drift scheduler: {e}", exc_info=True)
            await asyncio.sleep(DRIFT_CHECK_INTERVAL_SECONDS)


async def _handle_drift_detected(
    tenant_id: str,
    environment_id: str,
    environment_name: str,
    summary: Dict[str, Any]
) -> None:
    """
    Handle detected drift - create incident if needed, send notifications.
    """
    try:
        # Check if tenant has drift_incidents feature
        can_use_incidents, _ = await feature_service.can_use_feature(
            tenant_id, "drift_incidents"
        )

        if not can_use_incidents:
            return

        # Check if there's already an active incident for this environment
        active_incident = await _get_active_incident(tenant_id, environment_id)

        if active_incident:
            # Update existing incident with new affected workflows
            logger.debug(
                f"Active incident {active_incident['id']} exists for environment {environment_id}"
            )
            return

        # Check drift policy for auto-incident creation
        policy = await _get_drift_policy(tenant_id)

        if not policy:
            # No policy - don't auto-create incidents
            return

        if not policy.get("auto_create_incidents", False):
            return

        # Check if this is a production environment when auto_create_for_production_only
        if policy.get("auto_create_for_production_only", True):
            env_response = db_service.client.table("environments").select(
                "n8n_type"
            ).eq("id", environment_id).single().execute()

            if env_response.data:
                env_type = env_response.data.get("n8n_type", "").lower()
                if env_type not in ["production", "prod"]:
                    logger.debug(
                        f"Skipping auto-incident for non-production environment: {env_type}"
                    )
                    return

        # Create drift incident
        await _create_drift_incident(
            tenant_id=tenant_id,
            environment_id=environment_id,
            environment_name=environment_name,
            summary=summary,
            policy=policy
        )

    except Exception as e:
        logger.error(f"Failed to handle drift detection for environment {environment_id}: {e}")


async def _get_active_incident(tenant_id: str, environment_id: str) -> Optional[Dict[str, Any]]:
    """Get active drift incident for an environment."""
    try:
        response = db_service.client.table("drift_incidents").select(
            "*"
        ).eq("tenant_id", tenant_id).eq("environment_id", environment_id).in_(
            "status", ["detected", "acknowledged", "stabilized"]
        ).order("created_at", desc=True).limit(1).execute()

        return response.data[0] if response.data else None

    except Exception:
        return None


async def _get_drift_policy(tenant_id: str) -> Optional[Dict[str, Any]]:
    """Get drift policy for a tenant."""
    try:
        response = db_service.client.table("drift_policies").select(
            "*"
        ).eq("tenant_id", tenant_id).single().execute()

        return response.data

    except Exception:
        return None


async def _create_drift_incident(
    tenant_id: str,
    environment_id: str,
    environment_name: str,
    summary: Dict[str, Any],
    policy: Dict[str, Any]
) -> None:
    """Auto-create a drift incident."""
    now = datetime.utcnow()
    now_iso = now.isoformat()

    # Determine severity based on affected workflows
    with_drift = summary.get("withDrift", 0)
    not_in_git = summary.get("notInGit", 0)
    total_affected = with_drift + not_in_git

    if total_affected >= 10:
        severity = "critical"
    elif total_affected >= 5:
        severity = "high"
    elif total_affected >= 2:
        severity = "medium"
    else:
        severity = "low"

    # Calculate TTL based on severity
    ttl_hours_map = {
        "critical": policy.get("critical_ttl_hours", 24),
        "high": policy.get("high_ttl_hours", 48),
        "medium": policy.get("medium_ttl_hours", 72),
        "low": policy.get("low_ttl_hours", 168)
    }
    ttl_hours = ttl_hours_map.get(severity, policy.get("default_ttl_hours", 72))
    expires_at = now + timedelta(hours=ttl_hours)

    # Build affected workflows list
    affected_workflows = []
    for wf in summary.get("affectedWorkflows", []):
        drift_type = wf.get("driftType", "unknown")
        if wf.get("notInGit"):
            drift_type = "missing_in_git"
        elif wf.get("hasDrift"):
            drift_type = "modified"

        affected_workflows.append({
            "workflow_id": wf.get("id"),
            "workflow_name": wf.get("name"),
            "drift_type": drift_type,
            "change_summary": f"{wf.get('summary', {}).get('nodesModified', 0)} nodes modified"
            if wf.get("summary") else None
        })

    incident_data = {
        "tenant_id": tenant_id,
        "environment_id": environment_id,
        "status": "detected",
        "title": f"Drift detected in {environment_name}",
        "summary": {
            "totalWorkflows": summary.get("totalWorkflows", 0),
            "withDrift": with_drift,
            "notInGit": not_in_git,
            "inSync": summary.get("inSync", 0)
        },
        "severity": severity,
        "expires_at": expires_at.isoformat(),
        "detected_at": now_iso,
        "affected_workflows": affected_workflows,
        "drift_snapshot": summary,
        "created_at": now_iso,
        "updated_at": now_iso
    }

    try:
        response = db_service.client.table("drift_incidents").insert(
            incident_data
        ).execute()

        if response.data:
            incident_id = response.data[0]["id"]
            logger.info(
                f"Auto-created drift incident {incident_id} for environment {environment_id} "
                f"(severity: {severity}, affected: {total_affected})"
            )

            # Update environment with active incident
            db_service.client.table("environments").update({
                "active_drift_incident_id": incident_id
            }).eq("id", environment_id).execute()

            # Send notification if enabled
            if policy.get("notify_on_detection", True):
                await notification_service.emit_event(
                    tenant_id=tenant_id,
                    event_type="drift.detected",
                    environment_id=environment_id,
                    metadata={
                        "incident_id": incident_id,
                        "severity": severity,
                        "affected_count": total_affected,
                        "environment_name": environment_name
                    }
                )

    except Exception as e:
        logger.error(f"Failed to create drift incident: {e}")


async def _process_ttl_checks():
    """
    Periodically check for TTL expirations and warnings.
    Runs every minute.
    """
    global _ttl_checker_running

    while _ttl_checker_running:
        try:
            logger.debug("Running TTL expiration check...")

            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            # Get all active incidents with TTL that haven't expired yet
            response = db_service.client.table("drift_incidents").select(
                "id, tenant_id, environment_id, severity, expires_at, status"
            ).in_(
                "status", ["detected", "acknowledged", "stabilized"]
            ).not_.is_("expires_at", "null").execute()

            incidents = response.data or []

            for incident in incidents:
                incident_id = incident.get("id")
                tenant_id = incident.get("tenant_id")
                environment_id = incident.get("environment_id")
                expires_at_str = incident.get("expires_at")

                if not expires_at_str:
                    continue

                try:
                    expires_at = datetime.fromisoformat(
                        expires_at_str.replace('Z', '+00:00')
                    )
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)

                    # Check if expired
                    if now >= expires_at:
                        await _handle_ttl_expired(incident)
                        continue

                    # Check for warning
                    policy = await _get_drift_policy(tenant_id)
                    if policy and policy.get("notify_on_expiration_warning", True):
                        warning_hours = policy.get("expiration_warning_hours", 24)
                        warning_time = expires_at - timedelta(hours=warning_hours)

                        if now >= warning_time:
                            await _send_expiration_warning(incident, policy)

                except Exception as e:
                    logger.error(f"TTL check failed for incident {incident_id}: {e}")

            # Wait before next check
            await asyncio.sleep(TTL_CHECK_INTERVAL_SECONDS)

        except Exception as e:
            logger.error(f"Error in TTL checker: {e}", exc_info=True)
            await asyncio.sleep(TTL_CHECK_INTERVAL_SECONDS)


async def _handle_ttl_expired(incident: Dict[str, Any]) -> None:
    """Handle an expired TTL incident."""
    incident_id = incident.get("id")
    tenant_id = incident.get("tenant_id")
    environment_id = incident.get("environment_id")

    try:
        # Update incident status to indicate expiration
        now_iso = datetime.utcnow().isoformat()

        db_service.client.table("drift_incidents").update({
            "status": "closed",
            "closed_at": now_iso,
            "reason": "TTL expired - auto-closed",
            "updated_at": now_iso
        }).eq("id", incident_id).execute()

        # Clear active incident from environment
        db_service.client.table("environments").update({
            "active_drift_incident_id": None
        }).eq("id", environment_id).execute()

        logger.info(f"Auto-closed expired incident {incident_id}")

        # Notify
        await notification_service.emit_event(
            tenant_id=tenant_id,
            event_type="drift.ttl_expired",
            environment_id=environment_id,
            metadata={
                "incident_id": incident_id,
                "severity": incident.get("severity")
            }
        )

    except Exception as e:
        logger.error(f"Failed to handle expired TTL for incident {incident_id}: {e}")


async def _send_expiration_warning(
    incident: Dict[str, Any],
    policy: Dict[str, Any]
) -> None:
    """Send a warning notification about impending TTL expiration."""
    incident_id = incident.get("id")
    tenant_id = incident.get("tenant_id")
    environment_id = incident.get("environment_id")

    # Check if we've already sent a warning (use a flag in incident)
    try:
        # Get full incident to check warning_sent flag
        full_incident = db_service.client.table("drift_incidents").select(
            "expiration_warning_sent"
        ).eq("id", incident_id).single().execute()

        if full_incident.data and full_incident.data.get("expiration_warning_sent"):
            return  # Already sent

        # Mark warning as sent
        db_service.client.table("drift_incidents").update({
            "expiration_warning_sent": True,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", incident_id).execute()

        # Send notification
        await notification_service.emit_event(
            tenant_id=tenant_id,
            event_type="drift.ttl_warning",
            environment_id=environment_id,
            metadata={
                "incident_id": incident_id,
                "severity": incident.get("severity"),
                "expires_at": incident.get("expires_at"),
                "warning_hours": policy.get("expiration_warning_hours", 24)
            }
        )

        logger.info(f"Sent TTL expiration warning for incident {incident_id}")

    except Exception as e:
        logger.error(f"Failed to send expiration warning for incident {incident_id}: {e}")


async def start_drift_scheduler():
    """Start the drift detection scheduler background task."""
    global _drift_scheduler_running, _drift_scheduler_task

    if _drift_scheduler_running:
        logger.warning("Drift scheduler is already running")
        return

    _drift_scheduler_running = True
    _drift_scheduler_task = asyncio.create_task(_process_drift_detection())
    logger.info("Drift detection scheduler started")


async def stop_drift_scheduler():
    """Stop the drift detection scheduler background task."""
    global _drift_scheduler_running, _drift_scheduler_task

    if not _drift_scheduler_running:
        return

    _drift_scheduler_running = False
    if _drift_scheduler_task:
        _drift_scheduler_task.cancel()
        try:
            await _drift_scheduler_task
        except asyncio.CancelledError:
            pass
    logger.info("Drift detection scheduler stopped")


async def start_ttl_checker():
    """Start the TTL checker background task."""
    global _ttl_checker_running, _ttl_checker_task

    if _ttl_checker_running:
        logger.warning("TTL checker is already running")
        return

    _ttl_checker_running = True
    _ttl_checker_task = asyncio.create_task(_process_ttl_checks())
    logger.info("TTL expiration checker started")


async def stop_ttl_checker():
    """Stop the TTL checker background task."""
    global _ttl_checker_running, _ttl_checker_task

    if not _ttl_checker_running:
        return

    _ttl_checker_running = False
    if _ttl_checker_task:
        _ttl_checker_task.cancel()
        try:
            await _ttl_checker_task
        except asyncio.CancelledError:
            pass
    logger.info("TTL expiration checker stopped")


async def _process_retention_cleanup():
    """
    Periodically run retention cleanup for all tenants.
    Runs daily.
    """
    global _retention_cleanup_running

    while _retention_cleanup_running:
        try:
            logger.debug("Running retention cleanup...")
            from app.services.drift_retention_service import drift_retention_service

            results = await drift_retention_service.cleanup_all_tenants()

            if results.get("tenants_with_deletions", 0) > 0:
                logger.info(
                    f"Retention cleanup completed: {results['closed_incidents_deleted']} incidents, "
                    f"{results['reconciliation_artifacts_deleted']} artifacts, "
                    f"{results['approvals_deleted']} approvals deleted"
                )

            # Wait before next check (daily)
            await asyncio.sleep(RETENTION_CLEANUP_INTERVAL_SECONDS)

        except Exception as e:
            logger.error(f"Error in retention cleanup scheduler: {e}", exc_info=True)
            await asyncio.sleep(RETENTION_CLEANUP_INTERVAL_SECONDS)


async def start_retention_cleanup():
    """Start the retention cleanup scheduler background task."""
    global _retention_cleanup_running, _retention_cleanup_task

    if _retention_cleanup_running:
        logger.warning("Retention cleanup scheduler is already running")
        return

    _retention_cleanup_running = True
    _retention_cleanup_task = asyncio.create_task(_process_retention_cleanup())
    logger.info("Retention cleanup scheduler started")


async def stop_retention_cleanup():
    """Stop the retention cleanup scheduler background task."""
    global _retention_cleanup_running, _retention_cleanup_task

    if not _retention_cleanup_running:
        return

    _retention_cleanup_running = False
    if _retention_cleanup_task:
        _retention_cleanup_task.cancel()
        try:
            await _retention_cleanup_task
        except asyncio.CancelledError:
            pass
    logger.info("Retention cleanup scheduler stopped")


async def start_all_drift_schedulers():
    """Start all drift-related schedulers."""
    await start_drift_scheduler()
    await start_ttl_checker()
    await start_retention_cleanup()


async def stop_all_drift_schedulers():
    """Stop all drift-related schedulers."""
    await stop_drift_scheduler()
    await stop_ttl_checker()
    await stop_retention_cleanup()
