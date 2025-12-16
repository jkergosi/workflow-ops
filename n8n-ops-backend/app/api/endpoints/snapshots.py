from fastapi import APIRouter, HTTPException, status, Query, Depends, Body
from typing import Optional, List
from datetime import datetime
from uuid import uuid4
import logging
from pydantic import BaseModel
from app.services.database import db_service
from app.services.github_service import GitHubService
from app.services.provider_registry import ProviderRegistry
from app.services.notification_service import notification_service
from app.services.auth_service import get_current_user
from app.core.entitlements_gate import require_entitlement

logger = logging.getLogger(__name__)
from app.schemas.deployment import (
    SnapshotResponse,
    SnapshotCreate,
    SnapshotType,
)
from app.schemas.promotion import PromotionSnapshotResponse


class ManualSnapshotRequest(BaseModel):
    environment_id: str
    reason: Optional[str] = None
    notes: Optional[str] = None

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"


@router.get("/", response_model=List[SnapshotResponse])
async def get_snapshots(
    environment_id: Optional[str] = Query(None),
    type: Optional[SnapshotType] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    _: dict = Depends(require_entitlement("snapshots_enabled"))
):
    """
    Get list of snapshots with filtering and pagination.
    Environment-scoped by default.
    """
    try:
        # Build query
        query = db_service.client.table("snapshots").select("*").eq("tenant_id", MOCK_TENANT_ID)

        if environment_id:
            query = query.eq("environment_id", environment_id)
        if type:
            query = query.eq("type", type.value)
        if from_date:
            query = query.gte("created_at", from_date.isoformat())
        if to_date:
            query = query.lte("created_at", to_date.isoformat())

        # Apply pagination
        from_index = (page - 1) * page_size
        to_index = from_index + page_size
        query = query.order("created_at", desc=True).range(from_index, to_index - 1)

        result = query.execute()
        snapshots_data = result.data or []

        return [SnapshotResponse(**snapshot) for snapshot in snapshots_data]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch snapshots: {str(e)}",
        )


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(
    snapshot_id: str,
    _: dict = Depends(require_entitlement("snapshots_enabled"))
):
    """
    Get snapshot details including metadata and related deployment.
    """
    try:
        result = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("id", snapshot_id)
            .eq("tenant_id", MOCK_TENANT_ID)
            .single()
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot {snapshot_id} not found",
            )

        return SnapshotResponse(**result.data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch snapshot: {str(e)}",
        )


@router.post("/", response_model=SnapshotResponse)
async def create_manual_snapshot(
    request: ManualSnapshotRequest,
    user_info: dict = Depends(require_entitlement("snapshots_enabled"))
):
    """
    Create a manual snapshot of an environment.
    Exports all workflows to GitHub and creates a snapshot record.
    """
    try:
        environment_id = request.environment_id
        
        # Get environment config
        env_config = await db_service.get_environment(environment_id, MOCK_TENANT_ID)
        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment {environment_id} not found",
            )

        # Check GitHub config
        if not env_config.get("git_repo_url") or not env_config.get("git_pat"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub not configured for this environment. Configure Git integration first.",
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub is not properly configured",
            )

        # Create provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Get all workflows from N8N
        workflows = await adapter.get_workflows()
        if not workflows:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No workflows found in environment to backup",
            )

        # Export all workflows to GitHub
        env_type = env_config.get("n8n_type", "dev")
        commit_sha = None
        workflows_synced = 0
        reason = request.reason or "Manual backup"

        for workflow in workflows:
            try:
                workflow_id = workflow.get("id")
                full_workflow = await adapter.get_workflow(workflow_id)
                
                await github_service.sync_workflow_to_github(
                    workflow_id=workflow_id,
                    workflow_name=full_workflow.get("name"),
                    workflow_data=full_workflow,
                    commit_message=f"Manual snapshot: {reason}",
                    environment_type=env_type
                )
                workflows_synced += 1
            except Exception as e:
                logger.error(f"Failed to sync workflow {workflow.get('id')}: {str(e)}")
                continue

        if workflows_synced == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to sync any workflows to GitHub",
            )

        # Get the latest commit SHA
        try:
            commits = github_service.repo.get_commits(path=f"workflows/{env_type}", sha=github_service.branch)
            if commits:
                commit_sha = commits[0].sha
        except Exception as e:
            logger.warning(f"Could not get commit SHA: {str(e)}")

        # Create snapshot record
        snapshot_id = str(uuid4())
        user = user_info.get("user", {})
        
        snapshot_data = {
            "id": snapshot_id,
            "tenant_id": MOCK_TENANT_ID,
            "environment_id": environment_id,
            "git_commit_sha": commit_sha or "",
            "type": SnapshotType.MANUAL_BACKUP.value,
            "created_by_user_id": user.get("id"),
            "related_deployment_id": None,
            "metadata_json": {
                "reason": reason,
                "notes": request.notes,
                "workflows_count": workflows_synced,
                "environment_name": env_config.get("name"),
                "environment_type": env_type,
            },
        }

        await db_service.create_snapshot(snapshot_data)
        
        # Emit snapshot.created event
        try:
            await notification_service.emit_event(
                tenant_id=MOCK_TENANT_ID,
                event_type="snapshot.created",
                environment_id=environment_id,
                metadata={
                    "snapshot_id": snapshot_id,
                    "type": "manual_backup",
                    "reason": reason,
                    "workflows_count": workflows_synced,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to emit snapshot.created event: {str(e)}")

        # Fetch and return the created snapshot
        result = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("id", snapshot_id)
            .single()
            .execute()
        )

        return SnapshotResponse(**result.data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create manual snapshot: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create snapshot: {str(e)}",
        )


class SnapshotComparisonResponse(BaseModel):
    snapshot1: SnapshotResponse
    snapshot2: SnapshotResponse
    workflows: list
    summary: dict


@router.get("/compare")
async def compare_snapshots(
    snapshot1: str = Query(..., description="First snapshot ID (older)"),
    snapshot2: str = Query(..., description="Second snapshot ID (newer)"),
    _: dict = Depends(require_entitlement("snapshots_enabled"))
):
    """
    Compare two snapshots and return the differences.
    Shows which workflows were added, removed, or modified between snapshots.
    """
    try:
        # Get both snapshots
        snap1_result = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("id", snapshot1)
            .eq("tenant_id", MOCK_TENANT_ID)
            .single()
            .execute()
        )
        
        snap2_result = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("id", snapshot2)
            .eq("tenant_id", MOCK_TENANT_ID)
            .single()
            .execute()
        )

        if not snap1_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot {snapshot1} not found",
            )
        if not snap2_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot {snapshot2} not found",
            )

        snap1 = snap1_result.data
        snap2 = snap2_result.data

        # Verify both snapshots are from the same environment
        if snap1["environment_id"] != snap2["environment_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot compare snapshots from different environments",
            )

        # Get environment config
        env_config = await db_service.get_environment(snap1["environment_id"], MOCK_TENANT_ID)
        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment {snap1['environment_id']} not found",
            )

        # Check GitHub config
        if not env_config.get("git_repo_url") or not env_config.get("git_pat"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub not configured for this environment",
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

        env_type = env_config.get("n8n_type", "dev")

        # Get workflows at each snapshot's commit
        workflows1 = await github_service.get_all_workflows_from_github(
            environment_type=env_type,
            commit_sha=snap1.get("git_commit_sha")
        )
        workflows2 = await github_service.get_all_workflows_from_github(
            environment_type=env_type,
            commit_sha=snap2.get("git_commit_sha")
        )

        # Compare workflows
        workflow_diffs = []
        all_workflow_ids = set(workflows1.keys()) | set(workflows2.keys())
        
        added = 0
        removed = 0
        modified = 0
        unchanged = 0

        for wf_id in all_workflow_ids:
            wf1 = workflows1.get(wf_id)
            wf2 = workflows2.get(wf_id)
            
            if wf1 and not wf2:
                # Workflow was removed
                workflow_diffs.append({
                    "workflowId": wf_id,
                    "workflowName": wf1.get("name", wf_id),
                    "status": "removed",
                    "snapshot1Version": wf1,
                    "snapshot2Version": None,
                    "changes": []
                })
                removed += 1
            elif wf2 and not wf1:
                # Workflow was added
                workflow_diffs.append({
                    "workflowId": wf_id,
                    "workflowName": wf2.get("name", wf_id),
                    "status": "added",
                    "snapshot1Version": None,
                    "snapshot2Version": wf2,
                    "changes": []
                })
                added += 1
            else:
                # Compare the two versions
                changes = []
                
                # Compare basic properties
                if wf1.get("name") != wf2.get("name"):
                    changes.append(f"Name changed: '{wf1.get('name')}' → '{wf2.get('name')}'")
                
                # Compare node counts
                nodes1 = len(wf1.get("nodes", []))
                nodes2 = len(wf2.get("nodes", []))
                if nodes1 != nodes2:
                    changes.append(f"Node count changed: {nodes1} → {nodes2}")
                
                # Compare connections
                conn1 = len(wf1.get("connections", {}))
                conn2 = len(wf2.get("connections", {}))
                if conn1 != conn2:
                    changes.append(f"Connection count changed: {conn1} → {conn2}")
                
                # Compare active status
                if wf1.get("active") != wf2.get("active"):
                    changes.append(f"Active status changed: {wf1.get('active')} → {wf2.get('active')}")

                if changes:
                    workflow_diffs.append({
                        "workflowId": wf_id,
                        "workflowName": wf2.get("name", wf_id),
                        "status": "modified",
                        "snapshot1Version": None,  # Don't send full data to reduce response size
                        "snapshot2Version": None,
                        "changes": changes
                    })
                    modified += 1
                else:
                    unchanged += 1

        # Sort by status (added, removed, modified, then unchanged)
        status_order = {"added": 0, "removed": 1, "modified": 2, "unchanged": 3}
        workflow_diffs.sort(key=lambda x: status_order.get(x["status"], 4))

        return {
            "snapshot1": SnapshotResponse(**snap1),
            "snapshot2": SnapshotResponse(**snap2),
            "workflows": workflow_diffs,
            "summary": {
                "added": added,
                "removed": removed,
                "modified": modified,
                "unchanged": unchanged
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare snapshots: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare snapshots: {str(e)}",
        )


@router.post("/{snapshot_id}/restore")
async def restore_snapshot(
    snapshot_id: str,
    user_info: dict = Depends(require_entitlement("snapshots_enabled"))
):
    """
    Restore an environment to a snapshot's state.
    Pulls workflows from GitHub at the snapshot's commit SHA and pushes to N8N.
    Requires snapshots_enabled entitlement.
    """
    tenant_id = user_info["tenant"]["id"]

    try:
        # Get snapshot
        snapshot_result = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("id", snapshot_id)
            .eq("tenant_id", tenant_id)
            .single()
            .execute()
        )

        if not snapshot_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot {snapshot_id} not found",
            )

        snapshot = snapshot_result.data
        environment_id = snapshot["environment_id"]
        commit_sha = snapshot["git_commit_sha"]

        # Get environment config
        env_config = await db_service.get_environment(environment_id, tenant_id)
        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment {environment_id} not found",
            )

        # Check GitHub config
        if not env_config.get("git_repo_url") or not env_config.get("git_pat"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub not configured for this environment",
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

        # Create provider adapter
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)

        # Get all workflows from GitHub at the specific commit SHA
        workflows = await github_service.get_all_workflows_from_github(
            environment_type=env_config.get("n8n_type", "dev"),
            commit_sha=commit_sha
        )

        if not workflows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No workflows found in GitHub for commit {commit_sha}",
            )

        # Restore workflows to provider
        restored_count = 0
        errors = []

        for workflow_id, workflow_data in workflows.items():
            try:
                # Update or create workflow in provider
                await adapter.update_workflow(workflow_id, workflow_data)
                restored_count += 1
            except Exception as e:
                errors.append(f"Failed to restore workflow {workflow_id}: {str(e)}")

        # Optionally create a new snapshot after rollback
        # This would be a manual_backup type snapshot

        success = len(errors) == 0
        
        # Emit snapshot.restore_success or snapshot.restore_failure event
        try:
            event_type = "snapshot.restore_success" if success else "snapshot.restore_failure"
            await notification_service.emit_event(
                tenant_id=tenant_id,
                event_type=event_type,
                environment_id=environment_id,
                metadata={
                    "snapshot_id": snapshot_id,
                    "environment_id": environment_id,
                    "restored_count": restored_count,
                    "failed_count": len(errors),
                    "errors": errors
                }
            )
        except Exception as e:
            logger.error(f"Failed to emit snapshot.restore event: {str(e)}")

        return {
            "success": success,
            "restored": restored_count,
            "failed": len(errors),
            "errors": errors,
            "message": f"Restored {restored_count} workflows from snapshot",
        }

    except HTTPException:
        raise
    except Exception as e:
        # Emit snapshot.restore_failure event on exception
        try:
            snapshot_result = (
                db_service.client.table("snapshots")
                .select("*")
                .eq("id", snapshot_id)
                .eq("tenant_id", tenant_id)
                .single()
                .execute()
            )
            if snapshot_result.data:
                await notification_service.emit_event(
                    tenant_id=tenant_id,
                    event_type="snapshot.restore_failure",
                    environment_id=snapshot_result.data.get("environment_id"),
                    metadata={
                        "snapshot_id": snapshot_id,
                        "error_message": str(e),
                        "error_type": type(e).__name__
                    }
                )
        except Exception as event_error:
            logger.error(f"Failed to emit snapshot.restore_failure event: {str(event_error)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore snapshot: {str(e)}",
        )

