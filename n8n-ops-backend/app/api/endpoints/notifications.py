from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, List

from app.schemas.notification import (
    NotificationChannelCreate,
    NotificationChannelUpdate,
    NotificationChannelResponse,
    NotificationRuleCreate,
    NotificationRuleUpdate,
    NotificationRuleResponse,
    EventResponse,
    EventCatalogItem,
)
from app.services.notification_service import notification_service
from app.core.entitlements_gate import require_entitlement

router = APIRouter()


# Entitlement gates for notification/alerting features

# Mock tenant ID for development (same as other endpoints)
MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001"


# Channel endpoints
@router.get("/channels", response_model=List[NotificationChannelResponse])
async def get_notification_channels(
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """Get all notification channels for the tenant."""
    try:
        channels = await notification_service.get_channels(MOCK_TENANT_ID)
        return channels
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification channels: {str(e)}"
        )


@router.post("/channels", response_model=NotificationChannelResponse)
async def create_notification_channel(
    data: NotificationChannelCreate,
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """Create a new notification channel."""
    try:
        channel = await notification_service.create_channel(MOCK_TENANT_ID, data)
        return channel
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notification channel: {str(e)}"
        )


@router.get("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def get_notification_channel(
    channel_id: str,
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """Get a specific notification channel."""
    channel = await notification_service.get_channel(MOCK_TENANT_ID, channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification channel not found"
        )
    return channel


@router.put("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def update_notification_channel(
    channel_id: str,
    data: NotificationChannelUpdate,
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """Update a notification channel."""
    channel = await notification_service.update_channel(MOCK_TENANT_ID, channel_id, data)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification channel not found"
        )
    return channel


@router.delete("/channels/{channel_id}")
async def delete_notification_channel(
    channel_id: str,
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """Delete a notification channel."""
    await notification_service.delete_channel(MOCK_TENANT_ID, channel_id)
    return {"message": "Notification channel deleted"}


@router.post("/channels/{channel_id}/test")
async def test_notification_channel(
    channel_id: str,
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """
    Test a notification channel by sending a test event.
    Returns success/failure status and message.
    """
    result = await notification_service.test_channel(MOCK_TENANT_ID, channel_id)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    return result


# Rule endpoints
@router.get("/rules", response_model=List[NotificationRuleResponse])
async def get_notification_rules(
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """Get all notification rules for the tenant."""
    try:
        rules = await notification_service.get_rules(MOCK_TENANT_ID)
        return rules
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification rules: {str(e)}"
        )


@router.post("/rules", response_model=NotificationRuleResponse)
async def create_notification_rule(
    data: NotificationRuleCreate,
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """Create a new notification rule."""
    try:
        rule = await notification_service.create_rule(MOCK_TENANT_ID, data)
        return rule
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notification rule: {str(e)}"
        )


@router.get("/rules/{event_type}", response_model=NotificationRuleResponse)
async def get_notification_rule_by_event(
    event_type: str,
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """Get the notification rule for a specific event type."""
    rule = await notification_service.get_rule_by_event(MOCK_TENANT_ID, event_type)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification rule not found for this event type"
        )
    return rule


@router.put("/rules/{rule_id}", response_model=NotificationRuleResponse)
async def update_notification_rule(
    rule_id: str,
    data: NotificationRuleUpdate,
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """Update a notification rule."""
    rule = await notification_service.update_rule(MOCK_TENANT_ID, rule_id, data)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification rule not found"
        )
    return rule


@router.delete("/rules/{rule_id}")
async def delete_notification_rule(
    rule_id: str,
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """Delete a notification rule."""
    await notification_service.delete_rule(MOCK_TENANT_ID, rule_id)
    return {"message": "Notification rule deleted"}


# Event endpoints
@router.get("/events", response_model=List[EventResponse])
async def get_alert_events(
    limit: int = 50,
    event_type: Optional[str] = None,
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """
    Get recent alert events.

    - **limit**: Maximum number of events to return (default 50)
    - **event_type**: Filter by specific event type
    """
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be between 1 and 200"
        )

    try:
        events = await notification_service.get_recent_events(
            MOCK_TENANT_ID,
            limit,
            event_type
        )
        return events
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get events: {str(e)}"
        )


@router.get("/event-catalog", response_model=List[EventCatalogItem])
async def get_event_catalog(
    _: dict = Depends(require_entitlement("observability_alerts"))
):
    """
    Get the event catalog - a list of all available event types
    with their display names, descriptions, and categories.
    """
    return notification_service.get_event_catalog()
