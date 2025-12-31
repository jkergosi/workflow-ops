"""add_provider_to_audit_logs

Revision ID: f7g8h9i0j1k2
Revises: 'a1b2c3d4e5f6'
Create Date: 2025-01-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f7g8h9i0j1k2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    -- Add provider column to audit_logs (nullable for platform-scoped actions)
    ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS provider TEXT;
    
    -- Create indexes for provider filtering
    CREATE INDEX IF NOT EXISTS idx_audit_logs_provider ON audit_logs(provider);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_provider_timestamp ON audit_logs(provider, timestamp DESC);
    ''')


def downgrade() -> None:
    op.execute('''
    -- Drop indexes
    DROP INDEX IF EXISTS idx_audit_logs_provider_timestamp;
    DROP INDEX IF EXISTS idx_audit_logs_provider;
    
    -- Drop provider column
    ALTER TABLE audit_logs DROP COLUMN IF EXISTS provider;
    ''')

