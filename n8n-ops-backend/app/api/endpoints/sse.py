"""
SSE (Server-Sent Events) endpoints for real-time deployment updates.

Provides streaming endpoints for:
- Deployments list page (counters + deployment rows)
- Deployment detail page (single deployment with progress)
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi import status as http_status
from fastapi.responses import StreamingResponse
from datetime import datetime, timedelta, UTC
from typing import Optional
import asyncio
import json
import logging

from app.services.database import db_service
from app.services.sse_pubsub_service import sse_pubsub, SSEEvent
from app.schemas.sse import (
    DeploymentsListSnapshotPayload,
    DeploymentDetailSnapshotPayload,
    build_deployment_upsert_payload,
)
from app.schemas.deployment import (
    DeploymentResponse,
    DeploymentDetailResponse,
    DeploymentStatus,
    DeploymentWorkflowResponse,
    SnapshotResponse,
)
from app.core.entitlements_gate import require_entitlement

logger = logging.getLogger(__name__)

router = APIRouter()

# TODO: Replace with actual tenant ID from authenticated user
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000000"

# SSE constants
KEEPALIVE_INTERVAL = 15  # seconds
EVENT_WAIT_TIMEOUT = 5  # seconds


def _attach_progress_fields(deployment: dict, workflows: Optional[list] = None) -> dict:
    """
    Attach progress fields derived from summary_json.
    (Same logic as in deployments.py)
    """
    summary = deployment.get("summary_json") or {}
    total = summary.get("total")
    if total is None and workflows is not None:
        total = len(workflows)
    if total is None:
        total = 0

    status = deployment.get("status")

    if status in [DeploymentStatus.SUCCESS.value, DeploymentStatus.FAILED.value]:
        created = summary.get("created", 0)
        updated = summary.get("updated", 0)
        successful = created + updated
        deployment["progress_current"] = successful
        deployment["progress_total"] = total
    elif status == DeploymentStatus.RUNNING.value:
        processed = summary.get("processed", 0)
        if processed is None:
            processed = 0
        deployment["progress_current"] = min(processed + 1, total) if total else processed
        deployment["progress_total"] = total
    else:
        deployment["progress_current"] = 0
        deployment["progress_total"] = total

    deployment["current_workflow_name"] = summary.get("current_workflow")
    return deployment


async def _build_deployments_list_snapshot(tenant_id: str) -> dict:
    """
    Build snapshot payload for deployments list page.
    Includes deployments list and counters.
    """
    # Get deployments (similar to GET /deployments)
    query = (
        db_service.client.table("deployments")
        .select("*")
        .eq("tenant_id", tenant_id)
    )

    # Try to exclude deleted
    try:
        query = query.is_("deleted_at", "null")
    except Exception:
        pass

    query = query.order("started_at", desc=True).limit(50)
    result = query.execute()
    deployments_data = result.data or []

    # Attach progress fields
    for deployment in deployments_data:
        _attach_progress_fields(deployment)

    # Calculate counters
    # This week success count
    week_ago = datetime.now(UTC) - timedelta(days=7)
    this_week_query = (
        db_service.client.table("deployments")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("status", DeploymentStatus.SUCCESS.value)
        .gte("started_at", week_ago.isoformat())
    )
    this_week_result = this_week_query.execute()
    this_week_success_count = len(this_week_result.data) if this_week_result.data else 0

    # Running count
    running_query = (
        db_service.client.table("deployments")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("status", DeploymentStatus.RUNNING.value)
    )
    running_result = running_query.execute()
    running_count = len(running_result.data) if running_result.data else 0

    return {
        "deployments": deployments_data,
        "total": len(deployments_data),
        "page": 1,
        "page_size": 50,
        "this_week_success_count": this_week_success_count,
        "running_count": running_count
    }


async def _build_deployment_detail_snapshot(tenant_id: str, deployment_id: str) -> Optional[dict]:
    """
    Build snapshot payload for deployment detail page.
    Includes single deployment with workflows and snapshots.
    """
    # Get deployment
    query = (
        db_service.client.table("deployments")
        .select("*")
        .eq("id", deployment_id)
        .eq("tenant_id", tenant_id)
    )

    try:
        query = query.is_("deleted_at", "null")
        deployment_result = query.single().execute()
    except Exception:
        query = (
            db_service.client.table("deployments")
            .select("*")
            .eq("id", deployment_id)
            .eq("tenant_id", tenant_id)
        )
        deployment_result = query.single().execute()

    if not deployment_result.data:
        return None

    deployment_data = deployment_result.data

    # Get workflows
    workflows_result = (
        db_service.client.table("deployment_workflows")
        .select("*")
        .eq("deployment_id", deployment_id)
        .execute()
    )
    workflows_raw = workflows_result.data or []

    # Attach progress fields
    _attach_progress_fields(deployment_data, workflows_raw)

    # Get pre snapshot if exists
    pre_snapshot = None
    if deployment_data.get("pre_snapshot_id"):
        pre_snapshot_result = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("id", deployment_data["pre_snapshot_id"])
            .single()
            .execute()
        )
        if pre_snapshot_result.data:
            pre_snapshot = pre_snapshot_result.data

    # Get post snapshot if exists
    post_snapshot = None
    if deployment_data.get("post_snapshot_id"):
        post_snapshot_result = (
            db_service.client.table("snapshots")
            .select("*")
            .eq("id", deployment_data["post_snapshot_id"])
            .single()
            .execute()
        )
        if post_snapshot_result.data:
            post_snapshot = post_snapshot_result.data

    return {
        "deployment": {
            **deployment_data,
            "workflows": workflows_raw,
            "pre_snapshot": pre_snapshot,
            "post_snapshot": post_snapshot
        }
    }


def _format_sse_message(event_type: str, data: dict, event_id: str) -> str:
    """Format a message for SSE protocol."""
    lines = []
    lines.append(f"event: {event_type}")
    lines.append(f"id: {event_id}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")  # Empty line to end message
    lines.append("")
    return "\n".join(lines)


def _format_keepalive() -> str:
    """Format a keepalive comment for SSE."""
    return ": keepalive\n\n"


@router.get("/deployments")
async def sse_deployments_stream(
    request: Request,
    _: dict = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    SSE stream for deployments list page.

    On connect: sends snapshot with current deployments + counters.
    After: streams incremental events (deployment.upsert, deployment.progress, counts.update).
    """
    tenant_id = MOCK_TENANT_ID

    async def event_generator():
        subscription_id = None
        try:
            # Subscribe to deployments list scope
            subscription_id = await sse_pubsub.subscribe(tenant_id, "deployments_list")
            logger.info(f"SSE client connected for deployments list: {subscription_id}")

            # Send initial snapshot
            snapshot = await _build_deployments_list_snapshot(tenant_id)
            snapshot_event = SSEEvent(
                type="snapshot",
                tenant_id=tenant_id,
                payload=snapshot
            )
            yield _format_sse_message("snapshot", snapshot, snapshot_event.event_id)

            # Stream incremental events
            last_keepalive = datetime.now(UTC)

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"SSE client disconnected: {subscription_id}")
                    break

                # Try to get next event
                try:
                    async for event in sse_pubsub.get_events(subscription_id):
                        if await request.is_disconnected():
                            break

                        # Send the event
                        yield _format_sse_message(
                            event.type,
                            event.payload,
                            event.event_id
                        )

                        # Update keepalive timer
                        last_keepalive = datetime.now(UTC)

                        # Only process one event per iteration to check disconnect
                        break

                except asyncio.TimeoutError:
                    pass

                # Send keepalive if needed
                elapsed = (datetime.now(UTC) - last_keepalive).total_seconds()
                if elapsed >= KEEPALIVE_INTERVAL:
                    yield _format_keepalive()
                    last_keepalive = datetime.now(UTC)

                # Small sleep to prevent tight loop
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled: {subscription_id}")
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
        finally:
            if subscription_id:
                await sse_pubsub.unsubscribe(subscription_id)
                logger.info(f"SSE subscription cleaned up: {subscription_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/deployments/{deployment_id}")
async def sse_deployment_detail_stream(
    deployment_id: str,
    request: Request,
    _: dict = Depends(require_entitlement("workflow_ci_cd"))
):
    """
    SSE stream for deployment detail page.

    On connect: sends snapshot with single deployment + workflows + snapshots.
    After: streams events for this specific deployment.
    """
    tenant_id = MOCK_TENANT_ID

    # Verify deployment exists
    snapshot = await _build_deployment_detail_snapshot(tenant_id, deployment_id)
    if not snapshot:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {deployment_id} not found"
        )

    async def event_generator():
        subscription_id = None
        try:
            # Subscribe to deployment detail scope
            scope = f"deployment_detail:{deployment_id}"
            subscription_id = await sse_pubsub.subscribe(tenant_id, scope)
            logger.info(f"SSE client connected for deployment detail: {subscription_id} ({deployment_id})")

            # Send initial snapshot
            snapshot_event = SSEEvent(
                type="snapshot",
                tenant_id=tenant_id,
                deployment_id=deployment_id,
                payload=snapshot
            )
            yield _format_sse_message("snapshot", snapshot, snapshot_event.event_id)

            # Stream incremental events
            last_keepalive = datetime.now(UTC)

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"SSE client disconnected: {subscription_id}")
                    break

                # Try to get next event
                try:
                    async for event in sse_pubsub.get_events(subscription_id):
                        if await request.is_disconnected():
                            break

                        # Send the event
                        yield _format_sse_message(
                            event.type,
                            event.payload,
                            event.event_id
                        )

                        # Update keepalive timer
                        last_keepalive = datetime.now(UTC)

                        # Only process one event per iteration to check disconnect
                        break

                except asyncio.TimeoutError:
                    pass

                # Send keepalive if needed
                elapsed = (datetime.now(UTC) - last_keepalive).total_seconds()
                if elapsed >= KEEPALIVE_INTERVAL:
                    yield _format_keepalive()
                    last_keepalive = datetime.now(UTC)

                # Small sleep to prevent tight loop
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled: {subscription_id}")
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
        finally:
            if subscription_id:
                await sse_pubsub.unsubscribe(subscription_id)
                logger.info(f"SSE subscription cleaned up: {subscription_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# === Helper functions for emitting events ===

async def emit_deployment_upsert(deployment: dict, tenant_id: str = MOCK_TENANT_ID):
    """
    Emit a deployment.upsert event.
    Call this when a deployment is created or its status changes.
    """
    _attach_progress_fields(deployment)
    payload = build_deployment_upsert_payload(deployment)

    event = SSEEvent(
        type="deployment.upsert",
        tenant_id=tenant_id,
        deployment_id=deployment.get("id"),
        payload=payload.model_dump()
    )
    await sse_pubsub.publish(event)


async def emit_deployment_progress(
    deployment_id: str,
    progress_current: int,
    progress_total: int,
    current_workflow_name: Optional[str] = None,
    tenant_id: str = MOCK_TENANT_ID
):
    """
    Emit a deployment.progress event.
    Call this during deployment execution after each workflow.
    """
    event = SSEEvent(
        type="deployment.progress",
        tenant_id=tenant_id,
        deployment_id=deployment_id,
        payload={
            "deployment_id": deployment_id,
            "status": "running",
            "progress_current": progress_current,
            "progress_total": progress_total,
            "current_workflow_name": current_workflow_name
        }
    )
    await sse_pubsub.publish(event)


async def emit_counts_update(tenant_id: str = MOCK_TENANT_ID):
    """
    Emit a counts.update event.
    Call this when deployment completes to update counters.
    """
    # Calculate current counts
    week_ago = datetime.now(UTC) - timedelta(days=7)

    this_week_query = (
        db_service.client.table("deployments")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("status", DeploymentStatus.SUCCESS.value)
        .gte("started_at", week_ago.isoformat())
    )
    this_week_result = this_week_query.execute()
    this_week_success_count = len(this_week_result.data) if this_week_result.data else 0

    running_query = (
        db_service.client.table("deployments")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("status", DeploymentStatus.RUNNING.value)
    )
    running_result = running_query.execute()
    running_count = len(running_result.data) if running_result.data else 0

    event = SSEEvent(
        type="counts.update",
        tenant_id=tenant_id,
        payload={
            "this_week_success_count": this_week_success_count,
            "running_count": running_count
        }
    )
    await sse_pubsub.publish(event)


# === Background Job Progress Events ===

async def emit_sync_progress(
    job_id: str,
    environment_id: str,
    status: str,
    current_step: str,
    current: int,
    total: int,
    message: Optional[str] = None,
    errors: Optional[dict] = None,
    tenant_id: str = MOCK_TENANT_ID
):
    """Emit a sync.progress event."""
    from app.schemas.sse import SyncProgressPayload
    payload = SyncProgressPayload(
        job_id=job_id,
        environment_id=environment_id,
        status=status,
        current_step=current_step,
        current=current,
        total=total,
        message=message,
        errors=errors
    )
    event = SSEEvent(
        type="sync.progress",
        tenant_id=tenant_id,
        env_id=environment_id,
        payload=payload.model_dump()
    )
    await sse_pubsub.publish(event)


async def emit_backup_progress(
    job_id: str,
    environment_id: str,
    status: str,
    current: int,
    total: int,
    current_workflow_name: Optional[str] = None,
    message: Optional[str] = None,
    errors: Optional[list] = None,
    tenant_id: str = MOCK_TENANT_ID
):
    """Emit a backup.progress event."""
    from app.schemas.sse import BackupProgressPayload
    payload = BackupProgressPayload(
        job_id=job_id,
        environment_id=environment_id,
        status=status,
        current=current,
        total=total,
        current_workflow_name=current_workflow_name,
        message=message,
        errors=errors
    )
    event = SSEEvent(
        type="backup.progress",
        tenant_id=tenant_id,
        env_id=environment_id,
        payload=payload.model_dump()
    )
    await sse_pubsub.publish(event)


async def emit_restore_progress(
    job_id: str,
    environment_id: str,
    status: str,
    current: int,
    total: int,
    current_workflow_name: Optional[str] = None,
    message: Optional[str] = None,
    errors: Optional[list] = None,
    tenant_id: str = MOCK_TENANT_ID
):
    """Emit a restore.progress event."""
    from app.schemas.sse import RestoreProgressPayload
    payload = RestoreProgressPayload(
        job_id=job_id,
        environment_id=environment_id,
        status=status,
        current=current,
        total=total,
        current_workflow_name=current_workflow_name,
        message=message,
        errors=errors
    )
    event = SSEEvent(
        type="restore.progress",
        tenant_id=tenant_id,
        env_id=environment_id,
        payload=payload.model_dump()
    )
    await sse_pubsub.publish(event)


@router.get("/stream")
async def sse_background_jobs_stream(
    request: Request,
    env_id: Optional[str] = None,
    job_id: Optional[str] = None,
    token: Optional[str] = None
):
    """
    Generic SSE stream for background jobs (sync, backup, restore).
    
    Query params:
    - env_id: Filter by environment ID
    - job_id: Filter by specific job ID
    - token: Auth token (required since EventSource can't send headers)
    """
    # Validate token manually since EventSource can't send headers
    from app.services.auth_service import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    from fastapi import HTTPException, status
    
    # Create credentials object from query param token
    if token:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    else:
        # Try to get from Authorization header as fallback
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide token as query parameter: ?token=YOUR_TOKEN"
            )
    
    # Validate user
    try:
        user_info = await get_current_user(credentials)
        # Check entitlement
        from app.services.entitlements_service import entitlements_service
        tenant = user_info.get("tenant")
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        tenant_id = tenant["id"]
        await entitlements_service.enforce_flag(tenant_id, "environment_basic")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SSE auth validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

    # tenant_id is now set from authenticated user
    async def event_generator():
        subscription_id = None
        try:
            # Determine scope based on filters
            if job_id:
                scope = f"background_jobs_job:{job_id}"
            elif env_id:
                scope = f"background_jobs_env:{env_id}"
            else:
                scope = "background_jobs_list"
            
            subscription_id = await sse_pubsub.subscribe(tenant_id, scope)
            logger.info(f"SSE client connected for background jobs: {subscription_id} (scope={scope})")

            # Stream events
            last_keepalive = datetime.now(UTC)

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"SSE client disconnected: {subscription_id}")
                    break

                # Try to get next event
                try:
                    async for event in sse_pubsub.get_events(subscription_id):
                        if await request.is_disconnected():
                            break

                        # Send the event
                        yield _format_sse_message(
                            event.type,
                            event.payload,
                            event.event_id
                        )

                        # Update keepalive timer
                        last_keepalive = datetime.now(UTC)

                        # Only process one event per iteration to check disconnect
                        break

                except asyncio.TimeoutError:
                    pass

                # Send keepalive if needed
                elapsed = (datetime.now(UTC) - last_keepalive).total_seconds()
                if elapsed >= KEEPALIVE_INTERVAL:
                    yield _format_keepalive()
                    last_keepalive = datetime.now(UTC)

                # Small sleep to prevent tight loop
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled: {subscription_id}")
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
        finally:
            if subscription_id:
                await sse_pubsub.unsubscribe(subscription_id)
                logger.info(f"SSE subscription cleaned up: {subscription_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )