import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_handle_subscription_updated_downgrades_entitlements_on_unpaid():
    from app.api.endpoints.billing import handle_subscription_updated

    subscription = {
        "id": "sub_test_1",
        "status": "unpaid",
        "cancel_at_period_end": False,
        "current_period_start": 1704067200,
        "current_period_end": 1706745600,
        "items": {"data": [{"id": "si_1", "price": {"id": "price_monthly_pro"}, "quantity": 1}]},
        "metadata": {"tenant_id": "tenant-123"},
    }

    with patch("app.api.endpoints.billing.db_service") as mock_db, patch(
        "app.api.endpoints.billing.set_tenant_plan", new_callable=AsyncMock
    ) as mock_set_plan, patch(
        "app.api.endpoints.billing.upsert_subscription_items", new_callable=AsyncMock
    ) as mock_upsert_items:
        # subscription_plans lookup by price id
        plan_exec = MagicMock()
        plan_exec.data = {"id": "plan-pro", "name": "pro"}
        mock_db.client.table.return_value.select.return_value.or_.return_value.single.return_value.execute.return_value = plan_exec

        # subscriptions update chain
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        await handle_subscription_updated(subscription)

        mock_set_plan.assert_awaited_once_with("tenant-123", "free")
        mock_upsert_items.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_subscription_updated_keeps_entitlements_on_active():
    from app.api.endpoints.billing import handle_subscription_updated

    subscription = {
        "id": "sub_test_2",
        "status": "active",
        "cancel_at_period_end": False,
        "current_period_start": 1704067200,
        "current_period_end": 1706745600,
        "items": {"data": [{"id": "si_2", "price": {"id": "price_monthly_pro"}, "quantity": 1}]},
        "metadata": {"tenant_id": "tenant-456"},
    }

    with patch("app.api.endpoints.billing.db_service") as mock_db, patch(
        "app.api.endpoints.billing.set_tenant_plan", new_callable=AsyncMock
    ) as mock_set_plan, patch(
        "app.api.endpoints.billing.upsert_subscription_items", new_callable=AsyncMock
    ) as mock_upsert_items:
        plan_exec = MagicMock()
        plan_exec.data = {"id": "plan-pro", "name": "pro"}
        mock_db.client.table.return_value.select.return_value.or_.return_value.single.return_value.execute.return_value = plan_exec
        mock_db.client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        await handle_subscription_updated(subscription)

        mock_set_plan.assert_awaited_once_with("tenant-456", "pro")
        mock_upsert_items.assert_awaited_once()


