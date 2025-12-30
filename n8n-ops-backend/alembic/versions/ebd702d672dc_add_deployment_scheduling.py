"""add_deployment_scheduling

Revision ID: ebd702d672dc
Revises: None
Create Date: 2025-12-29 21:17:32

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ebd702d672dc'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    -- Add scheduled_at columns to deployments and promotions tables
    -- This enables scheduling deployments for future execution
    
    -- Add scheduled_at to deployments table
    ALTER TABLE deployments 
    ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP WITH TIME ZONE;
    
    -- Add scheduled_at to promotions table (for tracking)
    ALTER TABLE promotions 
    ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP WITH TIME ZONE;
    
    -- Create index for efficient querying of scheduled deployments
    CREATE INDEX IF NOT EXISTS idx_deployments_scheduled_at 
    ON deployments(scheduled_at) 
    WHERE scheduled_at IS NOT NULL AND status = 'scheduled';
    
    -- Add comment for documentation
    COMMENT ON COLUMN deployments.scheduled_at IS 'Timestamp when deployment is scheduled to execute. NULL means immediate execution.';
    COMMENT ON COLUMN promotions.scheduled_at IS 'Timestamp when promotion was scheduled to execute. NULL means immediate execution.';
    ''')


def downgrade() -> None:
    pass

