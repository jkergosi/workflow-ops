"""create_plan_limits_and_retention

Revision ID: be70defcb0d7
Revises: 'fe99d137fe5b'
Create Date: 2026-01-05 10:52:56

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'be70defcb0d7'
down_revision = 'fe99d137fe5b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    CREATE TABLE IF NOT EXISTS plan_limits (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), plan_name VARCHAR(50) NOT NULL UNIQUE, max_workflows INTEGER DEFAULT 10, max_environments INTEGER DEFAULT 1, max_users INTEGER DEFAULT 2, max_executions_daily INTEGER DEFAULT 100, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()); CREATE TABLE IF NOT EXISTS plan_retention_defaults (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), plan_name VARCHAR(50) NOT NULL UNIQUE, drift_checks INTEGER DEFAULT 7, closed_incidents INTEGER DEFAULT 0, reconciliation_artifacts INTEGER DEFAULT 0, approvals INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW()); INSERT INTO plan_limits (plan_name, max_workflows, max_environments, max_users, max_executions_daily) VALUES ('free', 10, 1, 2, 100), ('pro', 100, 3, 10, 1000), ('agency', 500, 10, 50, 10000), ('enterprise', -1, -1, -1, -1) ON CONFLICT (plan_name) DO UPDATE SET max_workflows = EXCLUDED.max_workflows, max_environments = EXCLUDED.max_environments, max_users = EXCLUDED.max_users, max_executions_daily = EXCLUDED.max_executions_daily, updated_at = NOW(); INSERT INTO plan_retention_defaults (plan_name, drift_checks, closed_incidents, reconciliation_artifacts, approvals) VALUES ('free', 7, 0, 0, 0), ('pro', 30, 180, 180, 180), ('agency', 90, 365, 365, 365), ('enterprise', 180, 2555, 2555, 2555) ON CONFLICT (plan_name) DO UPDATE SET drift_checks = EXCLUDED.drift_checks, closed_incidents = EXCLUDED.closed_incidents, reconciliation_artifacts = EXCLUDED.reconciliation_artifacts, approvals = EXCLUDED.approvals, updated_at = NOW();
    ''')


def downgrade() -> None:
    pass

