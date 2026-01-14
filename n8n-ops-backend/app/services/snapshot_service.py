"""
Snapshot Service - Async snapshot creation for background jobs
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

from app.services.database import db_service
from app.services.github_service import GitHubService
from app.services.provider_registry import ProviderRegistry
from app.services.notification_service import notification_service
from app.services.background_job_service import (
    BackgroundJobService,
    BackgroundJobStatus
)
from app.schemas.deployment import SnapshotType

logger = logging.getLogger(__name__)


class SnapshotService:
    """Service for managing snapshot creation operations"""

    @staticmethod
    async def create_snapshot_async(
        tenant_id: str,
        environment_id: str,
        reason: str,
        notes: Optional[str] = None,
        created_by_user_id: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a snapshot asynchronously by exporting all workflows to GitHub.
        Designed to be used with background jobs for long-running operations.

        This method performs the following steps:
        1. Validates environment configuration
        2. Fetches all workflows from N8N
        3. Exports each workflow to GitHub
        4. Creates snapshot record with commit SHA
        5. Emits notification events

        Progress updates are sent via background job service if job_id is provided.

        Args:
            tenant_id: Tenant identifier
            environment_id: Environment identifier
            reason: Human-readable reason for snapshot creation
            notes: Optional additional notes
            created_by_user_id: User ID who initiated the snapshot
            job_id: Optional background job ID for progress tracking

        Returns:
            Dict containing:
                - snapshot_id: Created snapshot ID
                - commit_sha: Git commit SHA
                - workflows_count: Number of workflows synced
                - environment_id: Environment ID

        Raises:
            ValueError: If environment not found, no workflows, or GitHub not configured
            Exception: Any other error during snapshot creation
        """
        logger.info(f"Starting async snapshot creation for environment {environment_id}")

        try:
            # Update job status to running
            if job_id:
                await BackgroundJobService.update_job_status(
                    job_id=job_id,
                    status=BackgroundJobStatus.RUNNING,
                    progress={
                        "current_step": "validating_environment",
                        "message": "Validating environment configuration...",
                        "percentage": 5
                    }
                )

            # Get environment config
            env_config = await db_service.get_environment(environment_id, tenant_id)
            if not env_config:
                raise ValueError(f"Environment {environment_id} not found")

            # Check GitHub configuration
            if not env_config.get("git_repo_url") or not env_config.get("git_pat"):
                raise ValueError("GitHub not configured for this environment. Configure Git integration first.")

            # Get environment type
            env_type = env_config.get("n8n_type")
            if not env_type:
                raise ValueError("Environment type is required for GitHub workflow operations. Set the environment type and try again.")

            # Create GitHub service
            repo_url = env_config.get("git_repo_url", "").rstrip('/').replace('.git', '')
            repo_parts = repo_url.split("/")
            github_service = GitHubService(
                token=env_config.get("git_pat"),
                repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
                repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
                branch=env_config.get("git_branch", "main")
            )

            if not github_service.is_configured():
                raise ValueError("GitHub is not properly configured")

            # Update progress: fetching workflows
            if job_id:
                await BackgroundJobService.update_job_status(
                    job_id=job_id,
                    status=BackgroundJobStatus.RUNNING,
                    progress={
                        "current_step": "fetching_workflows",
                        "message": "Fetching workflows from N8N...",
                        "percentage": 15
                    }
                )

            # Create provider adapter
            adapter = ProviderRegistry.get_adapter_for_environment(env_config)

            # Get all workflows from N8N
            workflows = await adapter.get_workflows()
            if not workflows:
                raise ValueError("No workflows found in environment to backup")

            total_workflows = len(workflows)
            logger.info(f"Found {total_workflows} workflows to export")

            # Export workflows to GitHub with progress updates
            commit_sha = None
            workflows_synced = 0
            workflow_metadata = []

            for idx, workflow in enumerate(workflows, 1):
                try:
                    workflow_id = workflow.get("id")
                    full_workflow = await adapter.get_workflow(workflow_id)

                    # Sync to GitHub
                    await github_service.sync_workflow_to_github(
                        workflow_id=workflow_id,
                        workflow_name=full_workflow.get("name"),
                        workflow_data=full_workflow,
                        commit_message=f"Manual snapshot: {reason}",
                        environment_type=env_type
                    )

                    workflows_synced += 1

                    # Collect workflow metadata
                    workflow_metadata.append({
                        "workflow_id": workflow_id,
                        "workflow_name": full_workflow.get("name", "Unknown"),
                        "active": full_workflow.get("active", False)
                    })

                    # Update progress periodically (every 5 workflows or on last)
                    if job_id and (idx % 5 == 0 or idx == total_workflows):
                        percentage = 15 + int((idx / total_workflows) * 70)  # 15% to 85%
                        await BackgroundJobService.update_job_status(
                            job_id=job_id,
                            status=BackgroundJobStatus.RUNNING,
                            progress={
                                "current_step": "syncing_workflows",
                                "message": f"Syncing workflows to GitHub... ({idx}/{total_workflows})",
                                "current": idx,
                                "total": total_workflows,
                                "percentage": percentage
                            }
                        )

                except Exception as e:
                    logger.error(f"Failed to sync workflow {workflow.get('id')}: {str(e)}")
                    # Continue with other workflows
                    continue

            if workflows_synced == 0:
                raise ValueError("Failed to sync any workflows to GitHub")

            # Update progress: finalizing
            if job_id:
                await BackgroundJobService.update_job_status(
                    job_id=job_id,
                    status=BackgroundJobStatus.RUNNING,
                    progress={
                        "current_step": "finalizing",
                        "message": "Creating snapshot record...",
                        "percentage": 90
                    }
                )

            # Get the latest commit SHA
            sanitized_folder = github_service._sanitize_foldername(env_type)
            try:
                commits = github_service.repo.get_commits(
                    path=f"workflows/{sanitized_folder}",
                    sha=github_service.branch
                )
                if commits:
                    commit_sha = commits[0].sha
                    logger.info(f"Got commit SHA: {commit_sha}")
            except Exception as e:
                logger.warning(f"Could not get commit SHA: {str(e)}")

            # Create snapshot record
            snapshot_id = str(uuid4())
            snapshot_data = {
                "id": snapshot_id,
                "tenant_id": tenant_id,
                "environment_id": environment_id,
                "git_commit_sha": commit_sha or "",
                "type": SnapshotType.MANUAL_BACKUP.value,
                "created_by_user_id": created_by_user_id,
                "related_deployment_id": None,
                "metadata_json": {
                    "reason": reason,
                    "notes": notes,
                    "workflows_count": workflows_synced,
                    "workflows": workflow_metadata,
                    "environment_name": env_config.get("name"),
                    "environment_type": env_type,
                    "created_at": datetime.utcnow().isoformat()
                }
            }

            await db_service.create_snapshot(snapshot_data)
            logger.info(f"Created snapshot {snapshot_id} with {workflows_synced} workflows")

            # Emit snapshot.created event
            try:
                await notification_service.emit_event(
                    tenant_id=tenant_id,
                    event_type="snapshot.created",
                    environment_id=environment_id,
                    metadata={
                        "snapshot_id": snapshot_id,
                        "type": "manual_backup",
                        "reason": reason,
                        "workflows_count": workflows_synced,
                        "commit_sha": commit_sha
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to emit snapshot.created event: {str(e)}")

            # Prepare result data
            result = {
                "snapshot_id": snapshot_id,
                "commit_sha": commit_sha or "",
                "workflows_count": workflows_synced,
                "environment_id": environment_id,
                "environment_name": env_config.get("name"),
                "created_at": datetime.utcnow().isoformat()
            }

            # Complete job with success
            if job_id:
                await BackgroundJobService.complete_job(
                    job_id=job_id,
                    result=result
                )

            logger.info(f"Successfully completed snapshot creation: {snapshot_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to create snapshot: {str(e)}")

            # Mark job as failed
            if job_id:
                await BackgroundJobService.fail_job(
                    job_id=job_id,
                    error_message=str(e),
                    error_details={
                        "error_type": type(e).__name__,
                        "environment_id": environment_id,
                        "tenant_id": tenant_id
                    }
                )

            # Re-raise the exception
            raise


# Singleton instance
snapshot_service = SnapshotService()
