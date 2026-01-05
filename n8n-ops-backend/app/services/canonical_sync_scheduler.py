"""
Canonical Workflow Sync Scheduler

Scheduled safety sync for repository and environment syncs.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from app.services.database import db_service
from app.services.canonical_repo_sync_service import CanonicalRepoSyncService
from app.services.canonical_env_sync_service import CanonicalEnvSyncService
from app.services.canonical_reconciliation_service import CanonicalReconciliationService
from app.services.background_job_service import (
    background_job_service,
    BackgroundJobType,
    BackgroundJobStatus
)

logger = logging.getLogger(__name__)

# Global flags to control schedulers
_repo_sync_scheduler_running = False
_repo_sync_scheduler_task = None

_env_sync_scheduler_running = False
_env_sync_scheduler_task = None

# Sync intervals (in seconds)
REPO_SYNC_INTERVAL = 30 * 60  # 30 minutes
ENV_SYNC_INTERVAL = 15 * 60   # 15 minutes


async def _process_repo_sync_scheduler():
    """Process scheduled repository syncs"""
    global _repo_sync_scheduler_running
    
    while _repo_sync_scheduler_running:
        try:
            # Get all environments with Git configured
            all_environments = await db_service.client.table("environments").select("*").execute()
            
            for env in (all_environments.data or []):
                if not env.get("git_repo_url") or not env.get("git_folder"):
                    continue
                
                tenant_id = env.get("tenant_id")
                environment_id = env.get("id")
                
                if not tenant_id or not environment_id:
                    continue
                
                # Check last sync time
                last_sync = await _get_last_repo_sync_time(tenant_id, environment_id)
                now = datetime.now(timezone.utc)
                
                # Sync if last sync was more than REPO_SYNC_INTERVAL ago
                if not last_sync or (now - last_sync).total_seconds() > REPO_SYNC_INTERVAL:
                    try:
                        # Create background job
                        job = await background_job_service.create_job(
                            tenant_id=tenant_id,
                            job_type=BackgroundJobType.CANONICAL_REPO_SYNC,
                            resource_id=environment_id,
                            resource_type="environment",
                            metadata={"trigger": "scheduled_sync"}
                        )
                        
                        # Run sync
                        await CanonicalRepoSyncService.sync_repository(
                            tenant_id=tenant_id,
                            environment_id=environment_id,
                            environment=env
                        )
                        
                        # Trigger reconciliation
                        await CanonicalReconciliationService.reconcile_all_pairs_for_environment(
                            tenant_id=tenant_id,
                            changed_env_id=environment_id
                        )
                        
                        logger.info(f"Scheduled repo sync completed for environment {environment_id}")
                    except Exception as e:
                        logger.error(f"Scheduled repo sync failed for environment {environment_id}: {str(e)}")
            
            # Wait before next cycle
            await asyncio.sleep(REPO_SYNC_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in repo sync scheduler: {str(e)}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


async def _process_env_sync_scheduler():
    """Process scheduled environment syncs"""
    global _env_sync_scheduler_running
    
    while _env_sync_scheduler_running:
        try:
            # Get all environments
            all_environments = await db_service.client.table("environments").select("*").execute()
            
            for env in (all_environments.data or []):
                tenant_id = env.get("tenant_id")
                environment_id = env.get("id")
                
                if not tenant_id or not environment_id:
                    continue
                
                # Check last sync time
                last_sync = await _get_last_env_sync_time(tenant_id, environment_id)
                now = datetime.now(timezone.utc)
                
                # Sync if last sync was more than ENV_SYNC_INTERVAL ago
                if not last_sync or (now - last_sync).total_seconds() > ENV_SYNC_INTERVAL:
                    try:
                        # Create background job
                        job = await background_job_service.create_job(
                            tenant_id=tenant_id,
                            job_type=BackgroundJobType.CANONICAL_ENV_SYNC,
                            resource_id=environment_id,
                            resource_type="environment",
                            metadata={"trigger": "scheduled_sync"}
                        )
                        
                        # Run sync
                        await CanonicalEnvSyncService.sync_environment(
                            tenant_id=tenant_id,
                            environment_id=environment_id,
                            environment=env,
                            job_id=job["id"]
                        )
                        
                        # Trigger reconciliation
                        await CanonicalReconciliationService.reconcile_all_pairs_for_environment(
                            tenant_id=tenant_id,
                            changed_env_id=environment_id
                        )
                        
                        logger.info(f"Scheduled env sync completed for environment {environment_id}")
                    except Exception as e:
                        logger.error(f"Scheduled env sync failed for environment {environment_id}: {str(e)}")
            
            # Wait before next cycle
            await asyncio.sleep(ENV_SYNC_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in env sync scheduler: {str(e)}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


async def _get_last_repo_sync_time(tenant_id: str, environment_id: str) -> datetime | None:
    """Get last repo sync time for an environment"""
    try:
        # Get most recent git state sync time
        response = (
            db_service.client.table("canonical_workflow_git_state")
            .select("last_repo_sync_at")
            .eq("tenant_id", tenant_id)
            .eq("environment_id", environment_id)
            .order("last_repo_sync_at", desc=True)
            .limit(1)
            .execute()
        )
        
        if response.data and response.data[0].get("last_repo_sync_at"):
            return datetime.fromisoformat(response.data[0]["last_repo_sync_at"].replace("Z", "+00:00"))
        
        return None
    except Exception:
        return None


async def _get_last_env_sync_time(tenant_id: str, environment_id: str) -> datetime | None:
    """Get last env sync time for an environment"""
    try:
        # Get most recent env map sync time
        response = (
            db_service.client.table("workflow_env_map")
            .select("last_env_sync_at")
            .eq("tenant_id", tenant_id)
            .eq("environment_id", environment_id)
            .order("last_env_sync_at", desc=True)
            .limit(1)
            .execute()
        )
        
        if response.data and response.data[0].get("last_env_sync_at"):
            return datetime.fromisoformat(response.data[0]["last_env_sync_at"].replace("Z", "+00:00"))
        
        return None
    except Exception:
        return None


async def start_canonical_sync_schedulers():
    """Start all canonical sync schedulers"""
    global _repo_sync_scheduler_running, _repo_sync_scheduler_task
    global _env_sync_scheduler_running, _env_sync_scheduler_task
    
    # Start repo sync scheduler
    if not _repo_sync_scheduler_running:
        _repo_sync_scheduler_running = True
        _repo_sync_scheduler_task = asyncio.create_task(_process_repo_sync_scheduler())
        logger.info("Canonical repo sync scheduler started")
    
    # Start env sync scheduler
    if not _env_sync_scheduler_running:
        _env_sync_scheduler_running = True
        _env_sync_scheduler_task = asyncio.create_task(_process_env_sync_scheduler())
        logger.info("Canonical env sync scheduler started")


async def stop_canonical_sync_schedulers():
    """Stop all canonical sync schedulers"""
    global _repo_sync_scheduler_running, _repo_sync_scheduler_task
    global _env_sync_scheduler_running, _env_sync_scheduler_task
    
    # Stop repo sync scheduler
    if _repo_sync_scheduler_running:
        _repo_sync_scheduler_running = False
        if _repo_sync_scheduler_task:
            _repo_sync_scheduler_task.cancel()
            try:
                await _repo_sync_scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Canonical repo sync scheduler stopped")
    
    # Stop env sync scheduler
    if _env_sync_scheduler_running:
        _env_sync_scheduler_running = False
        if _env_sync_scheduler_task:
            _env_sync_scheduler_task.cancel()
            try:
                await _env_sync_scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Canonical env sync scheduler stopped")

