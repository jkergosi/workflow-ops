"""add_provider_columns

Revision ID: m3n4o5p6q7r8
Revises: 'd2e3f4a5b6c7'
Create Date: 2025-01-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'm3n4o5p6q7r8'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    -- Add provider column to all provider-scoped tables
    ALTER TABLE environments ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE workflows ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE executions ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE credentials ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE deployments ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE snapshots ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE promotions ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE deployment_workflows ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE tags ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE n8n_users ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE notification_channels ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    ALTER TABLE notification_rules ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'n8n';
    
    -- Backfill existing records (should all be n8n, but ensure consistency)
    UPDATE environments SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE workflows SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE executions SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE credentials SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE deployments SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE snapshots SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE pipelines SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE promotions SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE deployment_workflows SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE tags SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE n8n_users SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE notification_channels SET provider = 'n8n' WHERE provider IS NULL;
    UPDATE notification_rules SET provider = 'n8n' WHERE provider IS NULL;
    
    -- Create composite indexes for efficient provider-scoped queries
    CREATE INDEX IF NOT EXISTS idx_environments_provider_tenant ON environments(provider, tenant_id);
    CREATE INDEX IF NOT EXISTS idx_workflows_provider_env ON workflows(provider, environment_id);
    CREATE INDEX IF NOT EXISTS idx_workflows_provider_tenant ON workflows(provider, tenant_id);
    CREATE INDEX IF NOT EXISTS idx_executions_provider_env ON executions(provider, environment_id);
    CREATE INDEX IF NOT EXISTS idx_executions_provider_tenant ON executions(provider, tenant_id);
    CREATE INDEX IF NOT EXISTS idx_executions_provider_tenant_created ON executions(provider, tenant_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_credentials_provider_env ON credentials(provider, environment_id);
    CREATE INDEX IF NOT EXISTS idx_deployments_provider_tenant ON deployments(provider, tenant_id);
    CREATE INDEX IF NOT EXISTS idx_snapshots_provider_env ON snapshots(provider, environment_id);
    CREATE INDEX IF NOT EXISTS idx_promotions_provider_tenant ON promotions(provider, tenant_id);
    CREATE INDEX IF NOT EXISTS idx_workflows_provider_n8n_id ON workflows(provider, n8n_workflow_id) WHERE provider = 'n8n';
    ''')


def downgrade() -> None:
    op.execute('''
    -- Drop indexes
    DROP INDEX IF EXISTS idx_workflows_provider_n8n_id;
    DROP INDEX IF EXISTS idx_promotions_provider_tenant;
    DROP INDEX IF EXISTS idx_snapshots_provider_env;
    DROP INDEX IF EXISTS idx_deployments_provider_tenant;
    DROP INDEX IF EXISTS idx_credentials_provider_env;
    DROP INDEX IF EXISTS idx_executions_provider_tenant_created;
    DROP INDEX IF EXISTS idx_executions_provider_tenant;
    DROP INDEX IF EXISTS idx_executions_provider_env;
    DROP INDEX IF EXISTS idx_workflows_provider_tenant;
    DROP INDEX IF EXISTS idx_workflows_provider_env;
    DROP INDEX IF EXISTS idx_environments_provider_tenant;
    
    -- Drop provider columns
    ALTER TABLE notification_rules DROP COLUMN IF EXISTS provider;
    ALTER TABLE notification_channels DROP COLUMN IF EXISTS provider;
    ALTER TABLE n8n_users DROP COLUMN IF EXISTS provider;
    ALTER TABLE tags DROP COLUMN IF EXISTS provider;
    ALTER TABLE deployment_workflows DROP COLUMN IF EXISTS provider;
    ALTER TABLE promotions DROP COLUMN IF EXISTS provider;
    ALTER TABLE pipelines DROP COLUMN IF EXISTS provider;
    ALTER TABLE snapshots DROP COLUMN IF EXISTS provider;
    ALTER TABLE deployments DROP COLUMN IF EXISTS provider;
    ALTER TABLE credentials DROP COLUMN IF EXISTS provider;
    ALTER TABLE executions DROP COLUMN IF EXISTS provider;
    ALTER TABLE workflows DROP COLUMN IF EXISTS provider;
    ALTER TABLE environments DROP COLUMN IF EXISTS provider;
    ''')

