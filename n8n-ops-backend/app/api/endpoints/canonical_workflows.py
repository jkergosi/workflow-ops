"""
API endpoints for canonical workflow system
"""
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
import logging
import asyncio

from app.schemas.canonical_workflow import (
    CanonicalWorkflowResponse,
    WorkflowEnvMapResponse,
    WorkflowDiffStateResponse,
    WorkflowLinkSuggestionResponse,
    OnboardingPreflightResponse,
    OnboardingInventoryRequest,
    OnboardingInventoryResponse,
    MigrationPRRequest,
    MigrationPRResponse,
    OnboardingCompleteCheck,
    WorkflowMappingStatus
)
from app.schemas.pagination import PaginatedResponse, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.services.canonical_workflow_service import CanonicalWorkflowService
from app.services.canonical_repo_sync_service import CanonicalRepoSyncService
from app.services.canonical_env_sync_service import CanonicalEnvSyncService
from app.services.canonical_reconciliation_service import CanonicalReconciliationService
from app.services.canonical_onboarding_service import CanonicalOnboardingService
from app.services.database import db_service
from app.services.background_job_service import (
    background_job_service,
    BackgroundJobType,
    BackgroundJobStatus
)
from app.services.sync_orchestrator_service import sync_orchestrator
from app.core.entitlements_gate import require_entitlement
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


def get_tenant_id(user_info: dict) -> str:
    tenant = user_info.get("tenant") or {}
    tenant_id = tenant.get("id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return tenant_id


# Onboarding Endpoints

@router.get("/onboarding/preflight", response_model=OnboardingPreflightResponse)
async def get_onboarding_preflight(
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """Get preflight checks for onboarding"""
    tenant_id = get_tenant_id(user_info)
    return await CanonicalOnboardingService.check_preflight(tenant_id)


@router.post("/onboarding/inventory", response_model=OnboardingInventoryResponse)
async def start_onboarding_inventory(
    request: OnboardingInventoryRequest,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """Start onboarding inventory phase (read-only sync operation)"""
    tenant_id = get_tenant_id(user_info)
    
    # Create background job
    job = await background_job_service.create_job(
        tenant_id=tenant_id,
        job_type=BackgroundJobType.CANONICAL_ONBOARDING_INVENTORY,
        resource_id=request.anchor_environment_id,
        resource_type="onboarding",
        created_by=user_info.get("user_id"),
        metadata={
            "anchor_environment_id": request.anchor_environment_id,
            "environment_configs": request.environment_configs
        }
    )
    
    # Enqueue background task
    background_tasks.add_task(
        _run_onboarding_inventory_background,
        job["id"],
        tenant_id,
        request.anchor_environment_id,
        request.environment_configs
    )
    
    return {
        "job_id": job["id"],
        "status": "pending",
        "message": "Inventory job started"
    }


async def _run_onboarding_inventory_background(
    job_id: str,
    tenant_id: str,
    anchor_environment_id: str,
    environment_configs: List[Dict[str, str]]
):
    """Background task for onboarding inventory"""
    try:
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING
        )
        
        tenant = await db_service.get_tenant(tenant_id)
        tenant_slug = CanonicalOnboardingService._generate_tenant_slug(tenant.get("name", "tenant"))
        
        results = await CanonicalOnboardingService.run_inventory_phase(
            tenant_id=tenant_id,
            anchor_environment_id=anchor_environment_id,
            environment_configs=environment_configs,
            tenant_slug=tenant_slug
        )
        
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.COMPLETED,
            result=results
        )
    except Exception as e:
        logger.error(f"Onboarding inventory failed: {str(e)}")
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=str(e)
        )

        # Emit failure SSE event
        try:
            from app.api.endpoints.sse import emit_sync_progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=None,  # Onboarding is tenant-level
                status="failed",
                current_step="failed",
                current=0,
                total=1,
                message=f"Onboarding inventory failed: {str(e)}",
                tenant_id=tenant_id
            )
        except Exception as sse_err:
            logger.warning(f"Failed to emit SSE failure event: {str(sse_err)}")


@router.post("/onboarding/migration-pr", response_model=MigrationPRResponse)
async def create_migration_pr(
    request: MigrationPRRequest,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_push"))
):
    """Create migration PR for canonical workflows"""
    tenant_id = get_tenant_id(user_info)
    
    try:
        result = await CanonicalOnboardingService.create_migration_pr(
            tenant_id=tenant_id,
            tenant_slug=request.tenant_slug
        )
        return result
    except Exception as e:
        logger.error(f"Failed to create migration PR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/onboarding/complete", response_model=OnboardingCompleteCheck)
async def check_onboarding_complete(
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """Check if onboarding is complete"""
    tenant_id = get_tenant_id(user_info)
    return await CanonicalOnboardingService.check_onboarding_complete(tenant_id)


# Canonical Workflow Endpoints

@router.get("/canonical-workflows", response_model=PaginatedResponse[CanonicalWorkflowResponse])
async def list_canonical_workflows(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    include_deleted: bool = False,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """
    List canonical workflows for tenant with server-side pagination.

    This endpoint returns paginated canonical workflows with collision detection.
    - Returns only the requested page of workflows
    - Performs filtering at the database level
    - Uses standardized pagination envelope

    Query params:
        page: Page number (1-indexed, default 1)
        page_size: Items per page (default 50, max 100)
        include_deleted: Include deleted workflows (default false)

    Returns:
        Standardized pagination envelope:
        {
            "items": [...],
            "total": int,
            "page": int,
            "pageSize": int,
            "totalPages": int,
            "hasMore": bool
        }
    """
    try:
        tenant_id = get_tenant_id(user_info)

        # Limit page_size to prevent abuse
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        # Calculate offset
        offset = (page - 1) * page_size

        # Build query with pagination
        query = (
            db_service.client.table("canonical_workflows")
            .select("*", count="exact")
            .eq("tenant_id", tenant_id)
        )

        if not include_deleted:
            query = query.is_("deleted_at", "null")

        # Add deterministic ordering by created_at DESC
        query = query.order("created_at", desc=True)

        # Apply pagination
        query = query.range(offset, offset + page_size - 1)

        # Execute query
        response = query.execute()

        workflows = response.data or []
        total = response.count if response.count is not None else 0

        # Detect hash collisions across all environments
        # Get all workflow mappings to build hash collision detection map
        all_mappings = await db_service.get_workflow_mappings(tenant_id=tenant_id)

        # Build hash collision detection map per environment
        # Map of environment_id -> content_hash -> list of canonical_ids
        hash_to_canonical_map: Dict[str, Dict[str, List[str]]] = {}
        for mapping in all_mappings:
            env_id = mapping.get("environment_id")
            content_hash = mapping.get("env_content_hash")
            canonical_id = mapping.get("canonical_id")

            if env_id and content_hash and canonical_id:
                if env_id not in hash_to_canonical_map:
                    hash_to_canonical_map[env_id] = {}
                if content_hash not in hash_to_canonical_map[env_id]:
                    hash_to_canonical_map[env_id][content_hash] = []
                if canonical_id not in hash_to_canonical_map[env_id][content_hash]:
                    hash_to_canonical_map[env_id][content_hash].append(canonical_id)

        # Enrich workflows with collision warnings
        for workflow in workflows:
            canonical_id = workflow.get("canonical_id")
            if not canonical_id:
                continue

            # Check for hash collisions across all environments
            collision_warnings = []
            for env_id, hash_map in hash_to_canonical_map.items():
                for content_hash, canonical_ids in hash_map.items():
                    if canonical_id in canonical_ids and len(canonical_ids) > 1:
                        # Collision detected
                        other_workflows = [cid for cid in canonical_ids if cid != canonical_id]
                        collision_warnings.append(
                            f"Environment {env_id}: Hash collision with {len(other_workflows)} other workflow(s) (hash: {content_hash[:12]}...)"
                        )

            # Add collision_warnings field to workflow
            if collision_warnings:
                workflow["collision_warnings"] = collision_warnings
            else:
                workflow["collision_warnings"] = None

        # Return standardized paginated response
        return PaginatedResponse.create(
            items=workflows,
            page=page,
            page_size=page_size,
            total=total
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list canonical workflows: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list canonical workflows: {str(e)}"
        )


@router.get("/canonical-workflows/{canonical_id}", response_model=CanonicalWorkflowResponse)
async def get_canonical_workflow(
    canonical_id: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """Get a canonical workflow by ID with collision warnings"""
    tenant_id = get_tenant_id(user_info)
    workflow = await CanonicalWorkflowService.get_canonical_workflow(
        tenant_id=tenant_id,
        canonical_id=canonical_id
    )
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canonical workflow not found"
        )

    # Detect hash collisions across all environments for this specific workflow
    # Get all workflow mappings for this canonical workflow
    all_mappings = await db_service.get_workflow_mappings(
        tenant_id=tenant_id,
        canonical_id=canonical_id
    )

    # Also get all other mappings to detect collisions
    all_tenant_mappings = await db_service.get_workflow_mappings(tenant_id=tenant_id)

    # Build hash collision detection map per environment
    # Map of environment_id -> content_hash -> list of canonical_ids
    hash_to_canonical_map: Dict[str, Dict[str, List[str]]] = {}
    for mapping in all_tenant_mappings:
        env_id = mapping.get("environment_id")
        content_hash = mapping.get("env_content_hash")
        mapped_canonical_id = mapping.get("canonical_id")

        if env_id and content_hash and mapped_canonical_id:
            if env_id not in hash_to_canonical_map:
                hash_to_canonical_map[env_id] = {}
            if content_hash not in hash_to_canonical_map[env_id]:
                hash_to_canonical_map[env_id][content_hash] = []
            if mapped_canonical_id not in hash_to_canonical_map[env_id][content_hash]:
                hash_to_canonical_map[env_id][content_hash].append(mapped_canonical_id)

    # Check for hash collisions across all environments
    collision_warnings = []
    for env_id, hash_map in hash_to_canonical_map.items():
        for content_hash, canonical_ids in hash_map.items():
            if canonical_id in canonical_ids and len(canonical_ids) > 1:
                # Collision detected
                other_workflows = [cid for cid in canonical_ids if cid != canonical_id]
                collision_warnings.append(
                    f"Environment {env_id}: Hash collision with {len(other_workflows)} other workflow(s) (hash: {content_hash[:12]}...)"
                )

    # Add collision_warnings field to workflow
    if collision_warnings:
        workflow["collision_warnings"] = collision_warnings
    else:
        workflow["collision_warnings"] = None

    return workflow


# Workflow Environment Mapping Endpoints

@router.get("/workflow-mappings", response_model=PaginatedResponse[WorkflowEnvMapResponse])
async def list_workflow_mappings(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    environment_id: Optional[str] = None,
    canonical_id: Optional[str] = None,
    status: Optional[str] = None,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """
    List workflow environment mappings with server-side pagination.

    This endpoint returns paginated workflow environment mappings with filters.
    - Returns only the requested page of mappings
    - Performs filtering at the database level
    - Uses standardized pagination envelope

    Query params:
        page: Page number (1-indexed, default 1)
        page_size: Items per page (default 50, max 100)
        environment_id: Optional filter by environment ID
        canonical_id: Optional filter by canonical workflow ID
        status: Optional filter by mapping status

    Returns:
        Standardized pagination envelope:
        {
            "items": [...],
            "total": int,
            "page": int,
            "pageSize": int,
            "totalPages": int,
            "hasMore": bool
        }
    """
    try:
        tenant_id = get_tenant_id(user_info)

        # Limit page_size to prevent abuse
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        # Calculate offset
        offset = (page - 1) * page_size

        # Build query with pagination
        query = (
            db_service.client.table("workflow_env_map")
            .select("*", count="exact")
            .eq("tenant_id", tenant_id)
        )

        # Apply optional filters
        if environment_id:
            query = query.eq("environment_id", environment_id)
        if canonical_id:
            query = query.eq("canonical_id", canonical_id)
        if status:
            query = query.eq("status", status)

        # Add deterministic ordering by last_env_sync_at DESC, then by canonical_id
        query = query.order("last_env_sync_at", desc=True).order("canonical_id", desc=False)

        # Apply pagination
        query = query.range(offset, offset + page_size - 1)

        # Execute query
        response = query.execute()

        mappings = response.data or []
        total = response.count if response.count is not None else 0

        # Return standardized paginated response
        return PaginatedResponse.create(
            items=mappings,
            page=page,
            page_size=page_size,
            total=total
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list workflow mappings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list workflow mappings: {str(e)}"
        )


# Sync Endpoints

@router.post("/sync/repo/{environment_id}")
async def sync_repository(
    environment_id: str,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """Sync workflows from Git repository to database (read-only operation)"""
    try:
        tenant_id = get_tenant_id(user_info)
        
        # Get user ID from user_info
        user = user_info.get("user", {})
        user_id = user.get("id", "00000000-0000-0000-0000-000000000000")
        
        # Get environment
        environment = await db_service.get_environment(environment_id, tenant_id)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )
        
        # Create background job
        job = await background_job_service.create_job(
            tenant_id=tenant_id,
            job_type=BackgroundJobType.CANONICAL_REPO_SYNC,
            resource_id=environment_id,
            resource_type="environment",
            created_by=user_id
        )
        
        if not job or not job.get("id"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create background job"
            )
        
        # Enqueue background task
        background_tasks.add_task(
            _run_repo_sync_background,
            job["id"],
            tenant_id,
            environment_id,
            environment
        )
        
        return {"job_id": job["id"], "status": "pending"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start repo sync: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start sync: {str(e)}"
        )


async def _run_repo_sync_background(
    job_id: str,
    tenant_id: str,
    environment_id: str,
    environment: Dict[str, Any]
):
    """Background task for repo sync"""
    try:
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING
        )
        
        results = await CanonicalRepoSyncService.sync_repository(
            tenant_id=tenant_id,
            environment_id=environment_id,
            environment=environment
        )
        
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.COMPLETED,
            result=results
        )
        
        # Trigger reconciliation for this environment
        await CanonicalReconciliationService.reconcile_all_pairs_for_environment(
            tenant_id=tenant_id,
            changed_env_id=environment_id
        )
    except Exception as e:
        logger.error(f"Repo sync failed: {str(e)}")
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=str(e)
        )

        # Emit failure SSE event
        try:
            from app.api.endpoints.sse import emit_sync_progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=None,  # Repo sync is not environment-specific
                status="failed",
                current_step="failed",
                current=0,
                total=1,
                message=f"Repository sync failed: {str(e)}",
                tenant_id=tenant_id
            )
        except Exception as sse_err:
            logger.warning(f"Failed to emit SSE failure event: {str(sse_err)}")


@router.post("/sync/env/{environment_id}")
async def sync_environment(
    environment_id: str,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """
    Sync workflows from n8n environment to database.

    IDEMPOTENT: If a sync job is already queued or running for this environment,
    returns the existing job ID instead of creating a duplicate.

    For DEV environments with Git configured, sync triggers a separate background job
    to commit changes to Git. This provides the path to create Git state for workflows.
    STAGING/PROD environments do not commit to Git.
    """
    try:
        tenant_id = get_tenant_id(user_info)

        # Get user ID from user_info
        user = user_info.get("user", {})
        user_id = user.get("id", "00000000-0000-0000-0000-000000000000")

        # Get environment
        environment = await db_service.get_environment(environment_id, tenant_id)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Use sync orchestrator for idempotent job creation
        job, is_new = await sync_orchestrator.request_sync(
            tenant_id=tenant_id,
            environment_id=environment_id,
            created_by=user_id
        )

        if not job or not job.get("id"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create or find sync job"
            )

        # If this is an existing job, return with already_running status
        if not is_new:
            return {
                "status": "already_running",
                "job_id": job["id"]
            }

        # Enqueue background task for new jobs only
        background_tasks.add_task(
            _run_env_sync_background,
            job["id"],
            tenant_id,
            environment_id,
            environment
        )

        return {"job_id": job["id"], "status": "pending"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start env sync: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start sync: {str(e)}"
        )


async def _run_env_sync_background(
    job_id: str,
    tenant_id: str,
    environment_id: str,
    environment: Dict[str, Any]
):
    """Background task for env sync"""
    # Track final status to ensure job is always updated
    final_status = BackgroundJobStatus.FAILED
    final_error_message = None
    final_results = {}

    try:
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING
        )

        # Emit initial SSE event (Phase: Discovering workflows)
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
                tenant_id=tenant_id
            )
        except Exception as sse_err:
            logger.warning(f"Failed to emit initial SSE event: {str(sse_err)}")

        # Get checkpoint from job progress if resuming
        job_data = await background_job_service.get_job(job_id)
        checkpoint = job_data.get("progress", {}).get("checkpoint")

        results = await CanonicalEnvSyncService.sync_environment(
            tenant_id=tenant_id,
            environment_id=environment_id,
            environment=environment,
            job_id=job_id,
            checkpoint=checkpoint,
            tenant_id_for_sse=tenant_id
        )

        # Update last_connected and last_sync_at timestamps on successful sync
        from datetime import datetime
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
        except Exception as conn_err:
            logger.warning(f"Failed to update environment timestamps: {str(conn_err)}")

        workflows_synced = results.get("workflows_synced", 0)
        workflows_linked = results.get("workflows_linked", 0)
        workflows_untracked = results.get("workflows_untracked", 0)
        workflows_missing = results.get("workflows_missing", 0)

        # Greenfield model: Drift detection only applies to non-DEV environments
        # DEV: n8n is source of truth, no drift concept
        # Non-DEV: Git is source of truth, detect drift between n8n and Git
        env_class = environment.get("environment_class", "").lower()
        is_dev = env_class == "dev"

        drift_count = 0
        if not is_dev:
            # Phase 3: Reconciling drift (non-DEV only)
            try:
                from app.api.endpoints.sse import emit_sync_progress
                await emit_sync_progress(
                    job_id=job_id,
                    environment_id=environment_id,
                    status="running",
                    current_step="reconciling_drift",
                    current=workflows_linked,
                    total=workflows_linked,
                    message=f"Detecting drift in {workflows_linked} linked workflow(s)...",
                    tenant_id=tenant_id
                )
            except Exception as sse_err:
                logger.warning(f"Failed to emit reconciliation SSE event: {str(sse_err)}")

            # Trigger reconciliation for this environment (wrapped in try-except to not block completion)
            try:
                reconciliation_results = await CanonicalReconciliationService.reconcile_all_pairs_for_environment(
                    tenant_id=tenant_id,
                    changed_env_id=environment_id
                )
            except Exception as recon_err:
                logger.warning(f"Reconciliation failed but continuing sync: {str(recon_err)}")

            # Get drift count from workflow_diff_state
            try:
                drift_result = db_service.client.table("workflow_diff_state").select(
                    "workflow_id"
                ).eq("tenant_id", tenant_id).eq("source_environment_id", environment_id).eq("diff_status", "modified").execute()
                drift_count = len(drift_result.data or [])
            except Exception as drift_err:
                logger.warning(f"Failed to get drift count: {str(drift_err)}")
        else:
            logger.info(f"DEV environment {environment_id}: Skipping drift detection (n8n is source of truth)")
            # DEV environment: Update drift_status to IN_SYNC since n8n is source of truth
            # and we just successfully synced from it
            try:
                await db_service.update_environment(
                    environment_id,
                    tenant_id,
                    {
                        "drift_status": "IN_SYNC",
                        "last_drift_check_at": now
                    }
                )
                logger.info(f"DEV sync: Updated drift_status to IN_SYNC for environment {environment_id}")
            except Exception as drift_update_err:
                logger.warning(f"Failed to update drift_status after DEV sync: {str(drift_update_err)}")

        # Phase 4: Finalizing sync
        try:
            from app.api.endpoints.sse import emit_sync_progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="running",
                current_step="finalizing_sync",
                current=0,
                total=0,
                message="Finalizing sync...",
                tenant_id=tenant_id
            )
        except Exception as sse_err:
            logger.warning(f"Failed to emit finalizing SSE event: {str(sse_err)}")
        
        # Add completion summary to results (Greenfield-aware)
        completion_summary = {
            "workflows_processed": workflows_synced,
            "workflows_linked": workflows_linked,
            "workflows_untracked": workflows_untracked,
            "workflows_missing": workflows_missing,
            "environment_class": env_class,
        }
        
        if is_dev:
            # DEV: n8n is source of truth, show Git persist status
            completion_summary["is_dev"] = True
            # workflows_persisted will be added by Phase 2 (Git sync) if applicable
        else:
            # Non-DEV: Git is source of truth, show drift detection
            completion_summary["is_dev"] = False
            completion_summary["drift_detected_count"] = drift_count
        
        results["completion_summary"] = completion_summary

        # Clean up large data from results before saving to database
        # Phase 2 (DEV Git sync) will read these from the job result, so we keep them
        # but only for DEV environments. For non-DEV, remove them to save space.
        cleaned_results = {**results}
        if not is_dev:
            # Non-DEV environments don't need these large lists
            cleaned_results.pop("observed_workflow_ids", None)
            cleaned_results.pop("created_workflow_ids", None)

        # Mark as successful - will be persisted in finally block
        final_status = BackgroundJobStatus.COMPLETED
        final_results = cleaned_results

        # Emit completion SSE event
        try:
            from app.api.endpoints.sse import emit_sync_progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="completed",
                current_step="completed",
                current=workflows_synced,
                total=workflows_synced,
                message=f"Sync complete: {workflows_synced} workflows processed",
                tenant_id=tenant_id
            )
        except Exception as sse_err:
            logger.warning(f"Failed to emit completion SSE event: {str(sse_err)}")
        
        # DEV environments: enqueue Phase 2 (Git commit) as separate background job
        env_class = environment.get("environment_class", "").lower()
        if env_class == "dev":
            git_repo_url = environment.get("git_repo_url")
            git_pat = environment.get("git_pat")
            
            if git_repo_url and git_pat:
                try:
                    # Create Phase 2 background job
                    phase2_job = await background_job_service.create_job(
                        tenant_id=tenant_id,
                        job_type=BackgroundJobType.DEV_GIT_SYNC,
                        resource_id=environment_id,
                        resource_type="environment",
                        created_by=None,  # System-created
                        metadata={
                            "phase1_job_id": job_id,
                            "environment_id": environment_id
                        }
                    )
                    
                    # Enqueue Phase 2 job (runs asynchronously, doesn't block Phase 1)
                    # Use asyncio.create_task() and yield to event loop to ensure it runs
                    import asyncio
                    try:
                        # Create task - this schedules it for execution
                        task = asyncio.create_task(
                            _run_dev_git_sync_background(
                                phase2_job["id"],
                                tenant_id,
                                environment_id,
                                environment,
                                job_id  # Pass Phase 1 job ID so Phase 2 can read its results
                            )
                        )
                        
                        # Add done callback to log completion/errors
                        def log_task_result(fut):
                            try:
                                fut.result()  # This will raise if task failed
                                logger.info(f"Phase 2 Git sync task completed successfully for job {phase2_job['id']}")
                            except Exception as e:
                                logger.error(f"Phase 2 Git sync task failed for job {phase2_job['id']}: {str(e)}", exc_info=True)
                        
                        task.add_done_callback(log_task_result)
                        
                        # Yield to event loop to ensure task is scheduled and starts running
                        # This is critical - without this, the task might not execute if parent completes immediately
                        await asyncio.sleep(0)
                        
                        logger.info(f"DEV sync: Enqueued Phase 2 Git sync job {phase2_job['id']} (task created and scheduled) for environment {environment_id}")
                    except Exception as task_err:
                        logger.error(f"DEV sync: Failed to create Phase 2 task: {str(task_err)}", exc_info=True)
                        # Fallback: try to run it directly (but this will block, so log warning)
                        logger.warning(f"DEV sync: Attempting direct execution of Phase 2 (this may block)")
                        try:
                            await _run_dev_git_sync_background(
                                phase2_job["id"],
                                tenant_id,
                                environment_id,
                                environment,
                                job_id
                            )
                        except Exception as direct_err:
                            logger.error(f"DEV sync: Direct execution also failed: {str(direct_err)}", exc_info=True)
                except Exception as git_job_err:
                    # Don't fail Phase 1 if Phase 2 job creation fails
                    logger.warning(f"DEV sync: Failed to enqueue Phase 2 Git sync job: {str(git_job_err)}", exc_info=True)
            else:
                logger.debug(f"DEV environment {environment_id} has no Git configuration, skipping Phase 2 Git sync")

    except Exception as e:
        logger.error(f"Env sync failed: {str(e)}")
        final_status = BackgroundJobStatus.FAILED
        final_error_message = str(e)

        # Emit failure SSE event
        try:
            from app.api.endpoints.sse import emit_sync_progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="failed",
                current_step="failed",
                current=0,
                total=1,
                message=f"Sync failed: {str(e)}",
                tenant_id=tenant_id
            )
        except Exception as sse_err:
            logger.warning(f"Failed to emit SSE failure event: {str(sse_err)}")

    finally:
        # ALWAYS update job status to ensure it never stays stuck in RUNNING state
        try:
            if final_status == BackgroundJobStatus.COMPLETED:
                await background_job_service.update_job_status(
                    job_id=job_id,
                    status=final_status,
                    result=final_results
                )
                logger.info(f"Env sync completed successfully for job {job_id}")
            else:
                await background_job_service.update_job_status(
                    job_id=job_id,
                    status=final_status,
                    error_message=final_error_message
                )
                logger.info(f"Env sync failed for job {job_id}: {final_error_message}")
        except Exception as status_update_err:
            # If even the status update fails, log it critically
            logger.critical(
                f"CRITICAL: Failed to update job {job_id} final status to {final_status}. "
                f"Job may be stuck in RUNNING state. Error: {str(status_update_err)}"
            )
            # Try one more time with minimal data to maximize chance of success
            try:
                await background_job_service.update_job_status(
                    job_id=job_id,
                    status=BackgroundJobStatus.FAILED,
                    error_message=f"Sync completed but status update failed: {str(status_update_err)}"
                )
            except Exception:
                pass  # At this point we've done everything we can


async def _run_dev_git_sync_background(
    job_id: str,
    tenant_id: str,
    environment_id: str,
    environment: Dict[str, Any],
    phase1_job_id: str
):
    """
    Phase 2 background job handler: DEV Git sync.
    Reads workflow IDs from Phase 1 job result and commits only those workflows.
    """
    try:
        # Phase 5: Persisting workflows to Git
        try:
            from app.api.endpoints.sse import emit_sync_progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="running",
                current_step="persisting_to_git",
                current=0,
                total=0,
                message="Preparing to persist workflows to Git...",
                tenant_id=tenant_id
            )
        except Exception as sse_err:
            logger.warning(f"Failed to emit SSE progress event: {str(sse_err)}")
        
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING,
            progress={
                "current": 0,
                "total": 0,
                "message": "Persisting workflows to Git...",
                "current_step": "persisting_to_git"
            }
        )
        
        # Read Phase 1 job result to get workflow IDs
        phase1_job = await background_job_service.get_job(phase1_job_id)
        if not phase1_job:
            raise Exception(f"Phase 1 job {phase1_job_id} not found")
        
        phase1_result = phase1_job.get("result") or {}
        observed_workflow_ids = phase1_result.get("observed_workflow_ids", [])
        created_workflow_ids = phase1_result.get("created_workflow_ids", [])
        
        if not observed_workflow_ids:
            logger.debug(f"Phase 2: No workflows to process for environment {environment_id}")
            await background_job_service.update_job_status(
                job_id=job_id,
                status=BackgroundJobStatus.COMPLETED,
                result={"message": "No workflows to commit", "workflows_persisted": 0}
            )
            return
        
        # Run DEV Git commit with workflow IDs from Phase 1
        committed_count = await _commit_dev_workflows_to_git(
            tenant_id=tenant_id,
            environment_id=environment_id,
            environment=environment,
            observed_workflow_ids=observed_workflow_ids,
            created_workflow_ids=created_workflow_ids,
            job_id=job_id,
            tenant_id_for_sse=tenant_id
        )

        # Update last_backup timestamp after Git commit
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        try:
            await db_service.update_environment(
                environment_id,
                tenant_id,
                {"last_backup": now}
            )
            logger.info(f"Phase 2: Updated last_backup timestamp for environment {environment_id}")
        except Exception as backup_err:
            logger.warning(f"Failed to update last_backup: {str(backup_err)}")

        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.COMPLETED,
            result={
                "message": "DEV Git sync completed",
                "workflows_persisted": committed_count
            }
        )
        
        # Update Phase 1 job result to include workflows_persisted in completion_summary
        try:
            phase1_job = await background_job_service.get_job(phase1_job_id)
            if phase1_job and phase1_job.get("result"):
                phase1_result = phase1_job.get("result", {})
                if phase1_result.get("completion_summary"):
                    phase1_result["completion_summary"]["workflows_persisted"] = committed_count
                    await background_job_service.update_job_status(
                        job_id=phase1_job_id,
                        status=BackgroundJobStatus.COMPLETED,
                        result=phase1_result
                    )
        except Exception as update_err:
            logger.warning(f"Failed to update Phase 1 completion summary: {str(update_err)}")
        
        # Emit completion
        try:
            from app.api.endpoints.sse import emit_sync_progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="completed",
                current_step="completed",
                current=committed_count,
                total=committed_count,
                message=f"Persisted {committed_count} workflow(s) to Git",
                tenant_id=tenant_id
            )
        except Exception as sse_err:
            logger.warning(f"Failed to emit completion SSE event: {str(sse_err)}")
        
        logger.info(f"Phase 2: DEV Git sync completed for environment {environment_id}")
        
    except Exception as e:
        logger.error(f"Phase 2: DEV Git sync failed: {str(e)}", exc_info=True)
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=str(e)
        )

        # Emit failure SSE event
        try:
            from app.api.endpoints.sse import emit_sync_progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="failed",
                current_step="failed",
                current=0,
                total=1,
                message=f"Git sync failed: {str(e)}",
                tenant_id=tenant_id
            )
        except Exception as sse_err:
            logger.warning(f"Failed to emit SSE failure event: {str(sse_err)}")


async def _commit_dev_workflows_to_git(
    tenant_id: str,
    environment_id: str,
    environment: Dict[str, Any],
    observed_workflow_ids: List[str],
    created_workflow_ids: List[str],
    job_id: Optional[str] = None,
    tenant_id_for_sse: Optional[str] = None
) -> int:
    """
    Commit workflows to Git for DEV environments with auto-canonicalization.
    
    In DEV, n8n is the source of truth. This function:
    - Bootstrap mode: If Git is empty, creates canonical workflows for observed workflows
      from Phase 1 and commits them to Git, ensuring all workflows are linked.
    - Normal mode: Commits changed linked workflows and auto-canonicalizes newly created
      untracked workflows from Phase 1 (creates canonical, links, commits to Git).
    
    Args:
        tenant_id: Tenant ID
        environment_id: Environment ID
        environment: Environment configuration
        observed_workflow_ids: List of n8n_workflow_ids observed in Phase 1
        created_workflow_ids: List of n8n_workflow_ids newly created (untracked) in Phase 1
    
    There is no untracked state in DEV after sync completes.
    """
    from app.services.github_service import GitHubService
    from datetime import datetime
    import re
    
    git_repo_url = environment.get("git_repo_url")
    git_branch = environment.get("git_branch", "main")
    git_pat = environment.get("git_pat")
    git_folder = environment.get("git_folder") or "dev"
    
    if not git_repo_url or not git_pat:
        return 0
    
    # Parse repo owner/name from URL
    match = re.match(r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$', git_repo_url)
    if not match:
        logger.warning(f"Could not parse Git repo URL: {git_repo_url}")
        return 0
    
    repo_owner, repo_name = match.groups()
    github = GitHubService(
        token=git_pat,
        repo_owner=repo_owner,
        repo_name=repo_name,
        branch=git_branch
    )
    
    if not github.is_configured():
        logger.error(f"GitHub service not properly configured for environment {environment_id}")
        return 0
    
    logger.info(f"DEV Git sync: Starting for environment {environment_id}, observed={len(observed_workflow_ids)}, created={len(created_workflow_ids)}")
    
    # Step 1: Detect bootstrap vs normal mode
    # Check if canonical_workflow_git_state has zero rows for this environment
    git_state_check = db_service.client.table("canonical_workflow_git_state").select(
        "canonical_id"
    ).eq("tenant_id", tenant_id).eq("environment_id", environment_id).limit(1).execute()
    
    is_bootstrap = len(git_state_check.data or []) == 0
    
    if is_bootstrap:
        # Bootstrap Mode: Git is empty, canonicalize observed workflows from Phase 1
        logger.info(f"DEV sync: Bootstrap mode detected for environment {environment_id}")
        
        if not observed_workflow_ids:
            logger.debug(f"No workflows to bootstrap for environment {environment_id}")
            return 0
        
        # Get only workflows observed in Phase 1
        all_workflows_result = db_service.client.table("workflow_env_map").select(
            "canonical_id, env_content_hash, workflow_data, n8n_workflow_id, status"
        ).eq("tenant_id", tenant_id).eq("environment_id", environment_id).in_("n8n_workflow_id", observed_workflow_ids).execute()
        
        if not all_workflows_result.data:
            logger.debug(f"No workflows to bootstrap for environment {environment_id}")
            return 0
        
        total_to_commit = len(all_workflows_result.data)
        
        # Emit progress
        if job_id and tenant_id_for_sse:
            try:
                from app.api.endpoints.sse import emit_sync_progress
                await emit_sync_progress(
                    job_id=job_id,
                    environment_id=environment_id,
                    status="running",
                    current_step="persisting_to_git",
                    current=0,
                    total=total_to_commit,
                    message=f"Bootstrap: Persisting {total_to_commit} workflow(s) to Git...",
                    tenant_id=tenant_id_for_sse
                )
            except Exception as sse_err:
                logger.warning(f"Failed to emit SSE progress event: {str(sse_err)}")
        
        committed_count = 0
        for mapping in all_workflows_result.data:
            try:
                canonical_id = mapping.get("canonical_id")
                env_hash = mapping.get("env_content_hash")
                workflow_data = mapping.get("workflow_data")
                n8n_workflow_id = mapping.get("n8n_workflow_id")
                
                if not workflow_data or not env_hash:
                    continue
                
                # If canonical_id is NULL, create canonical workflow
                if not canonical_id:
                    try:
                        workflow_name = workflow_data.get("name", "Unknown")
                        canonical_workflow = await CanonicalWorkflowService.create_canonical_workflow(
                            tenant_id=tenant_id,
                            created_by_user_id=None,  # System-created during bootstrap
                            display_name=workflow_name
                        )
                        canonical_id = canonical_workflow["canonical_id"]
                        
                        # Update workflow_env_map to set canonical_id and status='linked'
                        db_service.client.table("workflow_env_map").update({
                            "canonical_id": canonical_id,
                            "status": WorkflowMappingStatus.LINKED.value,
                            "linked_at": datetime.utcnow().isoformat()
                        }).eq("tenant_id", tenant_id).eq("environment_id", environment_id).eq("n8n_workflow_id", n8n_workflow_id).execute()
                        
                        logger.debug(f"Bootstrap: Created canonical workflow {canonical_id} for workflow {n8n_workflow_id}")
                    except Exception as create_err:
                        logger.warning(f"Bootstrap: Failed to create canonical workflow for {n8n_workflow_id}: {create_err}", exc_info=True)
                        continue
                
                # Commit workflow to Git
                try:
                    workflow_name = workflow_data.get("name", "Unknown")
                    await github.write_workflow_file(
                        canonical_id=canonical_id,
                        workflow_data=workflow_data,
                        git_folder=git_folder,
                        commit_message=f"sync(dev): bootstrap {workflow_name}"
                    )
                    
                    # Upsert canonical_workflow_git_state with git_content_hash = env_content_hash
                    git_path = f"workflows/{git_folder}/{canonical_id}.json"
                    db_service.client.table("canonical_workflow_git_state").upsert({
                        "tenant_id": tenant_id,
                        "environment_id": environment_id,
                        "canonical_id": canonical_id,
                        "git_path": git_path,
                        "git_content_hash": env_hash,
                        "last_repo_sync_at": datetime.utcnow().isoformat()
                    }, on_conflict="tenant_id,environment_id,canonical_id").execute()
                    
                    committed_count += 1
                    
                    # Emit progress update
                    if job_id and tenant_id_for_sse:
                        try:
                            from app.api.endpoints.sse import emit_sync_progress
                            await emit_sync_progress(
                                job_id=job_id,
                                environment_id=environment_id,
                                status="running",
                                current_step="persisting_to_git",
                                current=committed_count,
                                total=total_to_commit,
                                message=f"{committed_count} / {total_to_commit} workflows persisted",
                                tenant_id=tenant_id_for_sse
                            )
                        except Exception as sse_err:
                            logger.warning(f"Failed to emit SSE progress event: {str(sse_err)}")
                except Exception as commit_err:
                    logger.warning(f"Bootstrap: Failed to commit workflow {canonical_id} to Git: {commit_err}", exc_info=True)
            except Exception as workflow_err:
                logger.warning(f"Bootstrap: Error processing workflow: {workflow_err}", exc_info=True)
                continue
        
        logger.info(f"DEV sync: Bootstrap completed - committed {committed_count} workflow(s) to Git for environment {environment_id}")
        return committed_count
    
    else:
        # Normal Mode: Git already initialized
        logger.debug(f"DEV sync: Normal mode for environment {environment_id}")
        
        # Get linked workflows (canonical_id NOT NULL, status='linked')
        linked_workflows_result = db_service.client.table("workflow_env_map").select(
            "canonical_id, env_content_hash, workflow_data, n8n_workflow_id, status"
        ).eq("tenant_id", tenant_id).eq("environment_id", environment_id).eq("status", WorkflowMappingStatus.LINKED.value).not_.is_("canonical_id", "null").execute()
        
        # Count workflows to process
        workflows_to_commit_count = 0
        untracked_to_commit_count = 0
        
        # Get Git state to compare hashes
        canonical_ids = [row["canonical_id"] for row in (linked_workflows_result.data or []) if row.get("canonical_id")]
        git_hashes = {}
        if canonical_ids:
            git_state_result = db_service.client.table("canonical_workflow_git_state").select(
                "canonical_id, git_content_hash"
            ).eq("tenant_id", tenant_id).eq("environment_id", environment_id).in_("canonical_id", canonical_ids).execute()
            git_state_data = git_state_result.data if git_state_result else []
            git_hashes = {row["canonical_id"]: row["git_content_hash"] for row in git_state_data}
        
        # Find linked workflows with changes (env hash != git hash or no git hash)
        workflows_to_commit = []
        for mapping in (linked_workflows_result.data or []):
            canonical_id = mapping.get("canonical_id")
            env_hash = mapping.get("env_content_hash")
            workflow_data = mapping.get("workflow_data")
            
            if not workflow_data or not env_hash or not canonical_id:
                continue
            
            # Compare with git hash - commit if different or no git hash exists
            git_hash = git_hashes.get(canonical_id)
            if env_hash != git_hash:
                workflows_to_commit.append({
                    "canonical_id": canonical_id,
                    "workflow_data": workflow_data,
                    "env_hash": env_hash
                })
        
        # Count untracked workflows to auto-canonicalize
        untracked_to_commit = []
        if created_workflow_ids:
            untracked_workflows_result = db_service.client.table("workflow_env_map").select(
                "canonical_id, env_content_hash, workflow_data, n8n_workflow_id, status"
            ).eq("tenant_id", tenant_id).eq("environment_id", environment_id).in_("n8n_workflow_id", created_workflow_ids).eq("status", WorkflowMappingStatus.UNTRACKED.value).is_("canonical_id", "null").execute()
            if untracked_workflows_result.data:
                untracked_to_commit = untracked_workflows_result.data
        
        total_to_commit = len(workflows_to_commit) + len(untracked_to_commit)
        
        # Emit initial progress
        if job_id and tenant_id_for_sse and total_to_commit > 0:
            try:
                from app.api.endpoints.sse import emit_sync_progress
                await emit_sync_progress(
                    job_id=job_id,
                    environment_id=environment_id,
                    status="running",
                    current_step="persisting_to_git",
                    current=0,
                    total=total_to_commit,
                    message=f"Persisting {total_to_commit} workflow(s) to Git...",
                    tenant_id=tenant_id_for_sse
                )
            except Exception as sse_err:
                logger.warning(f"Failed to emit SSE progress event: {str(sse_err)}")
        
        # Commit changed linked workflows
        committed_count = 0
        if workflows_to_commit:
            for wf in workflows_to_commit:
                try:
                    workflow_name = wf["workflow_data"].get("name", "Unknown")
                    await github.write_workflow_file(
                        canonical_id=wf["canonical_id"],
                        workflow_data=wf["workflow_data"],
                        git_folder=git_folder,
                        commit_message=f"sync(dev): update {workflow_name}"
                    )
                    
                    # Update git_state with new hash
                    git_path = f"workflows/{git_folder}/{wf['canonical_id']}.json"
                    db_service.client.table("canonical_workflow_git_state").upsert({
                        "tenant_id": tenant_id,
                        "environment_id": environment_id,
                        "canonical_id": wf["canonical_id"],
                        "git_path": git_path,
                        "git_content_hash": wf["env_hash"],
                        "last_repo_sync_at": datetime.utcnow().isoformat()
                    }, on_conflict="tenant_id,environment_id,canonical_id").execute()
                    
                    committed_count += 1
                    
                    # Emit progress update
                    if job_id and tenant_id_for_sse:
                        try:
                            from app.api.endpoints.sse import emit_sync_progress
                            await emit_sync_progress(
                                job_id=job_id,
                                environment_id=environment_id,
                                status="running",
                                current_step="persisting_to_git",
                                current=committed_count,
                                total=total_to_commit,
                                message=f"{committed_count} / {total_to_commit} workflows persisted",
                                tenant_id=tenant_id_for_sse
                            )
                        except Exception as sse_err:
                            logger.warning(f"Failed to emit SSE progress event: {str(sse_err)}")
                except Exception as commit_err:
                    logger.warning(f"Failed to commit workflow {wf['canonical_id']} to Git: {commit_err}", exc_info=True)
        
        # Auto-canonicalize newly created untracked workflows from Phase 1
        if untracked_to_commit:
            logger.debug(f"DEV sync: Found {len(untracked_to_commit)} untracked workflow(s) to auto-canonicalize")
            
            for mapping in untracked_to_commit:
                    try:
                        env_hash = mapping.get("env_content_hash")
                        workflow_data = mapping.get("workflow_data")
                        n8n_workflow_id = mapping.get("n8n_workflow_id")
                        
                        if not workflow_data or not env_hash:
                            continue
                        
                        # Auto-canonicalize: create canonical workflow
                        workflow_name = workflow_data.get("name", "Unknown")
                        canonical_workflow = await CanonicalWorkflowService.create_canonical_workflow(
                            tenant_id=tenant_id,
                            created_by_user_id=None,  # System-created during sync
                            display_name=workflow_name
                        )
                        canonical_id = canonical_workflow["canonical_id"]
                        
                        # Update workflow_env_map to set canonical_id and status='linked'
                        db_service.client.table("workflow_env_map").update({
                            "canonical_id": canonical_id,
                            "status": WorkflowMappingStatus.LINKED.value,
                            "linked_at": datetime.utcnow().isoformat()
                        }).eq("tenant_id", tenant_id).eq("environment_id", environment_id).eq("n8n_workflow_id", n8n_workflow_id).execute()
                        
                        # Commit to Git
                        await github.write_workflow_file(
                            canonical_id=canonical_id,
                            workflow_data=workflow_data,
                            git_folder=git_folder,
                            commit_message=f"sync(dev): auto-canonicalize {workflow_name}"
                        )
                        
                        # Upsert canonical_workflow_git_state
                        git_path = f"workflows/{git_folder}/{canonical_id}.json"
                        db_service.client.table("canonical_workflow_git_state").upsert({
                            "tenant_id": tenant_id,
                            "environment_id": environment_id,
                            "canonical_id": canonical_id,
                            "git_path": git_path,
                            "git_content_hash": env_hash,
                            "last_repo_sync_at": datetime.utcnow().isoformat()
                        }, on_conflict="tenant_id,environment_id,canonical_id").execute()
                        
                        committed_count += 1
                        
                        # Emit progress update
                        if job_id and tenant_id_for_sse:
                            try:
                                from app.api.endpoints.sse import emit_sync_progress
                                await emit_sync_progress(
                                    job_id=job_id,
                                    environment_id=environment_id,
                                    status="running",
                                    current_step="persisting_to_git",
                                    current=committed_count,
                                    total=total_to_commit,
                                    message=f"{committed_count} / {total_to_commit} workflows persisted",
                                    tenant_id=tenant_id_for_sse
                                )
                            except Exception as sse_err:
                                logger.warning(f"Failed to emit SSE progress event: {str(sse_err)}")
                        
                        logger.debug(f"Auto-canonicalized workflow {n8n_workflow_id} → canonical {canonical_id}")
                    except Exception as auto_err:
                        logger.warning(f"Failed to auto-canonicalize workflow {mapping.get('n8n_workflow_id')}: {auto_err}", exc_info=True)
                        continue
        
        if committed_count > 0:
            logger.info(f"DEV sync: Committed {committed_count} workflow(s) to Git for environment {environment_id}")
        else:
            logger.debug(f"DEV sync: No workflow changes to commit to Git for environment {environment_id}")
        
        return committed_count


@router.post("/reconcile/{source_env_id}/{target_env_id}")
async def reconcile_environment_pair(
    source_env_id: str,
    target_env_id: str,
    force: bool = False,
    background_tasks: BackgroundTasks = None,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """Reconcile and compute diffs between two environments"""
    tenant_id = get_tenant_id(user_info)
    
    if background_tasks:
        # Create background job
        job = await background_job_service.create_job(
            tenant_id=tenant_id,
            job_type=BackgroundJobType.CANONICAL_RECONCILIATION,
            resource_id=f"{source_env_id}:{target_env_id}",
            resource_type="reconciliation",
            created_by=user_info.get("user_id")
        )
        
        # Enqueue background task
        background_tasks.add_task(
            _run_reconciliation_background,
            job["id"],
            tenant_id,
            source_env_id,
            target_env_id,
            force
        )
        
        return {"job_id": job["id"], "status": "pending"}
    else:
        # Run synchronously
        results = await CanonicalReconciliationService.reconcile_environment_pair(
            tenant_id=tenant_id,
            source_env_id=source_env_id,
            target_env_id=target_env_id,
            force=force
        )
        return results


async def _run_reconciliation_background(
    job_id: str,
    tenant_id: str,
    source_env_id: str,
    target_env_id: str,
    force: bool
):
    """Background task for reconciliation"""
    try:
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING
        )
        
        results = await CanonicalReconciliationService.reconcile_environment_pair(
            tenant_id=tenant_id,
            source_env_id=source_env_id,
            target_env_id=target_env_id,
            force=force
        )
        
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.COMPLETED,
            result=results
        )
    except Exception as e:
        logger.error(f"Reconciliation failed: {str(e)}")
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=str(e)
        )

        # Emit failure SSE event
        try:
            from app.api.endpoints.sse import emit_sync_progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=None,  # Reconciliation is cross-environment
                status="failed",
                current_step="failed",
                current=0,
                total=1,
                message=f"Reconciliation failed: {str(e)}",
                tenant_id=tenant_id
            )
        except Exception as sse_err:
            logger.warning(f"Failed to emit SSE failure event: {str(sse_err)}")


# Diff State Endpoints

@router.get("/diff-states", response_model=PaginatedResponse[WorkflowDiffStateResponse])
async def list_diff_states(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    source_env_id: Optional[str] = None,
    target_env_id: Optional[str] = None,
    canonical_id: Optional[str] = None,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """
    List workflow diff states with server-side pagination.

    This endpoint returns paginated workflow diff states between environments.
    - Returns only the requested page of diff states
    - Performs filtering at the database level
    - Uses standardized pagination envelope

    Query params:
        page: Page number (1-indexed, default 1)
        page_size: Items per page (default 50, max 100)
        source_env_id: Optional filter by source environment ID
        target_env_id: Optional filter by target environment ID
        canonical_id: Optional filter by canonical workflow ID

    Returns:
        Standardized pagination envelope:
        {
            "items": [...],
            "total": int,
            "page": int,
            "pageSize": int,
            "totalPages": int,
            "hasMore": bool
        }
    """
    try:
        tenant_id = get_tenant_id(user_info)

        # Limit page_size to prevent abuse
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

        # Calculate offset
        offset = (page - 1) * page_size

        # Build query with pagination
        query = (
            db_service.client.table("workflow_diff_state")
            .select("*", count="exact")
            .eq("tenant_id", tenant_id)
        )

        # Apply optional filters
        if source_env_id:
            query = query.eq("source_env_id", source_env_id)
        if target_env_id:
            query = query.eq("target_env_id", target_env_id)
        if canonical_id:
            query = query.eq("canonical_id", canonical_id)

        # Add deterministic ordering by computed_at DESC, then by canonical_id
        query = query.order("computed_at", desc=True).order("canonical_id", desc=False)

        # Apply pagination
        query = query.range(offset, offset + page_size - 1)

        # Execute query
        response = query.execute()

        diff_states = response.data or []
        total = response.count if response.count is not None else 0

        # Return standardized paginated response
        return PaginatedResponse.create(
            items=diff_states,
            page=page,
            page_size=page_size,
            total=total
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list workflow diff states: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list workflow diff states: {str(e)}"
        )


# Link Suggestions Endpoints

@router.get("/link-suggestions", response_model=List[WorkflowLinkSuggestionResponse])
async def list_link_suggestions(
    environment_id: Optional[str] = None,
    status: Optional[str] = None,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """List workflow link suggestions"""
    tenant_id = get_tenant_id(user_info)
    suggestions = await db_service.get_workflow_link_suggestions(
        tenant_id=tenant_id,
        environment_id=environment_id,
        status=status or "open"
    )
    return suggestions


@router.post("/link-suggestions/{suggestion_id}/resolve")
async def resolve_link_suggestion(
    suggestion_id: str,
    status: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_push"))
):
    """Resolve a workflow link suggestion"""
    tenant_id = get_tenant_id(user_info)
    user_id = user_info.get("user_id")
    
    result = await db_service.update_workflow_link_suggestion(
        suggestion_id=suggestion_id,
        tenant_id=tenant_id,
        status=status,
        resolved_by_user_id=user_id
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link suggestion not found"
        )
    
    return result

