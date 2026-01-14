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
from app.services.environment_action_guard import (
    environment_action_guard,
    EnvironmentAction,
    ActionGuardError
)
from app.schemas.environment import EnvironmentClass
from app.schemas.pagination import PaginatedResponse
from app.api.endpoints.admin_audit import create_audit_log, AuditActionType

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

def get_tenant_id(user_info: dict) -> str:
    tenant = user_info.get("tenant") or {}
    tenant_id = tenant.get("id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return tenant_id


@router.get("/", response_model=PaginatedResponse[SnapshotResponse])
async def get_snapshots(
    environment_id: Optional[str] = Query(None),
    type: Optional[SnapshotType] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("snapshots_enabled"))
):
    """
    Get list of snapshots with filtering and pagination.
    Environment-scoped by default.
    """
    try:
        tenant_id = get_tenant_id(user_info)

        # Build count query
        count_query = db_service.client.table("snapshots").select("id", count="exact").eq("tenant_id", tenant_id)
        if environment_id:
            count_query = count_query.eq("environment_id", environment_id)
        if type:
            count_query = count_query.eq("type", type.value)
        if from_date:
            count_query = count_query.gte("created_at", from_date.isoformat())
        if to_date:
            count_query = count_query.lte("created_at", to_date.isoformat())
        count_result = count_query.execute()
        total = count_result.count if count_result.count is not None else 0

        # Build data query
        query = db_service.client.table("snapshots").select("*").eq("tenant_id", tenant_id)

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

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        has_more = page < total_pages

        return {
            "items": [SnapshotResponse(**snapshot) for snapshot in snapshots_data],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "hasMore": has_more,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch snapshots: {str(e)}",
        )


@router.get("/{snapshot_id}", response_model=SnapshotResponse)
async def get_snapshot(
    snapshot_id: str,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("snapshots_enabled"))
):
    """
    Get snapshot details including metadata and related deployment.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        result = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("id", snapshot_id)
            .eq("tenant_id", tenant_id)
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
        tenant_id = get_tenant_id(user_info)
        user = user_info.get("user", {})
        user_role = user.get("role", "user")
        
        # Get environment config
        env_config = await db_service.get_environment(environment_id, tenant_id)
        if not env_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environment {environment_id} not found",
            )
        
        # Check action guard for manual snapshot
        env_class_str = env_config.get("environment_class", "dev")
        try:
            env_class = EnvironmentClass(env_class_str)
        except ValueError:
            env_class = EnvironmentClass.DEV
        
        # Get org policy flags (for now, from environment metadata or defaults)
        org_policy_flags = env_config.get("policy_flags", {}) or {}
        
        try:
            environment_action_guard.assert_can_perform_action(
                env_class=env_class,
                action=EnvironmentAction.MANUAL_SNAPSHOT,
                user_role=user_role,
                org_policy_flags=org_policy_flags,
                environment_name=env_config.get("n8n_name", environment_id)
            )
        except ActionGuardError as e:
            raise e

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

        # Export all workflows to GitHub (using environment type key for folder path)
        env_type = env_config.get("n8n_type")
        if not env_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment type is required for GitHub workflow operations. Set the environment type and try again.",
            )
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

        # Get the latest commit SHA (use sanitized environment type folder)
        sanitized_folder = github_service._sanitize_foldername(env_type)
        try:
            commits = github_service.repo.get_commits(path=f"workflows/{sanitized_folder}", sha=github_service.branch)
            if commits:
                commit_sha = commits[0].sha
        except Exception as e:
            logger.warning(f"Could not get commit SHA: {str(e)}")

        # Create snapshot record
        snapshot_id = str(uuid4())
        user = user_info.get("user", {})
        
        snapshot_data = {
            "id": snapshot_id,
            "tenant_id": tenant_id,
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
                tenant_id=tenant_id,
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
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("snapshots_enabled"))
):
    """
    Compare two snapshots and return the differences.
    Shows which workflows were added, removed, or modified between snapshots.
    """
    try:
        tenant_id = get_tenant_id(user_info)
        # Get both snapshots
        snap1_result = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("id", snapshot1)
            .eq("tenant_id", tenant_id)
            .single()
            .execute()
        )
        
        snap2_result = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("id", snapshot2)
            .eq("tenant_id", tenant_id)
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
        env_config = await db_service.get_environment(snap1["environment_id"], tenant_id)
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

        env_type = env_config.get("n8n_type")
        if not env_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment type is required for GitHub workflow operations. Set the environment type and try again.",
            )

        # Get workflows at each snapshot's commit (using environment type folder path)
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


@router.get("/workflows/{workflow_id}/environments/{environment_id}/latest")
async def get_latest_snapshot_for_workflow_environment(
    workflow_id: str,
    environment_id: str,
    type: Optional[SnapshotType] = Query(None, description="Filter by snapshot type (e.g., PRE_PROMOTION)"),
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("snapshots_enabled"))
):
    """
    Get the latest snapshot for a specific environment, optionally filtered by type.

    This endpoint is typically used to fetch the latest PRE_PROMOTION snapshot
    for rollback purposes. The workflow_id parameter provides context but the
    snapshot returned is environment-scoped (contains all workflows in the environment).

    Args:
        workflow_id: Workflow ID for context/authorization
        environment_id: Environment ID to fetch snapshot for
        type: Optional snapshot type filter (e.g., PRE_PROMOTION)

    Returns:
        Snapshot details including: snapshot_id, created_at, promotion_id (in metadata)

    Raises:
        HTTPException 404: When no snapshot exists for the environment (with or without type filter).
                          This is expected when attempting rollback before any promotions have occurred.
        HTTPException 500: When an unexpected error occurs during snapshot retrieval.
    """
    try:
        tenant_id = get_tenant_id(user_info)

        # Build query for latest snapshot
        query = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("environment_id", environment_id)
        )

        # Apply type filter if provided
        if type:
            query = query.eq("type", type.value)

        # Order by created_at descending and limit to 1
        query = query.order("created_at", desc=True).limit(1)

        result = query.execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No snapshot available for rollback in environment {environment_id}" +
                       (f" with type {type.value}" if type else ""),
            )

        snapshot_data = result.data[0]
        return SnapshotResponse(**snapshot_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch latest snapshot: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch latest snapshot: {str(e)}",
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

    Raises:
        HTTPException 404: When snapshot_id does not exist or when no workflows are found
                          in GitHub at the snapshot's commit SHA. These conditions prevent
                          rollback and require investigation.
        HTTPException 403: When user lacks permission to perform rollback (via ActionGuardError).
        HTTPException 400: When environment is not properly configured (missing GitHub config,
                          missing environment type, etc.).
        HTTPException 500: When an unexpected error occurs during the restore process.
    """
    tenant_id = user_info["tenant"]["id"]
    user = user_info.get("user", {})
    user_role = user.get("role", "user")

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
        
        # Check action guard for restore/rollback
        env_class_str = env_config.get("environment_class", "dev")
        try:
            env_class = EnvironmentClass(env_class_str)
        except ValueError:
            env_class = EnvironmentClass.DEV
        
        # Get org policy flags
        org_policy_flags = env_config.get("policy_flags", {}) or {}
        
        try:
            environment_action_guard.assert_can_perform_action(
                env_class=env_class,
                action=EnvironmentAction.RESTORE_ROLLBACK,
                user_role=user_role,
                org_policy_flags=org_policy_flags,
                environment_name=env_config.get("n8n_name", environment_id)
            )
        except ActionGuardError as e:
            raise e

        # Create audit log for rollback start
        user_id = user.get("id")
        user_email = user.get("email")
        user_name = user.get("name") or user_email

        await create_audit_log(
            action_type=AuditActionType.GITHUB_RESTORE_STARTED.value,
            action=f"Snapshot rollback started for environment {env_config.get('n8n_name', environment_id)}",
            actor_id=user_id,
            actor_email=user_email,
            actor_name=user_name,
            tenant_id=tenant_id,
            resource_type="snapshot",
            resource_id=snapshot_id,
            resource_name=f"Snapshot {snapshot_id[:8]}",
            metadata={
                "snapshot_id": snapshot_id,
                "environment_id": environment_id,
                "environment_name": env_config.get("n8n_name", environment_id),
                "commit_sha": commit_sha,
                "snapshot_type": snapshot.get("type"),
                "timestamp": datetime.utcnow().isoformat()
            }
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

        env_type = env_config.get("n8n_type")
        if not env_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment type is required for GitHub workflow operations. Set the environment type and try again.",
            )

        # Get all workflows from GitHub at the specific commit SHA (using environment type folder path)
        workflows = await github_service.get_all_workflows_from_github(
            environment_type=env_type,
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

        # Create audit log for rollback completion
        if success:
            await create_audit_log(
                action_type=AuditActionType.GITHUB_RESTORE_COMPLETED.value,
                action=f"Snapshot rollback completed successfully for environment {env_config.get('n8n_name', environment_id)}",
                actor_id=user_id,
                actor_email=user_email,
                actor_name=user_name,
                tenant_id=tenant_id,
                resource_type="snapshot",
                resource_id=snapshot_id,
                resource_name=f"Snapshot {snapshot_id[:8]}",
                metadata={
                    "snapshot_id": snapshot_id,
                    "environment_id": environment_id,
                    "environment_name": env_config.get("n8n_name", environment_id),
                    "commit_sha": commit_sha,
                    "restored_count": restored_count,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        else:
            await create_audit_log(
                action_type=AuditActionType.GITHUB_RESTORE_FAILED.value,
                action=f"Snapshot rollback failed for environment {env_config.get('n8n_name', environment_id)}",
                actor_id=user_id,
                actor_email=user_email,
                actor_name=user_name,
                tenant_id=tenant_id,
                resource_type="snapshot",
                resource_id=snapshot_id,
                resource_name=f"Snapshot {snapshot_id[:8]}",
                metadata={
                    "snapshot_id": snapshot_id,
                    "environment_id": environment_id,
                    "environment_name": env_config.get("n8n_name", environment_id),
                    "commit_sha": commit_sha,
                    "restored_count": restored_count,
                    "failed_count": len(errors),
                    "errors": errors,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

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
        # Create audit log for rollback failure on exception
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
                snapshot_data = snapshot_result.data
                env_id = snapshot_data.get("environment_id")

                # Get user info from outer scope if available
                try:
                    actor_id = user.get("id") if 'user' in locals() else None
                    actor_email = user.get("email") if 'user' in locals() else None
                    actor_name = user.get("name") or actor_email if 'user' in locals() else None
                except:
                    actor_id = None
                    actor_email = None
                    actor_name = None

                await create_audit_log(
                    action_type=AuditActionType.GITHUB_RESTORE_FAILED.value,
                    action=f"Snapshot rollback failed with exception",
                    actor_id=actor_id,
                    actor_email=actor_email,
                    actor_name=actor_name,
                    tenant_id=tenant_id,
                    resource_type="snapshot",
                    resource_id=snapshot_id,
                    resource_name=f"Snapshot {snapshot_id[:8]}",
                    metadata={
                        "snapshot_id": snapshot_id,
                        "environment_id": env_id,
                        "error_message": str(e),
                        "error_type": type(e).__name__,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )

                # Emit snapshot.restore_failure event
                await notification_service.emit_event(
                    tenant_id=tenant_id,
                    event_type="snapshot.restore_failure",
                    environment_id=env_id,
                    metadata={
                        "snapshot_id": snapshot_id,
                        "error_message": str(e),
                        "error_type": type(e).__name__
                    }
                )
        except Exception as event_error:
            logger.error(f"Failed to create audit log or emit event on restore failure: {str(event_error)}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore snapshot: {str(e)}",
        )

