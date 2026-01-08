-- Migration: Add Execution Retention Policy
-- Purpose: Enable time-based retention for executions table to prevent unbounded growth
-- Related: Task T002 - Performance hardening for large tenants (100k+ executions)

-- ============================================================================
-- 1. Create execution_retention_policies table
-- ============================================================================
-- Stores tenant-specific retention configuration for executions
-- Falls back to system default (90 days) if no tenant policy exists

CREATE TABLE IF NOT EXISTS execution_retention_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,

    -- Retention period in days (NULL = use system default from config)
    retention_days INTEGER NOT NULL DEFAULT 90,

    -- Whether retention is enabled for this tenant
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Optional: Minimum executions to keep regardless of age
    -- Useful for tenants with low activity to always show some history
    min_executions_to_keep INTEGER DEFAULT 100,

    -- Track last cleanup run
    last_cleanup_at TIMESTAMP WITH TIME ZONE,
    last_cleanup_deleted_count INTEGER DEFAULT 0,

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,

    -- Ensure one policy per tenant
    CONSTRAINT unique_tenant_retention_policy UNIQUE(tenant_id)
);

-- Index for efficient policy lookups
CREATE INDEX IF NOT EXISTS idx_retention_policies_tenant
ON execution_retention_policies(tenant_id)
WHERE is_enabled = TRUE;

-- ============================================================================
-- 2. Add indexes to executions table for efficient cleanup queries
-- ============================================================================
-- These indexes optimize the retention cleanup process by tenant and date

-- Composite index for retention queries (tenant + started_at)
-- Enables fast identification of old executions per tenant
CREATE INDEX IF NOT EXISTS idx_executions_retention_cleanup
ON executions(tenant_id, started_at)
WHERE started_at IS NOT NULL;

-- Partial index for executions without started_at (edge case cleanup)
-- Helps identify stale executions that never properly started
CREATE INDEX IF NOT EXISTS idx_executions_null_started_at
ON executions(tenant_id, created_at)
WHERE started_at IS NULL;

-- ============================================================================
-- 3. Create retention cleanup function
-- ============================================================================
-- PostgreSQL function to perform batch cleanup of old executions
-- Returns count of deleted records for monitoring/logging

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

-- ============================================================================
-- 4. Create updated_at trigger for retention_policies table
-- ============================================================================

CREATE OR REPLACE FUNCTION update_execution_retention_policies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_execution_retention_policies_updated_at
    BEFORE UPDATE ON execution_retention_policies
    FOR EACH ROW
    EXECUTE FUNCTION update_execution_retention_policies_updated_at();

-- ============================================================================
-- 5. Add helpful comments for documentation
-- ============================================================================

COMMENT ON TABLE execution_retention_policies IS 'Tenant-specific retention policies for executions. Controls automatic cleanup of old execution data to prevent unbounded database growth.';
COMMENT ON COLUMN execution_retention_policies.retention_days IS 'Number of days to retain executions. Executions older than this will be deleted during cleanup. Default: 90 days.';
COMMENT ON COLUMN execution_retention_policies.is_enabled IS 'Whether automatic retention cleanup is enabled for this tenant. When false, executions are kept indefinitely.';
COMMENT ON COLUMN execution_retention_policies.min_executions_to_keep IS 'Minimum number of executions to always keep, regardless of age. Useful for low-activity tenants to maintain some history.';
COMMENT ON COLUMN execution_retention_policies.last_cleanup_at IS 'Timestamp of last successful cleanup run for this tenant.';
COMMENT ON COLUMN execution_retention_policies.last_cleanup_deleted_count IS 'Number of executions deleted in the last cleanup run.';

COMMENT ON FUNCTION cleanup_old_executions IS 'Batch cleanup function for deleting old executions based on retention policy. Returns count of deleted records and summary JSONB. Safe to run repeatedly - respects min_executions_to_keep threshold.';

COMMENT ON INDEX idx_executions_retention_cleanup IS 'Optimizes retention cleanup queries by tenant and started_at date.';
COMMENT ON INDEX idx_executions_null_started_at IS 'Handles cleanup of stale executions that never properly started (started_at IS NULL).';

-- ============================================================================
-- 6. Insert default retention policies for existing tenants (optional)
-- ============================================================================
-- Uncomment to automatically create default policies for existing tenants
-- This is conservative - enables 90-day retention for all existing tenants

-- INSERT INTO execution_retention_policies (tenant_id, retention_days, is_enabled)
-- SELECT DISTINCT tenant_id, 90, TRUE
-- FROM executions
-- WHERE tenant_id IS NOT NULL
-- ON CONFLICT (tenant_id) DO NOTHING;
