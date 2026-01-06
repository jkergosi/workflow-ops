-- Create background_jobs table for tracking async background tasks
CREATE TABLE IF NOT EXISTS background_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    job_type VARCHAR(50) NOT NULL, -- 'promotion_execute', 'environment_sync', 'github_sync_from', 'github_sync_to', 'restore_execute', 'snapshot_restore'
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    resource_id UUID, -- promotion_id, environment_id, snapshot_id, etc.
    resource_type VARCHAR(50), -- 'promotion', 'environment', 'snapshot', 'workflow_sync'
    created_by UUID,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    progress JSONB DEFAULT '{}'::jsonb, -- { "current": 5, "total": 10, "percentage": 50, "message": "Processing workflow X" }
    result JSONB DEFAULT '{}'::jsonb, -- Final results when completed
    error_message TEXT,
    error_details JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb, -- Additional metadata for the job
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_background_jobs_tenant_status ON background_jobs(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_background_jobs_resource ON background_jobs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_background_jobs_job_type ON background_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_background_jobs_created_at ON background_jobs(created_at DESC);

-- Add updated_at trigger
CREATE OR REPLACE FUNCTION update_background_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_background_jobs_updated_at
    BEFORE UPDATE ON background_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_background_jobs_updated_at();

-- Add comments for documentation
COMMENT ON TABLE background_jobs IS 'Tracks background job execution for long-running operations';
COMMENT ON COLUMN background_jobs.job_type IS 'Type of background job: promotion_execute, environment_sync, github_sync_from, github_sync_to, restore_execute, snapshot_restore';
COMMENT ON COLUMN background_jobs.status IS 'Current status: pending, running, completed, failed, cancelled';
COMMENT ON COLUMN background_jobs.progress IS 'JSON object with current progress: {current, total, percentage, message}';
COMMENT ON COLUMN background_jobs.result IS 'JSON object with final results when job completes';
COMMENT ON COLUMN background_jobs.error_details IS 'JSON object with detailed error information if job fails';

