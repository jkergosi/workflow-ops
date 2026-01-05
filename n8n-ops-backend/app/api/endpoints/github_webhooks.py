"""
GitHub Webhook endpoints for canonical workflow repo sync
"""
from fastapi import APIRouter, Request, HTTPException, status, Depends, BackgroundTasks
from typing import Dict, Any
import hmac
import hashlib
import json
import logging

from app.services.database import db_service
from app.services.canonical_repo_sync_service import CanonicalRepoSyncService
from app.services.background_job_service import (
    background_job_service,
    BackgroundJobType,
    BackgroundJobStatus
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify GitHub webhook signature.
    
    Args:
        payload: Raw request body
        signature: X-Hub-Signature-256 header value
        secret: Webhook secret
        
    Returns:
        True if signature is valid
    """
    if not signature or not secret:
        return False
    
    # GitHub sends signature as "sha256=<hash>"
    if not signature.startswith("sha256="):
        return False
    
    expected_signature = signature[7:]  # Remove "sha256=" prefix
    computed_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, computed_signature)


@router.post("/github/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle GitHub webhook events for repository sync.
    
    Supports:
    - push events (workflow files changed)
    - pull_request events (merged PRs)
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        payload = json.loads(body.decode())
        
        # Get signature from headers
        signature = request.headers.get("X-Hub-Signature-256", "")
        event_type = request.headers.get("X-GitHub-Event", "")
        
        # For MVP, we'll use a simple approach:
        # - If webhook secret is configured, verify signature
        # - Otherwise, accept webhook (for development/testing)
        webhook_secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", None)
        if webhook_secret:
            if not verify_webhook_signature(body, signature, webhook_secret):
                logger.warning("Invalid webhook signature")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature"
                )
        
        # Process webhook event
        if event_type == "push":
            await _handle_push_event(payload, background_tasks)
        elif event_type == "pull_request":
            # Only process merged PRs
            if payload.get("action") == "closed" and payload.get("pull_request", {}).get("merged"):
                await _handle_pr_merged_event(payload, background_tasks)
        else:
            logger.debug(f"Ignoring webhook event type: {event_type}")
        
        return {"status": "ok"}
        
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        logger.error(f"Error processing GitHub webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )


async def _handle_push_event(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """Handle GitHub push event"""
    try:
        repository = payload.get("repository", {})
        repo_url = repository.get("html_url", "").replace("https://github.com/", "").replace(".git", "")
        ref = payload.get("ref", "")
        commits = payload.get("commits", [])
        
        # Extract repo owner and name
        repo_parts = repo_url.split("/")
        if len(repo_parts) != 2:
            logger.warning(f"Could not parse repo URL: {repo_url}")
            return
        
        repo_owner, repo_name = repo_parts
        
        # Find all environments using this repo
        # Note: This is a simplified approach - in production, you might want to cache this
        all_environments = await db_service.client.table("environments").select("*").execute()
        
        matching_environments = []
        for env in (all_environments.data or []):
            env_repo_url = env.get("git_repo_url", "")
            if env_repo_url and (repo_url in env_repo_url or env_repo_url.endswith(f"/{repo_owner}/{repo_name}")):
                matching_environments.append(env)
        
        if not matching_environments:
            logger.debug(f"No environments found for repo {repo_url}")
            return
        
        # Check if any workflow files were changed
        workflow_files_changed = False
        for commit in commits:
            added = commit.get("added", [])
            modified = commit.get("modified", [])
            removed = commit.get("removed", [])
            
            all_changed = added + modified + removed
            for file_path in all_changed:
                if file_path.startswith("workflows/") and file_path.endswith(".json"):
                    workflow_files_changed = True
                    break
            
            if workflow_files_changed:
                break
        
        if not workflow_files_changed:
            logger.debug("No workflow files changed in this push")
            return
        
        # Trigger repo sync for each matching environment
        for env in matching_environments:
            tenant_id = env.get("tenant_id")
            environment_id = env.get("id")
            
            if not tenant_id or not environment_id:
                continue
            
            # Create background job
            job = await background_job_service.create_job(
                tenant_id=tenant_id,
                job_type=BackgroundJobType.CANONICAL_REPO_SYNC,
                resource_id=environment_id,
                resource_type="environment",
                metadata={
                    "webhook_event": "push",
                    "repo_url": repo_url,
                    "ref": ref,
                    "commit_sha": payload.get("after")
                }
            )
            
            # Enqueue background task
            background_tasks.add_task(
                _run_repo_sync_from_webhook,
                job["id"],
                tenant_id,
                environment_id,
                env,
                payload.get("after")  # commit_sha
            )
            
            logger.info(f"Enqueued repo sync for environment {environment_id} from webhook")
            
    except Exception as e:
        logger.error(f"Error handling push event: {str(e)}")


async def _handle_pr_merged_event(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """Handle GitHub pull request merged event"""
    # Similar to push event, but we sync from the merged commit
    pr = payload.get("pull_request", {})
    if pr.get("merged"):
        # Treat as push event to the base branch
        push_payload = {
            "repository": payload.get("repository", {}),
            "ref": f"refs/heads/{pr.get('base', {}).get('ref', 'main')}",
            "after": pr.get("merge_commit_sha"),
            "commits": [{
                "added": [],
                "modified": pr.get("changed_files", []),
                "removed": []
            }]
        }
        await _handle_push_event(push_payload, background_tasks)


async def _run_repo_sync_from_webhook(
    job_id: str,
    tenant_id: str,
    environment_id: str,
    environment: Dict[str, Any],
    commit_sha: str = None
):
    """Background task for repo sync from webhook"""
    try:
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.RUNNING
        )
        
        results = await CanonicalRepoSyncService.sync_repository(
            tenant_id=tenant_id,
            environment_id=environment_id,
            environment=environment,
            commit_sha=commit_sha
        )
        
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.COMPLETED,
            result=results
        )
        
        # Trigger reconciliation
        from app.services.canonical_reconciliation_service import CanonicalReconciliationService
        await CanonicalReconciliationService.reconcile_all_pairs_for_environment(
            tenant_id=tenant_id,
            changed_env_id=environment_id
        )
    except Exception as e:
        logger.error(f"Repo sync from webhook failed: {str(e)}")
        await background_job_service.update_job_status(
            job_id=job_id,
            status=BackgroundJobStatus.FAILED,
            error_message=str(e)
        )

