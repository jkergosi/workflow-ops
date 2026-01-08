"""Factory for generating Stripe webhook events."""
from typing import Any, Dict, Optional
from ..fixture_loader import load_fixture, deep_merge


class StripeEventFactory:
    """Factory for creating Stripe webhook event data."""
    
    @staticmethod
    def subscription_created(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate subscription.created webhook event.
        
        Args:
            overrides: Dictionary of fields to override
        
        Returns:
            Subscription created event dictionary
        """
        base = load_fixture("stripe/subscription_created.json")
        if overrides:
            return deep_merge(base, overrides)
        return base
    
    @staticmethod
    def subscription_updated_downgrade() -> Dict[str, Any]:
        """
        Generate subscription.updated webhook event for a downgrade (agency -> pro).
        
        Returns:
            Subscription updated event dictionary showing downgrade
        """
        return load_fixture("stripe/subscription_updated_downgrade.json")
    
    @staticmethod
    def subscription_updated(
        old_plan: str = "agency",
        new_plan: str = "pro",
        overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate subscription.updated webhook event with custom plans.
        
        Args:
            old_plan: Previous plan name
            new_plan: New plan name
            overrides: Additional overrides
        
        Returns:
            Subscription updated event dictionary
        """
        base = StripeEventFactory.subscription_updated_downgrade()
        
        # Update plan names
        base["data"]["object"]["items"]["data"][0]["price"]["metadata"]["plan_name"] = new_plan
        base["data"]["previous_attributes"]["items"]["data"][0]["price"]["metadata"]["plan_name"] = old_plan
        
        if overrides:
            return deep_merge(base, overrides)
        return base
    
    @staticmethod
    def subscription_deleted() -> Dict[str, Any]:
        """
        Generate subscription.deleted webhook event.
        
        Returns:
            Subscription deleted event dictionary
        """
        return load_fixture("stripe/subscription_deleted.json")
    
    @staticmethod
    def invoice_paid() -> Dict[str, Any]:
        """
        Generate invoice.paid webhook event.
        
        Returns:
            Invoice paid event dictionary
        """
        return load_fixture("stripe/invoice_paid.json")
    
    @staticmethod
    def invalid_signature_error() -> Dict[str, Any]:
        """
        Generate webhook signature verification error.
        
        Returns:
            Invalid signature error dictionary
        """
        return load_fixture("stripe/webhook_signature_invalid.json")
    
    @staticmethod
    def malformed_event() -> str:
        """
        Generate malformed webhook event for error testing.
        
        Returns:
            Invalid JSON string
        """
        return '{"id": "evt_test", "type": "customer.subscription.updated", invalid}'
    
    @staticmethod
    def unknown_plan_event() -> Dict[str, Any]:
        """
        Generate subscription event with unknown plan name.
        
        Returns:
            Subscription event with unknown plan
        """
        base = StripeEventFactory.subscription_created()
        base["data"]["object"]["items"]["data"][0]["price"]["metadata"]["plan_name"] = "unknown_plan"
        return base

