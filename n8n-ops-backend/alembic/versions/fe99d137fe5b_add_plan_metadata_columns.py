"""add_plan_metadata_columns

Revision ID: fe99d137fe5b
Revises: 'af5ff910eede'
Create Date: 2026-01-05 10:52:46

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fe99d137fe5b'
down_revision = 'af5ff910eede'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('''
    ALTER TABLE plans ADD COLUMN IF NOT EXISTS icon VARCHAR(50); ALTER TABLE plans ADD COLUMN IF NOT EXISTS color_class VARCHAR(100); ALTER TABLE plans ADD COLUMN IF NOT EXISTS precedence INTEGER DEFAULT 0; UPDATE plans SET icon = CASE name WHEN 'free' THEN 'zap' WHEN 'pro' THEN 'credit-card' WHEN 'agency' THEN 'building-2' WHEN 'enterprise' THEN 'crown' ELSE 'credit-card' END WHERE icon IS NULL; UPDATE plans SET color_class = CASE name WHEN 'free' THEN 'text-gray-600' WHEN 'pro' THEN 'text-blue-600' WHEN 'agency' THEN 'text-purple-600' WHEN 'enterprise' THEN 'text-yellow-600' ELSE 'text-gray-600' END WHERE color_class IS NULL; UPDATE plans SET precedence = CASE name WHEN 'free' THEN 0 WHEN 'pro' THEN 10 WHEN 'agency' THEN 20 WHEN 'enterprise' THEN 30 ELSE 0 END WHERE precedence = 0;
    ''')


def downgrade() -> None:
    pass

