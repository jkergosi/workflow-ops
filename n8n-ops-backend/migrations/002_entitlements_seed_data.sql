-- ============================================================================
-- Phase 1: Seed Data for Entitlements
-- ============================================================================

-- Insert Plans
INSERT INTO plans (name, display_name, description, sort_order) VALUES
    ('free', 'Free', 'Basic features for small teams', 0),
    ('pro', 'Pro', 'Advanced features for growing teams', 1),
    ('enterprise', 'Enterprise', 'Full features for large organizations', 2),
    ('agency', 'Agency', 'Agency-specific features', 3)
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    sort_order = EXCLUDED.sort_order;

-- Insert Phase 1 Features
INSERT INTO features (name, display_name, description, type, default_value) VALUES
    ('snapshots_enabled', 'Snapshots', 'Git-backed environment snapshots for backup and rollback', 'flag', '{"enabled": false}'),
    ('workflow_ci_cd', 'Workflow CI/CD', 'Pipeline-based workflow promotion between environments', 'flag', '{"enabled": false}'),
    ('workflow_limits', 'Workflow Limits', 'Maximum number of workflows allowed per tenant', 'limit', '{"value": 5}')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    type = EXCLUDED.type,
    default_value = EXCLUDED.default_value;

-- ============================================================================
-- Free plan features
-- ============================================================================
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f
WHERE p.name = 'free' AND f.name = 'snapshots_enabled'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": false}'::jsonb
FROM plans p, features f
WHERE p.name = 'free' AND f.name = 'workflow_ci_cd'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 10}'::jsonb
FROM plans p, features f
WHERE p.name = 'free' AND f.name = 'workflow_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- ============================================================================
-- Pro plan features
-- ============================================================================
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f
WHERE p.name = 'pro' AND f.name = 'snapshots_enabled'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f
WHERE p.name = 'pro' AND f.name = 'workflow_ci_cd'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 200}'::jsonb
FROM plans p, features f
WHERE p.name = 'pro' AND f.name = 'workflow_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- ============================================================================
-- Enterprise plan features
-- ============================================================================
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f
WHERE p.name = 'enterprise' AND f.name = 'snapshots_enabled'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f
WHERE p.name = 'enterprise' AND f.name = 'workflow_ci_cd'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 5000}'::jsonb
FROM plans p, features f
WHERE p.name = 'enterprise' AND f.name = 'workflow_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- ============================================================================
-- Agency plan features (same as Pro for Phase 1)
-- ============================================================================
INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f
WHERE p.name = 'agency' AND f.name = 'snapshots_enabled'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"enabled": true}'::jsonb
FROM plans p, features f
WHERE p.name = 'agency' AND f.name = 'workflow_ci_cd'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO plan_features (plan_id, feature_id, value)
SELECT p.id, f.id, '{"value": 200}'::jsonb
FROM plans p, features f
WHERE p.name = 'agency' AND f.name = 'workflow_limits'
ON CONFLICT (plan_id, feature_id) DO UPDATE SET value = EXCLUDED.value;

-- ============================================================================
-- Migrate existing tenants to tenant_plans (assign 'free' plan by default)
-- ============================================================================
INSERT INTO tenant_plans (tenant_id, plan_id)
SELECT t.id, p.id
FROM tenants t
CROSS JOIN plans p
WHERE p.name = 'free'
AND NOT EXISTS (SELECT 1 FROM tenant_plans tp WHERE tp.tenant_id = t.id)
ON CONFLICT (tenant_id) DO NOTHING;
