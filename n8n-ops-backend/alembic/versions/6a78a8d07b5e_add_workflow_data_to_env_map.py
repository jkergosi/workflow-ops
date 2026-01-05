"""add_workflow_data_to_env_map

Revision ID: 6a78a8d07b5e
Revises: 'dcd2f2c8774d'
Create Date: 2026-01-05 17:08:30

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6a78a8d07b5e'
down_revision = 'dcd2f2c8774d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add workflow_data JSONB column to cache full workflow JSON for UI rendering
    op.execute('''
        ALTER TABLE workflow_env_map 
        ADD COLUMN IF NOT EXISTS workflow_data JSONB NULL;
    ''')
    
    # Create GIN index for efficient JSONB queries
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_env_map_workflow_data 
        ON workflow_env_map USING GIN (workflow_data) 
        WHERE workflow_data IS NOT NULL;
    ''')


def downgrade() -> None:
    # Drop index and column
    op.execute('DROP INDEX IF EXISTS idx_workflow_env_map_workflow_data;')
    op.execute('ALTER TABLE workflow_env_map DROP COLUMN IF EXISTS workflow_data;')

