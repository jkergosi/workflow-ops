"""add_execution_retention_policy

Revision ID: 20260108_retention
Revises: 20260108_mat_views
Create Date: 2026-01-08

Adds execution retention policy infrastructure for automatic cleanup of old executions.
This prevents unbounded database growth and improves query performance for large tenants.

Key components:
- execution_retention_policies table: Stores tenant-specific retention configuration
- cleanup_old_executions() function: Batch cleanup with safety thresholds
- Optimized indexes for efficient retention queries
- Updated_at trigger for audit tracking

Default retention: 90 days (configurable per tenant)
Safety feature: Maintains minimum execution count even if older than retention period
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260108_retention'
down_revision = '20260108_mat_views'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create execution_retention_policies table
    op.execute('''
        CREATE TABLE IF NOT EXISTS execution_retention_policies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            retention_days INTEGER NOT NULL DEFAULT 90,
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            min_executions_to_keep INTEGER DEFAULT 100,
            last_cleanup_at TIMESTAMP WITH TIME ZONE,
            last_cleanup_deleted_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_by UUID,
            updated_by UUID,
            CONSTRAINT unique_tenant_retention_policy UNIQUE(tenant_id)
        );
    ''')

    # Create indexes for retention policies
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_retention_policies_tenant
        ON execution_retention_policies(tenant_id)
        WHERE is_enabled = TRUE;
    ''')

    # Add indexes to executions table for efficient cleanup queries
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_executions_retention_cleanup
        ON executions(tenant_id, started_at)
        WHERE started_at IS NOT NULL;
    ''')

    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_executions_null_started_at
        ON executions(tenant_id, created_at)
        WHERE started_at IS NULL;
    ''')

    # Create retention cleanup function
    op.execute('''
        CREATE OR REPLACE FUNCTION cleanup_old_executions(
            p_tenant_id UUID,
            p_retention_days INTEGER DEFAULT 90,
            p_min_executions_to_keep INTEGER DEFAULT 100,
            p_batch_size INTEGER DEFAULT 1000
        )
        RETURNS TABLE(deleted_count INTEGER, execution_summary JSONB) AS $$
        DECLARE
            v_cutoff_date TIMESTAMP WITH TIME ZONE;
            v_deleted_count INTEGER := 0;
            v_total_executions INTEGER;
            v_executions_to_keep INTEGER;
            v_summary JSONB;
        BEGIN
            -- Calculate cutoff date
            v_cutoff_date := NOW() - (p_retention_days || ' days')::INTERVAL;

            -- Count total executions for tenant
            SELECT COUNT(*) INTO v_total_executions
            FROM executions
            WHERE tenant_id = p_tenant_id;

            -- Calculate how many executions we can safely delete
            -- Ensure we keep at least min_executions_to_keep
            v_executions_to_keep := GREATEST(p_min_executions_to_keep, 0);

            -- Only delete if we have more than min_executions_to_keep
            IF v_total_executions <= v_executions_to_keep THEN
                -- Build summary with no deletions
                v_summary := jsonb_build_object(
                    'tenant_id', p_tenant_id,
                    'cutoff_date', v_cutoff_date,
                    'total_executions', v_total_executions,
                    'min_to_keep', v_executions_to_keep,
                    'deleted', 0,
                    'reason', 'Total executions below minimum threshold'
                );

                RETURN QUERY SELECT 0, v_summary;
                RETURN;
            END IF;

            -- Delete old executions in batches to avoid lock contention
            -- Use started_at as primary date filter, fall back to created_at for incomplete executions
            WITH old_executions AS (
                SELECT id
                FROM executions
                WHERE tenant_id = p_tenant_id
                  AND (
                      (started_at IS NOT NULL AND started_at < v_cutoff_date)
                      OR (started_at IS NULL AND created_at < v_cutoff_date)
                  )
                ORDER BY COALESCE(started_at, created_at) ASC
                LIMIT p_batch_size
            )
            DELETE FROM executions
            WHERE id IN (SELECT id FROM old_executions);

            -- Get count of deleted rows
            GET DIAGNOSTICS v_deleted_count = ROW_COUNT;

            -- Build execution summary
            v_summary := jsonb_build_object(
                'tenant_id', p_tenant_id,
                'cutoff_date', v_cutoff_date,
                'retention_days', p_retention_days,
                'batch_size', p_batch_size,
                'total_executions_before', v_total_executions,
                'deleted_in_batch', v_deleted_count,
                'min_to_keep', v_executions_to_keep
            );

            -- Return results
            RETURN QUERY SELECT v_deleted_count, v_summary;
        END;
        $$ LANGUAGE plpgsql;
    ''')

    # Create updated_at trigger
    op.execute('''
        CREATE OR REPLACE FUNCTION update_execution_retention_policies_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    ''')

    op.execute('''
        CREATE TRIGGER trigger_update_execution_retention_policies_updated_at
            BEFORE UPDATE ON execution_retention_policies
            FOR EACH ROW
            EXECUTE FUNCTION update_execution_retention_policies_updated_at();
    ''')

    # Add documentation comments
    op.execute('''
        COMMENT ON TABLE execution_retention_policies IS 'Tenant-specific retention policies for executions. Controls automatic cleanup of old execution data to prevent unbounded database growth.';
        COMMENT ON COLUMN execution_retention_policies.retention_days IS 'Number of days to retain executions. Executions older than this will be deleted during cleanup. Default: 90 days.';
        COMMENT ON COLUMN execution_retention_policies.is_enabled IS 'Whether automatic retention cleanup is enabled for this tenant. When false, executions are kept indefinitely.';
        COMMENT ON COLUMN execution_retention_policies.min_executions_to_keep IS 'Minimum number of executions to always keep, regardless of age. Useful for low-activity tenants to maintain some history.';
        COMMENT ON COLUMN execution_retention_policies.last_cleanup_at IS 'Timestamp of last successful cleanup run for this tenant.';
        COMMENT ON COLUMN execution_retention_policies.last_cleanup_deleted_count IS 'Number of executions deleted in the last cleanup run.';
        COMMENT ON FUNCTION cleanup_old_executions IS 'Batch cleanup function for deleting old executions based on retention policy. Returns count of deleted records and summary JSONB. Safe to run repeatedly - respects min_executions_to_keep threshold.';
        COMMENT ON INDEX idx_executions_retention_cleanup IS 'Optimizes retention cleanup queries by tenant and started_at date.';
        COMMENT ON INDEX idx_executions_null_started_at IS 'Handles cleanup of stale executions that never properly started (started_at IS NULL).';
    ''')


def downgrade() -> None:
    # Drop comments (optional, comments don't need explicit removal)
    # Drop trigger and function
    op.execute('DROP TRIGGER IF EXISTS trigger_update_execution_retention_policies_updated_at ON execution_retention_policies;')
    op.execute('DROP FUNCTION IF EXISTS update_execution_retention_policies_updated_at();')
    op.execute('DROP FUNCTION IF EXISTS cleanup_old_executions(UUID, INTEGER, INTEGER, INTEGER);')

    # Drop indexes
    op.execute('DROP INDEX IF EXISTS idx_executions_null_started_at;')
    op.execute('DROP INDEX IF EXISTS idx_executions_retention_cleanup;')
    op.execute('DROP INDEX IF EXISTS idx_retention_policies_tenant;')

    # Drop table
    op.execute('DROP TABLE IF EXISTS execution_retention_policies;')
