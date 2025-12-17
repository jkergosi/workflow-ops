-- Migration: Create Credential Management Tables
-- Description: Creates tables for logical credentials, credential mappings, and workflow dependencies
-- Date: 2025-01-16

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- logical_credentials table
-- Stores abstract credential aliases (tenant-scoped)
-- ============================================
CREATE TABLE IF NOT EXISTS logical_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    required_type VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Enable RLS on logical_credentials
ALTER TABLE logical_credentials ENABLE ROW LEVEL SECURITY;

-- RLS policy for logical_credentials
CREATE POLICY logical_credentials_tenant_isolation ON logical_credentials
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ============================================
-- credential_mappings table
-- Links logical credentials to physical credentials per environment
-- ============================================
CREATE TABLE IF NOT EXISTS credential_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    logical_credential_id UUID NOT NULL REFERENCES logical_credentials(id) ON DELETE CASCADE,
    environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL DEFAULT 'n8n',
    physical_credential_id VARCHAR(255) NOT NULL,
    physical_name VARCHAR(255),
    physical_type VARCHAR(255),
    status VARCHAR(50) DEFAULT 'valid' CHECK (status IN ('valid', 'invalid', 'stale')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, logical_credential_id, environment_id, provider)
);

-- Enable RLS on credential_mappings
ALTER TABLE credential_mappings ENABLE ROW LEVEL SECURITY;

-- RLS policy for credential_mappings
CREATE POLICY credential_mappings_tenant_isolation ON credential_mappings
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ============================================
-- workflow_credential_dependencies table
-- Tracks which credentials each workflow requires
-- ============================================
CREATE TABLE IF NOT EXISTS workflow_credential_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    workflow_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL DEFAULT 'n8n',
    logical_credential_ids JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workflow_id, provider)
);

-- Enable RLS on workflow_credential_dependencies
ALTER TABLE workflow_credential_dependencies ENABLE ROW LEVEL SECURITY;

-- RLS policy for workflow_credential_dependencies
CREATE POLICY workflow_deps_tenant_isolation ON workflow_credential_dependencies
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ============================================
-- Indexes for performance
-- ============================================
CREATE INDEX IF NOT EXISTS idx_logical_credentials_tenant ON logical_credentials(tenant_id);
CREATE INDEX IF NOT EXISTS idx_logical_credentials_name ON logical_credentials(name);

CREATE INDEX IF NOT EXISTS idx_credential_mappings_tenant ON credential_mappings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_credential_mappings_logical ON credential_mappings(logical_credential_id);
CREATE INDEX IF NOT EXISTS idx_credential_mappings_env ON credential_mappings(environment_id);
CREATE INDEX IF NOT EXISTS idx_credential_mappings_status ON credential_mappings(status);

CREATE INDEX IF NOT EXISTS idx_workflow_deps_tenant ON workflow_credential_dependencies(tenant_id);
CREATE INDEX IF NOT EXISTS idx_workflow_deps_workflow ON workflow_credential_dependencies(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_deps_provider ON workflow_credential_dependencies(provider);

-- ============================================
-- Update triggers for updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for logical_credentials
DROP TRIGGER IF EXISTS update_logical_credentials_updated_at ON logical_credentials;
CREATE TRIGGER update_logical_credentials_updated_at
    BEFORE UPDATE ON logical_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for credential_mappings
DROP TRIGGER IF EXISTS update_credential_mappings_updated_at ON credential_mappings;
CREATE TRIGGER update_credential_mappings_updated_at
    BEFORE UPDATE ON credential_mappings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for workflow_credential_dependencies
DROP TRIGGER IF EXISTS update_workflow_deps_updated_at ON workflow_credential_dependencies;
CREATE TRIGGER update_workflow_deps_updated_at
    BEFORE UPDATE ON workflow_credential_dependencies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Grant permissions (adjust based on your setup)
-- ============================================
-- GRANT ALL ON logical_credentials TO authenticated;
-- GRANT ALL ON credential_mappings TO authenticated;
-- GRANT ALL ON workflow_credential_dependencies TO authenticated;
