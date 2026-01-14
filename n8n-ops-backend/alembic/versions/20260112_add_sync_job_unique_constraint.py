"""Add partial unique constraint to prevent duplicate sync jobs

Revision ID: 20260112_sync_unique
Revises: 20260112_fix_mv_ambiguous
Create Date: 2026-01-12

This migration adds a partial unique constraint on background_jobs to prevent
duplicate sync jobs for the same environment. The constraint only applies to
jobs with status 'pending' or 'running'.

Key design:
- Partial unique index: (resource_id, job_type) WHERE status IN ('pending', 'running')
- Only applies to environment sync jobs
- Allows multiple completed/failed jobs for same environment
- Race-safe: enforced at DB level
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260112_sync_unique'
down_revision = '20260112_fix_mv_ambiguous'
branch_labels = None
depends_on = None


def upgrade():
    # Create partial unique index to prevent duplicate active sync jobs
    # This ensures only ONE sync job can be pending or running for a given environment
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_background_jobs_active_sync_unique
        ON background_jobs (resource_id, job_type)
        WHERE resource_type = 'environment'
          AND job_type IN ('canonical_env_sync', 'canonical_repo_sync', 'environment_sync')
          AND status IN ('pending', 'running')
    """)

    # Also add an index for faster lookups of active jobs by environment
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_background_jobs_active_by_env
        ON background_jobs (tenant_id, resource_id, job_type, status)
        WHERE resource_type = 'environment'
          AND status IN ('pending', 'running')
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_background_jobs_active_sync_unique")
    op.execute("DROP INDEX IF EXISTS idx_background_jobs_active_by_env")
