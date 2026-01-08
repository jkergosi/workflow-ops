"""add_downgrade_grace_periods_table

Revision ID: 380513d302f0
Revises: '20260108_validate_indexes'
Create Date: 2026-01-08 10:24:30

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '380513d302f0'
down_revision = '20260108_validate_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    -- Create downgrade_grace_periods table for tracking resources in grace period after plan downgrades
    CREATE TABLE IF NOT EXISTS downgrade_grace_periods (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
      resource_type VARCHAR(50) NOT NULL CHECK (resource_type IN ('environment', 'team_member', 'workflow', 'execution', 'audit_log', 'snapshot')),
      resource_id VARCHAR(255) NOT NULL,
      action VARCHAR(50) NOT NULL CHECK (action IN ('read_only', 'schedule_deletion', 'disable', 'immediate_delete', 'warn_only', 'archive')),
      status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'warning', 'expired', 'resolved', 'cancelled')),
      starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      expires_at TIMESTAMPTZ NOT NULL,
      reason TEXT,
      metadata JSONB,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    
    -- Create indexes for efficient querying
    CREATE INDEX IF NOT EXISTS ix_downgrade_grace_periods_tenant_id
      ON downgrade_grace_periods(tenant_id);
    
    CREATE INDEX IF NOT EXISTS ix_downgrade_grace_periods_tenant_status
      ON downgrade_grace_periods(tenant_id, status);
    
    CREATE INDEX IF NOT EXISTS ix_downgrade_grace_periods_expires_at
      ON downgrade_grace_periods(expires_at)
      WHERE status = 'active';
    
    CREATE INDEX IF NOT EXISTS ix_downgrade_grace_periods_resource
      ON downgrade_grace_periods(tenant_id, resource_type, resource_id);
    
    -- Unique constraint to prevent duplicate grace periods for same resource
    CREATE UNIQUE INDEX IF NOT EXISTS uix_downgrade_grace_periods_active_resource
      ON downgrade_grace_periods(tenant_id, resource_type, resource_id)
      WHERE status = 'active';
    
    -- Add comment to table
    COMMENT ON TABLE downgrade_grace_periods IS 'Tracks resources that are over-limit after a plan downgrade and are in a grace period before action is taken';
    COMMENT ON COLUMN downgrade_grace_periods.resource_type IS 'Type of resource: environment, team_member, workflow, execution, audit_log, or snapshot';
    COMMENT ON COLUMN downgrade_grace_periods.resource_id IS 'ID of the specific resource (e.g., environment_id, user_id, workflow_id)';
    COMMENT ON COLUMN downgrade_grace_periods.action IS 'Action to take when grace period expires: read_only, schedule_deletion, disable, immediate_delete, warn_only, or archive';
    COMMENT ON COLUMN downgrade_grace_periods.status IS 'Current status: active, warning, expired, resolved, or cancelled';
    COMMENT ON COLUMN downgrade_grace_periods.starts_at IS 'When the grace period started (typically when downgrade occurred)';
    COMMENT ON COLUMN downgrade_grace_periods.expires_at IS 'When the grace period expires and action should be taken';
    COMMENT ON COLUMN downgrade_grace_periods.reason IS 'Human-readable reason for the grace period (e.g., "Plan downgrade from Pro to Free")';
    COMMENT ON COLUMN downgrade_grace_periods.metadata IS 'Additional metadata about the grace period (JSON format)';
    ''')


def downgrade() -> None:
    pass

