"""create_plan_feature_requirements

Revision ID: 9bc1bdfc90a0
Revises: 'be70defcb0d7'
Create Date: 2026-01-05 10:53:24

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9bc1bdfc90a0'
down_revision = 'be70defcb0d7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    CREATE TABLE IF NOT EXISTS plan_feature_requirements (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), feature_name VARCHAR(100) NOT NULL UNIQUE, required_plan VARCHAR(50), created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()); INSERT INTO plan_feature_requirements (feature_name, required_plan) VALUES ('github_sync', 'pro'), ('scheduled_backups', 'pro'), ('workflow_snapshots', 'free'), ('deployments', 'pro'), ('observability', 'pro'), ('audit_logs', 'pro'), ('custom_branding', 'agency'), ('sso', 'enterprise'), ('api_access', 'pro'), ('priority_support', 'pro'), ('environment_health', 'pro'), ('environment_diff', 'pro'), ('workflow_dirty_check', 'pro'), ('workflow_ci_cd', 'pro'), ('workflow_ci_cd_approval', 'agency'), ('snapshots_auto', 'pro'), ('snapshots_export', 'pro'), ('observability_alerts', 'pro'), ('observability_alerts_advanced', 'enterprise'), ('observability_logs', 'pro'), ('rbac_advanced', 'agency'), ('audit_export', 'agency'), ('agency_enabled', 'agency'), ('agency_client_management', 'agency'), ('agency_whitelabel', 'agency'), ('sso_saml', 'enterprise'), ('data_residency', 'enterprise'), ('drift_incidents', 'agency') ON CONFLICT (feature_name) DO UPDATE SET required_plan = EXCLUDED.required_plan, updated_at = NOW();
    ''')


def downgrade() -> None:
    pass

