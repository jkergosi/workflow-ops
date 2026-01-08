"""
Rollup Scheduler Service

Computes daily execution rollups for faster dashboard performance.
Runs once per day to pre-compute analytics data.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.services.database import db_service

logger = logging.getLogger(__name__)

# Global flags to control scheduler
_rollup_scheduler_running = False
_rollup_scheduler_task: Optional[asyncio.Task] = None

# Configuration
ROLLUP_INTERVAL_SECONDS = 3600  # 1 hour - check if rollups needed
ROLLUP_DAYS_TO_BACKFILL = 7  # On startup, ensure last 7 days are computed


async def _compute_rollups_for_date(rollup_date: datetime) -> int:
    """
    Compute rollups for a specific date using database function.
    
    Returns:
        Number of rows inserted/updated
    """
    try:
        date_str = rollup_date.strftime('%Y-%m-%d')
        
        # Call database function to compute rollups
        response = db_service.client.rpc(
            'compute_execution_rollup_for_date',
            {'p_rollup_date': date_str}
        ).execute()
        
        rows_affected = response.data if isinstance(response.data, int) else 0
        logger.info(f"Computed rollups for {date_str}: {rows_affected} rows")
        return rows_affected
        
    except Exception as e:
        logger.warning(f"Failed to compute rollups for {rollup_date}: {e}")
        return 0


async def _refresh_materialized_views():
    """
    Refresh all materialized views for dashboard performance.
    """
    try:
        response = db_service.client.rpc('refresh_all_materialized_views').execute()
        results = response.data or []
        for result in results:
            logger.info(f"Refreshed {result.get('view_name')} in {result.get('refresh_time')}")
        return True
    except Exception as e:
        logger.warning(f"Failed to refresh materialized views: {e}")
        return False


async def _check_and_compute_rollups():
    """
    Check which dates need rollup computation and compute them.
    Also refreshes materialized views.
    """
    try:
        now = datetime.now(timezone.utc)
        today = now.date()
        
        # Compute yesterday's rollups (most important - day is complete)
        yesterday = today - timedelta(days=1)
        await _compute_rollups_for_date(datetime.combine(yesterday, datetime.min.time()))
        
        # Refresh materialized views (hourly)
        await _refresh_materialized_views()
        
        # During off-peak hours (2-6 AM UTC), backfill older dates
        if 2 <= now.hour <= 6:
            for days_ago in range(2, ROLLUP_DAYS_TO_BACKFILL + 1):
                target_date = today - timedelta(days=days_ago)
                await _compute_rollups_for_date(datetime.combine(target_date, datetime.min.time()))
                # Small delay between computations
                await asyncio.sleep(1)
                
    except Exception as e:
        logger.error(f"Error in rollup computation cycle: {e}")


async def _rollup_scheduler_loop():
    """Main scheduler loop that runs periodically."""
    global _rollup_scheduler_running
    
    logger.info("Rollup scheduler started")
    
    # Initial backfill on startup
    logger.info(f"Starting initial backfill for last {ROLLUP_DAYS_TO_BACKFILL} days")
    today = datetime.now(timezone.utc).date()
    for days_ago in range(1, ROLLUP_DAYS_TO_BACKFILL + 1):
        target_date = today - timedelta(days=days_ago)
        await _compute_rollups_for_date(datetime.combine(target_date, datetime.min.time()))
        await asyncio.sleep(0.5)  # Small delay
    
    while _rollup_scheduler_running:
        try:
            await _check_and_compute_rollups()
        except Exception as e:
            logger.error(f"Error in rollup scheduler loop: {e}")
        
        # Wait for next interval
        await asyncio.sleep(ROLLUP_INTERVAL_SECONDS)
    
    logger.info("Rollup scheduler stopped")


def start_rollup_scheduler():
    """Start the rollup scheduler."""
    global _rollup_scheduler_running, _rollup_scheduler_task
    
    if _rollup_scheduler_running:
        logger.warning("Rollup scheduler already running")
        return
    
    _rollup_scheduler_running = True
    _rollup_scheduler_task = asyncio.create_task(_rollup_scheduler_loop())
    logger.info("Rollup scheduler started")


def stop_rollup_scheduler():
    """Stop the rollup scheduler."""
    global _rollup_scheduler_running, _rollup_scheduler_task
    
    _rollup_scheduler_running = False
    
    if _rollup_scheduler_task:
        _rollup_scheduler_task.cancel()
        _rollup_scheduler_task = None
    
    logger.info("Rollup scheduler stopped")


async def get_execution_rollups(
    tenant_id: str,
    start_date: datetime,
    end_date: datetime,
    environment_id: Optional[str] = None,
    workflow_id: Optional[str] = None
):
    """
    Get pre-computed rollup data for a date range.
    Falls back to live computation if no rollups exist.
    """
    try:
        params = {
            'p_tenant_id': tenant_id,
            'p_start_date': start_date.strftime('%Y-%m-%d'),
            'p_end_date': end_date.strftime('%Y-%m-%d')
        }
        if environment_id:
            params['p_environment_id'] = environment_id
        if workflow_id:
            params['p_workflow_id'] = workflow_id
            
        response = db_service.client.rpc('get_execution_rollups', params).execute()
        return response.data or []
        
    except Exception as e:
        logger.warning(f"Failed to get rollups: {e}")
        return []

