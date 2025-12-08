-- Migration: Rename environment fields to have n8n_ prefix
-- Date: 2024-12-08
-- Description: Renames name, type, base_url, api_key columns to n8n_name, n8n_type, n8n_base_url, n8n_api_key

-- Rename columns with n8n_ prefix for clarity
ALTER TABLE environments RENAME COLUMN name TO n8n_name;
ALTER TABLE environments RENAME COLUMN type TO n8n_type;
ALTER TABLE environments RENAME COLUMN base_url TO n8n_base_url;
ALTER TABLE environments RENAME COLUMN api_key TO n8n_api_key;

-- Update any existing check constraints if needed
-- The type constraint should still work as the values haven't changed

-- Add comments explaining the fields
COMMENT ON COLUMN environments.n8n_name IS 'Name/label for the N8N instance';
COMMENT ON COLUMN environments.n8n_type IS 'Environment type: dev, staging, or production';
COMMENT ON COLUMN environments.n8n_base_url IS 'Base URL of the N8N instance (e.g., https://n8n.example.com)';
COMMENT ON COLUMN environments.n8n_api_key IS 'API key for authenticating with the N8N instance';
COMMENT ON COLUMN environments.n8n_encryption_key IS 'Encryption key used by N8N for encrypting credentials';
