"""fix materialized view ambiguous column reference

Revision ID: 20260112_fix_mv_ambiguous
Revises: 20260108_mv_tracking
Create Date: 2026-01-12

Fixes ambiguous column reference 'view_name' in get_materialized_view_refresh_status function.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260112_fix_mv_ambiguous'
down_revision = '20260111_diff_state_cols'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop and recreate the function with proper column qualifications
    op.execute("DROP FUNCTION IF EXISTS get_materialized_view_refresh_status();")

    op.execute("""
        CREATE OR REPLACE FUNCTION get_materialized_view_refresh_status()
        RETURNS TABLE(
            view_name TEXT,
            last_refresh_started_at TIMESTAMPTZ,
            last_refresh_completed_at TIMESTAMPTZ,
            last_status TEXT,
            last_error_message TEXT,
            last_refresh_duration_ms INTEGER,
            last_row_count BIGINT,
            minutes_since_last_refresh NUMERIC,
            is_stale BOOLEAN,
            consecutive_failures INTEGER
        ) AS $$
        BEGIN
            RETURN QUERY
            WITH latest_refreshes AS (
                SELECT DISTINCT ON (log1.view_name)
                    log1.view_name as lr_view_name,
                    log1.refresh_started_at as lr_refresh_started_at,
                    log1.refresh_completed_at as lr_refresh_completed_at,
                    log1.status as lr_status,
                    log1.error_message as lr_error_message,
                    log1.refresh_duration_ms as lr_refresh_duration_ms,
                    log1.row_count as lr_row_count,
                    EXTRACT(EPOCH FROM (NOW() - log1.refresh_started_at)) / 60 as lr_minutes_since,
                    -- Consider stale if no successful refresh in last 2 hours (120 minutes)
                    CASE
                        WHEN log1.status = 'success' AND
                             EXTRACT(EPOCH FROM (NOW() - log1.refresh_completed_at)) / 60 > 120
                        THEN TRUE
                        WHEN log1.status = 'failed'
                        THEN TRUE
                        ELSE FALSE
                    END as lr_is_stale
                FROM materialized_view_refresh_log log1
                ORDER BY log1.view_name, log1.refresh_started_at DESC
            ),
            failure_counts AS (
                SELECT
                    log2.view_name as fc_view_name,
                    COUNT(*) as fc_consecutive_failures
                FROM materialized_view_refresh_log log2
                INNER JOIN (
                    SELECT DISTINCT ON (log3.view_name)
                        log3.view_name as latest_view_name,
                        log3.refresh_started_at as latest_refresh_started_at
                    FROM materialized_view_refresh_log log3
                    ORDER BY log3.view_name, log3.refresh_started_at DESC
                ) latest_per_view ON log2.view_name = latest_per_view.latest_view_name
                WHERE log2.refresh_started_at >= COALESCE(
                    (
                        SELECT log4.refresh_started_at
                        FROM materialized_view_refresh_log log4
                        WHERE log4.view_name = log2.view_name
                          AND log4.status = 'success'
                          AND log4.refresh_started_at <= latest_per_view.latest_refresh_started_at
                        ORDER BY log4.refresh_started_at DESC
                        LIMIT 1
                    ),
                    latest_per_view.latest_refresh_started_at
                )
                AND log2.status = 'failed'
                GROUP BY log2.view_name
            )
            SELECT
                lr.lr_view_name::TEXT,
                lr.lr_refresh_started_at,
                lr.lr_refresh_completed_at,
                lr.lr_status,
                lr.lr_error_message,
                lr.lr_refresh_duration_ms,
                lr.lr_row_count,
                lr.lr_minutes_since::NUMERIC(10,2),
                lr.lr_is_stale,
                COALESCE(fc.fc_consecutive_failures, 0)::INTEGER
            FROM latest_refreshes lr
            LEFT JOIN failure_counts fc ON lr.lr_view_name = fc.fc_view_name;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    # Revert to the original version from 20260108_mv_tracking
    op.execute("DROP FUNCTION IF EXISTS get_materialized_view_refresh_status();")

    op.execute("""
        CREATE OR REPLACE FUNCTION get_materialized_view_refresh_status()
        RETURNS TABLE(
            view_name TEXT,
            last_refresh_started_at TIMESTAMPTZ,
            last_refresh_completed_at TIMESTAMPTZ,
            last_status TEXT,
            last_error_message TEXT,
            last_refresh_duration_ms INTEGER,
            last_row_count BIGINT,
            minutes_since_last_refresh NUMERIC,
            is_stale BOOLEAN,
            consecutive_failures INTEGER
        ) AS $$
        BEGIN
            RETURN QUERY
            WITH latest_refreshes AS (
                SELECT DISTINCT ON (mvrl.view_name)
                    mvrl.view_name as lr_view_name,
                    mvrl.refresh_started_at,
                    mvrl.refresh_completed_at,
                    mvrl.status,
                    mvrl.error_message,
                    mvrl.refresh_duration_ms,
                    mvrl.row_count,
                    EXTRACT(EPOCH FROM (NOW() - mvrl.refresh_started_at)) / 60 as minutes_since,
                    -- Consider stale if no successful refresh in last 2 hours (120 minutes)
                    CASE
                        WHEN mvrl.status = 'success' AND
                             EXTRACT(EPOCH FROM (NOW() - mvrl.refresh_completed_at)) / 60 > 120
                        THEN TRUE
                        WHEN mvrl.status = 'failed'
                        THEN TRUE
                        ELSE FALSE
                    END as is_stale
                FROM materialized_view_refresh_log mvrl
                ORDER BY mvrl.view_name, mvrl.refresh_started_at DESC
            ),
            failure_counts AS (
                SELECT
                    mvrl.view_name as fc_view_name,
                    COUNT(*) as consecutive_failures
                FROM materialized_view_refresh_log mvrl
                INNER JOIN (
                    SELECT DISTINCT ON (mvrl2.view_name)
                        mvrl2.view_name,
                        mvrl2.refresh_started_at
                    FROM materialized_view_refresh_log mvrl2
                    ORDER BY mvrl2.view_name, mvrl2.refresh_started_at DESC
                ) latest ON mvrl.view_name = latest.view_name
                WHERE mvrl.refresh_started_at >= (
                    SELECT MIN(mvrl3.refresh_started_at)
                    FROM materialized_view_refresh_log mvrl3
                    WHERE mvrl3.view_name = mvrl.view_name
                      AND mvrl3.status = 'success'
                      AND mvrl3.refresh_started_at <= latest.refresh_started_at
                    ORDER BY mvrl3.refresh_started_at DESC
                    LIMIT 1
                )
                AND mvrl.status = 'failed'
                GROUP BY mvrl.view_name
            )
            SELECT
                lr.lr_view_name,
                lr.refresh_started_at,
                lr.refresh_completed_at,
                lr.status,
                lr.error_message,
                lr.refresh_duration_ms,
                lr.row_count,
                lr.minutes_since::NUMERIC(10,2),
                lr.is_stale,
                COALESCE(fc.consecutive_failures, 0)::INTEGER
            FROM latest_refreshes lr
            LEFT JOIN failure_counts fc ON lr.lr_view_name = fc.fc_view_name;
        END;
        $$ LANGUAGE plpgsql;
    """)
