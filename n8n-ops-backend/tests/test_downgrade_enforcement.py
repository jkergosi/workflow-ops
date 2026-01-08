import pytest
from unittest.mock import AsyncMock, patch

from app.services.downgrade_service import (
    downgrade_service,
    GracePeriodStatus,
    DowngradeAction,
    ResourceType,
)


@pytest.mark.asyncio
async def test_enforce_expired_grace_periods_idempotent():
    expired = [
        {
            "id": "gp-1",
            "tenant_id": "tenant-1",
            "resource_type": ResourceType.ENVIRONMENT.value,
            "resource_id": "env-1",
            "action": DowngradeAction.READ_ONLY.value,
            "status": GracePeriodStatus.ACTIVE.value,
        }
    ]

    with patch.object(
        downgrade_service,
        "get_expired_grace_periods",
        AsyncMock(side_effect=[expired, []]),
    ), patch.object(
        downgrade_service,
        "execute_downgrade_action",
        AsyncMock(return_value=True),
    ) as exec_action, patch.object(
        downgrade_service,
        "_update_grace_period_status",
        AsyncMock(return_value=True),
    ) as update_status:
        first_run = await downgrade_service.enforce_expired_grace_periods()
        second_run = await downgrade_service.enforce_expired_grace_periods()

    assert first_run["enforced_count"] == 1
    assert first_run["errors"] == []
    exec_action.assert_awaited_once()
    update_status.assert_awaited_once()

    assert second_run["checked_count"] == 0
    assert second_run["enforced_count"] == 0


@pytest.mark.asyncio
async def test_detect_overlimit_skips_existing_grace_periods():
    active_grace = [
        {
            "resource_type": ResourceType.ENVIRONMENT.value,
            "resource_id": "env-1",
            "status": GracePeriodStatus.ACTIVE.value,
        }
    ]

    with patch.object(
        downgrade_service,
        "get_active_grace_periods",
        AsyncMock(return_value=active_grace),
    ), patch.object(
        downgrade_service,
        "detect_environment_overlimit",
        AsyncMock(return_value=(True, 3, 1, ["env-1", "env-2"])),
    ), patch.object(
        downgrade_service,
        "detect_team_member_overlimit",
        AsyncMock(return_value=(False, 0, 0, [])),
    ), patch.object(
        downgrade_service,
        "detect_workflow_overlimit",
        AsyncMock(return_value=(False, 0, 0, [])),
    ), patch.object(
        downgrade_service,
        "initiate_grace_period",
        AsyncMock(return_value="gp-2"),
    ) as initiate_grace:
        summary = await downgrade_service.detect_overlimit_for_tenant("tenant-1")

    assert summary["grace_periods_created"] == 1
    assert summary["skipped_existing"] == 1
    initiate_grace.assert_awaited_once_with(
        tenant_id="tenant-1",
        resource_type=ResourceType.ENVIRONMENT,
        resource_id="env-2",
        reason="Scheduled over-limit check",
    )

