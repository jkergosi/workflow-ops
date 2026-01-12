"""
Unified Sync Orchestrator Service

Single entry point for all environment sync operations.
Ensures idempotent sync requests and prevents duplicate jobs.

MVP Design:
- ONE sync operation type per environment
- Scheduler is disabled by default
- Manual sync is idempotent (returns existing job if running)
- Duplicate jobs are impossible via DB constraint + atomic creation
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from uuid import uuid4

from app.services.database import db_service
from app.services.background_job_service import (
    background_job_service,
    BackgroundJobType,
    BackgroundJobStatus
)

logger = logging.getLogger(__name__)

# Unified sync job type for MVP
SYNC_JOB_TYPE = BackgroundJobType.CANONICAL_ENV_SYNC


class SyncOrchestratorService:
    """
    Unified sync orchestrator service.

    Key responsibilities:
    - Single entry point for triggering environment syncs
    - Idempotent sync requests (returns existing job if queued/running)
    - Always advances sync timestamps
    - Prevents duplicate sync jobs via atomic creation
    """

    @staticmethod
    async def get_active_sync_job(
        tenant_id: str,
        environment_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get active (pending or running) sync job for an environment.

        Returns None if no active job exists.
        """
        try:
            # Check for pending jobs
            pending_jobs = await background_job_service.get_jobs(
                tenant_id=tenant_id,
                resource_type="environment",
                resource_id=environment_id,
                job_type=SYNC_JOB_TYPE,
                status=BackgroundJobStatus.PENDING,
                limit=1
            )
            if pending_jobs:
                return pending_jobs[0]

            # Check for running jobs
            running_jobs = await background_job_service.get_jobs(
                tenant_id=tenant_id,
                resource_type="environment",
                resource_id=environment_id,
                job_type=SYNC_JOB_TYPE,
                status=BackgroundJobStatus.RUNNING,
                limit=1
            )
            if running_jobs:
                return running_jobs[0]

            return None
        except Exception as e:
            logger.error(f"Error checking for active sync job: {e}")
            return None

    @staticmethod
    async def request_sync(
        tenant_id: str,
        environment_id: str,
        created_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Request a sync for an environment.

        Idempotent: If a sync job is already queued or running, returns the existing job.

        Args:
            tenant_id: Tenant ID
            environment_id: Environment ID to sync
            created_by: User ID who requested the sync
            metadata: Optional metadata for the job

        Returns:
            Tuple of (job_dict, is_new_job)
            - job_dict: The job record (existing or newly created)
            - is_new_job: True if a new job was created, False if returning existing
        """
        # First check for existing active job
        existing_job = await SyncOrchestratorService.get_active_sync_job(
            tenant_id=tenant_id,
            environment_id=environment_id
        )

        if existing_job:
            logger.info(
                f"Sync already active for environment {environment_id}, "
                f"returning existing job {existing_job['id']}"
            )
            return existing_job, False

        # Always update last_sync_attempted_at even before job creation
        # This prevents "due" conditions from triggering multiple syncs
        await SyncOrchestratorService._update_sync_attempted_timestamp(
            environment_id=environment_id,
            tenant_id=tenant_id
        )

        # Attempt atomic job creation
        # The DB constraint will prevent duplicates even in race conditions
        try:
            job = await SyncOrchestratorService._create_sync_job_atomic(
                tenant_id=tenant_id,
                environment_id=environment_id,
                created_by=created_by,
                metadata=metadata
            )

            if job:
                logger.info(f"Created new sync job {job['id']} for environment {environment_id}")
                return job, True
            else:
                # Race condition: another job was created between our check and insert
                # Fetch and return the existing job
                existing_job = await SyncOrchestratorService.get_active_sync_job(
                    tenant_id=tenant_id,
                    environment_id=environment_id
                )
                if existing_job:
                    return existing_job, False
                else:
                    # Shouldn't happen, but handle gracefully
                    raise Exception("Failed to create sync job and no existing job found")

        except Exception as e:
            # Check if this is a duplicate key error
            error_str = str(e).lower()
            if "duplicate" in error_str or "unique" in error_str or "constraint" in error_str:
                # Another job was created concurrently, fetch and return it
                existing_job = await SyncOrchestratorService.get_active_sync_job(
                    tenant_id=tenant_id,
                    environment_id=environment_id
                )
                if existing_job:
                    return existing_job, False

            # Re-raise other errors
            raise

    @staticmethod
    async def _create_sync_job_atomic(
        tenant_id: str,
        environment_id: str,
        created_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a sync job atomically.

        Uses the partial unique constraint to prevent duplicates.
        Returns None if a duplicate already exists.
        """
        job_metadata = metadata or {}
        job_metadata["trigger"] = "manual"

        try:
            job = await background_job_service.create_job(
                tenant_id=tenant_id,
                job_type=SYNC_JOB_TYPE,
                resource_id=environment_id,
                resource_type="environment",
                created_by=created_by,
                metadata=job_metadata,
                initial_progress={
                    "current": 0,
                    "total": 0,
                    "percentage": 0,
                    "message": "Sync queued..."
                }
            )
            return job
        except Exception as e:
            error_str = str(e).lower()
            if "duplicate" in error_str or "unique" in error_str or "constraint" in error_str:
                logger.debug(f"Duplicate sync job prevented by constraint for environment {environment_id}")
                return None
            raise

    @staticmethod
    async def _update_sync_attempted_timestamp(
        environment_id: str,
        tenant_id: str
    ) -> None:
        """
        Update the sync attempted timestamp on the environment.

        Always called before attempting to create a sync job.
        This prevents false "due" conditions from the scheduler.
        """
        try:
            now = datetime.utcnow().isoformat()
            await db_service.update_environment(
                environment_id,
                tenant_id,
                {"last_sync_at": now}
            )
            logger.debug(f"Updated last_sync_at for environment {environment_id}")
        except Exception as e:
            # Log but don't fail - this is a best-effort update
            logger.warning(f"Failed to update last_sync_at for environment {environment_id}: {e}")

    @staticmethod
    async def complete_sync(
        job_id: str,
        environment_id: str,
        tenant_id: str,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark a sync job as complete and update timestamps.

        Called when sync completes successfully.
        Always advances the sync timestamp.
        """
        # Update environment timestamps
        now = datetime.utcnow().isoformat()
        try:
            await db_service.update_environment(
                environment_id,
                tenant_id,
                {
                    "last_connected": now,
                    "last_sync_at": now
                }
            )
        except Exception as e:
            logger.warning(f"Failed to update environment timestamps: {e}")

        # Complete the job
        await background_job_service.complete_job(
            job_id=job_id,
            result=result or {}
        )

    @staticmethod
    async def fail_sync(
        job_id: str,
        environment_id: str,
        tenant_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark a sync job as failed.

        Still advances the sync timestamp to prevent immediate retry.
        """
        # Update sync timestamp even on failure to prevent immediate retry
        now = datetime.utcnow().isoformat()
        try:
            await db_service.update_environment(
                environment_id,
                tenant_id,
                {"last_sync_at": now}
            )
        except Exception as e:
            logger.warning(f"Failed to update last_sync_at on failure: {e}")

        # Fail the job
        await background_job_service.fail_job(
            job_id=job_id,
            error_message=error_message,
            error_details=error_details
        )


# Singleton instance
sync_orchestrator = SyncOrchestratorService()
