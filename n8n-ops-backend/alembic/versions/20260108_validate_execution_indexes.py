"""validate_execution_indexes

Revision ID: 20260108_validate_indexes
Revises: 20260108_retention
Create Date: 2026-01-08

Validates and creates all critical indexes for executions table performance.
This migration ensures query performance for large-scale tenants (100k+ executions).

Key indexes validated/created:
1. Paginated listing indexes (ExecutionsPage)
2. Analytics aggregation indexes (ObservabilityPage)
3. Retention cleanup indexes (automated lifecycle)
4. Per-workflow analytics indexes
5. Error tracking indexes
6. Unique constraint for idempotent ingestion

All indexes use IF NOT EXISTS to be idempotent with previous migrations.
This migration consolidates index validation in one place for auditing.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260108_validate_indexes'
down_revision = '20260108_retention'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Validate and create all critical indexes for executions table.

    This migration is idempotent - all indexes use IF NOT EXISTS.
    Some indexes may already exist from previous migrations (20260107_182000, 20260108_retention).
    This consolidates all execution indexes in one migration for validation and documentation.
    """

    # ============================================================================
    # 1. TENANT + ENVIRONMENT INDEXES - Core query patterns
    # ============================================================================

    # Index for paginated execution listing (most common query)
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_executions_tenant_env_started
        ON executions(tenant_id, environment_id, started_at DESC)
        WHERE started_at IS NOT NULL;
    ''')

    op.execute('''
        COMMENT ON INDEX idx_executions_tenant_env_started IS
        'Optimizes paginated execution listing in ExecutionsPage. Covers tenant + environment filtering with started_at DESC sort.';
    ''')

    # Index for per-workflow filtering
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_executions_tenant_env_workflow_started
        ON executions(tenant_id, environment_id, workflow_id, started_at DESC)
        WHERE started_at IS NOT NULL;
    ''')

    op.execute('''
        COMMENT ON INDEX idx_executions_tenant_env_workflow_started IS
        'Optimizes workflow-filtered execution queries. Enables O(log n) lookup for workflow-specific execution history.';
    ''')

    # Index for status filtering
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_executions_tenant_env_status_started
        ON executions(tenant_id, environment_id, normalized_status, started_at DESC)
        WHERE normalized_status IS NOT NULL AND started_at IS NOT NULL;
    ''')

    op.execute('''
        COMMENT ON INDEX idx_executions_tenant_env_status_started IS
        'Optimizes status-filtered queries (e.g., show only errors). Partial index excludes NULL normalized_status.';
    ''')

    # Partial index for failed executions
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_executions_tenant_env_failed_started
        ON executions(tenant_id, environment_id, started_at DESC)
        WHERE normalized_status = 'error';
    ''')

    op.execute('''
        COMMENT ON INDEX idx_executions_tenant_env_failed_started IS
        'Highly selective partial index for failed executions only. Makes Recent Failures queries extremely fast.';
    ''')

    # ============================================================================
    # 2. RETENTION CLEANUP INDEXES
    # ============================================================================

    # Index for time-based retention cleanup
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_executions_retention_cleanup
        ON executions(tenant_id, started_at)
        WHERE started_at IS NOT NULL;
    ''')

    op.execute('''
        COMMENT ON INDEX idx_executions_retention_cleanup IS
        'Optimizes retention cleanup queries. Enables fast batch deletion of old executions.';
    ''')

    # Index for incomplete executions cleanup
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_executions_null_started_at
        ON executions(tenant_id, created_at)
        WHERE started_at IS NULL;
    ''')

    op.execute('''
        COMMENT ON INDEX idx_executions_null_started_at IS
        'Handles cleanup of stale executions that never properly started (started_at IS NULL).';
    ''')

    # ============================================================================
    # 3. ANALYTICS INDEXES
    # ============================================================================

    # Index for time-range analytics (sparkline queries)
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_executions_tenant_started_asc
        ON executions(tenant_id, started_at ASC)
        WHERE started_at IS NOT NULL;
    ''')

    op.execute('''
        COMMENT ON INDEX idx_executions_tenant_started_asc IS
        'Optimizes time-range analytics queries for sparkline data. ASC ordering matches bucketing logic.';
    ''')

    # ============================================================================
    # 4. UNIQUE CONSTRAINT FOR IDEMPOTENT INGESTION
    # ============================================================================

    # Unique constraint to prevent duplicate execution ingestion
    op.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_executions_unique_tenant_env_execution
        ON executions(tenant_id, environment_id, execution_id)
        WHERE execution_id IS NOT NULL;
    ''')

    op.execute('''
        COMMENT ON INDEX idx_executions_unique_tenant_env_execution IS
        'Ensures idempotent execution ingestion. Prevents duplicates and optimizes upsert operations.';
    ''')

    # ============================================================================
    # 5. UPDATE TABLE COMMENT WITH MAINTENANCE NOTES
    # ============================================================================

    op.execute('''
        COMMENT ON TABLE executions IS
        'Execution history table. Indexes optimized for paginated listing, analytics, retention cleanup, and error tracking.

MAINTENANCE: Run VACUUM ANALYZE weekly. Monitor index bloat. Retention policy (90 days default) keeps size bounded.';
    ''')

    # ============================================================================
    # 6. VALIDATION REPORT
    # ============================================================================

    # Print validation report during migration
    op.execute('''
        DO $$
        DECLARE
            index_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO index_count
            FROM pg_indexes
            WHERE tablename = 'executions';

            RAISE NOTICE '========================================';
            RAISE NOTICE 'Execution Indexes Validated: % indexes', index_count;
            RAISE NOTICE '========================================';
        END $$;
    ''')


def downgrade() -> None:
    """
    Rollback migration by dropping indexes.

    WARNING: This will severely degrade query performance.
    Only use in development/testing environments.
    """

    # Remove comments
    op.execute('COMMENT ON TABLE executions IS NULL;')

    # Drop indexes in reverse order
    op.execute('DROP INDEX IF EXISTS idx_executions_unique_tenant_env_execution;')
    op.execute('DROP INDEX IF EXISTS idx_executions_tenant_started_asc;')
    op.execute('DROP INDEX IF EXISTS idx_executions_null_started_at;')
    op.execute('DROP INDEX IF EXISTS idx_executions_retention_cleanup;')
    op.execute('DROP INDEX IF EXISTS idx_executions_tenant_env_failed_started;')
    op.execute('DROP INDEX IF EXISTS idx_executions_tenant_env_status_started;')
    op.execute('DROP INDEX IF EXISTS idx_executions_tenant_env_workflow_started;')
    op.execute('DROP INDEX IF EXISTS idx_executions_tenant_env_started;')
