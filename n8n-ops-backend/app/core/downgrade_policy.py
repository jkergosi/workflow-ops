"""
Downgrade policy constants and configuration.

Defines grace periods, actions, and policies for handling plan downgrades
when tenants have resources that exceed their new plan limits.
"""
from enum import Enum
from typing import Dict, Any, List
from datetime import timedelta


class DowngradeAction(str, Enum):
    """Actions that can be taken when a resource exceeds plan limits after downgrade."""

    # Resource remains accessible but read-only
    READ_ONLY = "read_only"

    # Resource is marked for deletion after grace period
    SCHEDULE_DELETION = "schedule_deletion"

    # Resource is immediately disabled but not deleted
    DISABLE = "disable"

    # Resource is immediately deleted (no grace period)
    IMMEDIATE_DELETE = "immediate_delete"

    # No action taken (warning only)
    WARN_ONLY = "warn_only"

    # Archive the resource (soft delete)
    ARCHIVE = "archive"


class ResourceType(str, Enum):
    """Types of resources that can be affected by downgrades."""

    ENVIRONMENT = "environment"
    TEAM_MEMBER = "team_member"
    WORKFLOW = "workflow"
    EXECUTION = "execution"
    AUDIT_LOG = "audit_log"
    SNAPSHOT = "snapshot"


class GracePeriodStatus(str, Enum):
    """Status of a resource in grace period."""

    ACTIVE = "active"  # Grace period is active, resource still accessible
    WARNING = "warning"  # Approaching end of grace period
    EXPIRED = "expired"  # Grace period ended, action should be taken
    RESOLVED = "resolved"  # User upgraded or removed resource
    CANCELLED = "cancelled"  # Grace period was cancelled (e.g., user upgraded)


# =============================================================================
# Grace Period Configuration
# =============================================================================

# Default grace periods by resource type (in days)
DEFAULT_GRACE_PERIODS: Dict[ResourceType, int] = {
    ResourceType.ENVIRONMENT: 30,  # 30 days to upgrade or remove environments
    ResourceType.TEAM_MEMBER: 14,  # 14 days to upgrade or remove team members
    ResourceType.WORKFLOW: 30,  # 30 days to upgrade or remove workflows
    ResourceType.SNAPSHOT: 7,  # 7 days before snapshots are deleted
    ResourceType.EXECUTION: 0,  # No grace period, retention policy applies immediately
    ResourceType.AUDIT_LOG: 0,  # No grace period, retention policy applies immediately
}

# Grace period timedeltas for easy use
GRACE_PERIOD_TIMEDELTAS: Dict[ResourceType, timedelta] = {
    resource_type: timedelta(days=days)
    for resource_type, days in DEFAULT_GRACE_PERIODS.items()
}


# =============================================================================
# Downgrade Action Configuration
# =============================================================================

# Default actions by resource type when limit is exceeded
DEFAULT_DOWNGRADE_ACTIONS: Dict[ResourceType, DowngradeAction] = {
    ResourceType.ENVIRONMENT: DowngradeAction.READ_ONLY,
    ResourceType.TEAM_MEMBER: DowngradeAction.DISABLE,
    ResourceType.WORKFLOW: DowngradeAction.READ_ONLY,
    ResourceType.SNAPSHOT: DowngradeAction.SCHEDULE_DELETION,
    ResourceType.EXECUTION: DowngradeAction.SCHEDULE_DELETION,  # Via retention policy
    ResourceType.AUDIT_LOG: DowngradeAction.SCHEDULE_DELETION,  # Via retention policy
}

# Actions that allow a grace period
GRACE_PERIOD_ALLOWED_ACTIONS = {
    DowngradeAction.READ_ONLY,
    DowngradeAction.SCHEDULE_DELETION,
    DowngradeAction.ARCHIVE,
}

# Actions that are immediate (no grace period)
IMMEDIATE_ACTIONS = {
    DowngradeAction.IMMEDIATE_DELETE,
    DowngradeAction.DISABLE,
}


# =============================================================================
# Warning Thresholds
# =============================================================================

# Days before grace period expiry to send warnings
WARNING_THRESHOLDS: Dict[str, int] = {
    "first_warning": 7,  # 7 days before expiry
    "second_warning": 3,  # 3 days before expiry
    "final_warning": 1,  # 1 day before expiry
}


# =============================================================================
# Resource Selection Rules
# =============================================================================

class ResourceSelectionStrategy(str, Enum):
    """Strategy for selecting which resources to mark when over limit."""

    # Keep oldest, mark newest for action
    NEWEST_FIRST = "newest_first"

    # Keep newest, mark oldest for action
    OLDEST_FIRST = "oldest_first"

    # Mark least recently used first
    LEAST_RECENTLY_USED = "least_recently_used"

    # Mark most recently used first
    MOST_RECENTLY_USED = "most_recently_used"

    # Let user choose which to keep
    USER_CHOICE = "user_choice"


# Default selection strategy by resource type
RESOURCE_SELECTION_STRATEGY: Dict[ResourceType, ResourceSelectionStrategy] = {
    ResourceType.ENVIRONMENT: ResourceSelectionStrategy.NEWEST_FIRST,
    ResourceType.TEAM_MEMBER: ResourceSelectionStrategy.OLDEST_FIRST,
    ResourceType.WORKFLOW: ResourceSelectionStrategy.NEWEST_FIRST,
    ResourceType.SNAPSHOT: ResourceSelectionStrategy.OLDEST_FIRST,
    ResourceType.EXECUTION: ResourceSelectionStrategy.OLDEST_FIRST,
    ResourceType.AUDIT_LOG: ResourceSelectionStrategy.OLDEST_FIRST,
}


# =============================================================================
# Notification Configuration
# =============================================================================

# Email notification templates for different downgrade scenarios
NOTIFICATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    "downgrade_initiated": {
        "subject": "Plan Downgrade: Action Required",
        "template": "downgrade_initiated",
    },
    "grace_period_warning": {
        "subject": "Reminder: {days} days until resource action",
        "template": "grace_period_warning",
    },
    "grace_period_expired": {
        "subject": "Grace Period Expired: Resources affected",
        "template": "grace_period_expired",
    },
    "resource_deleted": {
        "subject": "Resources deleted due to plan limits",
        "template": "resource_deleted",
    },
    "resource_disabled": {
        "subject": "Resources disabled due to plan limits",
        "template": "resource_disabled",
    },
}

# Who should receive notifications
NOTIFICATION_RECIPIENTS = {
    "owner": True,  # Tenant owner always receives notifications
    "admins": True,  # Tenant admins receive notifications
    "affected_users": False,  # Individual users affected by resource changes
}


# =============================================================================
# Policy Rules by Resource Type
# =============================================================================

class DowngradePolicy:
    """
    Complete downgrade policy configuration for a resource type.

    Defines how resources of a specific type should be handled when
    a tenant downgrades to a plan with lower limits.
    """

    def __init__(
        self,
        resource_type: ResourceType,
        grace_period_days: int,
        action: DowngradeAction,
        selection_strategy: ResourceSelectionStrategy,
        allow_user_selection: bool = False,
        require_notification: bool = True,
        allow_grace_period_extension: bool = False,
        max_grace_period_extensions: int = 0,
    ):
        self.resource_type = resource_type
        self.grace_period_days = grace_period_days
        self.grace_period_timedelta = timedelta(days=grace_period_days)
        self.action = action
        self.selection_strategy = selection_strategy
        self.allow_user_selection = allow_user_selection
        self.require_notification = require_notification
        self.allow_grace_period_extension = allow_grace_period_extension
        self.max_grace_period_extensions = max_grace_period_extensions

    @property
    def has_grace_period(self) -> bool:
        """Check if this policy includes a grace period."""
        return self.grace_period_days > 0 and self.action in GRACE_PERIOD_ALLOWED_ACTIONS

    @property
    def is_immediate(self) -> bool:
        """Check if this policy takes immediate action."""
        return self.action in IMMEDIATE_ACTIONS

    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary representation."""
        return {
            "resource_type": self.resource_type.value,
            "grace_period_days": self.grace_period_days,
            "action": self.action.value,
            "selection_strategy": self.selection_strategy.value,
            "allow_user_selection": self.allow_user_selection,
            "require_notification": self.require_notification,
            "allow_grace_period_extension": self.allow_grace_period_extension,
            "max_grace_period_extensions": self.max_grace_period_extensions,
            "has_grace_period": self.has_grace_period,
            "is_immediate": self.is_immediate,
        }


# Predefined policies for each resource type
DOWNGRADE_POLICIES: Dict[ResourceType, DowngradePolicy] = {
    ResourceType.ENVIRONMENT: DowngradePolicy(
        resource_type=ResourceType.ENVIRONMENT,
        grace_period_days=30,
        action=DowngradeAction.READ_ONLY,
        selection_strategy=ResourceSelectionStrategy.NEWEST_FIRST,
        allow_user_selection=True,  # Let user choose which environments to keep
        require_notification=True,
        allow_grace_period_extension=False,
        max_grace_period_extensions=0,
    ),
    ResourceType.TEAM_MEMBER: DowngradePolicy(
        resource_type=ResourceType.TEAM_MEMBER,
        grace_period_days=14,
        action=DowngradeAction.DISABLE,
        selection_strategy=ResourceSelectionStrategy.OLDEST_FIRST,
        allow_user_selection=True,  # Let owner choose which members to keep
        require_notification=True,
        allow_grace_period_extension=False,
        max_grace_period_extensions=0,
    ),
    ResourceType.WORKFLOW: DowngradePolicy(
        resource_type=ResourceType.WORKFLOW,
        grace_period_days=30,
        action=DowngradeAction.READ_ONLY,
        selection_strategy=ResourceSelectionStrategy.NEWEST_FIRST,
        allow_user_selection=True,
        require_notification=True,
        allow_grace_period_extension=False,
        max_grace_period_extensions=0,
    ),
    ResourceType.SNAPSHOT: DowngradePolicy(
        resource_type=ResourceType.SNAPSHOT,
        grace_period_days=7,
        action=DowngradeAction.SCHEDULE_DELETION,
        selection_strategy=ResourceSelectionStrategy.OLDEST_FIRST,
        allow_user_selection=False,  # Automatic deletion of oldest snapshots
        require_notification=True,
        allow_grace_period_extension=False,
        max_grace_period_extensions=0,
    ),
    ResourceType.EXECUTION: DowngradePolicy(
        resource_type=ResourceType.EXECUTION,
        grace_period_days=0,  # No grace period, retention policy applies
        action=DowngradeAction.SCHEDULE_DELETION,
        selection_strategy=ResourceSelectionStrategy.OLDEST_FIRST,
        allow_user_selection=False,
        require_notification=False,  # Retention cleanup is expected behavior
        allow_grace_period_extension=False,
        max_grace_period_extensions=0,
    ),
    ResourceType.AUDIT_LOG: DowngradePolicy(
        resource_type=ResourceType.AUDIT_LOG,
        grace_period_days=0,  # No grace period, retention policy applies
        action=DowngradeAction.SCHEDULE_DELETION,
        selection_strategy=ResourceSelectionStrategy.OLDEST_FIRST,
        allow_user_selection=False,
        require_notification=False,  # Retention cleanup is expected behavior
        allow_grace_period_extension=False,
        max_grace_period_extensions=0,
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_policy(resource_type: ResourceType) -> DowngradePolicy:
    """
    Get the downgrade policy for a specific resource type.

    Args:
        resource_type: Type of resource

    Returns:
        DowngradePolicy configuration
    """
    return DOWNGRADE_POLICIES[resource_type]


def get_grace_period_days(resource_type: ResourceType) -> int:
    """
    Get the grace period in days for a resource type.

    Args:
        resource_type: Type of resource

    Returns:
        Number of days for grace period
    """
    return DEFAULT_GRACE_PERIODS[resource_type]


def get_action(resource_type: ResourceType) -> DowngradeAction:
    """
    Get the default action for a resource type.

    Args:
        resource_type: Type of resource

    Returns:
        DowngradeAction to take
    """
    return DEFAULT_DOWNGRADE_ACTIONS[resource_type]


def has_grace_period(resource_type: ResourceType) -> bool:
    """
    Check if a resource type supports grace periods.

    Args:
        resource_type: Type of resource

    Returns:
        True if grace period is supported
    """
    policy = get_policy(resource_type)
    return policy.has_grace_period


def get_warning_days() -> List[int]:
    """
    Get list of days before expiry when warnings should be sent.

    Returns:
        List of days [7, 3, 1]
    """
    return [
        WARNING_THRESHOLDS["first_warning"],
        WARNING_THRESHOLDS["second_warning"],
        WARNING_THRESHOLDS["final_warning"],
    ]


def get_selection_strategy(resource_type: ResourceType) -> ResourceSelectionStrategy:
    """
    Get the resource selection strategy for a resource type.

    Args:
        resource_type: Type of resource

    Returns:
        ResourceSelectionStrategy to use
    """
    return RESOURCE_SELECTION_STRATEGY[resource_type]


# =============================================================================
# Export all public constants and functions
# =============================================================================

__all__ = [
    # Enums
    "DowngradeAction",
    "ResourceType",
    "GracePeriodStatus",
    "ResourceSelectionStrategy",

    # Policy class
    "DowngradePolicy",

    # Configuration dictionaries
    "DEFAULT_GRACE_PERIODS",
    "GRACE_PERIOD_TIMEDELTAS",
    "DEFAULT_DOWNGRADE_ACTIONS",
    "GRACE_PERIOD_ALLOWED_ACTIONS",
    "IMMEDIATE_ACTIONS",
    "WARNING_THRESHOLDS",
    "RESOURCE_SELECTION_STRATEGY",
    "NOTIFICATION_TEMPLATES",
    "NOTIFICATION_RECIPIENTS",
    "DOWNGRADE_POLICIES",

    # Helper functions
    "get_policy",
    "get_grace_period_days",
    "get_action",
    "has_grace_period",
    "get_warning_days",
    "get_selection_strategy",
]
