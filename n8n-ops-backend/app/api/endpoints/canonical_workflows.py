"""
API endpoints for canonical workflow system
"""
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
import logging

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
    OnboardingCompleteCheck
)
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
    _: dict = Depends(require_entitlement("workflow_write"))
):
    """Start onboarding inventory phase"""
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


@router.post("/onboarding/migration-pr", response_model=MigrationPRResponse)
async def create_migration_pr(
    request: MigrationPRRequest,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_write"))
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

@router.get("/canonical-workflows", response_model=List[CanonicalWorkflowResponse])
async def list_canonical_workflows(
    include_deleted: bool = False,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """List all canonical workflows for tenant"""
    tenant_id = get_tenant_id(user_info)
    workflows = await CanonicalWorkflowService.list_canonical_workflows(
        tenant_id=tenant_id,
        include_deleted=include_deleted
    )
    return workflows


@router.get("/canonical-workflows/{canonical_id}", response_model=CanonicalWorkflowResponse)
async def get_canonical_workflow(
    canonical_id: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """Get a canonical workflow by ID"""
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
    return workflow


# Workflow Environment Mapping Endpoints

@router.get("/workflow-mappings", response_model=List[WorkflowEnvMapResponse])
async def list_workflow_mappings(
    environment_id: Optional[str] = None,
    canonical_id: Optional[str] = None,
    status: Optional[str] = None,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """List workflow environment mappings"""
    tenant_id = get_tenant_id(user_info)
    mappings = await db_service.get_workflow_mappings(
        tenant_id=tenant_id,
        environment_id=environment_id,
        canonical_id=canonical_id,
        status=status
    )
    return mappings


# Sync Endpoints

@router.post("/sync/repo/{environment_id}")
async def sync_repository(
    environment_id: str,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_write"))
):
    """Sync workflows from Git repository to database"""
    tenant_id = get_tenant_id(user_info)
    
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
        created_by=user_info.get("user_id")
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


@router.post("/sync/env/{environment_id}")
async def sync_environment(
    environment_id: str,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_write"))
):
    """Sync workflows from n8n environment to database"""
    tenant_id = get_tenant_id(user_info)
    
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
        job_type=BackgroundJobType.CANONICAL_ENV_SYNC,
        resource_id=environment_id,
        resource_type="environment",
        created_by=user_info.get("user_id")
    )
    
    # Enqueue background task
    background_tasks.add_task(
        _run_env_sync_background,
        job["id"],
        tenant_id,
        environment_id,
        environment
    )
    
    return {"job_id": job["id"], "status": "pending"}


async def _run_env_sync_background(
    job_id: str,
    tenant_id: str,
    environment_id: str,
    environment: Dict[str, Any]
):
    """Background task for env sync"""
    try:
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING
        )
        
        # Get checkpoint from job progress if resuming
        job_data = await background_job_service.get_job(job_id)
        checkpoint = job_data.get("progress", {}).get("checkpoint")
        
        results = await CanonicalEnvSyncService.sync_environment(
            tenant_id=tenant_id,
            environment_id=environment_id,
            environment=environment,
            job_id=job_id,
            checkpoint=checkpoint
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
        logger.error(f"Env sync failed: {str(e)}")
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=str(e)
        )


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


# Diff State Endpoints

@router.get("/diff-states", response_model=List[WorkflowDiffStateResponse])
async def list_diff_states(
    source_env_id: Optional[str] = None,
    target_env_id: Optional[str] = None,
    canonical_id: Optional[str] = None,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """List workflow diff states"""
    tenant_id = get_tenant_id(user_info)
    diff_states = await db_service.get_workflow_diff_states(
        tenant_id=tenant_id,
        source_env_id=source_env_id,
        target_env_id=target_env_id,
        canonical_id=canonical_id
    )
    return diff_states


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
    _: dict = Depends(require_entitlement("workflow_write"))
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

