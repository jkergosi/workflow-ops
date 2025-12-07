-- Migration: Update subscription_plans.features with comprehensive feature flags
-- Date: 2025-12-06
-- Description: Adds detailed feature configuration for Free, Pro, and Enterprise plans

-- ============================================================================
-- UPDATE FREE PLAN FEATURES
-- ============================================================================
UPDATE subscription_plans SET features = '{
  "max_environments": 1,
  "max_team_members": 1,
  "github_backup": "manual",
  "github_restore": true,
  "scheduled_backup": false,
  "environment_promotion": false,
  "credential_remapping": false,
  "workflow_diff": false,
  "execution_metrics": "basic",
  "alerting": false,
  "role_based_access": false,
  "audit_logs": false,
  "audit_retention_days": 0,
  "workflow_lifecycle": false,
  "secret_vault": false,
  "compliance_tools": false,
  "environment_protection": false,
  "sso_scim": false,
  "support": "community"
}'::jsonb WHERE name = 'free';

-- ============================================================================
-- UPDATE PRO PLAN FEATURES
-- ============================================================================
UPDATE subscription_plans SET features = '{
  "max_environments": 3,
  "max_team_members": 5,
  "github_backup": "scheduled",
  "github_restore": true,
  "scheduled_backup": true,
  "environment_promotion": "manual",
  "credential_remapping": false,
  "workflow_diff": true,
  "execution_metrics": "full",
  "alerting": "basic",
  "role_based_access": true,
  "audit_logs": "limited",
  "audit_retention_days": 30,
  "workflow_lifecycle": true,
  "secret_vault": false,
  "compliance_tools": false,
  "environment_protection": false,
  "sso_scim": false,
  "support": "priority"
}'::jsonb WHERE name = 'pro';

-- ============================================================================
-- UPDATE ENTERPRISE PLAN FEATURES
-- ============================================================================
UPDATE subscription_plans SET features = '{
  "max_environments": "unlimited",
  "max_team_members": "unlimited",
  "github_backup": "scheduled",
  "github_restore": true,
  "scheduled_backup": true,
  "environment_promotion": "automated",
  "credential_remapping": true,
  "workflow_diff": true,
  "execution_metrics": "advanced",
  "alerting": "advanced",
  "role_based_access": true,
  "audit_logs": "full",
  "audit_retention_days": 365,
  "workflow_lifecycle": true,
  "secret_vault": true,
  "compliance_tools": true,
  "environment_protection": true,
  "sso_scim": true,
  "support": "dedicated"
}'::jsonb WHERE name = 'enterprise';

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================
-- SELECT name, features FROM subscription_plans;
