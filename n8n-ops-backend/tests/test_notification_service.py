"""
Unit tests for the notification service - channels, rules, and event emission.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from app.services.notification_service import NotificationService
from app.schemas.notification import (
    NotificationChannelCreate,
    NotificationChannelUpdate,
    NotificationRuleCreate,
    NotificationRuleUpdate,
    NotificationStatus,
    ChannelType,
    EVENT_CATALOG,
)


@pytest.fixture
def notification_service():
    """Create a NotificationService instance."""
    return NotificationService()


@pytest.fixture
def mock_db():
    """Mock database service."""
    with patch("app.services.notification_service.db_service") as mock:
        yield mock


# ============ Channel Tests ============


class TestChannelOperations:
    """Tests for notification channel operations."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_create_channel(self, notification_service, mock_db):
        """Should create a notification channel."""
        mock_db.create_notification_channel = AsyncMock(return_value={
            "id": "channel-1",
            "tenant_id": "tenant-1",
            "name": "Slack Alerts",
            "type": "slack",
            "config_json": {"webhook_url": "https://hooks.slack.com/xxx"},
            "is_enabled": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        data = NotificationChannelCreate(
            name="Slack Alerts",
            type=ChannelType.SLACK,
            config_json={"webhook_url": "https://hooks.slack.com/xxx"},
            is_enabled=True
        )

        result = await notification_service.create_channel("tenant-1", data)

        assert result.id == "channel-1"
        assert result.name == "Slack Alerts"
        assert result.type == "slack"
        mock_db.create_notification_channel.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_update_channel(self, notification_service, mock_db):
        """Should update a notification channel."""
        mock_db.update_notification_channel = AsyncMock(return_value={
            "id": "channel-1",
            "tenant_id": "tenant-1",
            "name": "Updated Slack",
            "type": "slack",
            "config_json": {"webhook_url": "https://new.webhook.url"},
            "is_enabled": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        data = NotificationChannelUpdate(
            name="Updated Slack",
            is_enabled=False
        )

        result = await notification_service.update_channel("tenant-1", "channel-1", data)

        assert result.name == "Updated Slack"
        assert result.is_enabled is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_update_channel_no_changes(self, notification_service, mock_db):
        """Should return current channel if no updates provided."""
        mock_db.get_notification_channel = AsyncMock(return_value={
            "id": "channel-1",
            "tenant_id": "tenant-1",
            "name": "Slack",
            "type": "slack",
            "config_json": {},
            "is_enabled": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        data = NotificationChannelUpdate()

        result = await notification_service.update_channel("tenant-1", "channel-1", data)

        assert result.id == "channel-1"
        mock_db.update_notification_channel.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_update_channel_not_found(self, notification_service, mock_db):
        """Should return None if channel not found."""
        mock_db.update_notification_channel = AsyncMock(return_value=None)

        data = NotificationChannelUpdate(name="New Name")

        result = await notification_service.update_channel("tenant-1", "nonexistent", data)

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_delete_channel(self, notification_service, mock_db):
        """Should delete a notification channel."""
        mock_db.delete_notification_channel = AsyncMock(return_value=True)

        result = await notification_service.delete_channel("tenant-1", "channel-1")

        assert result is True
        mock_db.delete_notification_channel.assert_called_once_with("channel-1", "tenant-1")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_channels(self, notification_service, mock_db):
        """Should get all channels for a tenant."""
        mock_db.get_notification_channels = AsyncMock(return_value=[
            {
                "id": "channel-1",
                "tenant_id": "tenant-1",
                "name": "Slack",
                "type": "slack",
                "config_json": {},
                "is_enabled": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "id": "channel-2",
                "tenant_id": "tenant-1",
                "name": "Email",
                "type": "email",
                "config_json": {},
                "is_enabled": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ])

        result = await notification_service.get_channels("tenant-1")

        assert len(result) == 2
        assert result[0].name == "Slack"
        assert result[1].name == "Email"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_channel(self, notification_service, mock_db):
        """Should get a specific channel."""
        mock_db.get_notification_channel = AsyncMock(return_value={
            "id": "channel-1",
            "tenant_id": "tenant-1",
            "name": "Slack",
            "type": "slack",
            "config_json": {"webhook_url": "https://..."},
            "is_enabled": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        result = await notification_service.get_channel("tenant-1", "channel-1")

        assert result.id == "channel-1"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_channel_not_found(self, notification_service, mock_db):
        """Should return None if channel not found."""
        mock_db.get_notification_channel = AsyncMock(return_value=None)

        result = await notification_service.get_channel("tenant-1", "nonexistent")

        assert result is None


# ============ Rule Tests ============


class TestRuleOperations:
    """Tests for notification rule operations."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_create_rule(self, notification_service, mock_db):
        """Should create a notification rule."""
        mock_db.create_notification_rule = AsyncMock(return_value={
            "id": "rule-1",
            "tenant_id": "tenant-1",
            "event_type": "promotion.success",
            "channel_ids": ["channel-1", "channel-2"],
            "is_enabled": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        data = NotificationRuleCreate(
            event_type="promotion.success",
            channel_ids=["channel-1", "channel-2"],
            is_enabled=True
        )

        result = await notification_service.create_rule("tenant-1", data)

        assert result.id == "rule-1"
        assert result.event_type == "promotion.success"
        assert len(result.channel_ids) == 2

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_update_rule(self, notification_service, mock_db):
        """Should update a notification rule."""
        mock_db.update_notification_rule = AsyncMock(return_value={
            "id": "rule-1",
            "tenant_id": "tenant-1",
            "event_type": "promotion.success",
            "channel_ids": ["channel-1"],
            "is_enabled": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        data = NotificationRuleUpdate(
            channel_ids=["channel-1"],
            is_enabled=False
        )

        result = await notification_service.update_rule("tenant-1", "rule-1", data)

        assert result.is_enabled is False
        assert len(result.channel_ids) == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_update_rule_no_changes(self, notification_service, mock_db):
        """Should return None if no updates provided."""
        data = NotificationRuleUpdate()

        result = await notification_service.update_rule("tenant-1", "rule-1", data)

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_delete_rule(self, notification_service, mock_db):
        """Should delete a notification rule."""
        mock_db.delete_notification_rule = AsyncMock(return_value=True)

        result = await notification_service.delete_rule("tenant-1", "rule-1")

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_rules(self, notification_service, mock_db):
        """Should get all rules for a tenant."""
        mock_db.get_notification_rules = AsyncMock(return_value=[
            {
                "id": "rule-1",
                "tenant_id": "tenant-1",
                "event_type": "promotion.success",
                "channel_ids": ["channel-1"],
                "is_enabled": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ])

        result = await notification_service.get_rules("tenant-1")

        assert len(result) == 1
        assert result[0].event_type == "promotion.success"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_rule_by_event(self, notification_service, mock_db):
        """Should get rule for a specific event type."""
        mock_db.get_notification_rule_by_event = AsyncMock(return_value={
            "id": "rule-1",
            "tenant_id": "tenant-1",
            "event_type": "sync.drift_detected",
            "channel_ids": ["channel-1"],
            "is_enabled": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })

        result = await notification_service.get_rule_by_event("tenant-1", "sync.drift_detected")

        assert result.event_type == "sync.drift_detected"


# ============ Event Tests ============


class TestEventEmission:
    """Tests for event emission and notification routing."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_emit_event_creates_event_record(self, notification_service, mock_db):
        """Should create an event record when emitting."""
        mock_db.create_event = AsyncMock(return_value={
            "id": "event-1",
            "tenant_id": "tenant-1",
            "event_type": "promotion.success",
            "environment_id": "env-1",
            "timestamp": datetime.utcnow(),
            "metadata_json": {"workflow_count": 5},
            "notification_status": "pending"
        })
        mock_db.get_notification_rule_by_event = AsyncMock(return_value=None)
        mock_db.update_event_notification_status = AsyncMock()

        result = await notification_service.emit_event(
            tenant_id="tenant-1",
            event_type="promotion.success",
            environment_id="env-1",
            metadata={"workflow_count": 5}
        )

        assert result.id == "event-1"
        assert result.event_type == "promotion.success"
        mock_db.create_event.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_emit_event_skipped_when_no_rule(self, notification_service, mock_db):
        """Should skip notification when no rule exists."""
        mock_db.create_event = AsyncMock(return_value={
            "id": "event-1",
            "tenant_id": "tenant-1",
            "event_type": "promotion.success",
            "timestamp": datetime.utcnow(),
        })
        mock_db.get_notification_rule_by_event = AsyncMock(return_value=None)
        mock_db.update_event_notification_status = AsyncMock()

        result = await notification_service.emit_event(
            tenant_id="tenant-1",
            event_type="promotion.success"
        )

        assert result.notification_status == NotificationStatus.SKIPPED
        assert result.channels_notified == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_emit_event_sends_to_channels(self, notification_service, mock_db):
        """Should send to configured channels when rule exists."""
        mock_db.create_event = AsyncMock(return_value={
            "id": "event-1",
            "tenant_id": "tenant-1",
            "event_type": "promotion.success",
            "timestamp": datetime.utcnow(),
        })
        mock_db.get_notification_rule_by_event = AsyncMock(return_value={
            "id": "rule-1",
            "is_enabled": True,
            "channel_ids": ["channel-1"]
        })
        mock_db.get_notification_channels = AsyncMock(return_value=[
            {
                "id": "channel-1",
                "type": "webhook",
                "config_json": {"url": "https://webhook.site/test"},
                "is_enabled": True
            }
        ])
        mock_db.update_event_notification_status = AsyncMock()

        with patch.object(notification_service, "send_notification", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await notification_service.emit_event(
                tenant_id="tenant-1",
                event_type="promotion.success"
            )

        assert result.notification_status == NotificationStatus.SENT
        assert "channel-1" in result.channels_notified
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_emit_event_handles_send_failure(self, notification_service, mock_db):
        """Should handle notification send failures."""
        mock_db.create_event = AsyncMock(return_value={
            "id": "event-1",
            "tenant_id": "tenant-1",
            "event_type": "promotion.failure",
            "timestamp": datetime.utcnow(),
        })
        mock_db.get_notification_rule_by_event = AsyncMock(return_value={
            "id": "rule-1",
            "is_enabled": True,
            "channel_ids": ["channel-1"]
        })
        mock_db.get_notification_channels = AsyncMock(return_value=[
            {
                "id": "channel-1",
                "type": "slack",
                "config_json": {"webhook_url": "https://invalid"},
                "is_enabled": True
            }
        ])
        mock_db.update_event_notification_status = AsyncMock()

        with patch.object(notification_service, "send_notification", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = False

            result = await notification_service.emit_event(
                tenant_id="tenant-1",
                event_type="promotion.failure"
            )

        assert result.notification_status == NotificationStatus.FAILED

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_recent_events(self, notification_service, mock_db):
        """Should get recent events for a tenant."""
        mock_db.get_events = AsyncMock(return_value=[
            {
                "id": "event-1",
                "tenant_id": "tenant-1",
                "event_type": "promotion.success",
                "timestamp": datetime.utcnow(),
                "notification_status": "sent",
                "channels_notified": ["channel-1"]
            },
            {
                "id": "event-2",
                "tenant_id": "tenant-1",
                "event_type": "sync.drift_detected",
                "timestamp": datetime.utcnow(),
                "notification_status": "skipped"
            }
        ])

        result = await notification_service.get_recent_events("tenant-1", limit=50)

        assert len(result) == 2
        mock_db.get_events.assert_called_once_with("tenant-1", 50, None)


# ============ Event Catalog Tests ============


class TestEventCatalog:
    """Tests for event catalog."""

    @pytest.mark.unit
    def test_get_event_catalog(self, notification_service):
        """Should return event catalog."""
        result = notification_service.get_event_catalog()

        assert len(result) > 0
        assert all(hasattr(item, "event_type") for item in result)
        assert all(hasattr(item, "display_name") for item in result)

    @pytest.mark.unit
    def test_event_catalog_has_expected_events(self, notification_service):
        """Should have expected event types."""
        result = notification_service.get_event_catalog()
        event_types = [item.event_type for item in result]

        # Check for some expected event types
        expected_events = [
            "promotion.success",
            "promotion.failure",
            "sync.drift_detected"
        ]
        for event in expected_events:
            assert event in event_types, f"Expected event {event} not found"


# ============ Send Notification Tests ============


class TestSendNotification:
    """Tests for send_notification method."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_slack_notification(self, notification_service):
        """Should send Slack notification via webhook."""
        channel = {
            "type": "slack",
            "config_json": {"webhook_url": "https://hooks.slack.com/test"},
            "name": "Slack Channel"
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await notification_service.send_notification(
                channel,
                "promotion.success",
                "env-1",
                {"message": "Promotion successful"}
            )

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_slack_missing_webhook(self, notification_service):
        """Should return False when Slack webhook URL is missing."""
        channel = {
            "type": "slack",
            "config_json": {},
            "name": "Bad Slack Channel"
        }

        result = await notification_service.send_notification(
            channel,
            "promotion.success",
            None,
            None
        )

        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_webhook_notification(self, notification_service):
        """Should send webhook notification."""
        channel = {
            "type": "webhook",
            "config_json": {"url": "https://webhook.example.com/notify"},
            "name": "Webhook Channel"
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await notification_service.send_notification(
                channel,
                "sync.drift_detected",
                "env-1",
                {"drifted_workflows": 3}
            )

        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_webhook_with_bearer_auth(self, notification_service):
        """Should include bearer token in webhook request."""
        channel = {
            "type": "webhook",
            "config_json": {
                "url": "https://api.example.com/events",
                "auth_type": "bearer",
                "auth_value": "secret-token"
            },
            "name": "Auth Webhook"
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await notification_service.send_notification(
                channel,
                "promotion.success",
                None,
                None
            )

            call_args = mock_client.post.call_args
            headers = call_args.kwargs.get("headers", {})
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer secret-token"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_webhook_with_basic_auth(self, notification_service):
        """Should include basic auth in webhook request."""
        import base64

        channel = {
            "type": "webhook",
            "config_json": {
                "url": "https://api.example.com/events",
                "auth_type": "basic",
                "auth_value": "user:pass"
            },
            "name": "Basic Auth Webhook"
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await notification_service.send_notification(
                channel,
                "promotion.success",
                None,
                None
            )

            call_args = mock_client.post.call_args
            headers = call_args.kwargs.get("headers", {})
            expected_auth = f"Basic {base64.b64encode(b'user:pass').decode()}"
            assert headers["Authorization"] == expected_auth

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_webhook_missing_url(self, notification_service):
        """Should return False when webhook URL is missing."""
        channel = {
            "type": "webhook",
            "config_json": {},
            "name": "Bad Webhook"
        }

        result = await notification_service.send_notification(
            channel,
            "promotion.success",
            None,
            None
        )

        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_unknown_channel_type(self, notification_service):
        """Should return False for unknown channel type."""
        channel = {
            "type": "unknown_type",
            "config_json": {},
            "name": "Unknown Channel"
        }

        result = await notification_service.send_notification(
            channel,
            "promotion.success",
            None,
            None
        )

        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_send_webhook_accepts_various_status_codes(self, notification_service):
        """Should accept 200, 201, 202, 204 status codes."""
        channel = {
            "type": "webhook",
            "config_json": {"url": "https://webhook.example.com"},
            "name": "Webhook"
        }

        for status_code in [200, 201, 202, 204]:
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.status_code = status_code

                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_class.return_value = mock_client

                result = await notification_service.send_notification(
                    channel,
                    "test",
                    None,
                    None
                )

                assert result is True, f"Expected True for status {status_code}"


# ============ Test Channel Tests ============


class TestTestChannel:
    """Tests for test_channel method."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_test_channel_success(self, notification_service, mock_db):
        """Should return success when test notification sent."""
        mock_db.get_notification_channel = AsyncMock(return_value={
            "id": "channel-1",
            "type": "webhook",
            "config_json": {"url": "https://webhook.example.com"},
            "name": "Test Channel"
        })

        with patch.object(notification_service, "send_notification", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await notification_service.test_channel("tenant-1", "channel-1")

        assert result["success"] is True
        assert "sent successfully" in result["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_test_channel_not_found(self, notification_service, mock_db):
        """Should return failure when channel not found."""
        mock_db.get_notification_channel = AsyncMock(return_value=None)

        result = await notification_service.test_channel("tenant-1", "nonexistent")

        assert result["success"] is False
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_test_channel_send_failure(self, notification_service, mock_db):
        """Should return failure when test notification fails."""
        mock_db.get_notification_channel = AsyncMock(return_value={
            "id": "channel-1",
            "type": "slack",
            "config_json": {"webhook_url": "https://invalid"},
            "name": "Bad Channel"
        })

        with patch.object(notification_service, "send_notification", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = False

            result = await notification_service.test_channel("tenant-1", "channel-1")

        assert result["success"] is False
        assert "Failed" in result["message"]

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_test_channel_exception(self, notification_service, mock_db):
        """Should handle exceptions during test."""
        mock_db.get_notification_channel = AsyncMock(return_value={
            "id": "channel-1",
            "type": "webhook",
            "config_json": {},
            "name": "Channel"
        })

        with patch.object(notification_service, "send_notification", new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("Network error")

            result = await notification_service.test_channel("tenant-1", "channel-1")

        assert result["success"] is False
        assert "Error" in result["message"]


# ============ Slack Notification Format Tests ============


class TestSlackNotificationFormat:
    """Tests for Slack notification formatting."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_slack_error_events_are_red(self, notification_service):
        """Should use red color for error events."""
        channel = {
            "type": "slack",
            "config_json": {"webhook_url": "https://hooks.slack.com/test"},
            "name": "Slack"
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await notification_service.send_notification(
                channel,
                "promotion.failure",  # Contains "failure"
                None,
                None
            )

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", {})
            attachment = payload.get("attachments", [{}])[0]
            assert attachment.get("color") == "#dc3545"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_slack_warning_events_are_yellow(self, notification_service):
        """Should use yellow color for warning events."""
        channel = {
            "type": "slack",
            "config_json": {"webhook_url": "https://hooks.slack.com/test"},
            "name": "Slack"
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await notification_service.send_notification(
                channel,
                "sync.drift_detected",  # Contains "drift"
                None,
                None
            )

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", {})
            attachment = payload.get("attachments", [{}])[0]
            assert attachment.get("color") == "#ffc107"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_slack_includes_environment_field(self, notification_service):
        """Should include environment in Slack fields."""
        channel = {
            "type": "slack",
            "config_json": {"webhook_url": "https://hooks.slack.com/test"},
            "name": "Slack"
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await notification_service.send_notification(
                channel,
                "promotion.success",
                "production-env-123",
                None
            )

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json", {})
            attachment = payload.get("attachments", [{}])[0]
            fields = attachment.get("fields", [])
            env_field = next((f for f in fields if f.get("title") == "Environment"), None)
            assert env_field is not None
            assert env_field["value"] == "production-env-123"
