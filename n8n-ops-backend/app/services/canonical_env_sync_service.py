"""
Canonical Environment Sync Service - n8n → DB sync (async, batched, resumable)

Greenfield Sync Model:
- DEV: n8n is source of truth. Full sync: workflow_data + env_content_hash + n8n_updated_at
- Non-DEV: Git is source of truth. Observational sync: env_content_hash + n8n_updated_at only (not workflow_data)
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


def _normalize_timestamp(ts: Optional[str]) -> Optional[str]:
    """Normalize timestamp to comparable format (strip timezone variations)"""
    if not ts:
        return None
    # Remove 'Z' suffix and microseconds for comparison
    return ts.replace("Z", "+00:00").split(".")[0] if ts else None


class CanonicalEnvSyncService:
    """Service for syncing workflows from n8n environment to database"""
    
    @staticmethod
    async def sync_environment(
        tenant_id: str,
        environment_id: str,
        environment: Dict[str, Any],
        job_id: Optional[str] = None,
        checkpoint: Optional[Dict[str, Any]] = None,
        tenant_id_for_sse: Optional[str] = None
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
            "workflows_skipped": 0,  # Short-circuited due to unchanged n8n_updated_at
            "workflows_linked": 0,
            "workflows_untracked": 0,
            "workflows_missing": 0,
            "errors": [],
            "observed_workflow_ids": [],  # All workflows observed in Phase 1
            "created_workflow_ids": []  # New untracked workflows created in Phase 1
        }
        
        try:
            # Phase 1: Discovering workflows
            if job_id and tenant_id_for_sse:
                try:
                    from app.api.endpoints.sse import emit_sync_progress
                    await emit_sync_progress(
                        job_id=job_id,
                        environment_id=environment_id,
                        status="running",
                        current_step="discovering_workflows",
                        current=0,
                        total=0,
                        message="Discovering workflows from n8n...",
                        tenant_id=tenant_id_for_sse
                    )
                except Exception as sse_err:
                    logger.warning(f"Failed to emit SSE progress event: {str(sse_err)}")
            
            # Get all workflows from n8n (may be summaries, we'll fetch full data in batch)
            n8n_workflow_summaries = await adapter.get_workflows()
            total_workflows = len(n8n_workflow_summaries)
            
            # Emit discovery complete
            if job_id and tenant_id_for_sse:
                try:
                    from app.api.endpoints.sse import emit_sync_progress
                    await emit_sync_progress(
                        job_id=job_id,
                        environment_id=environment_id,
                        status="running",
                        current_step="updating_environment_state",
                        current=0,
                        total=total_workflows,
                        message=f"Found {total_workflows} workflow(s). Updating environment state...",
                        tenant_id=tenant_id_for_sse
                    )
                except Exception as sse_err:
                    logger.warning(f"Failed to emit SSE progress event: {str(sse_err)}")
            
            # Determine starting point from checkpoint
            start_index = checkpoint.get("last_processed_index", 0) if checkpoint else 0
            
            # Process in batches
            # Transaction boundary: Each batch is an implicit transaction unit
            # - Individual workflow failures within a batch are isolated (caught per-workflow)
            # - Batch checkpoint ensures resumability after partial completion
            # - Database upserts provide atomicity for each workflow mapping
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

                # Update progress if job_id provided (phase: updating_environment_state)
                if job_id:
                    await background_job_service.update_job_status(
                        job_id=job_id,
                        status=BackgroundJobStatus.RUNNING,
                        progress={
                            "current": batch_start,
                            "total": total_workflows,
                            "percentage": int((batch_start / total_workflows) * 100) if total_workflows > 0 else 0,
                            "message": f"Updating environment state: {batch_start} / {total_workflows} workflows processed",
                            "current_step": "updating_environment_state"
                        }
                    )

                    # Emit SSE event for real-time updates (phase-based, not batch-based)
                    if tenant_id_for_sse:
                        try:
                            from app.api.endpoints.sse import emit_sync_progress
                            await emit_sync_progress(
                                job_id=job_id,
                                environment_id=environment_id,
                                status="running",
                                current_step="updating_environment_state",
                                current=batch_start,
                                total=total_workflows,
                                message=f"{batch_start} / {total_workflows} workflows processed",
                                tenant_id=tenant_id_for_sse
                            )
                        except Exception as sse_err:
                            logger.warning(f"Failed to emit SSE progress event: {str(sse_err)}")

                # Determine environment class for sync behavior
                env_class = environment.get("environment_class", "dev").lower()
                is_dev = env_class == "dev"

                # Process batch with transaction safety
                # Each workflow in batch has error isolation via try-catch in _process_workflow_batch
                batch_results = await CanonicalEnvSyncService._process_workflow_batch(
                    tenant_id,
                    environment_id,
                    batch_workflows,
                    is_dev=is_dev
                )

                # Aggregate results
                results["workflows_synced"] += batch_results["synced"]
                results["workflows_skipped"] += batch_results.get("skipped", 0)
                results["workflows_linked"] += batch_results["linked"]
                results["workflows_untracked"] += batch_results["untracked"]
                results["errors"].extend(batch_results["errors"])
                results["observed_workflow_ids"].extend(batch_results.get("observed_workflow_ids", []))
                results["created_workflow_ids"].extend(batch_results.get("created_workflow_ids", []))
                
                # Checkpoint after batch (store in job progress for resumability)
                if job_id:
                    checkpoint_data = {
                        "last_processed_index": batch_end,
                        "last_batch_end": batch_end,
                        "total_workflows": total_workflows
                    }
                    await background_job_service.update_job_status(
                        job_id=job_id,
                        status=BackgroundJobStatus.RUNNING,
                        progress={
                            "current": batch_end,
                            "total": total_workflows,
                            "percentage": int((batch_end / total_workflows) * 100) if total_workflows > 0 else 100,
                            "message": f"Updating environment state: {batch_end} / {total_workflows} workflows processed",
                            "current_step": "updating_environment_state",
                            "checkpoint": checkpoint_data
                        }
                    )
                    
                    # Emit SSE event after batch completion (phase-based, not batch-based)
                    if tenant_id_for_sse:
                        try:
                            from app.api.endpoints.sse import emit_sync_progress
                            await emit_sync_progress(
                                job_id=job_id,
                                environment_id=environment_id,
                                status="running",
                                current_step="updating_environment_state",
                                current=batch_end,
                                total=total_workflows,
                                message=f"{batch_end} / {total_workflows} workflows processed",
                                tenant_id=tenant_id_for_sse
                            )
                        except Exception as sse_err:
                            logger.warning(f"Failed to emit SSE progress event: {str(sse_err)}")
            
            # Mark workflows as missing if they no longer exist in n8n
            n8n_workflow_ids = {w.get("id") for w in n8n_workflow_summaries}
            missing_count = await CanonicalEnvSyncService._mark_missing_workflows_missing(
                tenant_id,
                environment_id,
                n8n_workflow_ids
            )
            results["workflows_missing"] = missing_count
            
            logger.info(
                f"Environment sync completed for tenant {tenant_id}, env {environment_id}: "
                f"{results['workflows_synced']} synced, {results['workflows_skipped']} skipped, "
                f"{results['workflows_untracked']} untracked, {results['workflows_missing']} missing"
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
        workflows: List[Dict[str, Any]],
        is_dev: bool = True
    ) -> Dict[str, Any]:
        """
        Process a batch of workflows.

        Greenfield Sync Model:
        - DEV (is_dev=True): Full sync - update workflow_data + env_content_hash + n8n_updated_at
        - Non-DEV (is_dev=False): Observational sync - update env_content_hash + n8n_updated_at only

        Short-circuit optimization: If n8n_updated_at is unchanged, skip processing.

        Transaction Safety:
        - Each workflow is processed independently within a try-catch block
        - Individual workflow failures don't affect other workflows in the batch
        - Database operations use upsert with on_conflict for idempotency
        - Per-workflow errors are collected and returned for reporting
        """
        batch_results = {
            "synced": 0,
            "skipped": 0,  # Short-circuited due to unchanged n8n_updated_at
            "linked": 0,
            "untracked": 0,
            "errors": [],
            "observed_workflow_ids": [],  # All workflows observed in this batch
            "created_workflow_ids": []  # New workflows created in this batch (untracked)
        }
        
        for workflow in workflows:
            try:
                n8n_workflow_id = workflow.get("id")
                if not n8n_workflow_id:
                    continue
                
                # Track all observed workflows
                batch_results["observed_workflow_ids"].append(n8n_workflow_id)
                
                # Get n8n's updatedAt timestamp for short-circuit check
                n8n_updated_at = workflow.get("updatedAt")
                
                # Check if this n8n workflow is already mapped
                existing_mapping = await CanonicalEnvSyncService._get_mapping_by_n8n_id(
                    tenant_id,
                    environment_id,
                    n8n_workflow_id
                )
                
                if existing_mapping:
                    existing_status = existing_mapping.get("status")
                    existing_canonical_id = existing_mapping.get("canonical_id")
                    existing_n8n_updated_at = existing_mapping.get("n8n_updated_at")
                    
                    # Short-circuit optimization: skip if n8n_updated_at unchanged
                    # Only applies when workflow is not in "missing" state (reappeared workflows need full processing)
                    if existing_status != "missing" and existing_n8n_updated_at and n8n_updated_at:
                        if _normalize_timestamp(existing_n8n_updated_at) == _normalize_timestamp(n8n_updated_at):
                            # Workflow unchanged - skip processing
                            batch_results["skipped"] += 1
                            if existing_canonical_id:
                                batch_results["linked"] += 1
                            continue
                    
                    # Compute content hash (only if not short-circuited)
                    content_hash = compute_workflow_hash(workflow)
                    
                    # Determine new status based on canonical_id presence for missing workflows
                    new_status = None
                    if existing_status == "missing":
                        # Workflow reappeared - transition based on canonical_id
                        if existing_canonical_id:
                            new_status = WorkflowMappingStatus.LINKED
                        else:
                            new_status = WorkflowMappingStatus.UNTRACKED
                    
                    # Update existing mapping
                    # DEV: update workflow_data + hash
                    # Non-DEV: update hash only (observational)
                    await CanonicalEnvSyncService._update_workflow_mapping(
                        tenant_id,
                        environment_id,
                        existing_canonical_id,
                        n8n_workflow_id,
                        content_hash,
                        status=new_status,
                        workflow_data=workflow if is_dev else None,  # Only store workflow_data in DEV
                        n8n_updated_at=n8n_updated_at
                    )
                    batch_results["synced"] += 1
                    if existing_canonical_id or (existing_status == "missing" and existing_canonical_id):
                        batch_results["linked"] += 1
                    elif existing_status == "missing" and not existing_canonical_id:
                        batch_results["untracked"] += 1
                else:
                    # New workflow - compute hash
                    content_hash = compute_workflow_hash(workflow)
                    
                    # Try to auto-link by hash
                    canonical_id = await CanonicalEnvSyncService._try_auto_link_by_hash(
                        tenant_id,
                        environment_id,
                        content_hash,
                        n8n_workflow_id
                    )
                    
                    if canonical_id:
                        # Auto-linked
                        # DEV: store workflow_data
                        # Non-DEV: observational only
                        await CanonicalEnvSyncService._create_workflow_mapping(
                            tenant_id,
                            environment_id,
                            canonical_id,
                            n8n_workflow_id,
                            content_hash,
                            status=WorkflowMappingStatus.LINKED,
                            workflow_data=workflow if is_dev else None,
                            n8n_updated_at=n8n_updated_at
                        )
                        batch_results["synced"] += 1
                        batch_results["linked"] += 1
                    else:
                        # Untracked - create mapping row with canonical_id=NULL
                        await CanonicalEnvSyncService._create_untracked_mapping(
                            tenant_id,
                            environment_id,
                            n8n_workflow_id,
                            content_hash,
                            workflow_data=workflow if is_dev else None,
                            n8n_updated_at=n8n_updated_at
                        )
                        batch_results["synced"] += 1
                        batch_results["untracked"] += 1
                        # Track newly created (untracked) workflows
                        batch_results["created_workflow_ids"].append(n8n_workflow_id)
                
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
        content_hash: str,
        n8n_workflow_id: str
    ) -> Optional[str]:
        """
        Try to auto-link n8n workflow to canonical workflow by content hash.
        
        Only links if:
        - Hash matches exactly
        - Match is unique (one canonical workflow with this hash)
        - canonical_id is not already linked to a different n8n_workflow_id in same environment
        
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
            if len(matching_canonical_ids) != 1:
                return None
            
            canonical_id = matching_canonical_ids[0]
            
            # Check if this canonical_id is already linked to a different n8n_workflow_id in same environment
            existing_mapping_response = (
                db_service.client.table("workflow_env_map")
                .select("n8n_workflow_id")
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("canonical_id", canonical_id)
                .neq("status", "missing")
                .execute()
            )
            
            for mapping in (existing_mapping_response.data or []):
                existing_n8n_id = mapping.get("n8n_workflow_id")
                if existing_n8n_id and existing_n8n_id != n8n_workflow_id:
                    # Conflict: canonical_id already linked to different n8n_workflow_id
                    logger.warning(
                        f"Cannot auto-link {n8n_workflow_id} to canonical {canonical_id}: "
                        f"already linked to {existing_n8n_id}"
                    )
                    return None
            
            return canonical_id
        except Exception as e:
            logger.warning(f"Error in auto-link by hash: {str(e)}")
            return None
    
    @staticmethod
    async def _create_workflow_mapping(
        tenant_id: str,
        environment_id: str,
        canonical_id: Optional[str],
        n8n_workflow_id: str,
        content_hash: str,
        status: Optional[WorkflowMappingStatus] = None,
        linked_by_user_id: Optional[str] = None,
        workflow_data: Optional[Dict[str, Any]] = None,
        n8n_updated_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new workflow environment mapping.

        This function is idempotent and safe to retry:
        - Uses upsert with unique constraint on (tenant_id, environment_id, n8n_workflow_id)
        - Checks for existing mappings to detect unexpected duplicates
        - Logs warnings if duplicate creation is attempted (indicates logic bug)
        - Always returns successfully, either creating or updating as needed
        """
        # Idempotency check: Verify if mapping already exists
        # This helps detect if _create_workflow_mapping is being called inappropriately
        existing_mapping = await CanonicalEnvSyncService._get_mapping_by_n8n_id(
            tenant_id,
            environment_id,
            n8n_workflow_id
        )

        if existing_mapping:
            # Mapping already exists - this indicates a potential logic issue
            # The caller should have used _update_workflow_mapping instead
            logger.warning(
                f"Idempotency check: Mapping already exists for n8n_workflow_id={n8n_workflow_id} "
                f"in env={environment_id}. Proceeding with upsert (safe to retry). "
                f"Existing: canonical_id={existing_mapping.get('canonical_id')}, "
                f"status={existing_mapping.get('status')}. "
                f"New: canonical_id={canonical_id}, status={status.value if status else None}"
            )

        mapping_data = {
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "n8n_workflow_id": n8n_workflow_id,
            "env_content_hash": content_hash,
            "last_env_sync_at": datetime.utcnow().isoformat(),
            "linked_at": datetime.utcnow().isoformat() if status == WorkflowMappingStatus.LINKED else None,
            "linked_by_user_id": linked_by_user_id,
            "status": status.value if status else None,
        }

        # Store workflow_data only if provided (DEV mode)
        if workflow_data is not None:
            mapping_data["workflow_data"] = workflow_data

        # Store n8n_updated_at for short-circuit optimization
        if n8n_updated_at is not None:
            mapping_data["n8n_updated_at"] = n8n_updated_at

        # Only include canonical_id if it's not None
        if canonical_id is not None:
            mapping_data["canonical_id"] = canonical_id

        try:
            # Use upsert with unique constraint on (tenant_id, environment_id, n8n_workflow_id)
            # This ensures idempotency: if the row exists, it will be updated; otherwise, created
            response = (
                db_service.client.table("workflow_env_map")
                .upsert(mapping_data, on_conflict="tenant_id,environment_id,n8n_workflow_id")
                .execute()
            )

            # Log successful creation/update for audit trail
            if existing_mapping:
                logger.info(
                    f"Updated existing mapping via upsert for n8n_workflow_id={n8n_workflow_id} "
                    f"in env={environment_id}"
                )
            else:
                logger.debug(
                    f"Created new mapping for n8n_workflow_id={n8n_workflow_id} "
                    f"in env={environment_id}, canonical_id={canonical_id}, status={status.value if status else None}"
                )

            return response.data[0] if response.data else mapping_data
        except Exception as e:
            logger.error(
                f"Error creating/updating workflow mapping for n8n_workflow_id={n8n_workflow_id}: {str(e)}"
            )
            raise
    
    @staticmethod
    async def _create_untracked_mapping(
        tenant_id: str,
        environment_id: str,
        n8n_workflow_id: str,
        content_hash: str,
        workflow_data: Optional[Dict[str, Any]] = None,
        n8n_updated_at: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a mapping row for an untracked workflow (canonical_id=NULL)"""
        return await CanonicalEnvSyncService._create_workflow_mapping(
            tenant_id=tenant_id,
            environment_id=environment_id,
            canonical_id=None,  # NULL for untracked
            n8n_workflow_id=n8n_workflow_id,
            content_hash=content_hash,
            status=WorkflowMappingStatus.UNTRACKED,
            workflow_data=workflow_data,
            n8n_updated_at=n8n_updated_at
        )
    
    @staticmethod
    async def _update_workflow_mapping(
        tenant_id: str,
        environment_id: str,
        canonical_id: Optional[str],
        n8n_workflow_id: str,
        content_hash: str,
        status: Optional[WorkflowMappingStatus] = None,
        workflow_data: Optional[Dict[str, Any]] = None,
        n8n_updated_at: Optional[str] = None
    ) -> None:
        """
        Update existing workflow mapping.
        
        Greenfield behavior:
        - DEV: workflow_data is provided - full update
        - Non-DEV: workflow_data is None - only update env_content_hash (observational)
        """
        try:
            update_data = {
                "n8n_workflow_id": n8n_workflow_id,
                "env_content_hash": content_hash,
                "last_env_sync_at": datetime.utcnow().isoformat()
            }
            
            # Update canonical_id if provided (handles NULL → value or value → value)
            if canonical_id is not None:
                update_data["canonical_id"] = canonical_id
            
            # Update status if explicitly provided (for transitions like missing→linked)
            if status is not None:
                update_data["status"] = status.value
                # Update linked_at if transitioning to linked
                if status == WorkflowMappingStatus.LINKED:
                    update_data["linked_at"] = datetime.utcnow().isoformat()
            
            # Only update workflow_data if provided (DEV mode)
            # In non-DEV mode, workflow_data=None means don't overwrite existing
            if workflow_data is not None:
                update_data["workflow_data"] = workflow_data
            
            # Always update n8n_updated_at for short-circuit optimization
            if n8n_updated_at is not None:
                update_data["n8n_updated_at"] = n8n_updated_at
            
            # Use n8n_workflow_id for update (more reliable than canonical_id which may be NULL)
            update_query = (
                db_service.client.table("workflow_env_map")
                .update(update_data)
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("n8n_workflow_id", n8n_workflow_id)
            )
            update_query.execute()
        except Exception as e:
            logger.error(f"Error updating workflow mapping: {str(e)}")
            raise
    
    @staticmethod
    async def _mark_missing_workflows_missing(
        tenant_id: str,
        environment_id: str,
        existing_n8n_ids: set
    ) -> int:
        """
        Mark workflows as missing if they no longer exist in n8n.

        Preserves n8n_workflow_id for history/audit.

        Returns count of workflows marked as missing.

        Transaction Safety:
        - Each workflow update is independent (no cross-workflow dependencies)
        - Individual workflow update failures don't affect others
        - Update operations are idempotent (safe to retry)
        """
        try:
            # Get all mappings for this environment
            response = (
                db_service.client.table("workflow_env_map")
                .select("canonical_id, n8n_workflow_id, status")
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .neq("status", "missing")
                .neq("status", "deleted")
                .execute()
            )

            missing_count = 0
            for mapping in (response.data or []):
                n8n_id = mapping.get("n8n_workflow_id")
                if n8n_id and n8n_id not in existing_n8n_ids:
                    # Transaction boundary: Each workflow update isolated via try-catch
                    try:
                        # Workflow no longer exists in n8n - mark as missing
                        # Preserve n8n_workflow_id for history
                        # Update last_env_sync_at when marking as missing
                        update_filter = (
                            db_service.client.table("workflow_env_map")
                            .update({
                                "status": WorkflowMappingStatus.MISSING.value,
                                "last_env_sync_at": datetime.utcnow().isoformat()
                            })
                            .eq("tenant_id", tenant_id)
                            .eq("environment_id", environment_id)
                            .eq("n8n_workflow_id", n8n_id)
                        )
                        update_filter.execute()
                        missing_count += 1
                    except Exception as update_err:
                        # Isolate failure to this workflow only
                        logger.warning(f"Failed to mark workflow {n8n_id} as missing: {str(update_err)}")
                        # Continue processing other workflows

            return missing_count
        except Exception as e:
            logger.error(f"Error marking missing workflows: {str(e)}")
            return 0

