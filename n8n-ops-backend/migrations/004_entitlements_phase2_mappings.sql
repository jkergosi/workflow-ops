-- ============================================================================
-- Phase 2: Plan-Feature Mappings for All 25 Features
-- ============================================================================
-- Plan Tiers: Free < Pro < Agency < Enterprise
-- Feature Types: flag (enabled: true/false), limit (value: number)
-- ============================================================================

-- ============================================================================
-- FREE PLAN
-- ============================================================================

-- Environment Features (Free)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'environment_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'environment_health'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'environment_diff'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 2}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'environment_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Workflow Features (Free)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'workflow_read'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'workflow_push'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'workflow_dirty_check'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'workflow_ci_cd_approval'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Snapshot Features (Free)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'snapshots_auto'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 5}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'snapshots_history'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'snapshots_export'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Observability Features (Free)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'observability_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'observability_alerts'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'observability_alerts_advanced'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'observability_logs'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 7}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'observability_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Security/RBAC Features (Free)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'rbac_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'rbac_advanced'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'audit_logs'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'audit_export'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Agency Features (Free - disabled)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'agency_enabled'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'agency_client_management'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'agency_whitelabel'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 0}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'agency_client_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Enterprise Features (Free - disabled)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'sso_saml'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'support_priority'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'free' AND f.name = 'data_residency'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- ============================================================================
-- PRO PLAN
-- ============================================================================

-- Environment Features (Pro)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'environment_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'environment_health'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'environment_diff'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 10}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'environment_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Workflow Features (Pro)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'workflow_read'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'workflow_push'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'workflow_dirty_check'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'workflow_ci_cd_approval'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Snapshot Features (Pro)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'snapshots_auto'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 30}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'snapshots_history'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'snapshots_export'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Observability Features (Pro)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'observability_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'observability_alerts'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'observability_alerts_advanced'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'observability_logs'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 30}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'observability_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Security/RBAC Features (Pro)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'rbac_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'rbac_advanced'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'audit_logs'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'audit_export'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Agency Features (Pro - disabled)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'agency_enabled'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'agency_client_management'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'agency_whitelabel'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 0}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'agency_client_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Enterprise Features (Pro)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'sso_saml'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'support_priority'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'pro' AND f.name = 'data_residency'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- ============================================================================
-- AGENCY PLAN
-- ============================================================================

-- Environment Features (Agency)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'environment_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'environment_health'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'environment_diff'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 50}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'environment_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Workflow Features (Agency)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'workflow_read'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'workflow_push'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'workflow_dirty_check'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'workflow_ci_cd_approval'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Update Agency workflow_limits (from Phase 1)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 1000}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'workflow_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Snapshot Features (Agency)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'snapshots_auto'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 90}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'snapshots_history'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'snapshots_export'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Observability Features (Agency)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'observability_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'observability_alerts'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'observability_alerts_advanced'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'observability_logs'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 90}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'observability_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Security/RBAC Features (Agency)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'rbac_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'rbac_advanced'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'audit_logs'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'audit_export'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Agency Features (Agency - enabled)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'agency_enabled'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'agency_client_management'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'agency_whitelabel'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 25}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'agency_client_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Enterprise Features (Agency)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'sso_saml'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'support_priority'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f WHERE p.name = 'agency' AND f.name = 'data_residency'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- ============================================================================
-- ENTERPRISE PLAN
-- ============================================================================

-- Environment Features (Enterprise)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'environment_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'environment_health'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'environment_diff'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 999}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'environment_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Workflow Features (Enterprise)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'workflow_read'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'workflow_push'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'workflow_dirty_check'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'workflow_ci_cd_approval'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Snapshot Features (Enterprise)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'snapshots_auto'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 365}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'snapshots_history'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'snapshots_export'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Observability Features (Enterprise)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'observability_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'observability_alerts'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'observability_alerts_advanced'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'observability_logs'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 365}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'observability_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Security/RBAC Features (Enterprise)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'rbac_basic'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'rbac_advanced'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'audit_logs'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'audit_export'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Agency Features (Enterprise)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'agency_enabled'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'agency_client_management'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'agency_whitelabel'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 100}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'agency_client_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- Enterprise Features (Enterprise - all enabled)
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'sso_saml'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'support_priority'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f WHERE p.name = 'enterprise' AND f.name = 'data_residency'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;
