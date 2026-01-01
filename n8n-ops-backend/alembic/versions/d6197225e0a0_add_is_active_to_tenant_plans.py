"""add_is_active_to_tenant_plans

Revision ID: d6197225e0a0
Revises: 3c4da474d855
Create Date: 2025-12-31 15:51:11.864652

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6197225e0a0'
down_revision = '3c4da474d855'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_active column to tenant_plans if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenant_plans'
                AND column_name = 'is_active'
            ) THEN
                ALTER TABLE tenant_plans ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true;
            END IF;
        END $$;
    """)

    # Add is_active column to tenant_feature_overrides if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenant_feature_overrides'
                AND column_name = 'is_active'
            ) THEN
                ALTER TABLE tenant_feature_overrides ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove is_active column from tenant_plans
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenant_plans'
                AND column_name = 'is_active'
            ) THEN
                ALTER TABLE tenant_plans DROP COLUMN is_active;
            END IF;
        END $$;
    """)

    # Remove is_active column from tenant_feature_overrides
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tenant_feature_overrides'
                AND column_name = 'is_active'
            ) THEN
                ALTER TABLE tenant_feature_overrides DROP COLUMN is_active;
            END IF;
        END $$;
    """)
