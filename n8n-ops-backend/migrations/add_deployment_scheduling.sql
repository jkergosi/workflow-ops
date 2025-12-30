-- Add scheduled_at columns to deployments and promotions tables
-- This enables scheduling deployments for future execution

-- Add scheduled_at to deployments table
ALTER TABLE deployments 
ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP WITH TIME ZONE;

-- Add scheduled_at to promotions table (for tracking)
ALTER TABLE promotions 
ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP WITH TIME ZONE;

-- Create index for efficient querying of scheduled deployments
CREATE INDEX IF NOT EXISTS idx_deployments_scheduled_at 
ON deployments(scheduled_at) 
WHERE scheduled_at IS NOT NULL AND status = 'scheduled';

-- Add comment for documentation
COMMENT ON COLUMN deployments.scheduled_at IS 'Timestamp when deployment is scheduled to execute. NULL means immediate execution.';
COMMENT ON COLUMN promotions.scheduled_at IS 'Timestamp when promotion was scheduled to execute. NULL means immediate execution.';

