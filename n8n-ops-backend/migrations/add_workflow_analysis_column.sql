-- Migration: Add analysis JSONB column to workflows table
-- Date: 2024-12-08
-- Description: Adds analysis column to store computed workflow analysis data

-- Add analysis column as JSONB (nullable for backward compatibility)
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS analysis JSONB;

-- Add index on analysis column for query performance
CREATE INDEX IF NOT EXISTS idx_workflows_analysis ON workflows USING GIN (analysis);

-- Add comment explaining the field
COMMENT ON COLUMN workflows.analysis IS 'Computed workflow analysis data including graph structure, reliability, performance, security, and other metrics';

