-- Migration: Create providers tables
-- Date: 2025-01-19
-- Description: Add provider as first-class purchasable product with plans and subscriptions

-- Providers table (automation platforms like n8n, Make.com)
CREATE TABLE IF NOT EXISTS providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    icon VARCHAR(255),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Provider plans table (subscription tiers per provider)
CREATE TABLE IF NOT EXISTS provider_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES providers(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    price_monthly DECIMAL(10,2) DEFAULT 0,
    price_yearly DECIMAL(10,2) DEFAULT 0,
    stripe_price_id_monthly VARCHAR(255),
    stripe_price_id_yearly VARCHAR(255),
    features JSONB DEFAULT '{}',
    max_environments INTEGER DEFAULT 1,
    max_workflows INTEGER DEFAULT 10,
    is_active BOOLEAN DEFAULT true,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider_id, name)
);

-- Tenant provider subscriptions (links tenants to provider plans)
CREATE TABLE IF NOT EXISTS tenant_provider_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    provider_id UUID REFERENCES providers(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES provider_plans(id) ON DELETE SET NULL,
    stripe_subscription_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'active',
    billing_cycle VARCHAR(20) DEFAULT 'monthly',
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, provider_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_provider_plans_provider_id ON provider_plans(provider_id);
CREATE INDEX IF NOT EXISTS idx_tenant_provider_subs_tenant_id ON tenant_provider_subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_provider_subs_provider_id ON tenant_provider_subscriptions(provider_id);
CREATE INDEX IF NOT EXISTS idx_tenant_provider_subs_status ON tenant_provider_subscriptions(status);

-- Seed initial providers
INSERT INTO providers (name, display_name, icon, description) VALUES
('n8n', 'n8n', 'workflow', 'Open-source workflow automation platform'),
('make', 'Make.com', 'zap', 'Visual automation platform for connecting apps')
ON CONFLICT (name) DO NOTHING;

-- Seed n8n plans
INSERT INTO provider_plans (provider_id, name, display_name, description, price_monthly, price_yearly, features, max_environments, max_workflows, sort_order)
SELECT
    p.id,
    'free',
    'Free',
    'Get started with basic workflow management',
    0,
    0,
    '{"github_backup": false, "promotions": false, "audit_logs": false}'::jsonb,
    1,
    10,
    1
FROM providers p WHERE p.name = 'n8n'
ON CONFLICT (provider_id, name) DO NOTHING;

INSERT INTO provider_plans (provider_id, name, display_name, description, price_monthly, price_yearly, features, max_environments, max_workflows, sort_order)
SELECT
    p.id,
    'pro',
    'Pro',
    'Advanced features for teams',
    29,
    290,
    '{"github_backup": true, "promotions": true, "audit_logs": true, "priority_support": false}'::jsonb,
    5,
    100,
    2
FROM providers p WHERE p.name = 'n8n'
ON CONFLICT (provider_id, name) DO NOTHING;

INSERT INTO provider_plans (provider_id, name, display_name, description, price_monthly, price_yearly, features, max_environments, max_workflows, sort_order)
SELECT
    p.id,
    'enterprise',
    'Enterprise',
    'Full-featured for large organizations',
    99,
    990,
    '{"github_backup": true, "promotions": true, "audit_logs": true, "priority_support": true, "sso": true, "custom_integrations": true}'::jsonb,
    -1,
    -1,
    3
FROM providers p WHERE p.name = 'n8n'
ON CONFLICT (provider_id, name) DO NOTHING;

-- Seed Make.com plans
INSERT INTO provider_plans (provider_id, name, display_name, description, price_monthly, price_yearly, features, max_environments, max_workflows, sort_order)
SELECT
    p.id,
    'free',
    'Free',
    'Get started with basic scenario management',
    0,
    0,
    '{"github_backup": false, "promotions": false}'::jsonb,
    1,
    10,
    1
FROM providers p WHERE p.name = 'make'
ON CONFLICT (provider_id, name) DO NOTHING;

INSERT INTO provider_plans (provider_id, name, display_name, description, price_monthly, price_yearly, features, max_environments, max_workflows, sort_order)
SELECT
    p.id,
    'pro',
    'Pro',
    'Advanced features for teams',
    29,
    290,
    '{"github_backup": true, "promotions": true, "audit_logs": true}'::jsonb,
    5,
    100,
    2
FROM providers p WHERE p.name = 'make'
ON CONFLICT (provider_id, name) DO NOTHING;

-- Enable Row Level Security
ALTER TABLE providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_provider_subscriptions ENABLE ROW LEVEL SECURITY;

-- RLS Policies for providers (public read)
CREATE POLICY "providers_select_policy" ON providers
    FOR SELECT USING (true);

-- RLS Policies for provider_plans (public read)
CREATE POLICY "provider_plans_select_policy" ON provider_plans
    FOR SELECT USING (true);

-- RLS Policies for tenant_provider_subscriptions (tenant-based)
CREATE POLICY "tenant_provider_subs_select_policy" ON tenant_provider_subscriptions
    FOR SELECT USING (true);

CREATE POLICY "tenant_provider_subs_insert_policy" ON tenant_provider_subscriptions
    FOR INSERT WITH CHECK (true);

CREATE POLICY "tenant_provider_subs_update_policy" ON tenant_provider_subscriptions
    FOR UPDATE USING (true);

CREATE POLICY "tenant_provider_subs_delete_policy" ON tenant_provider_subscriptions
    FOR DELETE USING (true);
