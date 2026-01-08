"""Scheduler for downgrade enforcement and over-limit detection."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.services.downgrade_service import downgrade_service
from app.core.config import settings

logger = logging.getLogger(__name__)

_scheduler_running = False
_scheduler_task: Optional[asyncio.Task] = None

CHECK_INTERVAL_SECONDS = getattr(settings, "DOWNGRADE_ENFORCEMENT_INTERVAL_SECONDS", 3600)


async def _run_enforcement_cycle() -> Dict[str, Any]:
    expired_summary = await downgrade_service.enforce_expired_grace_periods()
    overlimit_summary = await downgrade_service.detect_overlimit_all_tenants()

    return {
        "expired_summary": expired_summary,
        "overlimit_summary": overlimit_summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _scheduler_loop() -> None:
    global _scheduler_running
    logger.info(
        "Downgrade enforcement scheduler started (interval=%ss)",
        CHECK_INTERVAL_SECONDS,
    )

    while _scheduler_running:
        try:
            result = await _run_enforcement_cycle()
            expired = result["expired_summary"]
            overlimit = result["overlimit_summary"]
            logger.info(
                "Downgrade enforcement cycle complete: enforced=%s created_grace=%s errors=%s",
                expired.get("enforced_count", 0),
                overlimit.get("grace_periods_created", 0),
                len((expired.get("errors") or [])) + len((overlimit.get("errors") or [])),
            )
        except Exception as e:
            logger.error("Error in downgrade enforcement cycle: %s", e, exc_info=True)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    logger.info("Downgrade enforcement scheduler stopped")


def start_downgrade_enforcement_scheduler() -> None:
    global _scheduler_running, _scheduler_task
    if _scheduler_running:
        logger.warning("Downgrade enforcement scheduler already running")
        return

    _scheduler_running = True
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Downgrade enforcement scheduler task created and started")


async def stop_downgrade_enforcement_scheduler() -> None:
    global _scheduler_running, _scheduler_task
    if not _scheduler_running:
        return

    _scheduler_running = False
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass

    _scheduler_task = None
    logger.info("Downgrade enforcement scheduler stopped")


async def get_downgrade_scheduler_status() -> Dict[str, Any]:
    return {
        "running": _scheduler_running,
        "interval_seconds": CHECK_INTERVAL_SECONDS,
        "task_created": _scheduler_task is not None,
    }

