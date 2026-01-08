"""add_materialized_views

Revision ID: 20260108_mat_views
Revises: 20260108_rollups
Create Date: 2026-01-08

Adds materialized views for dashboard performance optimization.
These views pre-compute expensive aggregations for fast reads.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260108_mat_views'
down_revision = '20260108_rollups'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create materialized view for workflow performance summary
    # This pre-computes success rates, execution counts, and performance metrics
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS workflow_performance_summary AS
        SELECT
            e.tenant_id,
            e.environment_id,
            e.workflow_id,
            COUNT(*) as total_executions,
            SUM(CASE WHEN e.status = 'success' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN e.status = 'error' THEN 1 ELSE 0 END) as error_count,
            ROUND(
                (SUM(CASE WHEN e.status = 'success' THEN 1 ELSE 0 END)::NUMERIC / 
                NULLIF(COUNT(*), 0)) * 100, 2
            ) as success_rate,
            ROUND(AVG(e.execution_time)::NUMERIC, 2) as avg_duration_ms,
            MIN(e.execution_time) as min_duration_ms,
            MAX(e.execution_time) as max_duration_ms,
            MIN(e.started_at) as first_execution,
            MAX(e.started_at) as last_execution,
            -- Last 24 hours metrics
            SUM(CASE WHEN e.started_at >= NOW() - INTERVAL '24 hours' THEN 1 ELSE 0 END) as executions_24h,
            SUM(CASE WHEN e.started_at >= NOW() - INTERVAL '24 hours' AND e.status = 'error' THEN 1 ELSE 0 END) as errors_24h,
            -- Last 7 days metrics
            SUM(CASE WHEN e.started_at >= NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END) as executions_7d,
            SUM(CASE WHEN e.started_at >= NOW() - INTERVAL '7 days' AND e.status = 'error' THEN 1 ELSE 0 END) as errors_7d
        FROM executions e
        WHERE e.started_at >= NOW() - INTERVAL '30 days'
        GROUP BY e.tenant_id, e.environment_id, e.workflow_id;
    """)

    # Create unique index for efficient refresh
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_performance_summary_pk
        ON workflow_performance_summary(tenant_id, environment_id, workflow_id);
    """)

    # Create indexes for common query patterns
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_workflow_performance_summary_tenant
        ON workflow_performance_summary(tenant_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_workflow_performance_summary_tenant_env
        ON workflow_performance_summary(tenant_id, environment_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_workflow_performance_summary_errors
        ON workflow_performance_summary(tenant_id, errors_24h DESC)
        WHERE errors_24h > 0;
    """)

    # Create function to refresh materialized view
    # Can be called manually or by a scheduled job
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_workflow_performance_summary()
        RETURNS VOID AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY workflow_performance_summary;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Note: tenant_activity_summary removed - depends on tenant_subscriptions which may not exist
    # Can be added later when billing tables are confirmed

    # Create environment health summary view
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS environment_health_summary AS
        SELECT
            env.id as environment_id,
            env.tenant_id,
            env.n8n_name as environment_name,
            env.n8n_type as environment_type,
            env.is_active,
            COUNT(DISTINCT w.id) as workflow_count,
            COUNT(DISTINCT CASE WHEN w.status = 'synced' THEN w.id END) as synced_workflows,
            COUNT(DISTINCT CASE WHEN w.status = 'drifted' THEN w.id END) as drifted_workflows,
            -- Recent executions
            (SELECT COUNT(*) FROM executions ex 
             WHERE ex.environment_id = env.id 
             AND ex.started_at >= NOW() - INTERVAL '24 hours') as executions_24h,
            (SELECT COUNT(*) FROM executions ex 
             WHERE ex.environment_id = env.id 
             AND ex.status = 'error'
             AND ex.started_at >= NOW() - INTERVAL '24 hours') as errors_24h,
            -- Success rate (last 7 days)
            COALESCE(
                (SELECT ROUND(
                    (SUM(CASE WHEN ex.status = 'success' THEN 1 ELSE 0 END)::NUMERIC / 
                     NULLIF(COUNT(*), 0)) * 100, 2
                )
                FROM executions ex 
                WHERE ex.environment_id = env.id 
                AND ex.started_at >= NOW() - INTERVAL '7 days'), 0
            ) as success_rate_7d,
            -- Last sync time
            env.last_sync_at
        FROM environments env
        LEFT JOIN workflow_env_map w ON w.environment_id = env.id AND w.status NOT IN ('deleted', 'missing')
        WHERE env.is_active = true
        GROUP BY env.id, env.tenant_id, env.n8n_name, env.n8n_type, env.is_active, env.last_sync_at;
    """)

    # Create indexes for environment health
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_environment_health_summary_pk
        ON environment_health_summary(environment_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_environment_health_summary_tenant
        ON environment_health_summary(tenant_id);
    """)

    # Create function to refresh environment health
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_environment_health_summary()
        RETURNS VOID AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY environment_health_summary;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create a master refresh function that refreshes all views
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_all_materialized_views()
        RETURNS TABLE(view_name TEXT, refresh_time INTERVAL) AS $$
        DECLARE
            start_time TIMESTAMPTZ;
            end_time TIMESTAMPTZ;
        BEGIN
            -- Refresh workflow performance summary
            start_time := clock_timestamp();
            PERFORM refresh_workflow_performance_summary();
            end_time := clock_timestamp();
            view_name := 'workflow_performance_summary';
            refresh_time := end_time - start_time;
            RETURN NEXT;
            
            -- Refresh environment health summary
            start_time := clock_timestamp();
            PERFORM refresh_environment_health_summary();
            end_time := clock_timestamp();
            view_name := 'environment_health_summary';
            refresh_time := end_time - start_time;
            RETURN NEXT;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS refresh_all_materialized_views();")
    op.execute("DROP FUNCTION IF EXISTS refresh_environment_health_summary();")
    op.execute("DROP INDEX IF EXISTS idx_environment_health_summary_tenant;")
    op.execute("DROP INDEX IF EXISTS idx_environment_health_summary_pk;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS environment_health_summary;")
    op.execute("DROP FUNCTION IF EXISTS refresh_workflow_performance_summary();")
    op.execute("DROP INDEX IF EXISTS idx_workflow_performance_summary_errors;")
    op.execute("DROP INDEX IF EXISTS idx_workflow_performance_summary_tenant_env;")
    op.execute("DROP INDEX IF EXISTS idx_workflow_performance_summary_tenant;")
    op.execute("DROP INDEX IF EXISTS idx_workflow_performance_summary_pk;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS workflow_performance_summary;")

