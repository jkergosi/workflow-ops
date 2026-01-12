"""
Background job service for managing async task execution.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4
from app.services.database import db_service
from app.services.sse_pubsub_service import SSEEvent

logger = logging.getLogger(__name__)


class BackgroundJobStatus:
    """Job status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundJobType:
    """Job type constants"""
    PROMOTION_EXECUTE = "promotion_execute"
    ENVIRONMENT_SYNC = "environment_sync"
    GITHUB_SYNC_FROM = "github_sync_from"
    GITHUB_SYNC_TO = "github_sync_to"
    RESTORE_EXECUTE = "restore_execute"
    SNAPSHOT_RESTORE = "snapshot_restore"
    # Canonical workflow job types
    CANONICAL_REPO_SYNC = "canonical_repo_sync"
    CANONICAL_ENV_SYNC = "canonical_env_sync"
    CANONICAL_RECONCILIATION = "canonical_reconciliation"
    CANONICAL_ONBOARDING_INVENTORY = "canonical_onboarding_inventory"
    DEV_GIT_SYNC = "dev_git_sync"
    # Bulk operations
    BULK_WORKFLOW_OPERATION = "bulk_workflow_operation"


class BackgroundJobService:
    """Service for managing background jobs"""

    @staticmethod
    async def create_job(
        tenant_id: str,
        job_type: str,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        created_by: Optional[str] = None,
        initial_progress: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new background job record.
        
        Args:
            tenant_id: Tenant ID
            job_type: Type of job (use BackgroundJobType constants)
            resource_id: ID of the resource being processed (promotion_id, environment_id, etc.)
            resource_type: Type of resource ('promotion', 'environment', etc.)
            created_by: User ID who created the job
            initial_progress: Initial progress data
            metadata: Additional metadata for the job
            
        Returns:
            Job record dictionary
        """
        job_id = str(uuid4())
        job_data = {
            "id": job_id,
            "tenant_id": tenant_id,
            "job_type": job_type,
            "status": BackgroundJobStatus.PENDING,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "created_by": created_by,
            "progress": initial_progress or {},
            "result": {},
            "error_details": {},
            "metadata": metadata or {}
        }
        
        try:
            response = db_service.client.table("background_jobs").insert(job_data).execute()
            logger.info(f"Created background job {job_id} of type {job_type} for resource {resource_id}")
            return response.data[0]
        except Exception as e:
            logger.error(f"Failed to create background job: {str(e)}")
            raise

    @staticmethod
    async def update_job_status(
        job_id: str,
        status: str,
        progress: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update job status and progress.
        
        Args:
            job_id: Job ID
            status: New status (use BackgroundJobStatus constants)
            progress: Progress data (will be merged with existing)
            result: Result data (will be merged with existing)
            error_message: Error message if failed
            error_details: Detailed error information
            
        Returns:
            Updated job record
        """
        update_data: Dict[str, Any] = {"status": status}
        
        if status == BackgroundJobStatus.RUNNING:
            # Set started_at when job starts running (if not already set)
            try:
                current_job = await BackgroundJobService.get_job(job_id)
                if current_job and not current_job.get("started_at"):
                    update_data["started_at"] = datetime.utcnow().isoformat()
            except Exception:
                update_data["started_at"] = datetime.utcnow().isoformat()
        elif status in [BackgroundJobStatus.COMPLETED, BackgroundJobStatus.FAILED, BackgroundJobStatus.CANCELLED]:
            # Set completed_at when job finishes
            update_data["completed_at"] = datetime.utcnow().isoformat()
        
        if progress is not None:
            # Merge progress with existing
            try:
                current_job = await BackgroundJobService.get_job(job_id)
                current_progress = current_job.get("progress", {}) if current_job else {}
                merged_progress = {**current_progress, **progress}
                update_data["progress"] = merged_progress
            except Exception:
                update_data["progress"] = progress
        
        if result is not None:
            # Merge result with existing
            try:
                current_job = await BackgroundJobService.get_job(job_id)
                current_result = current_job.get("result", {}) if current_job else {}
                merged_result = {**current_result, **result}
                update_data["result"] = merged_result
            except Exception:
                update_data["result"] = result
        
        if error_message:
            update_data["error_message"] = error_message
        
        if error_details is not None:
            update_data["error_details"] = error_details
        
        try:
            response = db_service.client.table("background_jobs").update(update_data).eq("id", job_id).execute()
            if response.data:
                logger.debug(f"Updated job {job_id} status to {status}")
                return response.data[0]
            else:
                raise ValueError(f"Job {job_id} not found")
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {str(e)}")
            raise

    @staticmethod
    async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID"""
        try:
            response = db_service.client.table("background_jobs").select("*").eq("id", job_id).single().execute()
            return response.data
        except Exception as e:
            logger.debug(f"Job {job_id} not found: {str(e)}")
            return None

    @staticmethod
    async def get_jobs(
        tenant_id: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get jobs for a tenant with optional filters.
        
        Args:
            tenant_id: Tenant ID (required)
            resource_type: Optional resource type filter
            resource_id: Optional resource ID filter
            job_type: Optional job type filter
            status: Optional status filter
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            
        Returns:
            List of job records, ordered by created_at DESC
        """
        query = db_service.client.table("background_jobs").select("*").eq("tenant_id", tenant_id)
        
        if resource_type:
            query = query.eq("resource_type", resource_type)
        if resource_id:
            query = query.eq("resource_id", resource_id)
        if job_type:
            query = query.eq("job_type", job_type)
        if status:
            query = query.eq("status", status)
        
        # Use range() for pagination (Supabase uses inclusive range)
        response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        return response.data

    @staticmethod
    async def count_jobs(
        tenant_id: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        job_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """
        Count jobs for a tenant with optional filters.
        
        Args:
            tenant_id: Tenant ID (required)
            resource_type: Optional resource type filter
            resource_id: Optional resource ID filter
            job_type: Optional job type filter
            status: Optional status filter
            
        Returns:
            Total count of matching jobs
        """
        query = db_service.client.table("background_jobs").select("*", count="exact").eq("tenant_id", tenant_id)
        
        if resource_type:
            query = query.eq("resource_type", resource_type)
        if resource_id:
            query = query.eq("resource_id", resource_id)
        if job_type:
            query = query.eq("job_type", job_type)
        if status:
            query = query.eq("status", status)
        
        response = query.execute()
        return response.count or 0

    @staticmethod
    async def get_jobs_by_resource(
        resource_type: str,
        resource_id: str,
        tenant_id: Optional[str] = None,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get jobs for a specific resource.
        
        Args:
            resource_type: Type of resource ('promotion', 'environment', etc.)
            resource_id: ID of the resource
            tenant_id: Optional tenant ID filter
            job_type: Optional job type filter
            status: Optional status filter
            limit: Maximum number of jobs to return
            
        Returns:
            List of job records, ordered by created_at DESC
        """
        query = db_service.client.table("background_jobs").select("*").eq("resource_type", resource_type).eq("resource_id", resource_id)
        
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        
        if job_type:
            query = query.eq("job_type", job_type)
        
        if status:
            query = query.eq("status", status)
        
        response = query.order("created_at", desc=True).limit(limit).execute()
        return response.data

    @staticmethod
    async def get_latest_job_by_resource(
        resource_type: str,
        resource_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the latest job for a specific resource"""
        jobs = await BackgroundJobService.get_jobs_by_resource(resource_type, resource_id, tenant_id, limit=1)
        return jobs[0] if jobs else None

    @staticmethod
    async def cancel_job(job_id: str) -> Dict[str, Any]:
        """
        Cancel a running or pending job.

        Safety: This method sets the job status to CANCELLED in the database.
        Workers must cooperatively check the job status and exit gracefully when cancelled.
        This method does NOT forcefully kill threads or processes.

        Args:
            job_id: Job ID to cancel

        Returns:
            Updated job record

        Raises:
            ValueError: If job not found or cannot be cancelled
        """
        from app.services.sse_pubsub_service import sse_pubsub

        job = await BackgroundJobService.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.get("status") not in [BackgroundJobStatus.PENDING, BackgroundJobStatus.RUNNING]:
            raise ValueError(f"Cannot cancel job in status: {job.get('status')}")

        updated_job = await BackgroundJobService.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.CANCELLED,
            error_message="Job cancelled by user"
        )

        # Emit SSE event to notify clients and workers
        await sse_pubsub.publish(
            SSEEvent(
                type="job.status_changed",
                tenant_id=job.get("tenant_id"),
                payload={
                    "job_id": job_id,
                    "status": BackgroundJobStatus.CANCELLED,
                    "job_type": job.get("job_type"),
                    "resource_id": job.get("resource_id"),
                    "resource_type": job.get("resource_type"),
                    "error_message": "Job cancelled by user"
                }
            )
        )

        logger.info(f"Job {job_id} cancelled by user")
        return updated_job

    @staticmethod
    async def update_progress(
        job_id: str,
        current: Optional[int] = None,
        total: Optional[int] = None,
        percentage: Optional[float] = None,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update job progress.

        Args:
            job_id: Job ID
            current: Current item number
            total: Total items
            percentage: Progress percentage (0-100)
            message: Progress message

        Returns:
            Updated job record
        """
        progress: Dict[str, Any] = {}

        if current is not None:
            progress["current"] = current
        if total is not None:
            progress["total"] = total
        if percentage is not None:
            progress["percentage"] = percentage
        if message is not None:
            progress["message"] = message

        # Calculate percentage if not provided but current and total are
        if "percentage" not in progress and "current" in progress and "total" in progress:
            if progress["total"] > 0:
                progress["percentage"] = round((progress["current"] / progress["total"]) * 100, 2)

        return await BackgroundJobService.update_job_status(job_id, BackgroundJobStatus.RUNNING, progress=progress)

    @staticmethod
    async def complete_job(
        job_id: str,
        result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Mark a job as completed successfully.

        Args:
            job_id: Job ID
            result: Final result data

        Returns:
            Updated job record
        """
        from app.services.sse_pubsub_service import sse_pubsub

        job = await BackgroundJobService.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        result_data = result or {}
        result_data["completed_at"] = datetime.utcnow().isoformat()

        updated_job = await BackgroundJobService.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.COMPLETED,
            result=result_data
        )

        # Emit SSE event to notify clients
        await sse_pubsub.publish(
            SSEEvent(
                type="job.status_changed",
                tenant_id=job.get("tenant_id"),
                payload={
                    "job_id": job_id,
                    "status": BackgroundJobStatus.COMPLETED,
                    "job_type": job.get("job_type"),
                    "resource_id": job.get("resource_id"),
                    "resource_type": job.get("resource_type")
                }
            )
        )

        logger.info(f"Job {job_id} marked as completed")
        return updated_job

    @staticmethod
    async def fail_job(
        job_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Mark a job as failed.

        Args:
            job_id: Job ID
            error_message: Error message
            error_details: Detailed error information

        Returns:
            Updated job record
        """
        from app.services.sse_pubsub_service import sse_pubsub

        job = await BackgroundJobService.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        updated_job = await BackgroundJobService.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=error_message,
            error_details=error_details or {}
        )

        # Emit SSE event to notify clients
        await sse_pubsub.publish(
            SSEEvent(
                type="job.status_changed",
                tenant_id=job.get("tenant_id"),
                payload={
                    "job_id": job_id,
                    "status": BackgroundJobStatus.FAILED,
                    "job_type": job.get("job_type"),
                    "resource_id": job.get("resource_id"),
                    "resource_type": job.get("resource_type"),
                    "error_message": error_message
                }
            )
        )

        logger.error(f"Job {job_id} marked as failed: {error_message}")
        return updated_job

    @staticmethod
    async def cleanup_stale_jobs(
        max_runtime_hours: int = 24,
        tenant_id: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Clean up stale jobs that have been running too long.
        This should be called on startup and periodically to handle cases where
        the server crashed or restarted while jobs were running.

        Args:
            max_runtime_hours: Maximum hours a job should run before being marked as failed
            tenant_id: Optional tenant ID to filter by (None = all tenants)

        Returns:
            Dictionary with counts of cleaned up jobs
        """
        from datetime import timedelta
        from app.services.sse_pubsub_service import sse_pubsub

        cutoff_time = datetime.utcnow() - timedelta(hours=max_runtime_hours)
        cutoff_iso = cutoff_time.isoformat()

        cleaned_count = 0
        failed_count = 0
        completed_count = 0

        # First, handle jobs at 100% completion that should be marked as completed
        completed_query = (
            db_service.client.table("background_jobs")
            .select("*")
            .eq("status", BackgroundJobStatus.RUNNING)
        )

        if tenant_id:
            completed_query = completed_query.eq("tenant_id", tenant_id)

        completed_result = completed_query.execute()
        running_jobs = completed_result.data or []

        # Check for jobs at 100% that have been sitting for >5 minutes
        five_min_ago = datetime.utcnow() - timedelta(minutes=5)

        for job in running_jobs:
            job_id = job.get("id")
            progress = job.get("progress", {})
            percentage = progress.get("percentage", 0)
            updated_at_str = job.get("updated_at") or job.get("started_at")

            # Check if job is at 100% or if current == total
            is_complete = False
            if percentage >= 100:
                is_complete = True
            elif progress.get("current") and progress.get("total"):
                if progress["current"] >= progress["total"]:
                    is_complete = True

            if is_complete and updated_at_str:
                try:
                    from dateutil import parser as date_parser
                    updated_at = date_parser.parse(updated_at_str)
                    # Make timezone-aware if needed
                    if updated_at.tzinfo is None:
                        from datetime import timezone
                        updated_at = updated_at.replace(tzinfo=timezone.utc)

                    # If job has been at 100% for >5 minutes, mark as completed
                    if updated_at < five_min_ago.replace(tzinfo=updated_at.tzinfo):
                        result_data = job.get("result", {})
                        if not result_data.get("completed_at"):
                            result_data["completed_at"] = datetime.utcnow().isoformat()

                        await BackgroundJobService.update_job_status(
                            job_id=job_id,
                            status=BackgroundJobStatus.COMPLETED,
                            result=result_data
                        )

                        # Emit SSE event
                        await sse_pubsub.publish(
                            SSEEvent(
                                type="job.status_changed",
                                tenant_id=job.get("tenant_id"),
                                payload={
                                    "job_id": job_id,
                                    "status": BackgroundJobStatus.COMPLETED,
                                    "job_type": job.get("job_type"),
                                    "resource_id": job.get("resource_id"),
                                    "resource_type": job.get("resource_type")
                                }
                            )
                        )

                        cleaned_count += 1
                        completed_count += 1
                        logger.info(f"Marked job {job_id} as completed (was at 100% for >5min)")
                except Exception as parse_error:
                    logger.debug(f"Could not parse date for job {job_id}: {str(parse_error)}")

        # Find jobs that are still running but started too long ago
        query = (
            db_service.client.table("background_jobs")
            .select("*")
            .eq("status", BackgroundJobStatus.RUNNING)
            .lt("started_at", cutoff_iso)
        )

        if tenant_id:
            query = query.eq("tenant_id", tenant_id)

        result = query.execute()
        stale_jobs = result.data or []

        for job in stale_jobs:
            job_id = job.get("id")
            try:
                # Mark as failed with timeout error
                await BackgroundJobService.update_job_status(
                    job_id=job_id,
                    status=BackgroundJobStatus.FAILED,
                    error_message=f"Job timed out after running for more than {max_runtime_hours} hours. Server may have restarted or the task crashed.",
                    error_details={
                        "timeout_hours": max_runtime_hours,
                        "started_at": job.get("started_at"),
                        "marked_stale_at": datetime.utcnow().isoformat()
                    }
                )

                # Emit SSE event
                await sse_pubsub.publish(
                    SSEEvent(
                        type="job.status_changed",
                        tenant_id=job.get("tenant_id"),
                        payload={
                            "job_id": job_id,
                            "status": BackgroundJobStatus.FAILED,
                            "job_type": job.get("job_type"),
                            "resource_id": job.get("resource_id"),
                            "resource_type": job.get("resource_type"),
                            "error_message": f"Job timed out after running for more than {max_runtime_hours} hours"
                        }
                    )
                )

                # Also update associated deployment if this is a promotion job
                if job.get("resource_type") == "promotion" and job.get("result", {}).get("deployment_id"):
                    deployment_id = job.get("result", {}).get("deployment_id")
                    try:
                        from app.services.database import db_service as db_svc
                        await db_svc.update_deployment(deployment_id, {
                            "status": "failed",
                            "finished_at": datetime.utcnow().isoformat(),
                            "summary_json": {
                                "error": f"Deployment timed out after running for more than {max_runtime_hours} hours",
                                "timeout_hours": max_runtime_hours
                            }
                        })
                        logger.info(f"Marked associated deployment {deployment_id} as failed due to stale job")
                    except Exception as dep_error:
                        logger.error(f"Failed to update deployment {deployment_id} for stale job: {str(dep_error)}")

                cleaned_count += 1
                failed_count += 1
                logger.warning(f"Marked stale job {job_id} as failed (running for >{max_runtime_hours}h)")
            except Exception as e:
                logger.error(f"Failed to mark stale job {job_id} as failed: {str(e)}")

        # Also handle jobs that are pending but were created too long ago (likely never started)
        pending_cutoff = datetime.utcnow() - timedelta(hours=1)  # 1 hour for pending jobs
        pending_query = (
            db_service.client.table("background_jobs")
            .select("*")
            .eq("status", BackgroundJobStatus.PENDING)
            .lt("created_at", pending_cutoff.isoformat())
        )

        if tenant_id:
            pending_query = pending_query.eq("tenant_id", tenant_id)

        pending_result = pending_query.execute()
        stale_pending = pending_result.data or []

        for job in stale_pending:
            job_id = job.get("id")
            try:
                await BackgroundJobService.update_job_status(
                    job_id=job_id,
                    status=BackgroundJobStatus.FAILED,
                    error_message="Job was pending for more than 1 hour and never started. Server may have restarted before the task could run.",
                    error_details={
                        "created_at": job.get("created_at"),
                        "marked_stale_at": datetime.utcnow().isoformat()
                    }
                )

                # Emit SSE event
                await sse_pubsub.publish(
                    SSEEvent(
                        type="job.status_changed",
                        tenant_id=job.get("tenant_id"),
                        payload={
                            "job_id": job_id,
                            "status": BackgroundJobStatus.FAILED,
                            "job_type": job.get("job_type"),
                            "resource_id": job.get("resource_id"),
                            "resource_type": job.get("resource_type"),
                            "error_message": "Job was pending for more than 1 hour and never started"
                        }
                    )
                )

                cleaned_count += 1
                failed_count += 1
                logger.warning(f"Marked stale pending job {job_id} as failed")
            except Exception as e:
                logger.error(f"Failed to mark stale pending job {job_id} as failed: {str(e)}")

        return {
            "cleaned_count": cleaned_count,
            "failed_count": failed_count,
            "completed_count": completed_count,
            "stale_running": len(stale_jobs),
            "stale_pending": len(stale_pending)
        }


# Singleton instance
background_job_service = BackgroundJobService()

