from typing import Optional, List, Dict, Any
from datetime import datetime
import httpx
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.services.database import db_service
from app.schemas.notification import (
    NotificationChannelCreate,
    NotificationChannelUpdate,
    NotificationChannelResponse,
    NotificationRuleCreate,
    NotificationRuleUpdate,
    NotificationRuleResponse,
    EventCreate,
    EventResponse,
    EventCatalogItem,
    EVENT_CATALOG,
    NotificationStatus,
    ChannelType,
)


class NotificationService:
    """Service for managing notification channels, rules, and event emission"""

    # Channel operations
    async def create_channel(
        self,
        tenant_id: str,
        data: NotificationChannelCreate
    ) -> NotificationChannelResponse:
        """Create a notification channel"""
        channel_data = {
            "tenant_id": tenant_id,
            "name": data.name,
            "type": data.type.value,
            "config_json": data.config_json,
            "is_enabled": data.is_enabled
        }

        result = await db_service.create_notification_channel(channel_data)

        return NotificationChannelResponse(
            id=result["id"],
            tenant_id=result["tenant_id"],
            name=result["name"],
            type=result["type"],
            config_json=result["config_json"],
            is_enabled=result["is_enabled"],
            created_at=result["created_at"],
            updated_at=result["updated_at"]
        )

    async def update_channel(
        self,
        tenant_id: str,
        channel_id: str,
        data: NotificationChannelUpdate
    ) -> Optional[NotificationChannelResponse]:
        """Update a notification channel"""
        update_data = {}
        if data.name is not None:
            update_data["name"] = data.name
        if data.config_json is not None:
            update_data["config_json"] = data.config_json
        if data.is_enabled is not None:
            update_data["is_enabled"] = data.is_enabled

        if not update_data:
            # Nothing to update
            channel = await db_service.get_notification_channel(channel_id, tenant_id)
            if not channel:
                return None
            return self._channel_to_response(channel)

        result = await db_service.update_notification_channel(channel_id, tenant_id, update_data)
        if not result:
            return None

        return self._channel_to_response(result)

    async def delete_channel(self, tenant_id: str, channel_id: str) -> bool:
        """Delete a notification channel"""
        return await db_service.delete_notification_channel(channel_id, tenant_id)

    async def get_channels(self, tenant_id: str) -> List[NotificationChannelResponse]:
        """Get all notification channels for a tenant"""
        channels = await db_service.get_notification_channels(tenant_id)
        return [self._channel_to_response(c) for c in channels]

    async def get_channel(
        self,
        tenant_id: str,
        channel_id: str
    ) -> Optional[NotificationChannelResponse]:
        """Get a specific notification channel"""
        channel = await db_service.get_notification_channel(channel_id, tenant_id)
        if not channel:
            return None
        return self._channel_to_response(channel)

    def _channel_to_response(self, channel: Dict[str, Any]) -> NotificationChannelResponse:
        """Convert database record to response model"""
        return NotificationChannelResponse(
            id=channel["id"],
            tenant_id=channel["tenant_id"],
            name=channel["name"],
            type=channel["type"],
            config_json=channel["config_json"],
            is_enabled=channel["is_enabled"],
            created_at=channel["created_at"],
            updated_at=channel["updated_at"]
        )

    # Rule operations
    async def create_rule(
        self,
        tenant_id: str,
        data: NotificationRuleCreate
    ) -> NotificationRuleResponse:
        """Create a notification rule"""
        rule_data = {
            "tenant_id": tenant_id,
            "event_type": data.event_type,
            "channel_ids": data.channel_ids,
            "is_enabled": data.is_enabled
        }

        result = await db_service.create_notification_rule(rule_data)

        return NotificationRuleResponse(
            id=result["id"],
            tenant_id=result["tenant_id"],
            event_type=result["event_type"],
            channel_ids=result["channel_ids"],
            is_enabled=result["is_enabled"],
            created_at=result["created_at"],
            updated_at=result["updated_at"]
        )

    async def update_rule(
        self,
        tenant_id: str,
        rule_id: str,
        data: NotificationRuleUpdate
    ) -> Optional[NotificationRuleResponse]:
        """Update a notification rule"""
        update_data = {}
        if data.channel_ids is not None:
            update_data["channel_ids"] = data.channel_ids
        if data.is_enabled is not None:
            update_data["is_enabled"] = data.is_enabled

        if not update_data:
            return None

        result = await db_service.update_notification_rule(rule_id, tenant_id, update_data)
        if not result:
            return None

        return self._rule_to_response(result)

    async def delete_rule(self, tenant_id: str, rule_id: str) -> bool:
        """Delete a notification rule"""
        return await db_service.delete_notification_rule(rule_id, tenant_id)

    async def get_rules(self, tenant_id: str) -> List[NotificationRuleResponse]:
        """Get all notification rules for a tenant"""
        rules = await db_service.get_notification_rules(tenant_id)
        return [self._rule_to_response(r) for r in rules]

    async def get_rule_by_event(
        self,
        tenant_id: str,
        event_type: str
    ) -> Optional[NotificationRuleResponse]:
        """Get notification rule for a specific event type"""
        rule = await db_service.get_notification_rule_by_event(tenant_id, event_type)
        if not rule:
            return None
        return self._rule_to_response(rule)

    def _rule_to_response(self, rule: Dict[str, Any]) -> NotificationRuleResponse:
        """Convert database record to response model"""
        return NotificationRuleResponse(
            id=rule["id"],
            tenant_id=rule["tenant_id"],
            event_type=rule["event_type"],
            channel_ids=rule["channel_ids"],
            is_enabled=rule["is_enabled"],
            created_at=rule["created_at"],
            updated_at=rule["updated_at"]
        )

    # Event operations
    async def emit_event(
        self,
        tenant_id: str,
        event_type: str,
        environment_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EventResponse:
        """
        Emit an event and trigger notifications based on rules.
        """
        # Create event record
        event_data = {
            "tenant_id": tenant_id,
            "event_type": event_type,
            "environment_id": environment_id,
            "metadata_json": metadata,
            "notification_status": NotificationStatus.PENDING.value
        }

        result = await db_service.create_event(event_data)
        event_id = result["id"]

        # Look up notification rule for this event type
        rule = await db_service.get_notification_rule_by_event(tenant_id, event_type)

        channels_notified = []
        notification_status = NotificationStatus.SKIPPED

        if rule and rule.get("is_enabled") and rule.get("channel_ids"):
            # Get channels and send notifications
            channels = await db_service.get_notification_channels(tenant_id)
            channel_map = {c["id"]: c for c in channels}

            all_success = True
            for channel_id in rule["channel_ids"]:
                channel = channel_map.get(channel_id)
                if channel and channel.get("is_enabled"):
                    try:
                        success = await self.send_notification(
                            channel,
                            event_type,
                            environment_id,
                            metadata
                        )
                        if success:
                            channels_notified.append(channel_id)
                        else:
                            all_success = False
                    except Exception as e:
                        print(f"Failed to send notification to channel {channel_id}: {e}")
                        all_success = False

            if channels_notified:
                notification_status = NotificationStatus.SENT if all_success else NotificationStatus.FAILED
            else:
                notification_status = NotificationStatus.FAILED

        # Update event with notification status
        await db_service.update_event_notification_status(
            event_id,
            notification_status.value,
            channels_notified
        )

        return EventResponse(
            id=result["id"],
            tenant_id=result["tenant_id"],
            event_type=result["event_type"],
            environment_id=result.get("environment_id"),
            timestamp=result["timestamp"],
            metadata_json=result.get("metadata_json"),
            notification_status=notification_status,
            channels_notified=channels_notified
        )

    async def get_recent_events(
        self,
        tenant_id: str,
        limit: int = 50,
        event_type: Optional[str] = None
    ) -> List[EventResponse]:
        """Get recent events for a tenant"""
        events = await db_service.get_events(tenant_id, limit, event_type)
        return [
            EventResponse(
                id=e["id"],
                tenant_id=e["tenant_id"],
                event_type=e["event_type"],
                environment_id=e.get("environment_id"),
                timestamp=e["timestamp"],
                metadata_json=e.get("metadata_json"),
                notification_status=e.get("notification_status"),
                channels_notified=e.get("channels_notified")
            )
            for e in events
        ]

    def get_event_catalog(self) -> List[EventCatalogItem]:
        """Get the static event catalog"""
        return EVENT_CATALOG

    async def send_notification(
        self,
        channel: Dict[str, Any],
        event_type: str,
        environment_id: Optional[str],
        metadata: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Send a notification to a channel based on its type.
        Supports: slack, email, webhook
        """
        channel_type = channel.get("type", "")
        config = channel.get("config_json", {})

        # Get display name for event
        display_name = event_type
        for item in EVENT_CATALOG:
            if item.event_type == event_type:
                display_name = item.display_name
                break

        if channel_type == ChannelType.SLACK.value or channel_type == "slack":
            return await self._send_slack_notification(
                config, event_type, display_name, environment_id, metadata, channel.get("name")
            )
        elif channel_type == ChannelType.EMAIL.value or channel_type == "email":
            return await self._send_email_notification(
                config, event_type, display_name, environment_id, metadata, channel.get("name")
            )
        elif channel_type == ChannelType.WEBHOOK.value or channel_type == "webhook":
            return await self._send_webhook_notification(
                config, event_type, display_name, environment_id, metadata, channel.get("name")
            )
        else:
            print(f"Unknown channel type: {channel_type}")
            return False

    async def _send_slack_notification(
        self,
        config: Dict[str, Any],
        event_type: str,
        display_name: str,
        environment_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
        channel_name: Optional[str]
    ) -> bool:
        """Send notification to Slack via incoming webhook"""
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            print(f"Slack channel missing webhook_url")
            return False

        # Determine color based on event type
        color = "#36a64f"  # green for success
        if "failure" in event_type or "error" in event_type or "unhealthy" in event_type:
            color = "#dc3545"  # red for errors
        elif "blocked" in event_type or "missing" in event_type or "drift" in event_type:
            color = "#ffc107"  # yellow for warnings

        # Build Slack message
        fields = []
        if environment_id:
            fields.append({"title": "Environment", "value": environment_id, "short": True})
        if metadata:
            for key, value in metadata.items():
                if key != "message":
                    fields.append({"title": key.replace("_", " ").title(), "value": str(value), "short": True})

        attachment = {
            "fallback": f"{display_name}: {metadata.get('message', event_type) if metadata else event_type}",
            "color": color,
            "title": display_name,
            "text": metadata.get("message", "") if metadata else "",
            "fields": fields,
            "footer": "N8N Ops",
            "ts": int(datetime.utcnow().timestamp())
        }

        payload = {
            "attachments": [attachment]
        }

        # Add optional overrides
        if config.get("channel"):
            payload["channel"] = config["channel"]
        if config.get("username"):
            payload["username"] = config["username"]
        if config.get("icon_emoji"):
            payload["icon_emoji"] = config["icon_emoji"]

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception as e:
            print(f"Failed to send Slack notification: {e}")
            return False

    async def _send_email_notification(
        self,
        config: Dict[str, Any],
        event_type: str,
        display_name: str,
        environment_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
        channel_name: Optional[str]
    ) -> bool:
        """Send notification via email (SMTP)"""
        smtp_host = config.get("smtp_host")
        smtp_port = config.get("smtp_port", 587)
        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        from_address = config.get("from_address")
        to_addresses = config.get("to_addresses", [])
        use_tls = config.get("use_tls", True)

        if not all([smtp_host, smtp_user, smtp_password, from_address, to_addresses]):
            print(f"Email channel missing required configuration")
            return False

        # Build email content
        subject = f"[N8N Ops] {display_name}"

        # HTML body
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2 style="color: #333;">{display_name}</h2>
            <p><strong>Event Type:</strong> {event_type}</p>
        """

        if environment_id:
            body_html += f"<p><strong>Environment:</strong> {environment_id}</p>"

        if metadata:
            if metadata.get("message"):
                body_html += f"<p><strong>Message:</strong> {metadata['message']}</p>"

            other_metadata = {k: v for k, v in metadata.items() if k != "message"}
            if other_metadata:
                body_html += "<h3>Details:</h3><ul>"
                for key, value in other_metadata.items():
                    body_html += f"<li><strong>{key.replace('_', ' ').title()}:</strong> {value}</li>"
                body_html += "</ul>"

        body_html += f"""
            <hr style="border: 1px solid #eee;">
            <p style="color: #666; font-size: 12px;">
                Sent by N8N Ops at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
            </p>
        </body>
        </html>
        """

        # Plain text body
        body_text = f"{display_name}\n\nEvent Type: {event_type}\n"
        if environment_id:
            body_text += f"Environment: {environment_id}\n"
        if metadata:
            if metadata.get("message"):
                body_text += f"Message: {metadata['message']}\n"
            for key, value in metadata.items():
                if key != "message":
                    body_text += f"{key.replace('_', ' ').title()}: {value}\n"
        body_text += f"\nSent by N8N Ops at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_address
            msg["To"] = ", ".join(to_addresses)

            msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            if use_tls:
                server = smtplib.SMTP(smtp_host, smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(smtp_host, smtp_port)

            server.login(smtp_user, smtp_password)
            server.sendmail(from_address, to_addresses, msg.as_string())
            server.quit()
            return True
        except Exception as e:
            print(f"Failed to send email notification: {e}")
            return False

    async def _send_webhook_notification(
        self,
        config: Dict[str, Any],
        event_type: str,
        display_name: str,
        environment_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
        channel_name: Optional[str]
    ) -> bool:
        """Send notification to a generic webhook"""
        url = config.get("url")
        if not url:
            print(f"Webhook channel missing url")
            return False

        method = config.get("method", "POST").upper()
        headers = config.get("headers", {}) or {}
        auth_type = config.get("auth_type")
        auth_value = config.get("auth_value")

        # Build payload
        payload = {
            "event_type": event_type,
            "display_name": display_name,
            "environment_id": environment_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "source": "n8n-ops"
        }

        # Set content-type if not provided
        if "Content-Type" not in headers and "content-type" not in headers:
            headers["Content-Type"] = "application/json"

        # Handle authentication
        if auth_type == "basic" and auth_value:
            # auth_value should be "username:password"
            encoded = base64.b64encode(auth_value.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        elif auth_type == "bearer" and auth_value:
            headers["Authorization"] = f"Bearer {auth_value}"

        try:
            async with httpx.AsyncClient() as client:
                if method == "POST":
                    response = await client.post(url, json=payload, headers=headers, timeout=10.0)
                elif method == "PUT":
                    response = await client.put(url, json=payload, headers=headers, timeout=10.0)
                elif method == "PATCH":
                    response = await client.patch(url, json=payload, headers=headers, timeout=10.0)
                else:
                    print(f"Unsupported HTTP method: {method}")
                    return False

                return response.status_code in [200, 201, 202, 204]
        except Exception as e:
            print(f"Failed to send webhook notification to {url}: {e}")
            return False

    async def test_channel(
        self,
        tenant_id: str,
        channel_id: str
    ) -> Dict[str, Any]:
        """Test a notification channel by sending a test event"""
        channel = await db_service.get_notification_channel(channel_id, tenant_id)
        if not channel:
            return {"success": False, "message": "Channel not found"}

        try:
            success = await self.send_notification(
                channel,
                "system.test",
                None,
                {"message": "This is a test notification from n8n-ops"}
            )

            if success:
                return {"success": True, "message": "Test notification sent successfully"}
            else:
                return {"success": False, "message": "Failed to send test notification"}
        except Exception as e:
            return {"success": False, "message": f"Error: {str(e)}"}


# Global instance
notification_service = NotificationService()
