"""
Example: Integrating Webhook Lock Service with Stripe Webhooks

This file demonstrates how to integrate the webhook lock service
with Stripe webhook handlers to prevent race conditions.

NOTE: This is an example file, not production code.
See webhook_lock_service_README.md for full documentation.
"""

from fastapi import APIRouter, HTTPException, status, Request
from app.services.webhook_lock_service import webhook_lock_service
from app.services.stripe_service import stripe_service
from app.services.database import db_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def extract_tenant_id(event) -> str:
    """
    Extract tenant_id from Stripe webhook event.

    Tries multiple sources:
    1. Event metadata
    2. Subscription metadata
    3. Customer metadata
    4. Database lookup by customer_id
    """
    # Try event metadata first
    if hasattr(event.data, 'object'):
        obj = event.data.object
        if hasattr(obj, 'metadata') and obj.metadata:
            tenant_id = obj.metadata.get('tenant_id')
            if tenant_id:
                return tenant_id

    # Try to get tenant_id from subscription in database
    if event.type.startswith('customer.subscription'):
        subscription_id = event.data.object.id
        result = db_service.client.table("subscriptions").select(
            "tenant_id"
        ).eq("stripe_subscription_id", subscription_id).maybe_single().execute()

        if result.data:
            return result.data['tenant_id']

    # Try to get tenant_id from customer in database
    if hasattr(event.data.object, 'customer'):
        customer_id = event.data.object.customer
        result = db_service.client.table("subscriptions").select(
            "tenant_id"
        ).eq("stripe_customer_id", customer_id).maybe_single().execute()

        if result.data:
            return result.data['tenant_id']

    return None


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhooks with distributed locking.

    This endpoint demonstrates proper webhook locking to prevent
    race conditions from concurrent webhook events.
    """
    try:
        # 1. Verify webhook signature
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        if not sig_header:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing stripe-signature header"
            )

        event = stripe_service.construct_webhook_event(payload, sig_header)

        # 2. Extract tenant_id from event
        tenant_id = extract_tenant_id(event)

        if not tenant_id:
            logger.warning(
                f"Webhook event {event.id} ({event.type}) has no tenant_id, "
                "processing without lock"
            )
            # If no tenant_id, process without lock (or skip)
            # For this example, we'll just log and return success
            return {"status": "success", "message": "No tenant_id, skipped"}

        # 3. Acquire webhook lock for this tenant
        async with webhook_lock_service.acquire_webhook_lock(
            tenant_id,
            lock_type="stripe_webhook",
            timeout_seconds=30
        ) as locked:

            if not locked:
                # Lock timeout - another webhook is still processing
                logger.error(
                    f"Webhook lock timeout for tenant {tenant_id}, "
                    f"event {event.id} ({event.type})"
                )
                # Return 503 to signal Stripe to retry later
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Webhook processing locked, please retry later"
                )

            # 4. Process webhook with lock held (race condition prevented)
            logger.info(
                f"Processing webhook event {event.id} ({event.type}) "
                f"for tenant {tenant_id} with lock held"
            )

            if event.type == "checkout.session.completed":
                await handle_checkout_completed(event.data.object)

            elif event.type == "customer.subscription.updated":
                await handle_subscription_updated(event.data.object)

            elif event.type == "customer.subscription.deleted":
                await handle_subscription_deleted(event.data.object)

            elif event.type == "invoice.payment_succeeded":
                await handle_payment_succeeded(event.data.object)

            elif event.type == "invoice.payment_failed":
                await handle_payment_failed(event.data.object)

            else:
                logger.info(f"Unhandled webhook event type: {event.type}")

        # Lock is automatically released after context exit
        logger.info(
            f"Completed webhook event {event.id} ({event.type}) "
            f"for tenant {tenant_id}"
        )

        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook error: {str(e)}"
        )


# Webhook event handlers (simplified examples)

async def handle_checkout_completed(session):
    """Handle successful checkout session"""
    logger.info(f"Handling checkout completed: {session.id}")
    # Implementation would go here
    # This function is now safe from race conditions
    pass


async def handle_subscription_updated(subscription):
    """Handle subscription updates"""
    logger.info(f"Handling subscription updated: {subscription.id}")
    # Implementation would go here
    # Multiple concurrent updates will be serialized by the lock
    pass


async def handle_subscription_deleted(subscription):
    """Handle subscription deletion"""
    logger.info(f"Handling subscription deleted: {subscription.id}")
    # Implementation would go here
    pass


async def handle_payment_succeeded(invoice):
    """Handle successful payment"""
    logger.info(f"Handling payment succeeded: {invoice.id}")
    # Implementation would go here
    pass


async def handle_payment_failed(invoice):
    """Handle failed payment"""
    logger.info(f"Handling payment failed: {invoice.id}")
    # Implementation would go here
    pass


# Advanced: Using different lock types for different operations

async def handle_subscription_with_fine_grained_locking(subscription):
    """
    Example of using different lock types for different operations
    within the same tenant.
    """
    tenant_id = subscription.metadata.get('tenant_id')

    # Lock for subscription metadata updates
    async with webhook_lock_service.acquire_webhook_lock(
        tenant_id,
        lock_type="subscription_metadata"
    ) as locked:
        if locked:
            # Update subscription metadata
            pass

    # Different lock for billing calculations
    async with webhook_lock_service.acquire_webhook_lock(
        tenant_id,
        lock_type="billing_calculation"
    ) as locked:
        if locked:
            # Perform billing calculations
            pass


# Advanced: Monitoring and debugging

async def check_webhook_lock_status(tenant_id: str):
    """
    Check if a webhook lock is currently held for a tenant.
    Useful for debugging and monitoring.
    """
    status = await webhook_lock_service.check_lock_status(
        tenant_id,
        lock_type="stripe_webhook"
    )

    logger.info(f"Webhook lock status for {tenant_id}: {status}")
    return status


async def emergency_release_webhook_lock(tenant_id: str):
    """
    Emergency function to force release a webhook lock.
    Use only in exceptional circumstances.
    """
    logger.warning(f"Force releasing webhook lock for tenant {tenant_id}")
    result = await webhook_lock_service.force_release_lock(
        tenant_id,
        lock_type="stripe_webhook"
    )

    if result:
        logger.info(f"Successfully released webhook lock for {tenant_id}")
    else:
        logger.error(f"Failed to release webhook lock for {tenant_id}")

    return result


# Testing helper: Simulate concurrent webhooks

async def simulate_concurrent_webhooks(tenant_id: str, event_type: str):
    """
    Test helper to simulate concurrent webhook processing.
    Demonstrates that locks prevent race conditions.
    """
    import asyncio

    async def process_webhook(webhook_id: int):
        logger.info(f"Webhook {webhook_id} attempting to acquire lock...")

        async with webhook_lock_service.acquire_webhook_lock(
            tenant_id,
            timeout_seconds=10
        ) as locked:
            if locked:
                logger.info(f"Webhook {webhook_id} acquired lock")
                # Simulate processing time
                await asyncio.sleep(2)
                logger.info(f"Webhook {webhook_id} completed processing")
                return True
            else:
                logger.warning(f"Webhook {webhook_id} timed out waiting for lock")
                return False

    # Simulate 3 concurrent webhooks
    results = await asyncio.gather(
        process_webhook(1),
        process_webhook(2),
        process_webhook(3),
        return_exceptions=True
    )

    logger.info(f"Concurrent webhook test results: {results}")
    return results


if __name__ == "__main__":
    """
    Run this file directly to see example usage output.
    """
    print(__doc__)
    print("\nWebhook Lock Service Examples")
    print("=" * 50)
    print("\n1. Basic webhook handler with locking")
    print("2. Fine-grained locking for different operations")
    print("3. Lock status monitoring")
    print("4. Emergency lock release")
    print("5. Concurrent webhook simulation")
    print("\nSee webhook_lock_service_README.md for full documentation")
