"""
Test script for retention job scheduler

This script can be run directly to test the retention job functionality
without starting the full application.

Usage:
    python -m app.services.background_jobs.test_retention_job
"""
import asyncio
import logging
from datetime import datetime

from app.services.background_jobs.retention_job import (
    trigger_retention_enforcement,
    get_retention_scheduler_status,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_retention_enforcement():
    """Test the retention enforcement job"""
    logger.info("=" * 80)
    logger.info("Testing Retention Enforcement Job")
    logger.info("=" * 80)

    # Test 1: Dry run to preview what would be deleted
    logger.info("\n--- Test 1: Dry Run (Preview Only) ---")
    dry_run_result = await trigger_retention_enforcement(dry_run=True)
    logger.info(f"Dry run completed:")
    logger.info(f"  - Would delete {dry_run_result['total_deleted']} total records")
    logger.info(f"  - Executions: {dry_run_result['total_executions_deleted']}")
    logger.info(f"  - Audit logs: {dry_run_result['total_audit_logs_deleted']}")
    logger.info(f"  - Tenants processed: {dry_run_result['tenants_processed']}")
    logger.info(f"  - Duration: {dry_run_result.get('duration_seconds', 0):.2f}s")

    # Test 2: Check scheduler status
    logger.info("\n--- Test 2: Check Scheduler Status ---")
    status = await get_retention_scheduler_status()
    logger.info(f"Scheduler status:")
    logger.info(f"  - Running: {status['running']}")
    logger.info(f"  - Next run time: {status['next_run_hour_utc']:02d}:{status['next_run_minute_utc']:02d} UTC")
    logger.info(f"  - Check interval: {status['check_interval_seconds']}s")

    # Test 3: Actual enforcement (commented out for safety)
    # Uncomment this to test actual deletion
    # logger.info("\n--- Test 3: Actual Enforcement ---")
    # actual_result = await trigger_retention_enforcement(dry_run=False)
    # logger.info(f"Enforcement completed:")
    # logger.info(f"  - Deleted {actual_result['total_deleted']} total records")
    # logger.info(f"  - Executions: {actual_result['total_executions_deleted']}")
    # logger.info(f"  - Audit logs: {actual_result['total_audit_logs_deleted']}")
    # logger.info(f"  - Tenants processed: {actual_result['tenants_processed']}")
    # logger.info(f"  - Duration: {actual_result.get('duration_seconds', 0):.2f}s")

    logger.info("\n" + "=" * 80)
    logger.info("Testing Complete")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_retention_enforcement())
