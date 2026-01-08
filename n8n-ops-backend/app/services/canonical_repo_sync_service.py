"""
Canonical Repository Sync Service - Git → DB sync

Greenfield Sync Model:
- Git is source of truth for non-DEV environments
- Skip processing if git_content_hash is unchanged (optimization)
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.database import db_service
from app.services.github_service import GitHubService
from app.services.canonical_workflow_service import (
    CanonicalWorkflowService,
    compute_workflow_hash
)

logger = logging.getLogger(__name__)


class CanonicalRepoSyncService:
    """Service for syncing workflows from Git repository to database"""
    
    @staticmethod
    async def sync_repository(
        tenant_id: str,
        environment_id: str,
        environment: Dict[str, Any],
        commit_sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync workflows from Git repository to database.

        Args:
            tenant_id: Tenant ID
            environment_id: Environment ID
            environment: Environment configuration dict
            commit_sha: Optional specific commit to sync from

        Returns:
            Sync result with counts and errors

        Transaction Safety:
        - Each workflow file is processed independently within a try-catch block
        - Individual workflow failures don't halt entire sync operation
        - Database operations use upsert for idempotency
        - Per-workflow errors are collected and returned for reporting
        """
        git_repo_url = environment.get("git_repo_url")
        git_branch = environment.get("git_branch", "main")
        git_pat = environment.get("git_pat")
        git_folder = environment.get("git_folder")
        
        if not git_repo_url or not git_folder:
            raise ValueError("Git repository URL and git_folder are required")
        
        # Create GitHub service
        repo_url = git_repo_url.rstrip('/').replace('.git', '')
        repo_parts = repo_url.split("/")
        github_service = GitHubService(
            token=git_pat,
            repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
            repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
            branch=git_branch
        )
        
        if not github_service.is_configured():
            raise ValueError("GitHub service is not properly configured")
        
        results = {
            "workflows_synced": 0,
            "workflows_unchanged": 0,  # Skipped due to unchanged git_content_hash
            "workflows_created": 0,
            "workflows_updated": 0,
            "sidecars_ingested": 0,
            "errors": []
        }
        
        try:
            # Get all workflow files from Git (using git_folder)
            # Note: This method returns Dict[file_path, workflow_data]
            workflow_files = await github_service.get_all_workflow_files_from_github(
                git_folder=git_folder,
                commit_sha=commit_sha
            )
            
            # Get current commit SHA if not provided
            if not commit_sha:
                try:
                    branch = github_service.repo.get_branch(git_branch)
                    commit_sha = branch.commit.sha
                except Exception as e:
                    logger.warning(f"Could not get commit SHA: {str(e)}")
                    commit_sha = None
            
            # Process each workflow file
            for file_path, workflow_data in workflow_files.items():
                try:
                    # Extract canonical_id from filename
                    # Format: workflows/{git_folder}/{canonical_id}.json
                    canonical_id = file_path.split('/')[-1].replace('.json', '')
                    
                    # Compute content hash
                    content_hash = compute_workflow_hash(workflow_data)
                    
                    # Skip-if-unchanged optimization: check existing git_content_hash
                    existing_git_state = await CanonicalWorkflowService.get_canonical_workflow_git_state(
                        tenant_id, environment_id, canonical_id
                    )
                    if existing_git_state and existing_git_state.get("git_content_hash") == content_hash:
                        # Git content unchanged - skip processing
                        results["workflows_unchanged"] += 1
                        continue
                    
                    # Get or create canonical workflow
                    canonical = await CanonicalWorkflowService.get_canonical_workflow(
                        tenant_id, canonical_id
                    )
                    
                    if not canonical:
                        # Create new canonical workflow
                        display_name = workflow_data.get("name")
                        await CanonicalWorkflowService.create_canonical_workflow(
                            tenant_id=tenant_id,
                            canonical_id=canonical_id,
                            display_name=display_name
                        )
                        results["workflows_created"] += 1
                    else:
                        results["workflows_updated"] += 1
                    
                    # Upsert Git state
                    await CanonicalWorkflowService.upsert_canonical_workflow_git_state(
                        tenant_id=tenant_id,
                        environment_id=environment_id,
                        canonical_id=canonical_id,
                        git_path=file_path,
                        git_content_hash=content_hash,
                        git_commit_sha=commit_sha
                    )
                    
                    results["workflows_synced"] += 1
                    
                    # Try to ingest sidecar file if it exists
                    sidecar_path = file_path.replace('.json', '.env-map.json')
                    try:
                        sidecar_data = await github_service.get_file_content(
                            sidecar_path,
                            commit_sha or git_branch
                        )
                        if sidecar_data:
                            await CanonicalRepoSyncService._ingest_sidecar(
                                tenant_id,
                                canonical_id,
                                sidecar_data
                            )
                            results["sidecars_ingested"] += 1
                    except Exception:
                        # Sidecar doesn't exist or can't be read - that's OK
                        pass
                    
                except Exception as e:
                    error_msg = f"Error processing workflow file {file_path}: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            # Mark workflows dirty for reconciliation
            # (This will be handled by reconciliation service)
            
            logger.info(
                f"Repo sync completed for tenant {tenant_id}, env {environment_id}: "
                f"{results['workflows_synced']} synced, {results['workflows_unchanged']} unchanged, "
                f"{results['sidecars_ingested']} sidecars"
            )
            
            return results
            
        except Exception as e:
            error_msg = f"Repository sync failed: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            raise
    
    @staticmethod
    async def _ingest_sidecar(
        tenant_id: str,
        canonical_id: str,
        sidecar_data: Dict[str, Any]
    ) -> None:
        """
        Ingest sidecar file mappings into workflow_env_map.
        
        Sidecar format:
        {
            "canonical_workflow_id": "uuid",
            "workflow_name": "...",
            "environments": {
                "env_uuid_1": {
                    "environment_type": "prod",
                    "n8n_workflow_id": "203",
                    "content_hash": "sha256:...",
                    "last_seen_at": "..."
                }
            }
        }
        """
        environments = sidecar_data.get("environments", {})
        
        for env_id, env_data in environments.items():
            n8n_workflow_id = env_data.get("n8n_workflow_id")
            content_hash = env_data.get("content_hash", "").replace("sha256:", "")
            last_seen_at = env_data.get("last_seen_at")
            
            if not n8n_workflow_id:
                continue
            
            # Update or create mapping (status will be set during env sync)
            mapping_data = {
                "tenant_id": tenant_id,
                "environment_id": env_id,
                "canonical_id": canonical_id,
                "n8n_workflow_id": n8n_workflow_id,
                "env_content_hash": content_hash,
                "last_env_sync_at": last_seen_at or datetime.utcnow().isoformat(),
                "status": "linked"  # Sidecar implies linked
            }
            
            try:
                db_service.client.table("workflow_env_map").upsert(
                    mapping_data,
                    on_conflict="tenant_id,environment_id,n8n_workflow_id"
                ).execute()
            except Exception as e:
                logger.warning(f"Failed to ingest sidecar mapping for {env_id}: {str(e)}")

