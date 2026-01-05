"""
Promotions API endpoints for pipeline-aware environment promotion
"""
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks, Query
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

from app.services.feature_service import feature_service
from app.core.feature_gate import require_feature
from app.core.entitlements_gate import require_entitlement
from app.services.auth_service import get_current_user
from app.services.promotion_service import promotion_service
from app.services.database import db_service
from app.services.notification_service import notification_service
from app.services.environment_action_guard import (
    environment_action_guard,
    EnvironmentAction,
    ActionGuardError
)
from app.schemas.environment import EnvironmentClass
from app.services.background_job_service import (
    background_job_service,
    BackgroundJobStatus,
    BackgroundJobType
)
from app.api.endpoints.admin_audit import create_audit_log
from app.schemas.promotion import (
    PromotionInitiateRequest,
    PromotionInitiateResponse,
    PromotionApprovalRequest,
    PromotionExecuteRequest,
    PromotionDetail,
    PromotionListResponse,
    PromotionSnapshotRequest,
    PromotionSnapshotResponse,
    PromotionDriftCheck,
    PromotionStatus,
    WorkflowSelection,
    GateResult,
    PromotionExecutionResult,
    # NEW: Compare schemas
    DiffStatus,
    ChangeCategory,
    RiskLevel,
    WorkflowCompareResult,
    CompareSummary,
    PromotionCompareResult,
    DiffSummaryResponse,
)
from app.core.provider import Provider, DEFAULT_PROVIDER
from app.schemas.pipeline import PipelineResponse
from app.api.endpoints.sse import emit_deployment_upsert, emit_deployment_progress, emit_counts_update

router = APIRouter()


async def check_drift_policy_blocking(
    tenant_id: str,
    target_environment_id: str
) -> dict:
    """
    Check if drift policy blocks the deployment.

    Returns dict with:
    - blocked: bool - whether deployment is blocked
    - reason: str - reason for blocking (if blocked)
    - details: dict - additional details about the block
    """
    from app.services.entitlements_service import entitlements_service

    try:
        # Check if tenant has drift_policies entitlement
        if not await entitlements_service.has_flag(tenant_id, "drift_policies"):
            # No policy feature = no blocking
            return {"blocked": False, "reason": None, "details": {}}

        # Get tenant's drift policy
        policy_response = db_service.client.table("drift_policies").select(
            "*"
        ).eq("tenant_id", tenant_id).execute()

        if not policy_response.data or len(policy_response.data) == 0:
            # No policy defined = no blocking
            return {"blocked": False, "reason": None, "details": {}}

        policy = policy_response.data[0]

        # Check if policy blocks on drift or expired incidents
        block_on_drift = policy.get("block_deployments_on_drift", False)
        block_on_expired = policy.get("block_deployments_on_expired", False)

        if not block_on_drift and not block_on_expired:
            # Policy doesn't block anything
            return {"blocked": False, "reason": None, "details": {}}

        # Get active drift incidents for target environment
        incidents_response = db_service.client.table("drift_incidents").select(
            "id, status, severity, expires_at, title"
        ).eq("tenant_id", tenant_id).eq("environment_id", target_environment_id).in_(
            "status", ["detected", "acknowledged", "stabilized"]
        ).order("created_at", desc=True).limit(1).execute()

        if not incidents_response.data or len(incidents_response.data) == 0:
            # No active incidents = no blocking
            return {"blocked": False, "reason": None, "details": {}}

        incident = incidents_response.data[0]
        incident_id = incident.get("id")

        # Check for expired TTL
        if block_on_expired and incident.get("expires_at"):
            from datetime import datetime, timezone
            expires_at_str = incident.get("expires_at")
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            if now >= expires_at:
                return {
                    "blocked": True,
                    "reason": "drift_incident_expired",
                    "details": {
                        "incident_id": incident_id,
                        "incident_title": incident.get("title"),
                        "severity": incident.get("severity"),
                        "expired_at": expires_at_str,
                        "message": (
                            f"Deployment blocked: Drift incident has expired. "
                            f"Please resolve or extend the TTL for incident '{incident.get('title')}' before deploying."
                        )
                    }
                }

        # Check for active drift (not necessarily expired)
        if block_on_drift:
            return {
                "blocked": True,
                "reason": "active_drift_incident",
                "details": {
                    "incident_id": incident_id,
                    "incident_title": incident.get("title"),
                    "severity": incident.get("severity"),
                    "status": incident.get("status"),
                    "message": (
                        f"Deployment blocked: Active drift incident exists. "
                        f"Please resolve incident '{incident.get('title')}' before deploying to this environment."
                    )
                }
            }

        return {"blocked": False, "reason": None, "details": {}}

    except Exception as e:
        logger.warning(f"Failed to check drift policy blocking: {e}")
        # On error, don't block - fail open
        return {"blocked": False, "reason": None, "details": {"error": str(e)}}

def get_tenant_id(user_info: dict) -> str:
    tenant = user_info.get("tenant") or {}
    tenant_id = tenant.get("id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return tenant_id


@router.get("/compare", response_model=PromotionCompareResult)
async def compare_environments(
    pipeline_id: str = Query(..., description="Pipeline ID"),
    stage_id: str = Query(..., description="Stage ID within the pipeline"),
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Compare source and target environments for a pipeline stage.
    Returns authoritative diff status for each workflow.

    This is the canonical comparison endpoint - frontend MUST use this
    instead of computing diff status locally.
    """
    from app.services.diff_service import (
        compute_workflow_comparison,
        compute_change_categories,
        compute_risk_level,
        compute_diff_hash,
    )
    from app.services.promotion_service import normalize_workflow_for_comparison

    try:
        tenant_id = get_tenant_id(user_info)

        # Get pipeline
        pipeline_data = await db_service.get_pipeline(pipeline_id, tenant_id)
        if not pipeline_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )

        # Find the stage by ID, index, or source/target environment IDs
        active_stage = None
        stages = pipeline_data.get("stages", [])
        
        if not stages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pipeline has no stages configured"
            )
        
        # Try to match by index first (most common case - stage_id is numeric string like "0", "1", etc.)
        # This handles the case where frontend passes stage index
        try:
            stage_index = int(stage_id)
            if 0 <= stage_index < len(stages):
                active_stage = stages[stage_index]
        except (ValueError, TypeError):
            # stage_id is not numeric, continue to other matching methods
            pass
        
        # If not found by index, try to match by ID (for backwards compatibility if stages have IDs)
        if not active_stage:
            for stage in stages:
                if stage.get("id") == stage_id:
                    active_stage = stage
                    break
        
        # If still not found, try to match by source/target environment IDs
        # (stage_id might be in format "source_env_id:target_env_id")
        if not active_stage and ":" in stage_id:
            parts = stage_id.split(":", 1)
            if len(parts) == 2:
                source_id, target_id = parts
                for stage in stages:
                    if (stage.get("source_environment_id") == source_id and 
                        stage.get("target_environment_id") == target_id):
                        active_stage = stage
                        break

        if not active_stage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stage '{stage_id}' not found in pipeline. Pipeline has {len(stages)} stage(s). Valid stage indices are 0-{len(stages)-1}."
            )

        source_env_id = active_stage.get("source_environment_id")
        target_env_id = active_stage.get("target_environment_id")

        if not source_env_id or not target_env_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stage missing source or target environment ID"
            )

        # Get environment configs
        source_env = await db_service.get_environment(source_env_id, tenant_id)
        target_env = await db_service.get_environment(target_env_id, tenant_id)

        if not source_env or not target_env:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source or target environment not found"
            )

        # Check if canonical workflow system is being used
        # Use canonical workflow diff states from database (fast, cached)
        from app.services.canonical_reconciliation_service import CanonicalReconciliationService
        from app.services.canonical_workflow_service import CanonicalWorkflowService
        from app.services.database import db_service
        
        # Check onboarding status
        onboarding_allowed = await db_service.check_onboarding_gate(tenant_id)
        
        if onboarding_allowed:
            # Use canonical workflow diff states from database
            # Trigger reconciliation if needed (debounced)
            try:
                await CanonicalReconciliationService.reconcile_environment_pair(
                    tenant_id=tenant_id,
                    source_env_id=source_env_id,
                    target_env_id=target_env_id,
                    force=False
                )
            except Exception as recon_error:
                logger.warning(f"Reconciliation failed, falling back to direct comparison: {str(recon_error)}")
            
            # Get diff states from database
            diff_states = await db_service.get_workflow_diff_states(
                tenant_id=tenant_id,
                source_env_id=source_env_id,
                target_env_id=target_env_id
            )
            
            # Get canonical workflows and mappings
            canonical_workflows = await CanonicalWorkflowService.list_canonical_workflows(tenant_id)
            source_mappings = await db_service.get_workflow_mappings(
                tenant_id=tenant_id,
                environment_id=source_env_id
            )
            target_mappings = await db_service.get_workflow_mappings(
                tenant_id=tenant_id,
                environment_id=target_env_id
            )
            
            # Build source and target maps from canonical workflows
            source_map = {}
            target_map = {}
            
            # Get GitHub service for loading workflow content
            source_github = promotion_service._get_github_service(source_env)
            target_github = promotion_service._get_github_service(target_env)
            
            for canonical in canonical_workflows:
                canonical_id = canonical["canonical_id"]
                
                # Get source workflow from Git
                source_git_state = await CanonicalWorkflowService.get_canonical_workflow_git_state(
                    tenant_id, source_env_id, canonical_id
                )
                if source_git_state:
                    source_wf = await source_github.get_file_content(
                        source_git_state["git_path"],
                        source_git_state.get("git_commit_sha") or source_env.get("git_branch", "main")
                    )
                    if source_wf:
                        source_wf.pop("_comment", None)
                        # Use n8n_workflow_id as key for compatibility
                        source_mapping = next((m for m in source_mappings if m.get("canonical_id") == canonical_id), None)
                        if source_mapping and source_mapping.get("n8n_workflow_id"):
                            source_map[source_mapping["n8n_workflow_id"]] = source_wf
                        else:
                            source_map[canonical_id] = source_wf
                
                # Get target workflow from Git
                target_git_state = await CanonicalWorkflowService.get_canonical_workflow_git_state(
                    tenant_id, target_env_id, canonical_id
                )
                if target_git_state:
                    target_wf = await target_github.get_file_content(
                        target_git_state["git_path"],
                        target_git_state.get("git_commit_sha") or target_env.get("git_branch", "main")
                    )
                    if target_wf:
                        target_wf.pop("_comment", None)
                        # Use n8n_workflow_id as key for compatibility
                        target_mapping = next((m for m in target_mappings if m.get("canonical_id") == canonical_id), None)
                        if target_mapping and target_mapping.get("n8n_workflow_id"):
                            target_map[target_mapping["n8n_workflow_id"]] = target_wf
                        else:
                            target_map[canonical_id] = target_wf
        else:
            # Legacy mode - load directly from GitHub
            source_github = promotion_service._get_github_service(source_env)
            target_github = promotion_service._get_github_service(target_env)

            source_env_type = source_env.get("n8n_type")
            target_env_type = target_env.get("n8n_type")

            if not source_env_type or not target_env_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Environment type is required for comparison"
                )

            # Fetch workflows from GitHub
            source_map = await source_github.get_all_workflows_from_github(environment_type=source_env_type)
            target_map = await target_github.get_all_workflows_from_github(environment_type=target_env_type)

        # Build comparison results
        workflows: List[WorkflowCompareResult] = []
        summary_counts = {
            "added": 0,
            "modified": 0,
            "deleted": 0,
            "unchanged": 0,
            "target_hotfix": 0,
        }

        # Use diff states from database if available (faster)
        diff_states_map = {}
        if onboarding_allowed:
            diff_states = await db_service.get_workflow_diff_states(
                tenant_id=tenant_id,
                source_env_id=source_env_id,
                target_env_id=target_env_id
            )
            # Build map of canonical_id -> diff_state
            for diff_state in diff_states:
                canonical_id = diff_state.get("canonical_id")
                # Find n8n_workflow_id for this canonical_id
                source_mapping = next((m for m in source_mappings if m.get("canonical_id") == canonical_id), None)
                if source_mapping and source_mapping.get("n8n_workflow_id"):
                    diff_states_map[source_mapping["n8n_workflow_id"]] = diff_state

        all_workflow_ids = set(source_map.keys()) | set(target_map.keys())

        for wf_id in all_workflow_ids:
            source_wf = source_map.get(wf_id)
            target_wf = target_map.get(wf_id)

            # Determine DiffStatus - use cached diff state if available
            diff_status: DiffStatus
            risk_level = RiskLevel.LOW
            change_categories: List[ChangeCategory] = []
            diff_hash = None

            # Check if we have a cached diff state
            cached_diff = diff_states_map.get(wf_id)
            if cached_diff:
                # Use cached diff status
                diff_status_str = cached_diff.get("diff_status", "")
                if diff_status_str == "added":
                    diff_status = DiffStatus.ADDED
                    summary_counts["added"] += 1
                elif diff_status_str == "target_only":
                    diff_status = DiffStatus.DELETED
                    summary_counts["deleted"] += 1
                elif diff_status_str == "unchanged":
                    diff_status = DiffStatus.UNCHANGED
                    summary_counts["unchanged"] += 1
                elif diff_status_str == "target_hotfix":
                    diff_status = DiffStatus.TARGET_HOTFIX
                    summary_counts["target_hotfix"] += 1
                else:
                    diff_status = DiffStatus.MODIFIED
                    summary_counts["modified"] += 1
                
                # Still need to compute categories and risk from actual content
                if source_wf and target_wf and diff_status in [DiffStatus.MODIFIED, DiffStatus.TARGET_HOTFIX]:
                    from app.services.diff_service import compare_workflows as diff_compare
                    drift_result = diff_compare(source_wf, target_wf)
                    change_categories = compute_change_categories(source_wf, target_wf, drift_result.differences)
                    risk_level = compute_risk_level(change_categories)
                
                diff_hash = compute_diff_hash(source_wf, target_wf)
            else:
                # Compute diff status from workflow content
                if source_wf and not target_wf:
                    # Exists only in source -> ADDED
                    diff_status = DiffStatus.ADDED
                    summary_counts["added"] += 1
                    diff_hash = compute_diff_hash(source_wf, None)

                elif target_wf and not source_wf:
                    # Exists only in target -> DELETED (target-only)
                    diff_status = DiffStatus.DELETED
                    summary_counts["deleted"] += 1
                    diff_hash = compute_diff_hash(None, target_wf)

                else:
                    # Exists in both - compare normalized content
                    source_normalized = normalize_workflow_for_comparison(source_wf)
                    target_normalized = normalize_workflow_for_comparison(target_wf)

                    import json
                    source_json = json.dumps(source_normalized, sort_keys=True)
                    target_json = json.dumps(target_normalized, sort_keys=True)

                    if source_json == target_json:
                        # Content identical -> UNCHANGED
                        diff_status = DiffStatus.UNCHANGED
                        summary_counts["unchanged"] += 1
                        diff_hash = compute_diff_hash(source_wf, target_wf)
                    else:
                        # Content differs - check timestamps to determine who's newer
                        source_updated = source_wf.get("updatedAt")
                        target_updated = target_wf.get("updatedAt")

                        target_is_newer = False
                        if source_updated and target_updated:
                            try:
                                source_dt = datetime.fromisoformat(source_updated.replace('Z', '+00:00'))
                                target_dt = datetime.fromisoformat(target_updated.replace('Z', '+00:00'))
                                target_is_newer = target_dt > source_dt
                            except (ValueError, TypeError):
                                pass

                        if target_is_newer:
                            # Target modified more recently -> TARGET_HOTFIX
                            diff_status = DiffStatus.TARGET_HOTFIX
                            summary_counts["target_hotfix"] += 1
                        else:
                            # Source newer or unknown -> MODIFIED
                            diff_status = DiffStatus.MODIFIED
                            summary_counts["modified"] += 1

                        # Compute semantic categories and risk for modified workflows
                        from app.services.diff_service import compare_workflows as diff_compare
                        drift_result = diff_compare(source_wf, target_wf)
                        change_categories = compute_change_categories(source_wf, target_wf, drift_result.differences)
                        risk_level = compute_risk_level(change_categories)
                        diff_hash = compute_diff_hash(source_wf, target_wf)

            # Build result
            workflow_name = (source_wf or target_wf or {}).get("name", "Unknown")
            workflows.append(WorkflowCompareResult(
                workflow_id=wf_id,
                name=workflow_name,
                diff_status=diff_status,
                risk_level=risk_level,
                change_categories=change_categories,
                diff_hash=diff_hash,
                details_available=True,
                source_updated_at=datetime.fromisoformat(source_wf.get("updatedAt").replace('Z', '+00:00')) if source_wf and source_wf.get("updatedAt") else None,
                target_updated_at=datetime.fromisoformat(target_wf.get("updatedAt").replace('Z', '+00:00')) if target_wf and target_wf.get("updatedAt") else None,
                enabled_in_source=source_wf.get("active", False) if source_wf else False,
                enabled_in_target=target_wf.get("active", False) if target_wf else None,
            ))

        # Build summary
        total = len(workflows)
        summary = CompareSummary(
            total=total,
            added=summary_counts["added"],
            modified=summary_counts["modified"],
            deleted=summary_counts["deleted"],
            unchanged=summary_counts["unchanged"],
            target_hotfix=summary_counts["target_hotfix"],
        )

        return PromotionCompareResult(
            pipeline_id=pipeline_id,
            stage_id=stage_id,
            source_env_id=source_env_id,
            target_env_id=target_env_id,
            summary=summary,
            workflows=workflows,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare environments: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare environments: {str(e)}"
        )


def _generate_summary_bullets(
    diff_status: DiffStatus,
    change_categories: List[ChangeCategory],
    risk_level: RiskLevel,
    diff_result: dict,
    source_workflow: dict,
    target_workflow: dict
) -> tuple[List[str], Dict[str, List[str]]]:
    """
    Generate human-readable summary bullets from structured diff facts.
    Returns (bullets, evidence_map) where evidence_map maps each bullet to supporting facts.
    """
    bullets = []
    evidence_map = {}

    # Handle new workflow
    if diff_status == DiffStatus.ADDED:
        node_count = len(source_workflow.get("nodes", []))
        triggers = [n for n in source_workflow.get("nodes", []) if "trigger" in n.get("type", "").lower()]
        bullet = f"New workflow with {node_count} nodes"
        if triggers:
            trigger_types = [t.get("type", "").replace("n8n-nodes-base.", "") for t in triggers]
            bullet += f", triggered by {', '.join(trigger_types[:2])}"
        bullets.append(bullet)
        evidence_map[bullet] = ["Workflow exists only in source environment"]
        return bullets, evidence_map

    # Handle target-only workflow
    if diff_status == DiffStatus.DELETED:
        bullets.append("Workflow exists only in target environment (will not be affected by promotion)")
        evidence_map[bullets[0]] = ["No matching workflow in source environment"]
        return bullets, evidence_map

    # Handle unchanged
    if diff_status == DiffStatus.UNCHANGED:
        bullets.append("No functional differences detected between source and target")
        evidence_map[bullets[0]] = ["Normalized workflow content is identical"]
        return bullets, evidence_map

    # Handle target hotfix
    if diff_status == DiffStatus.TARGET_HOTFIX:
        bullets.append("Target environment has newer changes - promoting will overwrite hotfixes")
        evidence_map[bullets[0]] = ["Target workflow updatedAt is more recent than source"]

    # Generate category-specific bullets
    category_bullets = {
        ChangeCategory.NODE_ADDED: ("Nodes added to workflow", ["Node count increased"]),
        ChangeCategory.NODE_REMOVED: ("Nodes removed from workflow", ["Node count decreased"]),
        ChangeCategory.NODE_TYPE_CHANGED: ("Node types have changed", ["Node type property differs"]),
        ChangeCategory.CREDENTIALS_CHANGED: ("Credential references updated", ["credentials property differs"]),
        ChangeCategory.EXPRESSIONS_CHANGED: ("Dynamic expressions modified", ["Expression syntax detected in changes"]),
        ChangeCategory.HTTP_CHANGED: ("HTTP/API request configuration changed", ["HTTP node parameters differ"]),
        ChangeCategory.TRIGGER_CHANGED: ("Trigger configuration modified", ["Trigger node properties differ"]),
        ChangeCategory.ROUTING_CHANGED: ("Workflow routing/branching updated", ["Router/Switch/IF node changes"]),
        ChangeCategory.ERROR_HANDLING_CHANGED: ("Error handling configuration updated", ["Error handling node changes"]),
        ChangeCategory.SETTINGS_CHANGED: ("Workflow settings modified", ["settings property differs"]),
        ChangeCategory.CODE_CHANGED: ("Code/Function node logic modified", ["Code/Function node parameters differ"]),
        ChangeCategory.RENAME_ONLY: ("Only workflow or node names changed (no functional impact)", ["name property differs"]),
    }

    for category in change_categories:
        if category in category_bullets:
            bullet, evidence = category_bullets[category]
            bullets.append(bullet)
            evidence_map[bullet] = evidence

    # Add diff summary if available
    summary = diff_result.get("summary", {})
    if summary:
        if summary.get("nodesAdded", 0) > 0:
            b = f"{summary['nodesAdded']} node(s) added"
            if b not in bullets:
                bullets.append(b)
                evidence_map[b] = [f"nodesAdded: {summary['nodesAdded']}"]
        if summary.get("nodesRemoved", 0) > 0:
            b = f"{summary['nodesRemoved']} node(s) removed"
            if b not in bullets:
                bullets.append(b)
                evidence_map[b] = [f"nodesRemoved: {summary['nodesRemoved']}"]
        if summary.get("nodesModified", 0) > 0:
            b = f"{summary['nodesModified']} node(s) modified"
            if b not in bullets:
                bullets.append(b)
                evidence_map[b] = [f"nodesModified: {summary['nodesModified']}"]

    # Limit to 6 bullets
    if len(bullets) > 6:
        bullets = bullets[:6]
        evidence_map = {k: v for k, v in evidence_map.items() if k in bullets}

    # Ensure at least one bullet
    if not bullets:
        bullets.append("Workflow content differs between environments")
        evidence_map[bullets[0]] = ["Normalized JSON comparison detected differences"]

    return bullets, evidence_map


def _get_risk_explanation(risk_level: RiskLevel, change_categories: List[ChangeCategory]) -> str:
    """Generate a human-readable explanation for the risk level."""
    if risk_level == RiskLevel.HIGH:
        high_risk_cats = [c for c in change_categories if c in {
            ChangeCategory.CREDENTIALS_CHANGED,
            ChangeCategory.EXPRESSIONS_CHANGED,
            ChangeCategory.TRIGGER_CHANGED,
            ChangeCategory.HTTP_CHANGED,
            ChangeCategory.ROUTING_CHANGED,
            ChangeCategory.CODE_CHANGED,
        }]
        cat_names = [c.value.replace("_", " ") for c in high_risk_cats]
        return f"High risk due to: {', '.join(cat_names)}. These changes may affect workflow behavior or security."

    if risk_level == RiskLevel.MEDIUM:
        return "Medium risk: Changes to error handling or settings may affect workflow reliability."

    return "Low risk: Changes are cosmetic or non-functional (e.g., renaming)."


# Simple in-memory cache for diff summaries (keyed by diff_hash)
_diff_summary_cache: Dict[str, DiffSummaryResponse] = {}


@router.post("/diff-summary", response_model=DiffSummaryResponse)
async def generate_diff_summary(
    workflow_id: str = Query(..., description="Workflow ID to generate summary for"),
    source_env_id: str = Query(..., description="Source environment ID"),
    target_env_id: str = Query(..., description="Target environment ID"),
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Generate AI summary from structured diff facts.
    Cached by diff_hash for performance.

    Returns human-readable summary bullets with evidence links.
    """
    from app.services.diff_service import (
        compute_change_categories,
        compute_risk_level,
        compute_diff_hash,
        compare_workflows as diff_compare,
    )
    from app.services.promotion_service import normalize_workflow_for_comparison

    try:
        tenant_id = get_tenant_id(user_info)

        # Get environment configs
        source_env = await db_service.get_environment(source_env_id, tenant_id)
        target_env = await db_service.get_environment(target_env_id, tenant_id)

        if not source_env or not target_env:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source or target environment not found"
            )

        # Get workflows from GitHub
        source_github = promotion_service._get_github_service(source_env)
        target_github = promotion_service._get_github_service(target_env)

        source_env_type = source_env.get("n8n_type")
        target_env_type = target_env.get("n8n_type")

        if not source_env_type or not target_env_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment type is required for diff summary"
            )

        # Fetch workflows
        source_map = await source_github.get_all_workflows_from_github(environment_type=source_env_type)
        target_map = await target_github.get_all_workflows_from_github(environment_type=target_env_type)

        source_wf = source_map.get(workflow_id)
        target_wf = target_map.get(workflow_id)

        # Compute diff hash for caching
        diff_hash = compute_diff_hash(source_wf, target_wf)

        # Check cache
        if diff_hash and diff_hash in _diff_summary_cache:
            cached = _diff_summary_cache[diff_hash]
            return DiffSummaryResponse(
                bullets=cached.bullets,
                risk_level=cached.risk_level,
                risk_explanation=cached.risk_explanation,
                evidence_map=cached.evidence_map,
                change_categories=cached.change_categories,
                is_new_workflow=cached.is_new_workflow,
                cached=True,
            )

        # Determine diff status
        diff_status: DiffStatus
        risk_level = RiskLevel.LOW
        change_categories: List[ChangeCategory] = []
        diff_result = {"summary": {}, "differences": []}

        if source_wf and not target_wf:
            diff_status = DiffStatus.ADDED
            is_new = True
        elif target_wf and not source_wf:
            diff_status = DiffStatus.DELETED
            is_new = False
        else:
            is_new = False
            # Compare normalized content
            source_normalized = normalize_workflow_for_comparison(source_wf)
            target_normalized = normalize_workflow_for_comparison(target_wf)

            import json
            source_json = json.dumps(source_normalized, sort_keys=True)
            target_json = json.dumps(target_normalized, sort_keys=True)

            if source_json == target_json:
                diff_status = DiffStatus.UNCHANGED
            else:
                # Check timestamps
                source_updated = source_wf.get("updatedAt")
                target_updated = target_wf.get("updatedAt")
                target_is_newer = False

                if source_updated and target_updated:
                    try:
                        source_dt = datetime.fromisoformat(source_updated.replace('Z', '+00:00'))
                        target_dt = datetime.fromisoformat(target_updated.replace('Z', '+00:00'))
                        target_is_newer = target_dt > source_dt
                    except (ValueError, TypeError):
                        pass

                if target_is_newer:
                    diff_status = DiffStatus.TARGET_HOTFIX
                else:
                    diff_status = DiffStatus.MODIFIED

                # Compute detailed diff
                diff_result = diff_compare(source_wf, target_wf)
                change_categories = compute_change_categories(source_wf, target_wf, diff_result.differences)
                risk_level = compute_risk_level(change_categories)

        # Generate summary bullets
        bullets, evidence_map = _generate_summary_bullets(
            diff_status=diff_status,
            change_categories=change_categories,
            risk_level=risk_level,
            diff_result=diff_result if isinstance(diff_result, dict) else {"summary": diff_result.summary.__dict__ if hasattr(diff_result, 'summary') else {}, "differences": []},
            source_workflow=source_wf or {},
            target_workflow=target_wf or {},
        )

        # Get risk explanation
        risk_explanation = _get_risk_explanation(risk_level, change_categories)

        response = DiffSummaryResponse(
            bullets=bullets,
            risk_level=risk_level,
            risk_explanation=risk_explanation,
            evidence_map=evidence_map,
            change_categories=change_categories,
            is_new_workflow=diff_status == DiffStatus.ADDED,
            cached=False,
        )

        # Cache the response
        if diff_hash:
            _diff_summary_cache[diff_hash] = response

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate diff summary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate diff summary: {str(e)}"
        )


@router.post("/initiate", response_model=PromotionInitiateResponse)
async def initiate_deployment(
    request: PromotionInitiateRequest,
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Initiate a promotion - simplified version that creates the promotion record quickly.
    Heavy operations (snapshots, drift checks) are done during execution.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        user = user_info.get("user", {})
        user_role = user.get("role", "user")
        
        # Get pipeline
        pipeline_data = await db_service.get_pipeline(request.pipeline_id, tenant_id)
        if not pipeline_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )

        # Find the active stage for this source -> target
        active_stage = None
        for stage in pipeline_data.get("stages", []):
            if (stage.get("source_environment_id") == request.source_environment_id and
                stage.get("target_environment_id") == request.target_environment_id):
                active_stage = stage
                break

        if not active_stage:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No stage found for this source -> target environment pair"
            )
        
        # Get source and target environments for guard checks
        source_env = await db_service.get_environment(request.source_environment_id, tenant_id)
        target_env = await db_service.get_environment(request.target_environment_id, tenant_id)
        
        if not source_env or not target_env:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source or target environment not found"
            )
        
        # Check action guard for deploy outbound (from source)
        source_env_class_str = source_env.get("environment_class", "dev")
        try:
            source_env_class = EnvironmentClass(source_env_class_str)
        except ValueError:
            source_env_class = EnvironmentClass.DEV
        
        try:
            environment_action_guard.assert_can_perform_action(
                env_class=source_env_class,
                action=EnvironmentAction.DEPLOY_OUTBOUND,
                user_role=user_role,
                environment_name=source_env.get("n8n_name", request.source_environment_id)
            )
        except ActionGuardError as e:
            raise e
        
        # Check action guard for deploy inbound (to target)
        target_env_class_str = target_env.get("environment_class", "dev")
        try:
            target_env_class = EnvironmentClass(target_env_class_str)
        except ValueError:
            target_env_class = EnvironmentClass.DEV
        
        try:
            environment_action_guard.assert_can_perform_action(
                env_class=source_env_class,
                action=EnvironmentAction.DEPLOY_INBOUND,
                user_role=user_role,
                target_env_class=target_env_class,
                environment_name=target_env.get("n8n_name", request.target_environment_id)
            )
        except ActionGuardError as e:
            raise e

        # Check drift policy blocking for target environment
        drift_block = await check_drift_policy_blocking(
            tenant_id=tenant_id,
            target_environment_id=request.target_environment_id
        )
        if drift_block.get("blocked"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "deployment_blocked_by_drift_policy",
                    "reason": drift_block.get("reason"),
                    **drift_block.get("details", {})
                }
            )

        # Run credential preflight check
        preflight_result = None
        workflow_ids = [ws.workflow_id for ws in request.workflow_selections if ws.selected]
        provider = source_env.get("provider", "n8n") or "n8n"
        
        if workflow_ids:
            try:
                from app.api.endpoints.admin_credentials import credential_preflight_check
                from app.schemas.credential import CredentialPreflightRequest
                
                preflight_request = CredentialPreflightRequest(
                    source_environment_id=request.source_environment_id,
                    target_environment_id=request.target_environment_id,
                    workflow_ids=workflow_ids,
                    provider=provider
                )
                preflight_result = await credential_preflight_check(
                    body=preflight_request,
                    user_info=user_info
                )
                
                # Block promotion if there are blocking issues
                if not preflight_result.valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "credential_preflight_failed",
                            "blocking_issues": [issue.dict() for issue in preflight_result.blocking_issues],
                            "warnings": [issue.dict() for issue in preflight_result.warnings],
                            "resolved_mappings": [mapping.dict() for mapping in preflight_result.resolved_mappings]
                        }
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Preflight check failed (non-blocking): {e}")
                # Don't block promotion if preflight fails, but log it

        # Check if approval required
        requires_approval = active_stage.get("approvals", {}).get("require_approval", False)

        # Create promotion record immediately
        promotion_id = str(uuid4())

        # Simple gate results (actual checks done during execution)
        gate_results = GateResult(
            require_clean_drift=active_stage.get("gates", {}).get("require_clean_drift", False),
            drift_detected=False,
            drift_resolved=True,
            run_pre_flight_validation=active_stage.get("gates", {}).get("run_pre_flight_validation", False),
            credentials_exist=True,
            nodes_supported=True,
            webhooks_available=True,
            target_environment_healthy=True,
            risk_level_allowed=True,
            errors=[],
            warnings=[],
            credential_issues=[]
        )

        promotion_data = {
            "id": promotion_id,
            "tenant_id": tenant_id,
            "pipeline_id": request.pipeline_id,
            "source_environment_id": request.source_environment_id,
            "target_environment_id": request.target_environment_id,
            "status": PromotionStatus.PENDING_APPROVAL.value if requires_approval else PromotionStatus.PENDING.value,
            "source_snapshot_id": None,  # Created during execution
            "workflow_selections": [ws.dict() for ws in request.workflow_selections],
            "gate_results": gate_results.dict(),
            "created_by": user.get("id"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Store promotion
        await db_service.create_promotion(promotion_data)

        # TODO: Re-enable notification once core flow is working
        # try:
        #     await notification_service.emit_event(...)
        # except Exception as e:
        #     logger.error(f"Failed to emit promotion.started event: {str(e)}")

        return PromotionInitiateResponse(
            promotion_id=promotion_id,
            status=PromotionStatus.PENDING_APPROVAL if requires_approval else PromotionStatus.PENDING,
            gate_results=gate_results,
            requires_approval=requires_approval,
            approval_id=str(uuid4()) if requires_approval else None,
            dependency_warnings={},
            preflight=preflight_result.dict() if preflight_result else {
                "credential_issues": [],
                "dependency_warnings": {},
                "drift_detected": False,
                "valid": True,
                "blocking_issues": [],
                "warnings": [],
                "resolved_mappings": []
            },
            message="Promotion initiated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate promotion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate promotion: {str(e)}"
        )


async def _execute_promotion_background(
    job_id: str,
    promotion_id: str,
    deployment_id: str,
    promotion: dict,
    source_env: dict,
    target_env: dict,
    selected_workflows: list,
    tenant_id: str
):
    """
    Background task to execute promotion - transfers workflows from source to target.
    Updates job progress as it processes workflows.
    """
    from app.services.provider_registry import ProviderRegistry
    from app.schemas.deployment import DeploymentStatus, WorkflowChangeType, WorkflowStatus

    total_workflows = len(selected_workflows)
    
    try:
        # Update job status to running
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING,
            progress={"current": 0, "total": total_workflows, "percentage": 0, "message": "Starting promotion execution"}
        )

        # Get provider from environments (default to n8n for backward compatibility)
        source_provider = source_env.get("provider", "n8n") or "n8n"
        target_provider = target_env.get("provider", "n8n") or "n8n"
        
        # Create provider adapters using ProviderRegistry
        logger.info(f"[Job {job_id}] Creating provider adapters - Source: {source_provider}, Target: {target_provider}")
        source_adapter = ProviderRegistry.get_adapter_for_environment(source_env)
        target_adapter = ProviderRegistry.get_adapter_for_environment(target_env)
        
        # Test connections before proceeding
        logger.info(f"[Job {job_id}] Testing source environment connection...")
        source_connected = await source_adapter.test_connection()
        if not source_connected:
            raise ValueError(f"Failed to connect to source environment")
        logger.info(f"[Job {job_id}] Source environment connection successful")
        
        logger.info(f"[Job {job_id}] Testing target environment connection...")
        target_connected = await target_adapter.test_connection()
        if not target_connected:
            raise ValueError(f"Failed to connect to target environment")
        logger.info(f"[Job {job_id}] Target environment connection successful")

        # NOTE: deployment_workflows records are pre-created in execute_promotion() before this task starts
        # This ensures workflow records exist even if this background job fails early
        logger.info(f"[Job {job_id}] Starting transfer of {total_workflows} workflows (records already created)")

        # Transfer each workflow
        created_count = 0
        updated_count = 0
        failed_count = 0
        skipped_count = 0
        unchanged_count = 0
        workflow_results = []

        for idx, ws in enumerate(selected_workflows, 1):
            workflow_id = ws.get("workflow_id")
            workflow_name = ws.get("workflow_name")
            change_type = ws.get("change_type", "new")
            error_message = None
            status_result = WorkflowStatus.SUCCESS

            try:
                # Update progress
                await background_job_service.update_progress(
                    job_id=job_id,
                    current=idx,
                    total=total_workflows,
                    message=f"Processing workflow: {workflow_name}"
                )

                # Fetch workflow from source
                logger.info(f"[Job {job_id}] Fetching workflow {workflow_id} ({workflow_name}) from source environment {source_env.get('n8n_name', source_env.get('id'))}")
                source_workflow = await source_adapter.get_workflow(workflow_id)
                
                if not source_workflow:
                    raise ValueError(f"Workflow {workflow_id} not found in source environment")

                # Prepare workflow data for target (remove source-specific fields)
                workflow_data = {
                    "name": source_workflow.get("name"),
                    "nodes": source_workflow.get("nodes", []),
                    "connections": source_workflow.get("connections", {}),
                    "settings": source_workflow.get("settings", {}),
                    "staticData": source_workflow.get("staticData"),
                }
                
                logger.info(f"[Job {job_id}] Prepared workflow data for {workflow_name}: {len(workflow_data.get('nodes', []))} nodes")

                # Try to find existing workflow in target by name
                logger.info(f"[Job {job_id}] Checking for existing workflow '{workflow_name}' in target environment {target_env.get('n8n_name', target_env.get('id'))}")
                target_workflows = await target_adapter.get_workflows()
                logger.info(f"[Job {job_id}] Found {len(target_workflows)} existing workflows in target environment")
                existing_workflow = next(
                    (w for w in target_workflows if w.get("name") == workflow_name),
                    None
                )

                if existing_workflow:
                    # Update existing workflow
                    logger.info(f"[Job {job_id}] Updating existing workflow '{workflow_name}' (ID: {existing_workflow.get('id')}) in target")
                    result = await target_adapter.update_workflow(existing_workflow.get("id"), workflow_data)
                    logger.info(f"[Job {job_id}] Successfully updated workflow '{workflow_name}' in target environment")
                    updated_count += 1
                    change_type = "changed"
                else:
                    # Create new workflow
                    logger.info(f"[Job {job_id}] Creating new workflow '{workflow_name}' in target environment")
                    result = await target_adapter.create_workflow(workflow_data)
                    logger.info(f"[Job {job_id}] Successfully created workflow '{workflow_name}' (ID: {result.get('id', 'unknown')}) in target environment")
                    created_count += 1
                    change_type = "new"

            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                error_message = str(e)
                
                # Log detailed error information
                logger.error(f"[Job {job_id}] Failed to transfer workflow {workflow_name}: {error_message}")
                logger.error(f"[Job {job_id}] Error type: {type(e).__name__}")
                if hasattr(e, 'errno') and e.errno == 22:
                    logger.error(f"[Job {job_id}] Windows errno 22 (Invalid argument) - check for invalid characters in workflow data")
                logger.error(f"[Job {job_id}] Traceback: {error_traceback}")
                
                # Truncate error message if too long for database
                if len(error_message) > 500:
                    error_message = error_message[:500] + "..."
                
                status_result = WorkflowStatus.FAILED
                failed_count += 1

            # Update workflow record (already pre-created with PENDING status)
            wf_change_type_map = {
                "new": WorkflowChangeType.CREATED,
                "changed": WorkflowChangeType.UPDATED,
                "staging_hotfix": WorkflowChangeType.UPDATED,
                "conflict": WorkflowChangeType.SKIPPED,
                "unchanged": WorkflowChangeType.UNCHANGED,
            }
            wf_change_type = wf_change_type_map.get(change_type, WorkflowChangeType.UPDATED)

            workflow_update = {
                "change_type": wf_change_type.value,
                "status": status_result.value,
                "error_message": error_message,
            }
            await db_service.update_deployment_workflow(deployment_id, workflow_id, workflow_update)
            workflow_results.append({
                "deployment_id": deployment_id,
                "workflow_id": workflow_id,
                "workflow_name_at_time": workflow_name,
                **workflow_update
            })

            # Update deployment's updated_at timestamp and running summary so UI can see progress
            await db_service.update_deployment(deployment_id, {
                "summary_json": {
                    "total": total_workflows,
                    "created": created_count,
                    "updated": updated_count,
                    "deleted": 0,
                    "failed": failed_count,
                    "skipped": skipped_count,
                    "unchanged": unchanged_count,
                    "processed": idx,
                    "current_workflow": workflow_name
                }
            })

            # Emit SSE progress event
            try:
                await emit_deployment_progress(
                    deployment_id=deployment_id,
                    progress_current=idx,
                    progress_total=total_workflows,
                    current_workflow_name=workflow_name,
                    tenant_id=tenant_id
                )
            except Exception as sse_error:
                logger.warning(f"Failed to emit SSE progress event: {str(sse_error)}")

        # Calculate final summary
        summary_json = {
            "total": total_workflows,
            "created": created_count,
            "updated": updated_count,
            "deleted": 0,
            "failed": failed_count,
            "skipped": skipped_count,
            "unchanged": unchanged_count,
            "processed": total_workflows,
        }

        # Determine final status
        final_status = DeploymentStatus.SUCCESS if failed_count == 0 else DeploymentStatus.FAILED

        # Update deployment with results
        await db_service.update_deployment(deployment_id, {
            "status": final_status.value,
            "finished_at": datetime.utcnow().isoformat(),
            "summary_json": summary_json,
        })

        # Emit SSE events for deployment completion
        try:
            # Fetch updated deployment for full data
            updated_deployment = await db_service.get_deployment(deployment_id, tenant_id)
            if updated_deployment:
                await emit_deployment_upsert(updated_deployment, tenant_id)
            await emit_counts_update(tenant_id)
        except Exception as sse_error:
            logger.warning(f"Failed to emit SSE event for deployment completion: {str(sse_error)}")

        # Update promotion as completed
        promotion_status = "completed" if failed_count == 0 else "failed"
        await db_service.update_promotion(promotion_id, tenant_id, {
            "status": promotion_status,
            "completed_at": datetime.utcnow().isoformat()
        })

        # Update job as completed
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.COMPLETED if failed_count == 0 else BackgroundJobStatus.FAILED,
            progress={"current": total_workflows, "total": total_workflows, "percentage": 100},
            result={
                "deployment_id": deployment_id,
                "summary": summary_json,
                "workflow_results": workflow_results
            },
            error_message=None if failed_count == 0 else f"{failed_count} workflow(s) failed"
        )

        logger.info(f"Promotion {promotion_id} completed: {created_count} created, {updated_count} updated, {failed_count} failed")

    except Exception as e:
        logger.error(f"Background promotion execution failed: {str(e)}")
        error_msg = str(e)
        
        # Update job as failed
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=error_msg,
            error_details={"exception_type": type(e).__name__, "traceback": str(e)}
        )
        
        # Update promotion and deployment status to failed
        try:
            await db_service.update_promotion(promotion_id, tenant_id, {
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat()
            })
            await db_service.update_deployment(deployment_id, {
                "status": "failed",
                "finished_at": datetime.utcnow().isoformat(),
                "summary_json": {
                    "total": total_workflows,
                    "created": 0,
                    "updated": 0,
                    "deleted": 0,
                    "failed": total_workflows,
                    "skipped": 0,
                    "error": error_msg
                },
            })
            # Emit SSE events for deployment failure
            try:
                updated_deployment = await db_service.get_deployment(deployment_id, tenant_id)
                if updated_deployment:
                    await emit_deployment_upsert(updated_deployment, tenant_id)
                await emit_counts_update(tenant_id)
            except Exception as sse_error:
                logger.warning(f"Failed to emit SSE event for deployment failure: {str(sse_error)}")
        except Exception as update_error:
            logger.error(f"Failed to update promotion/deployment status: {str(update_error)}")


@router.post("/execute/{deployment_id}")
async def execute_deployment(
    deployment_id: str,
    request: Optional[PromotionExecuteRequest] = None,
    background_tasks: BackgroundTasks = None,
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Execute a deployment - creates deployment and starts background execution.
    If scheduled_at is provided, deployment will be scheduled for that time.
    Otherwise, executes immediately.
    Returns immediately with job_id for tracking progress.
    """
    from app.schemas.deployment import DeploymentStatus
    
    # Handle optional request body
    scheduled_at = None
    if request and request.scheduled_at:
        scheduled_at = request.scheduled_at
        # Validate scheduled_at is in the future
        if scheduled_at <= datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="scheduled_at must be in the future"
            )

    try:
        tenant_id = get_tenant_id(user_info)
        # The deployment_id parameter is actually the promotion_id from the initiate step
        # We'll create a new deployment_id later, so alias this correctly
        promotion_id = deployment_id

        # Get promotion record (still uses promotion_id in DB)
        promotion = await db_service.get_promotion(promotion_id, tenant_id)
        if not promotion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Promotion not found"
            )

        # Check status
        if promotion.get("status") not in ["pending", "approved"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Promotion cannot be executed in status: {promotion.get('status')}"
            )

        # Get source and target environments
        source_env = await db_service.get_environment(promotion.get("source_environment_id"), tenant_id)
        target_env = await db_service.get_environment(promotion.get("target_environment_id"), tenant_id)

        if not source_env or not target_env:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source or target environment not found"
            )

        # Re-check drift policy blocking before execution (may have changed since initiation)
        drift_block = await check_drift_policy_blocking(
            tenant_id=tenant_id,
            target_environment_id=promotion.get("target_environment_id")
        )
        if drift_block.get("blocked"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "deployment_blocked_by_drift_policy",
                    "reason": drift_block.get("reason"),
                    **drift_block.get("details", {})
                }
            )

        # Get selected workflows
        workflow_selections = promotion.get("workflow_selections", [])
        selected_workflows = [ws for ws in workflow_selections if ws.get("selected")]

        if not selected_workflows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No workflows selected for promotion"
            )

        # Create background job (link to both promotion and deployment)
        job = await background_job_service.create_job(
            tenant_id=tenant_id,
            job_type=BackgroundJobType.PROMOTION_EXECUTE,
            resource_id=promotion_id,
            resource_type="promotion",
            created_by=promotion.get("created_by") or "00000000-0000-0000-0000-000000000000",
            initial_progress={
                "current": 0,
                "total": len(selected_workflows),
                "percentage": 0,
                "message": "Initializing promotion execution"
            }
        )
        job_id = job["id"]

        # Determine deployment status and timing
        is_scheduled = scheduled_at is not None
        deployment_status = DeploymentStatus.SCHEDULED.value if is_scheduled else DeploymentStatus.RUNNING.value
        
        # Update promotion status
        if is_scheduled:
            # Keep promotion as pending until scheduled execution
            await db_service.update_promotion(promotion_id, tenant_id, {
                "status": PromotionStatus.PENDING.value,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None
            })
        else:
            await db_service.update_promotion(promotion_id, tenant_id, {"status": "running"})

        # Create deployment record
        deployment_id = str(uuid4())
        deployment_data = {
            "id": deployment_id,
            "tenant_id": tenant_id,
            "pipeline_id": promotion.get("pipeline_id"),
            "source_environment_id": promotion.get("source_environment_id"),
            "target_environment_id": promotion.get("target_environment_id"),
            "status": deployment_status,
            "triggered_by_user_id": promotion.get("created_by") or "00000000-0000-0000-0000-000000000000",
            "approved_by_user_id": None,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            "started_at": datetime.utcnow().isoformat() if not is_scheduled else None,
            "finished_at": None,
            "pre_snapshot_id": None,
            "post_snapshot_id": None,
            "summary_json": {"total": len(selected_workflows), "created": 0, "updated": 0, "deleted": 0, "failed": 0, "skipped": 0},
        }
        await db_service.create_deployment(deployment_data)

        # Pre-create all deployment_workflows records BEFORE background task
        # This ensures workflow records exist even if background job fails early (e.g., connection failure)
        # Without this, failed deployments have no workflows and cannot be rerun
        # NOTE: Don't set status here - database default will be used
        from app.schemas.deployment import WorkflowChangeType
        change_type_map = {
            "new": WorkflowChangeType.CREATED,
            "changed": WorkflowChangeType.UPDATED,
            "staging_hotfix": WorkflowChangeType.UPDATED,
            "conflict": WorkflowChangeType.SKIPPED,
            "unchanged": WorkflowChangeType.UNCHANGED,
        }
        pending_workflows = []
        for ws in selected_workflows:
            wf_change_type = change_type_map.get(ws.get("change_type", "new"), WorkflowChangeType.CREATED)
            pending_workflows.append({
                "deployment_id": deployment_id,
                "workflow_id": ws.get("workflow_id"),
                "workflow_name_at_time": ws.get("workflow_name"),
                "change_type": wf_change_type.value,
                # status will use database default, updated to success/failed during processing
            })

        if pending_workflows:
            await db_service.create_deployment_workflows_batch(pending_workflows)
            logger.info(f"Created {len(pending_workflows)} deployment_workflow records for deployment {deployment_id}")

        # Emit SSE events for new deployment
        try:
            await emit_deployment_upsert(deployment_data, tenant_id)
            await emit_counts_update(tenant_id)
        except Exception as sse_error:
            logger.warning(f"Failed to emit SSE event for deployment creation: {str(sse_error)}")

        # Create audit log for deployment creation
        try:
            provider = source_env.get("provider", "n8n") or "n8n"
            await create_audit_log(
                action_type="DEPLOYMENT_CREATED",
                action=f"Created deployment for {len(selected_workflows)} workflow(s)",
                actor_id=promotion.get("created_by") or "00000000-0000-0000-0000-000000000000",
                tenant_id=tenant_id,
                resource_type="deployment",
                resource_id=deployment_id,
                resource_name=f"Deployment {deployment_id[:8]}",
                provider=provider,
                new_value={
                    "deployment_id": deployment_id,
                    "promotion_id": promotion_id,
                    "status": DeploymentStatus.RUNNING.value,
                    "workflow_count": len(selected_workflows),
                    "source_environment_id": promotion.get("source_environment_id"),
                    "target_environment_id": promotion.get("target_environment_id"),
                    "pipeline_id": promotion.get("pipeline_id"),
                },
                metadata={
                    "job_id": job_id,
                    "workflow_selections": [{"workflow_id": ws.get("workflow_id"), "workflow_name": ws.get("workflow_name")} for ws in selected_workflows]
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to create audit log for deployment creation: {str(audit_error)}")
        
        # Update job with deployment_id in result for tracking
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.PENDING if is_scheduled else BackgroundJobStatus.PENDING,
            result={"deployment_id": deployment_id, "scheduled_at": scheduled_at.isoformat() if scheduled_at else None}
        )

        # Start background execution task only if not scheduled
        if not is_scheduled:
            if background_tasks is None:
                # If BackgroundTasks not injected, create task directly
                import asyncio
                asyncio.create_task(
                    _execute_promotion_background(
                        job_id=job_id,
                        promotion_id=promotion_id,
                        deployment_id=deployment_id,
                        promotion=promotion,
                        source_env=source_env,
                        target_env=target_env,
                        selected_workflows=selected_workflows,
                        tenant_id=tenant_id
                    )
                )
            else:
                # FastAPI BackgroundTasks.add_task() supports async functions directly
                background_tasks.add_task(
                    _execute_promotion_background,
                    job_id=job_id,
                    promotion_id=promotion_id,
                    deployment_id=deployment_id,
                    promotion=promotion,
                    source_env=source_env,
                    target_env=target_env,
                    selected_workflows=selected_workflows,
                    tenant_id=tenant_id
                )
            logger.info(f"[Job {job_id}] Background task added for promotion {promotion_id}, deployment {deployment_id}")
        else:
            logger.info(f"[Job {job_id}] Deployment {deployment_id} scheduled for {scheduled_at}")

        # Return immediately with job info
        status_msg = "scheduled" if is_scheduled else "running"
        message = (
            f"Deployment scheduled for {scheduled_at.strftime('%Y-%m-%d %H:%M:%S UTC')}. "
            f"Processing {len(selected_workflows)} workflow(s) will begin at that time."
            if is_scheduled
            else f"Promotion execution started. Processing {len(selected_workflows)} workflow(s) in the background."
        )
        
        return {
            "job_id": job_id,
            "promotion_id": promotion_id,
            "deployment_id": deployment_id,
            "status": status_msg,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            "message": message
        }

    except HTTPException:
        raise
    except Exception as e:
        # Update promotion status to failed
        try:
            await db_service.update_promotion(promotion_id, tenant_id, {
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat()
            })
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute promotion: {str(e)}"
        )


@router.get("/{promotion_id}/job")
async def get_promotion_job(
    promotion_id: str,
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get the latest background job status for a promotion execution.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get the latest job for this promotion
        job = await background_job_service.get_latest_job_by_resource(
            resource_type="promotion",
            resource_id=promotion_id,
            tenant_id=tenant_id
        )

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No job found for this promotion"
            )

        return {
            "job_id": job.get("id"),
            "promotion_id": promotion_id,
            "status": job.get("status"),
            "progress": job.get("progress", {}),
            "result": job.get("result", {}),
            "error_message": job.get("error_message"),
            "error_details": job.get("error_details", {}),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "created_at": job.get("created_at")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get promotion job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get promotion job: {str(e)}"
        )


@router.post("/approvals/{promotion_id}/approve")
async def approve_deployment(
    promotion_id: str,
    request: PromotionApprovalRequest,
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Approve or reject a pending promotion.
    Supports multi-approver workflows (1 of N / All).
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get promotion (still uses promotion_id in DB)
        promotion = await db_service.get_promotion(promotion_id, tenant_id)
        if not promotion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Promotion not found"
            )
        promotion_id = promotion.get("id") or promotion_id
        
        if promotion.get("status") != "pending_approval":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Promotion is not pending approval (status: {promotion.get('status')})"
            )
        
        # Get pipeline and stage for approval requirements
        pipeline = await db_service.get_pipeline(promotion.get("pipeline_id"), tenant_id)
        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        
        # Find active stage
        active_stage = None
        for stage in pipeline.get("stages", []):
            if (stage.get("source_environment_id") == promotion.get("source_environment_id") and
                stage.get("target_environment_id") == promotion.get("target_environment_id")):
                active_stage = stage
                break
        
        if not active_stage:
            raise HTTPException(status_code=400, detail="Active stage not found")
        
        approvals_config = active_stage.get("approvals", {})
        required_approvals_type = approvals_config.get("required_approvals", "1 of N")
        
        # Get existing approvals for this promotion
        existing_approvals = promotion.get("approvals", []) or []
        user = user_info.get("user") or {}
        approver_id = user.get("id") or "current_user"
        
        if request.action == "reject":
            # Rejection requires comment
            if not request.comment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Rejection comment is required"
                )
            
            # Update promotion to rejected
            await db_service.update_promotion(promotion_id, tenant_id, {
                "status": "rejected",
                "rejection_reason": request.comment,
                "rejected_by": approver_id,
                "rejected_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat()
            })
            
            # Emit promotion.blocked event for rejection
            try:
                await notification_service.emit_event(
                    tenant_id=tenant_id,
                    event_type="promotion.blocked",
                    environment_id=promotion.get("target_environment_id"),
                    metadata={
                        "promotion_id": promotion_id,
                        "pipeline_id": promotion.get("pipeline_id"),
                        "source_environment_id": promotion.get("source_environment_id"),
                        "target_environment_id": promotion.get("target_environment_id"),
                        "reason": "rejected",
                        "rejection_reason": request.comment,
                        "rejected_by": approver_id
                    }
                )
            except Exception as e:
                logger.error(f"Failed to emit promotion.blocked event: {str(e)}")
            
            # Create audit log
            await promotion_service._create_audit_log(
                tenant_id=tenant_id,
                promotion_id=promotion_id,
                action="reject",
                result={"reason": request.comment, "rejected_by": approver_id}
            )
            
            return {
                "id": promotion_id,
                "action": "reject",
                "status": "rejected",
                "message": "Promotion rejected"
            }
        
        # Approval
        # Check if user already approved
        if any(approval.get("approver_id") == approver_id for approval in existing_approvals):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already approved this promotion"
            )
        
        # Add approval record
        new_approval = {
            "approver_id": approver_id,
            "approved_at": datetime.utcnow().isoformat(),
            "comment": request.comment
        }
        existing_approvals.append(new_approval)
        
        # Check if enough approvals
        approval_count = len(existing_approvals)
        needs_more_approvals = False
        
        if required_approvals_type == "All":
            # Would need to know total required approvers from role/group
            # For now, assume 1 approval is enough if "All" is not strictly enforced
            approver_role = approvals_config.get("approver_role")
            approver_group = approvals_config.get("approver_group")
            # Simplified: if role/group specified, might need multiple approvers
            # In production, would query users with that role/group
            needs_more_approvals = False  # Simplified for MVP
        else:  # "1 of N"
            # At least 1 approval needed
            needs_more_approvals = approval_count < 1
        
        if needs_more_approvals:
            # Update promotion with approval but keep pending
            await db_service.update_promotion(promotion_id, tenant_id, {
                "approvals": existing_approvals,
                "updated_at": datetime.utcnow().isoformat()
            })
            
            # Create audit log
            await promotion_service._create_audit_log(
                tenant_id=tenant_id,
                promotion_id=promotion_id,
                action="approve",
                result={"approval_count": approval_count, "approver": approver_id}
            )
            
            return {
                "id": promotion_id,
                "action": "approve",
                "status": "pending_approval",
                "approval_count": approval_count,
                "message": "Approval recorded. Waiting for additional approvals."
            }
        else:
            # All approvals received - update to approved
            await db_service.update_promotion(promotion_id, tenant_id, {
                "status": "approved",
                "approvals": existing_approvals,
                "approved_by": approver_id,
                "approved_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            })
            
            # Create audit log
            await promotion_service._create_audit_log(
                tenant_id=tenant_id,
                promotion_id=promotion_id,
                action="approve_final",
                result={"approval_count": approval_count, "approver": approver_id, "all_approvals_received": True}
            )
            
            # Auto-execute if approved
            try:
                # Call execute_promotion directly (avoid circular import)
                # Get promotion again to ensure we have latest data
                updated_promotion = await db_service.get_promotion(promotion_id, tenant_id)
                
                # Update status to running
                await db_service.update_promotion(promotion_id, tenant_id, {"status": "running"})
                
                # Get pipeline and stage
                pipeline = await db_service.get_pipeline(updated_promotion.get("pipeline_id"), tenant_id)
                active_stage = None
                for stage in pipeline.get("stages", []):
                    if (stage.get("source_environment_id") == updated_promotion.get("source_environment_id") and
                        stage.get("target_environment_id") == updated_promotion.get("target_environment_id")):
                        active_stage = stage
                        break
                
                # Create pre-promotion snapshot
                target_pre_snapshot_id, _ = await promotion_service.create_snapshot(
                    tenant_id=tenant_id,
                    environment_id=updated_promotion.get("target_environment_id"),
                    reason="Pre-promotion snapshot",
                    metadata={"promotion_id": promotion_id}
                )
                
                # Execute promotion
                from app.schemas.pipeline import PipelineStage
                from app.schemas.promotion import WorkflowSelection
                stage_obj = PipelineStage(**active_stage)
                
                gate_results = updated_promotion.get("gate_results", {})
                credential_issues = gate_results.get("credential_issues", [])
                
                execution_result = await promotion_service.execute_promotion(
                    tenant_id=tenant_id,
                    promotion_id=promotion_id,
                    source_env_id=updated_promotion.get("source_environment_id"),
                    target_env_id=updated_promotion.get("target_environment_id"),
                    workflow_selections=[WorkflowSelection(**ws) for ws in updated_promotion.get("workflow_selections", [])],
                    source_snapshot_id=updated_promotion.get("source_snapshot_id", ""),
                    policy_flags=stage_obj.policy_flags.dict(),
                    credential_issues=credential_issues
                )
                
                # Create post-promotion snapshot
                target_post_snapshot_id, _ = await promotion_service.create_snapshot(
                    tenant_id=tenant_id,
                    environment_id=updated_promotion.get("target_environment_id"),
                    reason="Post-promotion snapshot",
                    metadata={"promotion_id": promotion_id, "source_snapshot_id": updated_promotion.get("source_snapshot_id")}
                )
                
                # Update promotion with results
                await db_service.update_promotion(promotion_id, tenant_id, {
                    "status": execution_result.status.value,
                    "target_pre_snapshot_id": target_pre_snapshot_id,
                    "target_post_snapshot_id": target_post_snapshot_id,
                    "execution_result": execution_result.dict(),
                    "completed_at": datetime.utcnow().isoformat()
                })
                
                execution_result.target_pre_snapshot_id = target_pre_snapshot_id
                execution_result.target_post_snapshot_id = target_post_snapshot_id
                return {
                    "id": promotion_id,
                    "action": "approve",
                    "status": "approved",
                    "execution_status": execution_result.get("status") if isinstance(execution_result, dict) else "completed",
                    "message": "Promotion approved and executed"
                }
            except Exception as e:
                logger.error(f"Auto-execution failed after approval: {str(e)}")
                return {
                    "id": promotion_id,
                    "action": "approve",
                    "status": "approved",
                    "message": f"Promotion approved but execution failed: {str(e)}"
                }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process approval: {str(e)}"
        )


@router.get("/", response_model=PromotionListResponse)
async def list_promotions(
    status_filter: Optional[str] = None,
    limit: int = 20,
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    List all promotions for the tenant.
    """
    # Placeholder - would query database
    return PromotionListResponse(
        data=[],
        total=0
    )


@router.get("/workflows/{workflow_id}/diff")
async def get_workflow_diff(
    workflow_id: str,
    source_environment_id: str = Query(..., description="Source environment ID"),
    target_environment_id: str = Query(..., description="Target environment ID"),
    source_snapshot_id: Optional[str] = Query(None, description="Source snapshot ID (defaults to latest)"),
    target_snapshot_id: Optional[str] = Query(None, description="Target snapshot ID (defaults to latest)"),
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get detailed diff for a single workflow between source and target environments.
    Returns structured diff result with differences and summary.
    """
    logger.info(f"[WORKFLOW_DIFF] Route hit! workflow_id={workflow_id}, source={source_environment_id}, target={target_environment_id}")
    try:
        tenant_id = get_tenant_id(user_info)
        if not source_environment_id or not target_environment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_environment_id and target_environment_id are required"
            )
        
        # If no snapshot IDs provided, use "latest" (will use latest from GitHub)
        source_snap = source_snapshot_id or "latest"
        target_snap = target_snapshot_id or "latest"
        
        diff_result = await promotion_service.get_workflow_diff(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            source_env_id=source_environment_id,
            target_env_id=target_environment_id,
            source_snapshot_id=source_snap,
            target_snapshot_id=target_snap
        )

        return {
            "data": diff_result
        }

    except ValueError as e:
        logger.error(f"ValueError in get_workflow_diff: {str(e)}")
        msg = str(e)
        # Environment type missing is a configuration/user error, not "not found"
        if "Environment type is required" in msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception in get_workflow_diff: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow diff: {str(e)}"
        )


@router.get("/initiate/{promotion_id}", response_model=PromotionDetail)
async def get_promotion(
    promotion_id: str,
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Get details of a specific promotion.
    """
    tenant_id = get_tenant_id(user_info)
    try:
        promo = await db_service.get_promotion(promotion_id, tenant_id)
        if not promo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Promotion not found"
            )
        
        # Get pipeline and environment names
        pipeline = await db_service.get_pipeline(promo.get("pipeline_id"), tenant_id)
        source_env = await db_service.get_environment(promo.get("source_environment_id"), tenant_id)
        target_env = await db_service.get_environment(promo.get("target_environment_id"), tenant_id)
        
        return {
            "id": promo.get("id"),
            "tenant_id": promo.get("tenant_id"),
            "pipeline_id": promo.get("pipeline_id"),
            "pipeline_name": pipeline.get("name") if pipeline else "Unknown",
            "source_environment_id": promo.get("source_environment_id"),
            "source_environment_name": source_env.get("n8n_name") if source_env else "Unknown",
            "target_environment_id": promo.get("target_environment_id"),
            "target_environment_name": target_env.get("n8n_name") if target_env else "Unknown",
            "status": promo.get("status"),
            "source_snapshot_id": promo.get("source_snapshot_id"),
            "target_pre_snapshot_id": promo.get("target_pre_snapshot_id"),
            "target_post_snapshot_id": promo.get("target_post_snapshot_id"),
            "workflow_selections": promo.get("workflow_selections", []),
            "gate_results": promo.get("gate_results"),
            "created_by": promo.get("created_by"),
            "approved_by": promo.get("approved_by"),
            "approved_at": promo.get("approved_at"),
            "rejection_reason": promo.get("rejection_reason"),
            "execution_result": promo.get("execution_result"),
            "created_at": promo.get("created_at"),
            "updated_at": promo.get("updated_at"),
            "completed_at": promo.get("completed_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get promotion: {str(e)}"
        )


@router.post("/snapshots", response_model=PromotionSnapshotResponse)
async def create_snapshot(
    request: PromotionSnapshotRequest,
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Create a snapshot of an environment (used for drift checking).
    """
    try:
        tenant_id = get_tenant_id(user_info)
        snapshot_id, commit_sha = await promotion_service.create_snapshot(
            tenant_id=tenant_id,
            environment_id=request.environment_id,
            reason=request.reason,
            metadata=request.metadata
        )

        return PromotionSnapshotResponse(
            snapshot_id=snapshot_id,
            commit_sha=commit_sha,
            workflows_count=0,  # Would get from snapshot
            created_at=datetime.utcnow()
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create snapshot: {str(e)}"
        )


@router.post("/check-drift")
async def check_drift(
    environment_id: str,
    snapshot_id: str,
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    Check if an environment has drifted from its snapshot.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        drift_check = await promotion_service.check_drift(
            tenant_id=tenant_id,
            environment_id=environment_id,
            snapshot_id=snapshot_id
        )

        return drift_check

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check drift: {str(e)}"
        )


@router.post("/compare-workflows", deprecated=True)
async def compare_workflows(
    request: dict,
    user_info: dict = Depends(get_current_user),
    _: None = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    DEPRECATED: Use GET /promotions/compare instead.

    Compare workflows between source and target environments.
    Returns list of workflow selections with change types.

    This endpoint is deprecated and will be removed in a future version.
    Use GET /promotions/compare?pipeline_id=...&stage_id=... for authoritative
    diff status with semantic categories and risk levels.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        source_environment_id = request.get("source_environment_id")
        target_environment_id = request.get("target_environment_id")
        source_snapshot_id = request.get("source_snapshot_id")
        target_snapshot_id = request.get("target_snapshot_id")
        
        if not source_environment_id or not target_environment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_environment_id and target_environment_id are required"
            )
        
        # If no snapshot IDs provided, use "latest" (will use latest from GitHub)
        source_snap = source_snapshot_id or "latest"
        target_snap = target_snapshot_id or "latest"
        
        selections = await promotion_service.compare_workflows(
            tenant_id=tenant_id,
            source_env_id=source_environment_id,
            target_env_id=target_environment_id,
            source_snapshot_id=source_snap,
            target_snapshot_id=target_snap
        )

        return {
            "data": [ws.dict() for ws in selections]
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare workflows: {str(e)}"
        )
