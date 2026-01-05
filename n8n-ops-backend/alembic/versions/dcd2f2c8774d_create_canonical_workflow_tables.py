"""create_canonical_workflow_tables

Revision ID: dcd2f2c8774d
Revises: '245ecb3e319b'
Create Date: 2026-01-05 16:34:03

Creates canonical workflow system tables and removes legacy workflows table.
Migration: dcd2f2c8774d - Canonical workflow identity system
See: reqs/canonical_CURSOR_FINAL.md
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'dcd2f2c8774d'
down_revision = '245ecb3e319b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgcrypto extension for gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto;')
    
    # Add canonical workflow columns to tenants table
    op.execute('''
        ALTER TABLE tenants 
        ADD COLUMN IF NOT EXISTS canonical_anchor_environment_id UUID 
        REFERENCES environments(id) ON DELETE SET NULL;
    ''')
    op.execute('''
        ALTER TABLE tenants 
        ADD COLUMN IF NOT EXISTS canonical_onboarded_at TIMESTAMPTZ NULL;
    ''')
    op.execute('''
        ALTER TABLE tenants 
        ADD COLUMN IF NOT EXISTS canonical_onboarding_version INTEGER NULL;
    ''')
    
    # Add git_folder to environments table
    op.execute('''
        ALTER TABLE environments 
        ADD COLUMN IF NOT EXISTS git_folder TEXT NULL;
    ''')
    
    # Create canonical_workflows table (identity only)
    op.execute('''
        CREATE TABLE IF NOT EXISTS canonical_workflows (
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            canonical_id UUID NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by_user_id UUID NULL,
            display_name TEXT NULL,
            deleted_at TIMESTAMPTZ NULL,
            PRIMARY KEY (tenant_id, canonical_id)
        );
    ''')
    
    # Create canonical_workflow_git_state table (per-environment Git state)
    op.execute('''
        CREATE TABLE IF NOT EXISTS canonical_workflow_git_state (
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
            canonical_id UUID NOT NULL,
            git_path TEXT NOT NULL,
            git_commit_sha TEXT NULL,
            git_content_hash TEXT NOT NULL,
            last_repo_sync_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, environment_id, canonical_id),
            FOREIGN KEY (tenant_id, canonical_id) 
                REFERENCES canonical_workflows(tenant_id, canonical_id) 
                ON DELETE CASCADE
        );
    ''')
    
    # Create workflow_env_map table (environment mappings)
    op.execute('''
        CREATE TABLE IF NOT EXISTS workflow_env_map (
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
            canonical_id UUID NOT NULL,
            n8n_workflow_id TEXT NULL,
            env_content_hash TEXT NOT NULL,
            last_env_sync_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            linked_at TIMESTAMPTZ NULL,
            linked_by_user_id UUID NULL,
            status TEXT NULL CHECK (status IN ('linked', 'ignored', 'deleted')),
            PRIMARY KEY (tenant_id, environment_id, canonical_id),
            FOREIGN KEY (tenant_id, canonical_id) 
                REFERENCES canonical_workflows(tenant_id, canonical_id) 
                ON DELETE CASCADE
        );
    ''')
    
    # Create workflow_link_suggestions table
    op.execute('''
        CREATE TABLE IF NOT EXISTS workflow_link_suggestions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
            n8n_workflow_id TEXT NOT NULL,
            canonical_id UUID NOT NULL,
            score NUMERIC NOT NULL,
            reason TEXT NULL,
            status TEXT NOT NULL DEFAULT 'open' 
                CHECK (status IN ('open', 'accepted', 'rejected', 'expired')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ NULL,
            resolved_by_user_id UUID NULL,
            FOREIGN KEY (tenant_id, canonical_id) 
                REFERENCES canonical_workflows(tenant_id, canonical_id) 
                ON DELETE CASCADE,
            UNIQUE(tenant_id, environment_id, n8n_workflow_id, canonical_id)
        );
    ''')
    
    # Create workflow_diff_state table
    op.execute('''
        CREATE TABLE IF NOT EXISTS workflow_diff_state (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            source_env_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
            target_env_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
            canonical_id UUID NOT NULL,
            diff_status TEXT NOT NULL 
                CHECK (diff_status IN ('unchanged', 'modified', 'added', 'target_only', 'target_hotfix')),
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, canonical_id) 
                REFERENCES canonical_workflows(tenant_id, canonical_id) 
                ON DELETE CASCADE,
            UNIQUE(tenant_id, source_env_id, target_env_id, canonical_id)
        );
    ''')
    
    # Create indexes for canonical_workflows
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_canonical_workflows_tenant 
        ON canonical_workflows(tenant_id);
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_canonical_workflows_created_at 
        ON canonical_workflows(created_at DESC);
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_canonical_workflows_deleted_at 
        ON canonical_workflows(deleted_at) WHERE deleted_at IS NOT NULL;
    ''')
    
    # Create indexes for canonical_workflow_git_state
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_canonical_git_state_tenant_env 
        ON canonical_workflow_git_state(tenant_id, environment_id);
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_canonical_git_state_canonical 
        ON canonical_workflow_git_state(canonical_id);
    ''')
    
    # Create indexes for workflow_env_map
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_env_map_tenant_env 
        ON workflow_env_map(tenant_id, environment_id);
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_env_map_canonical 
        ON workflow_env_map(canonical_id);
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_env_map_n8n_id 
        ON workflow_env_map(n8n_workflow_id) 
        WHERE n8n_workflow_id IS NOT NULL;
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_env_map_status 
        ON workflow_env_map(status) 
        WHERE status IS NOT NULL;
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_env_map_last_sync 
        ON workflow_env_map(last_env_sync_at DESC);
    ''')
    
    # Create indexes for workflow_link_suggestions
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_link_suggestions_tenant_env 
        ON workflow_link_suggestions(tenant_id, environment_id);
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_link_suggestions_status 
        ON workflow_link_suggestions(status) 
        WHERE status = 'open';
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_link_suggestions_created 
        ON workflow_link_suggestions(created_at DESC);
    ''')
    
    # Create indexes for workflow_diff_state
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_diff_state_tenant_envs 
        ON workflow_diff_state(tenant_id, source_env_id, target_env_id);
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_diff_state_canonical 
        ON workflow_diff_state(canonical_id);
    ''')
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_workflow_diff_state_computed 
        ON workflow_diff_state(computed_at DESC);
    ''')
    
    # Enable Row Level Security and create policies
    op.execute('ALTER TABLE canonical_workflows ENABLE ROW LEVEL SECURITY;')
    op.execute('''
        CREATE POLICY canonical_workflows_tenant_isolation 
        ON canonical_workflows 
        FOR ALL 
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid) 
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    ''')
    
    op.execute('ALTER TABLE canonical_workflow_git_state ENABLE ROW LEVEL SECURITY;')
    op.execute('''
        CREATE POLICY canonical_git_state_tenant_isolation 
        ON canonical_workflow_git_state 
        FOR ALL 
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid) 
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    ''')
    
    op.execute('ALTER TABLE workflow_env_map ENABLE ROW LEVEL SECURITY;')
    op.execute('''
        CREATE POLICY workflow_env_map_tenant_isolation 
        ON workflow_env_map 
        FOR ALL 
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid) 
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    ''')
    
    op.execute('ALTER TABLE workflow_link_suggestions ENABLE ROW LEVEL SECURITY;')
    op.execute('''
        CREATE POLICY workflow_link_suggestions_tenant_isolation 
        ON workflow_link_suggestions 
        FOR ALL 
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid) 
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    ''')
    
    op.execute('ALTER TABLE workflow_diff_state ENABLE ROW LEVEL SECURITY;')
    op.execute('''
        CREATE POLICY workflow_diff_state_tenant_isolation 
        ON workflow_diff_state 
        FOR ALL 
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid) 
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
    ''')
    
    # Remove legacy workflows table (full replacement, no coexistence)
    op.execute('DROP TABLE IF EXISTS workflows CASCADE;')


def downgrade() -> None:
    # Drop RLS policies
    op.execute('DROP POLICY IF EXISTS workflow_diff_state_tenant_isolation ON workflow_diff_state;')
    op.execute('DROP POLICY IF EXISTS workflow_link_suggestions_tenant_isolation ON workflow_link_suggestions;')
    op.execute('DROP POLICY IF EXISTS workflow_env_map_tenant_isolation ON workflow_env_map;')
    op.execute('DROP POLICY IF EXISTS canonical_git_state_tenant_isolation ON canonical_workflow_git_state;')
    op.execute('DROP POLICY IF EXISTS canonical_workflows_tenant_isolation ON canonical_workflows;')
    
    # Drop tables (in reverse order due to foreign keys)
    op.execute('DROP TABLE IF EXISTS workflow_diff_state CASCADE;')
    op.execute('DROP TABLE IF EXISTS workflow_link_suggestions CASCADE;')
    op.execute('DROP TABLE IF EXISTS workflow_env_map CASCADE;')
    op.execute('DROP TABLE IF EXISTS canonical_workflow_git_state CASCADE;')
    op.execute('DROP TABLE IF EXISTS canonical_workflows CASCADE;')
    
    # Remove columns from tenants and environments
    op.execute('ALTER TABLE tenants DROP COLUMN IF EXISTS canonical_onboarding_version;')
    op.execute('ALTER TABLE tenants DROP COLUMN IF EXISTS canonical_onboarded_at;')
    op.execute('ALTER TABLE tenants DROP COLUMN IF EXISTS canonical_anchor_environment_id;')
    op.execute('ALTER TABLE environments DROP COLUMN IF EXISTS git_folder;')

