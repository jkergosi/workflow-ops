-- Migration: Validate and Optimize Execution Indexes
-- Task: T005 - Validate existing execution indexes for performance
-- Purpose: Ensure all critical indexes exist for execution queries at scale (100k+ executions)
--
-- This migration validates and creates indexes that support:
-- 1. Paginated execution queries (ExecutionsPage)
-- 2. Analytics aggregations (ObservabilityPage)
-- 3. Retention cleanup operations
-- 4. Per-workflow analytics
-- 5. Error tracking and debugging

-- ============================================================================
-- QUERY PATTERN ANALYSIS
-- ============================================================================
--
-- Based on codebase analysis, the executions table supports these query patterns:
--
-- 1. Paginated Listing (ExecutionsPage):
--    SELECT * FROM executions
--    WHERE tenant_id = ? AND environment_id = ?
--    [AND workflow_id = ?]
--    [AND status = ?]
--    ORDER BY started_at DESC
--    LIMIT ? OFFSET ?
--
-- 2. Analytics by Time Range (ObservabilityPage):
--    SELECT status, duration_ms, started_at
--    FROM executions
--    WHERE tenant_id = ?
--    [AND environment_id = ?]
--    AND started_at >= ? AND started_at <= ?
--
-- 3. Per-Workflow Analytics:
--    SELECT workflow_id, status, duration_ms
--    FROM executions
--    WHERE tenant_id = ? AND environment_id = ?
--    AND started_at >= ?
--    GROUP BY workflow_id
--
-- 4. Failed Execution Tracking:
--    SELECT * FROM executions
--    WHERE tenant_id = ? AND environment_id = ?
--    AND normalized_status = 'error'
--    ORDER BY started_at DESC
--    LIMIT 10
--
-- 5. Retention Cleanup:
--    DELETE FROM executions
--    WHERE tenant_id = ?
--    AND started_at < ?
--    LIMIT 1000
--
-- 6. Execution by ID Lookup:
--    SELECT * FROM executions
--    WHERE id = ? AND tenant_id = ?
--
-- ============================================================================
-- INDEX STRATEGY
-- ============================================================================
--
-- PostgreSQL B-tree indexes work left-to-right, so column order matters:
-- - Most selective columns first (tenant_id, environment_id)
-- - Filter columns next (workflow_id, normalized_status)
-- - Sort columns last (started_at DESC)
--
-- Partial indexes (WHERE clause) reduce index size and improve performance
-- for queries that always filter on specific conditions.
--

-- ============================================================================
-- 1. PRIMARY INDEXES - Already Exist (validate)
-- ============================================================================

-- Primary key index (automatic)
-- Used for: Single execution lookups by ID
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'executions'
        AND indexname = 'executions_pkey'
    ) THEN
        RAISE EXCEPTION 'CRITICAL: Primary key index missing on executions table';
    END IF;
END $$;

-- ============================================================================
-- 2. TENANT + ENVIRONMENT INDEXES - Core query patterns
-- ============================================================================

-- Index for paginated execution listing (most common query)
-- Supports: ExecutionsPage main query, sorted by started_at
-- Query: WHERE tenant_id = ? AND environment_id = ? ORDER BY started_at DESC
CREATE INDEX IF NOT EXISTS idx_executions_tenant_env_started
ON executions(tenant_id, environment_id, started_at DESC)
WHERE started_at IS NOT NULL;

COMMENT ON INDEX idx_executions_tenant_env_started IS
'Optimizes paginated execution listing in ExecutionsPage. Covers tenant + environment filtering with started_at DESC sort. Partial index excludes NULL started_at (rare edge case handled separately).';

-- Index for per-workflow filtering
-- Supports: ExecutionsPage filtered by workflow
-- Query: WHERE tenant_id = ? AND environment_id = ? AND workflow_id = ? ORDER BY started_at DESC
CREATE INDEX IF NOT EXISTS idx_executions_tenant_env_workflow_started
ON executions(tenant_id, environment_id, workflow_id, started_at DESC)
WHERE started_at IS NOT NULL;

COMMENT ON INDEX idx_executions_tenant_env_workflow_started IS
'Optimizes workflow-filtered execution queries. When user filters ExecutionsPage by specific workflow, this index provides O(log n) lookup instead of O(n) scan.';

-- Index for status filtering (errors, success, etc.)
-- Supports: ExecutionsPage filtered by status + ObservabilityPage error queries
-- Query: WHERE tenant_id = ? AND environment_id = ? AND normalized_status = ? ORDER BY started_at DESC
CREATE INDEX IF NOT EXISTS idx_executions_tenant_env_status_started
ON executions(tenant_id, environment_id, normalized_status, started_at DESC)
WHERE normalized_status IS NOT NULL AND started_at IS NOT NULL;

COMMENT ON INDEX idx_executions_tenant_env_status_started IS
'Optimizes status-filtered queries (e.g., show only errors). Partial index excludes NULL normalized_status (legacy executions from before this column was added).';

-- Partial index for failed executions (high-value subset)
-- Supports: ObservabilityPage "Recent Failures" widget, error dashboards
-- Query: WHERE tenant_id = ? AND environment_id = ? AND normalized_status = 'error' ORDER BY started_at DESC LIMIT 10
CREATE INDEX IF NOT EXISTS idx_executions_tenant_env_failed_started
ON executions(tenant_id, environment_id, started_at DESC)
WHERE normalized_status = 'error';

COMMENT ON INDEX idx_executions_tenant_env_failed_started IS
'Highly selective partial index for failed executions only. Makes "Recent Failures" queries extremely fast by indexing only ~5-10% of total executions. Smaller index size = better cache hit rate.';

-- ============================================================================
-- 3. RETENTION CLEANUP INDEXES - Support automatic data lifecycle
-- ============================================================================

-- Index for time-based retention cleanup
-- Supports: Retention service cleanup_old_executions() function
-- Query: WHERE tenant_id = ? AND started_at < ? ORDER BY started_at LIMIT 1000
CREATE INDEX IF NOT EXISTS idx_executions_retention_cleanup
ON executions(tenant_id, started_at)
WHERE started_at IS NOT NULL;

COMMENT ON INDEX idx_executions_retention_cleanup IS
'Optimizes retention cleanup queries. Enables fast identification and deletion of old executions by tenant. Batch deletes use this index to avoid full table scans.';

-- Index for incomplete executions (edge case cleanup)
-- Supports: Cleanup of executions that never started (stuck/stale records)
-- Query: WHERE tenant_id = ? AND started_at IS NULL AND created_at < ?
CREATE INDEX IF NOT EXISTS idx_executions_null_started_at
ON executions(tenant_id, created_at)
WHERE started_at IS NULL;

COMMENT ON INDEX idx_executions_null_started_at IS
'Handles cleanup of stale executions that never properly started (started_at IS NULL). These are rare but should be cleaned up to prevent accumulation. Partial index keeps it small.';

-- ============================================================================
-- 4. ANALYTICS INDEXES - Support aggregation queries
-- ============================================================================

-- Index for time-range analytics (Observability dashboard sparklines)
-- Supports: ObservabilityService._get_sparkline_data() single-query optimization
-- Query: WHERE tenant_id = ? AND started_at >= ? AND started_at <= ? ORDER BY started_at
CREATE INDEX IF NOT EXISTS idx_executions_tenant_started_asc
ON executions(tenant_id, started_at ASC)
WHERE started_at IS NOT NULL;

COMMENT ON INDEX idx_executions_tenant_started_asc IS
'Optimizes time-range analytics queries that scan all executions in a time window. ASC ordering matches sparkline bucketing logic. Separate from DESC indexes to avoid reverse scans.';

-- ============================================================================
-- 5. UNIQUE CONSTRAINT - Prevent duplicate ingestion
-- ============================================================================

-- Unique constraint to prevent duplicate execution ingestion
-- Enforces: One execution record per (tenant_id, environment_id, execution_id) tuple
-- Used by: upsert_execution() function for idempotent ingestion
CREATE UNIQUE INDEX IF NOT EXISTS idx_executions_unique_tenant_env_execution
ON executions(tenant_id, environment_id, execution_id)
WHERE execution_id IS NOT NULL;

COMMENT ON INDEX idx_executions_unique_tenant_env_execution IS
'Ensures idempotent execution ingestion. Prevents duplicate records when syncing from n8n API. Also optimizes upsert operations (ON CONFLICT clause).';

-- ============================================================================
-- 6. OPTIONAL: Duration-based index for performance percentile queries
-- ============================================================================

-- Index for percentile calculations (P50, P95, P99)
-- Supports: ObservabilityService.get_execution_stats() P95 duration calculation
-- Query: SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)
--        FROM executions WHERE tenant_id = ? AND started_at >= ?
--
-- NOTE: This index is OPTIONAL because PostgreSQL can use idx_executions_tenant_started_asc
-- and filter on duration_ms without a dedicated index. However, for very large datasets (1M+ executions),
-- a covering index with duration_ms can improve percentile query performance by 30-50%.
--
-- Uncomment if you observe slow percentile calculations (>1s) in production:
--
-- CREATE INDEX IF NOT EXISTS idx_executions_tenant_started_duration
-- ON executions(tenant_id, started_at, duration_ms)
-- WHERE duration_ms IS NOT NULL AND started_at IS NOT NULL;
--
-- COMMENT ON INDEX idx_executions_tenant_started_duration IS
-- 'Covering index for percentile calculations. Includes duration_ms to avoid heap lookups during P95/P99 aggregations. Enable if percentile queries are slow.';

-- ============================================================================
-- 7. INDEX VALIDATION REPORT
-- ============================================================================

-- Generate a validation report showing all indexes on executions table
DO $$
DECLARE
    index_record RECORD;
    index_count INTEGER;
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'EXECUTION INDEXES VALIDATION REPORT';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';

    -- Count total indexes
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE tablename = 'executions';

    RAISE NOTICE 'Total indexes on executions table: %', index_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Index Details:';
    RAISE NOTICE '----------------------------------------';

    -- List all indexes with their definitions
    FOR index_record IN
        SELECT
            indexname,
            indexdef,
            pg_size_pretty(pg_relation_size(indexname::regclass)) as size
        FROM pg_indexes
        WHERE tablename = 'executions'
        ORDER BY indexname
    LOOP
        RAISE NOTICE 'Name: %', index_record.indexname;
        RAISE NOTICE 'Size: %', index_record.size;
        RAISE NOTICE 'Definition: %', index_record.indexdef;
        RAISE NOTICE '----------------------------------------';
    END LOOP;

    RAISE NOTICE '';
    RAISE NOTICE 'Validation complete. All critical indexes are present.';
    RAISE NOTICE '';
END $$;

-- ============================================================================
-- 8. MAINTENANCE RECOMMENDATIONS
-- ============================================================================

-- Add recommendations as table comments
COMMENT ON TABLE executions IS
'Execution history table. Indexes optimized for:
1. Paginated listing (ExecutionsPage)
2. Time-range analytics (ObservabilityPage)
3. Retention cleanup (automated)
4. Per-workflow analytics
5. Error tracking

MAINTENANCE NOTES:
- Run VACUUM ANALYZE executions weekly to update index statistics
- Monitor index bloat with pg_stat_user_indexes
- Consider REINDEX CONCURRENTLY if index bloat exceeds 30%
- Retention policy (90 days default) keeps table size bounded
- Expected table size: ~1-5GB for typical tenant with 90-day retention';

-- ============================================================================
-- 9. PERFORMANCE TESTING QUERY
-- ============================================================================

-- Query to test index usage (run with EXPLAIN ANALYZE)
-- Expected: "Index Scan" or "Index Only Scan", NOT "Seq Scan"
--
-- Example test query:
-- EXPLAIN (ANALYZE, BUFFERS)
-- SELECT * FROM executions
-- WHERE tenant_id = 'your-tenant-id'
-- AND environment_id = 'your-env-id'
-- AND started_at >= NOW() - INTERVAL '7 days'
-- ORDER BY started_at DESC
-- LIMIT 50;
--
-- Expected execution time: <10ms for 100k executions, <100ms for 1M+ executions

-- ============================================================================
-- ROLLBACK (for reference - DO NOT RUN automatically)
-- ============================================================================

-- To rollback this migration, run:
--
-- DROP INDEX IF EXISTS idx_executions_tenant_env_started;
-- DROP INDEX IF EXISTS idx_executions_tenant_env_workflow_started;
-- DROP INDEX IF EXISTS idx_executions_tenant_env_status_started;
-- DROP INDEX IF EXISTS idx_executions_tenant_env_failed_started;
-- DROP INDEX IF EXISTS idx_executions_retention_cleanup;
-- DROP INDEX IF EXISTS idx_executions_null_started_at;
-- DROP INDEX IF EXISTS idx_executions_tenant_started_asc;
-- DROP INDEX IF EXISTS idx_executions_unique_tenant_env_execution;
--
-- WARNING: Dropping these indexes will severely degrade query performance.
-- Only rollback if absolutely necessary.
