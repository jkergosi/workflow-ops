"""
Retention Job Scheduler

Scheduled background job to enforce plan-based retention policies
for executions and audit logs across all tenants.

This scheduler runs periodically (default: daily at 2 AM UTC) to clean up
old data based on each tenant's subscription plan retention limits.

Key Features:
- Automated daily enforcement of retention policies
- Configurable schedule and batch sizes
- Comprehensive logging and metrics
- Graceful startup and shutdown
- Integration with retention enforcement service

Related Components:
- T009: Retention enforcement service (core logic)
- T010: Execution retention enforcement
- T011: Audit log retention enforcement
- T012: Scheduled retention job (THIS FILE)

Usage:
    # Start the scheduler (called in main.py on startup)
    start_retention_scheduler()

    # Stop the scheduler (called in main.py on shutdown)
    stop_retention_scheduler()

    # Manually trigger retention enforcement
    await trigger_retention_enforcement(dry_run=False)
"""
import asyncio
import logging
from datetime import datetime, timezone, time
from typing import Optional, Dict, Any

from app.services.retention_enforcement_service import retention_enforcement_service
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global flags to control scheduler
_retention_scheduler_running = False
_retention_scheduler_task: Optional[asyncio.Task] = None

# Configuration
RETENTION_CHECK_INTERVAL_SECONDS = 3600  # Check every hour if retention job should run
RETENTION_JOB_HOUR_UTC = 2  # Run retention job at 2 AM UTC daily (off-peak hours)
RETENTION_JOB_MINUTE_UTC = 0  # At the start of the hour


async def trigger_retention_enforcement(dry_run: bool = False) -> Dict[str, Any]:
    """
    Manually trigger retention enforcement for all tenants.

    This function can be called manually to trigger retention enforcement
    outside of the normal schedule (e.g., for testing or admin operations).

    Args:
        dry_run: If True, only preview what would be deleted without actually deleting

    Returns:
        Dictionary containing enforcement summary with metrics

    Example:
        summary = await trigger_retention_enforcement(dry_run=True)
        print(f"Would delete {summary['total_deleted']} records")
    """
    logger.info(f"Manually triggering retention enforcement (dry_run={dry_run})")

    try:
        summary = await retention_enforcement_service.enforce_all_tenants_retention(dry_run=dry_run)

        logger.info(
            f"Retention enforcement completed: "
            f"deleted {summary['total_deleted']} records "
            f"({summary['total_executions_deleted']} executions, "
            f"{summary['total_audit_logs_deleted']} audit logs) "
            f"across {summary['tenants_processed']} tenants "
            f"in {summary['duration_seconds']:.2f}s (dry_run={dry_run})"
        )

        return summary

    except Exception as e:
        logger.error(f"Error during manual retention enforcement: {e}", exc_info=True)
        return {
            "total_deleted": 0,
            "total_executions_deleted": 0,
            "total_audit_logs_deleted": 0,
            "tenants_processed": 0,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
        }


async def _run_scheduled_retention_job():
    """
    Run the scheduled retention enforcement job.

    This is the main job that runs on schedule to enforce retention policies.
    It's called by the scheduler loop when it's time to run the job.
    """
    logger.info("Starting scheduled retention enforcement job")

    try:
        # Run retention enforcement for all tenants
        summary = await retention_enforcement_service.enforce_all_tenants_retention(dry_run=False)

        # Log detailed results
        logger.info(
            f"Scheduled retention job completed successfully:\n"
            f"  - Total deleted: {summary['total_deleted']} records\n"
            f"  - Executions deleted: {summary['total_executions_deleted']}\n"
            f"  - Audit logs deleted: {summary['total_audit_logs_deleted']}\n"
            f"  - Tenants processed: {summary['tenants_processed']}\n"
            f"  - Tenants with deletions: {summary['tenants_with_deletions']}\n"
            f"  - Tenants skipped: {summary['tenants_skipped']}\n"
            f"  - Errors: {len(summary.get('errors', []))}\n"
            f"  - Duration: {summary['duration_seconds']:.2f}s"
        )

        # Log any errors
        if summary.get('errors'):
            logger.warning(
                f"Retention job completed with {len(summary['errors'])} errors. "
                f"Failed tenant IDs: {', '.join(summary['errors'])}"
            )

        return summary

    except Exception as e:
        logger.error(f"Error during scheduled retention job: {e}", exc_info=True)
        return {
            "total_deleted": 0,
            "total_executions_deleted": 0,
            "total_audit_logs_deleted": 0,
            "tenants_processed": 0,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def _should_run_retention_job(last_run_date: Optional[datetime]) -> bool:
    """
    Check if it's time to run the retention job.

    The job runs once per day at the configured hour (default 2 AM UTC).
    This function checks if:
    1. The current time matches the scheduled hour
    2. The job hasn't already run today

    Args:
        last_run_date: Datetime when the job last ran (None if never run)

    Returns:
        True if the job should run now, False otherwise
    """
    now = datetime.now(timezone.utc)

    # Check if we're at the scheduled hour
    current_hour = now.hour
    if current_hour != RETENTION_JOB_HOUR_UTC:
        return False

    # Check if we haven't run today yet
    if last_run_date is None:
        logger.info("Retention job has never run - scheduling first run")
        return True

    # Check if last run was on a different day
    last_run_date_utc = last_run_date.astimezone(timezone.utc)
    if last_run_date_utc.date() < now.date():
        logger.info(
            f"Retention job last ran on {last_run_date_utc.date()}, "
            f"current date is {now.date()} - scheduling run"
        )
        return True

    return False


async def _retention_scheduler_loop():
    """
    Main scheduler loop that runs periodically.

    This loop checks every hour if it's time to run the retention job.
    When the scheduled time is reached, it triggers the retention enforcement.
    """
    global _retention_scheduler_running

    logger.info(
        f"Retention scheduler started - will run daily at "
        f"{RETENTION_JOB_HOUR_UTC:02d}:{RETENTION_JOB_MINUTE_UTC:02d} UTC"
    )

    last_run_date: Optional[datetime] = None

    # Optional: Run immediately on startup if configured
    run_on_startup = getattr(settings, 'RETENTION_JOB_RUN_ON_STARTUP', False)
    if run_on_startup:
        logger.info("Running retention job on startup (RETENTION_JOB_RUN_ON_STARTUP=True)")
        try:
            await _run_scheduled_retention_job()
            last_run_date = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Error running retention job on startup: {e}", exc_info=True)

    while _retention_scheduler_running:
        try:
            # Check if it's time to run the job
            if await _should_run_retention_job(last_run_date):
                logger.info("Triggering scheduled retention job")

                try:
                    await _run_scheduled_retention_job()
                    last_run_date = datetime.now(timezone.utc)

                except Exception as e:
                    logger.error(f"Error running scheduled retention job: {e}", exc_info=True)
                    # Continue running the scheduler even if one job fails

        except Exception as e:
            logger.error(f"Error in retention scheduler loop: {e}", exc_info=True)

        # Wait for next interval before checking again
        await asyncio.sleep(RETENTION_CHECK_INTERVAL_SECONDS)

    logger.info("Retention scheduler stopped")


def start_retention_scheduler():
    """
    Start the retention scheduler.

    This function should be called during application startup (in main.py).
    It creates an asyncio task that runs the scheduler loop in the background.

    Example:
        # In main.py startup event
        from app.services.background_jobs.retention_job import start_retention_scheduler
        start_retention_scheduler()
    """
    global _retention_scheduler_running, _retention_scheduler_task

    if _retention_scheduler_running:
        logger.warning("Retention scheduler already running")
        return

    _retention_scheduler_running = True
    _retention_scheduler_task = asyncio.create_task(_retention_scheduler_loop())
    logger.info("Retention scheduler task created and started")


async def stop_retention_scheduler():
    """
    Stop the retention scheduler.

    This function should be called during application shutdown (in main.py).
    It gracefully stops the scheduler loop and cancels the background task.

    Example:
        # In main.py shutdown event
        from app.services.background_jobs.retention_job import stop_retention_scheduler
        await stop_retention_scheduler()
    """
    global _retention_scheduler_running, _retention_scheduler_task

    if not _retention_scheduler_running:
        logger.info("Retention scheduler not running")
        return

    logger.info("Stopping retention scheduler...")
    _retention_scheduler_running = False

    if _retention_scheduler_task:
        _retention_scheduler_task.cancel()
        try:
            await _retention_scheduler_task
        except asyncio.CancelledError:
            logger.info("Retention scheduler task cancelled successfully")
        _retention_scheduler_task = None

    logger.info("Retention scheduler stopped")


async def get_retention_scheduler_status() -> Dict[str, Any]:
    """
    Get the current status of the retention scheduler.

    Returns:
        Dictionary containing:
        - running: bool - Whether the scheduler is running
        - next_run_hour_utc: int - The hour when the job will run
        - check_interval_seconds: int - How often the scheduler checks

    Example:
        status = await get_retention_scheduler_status()
        print(f"Scheduler running: {status['running']}")
    """
    return {
        "running": _retention_scheduler_running,
        "next_run_hour_utc": RETENTION_JOB_HOUR_UTC,
        "next_run_minute_utc": RETENTION_JOB_MINUTE_UTC,
        "check_interval_seconds": RETENTION_CHECK_INTERVAL_SECONDS,
        "task_exists": _retention_scheduler_task is not None,
    }
