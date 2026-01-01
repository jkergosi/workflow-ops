"""sync_tenant_plans_with_subscription_tier

Revision ID: d393b8991c99
Revises: d6197225e0a0
Create Date: 2025-12-31 15:53:36.787041

This migration syncs the tenant_plans table with the tenants.subscription_tier field.
It ensures that every tenant has a corresponding tenant_plans record that matches
their subscription_tier.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd393b8991c99'
down_revision = 'd6197225e0a0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update existing tenant_plans records to match the correct plan based on
    # the tenant's subscription_tier field
    op.execute("""
        UPDATE tenant_plans tp
        SET plan_id = p.id,
            updated_at = NOW()
        FROM tenants t
        JOIN plans p ON p.name = t.subscription_tier
        WHERE tp.tenant_id = t.id
        AND tp.plan_id != p.id;
    """)

    # Insert missing tenant_plans records for tenants that don't have one
    op.execute("""
        INSERT INTO tenant_plans (id, tenant_id, plan_id, is_active, entitlements_version, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            t.id,
            p.id,
            true,
            1,
            NOW(),
            NOW()
        FROM tenants t
        JOIN plans p ON p.name = t.subscription_tier
        WHERE NOT EXISTS (
            SELECT 1 FROM tenant_plans tp WHERE tp.tenant_id = t.id
        );
    """)


def downgrade() -> None:
    # Revert to free plan for all tenant_plans (not recommended, just for rollback)
    pass
