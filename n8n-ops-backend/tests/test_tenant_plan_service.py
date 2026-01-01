import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_set_tenant_plan_inserts_new_active_plan_and_updates_tenant():
    from app.services.tenant_plan_service import set_tenant_plan

    tenant_id = "tenant-1"

    with patch("app.services.tenant_plan_service.get_tenant_parent_id", new_callable=AsyncMock) as mock_parent, patch(
        "app.services.tenant_plan_service.list_child_tenant_ids", new_callable=AsyncMock
    ) as mock_children, patch(
        "app.services.tenant_plan_service.resolve_plan_id", new_callable=AsyncMock
    ) as mock_resolve_plan_id, patch(
        "app.services.tenant_plan_service.get_current_active_plan", new_callable=AsyncMock
    ) as mock_current, patch(
        "app.services.tenant_plan_service.db_service"
    ) as mock_db:
        mock_parent.return_value = None
        mock_children.return_value = []
        mock_resolve_plan_id.return_value = "plan-pro-id"
        mock_current.return_value = None

        tenant_plans_table = MagicMock()
        tenants_table = MagicMock()

        def table_side_effect(name: str):
            if name == "tenant_plans":
                return tenant_plans_table
            if name == "tenants":
                return tenants_table
            return MagicMock()

        mock_db.client.table.side_effect = table_side_effect

        # Chains
        tenant_plans_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()
        tenant_plans_table.insert.return_value.execute.return_value = MagicMock()
        tenants_table.update.return_value.eq.return_value.execute.return_value = MagicMock()

        changed = await set_tenant_plan(tenant_id, "pro")

        assert changed is True
        tenant_plans_table.update.assert_called()
        tenant_plans_table.insert.assert_called()
        tenants_table.update.assert_called()


@pytest.mark.asyncio
async def test_set_tenant_plan_noops_when_same_plan():
    from app.services.tenant_plan_service import set_tenant_plan, TenantPlanAssignment

    tenant_id = "tenant-1"

    with patch("app.services.tenant_plan_service.get_tenant_parent_id", new_callable=AsyncMock) as mock_parent, patch(
        "app.services.tenant_plan_service.list_child_tenant_ids", new_callable=AsyncMock
    ) as mock_children, patch(
        "app.services.tenant_plan_service.resolve_plan_id", new_callable=AsyncMock
    ) as mock_resolve_plan_id, patch(
        "app.services.tenant_plan_service.get_current_active_plan", new_callable=AsyncMock
    ) as mock_current, patch(
        "app.services.tenant_plan_service.db_service"
    ) as mock_db:
        mock_parent.return_value = None
        mock_children.return_value = []
        mock_resolve_plan_id.return_value = "plan-pro-id"
        mock_current.return_value = TenantPlanAssignment(
            tenant_id=tenant_id, plan_id="plan-pro-id", plan_name="pro", entitlements_version=5
        )

        changed = await set_tenant_plan(tenant_id, "pro")

        assert changed is False
        mock_db.client.table.assert_not_called()


@pytest.mark.asyncio
async def test_set_tenant_plan_propagates_to_children_and_downgrades_to_free():
    from app.services.tenant_plan_service import set_tenant_plan

    with patch("app.services.tenant_plan_service.get_tenant_parent_id", new_callable=AsyncMock) as mock_parent, patch(
        "app.services.tenant_plan_service.list_child_tenant_ids", new_callable=AsyncMock
    ) as mock_children, patch(
        "app.services.tenant_plan_service._set_plan_for_tenant", new_callable=AsyncMock
    ) as mock_set_for_tenant:
        mock_parent.return_value = None
        mock_children.return_value = ["child-1", "child-2"]
        mock_set_for_tenant.return_value = True

        await set_tenant_plan("agency-1", "free")

        # agency set first
        mock_set_for_tenant.assert_any_call("agency-1", "free", allow_child_override=False)
        # children should be forced to free (not agency/enterprise)
        mock_set_for_tenant.assert_any_call("child-1", "free", allow_child_override=True)
        mock_set_for_tenant.assert_any_call("child-2", "free", allow_child_override=True)


