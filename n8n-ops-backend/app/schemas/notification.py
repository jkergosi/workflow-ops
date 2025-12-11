from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ChannelType(str, Enum):
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"


class EventType(str, Enum):
    # Promotion events
    PROMOTION_STARTED = "promotion.started"
    PROMOTION_SUCCESS = "promotion.success"
    PROMOTION_FAILURE = "promotion.failure"
    PROMOTION_BLOCKED = "promotion.blocked"
    # Sync/Drift events
    SYNC_FAILURE = "sync.failure"
    SYNC_DRIFT_DETECTED = "sync.drift_detected"
    # Environment events
    ENVIRONMENT_UNHEALTHY = "environment.unhealthy"
    ENVIRONMENT_CONNECTION_LOST = "environment.connection_lost"
    ENVIRONMENT_RECOVERED = "environment.recovered"
    # Snapshot events
    SNAPSHOT_CREATED = "snapshot.created"
    SNAPSHOT_RESTORE_SUCCESS = "snapshot.restore_success"
    SNAPSHOT_RESTORE_FAILURE = "snapshot.restore_failure"
    # Credential events
    CREDENTIAL_PLACEHOLDER_CREATED = "credential.placeholder_created"
    CREDENTIAL_MISSING = "credential.missing"
    # System events
    SYSTEM_ERROR = "system.error"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


# Channel Config Models
class SlackConfig(BaseModel):
    webhook_url: str  # Slack incoming webhook URL
    channel: Optional[str] = None  # Override channel (optional)
    username: Optional[str] = None  # Override username (optional)
    icon_emoji: Optional[str] = None  # Override icon (optional)


class EmailConfig(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    from_address: str
    to_addresses: List[str]
    use_tls: bool = True


class WebhookConfig(BaseModel):
    url: str
    method: str = "POST"
    headers: Optional[Dict[str, str]] = None
    auth_type: Optional[str] = None  # "none", "basic", "bearer"
    auth_value: Optional[str] = None  # Basic auth credentials or bearer token


class NotificationChannelBase(BaseModel):
    name: str
    type: ChannelType
    config_json: Dict[str, Any]
    is_enabled: bool = True


class NotificationChannelCreate(NotificationChannelBase):
    pass


class NotificationChannelUpdate(BaseModel):
    name: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None


class NotificationChannelResponse(NotificationChannelBase):
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime


# Rule Models
class NotificationRuleBase(BaseModel):
    event_type: str
    channel_ids: List[str]
    is_enabled: bool = True


class NotificationRuleCreate(NotificationRuleBase):
    pass


class NotificationRuleUpdate(BaseModel):
    channel_ids: Optional[List[str]] = None
    is_enabled: Optional[bool] = None


class NotificationRuleResponse(NotificationRuleBase):
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime


# Event Models
class EventCreate(BaseModel):
    event_type: str
    environment_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class EventResponse(BaseModel):
    id: str
    tenant_id: str
    event_type: str
    environment_id: Optional[str] = None
    timestamp: datetime
    metadata_json: Optional[Dict[str, Any]] = None
    notification_status: Optional[NotificationStatus] = None
    channels_notified: Optional[List[str]] = None


# Event Catalog for UI
class EventCatalogItem(BaseModel):
    event_type: str
    display_name: str
    description: str
    category: str


# Static event catalog
EVENT_CATALOG: List[EventCatalogItem] = [
    # Promotion events
    EventCatalogItem(
        event_type="promotion.started",
        display_name="Promotion Started",
        description="A workflow promotion has been initiated",
        category="promotion"
    ),
    EventCatalogItem(
        event_type="promotion.success",
        display_name="Promotion Success",
        description="A workflow promotion completed successfully",
        category="promotion"
    ),
    EventCatalogItem(
        event_type="promotion.failure",
        display_name="Promotion Failed",
        description="A workflow promotion failed to complete",
        category="promotion"
    ),
    EventCatalogItem(
        event_type="promotion.blocked",
        display_name="Promotion Blocked",
        description="A workflow promotion was blocked by gates or approvals",
        category="promotion"
    ),
    # Sync/Drift events
    EventCatalogItem(
        event_type="sync.failure",
        display_name="Sync Failed",
        description="Environment synchronization failed",
        category="sync"
    ),
    EventCatalogItem(
        event_type="sync.drift_detected",
        display_name="Drift Detected",
        description="Workflow drift detected between environments",
        category="sync"
    ),
    # Environment events
    EventCatalogItem(
        event_type="environment.unhealthy",
        display_name="Environment Unhealthy",
        description="An environment health check failed",
        category="environment"
    ),
    EventCatalogItem(
        event_type="environment.connection_lost",
        display_name="Connection Lost",
        description="Connection to an n8n instance was lost",
        category="environment"
    ),
    EventCatalogItem(
        event_type="environment.recovered",
        display_name="Environment Recovered",
        description="A previously unhealthy environment has recovered",
        category="environment"
    ),
    # Snapshot events
    EventCatalogItem(
        event_type="snapshot.created",
        display_name="Snapshot Created",
        description="A new environment snapshot was created",
        category="snapshot"
    ),
    EventCatalogItem(
        event_type="snapshot.restore_success",
        display_name="Snapshot Restored",
        description="An environment was successfully restored from a snapshot",
        category="snapshot"
    ),
    EventCatalogItem(
        event_type="snapshot.restore_failure",
        display_name="Snapshot Restore Failed",
        description="Failed to restore an environment from a snapshot",
        category="snapshot"
    ),
    # Credential events
    EventCatalogItem(
        event_type="credential.placeholder_created",
        display_name="Credential Placeholder Created",
        description="A placeholder credential was created during promotion",
        category="credential"
    ),
    EventCatalogItem(
        event_type="credential.missing",
        display_name="Credential Missing",
        description="A required credential is missing in the target environment",
        category="credential"
    ),
    # System events
    EventCatalogItem(
        event_type="system.error",
        display_name="System Error",
        description="An unexpected system error occurred",
        category="system"
    ),
]
