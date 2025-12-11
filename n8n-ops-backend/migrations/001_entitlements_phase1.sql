-- ============================================================================
-- Phase 1: Entitlements System Tables
-- ============================================================================

-- 1. Features table - catalog of all features
CREATE TABLE IF NOT EXISTS features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(20) NOT NULL CHECK (type IN ('flag', 'limit')),
    default_value JSONB NOT NULL,  -- {"enabled": false} or {"value": 0}
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'deprecated', 'hidden')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Plans table - available subscription plans
CREATE TABLE IF NOT EXISTS plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,  -- 'free', 'pro', 'enterprise', 'agency'
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    sort_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Plan-Feature mappings (entitlements per plan)
CREATE TABLE IF NOT EXISTS plan_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    feature_id UUID NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    value JSONB NOT NULL,  -- {"enabled": true} or {"value": 200}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(plan_id, feature_id)
);

-- 4. Tenant-Plan assignment (bridges tenant to entitlements)
CREATE TABLE IF NOT EXISTS tenant_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES plans(id),
    entitlements_version INT DEFAULT 1,  -- Incremented on plan changes for cache invalidation
    effective_from TIMESTAMPTZ DEFAULT NOW(),
    effective_until TIMESTAMPTZ,  -- NULL = indefinite
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id)  -- One active plan per tenant
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_plan_features_plan_id ON plan_features(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_features_feature_id ON plan_features(feature_id);
CREATE INDEX IF NOT EXISTS idx_tenant_plans_tenant_id ON tenant_plans(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_plans_plan_id ON tenant_plans(plan_id);
CREATE INDEX IF NOT EXISTS idx_features_name ON features(name);

-- Trigger function to auto-update updated_at
CREATE OR REPLACE FUNCTION update_entitlements_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all entitlement tables
DROP TRIGGER IF EXISTS update_features_updated_at ON features;
CREATE TRIGGER update_features_updated_at BEFORE UPDATE ON features
    FOR EACH ROW EXECUTE FUNCTION update_entitlements_updated_at();

DROP TRIGGER IF EXISTS update_plans_updated_at ON plans;
CREATE TRIGGER update_plans_updated_at BEFORE UPDATE ON plans
    FOR EACH ROW EXECUTE FUNCTION update_entitlements_updated_at();

DROP TRIGGER IF EXISTS update_plan_features_updated_at ON plan_features;
CREATE TRIGGER update_plan_features_updated_at BEFORE UPDATE ON plan_features
    FOR EACH ROW EXECUTE FUNCTION update_entitlements_updated_at();

DROP TRIGGER IF EXISTS update_tenant_plans_updated_at ON tenant_plans;
CREATE TRIGGER update_tenant_plans_updated_at BEFORE UPDATE ON tenant_plans
    FOR EACH ROW EXECUTE FUNCTION update_entitlements_updated_at();

-- Trigger to increment entitlements_version when plan changes
CREATE OR REPLACE FUNCTION increment_entitlements_version()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.plan_id IS DISTINCT FROM NEW.plan_id THEN
        NEW.entitlements_version = OLD.entitlements_version + 1;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS increment_tenant_entitlements_version ON tenant_plans;
CREATE TRIGGER increment_tenant_entitlements_version BEFORE UPDATE ON tenant_plans
    FOR EACH ROW EXECUTE FUNCTION increment_entitlements_version();
