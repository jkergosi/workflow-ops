"""
Canonical Reconciliation Service - DB → DB reconciliation and diff computation
"""
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta

from app.services.database import db_service
from app.services.canonical_workflow_service import CanonicalWorkflowService
from app.schemas.canonical_workflow import WorkflowDiffStatus

logger = logging.getLogger(__name__)

RECONCILIATION_DEBOUNCE_SECONDS = 60  # 60 second debounce window (increased to reduce overhead)


class CanonicalReconciliationService:
    """Service for reconciling Git and n8n states, computing diffs"""
    
    # In-memory debounce tracking (for MVP - could be moved to DB for multi-instance)
    _pending_reconciliations: Dict[str, datetime] = {}
    
    @staticmethod
    async def reconcile_environment_pair(
        tenant_id: str,
        source_env_id: str,
        target_env_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Recompute diffs for all canonical workflows between two environments.
        
        This is incremental - only recomputes diffs for workflows whose inputs changed.
        
        Args:
            tenant_id: Tenant ID
            source_env_id: Source environment ID
            target_env_id: Target environment ID
            force: If True, recompute all diffs regardless of changes
            
        Returns:
            Reconciliation result with counts
        """
        debounce_key = f"{tenant_id}:{source_env_id}:{target_env_id}"
        
        # Check debounce
        if not force:
            now = datetime.utcnow()
            if debounce_key in CanonicalReconciliationService._pending_reconciliations:
                last_request = CanonicalReconciliationService._pending_reconciliations[debounce_key]
                if (now - last_request).total_seconds() < RECONCILIATION_DEBOUNCE_SECONDS:
                    # Still in debounce window - skip
                    logger.debug(f"Skipping reconciliation for {debounce_key} (debounced)")
                    return {"skipped": True, "reason": "debounced"}
            
            # Update debounce timestamp
            CanonicalReconciliationService._pending_reconciliations[debounce_key] = now
        
        results = {
            "diffs_computed": 0,
            "diffs_updated": 0,
            "diffs_unchanged": 0,
            "errors": []
        }
        
        try:
            # Get all canonical workflows for this tenant
            canonical_workflows = await CanonicalReconciliationService._get_canonical_workflows(
                tenant_id
            )
            
            for canonical in canonical_workflows:
                canonical_id = canonical["canonical_id"]
                
                try:
                    # Get Git state for both environments
                    source_git_state = await CanonicalWorkflowService.get_canonical_workflow_git_state(
                        tenant_id, source_env_id, canonical_id
                    )
                    target_git_state = await CanonicalWorkflowService.get_canonical_workflow_git_state(
                        tenant_id, target_env_id, canonical_id
                    )
                    
                    # Get environment mappings
                    source_mapping = await CanonicalReconciliationService._get_workflow_mapping(
                        tenant_id, source_env_id, canonical_id
                    )
                    target_mapping = await CanonicalReconciliationService._get_workflow_mapping(
                        tenant_id, target_env_id, canonical_id
                    )
                    
                    # Check if we need to recompute (incremental)
                    if not force:
                        existing_diff = await CanonicalReconciliationService._get_existing_diff(
                            tenant_id, source_env_id, target_env_id, canonical_id
                        )
                        
                        if existing_diff:
                            # Check if inputs changed
                            source_hash_changed = (
                                source_git_state and
                                existing_diff.get("source_git_hash") != source_git_state.get("git_content_hash")
                            )
                            target_hash_changed = (
                                target_git_state and
                                existing_diff.get("target_git_hash") != target_git_state.get("git_content_hash")
                            )
                            source_env_hash_changed = (
                                source_mapping and
                                existing_diff.get("source_env_hash") != source_mapping.get("env_content_hash")
                            )
                            target_env_hash_changed = (
                                target_mapping and
                                existing_diff.get("target_env_hash") != target_mapping.get("env_content_hash")
                            )
                            
                            if not any([source_hash_changed, target_hash_changed, source_env_hash_changed, target_env_hash_changed]):
                                # No changes - skip recomputation
                                results["diffs_unchanged"] += 1
                                continue
                    
                    # Compute diff status
                    diff_status = CanonicalReconciliationService._compute_diff_status(
                        source_git_state,
                        target_git_state,
                        source_mapping,
                        target_mapping
                    )

                    # Build conflict metadata if this is a conflict
                    conflict_metadata = None
                    if diff_status == WorkflowDiffStatus.CONFLICT:
                        conflict_metadata = CanonicalReconciliationService._build_conflict_metadata(
                            source_git_state,
                            target_git_state,
                            source_mapping,
                            target_mapping
                        )

                    # Upsert diff state
                    await CanonicalReconciliationService._upsert_diff_state(
                        tenant_id,
                        source_env_id,
                        target_env_id,
                        canonical_id,
                        diff_status,
                        source_git_state.get("git_content_hash") if source_git_state else None,
                        target_git_state.get("git_content_hash") if target_git_state else None,
                        source_mapping.get("env_content_hash") if source_mapping else None,
                        target_mapping.get("env_content_hash") if target_mapping else None,
                        conflict_metadata=conflict_metadata
                    )
                    
                    results["diffs_computed"] += 1
                    results["diffs_updated"] += 1
                    
                except Exception as e:
                    error_msg = f"Error computing diff for {canonical_id}: {str(e)}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
            
            # Mark stale rows (workflows that no longer exist)
            await CanonicalReconciliationService._mark_stale_diffs(
                tenant_id,
                source_env_id,
                target_env_id,
                {c["canonical_id"] for c in canonical_workflows}
            )
            
            logger.info(
                f"Reconciliation completed for {tenant_id}: "
                f"{results['diffs_computed']} computed, {results['diffs_unchanged']} unchanged"
            )
            
            return results
            
        except Exception as e:
            error_msg = f"Reconciliation failed: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            raise
    
    @staticmethod
    def _compute_diff_status(
        source_git_state: Optional[Dict[str, Any]],
        target_git_state: Optional[Dict[str, Any]],
        source_mapping: Optional[Dict[str, Any]],
        target_mapping: Optional[Dict[str, Any]]
    ) -> WorkflowDiffStatus:
        """
        Compute diff status between source and target environments.

        Logic:
        - If source Git hash == target Git hash: UNCHANGED
        - If source Git exists but target Git doesn't: ADDED
        - If target Git exists but source Git doesn't: TARGET_ONLY
        - If both exist but hashes differ:
          - If BOTH source env AND target Git have independent changes: CONFLICT
          - If source Git hash == target env hash: TARGET_HOTFIX (target modified)
          - Else: MODIFIED (source is newer)

        Conflict Detection:
        A conflict occurs when:
        1. Source environment has local changes (source_env_hash ≠ source_git_hash)
        2. Target Git has different changes (target_git_hash ≠ source_git_hash)
        3. Both changes are independent (not one being a subset of the other)
        """
        source_git_hash = source_git_state.get("git_content_hash") if source_git_state else None
        target_git_hash = target_git_state.get("git_content_hash") if target_git_state else None
        source_env_hash = source_mapping.get("env_content_hash") if source_mapping else None
        target_env_hash = target_mapping.get("env_content_hash") if target_mapping else None

        if not source_git_state and not target_git_state:
            # Neither exists in Git - shouldn't happen, but default to UNCHANGED
            return WorkflowDiffStatus.UNCHANGED

        if not source_git_state:
            # Source doesn't exist in Git, target does
            return WorkflowDiffStatus.TARGET_ONLY

        if not target_git_state:
            # Target doesn't exist in Git, source does
            return WorkflowDiffStatus.ADDED

        # Both exist - compare hashes
        if source_git_hash == target_git_hash:
            return WorkflowDiffStatus.UNCHANGED

        # Hashes differ - check for conflicts first
        # Conflict occurs when BOTH sides have independent modifications
        source_has_local_changes = (
            source_env_hash is not None and
            source_env_hash != source_git_hash
        )
        target_git_has_changes = target_git_hash != source_git_hash

        if source_has_local_changes and target_git_has_changes:
            # Both source environment and target Git have been modified independently
            # Check if target env also differs from target Git (additional complexity)
            target_has_local_changes = (
                target_env_hash is not None and
                target_env_hash != target_git_hash
            )

            # This is a conflict: source env modified, target Git modified
            # (and possibly target env also modified)
            return WorkflowDiffStatus.CONFLICT

        # No conflict - check for target hotfix scenario
        if target_env_hash and source_git_hash == target_env_hash:
            # Target environment matches source Git, but target Git differs
            # This means target was modified in Git (hotfix scenario)
            return WorkflowDiffStatus.TARGET_HOTFIX

        # Source and target both differ, but no conflict
        return WorkflowDiffStatus.MODIFIED
    
    @staticmethod
    def _build_conflict_metadata(
        source_git_state: Optional[Dict[str, Any]],
        target_git_state: Optional[Dict[str, Any]],
        source_mapping: Optional[Dict[str, Any]],
        target_mapping: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Build conflict metadata when a conflict is detected.

        Captures the state of all four sources (source Git, target Git, source env, target env)
        to provide context for conflict resolution.

        Args:
            source_git_state: Source environment Git state
            target_git_state: Target environment Git state
            source_mapping: Source environment mapping
            target_mapping: Target environment mapping

        Returns:
            Conflict metadata dictionary with hashes and timestamps, or None if no conflict detected
        """
        source_git_hash = source_git_state.get("git_content_hash") if source_git_state else None
        target_git_hash = target_git_state.get("git_content_hash") if target_git_state else None
        source_env_hash = source_mapping.get("env_content_hash") if source_mapping else None
        target_env_hash = target_mapping.get("env_content_hash") if target_mapping else None

        # Only build metadata if there's actually a conflict scenario
        source_has_local_changes = (
            source_env_hash is not None and
            source_env_hash != source_git_hash
        )
        target_git_has_changes = target_git_hash != source_git_hash

        if not (source_has_local_changes and target_git_has_changes):
            # Not a conflict scenario
            return None

        metadata = {
            "conflict_detected_at": datetime.utcnow().isoformat(),
            "source_git_hash": source_git_hash,
            "target_git_hash": target_git_hash,
            "source_env_hash": source_env_hash,
            "target_env_hash": target_env_hash,
            "conflict_type": "divergent_changes",
            "description": "Source environment and target Git have independent modifications"
        }

        # Add timestamps if available
        if source_git_state and "updated_at" in source_git_state:
            metadata["source_git_updated_at"] = source_git_state["updated_at"]
        if target_git_state and "updated_at" in target_git_state:
            metadata["target_git_updated_at"] = target_git_state["updated_at"]
        if source_mapping and "updated_at" in source_mapping:
            metadata["source_env_updated_at"] = source_mapping["updated_at"]
        if target_mapping and "updated_at" in target_mapping:
            metadata["target_env_updated_at"] = target_mapping["updated_at"]

        return metadata

    @staticmethod
    async def _get_canonical_workflows(tenant_id: str) -> List[Dict[str, Any]]:
        """Get all canonical workflows for a tenant (not deleted)"""
        try:
            response = (
                db_service.client.table("canonical_workflows")
                .select("canonical_id")
                .eq("tenant_id", tenant_id)
                .is_("deleted_at", "null")
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Error fetching canonical workflows: {str(e)}")
            return []
    
    @staticmethod
    async def _get_workflow_mapping(
        tenant_id: str,
        environment_id: str,
        canonical_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get workflow environment mapping"""
        try:
            response = (
                db_service.client.table("workflow_env_map")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("environment_id", environment_id)
                .eq("canonical_id", canonical_id)
                .single()
                .execute()
            )
            return response.data if response.data else None
        except Exception:
            return None
    
    @staticmethod
    async def _get_existing_diff(
        tenant_id: str,
        source_env_id: str,
        target_env_id: str,
        canonical_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get existing diff state"""
        try:
            response = (
                db_service.client.table("workflow_diff_state")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("source_env_id", source_env_id)
                .eq("target_env_id", target_env_id)
                .eq("canonical_id", canonical_id)
                .single()
                .execute()
            )
            return response.data if response.data else None
        except Exception:
            return None
    
    @staticmethod
    async def _upsert_diff_state(
        tenant_id: str,
        source_env_id: str,
        target_env_id: str,
        canonical_id: str,
        diff_status: WorkflowDiffStatus,
        source_git_hash: Optional[str] = None,
        target_git_hash: Optional[str] = None,
        source_env_hash: Optional[str] = None,
        target_env_hash: Optional[str] = None,
        conflict_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Create or update diff state.

        Args:
            tenant_id: Tenant ID
            source_env_id: Source environment ID
            target_env_id: Target environment ID
            canonical_id: Canonical workflow ID
            diff_status: Computed diff status
            source_git_hash: Source Git content hash (for incremental recompute)
            target_git_hash: Target Git content hash (for incremental recompute)
            source_env_hash: Source environment content hash (for incremental recompute)
            target_env_hash: Target environment content hash (for incremental recompute)
            conflict_metadata: Optional conflict metadata (only for CONFLICT status)
        """
        diff_data = {
            "tenant_id": tenant_id,
            "source_env_id": source_env_id,
            "target_env_id": target_env_id,
            "canonical_id": canonical_id,
            "diff_status": diff_status.value,
            "computed_at": datetime.utcnow().isoformat()
        }

        # Store hashes for incremental recomputation (used in reconcile_environment_pair)
        # These are not in the DB schema but used for change detection
        diff_data["source_git_hash"] = source_git_hash
        diff_data["target_git_hash"] = target_git_hash
        diff_data["source_env_hash"] = source_env_hash
        diff_data["target_env_hash"] = target_env_hash

        # Add conflict metadata if provided
        if conflict_metadata is not None:
            diff_data["conflict_metadata"] = conflict_metadata

        try:
            db_service.client.table("workflow_diff_state").upsert(
                diff_data,
                on_conflict="tenant_id,source_env_id,target_env_id,canonical_id"
            ).execute()
        except Exception as e:
            logger.error(f"Error upserting diff state: {str(e)}")
            raise
    
    @staticmethod
    async def _mark_stale_diffs(
        tenant_id: str,
        source_env_id: str,
        target_env_id: str,
        valid_canonical_ids: Set[str]
    ) -> None:
        """
        Mark diff states as stale for canonical workflows that no longer exist.
        
        For MVP, we'll delete stale rows (they can be recomputed if needed).
        """
        try:
            # Get all diff states for this env pair
            response = (
                db_service.client.table("workflow_diff_state")
                .select("canonical_id")
                .eq("tenant_id", tenant_id)
                .eq("source_env_id", source_env_id)
                .eq("target_env_id", target_env_id)
                .execute()
            )
            
            existing_canonical_ids = {row["canonical_id"] for row in (response.data or [])}
            stale_ids = existing_canonical_ids - valid_canonical_ids
            
            if stale_ids:
                # Delete stale diff states
                for canonical_id in stale_ids:
                    db_service.client.table("workflow_diff_state").delete().eq(
                        "tenant_id", tenant_id
                    ).eq("source_env_id", source_env_id).eq(
                        "target_env_id", target_env_id
                    ).eq("canonical_id", canonical_id).execute()
                
                logger.info(f"Marked {len(stale_ids)} stale diff states for deletion")
        except Exception as e:
            logger.warning(f"Error marking stale diffs: {str(e)}")
    
    @staticmethod
    async def reconcile_all_pairs_for_environment(
        tenant_id: str,
        changed_env_id: str
    ) -> Dict[str, Any]:
        """
        Recompute diffs for all environment pairs involving the changed environment.

        Called after repo sync or env sync completes.

        Note: Reconciliation is debounced per environment pair to reduce overhead.
        """
        # Get all environments for tenant
        environments = await db_service.get_environments(tenant_id)
        env_ids = [env["id"] for env in environments]

        # Filter out the changed environment
        other_env_ids = [env_id for env_id in env_ids if env_id != changed_env_id]

        # Early exit if no other environments to reconcile with
        if not other_env_ids:
            logger.debug(f"No other environments to reconcile with for {changed_env_id}")
            return {"pairs_reconciled": 0, "errors": []}

        logger.info(f"Reconciling {len(other_env_ids)} environment pairs for changed env {changed_env_id}")

        results = {
            "pairs_reconciled": 0,
            "errors": []
        }

        # Recompute for all pairs involving changed_env_id
        for env_id in other_env_ids:
            try:
                # Reconcile source -> target
                result = await CanonicalReconciliationService.reconcile_environment_pair(
                    tenant_id, changed_env_id, env_id
                )
                if not result.get("skipped"):
                    results["pairs_reconciled"] += 1

                # Reconcile target -> source (reverse direction)
                result = await CanonicalReconciliationService.reconcile_environment_pair(
                    tenant_id, env_id, changed_env_id
                )
                if not result.get("skipped"):
                    results["pairs_reconciled"] += 1
            except Exception as e:
                error_msg = f"Error reconciling pair ({changed_env_id}, {env_id}): {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)

        logger.info(f"Reconciliation complete: {results['pairs_reconciled']} pairs processed")
        return results

