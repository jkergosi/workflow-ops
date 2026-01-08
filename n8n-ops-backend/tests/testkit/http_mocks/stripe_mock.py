"""HTTP mocking helpers for Stripe webhook events."""
import hashlib
import hmac
import time
from typing import Dict, Any


class StripeWebhookMock:
    """Helper class for mocking Stripe webhook events with signature verification."""
    
    def __init__(self, webhook_secret: str = "whsec_test_secret"):
        """
        Initialize Stripe webhook mock.
        
        Args:
            webhook_secret: Webhook signing secret
        """
        self.webhook_secret = webhook_secret
    
    def generate_signature(self, payload: str, timestamp: int = None) -> str:
        """
        Generate valid Stripe webhook signature.
        
        Args:
            payload: JSON payload string
            timestamp: Optional timestamp (uses current time if not provided)
        
        Returns:
            Stripe signature header value
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        signed_payload = f"{timestamp}.{payload}"
        
        signature = hmac.new(
            self.webhook_secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        return f"t={timestamp},v1={signature}"
    
    def create_webhook_headers(self, payload: str) -> Dict[str, str]:
        """
        Create headers for Stripe webhook request.
        
        Args:
            payload: JSON payload string
        
        Returns:
            Dictionary of headers including signature
        """
        return {
            "Stripe-Signature": self.generate_signature(payload),
            "Content-Type": "application/json"
        }
    
    def create_invalid_signature_headers(self) -> Dict[str, str]:
        """
        Create headers with invalid signature.
        
        Returns:
            Dictionary of headers with invalid signature
        """
        return {
            "Stripe-Signature": "t=123456789,v1=invalid_signature",
            "Content-Type": "application/json"
        }
    
    @staticmethod
    def verify_signature_would_fail(signature: str, payload: str, secret: str) -> bool:
        """
        Check if signature verification would fail.
        
        Args:
            signature: Stripe-Signature header value
            payload: JSON payload string
            secret: Webhook secret
        
        Returns:
            True if verification would fail
        """
        try:
            parts = dict(item.split("=") for item in signature.split(","))
            timestamp = int(parts["t"])
            provided_sig = parts["v1"]
            
            signed_payload = f"{timestamp}.{payload}"
            expected_sig = hmac.new(
                secret.encode("utf-8"),
                signed_payload.encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
            
            return provided_sig != expected_sig
        except (KeyError, ValueError):
            return True

