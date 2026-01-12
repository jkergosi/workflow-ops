import stripe
from typing import Dict, Any, Optional
from app.core.config import settings

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service for handling Stripe payments and subscriptions"""

    def __init__(self):
        self.api_key = settings.STRIPE_SECRET_KEY

    async def create_customer(self, email: str, name: str, tenant_id: str) -> Dict[str, Any]:
        """Create a Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"tenant_id": tenant_id}
            )
            return {
                "id": customer.id,
                "email": customer.email,
                "name": customer.name
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create Stripe customer: {str(e)}")

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        tenant_id: str,
        billing_cycle: str = "monthly",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe checkout session"""
        try:
            extra_metadata = metadata or {}
            merged_metadata: Dict[str, str] = {
                "tenant_id": str(tenant_id),
                "billing_cycle": str(billing_cycle),
                **{str(k): str(v) for k, v in extra_metadata.items()},
            }
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[{
                    "price": price_id,
                    "quantity": 1,
                }],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=merged_metadata,
                subscription_data={"metadata": merged_metadata},
            )
            return {
                "session_id": session.id,
                "id": session.id,
                "url": session.url
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create checkout session: {str(e)}")

    async def create_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> Dict[str, Any]:
        """Create a Stripe customer portal session"""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url
            )
            return {
                "url": session.url
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to create portal session: {str(e)}")

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Get subscription details"""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            items = []
            try:
                for item in (subscription.get("items", {}).get("data", []) or []):
                    price = item.get("price") or {}
                    items.append(
                        {
                            "id": item.get("id"),
                            "price": {"id": price.get("id")},
                            "quantity": item.get("quantity"),
                        }
                    )
            except Exception:
                items = []

            metadata = {}
            try:
                metadata = dict(subscription.metadata or {})
            except Exception:
                metadata = {}

            return {
                "id": subscription.id,
                "customer": subscription.customer,
                "status": subscription.status,
                "metadata": metadata,
                "items": {"data": items},
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "canceled_at": subscription.canceled_at,
                "trial_end": subscription.trial_end
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to get subscription: {str(e)}")

    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True
    ) -> Dict[str, Any]:
        """Cancel a subscription"""
        try:
            if at_period_end:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                subscription = stripe.Subscription.delete(subscription_id)

            return {
                "id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "canceled_at": subscription.canceled_at
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to cancel subscription: {str(e)}")

    async def update_subscription_item_quantity(self, subscription_item_id: str, quantity: int) -> Dict[str, Any]:
        """Update a Stripe subscription item quantity (used for agency per-client item)."""
        try:
            item = stripe.SubscriptionItem.modify(
                subscription_item_id,
                quantity=int(quantity),
            )
            return {
                "id": item.id,
                "quantity": item.quantity,
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to update subscription item quantity: {str(e)}")

    async def reactivate_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Reactivate a canceled subscription"""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False
            )
            return {
                "id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to reactivate subscription: {str(e)}")

    async def get_upcoming_invoice(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get upcoming invoice for a customer"""
        try:
            invoice = stripe.Invoice.upcoming(customer=customer_id)
            return {
                "amount_due": invoice.amount_due / 100,  # Convert cents to dollars
                "currency": invoice.currency,
                "period_start": invoice.period_start,
                "period_end": invoice.period_end,
                "next_payment_attempt": invoice.next_payment_attempt
            }
        except stripe.error.InvalidRequestError:
            # No upcoming invoice (e.g., no active subscription)
            return None
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to get upcoming invoice: {str(e)}")

    async def list_invoices(
        self,
        customer_id: str,
        limit: int = 10,
        starting_after: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List invoices for a customer with pagination support.

        Stripe automatically returns invoices ordered by creation date (newest first),
        providing deterministic date-based ordering.

        Args:
            customer_id: Stripe customer ID
            limit: Number of invoices to return (max 100)
            starting_after: Cursor for pagination (invoice ID to start after)

        Returns:
            Dictionary with 'data' (list of invoices) and 'has_more' (bool)
        """
        try:
            params = {
                "customer": customer_id,
                "limit": limit
            }
            if starting_after:
                params["starting_after"] = starting_after

            invoices = stripe.Invoice.list(**params)
            return {
                "data": [{
                    "id": invoice.id,
                    "number": getattr(invoice, "number", invoice.id),
                    "amount_paid": invoice.amount_paid / 100,
                    "amount_paid_cents": invoice.amount_paid,
                    "currency": invoice.currency,
                    "status": invoice.status,
                    "created": invoice.created,
                    "invoice_pdf": invoice.invoice_pdf,
                    "hosted_invoice_url": invoice.hosted_invoice_url
                } for invoice in invoices.data],
                "has_more": invoices.has_more
            }
        except stripe.error.StripeError as e:
            raise Exception(f"Failed to list invoices: {str(e)}")

    async def get_default_payment_method(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get default payment method for a customer"""
        try:
            customer = stripe.Customer.retrieve(customer_id)
            if not customer.invoice_settings or not customer.invoice_settings.default_payment_method:
                return None
            
            payment_method_id = customer.invoice_settings.default_payment_method
            if isinstance(payment_method_id, str):
                pm = stripe.PaymentMethod.retrieve(payment_method_id)
                if pm.type == "card" and pm.card:
                    return {
                        "brand": pm.card.brand,
                        "last4": pm.card.last4,
                        "exp_month": pm.card.exp_month,
                        "exp_year": pm.card.exp_year
                    }
            return None
        except stripe.error.StripeError:
            return None

    def construct_webhook_event(
        self,
        payload: bytes,
        sig_header: str
    ) -> stripe.Event:
        """Construct and verify webhook event"""
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except ValueError as e:
            raise Exception(f"Invalid payload: {str(e)}")
        except stripe.error.SignatureVerificationError as e:
            raise Exception(f"Invalid signature: {str(e)}")


# Global instance
stripe_service = StripeService()
