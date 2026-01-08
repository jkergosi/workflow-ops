import asyncio
import pytest

from app.services.sse_pubsub_service import SSEEvent, sse_pubsub


@pytest.mark.asyncio
async def test_sse_pubsub_resubscribes_after_disconnect():
    tenant_id = "tenant-reconnect"
    scope = "background_jobs_list"

    first_subscription = await sse_pubsub.subscribe(tenant_id, scope)
    await sse_pubsub.unsubscribe(first_subscription)

    second_subscription = await sse_pubsub.subscribe(tenant_id, scope)
    received: list[SSEEvent] = []

    async def consume():
        async for event in sse_pubsub.get_events(second_subscription):
            received.append(event)
            break

    consumer = asyncio.create_task(consume())

    try:
        payload = {"status": "running"}
        await sse_pubsub.publish(SSEEvent(type="sync.progress", tenant_id=tenant_id, payload=payload))
        await asyncio.wait_for(consumer, timeout=1)
    finally:
        await sse_pubsub.unsubscribe(second_subscription)

    assert received, "Expected an SSE event after reconnect publish"
    assert received[0].payload == payload
    assert sse_pubsub.get_subscription_count() == 0

