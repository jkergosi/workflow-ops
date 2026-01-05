"""create_workflow_policy_matrix

Revision ID: 245ecb3e319b
Revises: '9bc1bdfc90a0'
Create Date: 2026-01-05 11:11:41

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '245ecb3e319b'
down_revision = '9bc1bdfc90a0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    CREATE TABLE IF NOT EXISTS workflow_policy_matrix (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), environment_class VARCHAR(20) NOT NULL UNIQUE, can_view_details BOOLEAN DEFAULT true, can_open_in_n8n BOOLEAN DEFAULT true, can_create_deployment BOOLEAN DEFAULT true, can_edit_directly BOOLEAN DEFAULT false, can_soft_delete BOOLEAN DEFAULT false, can_hard_delete BOOLEAN DEFAULT false, can_create_drift_incident BOOLEAN DEFAULT false, drift_incident_required BOOLEAN DEFAULT false, edit_requires_confirmation BOOLEAN DEFAULT true, edit_requires_admin BOOLEAN DEFAULT false, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()); CREATE TABLE IF NOT EXISTS plan_policy_overrides (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), plan_name VARCHAR(50) NOT NULL, environment_class VARCHAR(20), can_edit_directly BOOLEAN, can_soft_delete BOOLEAN, can_hard_delete BOOLEAN, can_create_drift_incident BOOLEAN, drift_incident_required BOOLEAN, edit_requires_confirmation BOOLEAN, edit_requires_admin BOOLEAN, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW(), UNIQUE(plan_name, environment_class)); INSERT INTO workflow_policy_matrix (environment_class, can_view_details, can_open_in_n8n, can_create_deployment, can_edit_directly, can_soft_delete, can_hard_delete, can_create_drift_incident, drift_incident_required, edit_requires_confirmation, edit_requires_admin) VALUES ('dev', true, true, true, true, true, false, true, false, true, false), ('staging', true, true, true, true, false, false, true, false, true, true), ('production', true, true, true, false, false, false, true, true, false, false) ON CONFLICT (environment_class) DO UPDATE SET can_view_details = EXCLUDED.can_view_details, can_open_in_n8n = EXCLUDED.can_open_in_n8n, can_create_deployment = EXCLUDED.can_create_deployment, can_edit_directly = EXCLUDED.can_edit_directly, can_soft_delete = EXCLUDED.can_soft_delete, can_hard_delete = EXCLUDED.can_hard_delete, can_create_drift_incident = EXCLUDED.can_create_drift_incident, drift_incident_required = EXCLUDED.drift_incident_required, edit_requires_confirmation = EXCLUDED.edit_requires_confirmation, edit_requires_admin = EXCLUDED.edit_requires_admin, updated_at = NOW();
    ''')


def downgrade() -> None:
    pass

