-- ============================================================================
-- Phase 2: Full Feature Catalog (22 new features, 25 total)
-- ============================================================================

-- Environment Features
INSERT INTO features (name, display_name, description, type, default_value) VALUES
    ('environment_basic', 'Basic Environments', 'Create and manage N8N environments', 'flag', '{"enabled": true}'),
    ('environment_health', 'Environment Health', 'Health monitoring and status checks', 'flag', '{"enabled": false}'),
    ('environment_diff', 'Environment Diff', 'Drift detection between environments and Git', 'flag', '{"enabled": false}'),
    ('environment_limits', 'Environment Limits', 'Maximum number of environments allowed', 'limit', '{"value": 2}')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    type = EXCLUDED.type,
    default_value = EXCLUDED.default_value;

-- Workflow Features
INSERT INTO features (name, display_name, description, type, default_value) VALUES
    ('workflow_read', 'View Workflows', 'View and list workflows', 'flag', '{"enabled": true}'),
    ('workflow_push', 'Push Workflows', 'Upload, modify, and sync workflows', 'flag', '{"enabled": true}'),
    ('workflow_dirty_check', 'Dirty State Detection', 'Detect unsaved changes and conflicts', 'flag', '{"enabled": false}'),
    ('workflow_ci_cd_approval', 'CI/CD Approvals', 'Require approvals for workflow promotions', 'flag', '{"enabled": false}')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    type = EXCLUDED.type,
    default_value = EXCLUDED.default_value;

-- Snapshot Features
INSERT INTO features (name, display_name, description, type, default_value) VALUES
    ('snapshots_auto', 'Automatic Snapshots', 'Automated snapshot creation on changes', 'flag', '{"enabled": false}'),
    ('snapshots_history', 'Snapshot History', 'Number of snapshots retained per environment', 'limit', '{"value": 5}'),
    ('snapshots_export', 'Snapshot Export', 'Export snapshots to external storage', 'flag', '{"enabled": false}')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    type = EXCLUDED.type,
    default_value = EXCLUDED.default_value;

-- Observability Features
INSERT INTO features (name, display_name, description, type, default_value) VALUES
    ('observability_basic', 'Basic Observability', 'Execution metrics and performance data', 'flag', '{"enabled": true}'),
    ('observability_alerts', 'Alerts', 'Notification rules for execution failures', 'flag', '{"enabled": false}'),
    ('observability_alerts_advanced', 'Advanced Alerts', 'Complex alert conditions and escalations', 'flag', '{"enabled": false}'),
    ('observability_logs', 'Execution Logs', 'Detailed execution log access', 'flag', '{"enabled": false}'),
    ('observability_limits', 'Log Retention', 'Days of log retention', 'limit', '{"value": 7}')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    type = EXCLUDED.type,
    default_value = EXCLUDED.default_value;

-- Security/RBAC Features
INSERT INTO features (name, display_name, description, type, default_value) VALUES
    ('rbac_basic', 'Basic RBAC', 'Basic role management (admin, developer, viewer)', 'flag', '{"enabled": true}'),
    ('rbac_advanced', 'Advanced RBAC', 'Custom roles and fine-grained permissions', 'flag', '{"enabled": false}'),
    ('audit_logs', 'Audit Logs', 'User action audit logging', 'flag', '{"enabled": false}'),
    ('audit_export', 'Audit Export', 'Export audit logs for compliance', 'flag', '{"enabled": false}')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    type = EXCLUDED.type,
    default_value = EXCLUDED.default_value;

-- Agency Features
INSERT INTO features (name, display_name, description, type, default_value) VALUES
    ('agency_enabled', 'Agency Mode', 'Multi-client agency management', 'flag', '{"enabled": false}'),
    ('agency_client_management', 'Client Management', 'Manage client organizations', 'flag', '{"enabled": false}'),
    ('agency_whitelabel', 'White Label', 'Custom branding and white-label options', 'flag', '{"enabled": false}'),
    ('agency_client_limits', 'Client Limits', 'Maximum number of agency clients', 'limit', '{"value": 0}')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    type = EXCLUDED.type,
    default_value = EXCLUDED.default_value;

-- Enterprise Features
INSERT INTO features (name, display_name, description, type, default_value) VALUES
    ('sso_saml', 'SSO/SAML', 'Single sign-on with SAML integration', 'flag', '{"enabled": false}'),
    ('support_priority', 'Priority Support', 'Priority technical support access', 'flag', '{"enabled": false}'),
    ('data_residency', 'Data Residency', 'Regional data storage controls', 'flag', '{"enabled": false}')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    type = EXCLUDED.type,
    default_value = EXCLUDED.default_value;
