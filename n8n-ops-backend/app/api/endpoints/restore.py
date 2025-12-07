from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime

from app.services.n8n_client import N8NClient
from app.services.database import db_service
from app.services.github_service import GitHubService

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


# Request/Response models
class RestoreOptions(BaseModel):
    include_workflows: bool = True
    include_credentials: bool = False
    include_tags: bool = False
    create_snapshots: bool = True
    selected_workflow_ids: Optional[List[str]] = None  # If None, restore all


class WorkflowPreview(BaseModel):
    workflow_id: str
    name: str
    status: str  # "new" or "update"
    nodes_count: int = 0


class RestorePreviewResponse(BaseModel):
    environment_id: str
    environment_name: str
    github_repo: str
    github_branch: str
    workflows: List[WorkflowPreview]
    total_new: int
    total_update: int
    credentials_available: bool
    tags_available: bool
    has_encryption_key: bool


class RestoreResultItem(BaseModel):
    workflow_id: str
    name: str
    action: str  # "created", "updated", "failed"
    error: Optional[str] = None
    snapshot_id: Optional[str] = None


class RestoreExecuteResponse(BaseModel):
    success: bool
    workflows_created: int
    workflows_updated: int
    workflows_failed: int
    snapshots_created: int
    results: List[RestoreResultItem]
    errors: List[str]


class RollbackRequest(BaseModel):
    snapshot_id: str


class SnapshotResponse(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str
    version: int
    trigger: str
    created_at: str


def extract_workflow_id_from_comment(workflow_data: Dict[str, Any]) -> Optional[str]:
    """Extract original workflow ID from _comment field"""
    comment = workflow_data.get("_comment", "")
    if "Workflow ID:" in comment:
        return comment.split("Workflow ID:")[-1].strip()
    return None


@router.get("/{environment_id}/preview", response_model=RestorePreviewResponse)
async def get_restore_preview(environment_id: str):
    """
    Get a preview of what will be restored from GitHub to the N8N instance.
    Shows which workflows are new vs updates.
    """
    try:
        # Get environment configuration
        env_config = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Check GitHub configuration
        git_repo_url = env_config.get("git_repo_url")
        git_branch = env_config.get("git_branch", "main")
        git_pat = env_config.get("git_pat")

        if not git_repo_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub repository not configured for this environment"
            )

        # Parse GitHub repo URL to get owner and name
        # Expected format: https://github.com/owner/repo
        try:
            parts = git_repo_url.rstrip("/").split("/")
            repo_owner = parts[-2]
            repo_name = parts[-1].replace(".git", "")
        except (IndexError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid GitHub repository URL format"
            )

        # Create GitHub service with environment-specific config
        github_service = GitHubService(
            token=git_pat,
            repo_owner=repo_owner,
            repo_name=repo_name,
            branch=git_branch
        )

        if not github_service.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub is not properly configured"
            )

        # Get workflows from GitHub
        github_workflows = await github_service.get_all_workflows_from_github()

        # Get existing workflows from N8N
        n8n_client = N8NClient(
            base_url=env_config.get("base_url"),
            api_key=env_config.get("api_key")
        )
        n8n_workflows = await n8n_client.get_workflows()

        # Create a map of existing workflow IDs
        existing_workflow_ids = {wf.get("id") for wf in n8n_workflows}

        # Build preview list
        workflow_previews = []
        total_new = 0
        total_update = 0

        for gh_workflow in github_workflows:
            # Extract original workflow ID from _comment
            original_id = extract_workflow_id_from_comment(gh_workflow)
            workflow_name = gh_workflow.get("name", "Unknown")
            nodes = gh_workflow.get("nodes", [])

            if original_id and original_id in existing_workflow_ids:
                status_str = "update"
                total_update += 1
            else:
                status_str = "new"
                total_new += 1

            workflow_previews.append(WorkflowPreview(
                workflow_id=original_id or f"new-{workflow_name}",
                name=workflow_name,
                status=status_str,
                nodes_count=len(nodes)
            ))

        # Check if encryption key is available for credentials
        has_encryption_key = bool(env_config.get("n8n_encryption_key"))

        return RestorePreviewResponse(
            environment_id=environment_id,
            environment_name=env_config.get("name", ""),
            github_repo=git_repo_url,
            github_branch=git_branch,
            workflows=workflow_previews,
            total_new=total_new,
            total_update=total_update,
            credentials_available=False,  # TODO: Check if credentials exist in GitHub
            tags_available=False,  # TODO: Check if tags can be restored
            has_encryption_key=has_encryption_key
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get restore preview: {str(e)}"
        )


@router.post("/{environment_id}/execute", response_model=RestoreExecuteResponse)
async def execute_restore(environment_id: str, options: RestoreOptions):
    """
    Execute restore from GitHub to N8N instance.
    Creates snapshots of existing workflows before updating them.
    """
    try:
        # Get environment configuration
        env_config = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Environment not found"
            )

        # Check GitHub configuration
        git_repo_url = env_config.get("git_repo_url")
        git_branch = env_config.get("git_branch", "main")
        git_pat = env_config.get("git_pat")

        if not git_repo_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub repository not configured for this environment"
            )

        # Parse GitHub repo URL
        try:
            parts = git_repo_url.rstrip("/").split("/")
            repo_owner = parts[-2]
            repo_name = parts[-1].replace(".git", "")
        except (IndexError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid GitHub repository URL format"
            )

        # Create services
        github_service = GitHubService(
            token=git_pat,
            repo_owner=repo_owner,
            repo_name=repo_name,
            branch=git_branch
        )

        n8n_client = N8NClient(
            base_url=env_config.get("base_url"),
            api_key=env_config.get("api_key")
        )

        # Get workflows from GitHub
        github_workflows = await github_service.get_all_workflows_from_github()

        # Get existing workflows from N8N
        n8n_workflows = await n8n_client.get_workflows()
        existing_workflows_map = {wf.get("id"): wf for wf in n8n_workflows}

        # Track results
        results = []
        errors = []
        workflows_created = 0
        workflows_updated = 0
        workflows_failed = 0
        snapshots_created = 0

        for gh_workflow in github_workflows:
            original_id = extract_workflow_id_from_comment(gh_workflow)
            workflow_name = gh_workflow.get("name", "Unknown")

            # If specific workflows selected, check if this one is included
            if options.selected_workflow_ids is not None:
                if original_id not in options.selected_workflow_ids:
                    continue

            # Remove _comment field before sending to N8N
            workflow_data = {k: v for k, v in gh_workflow.items() if k != "_comment"}

            try:
                if original_id and original_id in existing_workflows_map:
                    # Update existing workflow
                    existing = existing_workflows_map[original_id]
                    snapshot_id = None

                    # Create snapshot before updating
                    if options.create_snapshots:
                        try:
                            # Get current version count
                            existing_snapshots = await db_service.get_workflow_snapshots(
                                MOCK_TENANT_ID, original_id
                            )
                            next_version = len(existing_snapshots) + 1

                            snapshot_data = {
                                "tenant_id": MOCK_TENANT_ID,
                                "workflow_id": original_id,
                                "workflow_name": existing.get("name"),
                                "version": next_version,
                                "data": existing,
                                "trigger": "auto-before-restore"
                            }
                            snapshot = await db_service.create_workflow_snapshot(snapshot_data)
                            snapshot_id = snapshot.get("id")
                            snapshots_created += 1
                        except Exception as snap_err:
                            errors.append(f"Failed to create snapshot for {workflow_name}: {str(snap_err)}")

                    # Update the workflow
                    await n8n_client.update_workflow(original_id, workflow_data)
                    workflows_updated += 1

                    results.append(RestoreResultItem(
                        workflow_id=original_id,
                        name=workflow_name,
                        action="updated",
                        snapshot_id=snapshot_id
                    ))
                else:
                    # Create new workflow
                    new_workflow = await n8n_client.create_workflow(workflow_data)
                    new_id = new_workflow.get("id")
                    workflows_created += 1

                    results.append(RestoreResultItem(
                        workflow_id=new_id or "unknown",
                        name=workflow_name,
                        action="created"
                    ))

            except Exception as wf_err:
                workflows_failed += 1
                error_msg = f"Failed to restore {workflow_name}: {str(wf_err)}"
                errors.append(error_msg)

                results.append(RestoreResultItem(
                    workflow_id=original_id or f"new-{workflow_name}",
                    name=workflow_name,
                    action="failed",
                    error=str(wf_err)
                ))

        # Sync workflows to database cache
        try:
            updated_workflows = await n8n_client.get_workflows()
            await db_service.sync_workflows_from_n8n(MOCK_TENANT_ID, environment_id, updated_workflows)

            # Update workflow count
            await db_service.update_environment_workflow_count(
                environment_id, MOCK_TENANT_ID, len(updated_workflows)
            )
        except Exception as sync_err:
            errors.append(f"Failed to sync workflows to cache: {str(sync_err)}")

        return RestoreExecuteResponse(
            success=workflows_failed == 0,
            workflows_created=workflows_created,
            workflows_updated=workflows_updated,
            workflows_failed=workflows_failed,
            snapshots_created=snapshots_created,
            results=results,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute restore: {str(e)}"
        )


@router.get("/snapshots/{workflow_id}", response_model=List[SnapshotResponse])
async def get_workflow_snapshots(workflow_id: str):
    """Get all snapshots for a specific workflow"""
    try:
        snapshots = await db_service.get_workflow_snapshots(MOCK_TENANT_ID, workflow_id)

        return [
            SnapshotResponse(
                id=snap.get("id"),
                workflow_id=snap.get("workflow_id"),
                workflow_name=snap.get("workflow_name"),
                version=snap.get("version", 0),
                trigger=snap.get("trigger", "unknown"),
                created_at=snap.get("created_at", "")
            )
            for snap in snapshots
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workflow snapshots: {str(e)}"
        )


@router.post("/rollback")
async def rollback_workflow(request: RollbackRequest):
    """
    Rollback a workflow to a previous snapshot.
    Requires the snapshot ID.
    """
    try:
        # Get the snapshot
        snapshots = await db_service.get_workflow_snapshots(MOCK_TENANT_ID)
        snapshot = next(
            (s for s in snapshots if s.get("id") == request.snapshot_id),
            None
        )

        if not snapshot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Snapshot not found"
            )

        workflow_id = snapshot.get("workflow_id")
        workflow_data = snapshot.get("data")
        workflow_name = snapshot.get("workflow_name")

        if not workflow_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Snapshot does not contain workflow data"
            )

        # Get the environment for this workflow
        # We need to find which environment has this workflow
        environments = await db_service.get_environments(MOCK_TENANT_ID)

        n8n_client = None
        env_id = None

        for env in environments:
            try:
                client = N8NClient(
                    base_url=env.get("base_url"),
                    api_key=env.get("api_key")
                )
                # Try to get the workflow from this environment
                existing = await client.get_workflow(workflow_id)
                if existing:
                    n8n_client = client
                    env_id = env.get("id")
                    break
            except Exception:
                continue

        if not n8n_client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Could not find workflow in any environment"
            )

        # Create a snapshot of current state before rollback
        try:
            current_workflow = await n8n_client.get_workflow(workflow_id)
            existing_snapshots = await db_service.get_workflow_snapshots(
                MOCK_TENANT_ID, workflow_id
            )
            next_version = len(existing_snapshots) + 1

            rollback_snapshot_data = {
                "tenant_id": MOCK_TENANT_ID,
                "workflow_id": workflow_id,
                "workflow_name": current_workflow.get("name"),
                "version": next_version,
                "data": current_workflow,
                "trigger": "auto-before-rollback"
            }
            await db_service.create_workflow_snapshot(rollback_snapshot_data)
        except Exception as snap_err:
            # Log but continue with rollback
            print(f"Warning: Failed to create pre-rollback snapshot: {snap_err}")

        # Perform the rollback
        await n8n_client.update_workflow(workflow_id, workflow_data)

        # Update database cache
        if env_id:
            updated_workflows = await n8n_client.get_workflows()
            await db_service.sync_workflows_from_n8n(MOCK_TENANT_ID, env_id, updated_workflows)

        return {
            "success": True,
            "message": f"Successfully rolled back workflow '{workflow_name}' to version {snapshot.get('version')}",
            "workflow_id": workflow_id,
            "rolled_back_to_version": snapshot.get("version")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback workflow: {str(e)}"
        )
