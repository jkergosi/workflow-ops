-- ============================================================================
-- Phase 3: Tenant Feature Overrides
-- Allows per-tenant customization of feature values
-- ============================================================================

-- Tenant Feature Overrides - allows overriding any feature value per tenant
CREATE TABLE IF NOT EXISTS tenant_feature_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    feature_id UUID NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    value JSONB NOT NULL,  -- {"enabled": true} or {"value": 500}
    reason TEXT,           -- Admin note explaining why override was added
    created_by UUID REFERENCES users(id),
    expires_at TIMESTAMPTZ,  -- NULL = permanent, otherwise auto-expires
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, feature_id)
);

-- Index for efficient lookup
CREATE INDEX IF NOT EXISTS idx_tenant_feature_overrides_tenant_id
    ON tenant_feature_overrides(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_feature_overrides_feature_id
    ON tenant_feature_overrides(feature_id);
CREATE INDEX IF NOT EXISTS idx_tenant_feature_overrides_active
    ON tenant_feature_overrides(tenant_id, is_active) WHERE is_active = true;

-- Apply updated_at trigger
DROP TRIGGER IF EXISTS update_tenant_feature_overrides_updated_at ON tenant_feature_overrides;
CREATE TRIGGER update_tenant_feature_overrides_updated_at BEFORE UPDATE ON tenant_feature_overrides
    FOR EACH ROW EXECUTE FUNCTION update_entitlements_updated_at();

-- Trigger to increment entitlements_version when override changes
CREATE OR REPLACE FUNCTION increment_entitlements_version_on_override()
RETURNS TRIGGER AS $$
BEGIN
    -- Increment version for the affected tenant
    UPDATE tenant_plans
    SET entitlements_version = entitlements_version + 1
    WHERE tenant_id = COALESCE(NEW.tenant_id, OLD.tenant_id);

    RETURN COALESCE(NEW, OLD);
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS trigger_increment_version_on_override_insert ON tenant_feature_overrides;
CREATE TRIGGER trigger_increment_version_on_override_insert
    AFTER INSERT ON tenant_feature_overrides
    FOR EACH ROW EXECUTE FUNCTION increment_entitlements_version_on_override();

DROP TRIGGER IF EXISTS trigger_increment_version_on_override_update ON tenant_feature_overrides;
CREATE TRIGGER trigger_increment_version_on_override_update
    AFTER UPDATE ON tenant_feature_overrides
    FOR EACH ROW EXECUTE FUNCTION increment_entitlements_version_on_override();

DROP TRIGGER IF EXISTS trigger_increment_version_on_override_delete ON tenant_feature_overrides;
CREATE TRIGGER trigger_increment_version_on_override_delete
    AFTER DELETE ON tenant_feature_overrides
    FOR EACH ROW EXECUTE FUNCTION increment_entitlements_version_on_override();
