"""add_tenant_hierarchy_and_billing_items

Revision ID: 7c71b22483d5
Revises: 'd393b8991c99'
Create Date: 2025-12-31 17:45:16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7c71b22483d5'
down_revision = 'd393b8991c99'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    ALTER TABLE tenants ADD COLUMN IF NOT EXISTS parent_tenant_id uuid REFERENCES tenants(id);
    CREATE INDEX IF NOT EXISTS ix_tenants_parent ON tenants(parent_tenant_id);
    
    CREATE UNIQUE INDEX IF NOT EXISTS ux_tenant_plans_one_active
    ON tenant_plans (tenant_id)
    WHERE is_active = true;
    
    CREATE TABLE IF NOT EXISTS subscription_items (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id uuid NOT NULL REFERENCES tenants(id),
      stripe_subscription_id text NOT NULL,
      stripe_subscription_item_id text NOT NULL,
      stripe_price_id text NOT NULL,
      usage_type text NOT NULL CHECK (usage_type IN ('base','per_client')),
      created_at timestamptz DEFAULT now(),
      updated_at timestamptz DEFAULT now(),
      UNIQUE(stripe_subscription_item_id)
    );
    
    CREATE TABLE IF NOT EXISTS subscription_plan_price_items (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      plan_name text NOT NULL,
      usage_type text NOT NULL CHECK (usage_type IN ('base','per_client')),
      stripe_price_id_monthly text,
      stripe_price_id_yearly text,
      created_at timestamptz DEFAULT now(),
      updated_at timestamptz DEFAULT now(),
      UNIQUE(plan_name, usage_type)
    );
    ''')


def downgrade() -> None:
    pass

