from fastapi import APIRouter, HTTPException, status, UploadFile, File, Body, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
import json
import zipfile
import io
import re
from datetime import datetime
import logging

from app.schemas.workflow import WorkflowResponse, WorkflowUpload, WorkflowTagsUpdate
from app.services.provider_registry import ProviderRegistry
from app.services.database import db_service
from app.services.github_service import GitHubService
from app.services.diff_service import compare_workflows
from app.services.sync_status_service import compute_sync_status
from app.core.entitlements_gate import require_workflow_limit, require_entitlement
from app.api.endpoints.admin_audit import create_audit_log, AuditActionType
from app.services.background_job_service import (
    background_job_service,
    BackgroundJobStatus,
    BackgroundJobType
)
from app.api.endpoints.sse import emit_backup_progress

logger = logging.getLogger(__name__)

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


async def resolve_environment_config(
    environment_id: Optional[str] = None,
    environment: Optional[str] = None
) -> Dict[str, Any]:
    """
    Helper function to resolve environment configuration.
    Prefers environment_id, falls back to environment type for backward compatibility.
    """
    if environment_id:
        env_config = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment with ID '{environment_id}' not found"
            )
        return env_config
    elif environment:
        env_config = await db_service.get_environment_by_type(MOCK_TENANT_ID, environment)
        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment '{environment}' not configured"
            )
        return env_config
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either environment_id or environment parameter is required"
        )


@router.get("/", response_model=List[Dict[str, Any]])
async def get_workflows(
    environment_id: Optional[str] = None,
    environment: Optional[str] = None,  # Deprecated: use environment_id instead
    force_refresh: bool = False,
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """
    Get all workflows for the specified environment.

    By default, returns cached workflows from the database.
    Use force_refresh=true to fetch fresh data from N8N API and update the cache.
    
    Args:
        environment_id: Environment UUID (preferred)
        environment: Environment type string (deprecated, for backward compatibility)
    """
    try:
        env_config = await resolve_environment_config(environment_id, environment)
        env_id = env_config.get("id")

        # Try to get workflows from cache first (unless force_refresh is requested)
        if not force_refresh:
            cached_workflows = await db_service.get_workflows(MOCK_TENANT_ID, env_id)

            if cached_workflows is not None:
                # Transform cached workflows to match frontend expectations (including empty lists)
                transformed_workflows = []
                for cached in cached_workflows:
                    # Extract data from workflow_data JSONB field
                    workflow_data = cached.get("workflow_data", {})

                    workflow_obj = {
                        "id": cached.get("n8n_workflow_id"),
                        "name": cached.get("name"),
                        "description": "",
                        "active": cached.get("active", False),
                        "tags": cached.get("tags", []),
                        "createdAt": cached.get("created_at"),
                        "updatedAt": cached.get("updated_at"),
                        "nodes": workflow_data.get("nodes", []),
                        "connections": workflow_data.get("connections", {}),
                        "settings": workflow_data.get("settings", {}),
                        "lastSyncedAt": cached.get("last_synced_at"),  # Extra field for frontend to show cache status
                        "syncStatus": cached.get("sync_status")  # Sync status field
                    }
                    # Include analysis if available
                    if cached.get("analysis"):
                        workflow_obj["analysis"] = cached.get("analysis")
                    transformed_workflows.append(workflow_obj)

                return transformed_workflows

        # If no cache or force_refresh, fetch from N8N
        # Create provider adapter for environment
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Fetch workflows from provider
        workflows = await adapter.get_workflows()

        # Compute analysis for each workflow
        from app.services.workflow_analysis_service import analyze_workflow
        workflows_with_analysis = {}
        for workflow in workflows:
            try:
                analysis = analyze_workflow(workflow)
                workflows_with_analysis[workflow.get("id")] = analysis
            except Exception as e:
                # Log error but continue - analysis is optional
                import logging
                logging.warning(f"Failed to analyze workflow {workflow.get('id', 'unknown')}: {str(e)}")
                # Continue without analysis for this workflow

        # Sync workflows to database cache with analysis
        await db_service.sync_workflows_from_n8n(
            MOCK_TENANT_ID, 
            env_id, 
            workflows,
            workflows_with_analysis=workflows_with_analysis if workflows_with_analysis else None
        )

        # Compute sync status for all workflows if GitHub is configured
        sync_status_map = {}
        if env_config.get("git_repo_url"):
            try:
                # Create GitHub service
                repo_url = env_config.get("git_repo_url", "").rstrip('/').replace('.git', '')
                repo_parts = repo_url.split("/")
                github_service = GitHubService(
                    token=env_config.get("git_pat"),
                    repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
                    repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
                    branch=env_config.get("git_branch", "main")
                )
                
                if github_service.is_configured():
                    # Get all workflows from GitHub (using environment type key for folder path)
                    # get_all_workflows_from_github returns Dict[workflow_id, workflow_data]
                    env_type = env_config.get("n8n_type")
                    if not env_type:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Environment type is required for GitHub workflow operations. Set the environment type and try again.",
                        )
                    github_workflow_map = await github_service.get_all_workflows_from_github(environment_type=env_type)
                    
                    # Compute sync status for each workflow
                    for workflow in workflows:
                        workflow_id = workflow.get("id")
                        try:
                            github_workflow = github_workflow_map.get(workflow_id)
                            cached_workflow = await db_service.get_workflow(MOCK_TENANT_ID, env_id, workflow_id)
                            last_synced_at = cached_workflow.get("last_synced_at") if cached_workflow else None
                            
                            sync_status = compute_sync_status(
                                n8n_workflow=workflow,
                                github_workflow=github_workflow,
                                last_synced_at=last_synced_at,
                                n8n_updated_at=workflow.get("updatedAt"),
                                github_updated_at=github_workflow.get("updatedAt") if github_workflow else None
                            )
                            
                            sync_status_map[workflow_id] = sync_status
                            
                            # Update in database
                            await db_service.update_workflow_sync_status(
                                tenant_id=MOCK_TENANT_ID,
                                environment_id=env_id,
                                n8n_workflow_id=workflow_id,
                                sync_status=sync_status
                            )
                        except Exception as status_error:
                            # Log but continue
                            print(f"Failed to compute sync status for workflow {workflow_id}: {str(status_error)}")
            except Exception as e:
                # Log but don't fail the request
                print(f"Failed to compute sync statuses: {str(e)}")

        # Transform the response to match our frontend expectations
        transformed_workflows = []
        for workflow in workflows:
            # Transform tags from objects to strings
            tags = workflow.get("tags", [])
            tag_strings = []
            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, dict):
                        tag_strings.append(tag.get("name", ""))
                    elif isinstance(tag, str):
                        tag_strings.append(tag)

            workflow_obj = {
                "id": workflow.get("id"),
                "name": workflow.get("name"),
                "description": "",  # N8N doesn't have description field
                "active": workflow.get("active", False),
                "tags": tag_strings,
                "createdAt": workflow.get("createdAt"),
                "updatedAt": workflow.get("updatedAt"),
                "nodes": workflow.get("nodes", []),
                "connections": workflow.get("connections", {}),
                "settings": workflow.get("settings", {}),
                "syncStatus": sync_status_map.get(workflow.get("id"))  # Include sync status
            }
            # Include analysis if available
            workflow_id = workflow.get("id")
            if workflow_id in workflows_with_analysis:
                workflow_obj["analysis"] = workflows_with_analysis[workflow_id]
            transformed_workflows.append(workflow_obj)

        # Update the workflow count in the environment record
        try:
            await db_service.update_environment_workflow_count(
                environment_id=env_id,
                tenant_id=MOCK_TENANT_ID,
                count=len(transformed_workflows)
            )
        except Exception as e:
            # Log error but don't fail the request
            print(f"Failed to update workflow count: {str(e)}")

        return transformed_workflows

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch workflows: {str(e)}"
        )


def _sanitize_filename(name: str) -> str:
    """Sanitize a string to be used as a filename"""
    # Replace invalid filename characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove any leading/trailing spaces or dots
    sanitized = sanitized.strip('. ')
    # Limit length to 200 characters
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized if sanitized else "workflow"


@router.get("/download")
async def download_workflows(environment_id: str):
    """Download all workflows from an environment as a ZIP file"""
    try:
        print(f"DEBUG: Attempting to download workflows for environment_id: {environment_id}")
        # Get environment configuration by ID
        env_config = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        print(f"DEBUG: Retrieved env_config: {env_config}")

        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment not found"
            )

        # Validate that API key exists
        if not env_config.get("api_key"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment does not have an API key configured"
            )

        # Create provider adapter for environment
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Fetch all workflows from provider
        workflows = await adapter.get_workflows()

        if not workflows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No workflows found in this environment"
            )

        # Create in-memory zip file
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Track filenames to handle duplicates
            used_filenames = set()

            for workflow in workflows:
                try:
                    # Get full workflow details
                    workflow_id = workflow.get("id")
                    full_workflow = await adapter.get_workflow(workflow_id)

                    # Create filename from workflow name
                    workflow_name = full_workflow.get("name", f"workflow_{workflow_id}")
                    base_filename = _sanitize_filename(workflow_name)
                    filename = f"{base_filename}.json"

                    # Handle duplicate filenames
                    counter = 1
                    while filename in used_filenames:
                        filename = f"{base_filename}_{workflow_id[:8]}.json"
                        if filename in used_filenames:
                            filename = f"{base_filename}_{counter}.json"
                            counter += 1

                    used_filenames.add(filename)

                    # Add workflow to zip
                    workflow_json = json.dumps(full_workflow, indent=2)
                    zip_file.writestr(filename, workflow_json)

                except Exception as workflow_error:
                    # Log error but continue with other workflows
                    print(f"Failed to download workflow {workflow.get('id')}: {str(workflow_error)}")
                    continue

        # Prepare zip for download
        zip_buffer.seek(0)

        # Create filename with environment name and timestamp
        env_name = _sanitize_filename(env_config.get("name", "environment"))
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"{env_name}_workflows_{timestamp}.zip"

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Error in download_workflows: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download workflows: {str(e)}"
        )


@router.post("/sync-from-github")
async def sync_workflows_from_github(
    environment_id: Optional[str] = None,
    environment: Optional[str] = None,  # Deprecated: use environment_id instead
    _: dict = Depends(require_entitlement("workflow_push"))
):
    """Sync workflows from GitHub to N8N"""
    try:
        env_config = await resolve_environment_config(environment_id, environment)

        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment '{environment}' not configured"
            )

        # Check if GitHub is configured for this environment
        if not env_config.get("git_repo_url"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="GitHub configuration not found for this environment"
            )

        # Create GitHub service from environment configuration
        repo_url = env_config.get("git_repo_url", "").rstrip('/').replace('.git', '')
        repo_parts = repo_url.split("/")
        github_service = GitHubService(
            token=env_config.get("git_pat"),
            repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
            repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
            branch=env_config.get("git_branch", "main")
        )

        # Get workflows from GitHub (using environment type key for folder path)
        # get_all_workflows_from_github returns Dict[workflow_id, workflow_data]
        env_type = env_config.get("n8n_type")
        if not env_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment type is required for GitHub workflow operations. Set the environment type and try again.",
            )
        github_workflow_map = await github_service.get_all_workflows_from_github(environment_type=env_type)

        # Create provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Upload workflows to provider
        synced_workflows = []
        errors = []

        for workflow_id, workflow_data in github_workflow_map.items():
            result = await _upload_single_workflow(
                workflow_data,
                adapter,
                None,  # Don't sync back to GitHub
                MOCK_TENANT_ID,
                env_config.get("id")
            )
            if result["success"]:
                synced_workflows.append(result["workflow"])
            else:
                errors.append(result["error"])

        # After syncing from GitHub, recompute sync status for all workflows
        # Get all workflows from provider
        n8n_workflows = await adapter.get_workflows()
        
        # Compute sync status for all workflows
        for workflow in n8n_workflows:
            workflow_id = workflow.get("id")
            try:
                github_workflow = github_workflow_map.get(workflow_id)
                cached_workflow = await db_service.get_workflow(MOCK_TENANT_ID, env_config.get("id"), workflow_id)
                last_synced_at = cached_workflow.get("last_synced_at") if cached_workflow else None
                
                sync_status = compute_sync_status(
                    n8n_workflow=workflow,
                    github_workflow=github_workflow,
                    last_synced_at=last_synced_at,
                    n8n_updated_at=workflow.get("updatedAt"),
                    github_updated_at=github_workflow.get("updatedAt") if github_workflow else None
                )
                
                # Update in database
                await db_service.update_workflow_sync_status(
                    tenant_id=MOCK_TENANT_ID,
                    environment_id=env_config.get("id"),
                    n8n_workflow_id=workflow_id,
                    sync_status=sync_status
                )
            except Exception as status_error:
                # Log but continue
                print(f"Failed to compute sync status for workflow {workflow_id}: {str(status_error)}")

        return {
            "success": len(synced_workflows) > 0,
            "synced": len(synced_workflows),
            "failed": len(errors),
            "workflows": synced_workflows,
            "errors": errors
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync workflows from GitHub: {str(e)}"
        )


async def _backup_workflows_to_github_background(
    job_id: str,
    environment_id: str,
    env_config: dict,
    force: bool,
    tenant_id: str
):
    """Background task for backing up workflows to GitHub."""
    try:
        # Update job status to running
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING,
            progress={
                "current": 0,
                "total": 1,
                "percentage": 0,
                "message": "Initializing backup..."
            }
        )

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
            raise Exception("GitHub is not properly configured")

        # Create provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Get all workflows
        workflows = await adapter.get_workflows()
        if not workflows:
            raise Exception("No workflows found in this environment")

        # Filter workflows to sync
        last_backup = env_config.get("last_backup")
        workflows_to_sync = []
        
        if force:
            workflows_to_sync = workflows
        elif last_backup:
            last_backup_dt = datetime.fromisoformat(last_backup.replace('Z', '+00:00')) if isinstance(last_backup, str) else last_backup
            for workflow in workflows:
                updated_at_str = workflow.get("updatedAt")
                if updated_at_str:
                    updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                    if updated_at > last_backup_dt:
                        workflows_to_sync.append(workflow)
                else:
                    workflows_to_sync.append(workflow)
        else:
            workflows_to_sync = workflows

        env_type = env_config.get("n8n_type")
        if not env_type:
            raise Exception("Environment type is required for GitHub workflow operations")

        # Get GitHub workflows for comparison
        github_workflow_map = await github_service.get_all_workflows_from_github(environment_type=env_type)

        # Sync workflows
        synced_workflows = []
        errors = []
        total = len(workflows_to_sync)

        for idx, workflow in enumerate(workflows_to_sync):
            try:
                workflow_id = workflow.get("id")
                full_workflow = await adapter.get_workflow(workflow_id)

                await emit_backup_progress(
                    job_id=job_id,
                    environment_id=environment_id,
                    status="running",
                    current=idx + 1,
                    total=total,
                    current_workflow_name=full_workflow.get("name"),
                    message=f"Backing up workflow {idx + 1} of {total}"
                )

                await github_service.sync_workflow_to_github(
                    workflow_id=workflow_id,
                    workflow_name=full_workflow.get("name"),
                    workflow_data=full_workflow,
                    environment_type=env_type
                )

                synced_workflows.append({
                    "id": workflow_id,
                    "name": full_workflow.get("name")
                })

                await background_job_service.update_progress(
                    job_id=job_id,
                    current=idx + 1,
                    total=total,
                    message=f"Backed up {full_workflow.get('name')}"
                )

            except Exception as sync_error:
                error_msg = f"Failed to sync workflow {workflow.get('id')}: {str(sync_error)}"
                errors.append(error_msg)
                logger.error(error_msg)
                continue

        # Compute sync status for all workflows
        for workflow in workflows:
            workflow_id = workflow.get("id")
            try:
                full_workflow = await adapter.get_workflow(workflow_id)
                github_workflow = github_workflow_map.get(workflow_id)
                cached_workflow = await db_service.get_workflow(MOCK_TENANT_ID, env_config.get("id"), workflow_id)
                last_synced_at = cached_workflow.get("last_synced_at") if cached_workflow else None
                
                sync_status = compute_sync_status(
                    n8n_workflow=full_workflow,
                    github_workflow=github_workflow,
                    last_synced_at=last_synced_at,
                    n8n_updated_at=full_workflow.get("updatedAt"),
                    github_updated_at=github_workflow.get("updatedAt") if github_workflow else None
                )
                
                await db_service.update_workflow_sync_status(
                    tenant_id=MOCK_TENANT_ID,
                    environment_id=env_config.get("id"),
                    n8n_workflow_id=workflow_id,
                    sync_status=sync_status
                )
            except Exception as status_error:
                logger.warning(f"Failed to compute sync status for workflow {workflow_id}: {str(status_error)}")
                continue

        # Update last_backup timestamp
        if synced_workflows:
            await db_service.update_environment(
                env_config.get("id"),
                MOCK_TENANT_ID,
                {"last_backup": datetime.utcnow().isoformat()}
            )

        skipped_count = len(workflows) - len(workflows_to_sync)
        has_errors = len(errors) > 0
        final_status = BackgroundJobStatus.COMPLETED if not has_errors else BackgroundJobStatus.FAILED

        await background_job_service.update_job_status(
            job_id=job_id,
            status=final_status,
            progress={
                "current": total,
                "total": total,
                "percentage": 100,
                "message": f"Backup completed: {len(synced_workflows)} synced, {skipped_count} skipped"
            },
            result={
                "synced": len(synced_workflows),
                "skipped": skipped_count,
                "failed": len(errors),
                "workflows": synced_workflows
            },
            error_message=f"Backup completed with {len(errors)} errors" if has_errors else None,
            error_details={"errors": errors} if has_errors else None
        )

        await emit_backup_progress(
            job_id=job_id,
            environment_id=environment_id,
            status="completed" if not has_errors else "failed",
            current=total,
            total=total,
            message=f"Backup completed: {len(synced_workflows)} synced" if not has_errors else f"Backup completed with {len(errors)} errors",
            errors=errors if has_errors else None
        )

        # Create audit log
        try:
            provider = env_config.get("provider", "n8n") or "n8n"
            action_type = AuditActionType.GITHUB_BACKUP_COMPLETED if not has_errors else AuditActionType.GITHUB_BACKUP_FAILED
            await create_audit_log(
                action_type=action_type,
                action=f"GitHub backup {'completed' if not has_errors else 'failed'}",
                tenant_id=tenant_id,
                resource_type="environment",
                resource_id=environment_id,
                resource_name=env_config.get("n8n_name", environment_id),
                provider=provider,
                new_value={
                    "job_id": job_id,
                    "synced": len(synced_workflows),
                    "skipped": skipped_count,
                    "failed": len(errors),
                    "errors": errors if has_errors else None
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to create audit log: {str(audit_error)}")

    except Exception as e:
        logger.error(f"Background backup failed for environment {environment_id}: {str(e)}")
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=str(e),
            error_details={"error_type": type(e).__name__}
        )
        await emit_backup_progress(
            job_id=job_id,
            environment_id=environment_id,
            status="failed",
            current=0,
            total=1,
            message=f"Backup failed: {str(e)}",
            errors=[str(e)]
        )
        # Create audit log for failure
        try:
            provider = env_config.get("provider", "n8n") or "n8n"
            await create_audit_log(
                action_type=AuditActionType.GITHUB_BACKUP_FAILED,
                action=f"GitHub backup failed: {str(e)}",
                tenant_id=tenant_id,
                resource_type="environment",
                resource_id=environment_id,
                resource_name=env_config.get("n8n_name", environment_id),
                provider=provider,
                new_value={
                    "job_id": job_id,
                    "error": str(e)
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to create audit log: {str(audit_error)}")


@router.post("/sync-to-github")
async def sync_workflows_to_github(
    background_tasks: BackgroundTasks,
    environment_id: Optional[str] = None,
    environment: Optional[str] = None,  # Deprecated: use environment_id instead
    force: bool = False,  # Force full sync, bypassing incremental check
    user_info: dict = Depends(require_entitlement("workflow_push"))
):
    """Backup/sync all workflows from N8N to GitHub. Returns immediately with job_id. Backup runs in background."""
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
        
        env_config = await resolve_environment_config(environment_id, environment)

        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment '{environment}' not configured"
            )

        # Check if GitHub is configured
        if not env_config.get("git_repo_url"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="GitHub configuration not found for this environment"
            )

        # Create GitHub service for validation
        repo_url = env_config.get("git_repo_url", "").rstrip('/').replace('.git', '')
        repo_parts = repo_url.split("/")
        github_service = GitHubService(
            token=env_config.get("git_pat"),
            repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
            repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
            branch=env_config.get("git_branch", "main")
        )

        if not github_service.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub is not properly configured"
            )

        # Create background job
        job = await background_job_service.create_job(
            tenant_id=tenant_id,
            job_type=BackgroundJobType.GITHUB_SYNC_TO,
            resource_id=env_config.get("id"),
            resource_type="environment",
            created_by=user_id,
            initial_progress={
                "current": 0,
                "total": 1,
                "percentage": 0,
                "message": "Initializing backup..."
            }
        )
        job_id = job["id"]

        # Create audit log for backup start
        try:
            provider = env_config.get("provider", "n8n") or "n8n"
            await create_audit_log(
                action_type=AuditActionType.GITHUB_BACKUP_STARTED,
                action=f"Started GitHub backup",
                tenant_id=tenant_id,
                resource_type="environment",
                resource_id=env_config.get("id"),
                resource_name=env_config.get("n8n_name", env_config.get("id")),
                provider=provider,
                new_value={
                    "job_id": job_id,
                    "force": force
                }
            )
        except Exception as audit_error:
            logger.warning(f"Failed to create audit log: {str(audit_error)}")

        # Start background task
        background_tasks.add_task(
            _backup_workflows_to_github_background,
            job_id=job_id,
            environment_id=env_config.get("id"),
            env_config=env_config,
            force=force,
            tenant_id=tenant_id
        )

        return {
            "job_id": job_id,
            "status": "running",
            "message": "Backup started in background"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start backup: {str(e)}"
        )


@router.get("/drift", response_model=Dict[str, Any])
async def get_all_workflows_drift(
    environment_id: Optional[str] = None,
    environment: Optional[str] = None  # Deprecated: use environment_id instead
):
    """
    Get drift status for all workflows in the environment.

    Compares all runtime workflows against their GitHub versions.
    Returns aggregated drift analysis for the entire environment.
    """
    try:
        env_config = await resolve_environment_config(environment_id, environment)

        # Check if GitHub is configured
        if not env_config.get("git_repo_url") or not env_config.get("git_pat"):
            return {
                "gitConfigured": False,
                "message": "GitHub is not configured for this environment",
                "workflows": [],
                "summary": {
                    "total": 0,
                    "withDrift": 0,
                    "notInGit": 0,
                    "inSync": 0
                }
            }

        # Create provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

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
            return {
                "gitConfigured": False,
                "message": "GitHub is not properly configured",
                "workflows": [],
                "summary": {
                    "total": 0,
                    "withDrift": 0,
                    "notInGit": 0,
                    "inSync": 0
                }
            }

        # Fetch all workflows from provider
        runtime_workflows = await adapter.get_workflows()

        # Fetch all workflows from GitHub (using environment type key for folder path)
        # get_all_workflows_from_github returns Dict[workflow_id, workflow_data]
        env_type = env_config.get("n8n_type")
        if not env_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment type is required for GitHub workflow operations. Set the environment type and try again.",
            )
        git_workflows_map = await github_service.get_all_workflows_from_github(environment_type=env_type)

        # Create a map of git workflows by name
        git_by_name = {}
        for wf_id, gw in git_workflows_map.items():
            # The workflow data is the dict itself
            name = gw.get("name", "")
            if name:
                git_by_name[name] = gw

        # Compare each runtime workflow
        workflow_results = []
        summary = {
            "total": len(runtime_workflows),
            "withDrift": 0,
            "notInGit": 0,
            "inSync": 0
        }

        for runtime_wf in runtime_workflows:
            wf_name = runtime_wf.get("name", "")
            wf_id = runtime_wf.get("id", "")

            git_entry = git_by_name.get(wf_name)

            if git_entry is None:
                # Not in Git
                summary["notInGit"] += 1
                workflow_results.append({
                    "id": wf_id,
                    "name": wf_name,
                    "active": runtime_wf.get("active", False),
                    "hasDrift": False,
                    "notInGit": True,
                    "lastCommitSha": None,
                    "lastCommitDate": None,
                    "summary": None
                })
            else:
                # Compare - git_entry IS the workflow data itself
                git_workflow = git_entry
                # We don't have commit info from get_all_workflows_from_github
                # Set to None for now (could be enhanced later)
                last_commit_sha = None
                last_commit_date = None

                drift_result = compare_workflows(
                    git_workflow=git_workflow,
                    runtime_workflow=runtime_wf,
                    last_commit_sha=last_commit_sha,
                    last_commit_date=last_commit_date
                )

                if drift_result.has_drift:
                    summary["withDrift"] += 1
                else:
                    summary["inSync"] += 1

                workflow_results.append({
                    "id": wf_id,
                    "name": wf_name,
                    "active": runtime_wf.get("active", False),
                    "hasDrift": drift_result.has_drift,
                    "notInGit": False,
                    "lastCommitSha": last_commit_sha,
                    "lastCommitDate": last_commit_date,
                    "summary": {
                        "nodesAdded": drift_result.summary.nodes_added,
                        "nodesRemoved": drift_result.summary.nodes_removed,
                        "nodesModified": drift_result.summary.nodes_modified,
                        "connectionsChanged": drift_result.summary.connections_changed,
                        "settingsChanged": drift_result.summary.settings_changed
                    },
                    "differenceCount": len(drift_result.differences)
                })

        # Sort: drift first, then not in git, then in sync
        workflow_results.sort(key=lambda x: (
            0 if x["hasDrift"] else (1 if x["notInGit"] else 2),
            x["name"].lower()
        ))

        return {
            "gitConfigured": True,
            "workflows": workflow_results,
            "summary": summary
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check drift: {str(e)}"
        )


@router.get("/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow(
    workflow_id: str,
    environment_id: Optional[str] = None,
    environment: Optional[str] = None,  # Deprecated: use environment_id instead
    _: dict = Depends(require_entitlement("workflow_read"))
):
    """Get a specific workflow by ID"""
    try:
        env_config = await resolve_environment_config(environment_id, environment)

        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment '{environment}' not configured"
            )

        env_id = env_config.get("id")

        # Try to get workflow from database first (to get analysis)
        cached_workflow = await db_service.get_workflow(MOCK_TENANT_ID, env_id, workflow_id)

        # Create provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Fetch workflow from provider
        workflow = await adapter.get_workflow(workflow_id)
        
        # Merge analysis from database if available
        if cached_workflow and cached_workflow.get("analysis"):
            workflow["analysis"] = cached_workflow.get("analysis")
        
        return workflow

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch workflow: {str(e)}"
        )


@router.post("/upload")
async def upload_workflows(
    files: List[UploadFile] = File(...),
    environment: str = "dev",
    sync_to_github: bool = True,
    user_info: dict = Depends(require_workflow_limit())
):
    """Upload workflow files (.json or .zip) to N8N. Requires workflow_limits entitlement."""
    tenant_id = user_info["tenant"]["id"]

    try:
        env_config = await resolve_environment_config(None, environment)

        # Create provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Get GitHub service from environment configuration
        github_service = None

        if sync_to_github and env_config.get("git_repo_url"):
            repo_url = env_config.get("git_repo_url", "").rstrip('/').replace('.git', '')
            repo_parts = repo_url.split("/")
            github_service = GitHubService(
                token=env_config.get("git_pat"),
                repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
                repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
                branch=env_config.get("git_branch", "")
            )

        env_type = None
        if github_service and github_service.is_configured():
            env_type = env_config.get("n8n_type")
            if not env_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Environment type is required for GitHub workflow operations. Set the environment type and try again.",
                )

        uploaded_workflows = []
        errors = []

        for file in files:
            try:
                # Read file content
                content = await file.read()

                # Handle ZIP files
                if file.filename.endswith('.zip'):
                    with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
                        for json_file in zip_file.namelist():
                            if json_file.endswith('.json'):
                                with zip_file.open(json_file) as f:
                                    workflow_data = json.loads(f.read())
                                    result = await _upload_single_workflow(
                                        workflow_data,
                                        adapter,
                                        github_service,
                                        MOCK_TENANT_ID,
                                        env_config.get("id"),
                                        environment_type=env_type
                                    )
                                    if result["success"]:
                                        uploaded_workflows.append(result["workflow"])
                                    else:
                                        errors.append(result["error"])

                # Handle JSON files
                elif file.filename.endswith('.json'):
                    workflow_data = json.loads(content)
                    result = await _upload_single_workflow(
                        workflow_data,
                        adapter,
                        github_service,
                        MOCK_TENANT_ID,
                        env_config.get("id"),
                        environment_type=env_type
                    )
                    if result["success"]:
                        uploaded_workflows.append(result["workflow"])
                    else:
                        errors.append(result["error"])

            except Exception as e:
                errors.append(f"Error processing {file.filename}: {str(e)}")

        return {
            "success": len(uploaded_workflows) > 0,
            "uploaded": len(uploaded_workflows),
            "failed": len(errors),
            "workflows": uploaded_workflows,
            "errors": errors
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload workflows: {str(e)}"
        )


async def _upload_single_workflow(
    workflow_data: Dict[str, Any],
    adapter,  # ProviderAdapter
    github_service: GitHubService,
    tenant_id: str,
    environment_id: str = None,
    environment_type: str = None
) -> Dict[str, Any]:
    """Helper function to upload a single workflow"""
    try:
        # Create workflow in provider
        created_workflow = await adapter.create_workflow(workflow_data)

        # Create snapshot in database
        snapshot_data = {
            "tenant_id": tenant_id,
            "workflow_id": created_workflow.get("id"),
            "workflow_name": created_workflow.get("name"),
            "version": 1,  # Initial version
            "data": created_workflow,
            "trigger": "manual",
            "created_at": datetime.utcnow().isoformat()
        }
        await db_service.create_workflow_snapshot(snapshot_data)

        # Sync to GitHub if configured (using environment type key folder)
        if github_service and github_service.is_configured():
            try:
                await github_service.sync_workflow_to_github(
                    workflow_id=created_workflow.get("id"),
                    workflow_name=created_workflow.get("name"),
                    workflow_data=created_workflow,
                    environment_type=environment_type
                )
            except Exception as github_error:
                print(f"GitHub sync failed: {str(github_error)}")

        # Update workflow count if environment_id provided
        if environment_id:
            try:
                # Get current count from provider
                all_workflows = await adapter.get_workflows()
                await db_service.update_environment_workflow_count(
                    environment_id=environment_id,
                    tenant_id=tenant_id,
                    count=len(all_workflows)
                )
            except Exception as count_error:
                print(f"Failed to update workflow count: {str(count_error)}")

        return {
            "success": True,
            "workflow": created_workflow
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/{workflow_id}/activate")
async def activate_workflow(
    workflow_id: str,
    environment_id: Optional[str] = None,
    environment: Optional[str] = None,  # Deprecated: use environment_id instead
    _: dict = Depends(require_entitlement("workflow_push"))
):
    """Activate a workflow"""
    try:
        env_config = await resolve_environment_config(environment_id, environment)

        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        workflow = await adapter.activate_workflow(workflow_id)

        # Update cache with activated workflow
        try:
            await db_service.update_workflow_in_cache(
                MOCK_TENANT_ID,
                env_config.get("id"),
                workflow_id,
                workflow
            )
        except Exception as cache_error:
            print(f"Failed to update workflow cache: {str(cache_error)}")

        # Create audit log with provider context
        try:
            await create_audit_log(
                action_type="WORKFLOW_ACTIVATED",
                action=f"Activated workflow '{workflow.get('name', workflow_id)}'",
                tenant_id=MOCK_TENANT_ID,
                resource_type="workflow",
                resource_id=workflow_id,
                resource_name=workflow.get("name", workflow_id),
                provider=env_config.get("provider", "n8n"),
                old_value={"active": False},
                new_value={"active": True},
                metadata={
                    "environment_id": env_config.get("id"),
                    "environment_name": env_config.get("n8n_name") or env_config.get("name")
                }
            )
        except Exception:
            pass

        return workflow

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate workflow: {str(e)}"
        )


@router.post("/{workflow_id}/deactivate")
async def deactivate_workflow(
    workflow_id: str,
    environment_id: Optional[str] = None,
    environment: Optional[str] = None,  # Deprecated: use environment_id instead
    _: dict = Depends(require_entitlement("workflow_push"))
):
    """Deactivate a workflow"""
    try:
        env_config = await resolve_environment_config(environment_id, environment)

        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        workflow = await adapter.deactivate_workflow(workflow_id)

        # Update cache with deactivated workflow
        try:
            await db_service.update_workflow_in_cache(
                MOCK_TENANT_ID,
                env_config.get("id"),
                workflow_id,
                workflow
            )
        except Exception as cache_error:
            print(f"Failed to update workflow cache: {str(cache_error)}")

        # Create audit log with provider context
        try:
            await create_audit_log(
                action_type="WORKFLOW_DEACTIVATED",
                action=f"Deactivated workflow '{workflow.get('name', workflow_id)}'",
                tenant_id=MOCK_TENANT_ID,
                resource_type="workflow",
                resource_id=workflow_id,
                resource_name=workflow.get("name", workflow_id),
                provider=env_config.get("provider", "n8n"),
                old_value={"active": True},
                new_value={"active": False},
                metadata={
                    "environment_id": env_config.get("id"),
                    "environment_name": env_config.get("n8n_name") or env_config.get("name")
                }
            )
        except Exception:
            pass

        return workflow

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate workflow: {str(e)}"
        )


@router.put("/{workflow_id}/tags")
async def update_workflow_tags(
    workflow_id: str,
    tag_names: List[str] = Body(...),
    environment_id: Optional[str] = None,
    environment: Optional[str] = None  # Deprecated: use environment_id instead
):
    """Update workflow tags - expects body: ["tag1", "tag2"]"""
    print(f"DEBUG: update_workflow_tags called with workflow_id={workflow_id}, environment_id={environment_id}, environment={environment}, tag_names={tag_names}")
    try:
        env_config = await resolve_environment_config(environment_id, environment)

        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        all_workflows = await adapter.get_workflows()
        tag_id_map = {}

        for workflow in all_workflows:
            tags = workflow.get("tags", [])
            for tag in tags:
                if isinstance(tag, dict):
                    tag_name = tag.get("name", "")
                    tag_id = tag.get("id")
                    if tag_name and tag_id and tag_name not in tag_id_map:
                        tag_id_map[tag_name] = tag_id

        tag_ids = []
        for tag_name in tag_names:
            if tag_name in tag_id_map:
                tag_ids.append(tag_id_map[tag_name])
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tag '{tag_name}' not found. Tags must exist before assigning to workflows."
                )

        result = await adapter.update_workflow_tags(workflow_id, tag_ids)

        # Update cache with the new tags
        try:
            # Fetch the updated workflow from provider to get the complete data
            updated_workflow = await adapter.get_workflow(workflow_id)
            await db_service.update_workflow_in_cache(
                MOCK_TENANT_ID,
                env_config.get("id"),
                workflow_id,
                updated_workflow
            )
        except Exception as cache_error:
            print(f"Failed to update workflow cache after tag update: {str(cache_error)}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update workflow tags: {str(e)}"
        )


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    workflow_data: Dict[str, Any],
    environment_id: Optional[str] = None,
    environment: Optional[str] = None,  # Deprecated: use environment_id instead
    _: dict = Depends(require_entitlement("workflow_push"))
):
    """Update a workflow (name, active status, tags)"""
    try:
        env_config = await db_service.get_environment_by_type(MOCK_TENANT_ID, environment)

        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment '{environment}' not configured"
            )

        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Debug: log what we received
        import json
        print(f"DEBUG ENDPOINT: Received workflow_data keys: {list(workflow_data.keys())}")

        # Update workflow in provider - adapter will clean the data
        updated_workflow = await adapter.update_workflow(workflow_id, workflow_data)

        # Update cache with modified workflow
        try:
            await db_service.update_workflow_in_cache(
                MOCK_TENANT_ID,
                env_config.get("id"),
                workflow_id,
                updated_workflow
            )
        except Exception as cache_error:
            print(f"Failed to update workflow cache: {str(cache_error)}")

        # Transform the response to match frontend expectations
        tags_response = updated_workflow.get("tags", [])
        tag_strings = []
        if isinstance(tags_response, list):
            for tag in tags_response:
                if isinstance(tag, dict):
                    tag_strings.append(tag.get("name", ""))
                elif isinstance(tag, str):
                    tag_strings.append(tag)

        return {
            "id": updated_workflow.get("id"),
            "name": updated_workflow.get("name"),
            "description": "",
            "active": updated_workflow.get("active", False),
            "tags": tag_strings,
            "createdAt": updated_workflow.get("createdAt"),
            "updatedAt": updated_workflow.get("updatedAt"),
            "nodes": updated_workflow.get("nodes", []),
            "connections": updated_workflow.get("connections", {}),
            "settings": updated_workflow.get("settings", {})
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update workflow: {str(e)}"
        )


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    environment_id: Optional[str] = None,
    environment: Optional[str] = None,  # Deprecated: use environment_id instead
    _: dict = Depends(require_entitlement("workflow_push"))
):
    """Delete a workflow from provider"""
    try:
        env_config = await resolve_environment_config(environment_id, environment)

        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Get workflow name before deletion for audit log
        workflow_name = None
        try:
            workflow_data = await adapter.get_workflow(workflow_id)
            workflow_name = workflow_data.get("name", workflow_id)
        except Exception:
            workflow_name = workflow_id

        await adapter.delete_workflow(workflow_id)

        # Soft delete from cache
        try:
            await db_service.delete_workflow_from_cache(
                MOCK_TENANT_ID,
                env_config.get("id"),
                workflow_id
            )
        except Exception as cache_error:
            print(f"Failed to delete workflow from cache: {str(cache_error)}")

        # Update workflow count after deletion
        try:
            all_workflows = await adapter.get_workflows()
            await db_service.update_environment_workflow_count(
                environment_id=env_config.get("id"),
                tenant_id=MOCK_TENANT_ID,
                count=len(all_workflows)
            )
        except Exception as count_error:
            print(f"Failed to update workflow count: {str(count_error)}")

        # Create audit log with provider context
        try:
            await create_audit_log(
                action_type="WORKFLOW_DELETED",
                action=f"Deleted workflow '{workflow_name}'",
                tenant_id=MOCK_TENANT_ID,
                resource_type="workflow",
                resource_id=workflow_id,
                resource_name=workflow_name,
                provider=env_config.get("provider", "n8n"),  # Provider context
                metadata={
                    "environment_id": env_config.get("id"),
                    "environment_name": env_config.get("n8n_name") or env_config.get("name")
                }
            )
        except Exception:
            pass  # Don't fail if audit logging fails

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete workflow: {str(e)}"
        )


@router.get("/{workflow_id}/drift", response_model=Dict[str, Any])
async def get_workflow_drift(
    workflow_id: str,
    environment_id: Optional[str] = None,
    environment: Optional[str] = None,  # Deprecated: use environment_id instead
    _: dict = Depends(require_entitlement("workflow_dirty_check"))
):
    """
    Compare a workflow between N8N runtime and GitHub repository.

    Returns drift detection results including:
    - Whether drift exists
    - Last commit info
    - List of differences
    - Summary of changes (nodes added/removed/modified)
    """
    try:
        env_config = await resolve_environment_config(environment_id, environment)

        # Create provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Fetch workflow from provider (runtime version)
        try:
            runtime_workflow = await adapter.get_workflow(workflow_id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow not found in N8N: {str(e)}"
            )

        workflow_name = runtime_workflow.get("name", "")

        # Check if GitHub is configured for this environment
        if not env_config.get("git_repo_url") or not env_config.get("git_pat"):
            # GitHub not configured - return no drift info
            return {
                "hasDrift": False,
                "gitVersion": None,
                "runtimeVersion": runtime_workflow,
                "lastCommitSha": None,
                "lastCommitDate": None,
                "differences": [],
                "summary": {
                    "nodesAdded": 0,
                    "nodesRemoved": 0,
                    "nodesModified": 0,
                    "connectionsChanged": False,
                    "settingsChanged": False
                },
                "gitConfigured": False,
                "message": "GitHub is not configured for this environment"
            }

        # Create GitHub service from environment configuration
        repo_url = env_config.get("git_repo_url", "").rstrip('/').replace('.git', '')
        repo_parts = repo_url.split("/")
        github_service = GitHubService(
            token=env_config.get("git_pat"),
            repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
            repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
            branch=env_config.get("git_branch", "main")
        )

        # Check if GitHub is properly configured
        if not github_service.is_configured():
            return {
                "hasDrift": False,
                "gitVersion": None,
                "runtimeVersion": runtime_workflow,
                "lastCommitSha": None,
                "lastCommitDate": None,
                "differences": [],
                "summary": {
                    "nodesAdded": 0,
                    "nodesRemoved": 0,
                    "nodesModified": 0,
                    "connectionsChanged": False,
                    "settingsChanged": False
                },
                "gitConfigured": False,
                "message": "GitHub is not properly configured"
            }

        # Fetch workflow from GitHub by name (using environment type key for folder path)
        env_type = env_config.get("n8n_type")
        if not env_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment type is required for GitHub workflow operations. Set the environment type and try again.",
            )
        git_result = await github_service.get_workflow_by_name(workflow_name, environment_type=env_type)

        if git_result is None:
            # Workflow not found in GitHub
            return {
                "hasDrift": False,
                "gitVersion": None,
                "runtimeVersion": runtime_workflow,
                "lastCommitSha": None,
                "lastCommitDate": None,
                "differences": [],
                "summary": {
                    "nodesAdded": 0,
                    "nodesRemoved": 0,
                    "nodesModified": 0,
                    "connectionsChanged": False,
                    "settingsChanged": False
                },
                "gitConfigured": True,
                "notInGit": True,
                "message": f"Workflow '{workflow_name}' not found in GitHub repository"
            }

        # Compare workflows
        git_workflow = git_result.get("workflow")
        last_commit_sha = git_result.get("commit_sha")
        last_commit_date = git_result.get("commit_date")

        drift_result = compare_workflows(
            git_workflow=git_workflow,
            runtime_workflow=runtime_workflow,
            last_commit_sha=last_commit_sha,
            last_commit_date=last_commit_date
        )

        # Return the drift result
        result = drift_result.to_dict()
        result["gitConfigured"] = True
        result["notInGit"] = False
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check workflow drift: {str(e)}"
        )


