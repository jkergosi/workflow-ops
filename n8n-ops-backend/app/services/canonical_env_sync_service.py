"""
Canonical Environment Sync Service - n8n → DB sync (async, batched, resumable)
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.database import db_service
from app.services.provider_registry import ProviderRegistry
from app.services.canonical_workflow_service import (
    CanonicalWorkflowService,
    compute_workflow_hash
)
from app.schemas.canonical_workflow import WorkflowMappingStatus

logger = logging.getLogger(__name__)

BATCH_SIZE = 25  # Process 25-30 workflows per batch (checkpoint after each)


class CanonicalEnvSyncService:
    """Service for syncing workflows from n8n environment to database"""
    
    @staticmethod
    async def sync_environment(
        tenant_id: str,
        environment_id: str,
        environment: Dict[str, Any],
        job_id: Optional[str] = None,
        checkpoint: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Sync workflows from n8n environment to database.
        
        This is an async, batched, resumable operation.
        Processes workflows in batches of 25-30 and checkpoints after each batch.
        
        Args:
            tenant_id: Tenant ID
            environment_id: Environment ID
            environment: Environment configuration
            job_id: Optional background job ID for progress tracking
            checkpoint: Optional checkpoint data to resume from
            
        Returns:
            Sync result with counts and errors
        """
        from app.services.background_job_service import background_job_service, BackgroundJobStatus
        
        adapter = ProviderRegistry.get_adapter_for_environment(environment)
        
        results = {
            "workflows_synced": 0,
            "workflows_linked": 0,
            "workflows_untracked": 0,
            "workflows_deleted": 0,
            "errors": []
        }
        
        try:
            # Get all workflows from n8n (may be summaries, we'll fetch full data in batch)
            n8n_workflow_summaries = await adapter.get_workflows()
            total_workflows = len(n8n_workflow_summaries)
            
            # Determine starting point from checkpoint
            start_index = checkpoint.get("last_processed_index", 0) if checkpoint else 0
            
            # Process in batches
            for batch_start in range(start_index, total_workflows, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, total_workflows)
                batch_summaries = n8n_workflow_summaries[batch_start:batch_end]
                
                # Fetch full workflow data for this batch
                batch_workflows = []
                for summary in batch_summaries:
                    workflow_id = summary.get("id")
                    if workflow_id:
                        try:
                            full_workflow = await adapter.get_workflow(workflow_id)
                            batch_workflows.append(full_workflow)
                        except Exception as e:
                            logger.warning(f"Failed to fetch full workflow {workflow_id}: {str(e)}, using summary")
                            # Fallback to summary if full fetch fails
                            batch_workflows.append(summary)
                
                # Update progress if job_id provided
                if job_id:
                    await background_job_service.update_job_status(
                        job_id=job_id,
                        status=BackgroundJobStatus.RUNNING,
                        progress={
                            "current": batch_start,
                            "total": total_workflows,
                            "percentage": int((batch_start / total_workflows) * 100) if total_workflows > 0 else 0,
                            "message": f"Processing batch {batch_start // BATCH_SIZE + 1}: workflows {batch_start + 1}-{batch_end}"
                        }
                    )
                
                # Process batch
                batch_results = await CanonicalEnvSyncService._process_workflow_batch(
                    tenant_id,
                    environment_id,
                    batch_workflows
                )
                
                # Aggregate results
                results["workflows_synced"] += batch_results["synced"]
                results["workflows_linked"] += batch_results["linked"]
                results["workflows_untracked"] += batch_results["untracked"]
                results["workflows_deleted"] += batch_results["deleted"]
                results["errors"].extend(batch_results["errors"])
                
                # Checkpoint after batch (store in job progress for resumability)
                if job_id:
                    checkpoint_data = {
                        "last_processed_index": batch_end,
                        "last_batch_end": batch_end,
                        "total_workflows": total_workflows
                    }
                    await background_job_service.update_job_status(
                        job_id=job_id,
                        progress={
                            "current": batch_end,
                            "total": total_workflows,
                            "percentage": int((batch_end / total_workflows) * 100) if total_workflows > 0 else 100,
                            "message": f"Completed batch {batch_start // BATCH_SIZE + 1}",
                            "checkpoint": checkpoint_data
                        }
                    )
            
            # Mark workflows as deleted if they no longer exist in n8n
            n8n_workflow_ids = {w.get("id") for w in n8n_workflow_summaries}
            await CanonicalEnvSyncService._mark_missing_workflows_deleted(
                tenant_id,
                environment_id,
                n8n_workflow_ids
            )
            
            logger.info(
                f"Environment sync completed for tenant {tenant_id}, env {environment_id}: "
                f"{results['workflows_synced']} synced, {results['workflows_untracked']} untracked"
            )
            
            return results
            
        except Exception as e:
            error_msg = f"Environment sync failed: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            raise
    
    @staticmethod
    async def _process_workflow_batch(
        tenant_id: str,
        environment_id: str,
        workflows: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process a batch of workflows"""
        batch_results = {
            "synced": 0,
            "linked": 0,
            "untracked": 0,
            "deleted": 0,
            "errors": []
        }
        
        for workflow in workflows:
            try:
                n8n_workflow_id = workflow.get("id")
                if not n8n_workflow_id:
                    continue
                
                # Compute content hash
                content_hash = compute_workflow_hash(workflow)
                
                # Check if this n8n workflow is already mapped
                existing_mapping = await CanonicalEnvSyncService._get_mapping_by_n8n_id(
                    tenant_id,
                    environment_id,
                    n8n_workflow_id
                )
                
                if existing_mapping:
                    # Update existing mapping (store workflow_data for UI caching)
                    await CanonicalEnvSyncService._update_workflow_mapping(
                        tenant_id,
                        environment_id,
                        existing_mapping["canonical_id"],
                        n8n_workflow_id,
                        content_hash,
                        workflow_data=workflow  # Store full workflow JSON
                    )
                    batch_results["synced"] += 1
                    if existing_mapping.get("status") == "linked":
                        batch_results["linked"] += 1
                else:
                    # New workflow - check if we can auto-link by hash
                    canonical_id = await CanonicalEnvSyncService._try_auto_link_by_hash(
                        tenant_id,
                        environment_id,
                        content_hash
                    )
                    
                    if canonical_id:
                        # Auto-linked (store workflow_data for UI caching)
                        await CanonicalEnvSyncService._create_workflow_mapping(
                            tenant_id,
                            environment_id,
                            canonical_id,
                            n8n_workflow_id,
                            content_hash,
                            status=WorkflowMappingStatus.LINKED,
                            workflow_data=workflow  # Store full workflow JSON
                        )
                        batch_results["synced"] += 1
                        batch_results["linked"] += 1
                    else:
                        # Untracked - no mapping created (absence of row = untracked)
                        # Will be surfaced in UI for user to adopt/ignore/delete
                        batch_results["synced"] += 1
                        batch_results["untracked"] += 1
                
            except Exception as e:
                error_msg = f"Error processing workflow {workflow.get('id', 'unknown')}: {str(e)}"
                logger.error(error_msg)
                batch_results["errors"].append(error_msg)
        
        return batch_results
    
    @staticmethod
    async def _get_mapping_by_n8n_id(
        tenant_id: str,
        environment_id: str,
        n8n_workflow_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get workflow mapping by n8n_workflow_id"""
        try:
            response = (
                db_service.client.table("workflow_env_map")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("n8n_workflow_id", n8n_workflow_id)
                .single()
                .execute()
            )
            return response.data if response.data else None
        except Exception:
            return None
    
    @staticmethod
    async def _try_auto_link_by_hash(
        tenant_id: str,
        environment_id: str,
        content_hash: str
    ) -> Optional[str]:
        """
        Try to auto-link n8n workflow to canonical workflow by content hash.
        
        Only links if:
        - Hash matches exactly
        - Match is unique (one canonical workflow with this hash)
        
        Returns canonical_id if linked, None otherwise.
        """
        try:
            # Find canonical workflows with matching Git content hash
            git_state_response = (
                db_service.client.table("canonical_workflow_git_state")
                .select("canonical_id")
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("git_content_hash", content_hash)
                .execute()
            )
            
            matching_canonical_ids = [row["canonical_id"] for row in (git_state_response.data or [])]
            
            # Only auto-link if exactly one match
            if len(matching_canonical_ids) == 1:
                return matching_canonical_ids[0]
            
            return None
        except Exception as e:
            logger.warning(f"Error in auto-link by hash: {str(e)}")
            return None
    
    @staticmethod
    async def _create_workflow_mapping(
        tenant_id: str,
        environment_id: str,
        canonical_id: str,
        n8n_workflow_id: str,
        content_hash: str,
        status: Optional[WorkflowMappingStatus] = None,
        linked_by_user_id: Optional[str] = None,
        workflow_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new workflow environment mapping"""
        mapping_data = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "canonical_id": canonical_id,
            "n8n_workflow_id": n8n_workflow_id,
            "env_content_hash": content_hash,
            "last_env_sync_at": datetime.utcnow().isoformat(),
            "linked_at": datetime.utcnow().isoformat() if status == WorkflowMappingStatus.LINKED else None,
            "linked_by_user_id": linked_by_user_id,
            "status": status.value if status else None,
            "workflow_data": workflow_data  # Store full workflow JSON for UI caching
        }
        
        try:
            response = (
                db_service.client.table("workflow_env_map")
                .upsert(mapping_data, on_conflict="tenant_id,environment_id,canonical_id")
                .execute()
            )
            return response.data[0] if response.data else mapping_data
        except Exception as e:
            logger.error(f"Error creating workflow mapping: {str(e)}")
            raise
    
    @staticmethod
    async def _update_workflow_mapping(
        tenant_id: str,
        environment_id: str,
        canonical_id: str,
        n8n_workflow_id: str,
        content_hash: str,
        workflow_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update existing workflow mapping"""
        try:
            update_data = {
                "n8n_workflow_id": n8n_workflow_id,
                "env_content_hash": content_hash,
                "last_env_sync_at": datetime.utcnow().isoformat()
            }
            if workflow_data is not None:
                update_data["workflow_data"] = workflow_data  # Update cached workflow JSON
            db_service.client.table("workflow_env_map").update(update_data).eq("tenant_id", tenant_id).eq("environment_id", environment_id).eq("canonical_id", canonical_id).execute()
        except Exception as e:
            logger.error(f"Error updating workflow mapping: {str(e)}")
            raise
    
    @staticmethod
    async def _mark_missing_workflows_deleted(
        tenant_id: str,
        environment_id: str,
        existing_n8n_ids: set
    ) -> int:
        """
        Mark workflows as deleted if they no longer exist in n8n.
        
        Returns count of workflows marked as deleted.
        """
        try:
            # Get all mappings for this environment
            response = (
                db_service.client.table("workflow_env_map")
                .select("canonical_id, n8n_workflow_id, status")
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .neq("status", "deleted")
                .execute()
            )
            
            deleted_count = 0
            for mapping in (response.data or []):
                n8n_id = mapping.get("n8n_workflow_id")
                if n8n_id and n8n_id not in existing_n8n_ids:
                    # Workflow no longer exists in n8n - mark as deleted
                    db_service.client.table("workflow_env_map").update({
                        "status": WorkflowMappingStatus.DELETED.value,
                        "n8n_workflow_id": None  # Clear n8n_workflow_id since it no longer exists
                    }).eq("tenant_id", tenant_id).eq("environment_id", environment_id).eq("canonical_id", mapping["canonical_id"]).execute()
                    deleted_count += 1
            
            return deleted_count
        except Exception as e:
            logger.error(f"Error marking missing workflows as deleted: {str(e)}")
            return 0

