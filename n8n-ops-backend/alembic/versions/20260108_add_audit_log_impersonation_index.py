"""add_audit_log_impersonation_index

Revision ID: 20260108_audit_imp_idx
Revises: 380513d302f0
Create Date: 2026-01-08

Adds optimized database indexes for audit log queries on impersonation sessions.

This migration improves query performance for:
1. Finding all actions performed during a specific impersonation session
2. Searching audit logs by impersonated user (to see what was done "as" them)
3. Analyzing impersonation activity patterns across tenants
4. Security audits and compliance reporting

The indexes support both exact lookups and filtered queries combining
impersonation context with timestamps, making audit trail queries performant
even with large audit log datasets.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260108_audit_imp_idx'
down_revision = '380513d302f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add indexes for impersonation-related audit log queries
    op.execute('''
        -- Index for queries filtering by impersonation session ID
        -- Supports: "Show me all actions during this impersonation session"
        CREATE INDEX IF NOT EXISTS idx_audit_logs_impersonation_session_id
        ON audit_logs(impersonation_session_id)
        WHERE impersonation_session_id IS NOT NULL;

        -- Composite index for impersonation session queries with timestamp ordering
        -- Supports: "Show me all actions during this session, ordered by time"
        CREATE INDEX IF NOT EXISTS idx_audit_logs_impersonation_session_timestamp
        ON audit_logs(impersonation_session_id, timestamp DESC)
        WHERE impersonation_session_id IS NOT NULL;

        -- Index for queries filtering by impersonated user
        -- Supports: "Show me all actions performed as this user (across all sessions)"
        CREATE INDEX IF NOT EXISTS idx_audit_logs_impersonated_user_id
        ON audit_logs(impersonated_user_id)
        WHERE impersonated_user_id IS NOT NULL;

        -- Composite index for impersonated user queries with timestamp
        -- Supports: "Show me recent actions performed as this user"
        CREATE INDEX IF NOT EXISTS idx_audit_logs_impersonated_user_timestamp
        ON audit_logs(impersonated_user_id, timestamp DESC)
        WHERE impersonated_user_id IS NOT NULL;

        -- Composite index for tenant + impersonation filtering
        -- Supports: "Show me all impersonation activity within this tenant"
        CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_impersonation
        ON audit_logs(tenant_id, impersonation_session_id, timestamp DESC)
        WHERE impersonation_session_id IS NOT NULL;

        -- Index for actor queries during impersonation
        -- Supports: "Show me all actions by this platform admin while impersonating"
        -- Note: actor_id represents the impersonator when impersonation_session_id is set
        CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_impersonation
        ON audit_logs(actor_id, impersonation_session_id, timestamp DESC)
        WHERE impersonation_session_id IS NOT NULL;
    ''')

    # Add documentation comments
    op.execute('''
        COMMENT ON INDEX idx_audit_logs_impersonation_session_id IS 'Optimizes queries filtering audit logs by impersonation session ID. Supports security audits and compliance reporting.';
        COMMENT ON INDEX idx_audit_logs_impersonation_session_timestamp IS 'Optimizes time-ordered queries for a specific impersonation session. Enables efficient session activity timelines.';
        COMMENT ON INDEX idx_audit_logs_impersonated_user_id IS 'Optimizes queries for all actions performed as a specific user across all impersonation sessions.';
        COMMENT ON INDEX idx_audit_logs_impersonated_user_timestamp IS 'Optimizes time-ordered queries for actions performed as a specific user during impersonation.';
        COMMENT ON INDEX idx_audit_logs_tenant_impersonation IS 'Optimizes queries for all impersonation activity within a tenant. Supports tenant-level impersonation audits.';
        COMMENT ON INDEX idx_audit_logs_actor_impersonation IS 'Optimizes queries for actions by a specific platform admin during impersonation. Tracks admin activity patterns.';
    ''')


def downgrade() -> None:
    # Drop indexes in reverse order
    op.execute('''
        DROP INDEX IF EXISTS idx_audit_logs_actor_impersonation;
        DROP INDEX IF EXISTS idx_audit_logs_tenant_impersonation;
        DROP INDEX IF EXISTS idx_audit_logs_impersonated_user_timestamp;
        DROP INDEX IF EXISTS idx_audit_logs_impersonated_user_id;
        DROP INDEX IF EXISTS idx_audit_logs_impersonation_session_timestamp;
        DROP INDEX IF EXISTS idx_audit_logs_impersonation_session_id;
    ''')
