"""add_execution_counts_function

Revision ID: 20260108_exec_counts
Revises: 855f0d7fe1de
Create Date: 2026-01-08

Adds PostgreSQL function for efficient execution count aggregation.
This replaces client-side counting with database-level GROUP BY.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260108_exec_counts'
down_revision = '855f0d7fe1de'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create PostgreSQL function for execution counts aggregation
    # This uses GROUP BY at the database level instead of client-side counting
    op.execute("""
        CREATE OR REPLACE FUNCTION get_execution_counts_by_workflow(
            p_tenant_id UUID,
            p_environment_id UUID
        )
        RETURNS TABLE(workflow_id TEXT, execution_count BIGINT) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                e.workflow_id::TEXT,
                COUNT(*)::BIGINT as execution_count
            FROM executions e
            WHERE e.tenant_id = p_tenant_id
              AND e.environment_id = p_environment_id
            GROUP BY e.workflow_id;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """)

    # Add index to support the function if not already present
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_executions_tenant_env_workflow
        ON executions(tenant_id, environment_id, workflow_id);
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS get_execution_counts_by_workflow(UUID, UUID);")
    op.execute("DROP INDEX IF EXISTS idx_executions_tenant_env_workflow;")

