from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from typing import List
from datetime import datetime
from uuid import uuid4
import logging

from app.schemas.environment import (
    EnvironmentCreate,
    EnvironmentUpdate,
    EnvironmentResponse,
    EnvironmentTestConnection,
    GitTestConnection
)
from app.services.database import db_service
from app.services.provider_registry import ProviderRegistry
from app.services.github_service import GitHubService
from app.services.entitlements_service import entitlements_service
from app.core.entitlements_gate import require_entitlement, require_environment_limit
from app.api.endpoints.admin_audit import create_audit_log, AuditActionType
from app.services.background_job_service import (
    background_job_service,
    BackgroundJobStatus,
    BackgroundJobType
)
from app.api.endpoints.sse import emit_sync_progress
from app.services.environment_action_guard import (
    environment_action_guard,
    EnvironmentAction,
    ActionGuardError
)
from app.schemas.environment import EnvironmentClass
from app.services.auth_service import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


def get_tenant_id(user_info: dict) -> str:
    tenant = user_info.get("tenant") or {}
    tenant_id = tenant.get("id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return tenant_id


@router.get("/test")
async def test_endpoint():
    """Simple test endpoint"""
    return {"status": "ok", "message": "Environments router is working"}


@router.get("/", response_model=List[EnvironmentResponse], response_model_exclude_none=False)
async def get_environments(
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """Get all environments for the current tenant"""
    try:
        tenant_id = get_tenant_id(user_info)
        environments = await db_service.get_environments(tenant_id)
        return environments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch environments: {str(e)}"
        )


@router.get("/limits")
async def get_environment_limits(
    user_info: dict = Depends(get_current_user)
):
    """Get environment limits and current usage for the tenant"""
    try:
        tenant_id = get_tenant_id(user_info)
        can_add, message, current, max_allowed = await entitlements_service.can_add_environment(tenant_id)
        return {
            "can_add": can_add,
            "message": message,
            "current": current,
            "max": max_allowed if max_allowed >= 9999 else max_allowed  # 9999 = unlimited
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch environment limits: {str(e)}"
        )


@router.post("/test-connection")
async def test_environment_connection(
    connection: EnvironmentTestConnection,
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """Test connection to a workflow provider instance (defaults to n8n)"""
    try:
        # Use ProviderRegistry to get adapter (defaults to n8n for now)
        # In the future, this could accept a provider parameter
        config = {
            "n8n_base_url": connection.n8n_base_url,
            "n8n_api_key": connection.n8n_api_key
        }
        adapter = ProviderRegistry.get_adapter(provider="n8n", config=config)
        is_connected = await adapter.test_connection()

        if is_connected:
            return {
                "success": True,
                "message": "Successfully connected to workflow provider instance"
            }
        else:
            return {
                "success": False,
                "message": "Failed to connect to workflow provider instance. Please check your URL and API key."
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection error: {str(e)}"
        }


@router.post("/test-git-connection")
async def test_git_connection(
    connection: GitTestConnection,
    _: dict = Depends(require_entitlement("environment_diff"))
):
    """Test connection to a GitHub repository"""
    try:
        # Parse repo URL to extract owner and repo name
        # Expected format: https://github.com/owner/repo or https://github.com/owner/repo.git
        repo_url = connection.git_repo_url.rstrip('/')
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]

        parts = repo_url.split('github.com/')
        if len(parts) != 2:
            return {
                "success": False,
                "message": "Invalid GitHub repository URL format. Expected: https://github.com/owner/repo"
            }

        repo_path = parts[1].strip('/')
        path_parts = repo_path.split('/')
        if len(path_parts) < 2:
            return {
                "success": False,
                "message": "Invalid GitHub repository path. Expected format: owner/repo"
            }

        owner = path_parts[0]
        repo_name = path_parts[1]

        # Create GitHub service with provided credentials
        github_service = GitHubService(
            token=connection.git_pat,
            repo_owner=owner,
            repo_name=repo_name,
            branch=connection.git_branch
        )

        # Test access by trying to access the repo
        if not github_service.is_configured():
            return {
                "success": False,
                "message": "GitHub configuration is incomplete"
            }

        repo = github_service.repo
        if repo is None:
            return {
                "success": False,
                "message": "Failed to access repository. Please check your repository URL and Personal Access Token."
            }

        # Try to verify the branch exists
        try:
            repo.get_branch(connection.git_branch)
        except Exception:
            return {
                "success": False,
                "message": f"Branch '{connection.git_branch}' not found in repository. Please check the branch name."
            }

        return {
            "success": True,
            "message": f"Successfully connected to {owner}/{repo_name} (branch: {connection.git_branch})"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Connection error: {str(e)}"
        }


@router.get("/{environment_id}", response_model=EnvironmentResponse, response_model_exclude_none=False)
async def get_environment(
    environment_id: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """Get a specific environment by ID"""
    try:
        tenant_id = get_tenant_id(user_info)
        environment = await db_service.get_environment(environment_id, tenant_id)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )
        return environment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch environment: {str(e)}"
        )


@router.post("/", response_model=EnvironmentResponse, status_code=status.HTTP_201_CREATED, response_model_exclude_none=False)
async def create_environment(
    environment: EnvironmentCreate,
    user_info: dict = Depends(get_current_user),
    limit_check: dict = Depends(require_environment_limit())
):
    """
    Create a new environment.

    This endpoint enforces plan-based environment limits server-side.
    The require_environment_limit() dependency ensures tenants cannot exceed
    their plan's environment quota (e.g., 1 for Free, 3 for Pro).
    """
    try:
        tenant_id = get_tenant_id(user_info)

        # Double-check environment limit as an additional safety measure
        # The decorator already checked, but we verify again before DB write
        can_add, message, current, limit = await entitlements_service.can_add_environment(tenant_id)
        if not can_add:
            logger.warning(
                f"Environment creation blocked for tenant {tenant_id}: "
                f"{current}/{limit} environments (limit reached)"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "environment_limit_reached",
                    "current_count": current,
                    "limit": limit,
                    "message": message,
                }
            )

        # Type is now optional metadata - no uniqueness check needed
        # Multiple environments can have the same type

        environment_data = {
            "tenant_id": tenant_id,
            "n8n_name": environment.n8n_name,
            "n8n_type": environment.n8n_type,  # Optional, can be None
            "n8n_base_url": environment.n8n_base_url,
            "n8n_api_key": environment.n8n_api_key,
            "n8n_encryption_key": environment.n8n_encryption_key,
            "is_active": environment.is_active,
            "allow_upload": environment.allow_upload,
            "git_repo_url": environment.git_repo_url,
            "git_branch": environment.git_branch,
            "git_pat": environment.git_pat
        }

        created_environment = await db_service.create_environment(environment_data)

        logger.info(
            f"Environment '{environment.n8n_name}' created for tenant {tenant_id}. "
            f"Usage: {current + 1}/{limit}"
        )

        # Create audit log with provider context
        try:
            provider = created_environment.get("provider", "n8n")
            await create_audit_log(
                action_type="ENVIRONMENT_CREATED",
                action=f"Created environment '{environment.n8n_name}'",
                tenant_id=tenant_id,
                resource_type="environment",
                resource_id=created_environment.get("id"),
                resource_name=environment.n8n_name,
                provider=provider,
                new_value={
                    "name": environment.n8n_name,
                    "type": environment.n8n_type,
                    "base_url": environment.n8n_base_url
                }
            )
        except Exception:
            pass  # Don't fail if audit logging fails

        return created_environment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create environment: {str(e)}"
        )


@router.patch("/{environment_id}", response_model=EnvironmentResponse, response_model_exclude_none=False)
async def update_environment(
    environment_id: str,
    environment: EnvironmentUpdate,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """Update an environment"""
    try:
        tenant_id = get_tenant_id(user_info)
        # Check if environment exists
        existing = await db_service.get_environment(environment_id, tenant_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Build update data (only include non-None fields)
        update_data = {k: v for k, v in environment.dict(exclude_unset=True).items() if v is not None}

        if not update_data:
            return existing

        updated_environment = await db_service.update_environment(
            environment_id,
            tenant_id,
            update_data
        )

        if not updated_environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        return updated_environment
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update environment: {str(e)}"
        )


@router.delete("/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(
    environment_id: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """Delete an environment"""
    try:
        tenant_id = get_tenant_id(user_info)
        # Check if environment exists
        existing = await db_service.get_environment(environment_id, tenant_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Store info for audit log before deletion
        env_name = existing.get("n8n_name", existing.get("name", environment_id))
        env_provider = existing.get("provider", "n8n")

        await db_service.delete_environment(environment_id, tenant_id)

        # Create audit log with provider context
        try:
            await create_audit_log(
                action_type="ENVIRONMENT_DELETED",
                action=f"Deleted environment '{env_name}'",
                tenant_id=tenant_id,
                resource_type="environment",
                resource_id=environment_id,
                resource_name=env_name,
                provider=env_provider,
                old_value={
                    "name": env_name,
                    "type": existing.get("n8n_type"),
                    "base_url": existing.get("n8n_base_url")
                }
            )
        except Exception:
            pass

        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete environment: {str(e)}"
        )


@router.post("/{environment_id}/update-connection-status")
async def update_connection_status(
    environment_id: str,
    user_info: dict = Depends(get_current_user)
):
    """Update the last_connected timestamp for an environment"""
    try:
        tenant_id = get_tenant_id(user_info)
        environment = await db_service.get_environment(environment_id, tenant_id)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Test connection using provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(environment)
        is_connected = await adapter.test_connection()

        if is_connected:
            # Update last_connected timestamp
            await db_service.update_environment(
                environment_id,
                tenant_id,
                {"last_connected": datetime.utcnow().isoformat()}
            )

        return {
            "success": is_connected,
            "message": "Connected" if is_connected else "Connection failed"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update connection status: {str(e)}"
        )


async def _sync_environment_background(
    job_id: str,
    environment_id: str,
    environment: dict,
    tenant_id: str
):
    """Background task for syncing environment from N8N."""
    try:
        # Update job status to running
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING,
            progress={
                "current": 0,
                "total": 5,  # workflows, executions, credentials, users, tags
                "percentage": 0,
                "message": "Starting sync..."
            }
        )
        await emit_sync_progress(
            job_id=job_id,
            environment_id=environment_id,
            status="running",
            current_step="initializing",
            current=0,
            total=5,
            message="Starting sync...",
            tenant_id=tenant_id
        )

        # Create provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(environment)

        # Test connection
        is_connected = await adapter.test_connection()
        if not is_connected:
            raise Exception("Cannot connect to provider instance")

        sync_results = {
            "workflows": {"synced": 0, "errors": []},
            "executions": {"synced": 0, "errors": []},
            "credentials": {"synced": 0, "errors": []},
            "users": {"synced": 0, "errors": []},
            "tags": {"synced": 0, "errors": []}
        }

        # Sync workflows (step 1/5)
        try:
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="running",
                current_step="workflows",
                current=1,
                total=5,
                message="Syncing workflows...",
                tenant_id=tenant_id
            )
            workflows = await adapter.get_workflows()
            
            from app.services.workflow_analysis_service import analyze_workflow
            workflows_with_analysis = {}
            for workflow in workflows:
                try:
                    analysis = analyze_workflow(workflow)
                    workflows_with_analysis[workflow.get("id")] = analysis
                except Exception as e:
                    logger.warning(f"Failed to analyze workflow {workflow.get('id', 'unknown')}: {str(e)}")
            
            # Use canonical workflow system for syncing
            from app.services.canonical_env_sync_service import CanonicalEnvSyncService
            from app.services.canonical_reconciliation_service import CanonicalReconciliationService

            # Sync using canonical workflow system
            env_sync_result = await CanonicalEnvSyncService.sync_environment(
                tenant_id=tenant_id,
                environment_id=environment_id,
                environment=environment,
                job_id=job_id,
                tenant_id_for_sse=tenant_id  # Enable SSE events for live log streaming
            )
            
            sync_results["workflows"]["synced"] = env_sync_result.get("workflows_synced", 0)
            sync_results["workflows"]["errors"] = env_sync_result.get("errors", [])
            
            # Update workflow count (for backward compatibility)
            await db_service.update_environment_workflow_count(
                environment_id,
                tenant_id,
                env_sync_result.get("workflows_synced", 0)
            )
            
            # Greenfield model: Drift detection only for non-DEV environments
            # DEV: n8n is source of truth, no drift concept
            # Non-DEV: Git is source of truth, detect drift
            env_class = environment.get("environment_class", "").lower()
            is_dev = env_class == "dev"
            
            if not is_dev:
                # Trigger reconciliation (drift detection) for non-DEV environments
                try:
                    await CanonicalReconciliationService.reconcile_all_pairs_for_environment(
                        tenant_id=tenant_id,
                        changed_env_id=environment_id
                    )
                except Exception as recon_error:
                    logger.warning(f"Failed to trigger reconciliation after env sync: {str(recon_error)}")
            else:
                logger.info(f"DEV environment {environment_id}: Skipping drift detection (n8n is source of truth)")

            # DEV environments: commit changed workflows to Git
            if is_dev:
                # Emit SSE: starting Git phase
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
                
                try:
                    from app.services.github_service import GitHubService
                    from app.services.canonical_workflow_service import compute_workflow_hash

                    git_repo_url = environment.get("git_repo_url")
                    git_branch = environment.get("git_branch", "main")
                    git_pat = environment.get("git_pat")
                    
                    logger.info(f"DEV sync Git config: repo_url={git_repo_url}, branch={git_branch}, has_pat={bool(git_pat)}")

                    if git_repo_url and git_pat:
                        # Parse repo owner/name from URL
                        import re
                        match = re.match(r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$', git_repo_url)
                        if match:
                            repo_owner, repo_name = match.groups()
                            logger.info(f"DEV sync: Parsed repo {repo_owner}/{repo_name}")
                            
                            github = GitHubService(
                                token=git_pat,
                                repo_owner=repo_owner,
                                repo_name=repo_name,
                                branch=git_branch
                            )

                            # Get workflows with differences (n8n hash != git hash)
                            env_map_result = db_service.client.table("workflow_env_map").select(
                                "canonical_id, env_content_hash, workflow_data"
                            ).eq("tenant_id", tenant_id).eq("environment_id", environment_id).execute()

                            env_map_data = env_map_result.data if env_map_result else []
                            logger.info(f"DEV sync: Found {len(env_map_data)} workflows in env_map")

                            git_state_result = db_service.client.table("canonical_workflow_git_state").select(
                                "canonical_id, git_content_hash"
                            ).eq("tenant_id", tenant_id).eq("environment_id", environment_id).execute()

                            git_state_data = git_state_result.data if git_state_result else []
                            logger.info(f"DEV sync: Found {len(git_state_data)} workflows in git_state")

                            # Build lookup for Git hashes
                            git_hashes = {row["canonical_id"]: row["git_content_hash"] for row in git_state_data}

                            # Find workflows with changes - debug each decision
                            workflows_to_commit = []
                            skipped_no_data = 0
                            skipped_no_hash = 0
                            skipped_unchanged = 0

                            for mapping in env_map_data:
                                canonical_id = mapping["canonical_id"]
                                env_hash = mapping.get("env_content_hash")
                                git_hash = git_hashes.get(canonical_id)
                                workflow_data = mapping.get("workflow_data")

                                if not workflow_data:
                                    skipped_no_data += 1
                                    continue
                                if not env_hash:
                                    skipped_no_hash += 1
                                    continue
                                if env_hash == git_hash:
                                    skipped_unchanged += 1
                                    continue
                                    
                                workflows_to_commit.append({
                                    "canonical_id": canonical_id,
                                    "workflow_data": workflow_data,
                                    "env_hash": env_hash
                                })
                            
                            logger.info(f"DEV sync: {len(workflows_to_commit)} to commit, {skipped_no_data} no workflow_data, {skipped_no_hash} no hash, {skipped_unchanged} unchanged")
                            
                            # Emit SSE with commit count
                            await emit_sync_progress(
                                job_id=job_id,
                                environment_id=environment_id,
                                status="running",
                                current_step="persisting_to_git",
                                current=0,
                                total=len(workflows_to_commit),
                                message=f"Committing {len(workflows_to_commit)} workflow(s) to Git...",
                                tenant_id=tenant_id
                            )

                            # Commit changed workflows to Git
                            if workflows_to_commit:
                                git_folder = environment.get("git_folder") or "dev"
                                committed_count = 0
                                commit_errors = []

                                for idx, wf in enumerate(workflows_to_commit):
                                    try:
                                        workflow_name = wf["workflow_data"].get("name", "Unknown")
                                        logger.info(f"DEV sync: Committing {wf['canonical_id']} ({workflow_name}) to {git_folder}/")
                                        
                                        await github.write_workflow_file(
                                            canonical_id=wf["canonical_id"],
                                            workflow_data=wf["workflow_data"],
                                            git_folder=git_folder,
                                            commit_message=f"sync(dev): update {workflow_name}"
                                        )

                                        # Update git_state with new hash
                                        db_service.client.table("canonical_workflow_git_state").upsert({
                                            "tenant_id": tenant_id,
                                            "environment_id": environment_id,
                                            "canonical_id": wf["canonical_id"],
                                            "git_content_hash": wf["env_hash"],
                                            "last_git_sync_at": datetime.utcnow().isoformat()
                                        }, on_conflict="tenant_id,environment_id,canonical_id").execute()

                                        committed_count += 1
                                        
                                        # Emit SSE progress
                                        await emit_sync_progress(
                                            job_id=job_id,
                                            environment_id=environment_id,
                                            status="running",
                                            current_step="persisting_to_git",
                                            current=committed_count,
                                            total=len(workflows_to_commit),
                                            message=f"Committed {committed_count}/{len(workflows_to_commit)}: {workflow_name}",
                                            tenant_id=tenant_id
                                        )
                                    except Exception as commit_err:
                                        error_msg = f"Failed to commit {wf['canonical_id']}: {commit_err}"
                                        logger.error(error_msg, exc_info=True)
                                        commit_errors.append(error_msg)

                                logger.info(f"DEV sync: committed {committed_count}/{len(workflows_to_commit)} workflows to Git")
                                if commit_errors:
                                    logger.error(f"DEV sync Git errors: {commit_errors}")
                            else:
                                logger.info("DEV sync: no workflow changes to commit to Git")
                                await emit_sync_progress(
                                    job_id=job_id,
                                    environment_id=environment_id,
                                    status="running",
                                    current_step="persisting_to_git",
                                    current=0,
                                    total=0,
                                    message="No workflow changes to commit to Git",
                                    tenant_id=tenant_id
                                )
                        else:
                            logger.error(f"DEV sync: Could not parse Git repo URL: {git_repo_url}")
                            await emit_sync_progress(
                                job_id=job_id,
                                environment_id=environment_id,
                                status="running",
                                current_step="persisting_to_git",
                                current=0,
                                total=0,
                                message=f"Git config error: invalid repo URL format",
                                tenant_id=tenant_id
                            )
                    else:
                        logger.warning(f"DEV environment has no Git configuration: repo_url={git_repo_url}, has_pat={bool(git_pat)}")
                        await emit_sync_progress(
                            job_id=job_id,
                            environment_id=environment_id,
                            status="running",
                            current_step="persisting_to_git",
                            current=0,
                            total=0,
                            message="Skipping Git: no repository configured",
                            tenant_id=tenant_id
                        )
                except Exception as git_err:
                    logger.error(f"Failed to commit DEV changes to Git: {git_err}", exc_info=True)
                    await emit_sync_progress(
                        job_id=job_id,
                        environment_id=environment_id,
                        status="running",
                        current_step="persisting_to_git",
                        current=0,
                        total=0,
                        message=f"Git error: {str(git_err)[:100]}",
                        tenant_id=tenant_id
                    )

            # Refresh workflow credential dependencies
            try:
                provider = environment.get("provider", "n8n") or "n8n"
                adapter_class = ProviderRegistry.get_adapter_class(provider)
                for workflow in workflows:
                    workflow_id = workflow.get("id")
                    workflow_data = workflow.get("workflow_data") or workflow

                    # Extract logical credentials
                    logical_keys = adapter_class.extract_logical_credentials(workflow_data)
                    
                    # Convert logical keys to logical credential IDs
                    logical_cred_ids = []
                    for key in logical_keys:
                        logical = await db_service.find_logical_credential_by_name(tenant_id, key)
                        if logical:
                            logical_cred_ids.append(logical.get("id"))
                    
                    # Upsert dependency record
                    await db_service.upsert_workflow_dependencies(
                        tenant_id=tenant_id,
                        environment_id=environment_id,
                        workflow_id=workflow_id,
                        provider=provider,
                        logical_credential_ids=logical_cred_ids
                    )
                
                logger.info(f"Refreshed credential dependencies for {len(workflows)} workflows")
            except Exception as dep_error:
                logger.warning(f"Failed to refresh workflow dependencies: {dep_error}")
                # Don't fail sync if dependency refresh fails
        except Exception as e:
            logger.error(f"Failed to sync workflows: {str(e)}")
            sync_results["workflows"]["errors"].append(str(e))

        # Sync executions (step 2/5)
        try:
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="running",
                current_step="executions",
                current=2,
                total=5,
                message="Syncing executions...",
                tenant_id=tenant_id
            )
            executions = await adapter.get_executions(limit=250)
            synced_executions = await db_service.sync_executions_from_n8n(
                tenant_id,
                environment_id,
                executions
            )
            sync_results["executions"]["synced"] = len(synced_executions)
        except Exception as e:
            logger.error(f"Failed to sync executions: {str(e)}")
            sync_results["executions"]["errors"].append(str(e))

        # Sync credentials (step 3/5)
        try:
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="running",
                current_step="credentials",
                current=3,
                total=5,
                message="Syncing credentials...",
                tenant_id=tenant_id
            )
            credentials = await adapter.get_credentials()
            synced_credentials = await db_service.sync_credentials_from_n8n(
                tenant_id,
                environment_id,
                credentials
            )
            sync_results["credentials"]["synced"] = len(synced_credentials)
        except Exception as e:
            sync_results["credentials"]["errors"].append(str(e))

        # Sync users (step 4/5)
        try:
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="running",
                current_step="users",
                current=4,
                total=5,
                message="Syncing users...",
                tenant_id=tenant_id
            )
            users = await adapter.get_users()
            if not users:
                logger.warning(f"No users returned from N8N for environment {environment_id}")
            synced_users = await db_service.sync_n8n_users_from_n8n(
                tenant_id,
                environment_id,
                users or []
            )
            sync_results["users"]["synced"] = len(synced_users)
        except Exception as e:
            logger.error(f"Failed to sync users: {str(e)}")
            sync_results["users"]["errors"].append(str(e))

        # Sync tags (step 5/5)
        try:
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="running",
                current_step="tags",
                current=5,
                total=5,
                message="Syncing tags...",
                tenant_id=tenant_id
            )
            tags = await adapter.get_tags()
            synced_tags = await db_service.sync_tags_from_n8n(
                tenant_id,
                environment_id,
                tags
            )
            sync_results["tags"]["synced"] = len(synced_tags)
        except Exception as e:
            sync_results["tags"]["errors"].append(str(e))

        # Check if all syncs were successful
        has_errors = any(
            sync_results[key]["errors"]
            for key in ["workflows", "executions", "credentials", "users", "tags"]
        )

        # Update job status
        final_status = BackgroundJobStatus.COMPLETED if not has_errors else BackgroundJobStatus.FAILED
        
        # Update last_connected and last_sync_at timestamps only on successful completion
        if final_status == BackgroundJobStatus.COMPLETED:
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
        await background_job_service.update_job_status(
            job_id=job_id,
            status=final_status,
            progress={
                "current": 5,
                "total": 5,
                "percentage": 100,
                "message": "Sync completed successfully" if not has_errors else "Sync completed with errors"
            },
            result=sync_results,
            error_message="Sync completed with errors" if has_errors else None,
            error_details={"errors": sync_results} if has_errors else None
        )

        await emit_sync_progress(
            job_id=job_id,
            environment_id=environment_id,
            status="completed" if not has_errors else "failed",
            current_step="completed",
            current=5,
            total=5,
            message="Sync completed successfully" if not has_errors else "Sync completed with errors",
            errors=sync_results if has_errors else None,
            tenant_id=tenant_id
        )

        # Create audit log
        try:
            provider = environment.get("provider", "n8n") or "n8n"
            action_type = AuditActionType.ENVIRONMENT_SYNC_COMPLETED if not has_errors else AuditActionType.ENVIRONMENT_SYNC_FAILED
            await create_audit_log(
                action_type=action_type,
                action=f"Environment sync {'completed' if not has_errors else 'failed'}",
                tenant_id=tenant_id,
                resource_type="environment",
                resource_id=environment_id,
                resource_name=environment.get("n8n_name", environment_id),
                provider=provider,
                new_value={
                    "job_id": job_id,
                    "results": sync_results,
                    "has_errors": has_errors
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to create audit log: {str(audit_error)}")

    except Exception as e:
        logger.error(f"Background sync failed for environment {environment_id}: {str(e)}")
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=str(e),
            error_details={"error_type": type(e).__name__}
        )
        await emit_sync_progress(
            job_id=job_id,
            environment_id=environment_id,
            status="failed",
            current_step="error",
            current=0,
            total=5,
            message=f"Sync failed: {str(e)}",
            errors={"error": str(e)},
            tenant_id=tenant_id
        )
        # Create audit log for failure
        try:
            provider = environment.get("provider", "n8n") or "n8n"
            await create_audit_log(
                action_type=AuditActionType.ENVIRONMENT_SYNC_FAILED,
                action=f"Environment sync failed: {str(e)}",
                tenant_id=tenant_id,
                resource_type="environment",
                resource_id=environment_id,
                resource_name=environment.get("n8n_name", environment_id),
                provider=provider,
                new_value={
                    "job_id": job_id,
                    "error": str(e)
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to create audit log: {str(audit_error)}")


@router.post("/{environment_id}/sync")
async def sync_environment(
    environment_id: str,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(require_entitlement("environment_basic"))
):
    """
    Sync workflows, executions, credentials, tags, and users from N8N to database.
    Returns immediately with job_id. Sync runs in background.
    """
    try:
        # Get tenant_id from authenticated user
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        tenant_id = tenant["id"]
        user = user_info.get("user", {})
        user_id = user.get("id", "00000000-0000-0000-0000-000000000000")
        user_role = user.get("role", "user")
        
        # Get environment details
        environment = await db_service.get_environment(environment_id, tenant_id)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )
        
        # Check action guard
        env_class_str = environment.get("environment_class", "dev")
        try:
            env_class = EnvironmentClass(env_class_str)
        except ValueError:
            env_class = EnvironmentClass.DEV
        
        try:
            environment_action_guard.assert_can_perform_action(
                env_class=env_class,
                action=EnvironmentAction.SYNC_STATUS,
                user_role=user_role,
                environment_name=environment.get("n8n_name", environment_id)
            )
        except ActionGuardError as e:
            raise e

        # Create provider adapter for connection test
        adapter = ProviderRegistry.get_adapter_for_environment(environment)

        # Test connection first (fail fast if not connected)
        is_connected = await adapter.test_connection()
        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to provider instance. Please check environment configuration."
            )

        # Create background job
        job = await background_job_service.create_job(
            tenant_id=tenant_id,
            job_type=BackgroundJobType.ENVIRONMENT_SYNC,
            resource_id=environment_id,
            resource_type="environment",
            created_by=user_id,
            initial_progress={
                "current": 0,
                "total": 5,
                "percentage": 0,
                "message": "Initializing sync..."
            }
        )
        job_id = job["id"]

        # Create audit log for sync start
        try:
            provider = environment.get("provider", "n8n") or "n8n"
            await create_audit_log(
                action_type=AuditActionType.ENVIRONMENT_SYNC_STARTED,
                action=f"Started environment sync",
                tenant_id=tenant_id,
                resource_type="environment",
                resource_id=environment_id,
                resource_name=environment.get("n8n_name", environment_id),
                provider=provider,
                new_value={
                    "job_id": job_id
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to create audit log: {str(audit_error)}")

        # Start background task
        background_tasks.add_task(
            _sync_environment_background,
            job_id=job_id,
            environment_id=environment_id,
            environment=environment,
            tenant_id=tenant_id
        )

        return {
            "job_id": job_id,
            "status": "running",
            "message": "Sync started in background"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start sync: {str(e)}"
        )


@router.get("/{environment_id}/jobs")
async def get_environment_jobs(
    environment_id: str,
    user_info: dict = Depends(get_current_user),
    limit: int = 10,
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """Get recent background jobs for an environment"""
    try:
        tenant_id = get_tenant_id(user_info)
        jobs = await background_job_service.get_jobs_by_resource(
            resource_type="environment",
            resource_id=environment_id,
            tenant_id=tenant_id,
            limit=limit
        )
        return jobs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get jobs: {str(e)}"
        )


@router.post("/{environment_id}/sync-users")
async def sync_users_only(
    environment_id: str,
    user_info: dict = Depends(get_current_user)
):
    """
    Sync only users from N8N to database.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get environment details
        environment = await db_service.get_environment(environment_id, tenant_id)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create provider adapter for this environment
        adapter = ProviderRegistry.get_adapter_for_environment(environment)

        # Test connection first
        is_connected = await adapter.test_connection()
        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to provider instance. Please check environment configuration."
            )

        # Sync users only
        try:
            users = await adapter.get_users()
            if not users:
                logger.warning(f"No users returned from N8N for environment {environment_id}")
            logger.info(f"Fetched {len(users) if users else 0} users from N8N for environment {environment_id}")
            synced_users = await db_service.sync_n8n_users_from_n8n(
                tenant_id,
                environment_id,
                users or []
            )

            return {
                "success": True,
                "message": "Users synced successfully",
                "synced": len(synced_users)
            }
        except Exception as e:
            logger.error(f"Failed to sync users for environment {environment_id}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"Failed to sync users: {str(e)}",
                "synced": 0
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync users: {str(e)}"
        )


@router.post("/{environment_id}/sync-executions")
async def sync_executions_only(
    environment_id: str,
    user_info: dict = Depends(get_current_user)
):
    """
    Sync only executions from N8N to database.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get environment details
        environment = await db_service.get_environment(environment_id, tenant_id)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create provider adapter for this environment
        adapter = ProviderRegistry.get_adapter_for_environment(environment)

        # Test connection first
        is_connected = await adapter.test_connection()
        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to provider instance. Please check environment configuration."
            )

        # Generate job ID for progress tracking
        job_id = str(uuid4())

        # Sync executions only
        try:
            # Emit start progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="running",
                current_step="executions",
                current=0,
                total=1,
                message="Starting execution sync...",
                tenant_id=tenant_id
            )

            # N8N enforces a max limit (commonly 250). Use a safe upper bound.
            # NOTE: With pagination support, this will now fetch multiple pages if needed.
            executions = await adapter.get_executions(limit=250)

            if not executions:
                logger.warning(f"No executions returned from N8N for environment {environment_id}")

            synced_executions = await db_service.sync_executions_from_n8n(
                tenant_id,
                environment_id,
                executions
            )

            # Emit completion progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="completed",
                current_step="executions",
                current=1,
                total=1,
                message=f"Synced {len(synced_executions)} executions successfully",
                tenant_id=tenant_id
            )

            return {
                "success": True,
                "message": "Executions synced successfully",
                "synced": len(synced_executions),
                "job_id": job_id  # Include job_id for progress tracking
            }
        except Exception as e:
            logger.error(f"Failed to sync executions for environment {environment_id}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

            # Emit failure progress
            await emit_sync_progress(
                job_id=job_id,
                environment_id=environment_id,
                status="failed",
                current_step="executions",
                current=0,
                total=1,
                message=f"Sync failed: {str(e)}",
                tenant_id=tenant_id
            )

            return {
                "success": False,
                "message": f"Failed to sync executions: {str(e)}",
                "synced": 0,
                "job_id": job_id
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync executions: {str(e)}"
        )


@router.post("/{environment_id}/sync-tags")
async def sync_tags_only(
    environment_id: str,
    user_info: dict = Depends(get_current_user)
):
    """
    Sync only tags from N8N to database.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get environment details
        environment = await db_service.get_environment(environment_id, tenant_id)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Create provider adapter for this environment
        adapter = ProviderRegistry.get_adapter_for_environment(environment)

        # Test connection first
        is_connected = await adapter.test_connection()
        if not is_connected:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cannot connect to provider instance. Please check environment configuration."
            )

        # Sync tags only
        try:
            tags = await adapter.get_tags()
            synced_tags = await db_service.sync_tags_from_n8n(
                tenant_id,
                environment_id,
                tags
            )

            return {
                "success": True,
                "message": "Tags synced successfully",
                "synced": len(synced_tags)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to sync tags: {str(e)}",
                "synced": 0
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync tags: {str(e)}"
        )


# =============================================================================
# Drift Detection Endpoints
# =============================================================================

@router.get("/{environment_id}/drift")
async def get_environment_drift(
    environment_id: str,
    user_info: dict = Depends(get_current_user),
    refresh: bool = False,
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """
    Get drift status for an environment.

    By default returns cached drift status. Set refresh=true to run fresh detection.

    Returns:
        - driftStatus: IN_SYNC | DRIFT_DETECTED | UNKNOWN | ERROR
        - lastDriftDetectedAt: Timestamp of last detection
        - summary: Detailed drift summary (when refresh=true or recently detected)
    """
    from app.services.drift_detection_service import drift_detection_service

    try:
        tenant_id = get_tenant_id(user_info)
        if refresh:
            # Run fresh drift detection
            summary = await drift_detection_service.detect_drift(
                tenant_id=tenant_id,
                environment_id=environment_id,
                update_status=True
            )
            return {
                "driftStatus": "DRIFT_DETECTED" if (summary.with_drift > 0 or summary.not_in_git > 0) else "IN_SYNC",
                "lastDriftDetectedAt": summary.last_detected_at,
                "gitConfigured": summary.git_configured,
                "summary": summary.to_dict(),
                "error": summary.error
            }
        else:
            # Return cached status
            cached = await drift_detection_service.get_cached_drift_status(
                tenant_id=tenant_id,
                environment_id=environment_id
            )
            return cached

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get drift status: {str(e)}"
        )


@router.post("/{environment_id}/drift/refresh")
async def refresh_environment_drift(
    environment_id: str,
    background_tasks: BackgroundTasks,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("environment_basic"))
):
    """
    Trigger a fresh drift detection for an environment.

    Runs drift detection in the foreground and returns the full summary.
    For very large environments, consider using background job approach.
    """
    from app.services.drift_detection_service import drift_detection_service

    try:
        tenant_id = get_tenant_id(user_info)
        # Verify environment exists
        environment = await db_service.get_environment(environment_id, tenant_id)
        if not environment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Run drift detection
        summary = await drift_detection_service.detect_drift(
            tenant_id=tenant_id,
            environment_id=environment_id,
            update_status=True
        )

        return {
            "success": True,
            "driftStatus": "DRIFT_DETECTED" if (summary.with_drift > 0 or summary.not_in_git > 0) else "IN_SYNC",
            "lastDriftDetectedAt": summary.last_detected_at,
            "gitConfigured": summary.git_configured,
            "summary": summary.to_dict(),
            "error": summary.error
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh drift status: {str(e)}"
        )


