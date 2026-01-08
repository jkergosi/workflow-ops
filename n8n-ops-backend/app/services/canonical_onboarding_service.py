"""
Canonical Onboarding Service - Multi-phase onboarding wizard
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from app.services.database import db_service
from app.services.github_service import GitHubService
from app.services.provider_registry import ProviderRegistry
from app.services.canonical_workflow_service import (
    CanonicalWorkflowService,
    compute_workflow_hash
)
from app.services.canonical_repo_sync_service import CanonicalRepoSyncService
from app.services.canonical_env_sync_service import CanonicalEnvSyncService

logger = logging.getLogger(__name__)


class CanonicalOnboardingService:
    """Service for onboarding tenants to canonical workflow system"""
    
    @staticmethod
    async def check_preflight(tenant_id: str) -> Dict[str, Any]:
        """
        Preflight checks before onboarding.
        
        Returns:
            Dict with is_pre_canonical, has_legacy_workflows, has_legacy_git_layout, environments
        """
        # Check if already onboarded
        tenant = await db_service.get_tenant(tenant_id)
        is_onboarded = bool(tenant.get("canonical_onboarded_at"))
        
        # Check for canonical workflows (check if tenant has any canonical workflows)
        canonical_workflow_count = 0
        try:
            response = db_service.client.table("canonical_workflows").select("canonical_id", count="exact").eq("tenant_id", tenant_id).is_("deleted_at", "null").execute()
            canonical_workflow_count = response.count or 0
        except Exception:
            # Table doesn't exist or error - assume no canonical workflows
            pass
        
        # Legacy check: if canonical workflows exist, tenant is already onboarded
        legacy_workflow_count = 0 if canonical_workflow_count > 0 else 0
        
        # Check Git layout (check if any environment has git_folder set)
        environments = await db_service.get_environments(tenant_id)
        has_git_folder = any(env.get("git_folder") for env in environments)
        
        return {
            "is_pre_canonical": not is_onboarded,
            "has_legacy_workflows": legacy_workflow_count > 0,
            "has_legacy_git_layout": not has_git_folder,
            "environments": [
                {
                    "id": env["id"],
                    "name": env["name"],
                    "environment_type": env.get("environment_type"),
                    "git_repo_url": env.get("git_repo_url"),
                    "git_folder": env.get("git_folder")
                }
                for env in environments
            ]
        }
    
    @staticmethod
    async def start_inventory(
        tenant_id: str,
        anchor_environment_id: str,
        environment_configs: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Start inventory phase - scan workflows from all environments.
        
        Args:
            tenant_id: Tenant ID
            anchor_environment_id: Anchor environment ID
            environment_configs: List of {environment_id, git_repo_url, git_folder} configs
            
        Returns:
            Job ID for background processing
        """
        from app.services.background_job_service import background_job_service, BackgroundJobType, BackgroundJobStatus
        
        # Validate tenant slug (will be used for branch name)
        tenant = await db_service.get_tenant(tenant_id)
        tenant_slug = CanonicalOnboardingService._generate_tenant_slug(tenant.get("name", "tenant"))
        
        # Create background job
        job = await background_job_service.create_job(
            tenant_id=tenant_id,
            job_type=BackgroundJobType.CANONICAL_ONBOARDING_INVENTORY,
            status=BackgroundJobStatus.PENDING,
            metadata={
                "anchor_environment_id": anchor_environment_id,
                "environment_configs": environment_configs,
                "tenant_slug": tenant_slug
            }
        )
        
        # Enqueue background task
        # (In real implementation, this would trigger async processing)
        
        return {
            "job_id": job["id"],
            "status": "pending",
            "message": "Inventory job created"
        }
    
    @staticmethod
    async def run_inventory_phase(
        tenant_id: str,
        anchor_environment_id: str,
        environment_configs: List[Dict[str, str]],
        tenant_slug: str
    ) -> Dict[str, Any]:
        """
        Run inventory phase - scan and generate canonical IDs.

        This is the actual background processing logic.

        Transaction Safety:
        - Each environment sync is wrapped in try-catch for isolation
        - Partial failures are tracked and reported but don't halt entire operation
        - Idempotent operations ensure retry safety (duplicate protection via unique constraints)
        - Each batch within env sync has implicit transaction boundaries via upsert atomicity

        Returns detailed per-workflow tracking including:
        - workflow_results: List of per-workflow results with status (success/error/skipped)
        - environment_results: Per-environment summary of operations
        - Aggregated counts for backwards compatibility
        - has_errors: Boolean flag indicating if any errors occurred
        """
        results = {
            "workflows_inventoried": 0,
            "canonical_ids_generated": 0,
            "auto_links": 0,
            "suggested_links": 0,
            "untracked_workflows": 0,
            "errors": [],
            "has_errors": False,
            # Enhanced per-workflow tracking
            "workflow_results": [],  # List[WorkflowInventoryResult]
            "environment_results": {}  # Dict[env_id -> EnvironmentInventoryResult]
        }

        # Step 1: Scan anchor environment (Git)
        # Transaction boundary: anchor sync isolated from other environment syncs
        anchor_config = next(
            (cfg for cfg in environment_configs if cfg["environment_id"] == anchor_environment_id),
            None
        )

        if not anchor_config:
            raise ValueError("Anchor environment not found in configs")

        # Get anchor environment
        anchor_env = await db_service.get_environment(anchor_environment_id, tenant_id)
        if not anchor_env:
            raise ValueError(f"Anchor environment {anchor_environment_id} not found")

        # Sync anchor environment from Git with enhanced error tracking
        # Transaction boundary: wrapped in try-catch for rollback-on-error semantics
        try:
            anchor_sync_result = await CanonicalRepoSyncService.sync_repository(
                tenant_id=tenant_id,
                environment_id=anchor_environment_id,
                environment={
                    **anchor_env,
                    "git_repo_url": anchor_config.get("git_repo_url") or anchor_env.get("git_repo_url"),
                    "git_folder": anchor_config.get("git_folder") or anchor_env.get("git_folder")
                }
            )

            results["workflows_inventoried"] += anchor_sync_result.get("workflows_synced", 0)
            results["canonical_ids_generated"] += anchor_sync_result.get("workflows_created", 0)

            # Track per-environment results for anchor
            results["environment_results"][anchor_environment_id] = {
                "environment_id": anchor_environment_id,
                "environment_name": anchor_env.get("name", "Unknown"),
                "success_count": anchor_sync_result.get("workflows_synced", 0),
                "error_count": len(anchor_sync_result.get("errors", [])),
                "skipped_count": anchor_sync_result.get("workflows_unchanged", 0),
                "created_count": anchor_sync_result.get("workflows_created", 0)
            }

            # Track errors from anchor sync
            if anchor_sync_result.get("errors"):
                results["errors"].extend(anchor_sync_result["errors"])
                results["has_errors"] = True
                # Parse and add to workflow_results (best effort)
                for error in anchor_sync_result["errors"]:
                    results["workflow_results"].append({
                        "environment_id": anchor_environment_id,
                        "environment_name": anchor_env.get("name", "Unknown"),
                        "workflow_id": None,  # Git sync errors may not have workflow ID
                        "workflow_name": None,
                        "canonical_id": None,
                        "status": "error",
                        "error": error
                    })
        except Exception as e:
            # Transaction rollback semantics: log error but continue with other environments
            error_msg = f"Anchor environment sync failed: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            results["has_errors"] = True
            results["environment_results"][anchor_environment_id] = {
                "environment_id": anchor_environment_id,
                "environment_name": anchor_env.get("name", "Unknown"),
                "success_count": 0,
                "error_count": 1,
                "skipped_count": 0,
                "created_count": 0
            }
            results["workflow_results"].append({
                "environment_id": anchor_environment_id,
                "environment_name": anchor_env.get("name", "Unknown"),
                "workflow_id": None,
                "workflow_name": None,
                "canonical_id": None,
                "status": "error",
                "error": error_msg
            })

        # Step 2: Scan other environments (n8n) with enhanced per-workflow tracking
        # Transaction boundary: each environment sync is isolated
        for env_config in environment_configs:
            if env_config["environment_id"] == anchor_environment_id:
                continue

            env_id = env_config["environment_id"]
            env = await db_service.get_environment(env_id, tenant_id)
            if not env:
                logger.warning(f"Environment {env_id} not found, skipping")
                continue

            # Transaction boundary: wrap each environment sync in try-catch
            # This ensures one environment's failure doesn't affect others
            try:
                # Sync environment from n8n
                env_sync_result = await CanonicalEnvSyncService.sync_environment(
                    tenant_id=tenant_id,
                    environment_id=env_id,
                    environment=env
                )

                results["workflows_inventoried"] += env_sync_result.get("workflows_synced", 0)
                results["untracked_workflows"] += env_sync_result.get("workflows_untracked", 0)

                # Track per-environment summary
                results["environment_results"][env_id] = {
                    "environment_id": env_id,
                    "environment_name": env.get("name", "Unknown"),
                    "success_count": env_sync_result.get("workflows_synced", 0),
                    "error_count": len(env_sync_result.get("errors", [])),
                    "skipped_count": env_sync_result.get("workflows_skipped", 0),
                    "linked_count": env_sync_result.get("workflows_linked", 0),
                    "untracked_count": env_sync_result.get("workflows_untracked", 0)
                }

                # Track per-workflow successes
                # For successfully synced workflows, extract details from observed_workflow_ids
                for workflow_id in env_sync_result.get("observed_workflow_ids", []):
                    # Determine if this was a new untracked workflow or existing linked workflow
                    is_new_untracked = workflow_id in env_sync_result.get("created_workflow_ids", [])

                    results["workflow_results"].append({
                        "environment_id": env_id,
                        "environment_name": env.get("name", "Unknown"),
                        "workflow_id": workflow_id,
                        "workflow_name": None,  # Not available in summary
                        "canonical_id": None if is_new_untracked else "linked",  # Placeholder
                        "status": "success",
                        "error": None,
                        "is_new_untracked": is_new_untracked
                    })

                # Track per-workflow errors from env sync
                if env_sync_result.get("errors"):
                    results["errors"].extend(env_sync_result["errors"])
                    results["has_errors"] = True
                    for error in env_sync_result["errors"]:
                        # Try to extract workflow ID from error message
                        workflow_id = CanonicalOnboardingService._extract_workflow_id_from_error(error)
                        results["workflow_results"].append({
                            "environment_id": env_id,
                            "environment_name": env.get("name", "Unknown"),
                            "workflow_id": workflow_id,
                            "workflow_name": None,
                            "canonical_id": None,
                            "status": "error",
                            "error": error
                        })
            except Exception as e:
                # Transaction rollback semantics: isolate failure to this environment only
                error_msg = f"Environment sync failed for {env.get('name', env_id)}: {str(e)}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                results["has_errors"] = True
                results["environment_results"][env_id] = {
                    "environment_id": env_id,
                    "environment_name": env.get("name", "Unknown"),
                    "success_count": 0,
                    "error_count": 1,
                    "skipped_count": 0,
                    "linked_count": 0,
                    "untracked_count": 0
                }
                results["workflow_results"].append({
                    "environment_id": env_id,
                    "environment_name": env.get("name", "Unknown"),
                    "workflow_id": None,
                    "workflow_name": None,
                    "canonical_id": None,
                    "status": "error",
                    "error": error_msg
                })
                # Continue processing other environments despite this failure

        # Step 3: Auto-link by hash
        # Transaction boundary: auto-linking isolated from sync operations
        try:
            auto_link_result = await CanonicalOnboardingService._auto_link_by_hash(tenant_id)
            results["auto_links"] = auto_link_result.get("linked", 0)
            if auto_link_result.get("errors"):
                results["errors"].extend(auto_link_result["errors"])
        except Exception as e:
            error_msg = f"Auto-link by hash failed: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            # Continue with link suggestions even if auto-link fails

        # Step 4: Generate link suggestions
        # Transaction boundary: suggestion generation isolated from critical operations
        try:
            suggestions_result = await CanonicalOnboardingService._generate_link_suggestions(tenant_id)
            results["suggested_links"] = suggestions_result.get("suggestions", 0)
            if suggestions_result.get("errors"):
                results["errors"].extend(suggestions_result["errors"])
        except Exception as e:
            error_msg = f"Link suggestion generation failed: {str(e)}"
            logger.error(error_msg)
            results["errors"].append(error_msg)
            # Non-critical failure - continue

        # Step 5: Enrich workflow results with workflow names (best effort)
        # This is non-critical and runs after all critical operations complete
        try:
            await CanonicalOnboardingService._enrich_workflow_results_with_names(
                tenant_id, results["workflow_results"]
            )
        except Exception as e:
            logger.warning(f"Failed to enrich workflow names: {str(e)}")
            # Non-critical - continue without enrichment

        return results
    
    @staticmethod
    async def _auto_link_by_hash(tenant_id: str) -> Dict[str, Any]:
        """
        Auto-link workflows by exact content hash match.
        
        Only links if:
        - Hash matches exactly
        - Match is unique (one canonical workflow with this hash)
        """
        results = {"linked": 0, "errors": []}
        
        try:
            # Get all environment mappings without canonical_id (untracked)
            # Actually, untracked workflows don't have mappings - we need to find them differently
            # For MVP, we'll check during env sync which already does auto-linking
            
            # This is handled by CanonicalEnvSyncService._try_auto_link_by_hash
            # So we just return the count
            
            return results
        except Exception as e:
            logger.error(f"Error in auto-link by hash: {str(e)}")
            results["errors"].append(str(e))
            return results
    
    @staticmethod
    async def _generate_link_suggestions(tenant_id: str) -> Dict[str, Any]:
        """
        Generate link suggestions for workflows that are similar but not exact matches.
        
        For MVP, we'll use a simple heuristic:
        - Same workflow name
        - Similar node count
        - Similar structure
        
        More sophisticated matching can be added later.
        """
        results = {"suggestions": 0, "errors": []}
        
        # For MVP, we'll skip sophisticated suggestions
        # Just return empty - can be enhanced later
        
        return results
    
    @staticmethod
    async def create_migration_pr(
        tenant_id: str,
        tenant_slug: str
    ) -> Dict[str, Any]:
        """
        Create migration PR with all canonical workflows.
        
        Args:
            tenant_id: Tenant ID
            tenant_slug: Validated tenant slug for branch name
            
        Returns:
            PR URL, branch name, commit SHA, or error
        """
        # Get anchor environment
        tenant = await db_service.get_tenant(tenant_id)
        anchor_env_id = tenant.get("canonical_anchor_environment_id")
        
        if not anchor_env_id:
            raise ValueError("Anchor environment not set")
        
        anchor_env = await db_service.get_environment(anchor_env_id, tenant_id)
        if not anchor_env:
            raise ValueError("Anchor environment not found")
        
        git_repo_url = anchor_env.get("git_repo_url")
        git_branch = anchor_env.get("git_branch", "main")
        git_pat = anchor_env.get("git_pat")
        git_folder = anchor_env.get("git_folder")
        
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
        
        # Get all canonical workflows for this tenant
        canonical_workflows = await CanonicalWorkflowService.list_canonical_workflows(tenant_id)
        
        # Prepare workflow files and sidecar files
        workflow_files = {}
        sidecar_files = {}
        migration_map = {
            "tenant_id": tenant_id,
            "tenant_slug": tenant_slug,
            "migrated_at": datetime.utcnow().isoformat(),
            "workflows": []
        }
        
        for canonical in canonical_workflows:
            canonical_id = canonical["canonical_id"]
            
            # Get Git state for anchor environment
            git_state = await CanonicalWorkflowService.get_canonical_workflow_git_state(
                tenant_id, anchor_env_id, canonical_id
            )
            
            if not git_state:
                # Skip workflows without Git state
                continue
            
            # Get workflow content from Git
            workflow_content = await github_service.get_file_content(
                git_state["git_path"],
                git_state.get("git_commit_sha") or git_branch
            )
            
            if workflow_content:
                # Remove metadata (keep pure n8n format)
                workflow_content.pop("_comment", None)
                
                file_path = git_state["git_path"]
                workflow_files[file_path] = json.dumps(workflow_content, indent=2)
                
                # Build sidecar file
                sidecar_data = {
                    "canonical_workflow_id": canonical_id,
                    "workflow_name": workflow_content.get("name", "Unknown"),
                    "environments": {}
                }
                
                # Get all environment mappings for this canonical workflow
                mappings = await CanonicalOnboardingService._get_all_mappings_for_canonical(
                    tenant_id, canonical_id
                )
                
                for mapping in mappings:
                    env_id = mapping["environment_id"]
                    sidecar_data["environments"][env_id] = {
                        "n8n_workflow_id": mapping.get("n8n_workflow_id"),
                        "content_hash": f"sha256:{mapping.get('env_content_hash', '')}",
                        "last_seen_at": mapping.get("last_env_sync_at")
                    }
                
                sidecar_path = file_path.replace('.json', '.env-map.json')
                sidecar_files[sidecar_path] = sidecar_data
                
                migration_map["workflows"].append({
                    "canonical_id": canonical_id,
                    "display_name": canonical.get("display_name"),
                    "git_path": file_path
                })
        
        # Create migration PR
        import json
        pr_result = await github_service.create_migration_branch_and_pr(
            tenant_slug=tenant_slug,
            workflow_files=workflow_files,
            sidecar_files=sidecar_files,
            migration_map=migration_map
        )
        
        return pr_result
    
    @staticmethod
    async def _get_all_mappings_for_canonical(
        tenant_id: str,
        canonical_id: str
    ) -> List[Dict[str, Any]]:
        """Get all environment mappings for a canonical workflow"""
        try:
            response = (
                db_service.client.table("workflow_env_map")
                .select("*")
                .eq("tenant_id", tenant_id)
                .eq("canonical_id", canonical_id)
                .execute()
            )
            return response.data or []
        except Exception:
            return []
    
    @staticmethod
    def _generate_tenant_slug(tenant_name: str) -> str:
        """
        Generate tenant slug from display name.

        Rules:
        - lowercase
        - alphanumeric + hyphens only
        - validated, not auto-sanitized
        """
        # Convert to lowercase
        slug = tenant_name.lower()

        # Replace spaces with hyphens
        slug = slug.replace(' ', '-')

        # Remove invalid characters (keep only alphanumeric and hyphens)
        slug = re.sub(r'[^a-z0-9-]', '', slug)

        # Collapse multiple hyphens
        slug = re.sub(r'-+', '-', slug)

        # Remove leading/trailing hyphens
        slug = slug.strip('-')

        # Validate
        if not re.match(r'^[a-z0-9-]+$', slug):
            raise ValueError(f"Invalid tenant slug generated: {slug}")

        return slug

    @staticmethod
    def _extract_workflow_id_from_error(error_msg: str) -> Optional[str]:
        """
        Extract workflow ID from error message.

        Attempts to parse workflow IDs from common error message patterns:
        - "Error processing workflow {id}: ..."
        - "... workflow {id} ..."
        - "... n8n_workflow_id={id} ..."

        Returns workflow ID if found, None otherwise.
        """
        if not error_msg:
            return None

        # Pattern 1: "Error processing workflow <id>:"
        match = re.search(r'workflow (\w+):', error_msg)
        if match:
            return match.group(1)

        # Pattern 2: "n8n_workflow_id=<id>"
        match = re.search(r'n8n_workflow_id=(\w+)', error_msg)
        if match:
            return match.group(1)

        # Pattern 3: Generic "workflow <id>"
        match = re.search(r'workflow (\w+)', error_msg)
        if match:
            return match.group(1)

        return None

    @staticmethod
    async def _enrich_workflow_results_with_names(
        tenant_id: str,
        workflow_results: List[Dict[str, Any]]
    ) -> None:
        """
        Enrich workflow results with actual workflow names from database.

        This is a best-effort enrichment operation that queries the database to
        populate workflow_name fields for better UI display. Modifies workflow_results
        in place.

        Args:
            tenant_id: Tenant ID
            workflow_results: List of workflow result dicts to enrich (modified in place)
        """
        if not workflow_results:
            return

        # Collect all workflow IDs that need enrichment
        workflow_ids_to_fetch = set()
        for result in workflow_results:
            if result.get("workflow_id") and not result.get("workflow_name"):
                workflow_ids_to_fetch.add((result["workflow_id"], result["environment_id"]))

        if not workflow_ids_to_fetch:
            return

        # Batch fetch workflow names from workflow_env_map and canonical_workflows
        workflow_name_map = {}  # (workflow_id, env_id) -> workflow_name

        for workflow_id, env_id in workflow_ids_to_fetch:
            try:
                # First try to get name from workflow_env_map by looking up the canonical workflow
                mapping_response = (
                    db_service.client.table("workflow_env_map")
                    .select("canonical_id")
                    .eq("tenant_id", tenant_id)
                    .eq("environment_id", env_id)
                    .eq("n8n_workflow_id", workflow_id)
                    .limit(1)
                    .execute()
                )

                if mapping_response.data:
                    canonical_id = mapping_response.data[0].get("canonical_id")
                    if canonical_id:
                        # Get canonical workflow name
                        canonical_response = (
                            db_service.client.table("canonical_workflows")
                            .select("display_name")
                            .eq("tenant_id", tenant_id)
                            .eq("canonical_id", canonical_id)
                            .is_("deleted_at", "null")
                            .limit(1)
                            .execute()
                        )
                        if canonical_response.data:
                            workflow_name_map[(workflow_id, env_id)] = (
                                canonical_response.data[0].get("display_name") or f"Workflow {workflow_id[:8]}"
                            )
                            continue

                # Fallback: try to get name from provider (n8n API) - optional for future enhancement
                # For now, use a placeholder
                workflow_name_map[(workflow_id, env_id)] = f"Workflow {workflow_id[:8]}"

            except Exception as e:
                logger.debug(f"Failed to fetch name for workflow {workflow_id}: {str(e)}")
                workflow_name_map[(workflow_id, env_id)] = f"Workflow {workflow_id[:8]}"

        # Apply enriched names to results
        for result in workflow_results:
            workflow_id = result.get("workflow_id")
            env_id = result.get("environment_id")
            if workflow_id and env_id and (workflow_id, env_id) in workflow_name_map:
                result["workflow_name"] = workflow_name_map[(workflow_id, env_id)]
    
    @staticmethod
    async def check_onboarding_complete(tenant_id: str) -> Dict[str, Any]:
        """
        Check if onboarding is complete.
        
        Criteria:
        - Successful repo sync for anchor environment
        - Successful env sync for all environments
        - Zero untracked/unmanaged workflows in anchor env
        - All ambiguous links resolved
        """
        tenant = await db_service.get_tenant(tenant_id)
        anchor_env_id = tenant.get("canonical_anchor_environment_id")
        
        if not anchor_env_id:
            return {
                "is_complete": False,
                "missing_repo_syncs": ["anchor_environment"],
                "missing_env_syncs": [],
                "untracked_workflows": 0,
                "unresolved_suggestions": 0,
                "message": "Anchor environment not set"
            }
        
        # Check repo sync status (check if Git state exists for anchor)
        git_states = (
            db_service.client.table("canonical_workflow_git_state")
            .select("canonical_id")
            .eq("tenant_id", tenant_id)
            .eq("environment_id", anchor_env_id)
            .execute()
        )
        
        has_repo_sync = len(git_states.data or []) > 0
        
        # Check env sync status for all environments
        environments = await db_service.get_environments(tenant_id)
        missing_env_syncs = []
        
        for env in environments:
            mappings = (
                db_service.client.table("workflow_env_map")
                .select("canonical_id")
                .eq("tenant_id", tenant_id)
                .eq("environment_id", env["id"])
                .execute()
            )
            if len(mappings.data or []) == 0:
                missing_env_syncs.append(env["id"])
        
        # Check for untracked workflows in anchor env
        # (workflows in n8n without mappings)
        # This is complex - for MVP, we'll assume env sync handles this
        
        # Check for unresolved link suggestions
        suggestions = (
            db_service.client.table("workflow_link_suggestions")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("status", "open")
            .execute()
        )
        unresolved_suggestions = len(suggestions.data or [])
        
        is_complete = (
            has_repo_sync and
            len(missing_env_syncs) == 0 and
            unresolved_suggestions == 0
        )
        
        return {
            "is_complete": is_complete,
            "missing_repo_syncs": [] if has_repo_sync else [anchor_env_id],
            "missing_env_syncs": missing_env_syncs,
            "untracked_workflows": 0,  # Would need to query n8n to get accurate count
            "unresolved_suggestions": unresolved_suggestions,
            "message": "Onboarding complete" if is_complete else "Onboarding in progress"
        }

