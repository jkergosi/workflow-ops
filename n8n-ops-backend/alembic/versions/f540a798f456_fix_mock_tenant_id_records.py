"""fix_mock_tenant_id_records

Revision ID: f540a798f456
Revises: 0d3cc810ee1a
Create Date: 2025-12-31 20:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f540a798f456'
down_revision = '0d3cc810ee1a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix records with MOCK_TENANT_ID by assigning them to the first real tenant
    # This is a simplified approach that handles all tables uniformly
    op.execute('''
    DO $$
    DECLARE
      first_tenant_id UUID;
    BEGIN
      -- Get first real tenant (not the mock one)
      SELECT id INTO first_tenant_id
      FROM tenants
      WHERE id != '00000000-0000-0000-0000-000000000000'
      ORDER BY created_at ASC
      LIMIT 1;

      -- Only proceed if we found a real tenant
      IF first_tenant_id IS NOT NULL THEN
        -- Update environments
        UPDATE environments
        SET tenant_id = first_tenant_id
        WHERE tenant_id = '00000000-0000-0000-0000-000000000000';

        -- Update workflows
        UPDATE workflows
        SET tenant_id = first_tenant_id
        WHERE tenant_id = '00000000-0000-0000-0000-000000000000';

        -- Update executions
        UPDATE executions
        SET tenant_id = first_tenant_id
        WHERE tenant_id = '00000000-0000-0000-0000-000000000000';

        -- Update snapshots
        UPDATE snapshots
        SET tenant_id = first_tenant_id
        WHERE tenant_id = '00000000-0000-0000-0000-000000000000';

        -- Update deployments
        UPDATE deployments
        SET tenant_id = first_tenant_id
        WHERE tenant_id = '00000000-0000-0000-0000-000000000000';

        -- Update promotions
        UPDATE promotions
        SET tenant_id = first_tenant_id
        WHERE tenant_id = '00000000-0000-0000-0000-000000000000';

        -- Update credentials
        UPDATE credentials
        SET tenant_id = first_tenant_id
        WHERE tenant_id = '00000000-0000-0000-0000-000000000000';

        -- Update tags
        UPDATE tags
        SET tenant_id = first_tenant_id
        WHERE tenant_id = '00000000-0000-0000-0000-000000000000';

        -- Update n8n_users
        UPDATE n8n_users
        SET tenant_id = first_tenant_id
        WHERE tenant_id = '00000000-0000-0000-0000-000000000000';

        -- Update pipelines
        UPDATE pipelines
        SET tenant_id = first_tenant_id
        WHERE tenant_id = '00000000-0000-0000-0000-000000000000';
      END IF;
    END;
    $$;
    ''')


def downgrade() -> None:
    pass
