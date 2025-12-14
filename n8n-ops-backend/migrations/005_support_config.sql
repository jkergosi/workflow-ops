-- Migration: Support Configuration
-- Adds table for storing support integration settings (n8n webhook, JSM portal, etc.)

-- ============================================================================
-- 1. Create support_config table
-- ============================================================================

CREATE TABLE IF NOT EXISTS support_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL UNIQUE,

    -- n8n Integration
    n8n_webhook_url TEXT,
    n8n_api_key TEXT,

    -- Jira Service Management
    jsm_portal_url TEXT,
    jsm_cloud_instance TEXT,
    jsm_api_token TEXT,
    jsm_project_key TEXT,

    -- JSM Request Type IDs
    jsm_bug_request_type_id TEXT,
    jsm_feature_request_type_id TEXT,
    jsm_help_request_type_id TEXT,

    -- JSM Widget
    jsm_widget_embed_code TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 2. Create indexes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_support_config_tenant_id ON support_config(tenant_id);

-- ============================================================================
-- 3. Add updated_at trigger
-- ============================================================================

CREATE OR REPLACE FUNCTION update_support_config_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_support_config_updated_at ON support_config;

CREATE TRIGGER trg_support_config_updated_at
    BEFORE UPDATE ON support_config
    FOR EACH ROW
    EXECUTE FUNCTION update_support_config_updated_at();
