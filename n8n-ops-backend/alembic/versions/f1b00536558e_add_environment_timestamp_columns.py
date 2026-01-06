"""add_environment_timestamp_columns

Revision ID: f1b00536558e
Revises: '6a78a8d07b5e'
Create Date: 2026-01-06 09:24:22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f1b00536558e'
down_revision = '6a78a8d07b5e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    ALTER TABLE environments ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ NULL; ALTER TABLE environments ADD COLUMN IF NOT EXISTS last_drift_check_at TIMESTAMPTZ NULL; ALTER TABLE environments ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ NULL;
    ''')


def downgrade() -> None:
    pass

