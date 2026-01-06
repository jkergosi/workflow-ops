"""
Health Check Scheduler Service

Periodically runs health checks for all active environments to update
last_heartbeat_at timestamps.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.services.database import db_service
from app.services.observability_service import observability_service

logger = logging.getLogger(__name__)

# Global flags to control scheduler
_health_check_scheduler_running = False
_health_check_scheduler_task: Optional[asyncio.Task] = None

# Configuration
HEALTH_CHECK_INTERVAL_SECONDS = 60  # 1 minute


async def _process_health_checks():
    """
    Periodically run health checks for all active environments.
    Runs every 1 minute.
    """
    global _health_check_scheduler_running

    while _health_check_scheduler_running:
        try:
            logger.debug("Running scheduled health checks...")

            # Get all active environments
            response = db_service.client.table("environments").select(
                "id, tenant_id, n8n_name, n8n_base_url, is_active"
            ).eq("is_active", True).execute()

            environments = response.data or []

            if environments:
                logger.debug(f"Checking health for {len(environments)} environment(s)")

            for env in environments:
                env_id = env.get("id")
                tenant_id = env.get("tenant_id")
                env_name = env.get("n8n_name", "Unknown")
                base_url = env.get("n8n_base_url", "")

                if not env_id or not tenant_id:
                    continue

                try:
                    logger.debug(
                        f"Health check: env_id={env_id}, tenant_id={tenant_id}, "
                        f"name={env_name}, url={base_url}"
                    )
                    
                    # Run health check (this updates last_heartbeat_at on success)
                    result = await observability_service.check_environment_health(
                        tenant_id=tenant_id,
                        environment_id=env_id
                    )
                    
                    logger.info(
                        f"Health check completed: env_id={env_id}, status={result.status.value}, "
                        f"latency_ms={result.latency_ms}, timestamp={datetime.utcnow().isoformat()}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Health check failed for environment {env_id} ({env_name}): {str(e)}"
                    )

            # Wait before next cycle
            await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)

        except Exception as e:
            logger.error(f"Error in health check scheduler: {str(e)}")
            await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)


async def start_health_check_scheduler():
    """Start the health check scheduler"""
    global _health_check_scheduler_running, _health_check_scheduler_task

    if _health_check_scheduler_running:
        logger.warning("Health check scheduler is already running")
        return

    _health_check_scheduler_running = True
    _health_check_scheduler_task = asyncio.create_task(_process_health_checks())
    logger.info("Health check scheduler started (interval: 60s)")


async def stop_health_check_scheduler():
    """Stop the health check scheduler"""
    global _health_check_scheduler_running, _health_check_scheduler_task

    if not _health_check_scheduler_running:
        return

    _health_check_scheduler_running = False

    if _health_check_scheduler_task:
        _health_check_scheduler_task.cancel()
        try:
            await _health_check_scheduler_task
        except asyncio.CancelledError:
            pass
        _health_check_scheduler_task = None

    logger.info("Health check scheduler stopped")

