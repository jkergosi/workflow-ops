-- ============================================================================
-- Execution Indexes Validation Script
-- ============================================================================
-- Purpose: Validate that all critical indexes exist and are healthy
-- Usage: psql -d your_database -f validate_execution_indexes.sql
-- Output: Human-readable report of index status
-- ============================================================================

\echo '========================================'
\echo 'EXECUTION INDEXES VALIDATION REPORT'
\echo '========================================'
\echo ''

-- ============================================================================
-- 1. Check if executions table exists
-- ============================================================================

\echo '1. TABLE EXISTENCE CHECK'
\echo '----------------------------------------'

SELECT
    CASE
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'executions')
        THEN '✓ executions table exists'
        ELSE '✗ ERROR: executions table not found!'
    END AS status;

\echo ''

-- ============================================================================
-- 2. Check all required indexes
-- ============================================================================

\echo '2. REQUIRED INDEXES CHECK'
\echo '----------------------------------------'

WITH required_indexes AS (
    SELECT unnest(ARRAY[
        'executions_pkey',
        'idx_executions_tenant_env_started',
        'idx_executions_tenant_env_workflow_started',
        'idx_executions_tenant_env_status_started',
        'idx_executions_tenant_env_failed_started',
        'idx_executions_retention_cleanup',
        'idx_executions_null_started_at',
        'idx_executions_tenant_started_asc',
        'idx_executions_unique_tenant_env_execution'
    ]) AS index_name
),
existing_indexes AS (
    SELECT indexname
    FROM pg_indexes
    WHERE tablename = 'executions'
)
SELECT
    r.index_name,
    CASE
        WHEN e.indexname IS NOT NULL THEN '✓ Present'
        ELSE '✗ MISSING'
    END AS status
FROM required_indexes r
LEFT JOIN existing_indexes e ON r.index_name = e.indexname
ORDER BY r.index_name;

\echo ''

-- ============================================================================
-- 3. Index size report
-- ============================================================================

\echo '3. INDEX SIZE REPORT'
\echo '----------------------------------------'

SELECT
    indexname AS "Index Name",
    pg_size_pretty(pg_relation_size(indexrelid)) AS "Size",
    idx_scan AS "Scans",
    idx_tup_read AS "Tuples Read",
    idx_tup_fetch AS "Tuples Fetched",
    CASE
        WHEN idx_scan = 0 THEN '⚠ Never used'
        WHEN idx_scan < 100 THEN '⚠ Rarely used'
        ELSE '✓ Active'
    END AS "Usage Status"
FROM pg_stat_user_indexes
WHERE tablename = 'executions'
ORDER BY pg_relation_size(indexrelid) DESC;

\echo ''

-- ============================================================================
-- 4. Table statistics
-- ============================================================================

\echo '4. TABLE STATISTICS'
\echo '----------------------------------------'

SELECT
    schemaname AS "Schema",
    tablename AS "Table",
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS "Total Size",
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS "Table Size",
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS "Indexes Size",
    n_live_tup AS "Live Rows",
    n_dead_tup AS "Dead Rows",
    CASE
        WHEN n_live_tup > 0
        THEN ROUND(100.0 * n_dead_tup / n_live_tup, 2)
        ELSE 0
    END AS "Dead Row %",
    last_vacuum AS "Last Vacuum",
    last_analyze AS "Last Analyze"
FROM pg_stat_user_tables
WHERE tablename = 'executions';

\echo ''

-- ============================================================================
-- 5. Index bloat check (approximate)
-- ============================================================================

\echo '5. INDEX BLOAT CHECK (Approximate)'
\echo '----------------------------------------'

SELECT
    indexname AS "Index Name",
    pg_size_pretty(pg_relation_size(indexrelid)) AS "Current Size",
    CASE
        WHEN pg_relation_size(indexrelid) > 100 * 1024 * 1024 -- > 100MB
        THEN '⚠ Large index - monitor for bloat'
        ELSE '✓ Size OK'
    END AS "Bloat Status",
    CASE
        WHEN idx_scan = 0 THEN '⚠ Consider dropping (never used)'
        ELSE '✓ In use'
    END AS "Usage Recommendation"
FROM pg_stat_user_indexes
WHERE tablename = 'executions'
ORDER BY pg_relation_size(indexrelid) DESC;

\echo ''

-- ============================================================================
-- 6. Query planner statistics check
-- ============================================================================

\echo '6. QUERY PLANNER STATISTICS'
\echo '----------------------------------------'

SELECT
    schemaname AS "Schema",
    tablename AS "Table",
    attname AS "Column",
    n_distinct AS "Distinct Values",
    correlation AS "Correlation",
    CASE
        WHEN last_analyze IS NULL THEN '✗ Never analyzed'
        WHEN last_analyze < NOW() - INTERVAL '7 days' THEN '⚠ Stale (>7 days)'
        ELSE '✓ Fresh'
    END AS "Statistics Status"
FROM pg_stats
WHERE tablename = 'executions'
AND attname IN ('tenant_id', 'environment_id', 'workflow_id', 'normalized_status', 'started_at')
ORDER BY attname;

\echo ''

-- ============================================================================
-- 7. Sample query performance test
-- ============================================================================

\echo '7. SAMPLE QUERY PERFORMANCE TEST'
\echo '----------------------------------------'
\echo 'Testing paginated execution query with EXPLAIN...'
\echo ''

-- This will show the query plan without actually executing
-- Replace 'sample-tenant-id' with a real tenant ID for accurate results
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM executions
WHERE tenant_id = (SELECT tenant_id FROM executions LIMIT 1)
AND environment_id = (SELECT environment_id FROM executions LIMIT 1)
ORDER BY started_at DESC
LIMIT 50;

\echo ''

-- ============================================================================
-- 8. Recommendations
-- ============================================================================

\echo '8. MAINTENANCE RECOMMENDATIONS'
\echo '----------------------------------------'

WITH table_stats AS (
    SELECT
        n_dead_tup,
        n_live_tup,
        last_vacuum,
        last_analyze
    FROM pg_stat_user_tables
    WHERE tablename = 'executions'
)
SELECT
    CASE
        WHEN last_vacuum IS NULL OR last_vacuum < NOW() - INTERVAL '7 days'
        THEN '⚠ Run VACUUM ANALYZE executions; (last vacuum: ' || COALESCE(last_vacuum::TEXT, 'never') || ')'
        ELSE '✓ Vacuum is up to date'
    END AS vacuum_recommendation,
    CASE
        WHEN last_analyze IS NULL OR last_analyze < NOW() - INTERVAL '7 days'
        THEN '⚠ Run ANALYZE executions; (last analyze: ' || COALESCE(last_analyze::TEXT, 'never') || ')'
        ELSE '✓ Statistics are up to date'
    END AS analyze_recommendation,
    CASE
        WHEN n_live_tup > 0 AND n_dead_tup::FLOAT / n_live_tup > 0.2
        THEN '⚠ Consider VACUUM (dead row ratio: ' || ROUND(100.0 * n_dead_tup / n_live_tup, 2) || '%)'
        ELSE '✓ Dead row ratio is acceptable'
    END AS dead_row_recommendation
FROM table_stats;

\echo ''
\echo '========================================'
\echo 'VALIDATION COMPLETE'
\echo '========================================'
\echo ''
\echo 'Notes:'
\echo '- ✓ indicates healthy status'
\echo '- ⚠ indicates action may be needed'
\echo '- ✗ indicates error or critical issue'
\echo ''
\echo 'If you see missing indexes, run the migration:'
\echo '  alembic upgrade head'
\echo ''
\echo 'For maintenance recommendations, run suggested commands.'
\echo ''
