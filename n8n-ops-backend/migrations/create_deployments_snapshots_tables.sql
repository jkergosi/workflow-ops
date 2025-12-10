-- Migration: Create deployments, snapshots, and deployment_workflows tables
-- Date: 2024-12-XX
-- Description: 
--   - Creates snapshots table for Git-backed environment states
--   - Creates deployments table for promotion records
--   - Creates deployment_workflows table for per-workflow results

-- Snapshots table: Git-backed environment states
CREATE TABLE IF NOT EXISTS snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    git_commit_sha TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('auto_backup', 'pre_promotion', 'post_promotion', 'manual_backup')),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by_user_id TEXT,
    related_deployment_id UUID, -- Will reference deployments table after it's created
    metadata_json JSONB,
    CONSTRAINT fk_snapshots_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_snapshots_environment FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
);

-- Deployments table: Promotion records (pipeline stage executions)
CREATE TABLE IF NOT EXISTS deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    pipeline_id UUID REFERENCES pipelines(id) ON DELETE SET NULL,
    source_environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    target_environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'success', 'failed', 'canceled')) DEFAULT 'pending',
    triggered_by_user_id TEXT NOT NULL,
    approved_by_user_id TEXT,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP WITH TIME ZONE,
    pre_snapshot_id UUID REFERENCES snapshots(id) ON DELETE SET NULL,
    post_snapshot_id UUID REFERENCES snapshots(id) ON DELETE SET NULL,
    summary_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_deployments_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT fk_deployments_source_env FOREIGN KEY (source_environment_id) REFERENCES environments(id) ON DELETE CASCADE,
    CONSTRAINT fk_deployments_target_env FOREIGN KEY (target_environment_id) REFERENCES environments(id) ON DELETE CASCADE,
    CONSTRAINT fk_deployments_pre_snapshot FOREIGN KEY (pre_snapshot_id) REFERENCES snapshots(id) ON DELETE SET NULL,
    CONSTRAINT fk_deployments_post_snapshot FOREIGN KEY (post_snapshot_id) REFERENCES snapshots(id) ON DELETE SET NULL
);

-- Now add the foreign key constraint for snapshots.related_deployment_id
ALTER TABLE snapshots 
ADD CONSTRAINT fk_snapshots_deployment FOREIGN KEY (related_deployment_id) REFERENCES deployments(id) ON DELETE SET NULL;

-- Deployment workflows table: Per-workflow results within a deployment
CREATE TABLE IF NOT EXISTS deployment_workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_id UUID NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
    workflow_id TEXT NOT NULL,
    workflow_name_at_time TEXT NOT NULL,
    change_type TEXT NOT NULL CHECK (change_type IN ('created', 'updated', 'deleted', 'skipped', 'unchanged')),
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'skipped')) DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_deployment_workflows_deployment FOREIGN KEY (deployment_id) REFERENCES deployments(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_snapshots_environment_id ON snapshots(environment_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_type ON snapshots(type);
CREATE INDEX IF NOT EXISTS idx_snapshots_created_at ON snapshots(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_deployment_id ON snapshots(related_deployment_id);

CREATE INDEX IF NOT EXISTS idx_deployments_tenant_id ON deployments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_deployments_pipeline_id ON deployments(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_deployments_source_env ON deployments(source_environment_id);
CREATE INDEX IF NOT EXISTS idx_deployments_target_env ON deployments(target_environment_id);
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_deployments_started_at ON deployments(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_deployment_workflows_deployment_id ON deployment_workflows(deployment_id);
CREATE INDEX IF NOT EXISTS idx_deployment_workflows_workflow_id ON deployment_workflows(workflow_id);

-- Comments
COMMENT ON TABLE snapshots IS 'Git-backed environment states. Metadata only; actual workflow JSON is stored in GitHub.';
COMMENT ON TABLE deployments IS 'Promotion records representing pipeline stage executions. Links pre and post snapshots.';
COMMENT ON TABLE deployment_workflows IS 'Per-workflow results within a deployment, tracking change type and status.';

COMMENT ON COLUMN snapshots.git_commit_sha IS 'Git commit SHA that stores the full workflow state for this environment at this point in time.';
COMMENT ON COLUMN snapshots.type IS 'Type of snapshot: auto_backup, pre_promotion, post_promotion, or manual_backup.';
COMMENT ON COLUMN deployments.status IS 'Deployment status: pending, running, success, failed, or canceled.';
COMMENT ON COLUMN deployments.summary_json IS 'Summary statistics: total, created, updated, deleted, failed counts.';
COMMENT ON COLUMN deployment_workflows.change_type IS 'Type of change: created, updated, deleted, skipped, or unchanged.';

