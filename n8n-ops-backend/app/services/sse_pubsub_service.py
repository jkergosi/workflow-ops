"""
SSE Pub/Sub Service for real-time deployment updates.

Provides an in-memory asyncio-based pub/sub mechanism for SSE event streaming.
Supports tenant isolation and scope-based filtering.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, AsyncGenerator
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)


@dataclass
class SSEEvent:
    """SSE event envelope with routing metadata."""
    type: str  # Event type: snapshot, deployment.upsert, deployment.progress, counts.update
    tenant_id: str
    payload: dict
    event_id: str = field(default_factory=lambda: str(uuid4()))
    env_id: Optional[str] = None
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Optional: target specific deployment (for filtering)
    deployment_id: Optional[str] = None


@dataclass
class Subscription:
    """A client subscription to SSE events."""
    id: str
    tenant_id: str
    scope: str  # "deployments_list" or "deployment_detail:{deployment_id}"
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def deployment_id(self) -> Optional[str]:
        """Extract deployment_id from scope if this is a detail subscription."""
        if self.scope.startswith("deployment_detail:"):
            return self.scope.split(":", 1)[1]
        return None

    @property
    def environment_id(self) -> Optional[str]:
        """Extract environment_id from scope if this is an environment subscription."""
        if self.scope.startswith("background_jobs_env:"):
            return self.scope.split(":", 1)[1]
        return None

    @property
    def job_id(self) -> Optional[str]:
        """Extract job_id from scope if this is a job subscription."""
        if self.scope.startswith("background_jobs_job:"):
            return self.scope.split(":", 1)[1]
        return None


class SSEPubSubService:
    """
    In-memory pub/sub service for SSE event distribution.

    Supports:
    - Tenant isolation (events only reach subscriptions for same tenant)
    - Scope-based filtering (list vs detail subscriptions)
    - Backpressure handling (oldest events dropped when queue full)
    """

    def __init__(self):
        self._subscriptions: dict[str, Subscription] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, tenant_id: str, scope: str) -> str:
        """
        Create a new subscription for SSE events.

        Args:
            tenant_id: Tenant ID for isolation
            scope: Either "deployments_list" or "deployment_detail:{deployment_id}"

        Returns:
            subscription_id: Unique ID for this subscription
        """
        subscription_id = str(uuid4())
        subscription = Subscription(
            id=subscription_id,
            tenant_id=tenant_id,
            scope=scope
        )

        async with self._lock:
            self._subscriptions[subscription_id] = subscription

        logger.info(f"SSE subscription created: {subscription_id} (tenant={tenant_id}, scope={scope})")
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription."""
        async with self._lock:
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]
                logger.info(f"SSE subscription removed: {subscription_id}")

    async def publish(self, event: SSEEvent) -> None:
        """
        Publish an event to all matching subscriptions.

        Events are routed based on:
        - tenant_id must match
        - For deployment_detail scopes, deployment_id must match (if present in event)
        - deployments_list scope receives all deployment events for the tenant
        """
        async with self._lock:
            subscriptions = list(self._subscriptions.values())

        for sub in subscriptions:
            # Tenant isolation
            if sub.tenant_id != event.tenant_id:
                continue

            # Scope-based filtering
            if sub.scope == "deployments_list":
                # List scope receives all deployment events
                should_send = event.type.startswith("deployment.") or event.type == "counts.update"
            elif sub.scope.startswith("deployment_detail:"):
                # Detail scope only receives events for that specific deployment
                sub_deployment_id = sub.deployment_id
                if event.deployment_id and sub_deployment_id:
                    should_send = (event.deployment_id == sub_deployment_id)
                else:
                    # If event doesn't have deployment_id, send to all detail scopes
                    # (for counts.update events, etc.)
                    should_send = event.type.startswith("deployment.") or event.type == "counts.update"
            elif sub.scope == "background_jobs_list":
                # List scope receives all background job events
                should_send = event.type in ["sync.progress", "backup.progress", "restore.progress"]
            elif sub.scope.startswith("background_jobs_env:"):
                # Environment scope receives events for that specific environment
                sub_env_id = sub.environment_id
                if event.env_id and sub_env_id:
                    should_send = (event.env_id == sub_env_id) and event.type in ["sync.progress", "backup.progress", "restore.progress"]
                else:
                    should_send = False
            elif sub.scope.startswith("background_jobs_job:"):
                # Job scope receives events for that specific job
                sub_job_id = sub.job_id
                # Extract job_id from payload if available
                event_job_id = event.payload.get("job_id") if isinstance(event.payload, dict) else None
                if event_job_id and sub_job_id:
                    should_send = (event_job_id == sub_job_id) and event.type in ["sync.progress", "backup.progress", "restore.progress"]
                else:
                    should_send = False
            else:
                should_send = False

            if should_send:
                try:
                    # Non-blocking put with backpressure handling
                    if sub.queue.full():
                        # Drop oldest event to make room
                        try:
                            sub.queue.get_nowait()
                            logger.warning(f"SSE queue full for {sub.id}, dropped oldest event")
                        except asyncio.QueueEmpty:
                            pass

                    sub.queue.put_nowait(event)
                except Exception as e:
                    logger.error(f"Failed to queue event for subscription {sub.id}: {e}")

    async def get_events(self, subscription_id: str) -> AsyncGenerator[SSEEvent, None]:
        """
        Async generator that yields events for a subscription.

        Yields events as they become available, with a timeout for keepalive.
        """
        async with self._lock:
            subscription = self._subscriptions.get(subscription_id)

        if not subscription:
            return

        while True:
            try:
                # Wait for event with timeout (for keepalive checks)
                event = await asyncio.wait_for(
                    subscription.queue.get(),
                    timeout=5.0  # 5 second timeout for keepalive opportunities
                )
                yield event
            except asyncio.TimeoutError:
                # No event received, but subscription still active
                # Caller can use this opportunity to send keepalive
                continue
            except asyncio.CancelledError:
                break

    def get_subscription_count(self) -> int:
        """Get number of active subscriptions."""
        return len(self._subscriptions)

    def get_subscriptions_for_tenant(self, tenant_id: str) -> list[str]:
        """Get subscription IDs for a tenant (for debugging)."""
        return [
            sub.id for sub in self._subscriptions.values()
            if sub.tenant_id == tenant_id
        ]


# Singleton instance
sse_pubsub = SSEPubSubService()
