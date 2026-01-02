"""add_agency_to_tenants_subscription_tier

Revision ID: 86cc31c831b1
Revises: b3da68cf4d15
Create Date: 2026-01-02 10:24:43.312796

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '86cc31c831b1'
down_revision = 'b3da68cf4d15'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing constraint and add a new one with 'agency' included
    op.execute("""
        ALTER TABLE tenants DROP CONSTRAINT IF EXISTS tenants_subscription_tier_check;
        ALTER TABLE tenants ADD CONSTRAINT tenants_subscription_tier_check
            CHECK (subscription_tier IN ('free', 'pro', 'agency', 'enterprise'));
    """)


def downgrade() -> None:
    # Revert to constraint without 'agency'
    op.execute("""
        ALTER TABLE tenants DROP CONSTRAINT IF EXISTS tenants_subscription_tier_check;
        ALTER TABLE tenants ADD CONSTRAINT tenants_subscription_tier_check
            CHECK (subscription_tier IN ('free', 'pro', 'enterprise'));
    """)
