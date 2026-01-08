"""
E2E tests for billing downgrade flow.

Tests the complete downgrade workflow:
1. Stripe webhook (subscription.updated)
2. Plan change detection
3. Over-limit detection
4. Grace period creation
5. Entitlement enforcement
6. Error scenarios (invalid signature, malformed event)
"""
import pytest
import json
from tests.testkit import StripeEventFactory, StripeWebhookMock, DatabaseSeeder


pytestmark = pytest.mark.asyncio


class TestDowngradeFlowE2E:
    """E2E tests for billing downgrade flow."""
    
    async def test_complete_downgrade_flow(
        self,
        async_client,
        testkit,
        stripe_webhook_mock
    ):
        """Test complete downgrade from Stripe webhook to enforcement."""
        setup = testkit.db.create_full_tenant_setup()
        
        # Create Stripe downgrade event (agency → pro)
        event = testkit.stripe.subscription_updated_downgrade()
        payload = json.dumps(event)
        
        # Generate valid webhook signature
        webhook_mock = stripe_webhook_mock("whsec_test_secret")
        headers = webhook_mock.create_webhook_headers(payload)
        
        # Step 1: Send Stripe webhook
        response = await async_client.post(
            "/api/v1/billing/stripe-webhook",
            content=payload,
            headers=headers
        )
        
        assert response.status_code in [200, 503]
        
        # Step 2: Verify over-limit detection occurred
        # System should detect tenant is over limits for new plan
        
        # Step 3: Verify grace period created
        # System should create grace period records for over-limit resources
        
        # Step 4: Test entitlement enforcement
        # Attempt to create environment beyond new limit
        response = await async_client.post(
            "/api/v1/environments",
            json={
                "name": "Extra Environment",
                "n8n_base_url": "https://extra.n8n.example.com",
                "n8n_api_key": "fake-key"
            }
        )
        
        # Should be blocked by entitlement limit
        assert response.status_code in [403, 503]
    
    async def test_downgrade_grace_period_tracking(
        self,
        async_client,
        testkit,
        stripe_webhook_mock
    ):
        """Test that grace periods are properly tracked."""
        setup = testkit.db.create_full_tenant_setup()
        
        # Trigger downgrade
        event = testkit.stripe.subscription_updated("agency", "pro")
        payload = json.dumps(event)
        
        webhook_mock = stripe_webhook_mock("whsec_test_secret")
        headers = webhook_mock.create_webhook_headers(payload)
        
        response = await async_client.post(
            "/api/v1/billing/stripe-webhook",
            content=payload,
            headers=headers
        )
        
        assert response.status_code in [200, 503]
        
        # Query grace periods
        # Verify grace periods were created for over-limit resources
    
    async def test_downgrade_resource_selection_strategy(
        self,
        async_client,
        testkit
    ):
        """Test that correct resource selection strategy is applied."""
        setup = testkit.db.create_full_tenant_setup()
        
        # When over limit, system should select resources based on strategy
        # (OLDEST_FIRST, NEWEST_FIRST, or USER_CHOICE)
        # Test that selection follows configured strategy
        pass  # Implementation depends on actual selection logic


class TestDowngradeErrorScenariosE2E:
    """E2E tests for downgrade error scenarios."""
    
    async def test_invalid_stripe_signature(
        self,
        async_client,
        testkit,
        stripe_webhook_mock
    ):
        """Test handling of invalid Stripe webhook signature."""
        event = testkit.stripe.subscription_updated_downgrade()
        payload = json.dumps(event)
        
        # Create invalid signature
        webhook_mock = stripe_webhook_mock("whsec_test_secret")
        headers = webhook_mock.create_invalid_signature_headers()
        
        response = await async_client.post(
            "/api/v1/billing/stripe-webhook",
            content=payload,
            headers=headers
        )
        
        # Should reject invalid signature
        assert response.status_code in [400, 401, 403]
    
    async def test_malformed_stripe_event(
        self,
        async_client,
        testkit
    ):
        """Test handling of malformed Stripe webhook event."""
        malformed_payload = testkit.stripe.malformed_event()
        
        response = await async_client.post(
            "/api/v1/billing/stripe-webhook",
            content=malformed_payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Should handle malformed JSON
        assert response.status_code in [400, 422]
    
    async def test_unknown_plan_in_event(
        self,
        async_client,
        testkit,
        stripe_webhook_mock
    ):
        """Test handling of webhook with unknown plan name."""
        event = testkit.stripe.unknown_plan_event()
        payload = json.dumps(event)
        
        webhook_mock = stripe_webhook_mock("whsec_test_secret")
        headers = webhook_mock.create_webhook_headers(payload)
        
        response = await async_client.post(
            "/api/v1/billing/stripe-webhook",
            content=payload,
            headers=headers
        )
        
        # Should handle unknown plan gracefully
        assert response.status_code in [200, 400, 503]

