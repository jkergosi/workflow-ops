"""add_workflow_diff_state_columns

Revision ID: 20260111_diff_state_cols
Revises: 20260108_sparkline_agg
Create Date: 2026-01-11

Adds missing columns to workflow_diff_state table for incremental diff computation:
- source_git_hash: Hash of source environment Git state
- target_git_hash: Hash of target environment Git state
- source_env_hash: Hash of source environment content
- target_env_hash: Hash of target environment content
- conflict_metadata: JSONB metadata for conflict resolution

Also updates the diff_status check constraint to include 'conflict' status.
"""
from alembic import op

revision = '20260111_diff_state_cols'
down_revision = '20260108_sparkline_agg'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns to workflow_diff_state
    op.execute("""
        ALTER TABLE workflow_diff_state
        ADD COLUMN IF NOT EXISTS source_git_hash TEXT NULL;
    """)

    op.execute("""
        ALTER TABLE workflow_diff_state
        ADD COLUMN IF NOT EXISTS target_git_hash TEXT NULL;
    """)

    op.execute("""
        ALTER TABLE workflow_diff_state
        ADD COLUMN IF NOT EXISTS source_env_hash TEXT NULL;
    """)

    op.execute("""
        ALTER TABLE workflow_diff_state
        ADD COLUMN IF NOT EXISTS target_env_hash TEXT NULL;
    """)

    op.execute("""
        ALTER TABLE workflow_diff_state
        ADD COLUMN IF NOT EXISTS conflict_metadata JSONB NULL;
    """)

    # Drop the old check constraint and create a new one that includes 'conflict'
    op.execute("""
        ALTER TABLE workflow_diff_state
        DROP CONSTRAINT IF EXISTS workflow_diff_state_diff_status_check;
    """)

    op.execute("""
        ALTER TABLE workflow_diff_state
        ADD CONSTRAINT workflow_diff_state_diff_status_check
        CHECK (diff_status IN ('unchanged', 'modified', 'added', 'target_only', 'target_hotfix', 'conflict'));
    """)

    # Add index for conflict detection queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_workflow_diff_state_conflict
        ON workflow_diff_state(diff_status)
        WHERE diff_status = 'conflict';
    """)


def downgrade() -> None:
    # Drop the conflict index
    op.execute("DROP INDEX IF EXISTS idx_workflow_diff_state_conflict;")

    # Revert check constraint to original
    op.execute("""
        ALTER TABLE workflow_diff_state
        DROP CONSTRAINT IF EXISTS workflow_diff_state_diff_status_check;
    """)

    op.execute("""
        ALTER TABLE workflow_diff_state
        ADD CONSTRAINT workflow_diff_state_diff_status_check
        CHECK (diff_status IN ('unchanged', 'modified', 'added', 'target_only', 'target_hotfix'));
    """)

    # Drop added columns
    op.execute("ALTER TABLE workflow_diff_state DROP COLUMN IF EXISTS conflict_metadata;")
    op.execute("ALTER TABLE workflow_diff_state DROP COLUMN IF EXISTS target_env_hash;")
    op.execute("ALTER TABLE workflow_diff_state DROP COLUMN IF EXISTS source_env_hash;")
    op.execute("ALTER TABLE workflow_diff_state DROP COLUMN IF EXISTS target_git_hash;")
    op.execute("ALTER TABLE workflow_diff_state DROP COLUMN IF EXISTS source_git_hash;")
