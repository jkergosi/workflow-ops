"""add_provider_config_to_environments

Revision ID: l3m4n5o6p7q8
Revises: 'f7g8h9i0j1k2'
Create Date: 2025-01-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'l3m4n5o6p7q8'
down_revision = 'f7g8h9i0j1k2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    -- Add provider_config JSONB column to environments
    ALTER TABLE environments ADD COLUMN IF NOT EXISTS provider_config JSONB DEFAULT '{}'::jsonb;
    
    -- Backfill provider_config from existing n8n_* fields for n8n provider
    UPDATE environments
    SET provider_config = jsonb_build_object(
        'base_url', n8n_base_url,
        'api_key', n8n_api_key,
        'encryption_key', n8n_encryption_key
    )
    WHERE provider = 'n8n' AND (provider_config IS NULL OR provider_config = '{}'::jsonb);
    ''')


def downgrade() -> None:
    op.execute('''
    -- Drop provider_config column
    ALTER TABLE environments DROP COLUMN IF EXISTS provider_config;
    ''')

