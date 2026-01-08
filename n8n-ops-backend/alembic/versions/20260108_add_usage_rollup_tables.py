"""add_usage_rollup_tables

Revision ID: 20260108_rollups
Revises: 20260108_error_class
Create Date: 2026-01-08

Adds rollup tables for pre-computed analytics.
Background jobs populate these tables daily for faster dashboard loads.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260108_rollups'
down_revision = '20260108_error_class'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create daily execution rollup table
    op.execute("""
        CREATE TABLE IF NOT EXISTS execution_rollups_daily (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            environment_id UUID,
            workflow_id TEXT,
            rollup_date DATE NOT NULL,
            total_executions INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            error_count INTEGER NOT NULL DEFAULT 0,
            running_count INTEGER NOT NULL DEFAULT 0,
            avg_duration_ms DOUBLE PRECISION,
            min_duration_ms INTEGER,
            max_duration_ms INTEGER,
            p50_duration_ms INTEGER,
            p95_duration_ms INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(tenant_id, environment_id, workflow_id, rollup_date)
        );
    """)

    # Create indexes for efficient queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_execution_rollups_tenant_date
        ON execution_rollups_daily(tenant_id, rollup_date DESC);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_execution_rollups_tenant_env_date
        ON execution_rollups_daily(tenant_id, environment_id, rollup_date DESC);
    """)

    # Create function to compute daily rollup for a specific date
    op.execute("""
        CREATE OR REPLACE FUNCTION compute_execution_rollup_for_date(
            p_rollup_date DATE,
            p_tenant_id UUID DEFAULT NULL
        )
        RETURNS INTEGER AS $$
        DECLARE
            rows_inserted INTEGER;
        BEGIN
            -- Insert or update rollups for the specified date
            INSERT INTO execution_rollups_daily (
                tenant_id,
                environment_id,
                workflow_id,
                rollup_date,
                total_executions,
                success_count,
                error_count,
                running_count,
                avg_duration_ms,
                min_duration_ms,
                max_duration_ms,
                p50_duration_ms,
                p95_duration_ms
            )
            SELECT
                e.tenant_id,
                e.environment_id,
                e.workflow_id,
                p_rollup_date as rollup_date,
                COUNT(*) as total_executions,
                SUM(CASE WHEN e.status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN e.status = 'error' THEN 1 ELSE 0 END) as error_count,
                SUM(CASE WHEN e.status = 'running' THEN 1 ELSE 0 END) as running_count,
                AVG(e.execution_time)::DOUBLE PRECISION as avg_duration_ms,
                MIN(e.execution_time)::INTEGER as min_duration_ms,
                MAX(e.execution_time)::INTEGER as max_duration_ms,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY e.execution_time)::INTEGER as p50_duration_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY e.execution_time)::INTEGER as p95_duration_ms
            FROM executions e
            WHERE DATE(e.started_at) = p_rollup_date
              AND (p_tenant_id IS NULL OR e.tenant_id = p_tenant_id)
            GROUP BY e.tenant_id, e.environment_id, e.workflow_id
            ON CONFLICT (tenant_id, environment_id, workflow_id, rollup_date)
            DO UPDATE SET
                total_executions = EXCLUDED.total_executions,
                success_count = EXCLUDED.success_count,
                error_count = EXCLUDED.error_count,
                running_count = EXCLUDED.running_count,
                avg_duration_ms = EXCLUDED.avg_duration_ms,
                min_duration_ms = EXCLUDED.min_duration_ms,
                max_duration_ms = EXCLUDED.max_duration_ms,
                p50_duration_ms = EXCLUDED.p50_duration_ms,
                p95_duration_ms = EXCLUDED.p95_duration_ms,
                updated_at = NOW();
            
            GET DIAGNOSTICS rows_inserted = ROW_COUNT;
            RETURN rows_inserted;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create function to get rollup data for a date range
    op.execute("""
        CREATE OR REPLACE FUNCTION get_execution_rollups(
            p_tenant_id UUID,
            p_start_date DATE,
            p_end_date DATE,
            p_environment_id UUID DEFAULT NULL,
            p_workflow_id TEXT DEFAULT NULL
        )
        RETURNS TABLE(
            rollup_date DATE,
            total_executions BIGINT,
            success_count BIGINT,
            error_count BIGINT,
            avg_duration_ms DOUBLE PRECISION,
            success_rate DOUBLE PRECISION
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                r.rollup_date,
                SUM(r.total_executions)::BIGINT as total_executions,
                SUM(r.success_count)::BIGINT as success_count,
                SUM(r.error_count)::BIGINT as error_count,
                AVG(r.avg_duration_ms) as avg_duration_ms,
                CASE 
                    WHEN SUM(r.total_executions) > 0 
                    THEN (SUM(r.success_count)::DOUBLE PRECISION / SUM(r.total_executions)) * 100
                    ELSE 0 
                END as success_rate
            FROM execution_rollups_daily r
            WHERE r.tenant_id = p_tenant_id
              AND r.rollup_date >= p_start_date
              AND r.rollup_date <= p_end_date
              AND (p_environment_id IS NULL OR r.environment_id = p_environment_id)
              AND (p_workflow_id IS NULL OR r.workflow_id = p_workflow_id)
            GROUP BY r.rollup_date
            ORDER BY r.rollup_date;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS get_execution_rollups(UUID, DATE, DATE, UUID, TEXT);")
    op.execute("DROP FUNCTION IF EXISTS compute_execution_rollup_for_date(DATE, UUID);")
    op.execute("DROP INDEX IF EXISTS idx_execution_rollups_tenant_env_date;")
    op.execute("DROP INDEX IF EXISTS idx_execution_rollups_tenant_date;")
    op.execute("DROP TABLE IF EXISTS execution_rollups_daily;")

