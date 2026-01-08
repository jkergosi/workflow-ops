# 08 - Database Schema (MVP-Critical Tables)

## Core Tables

### tenants
**Purpose**: Tenant isolation root

**Key Columns**:
- `id` (UUID PK)
- `name`, `slug`
- `subscription_tier`: free/pro/agency/enterprise (deprecated, use tenant_plans)
- `created_at`, `updated_at`

**RLS**: Enabled (policy not documented in repo)

### users
**Purpose**: User accounts

**Key Columns**:
- `id` (UUID PK)
- `tenant_id` (UUID FK)
- `email`, `supabase_auth_id`
- `role`: viewer/developer/admin
- `is_active` (bool)

**RLS**: Enabled

### environments
**Purpose**: Connected n8n/provider instances

**Key Columns**:
- `id` (UUID PK), `tenant_id` (UUID FK)
- `name`, `url`, `api_key` (encrypted)
- `provider`: n8n (enum)
- `environment_class`: dev/staging/production
- `drift_handling_mode`: warn_only/manual_override/require_attestation
- `github_repo_url`, `github_token`
- `last_heartbeat_at`, `last_sync_at`

**Constraints**: Unique `(tenant_id, name)`

**Migration**: Base table + multiple enhancement migrations

---

## Workflow Tables

### workflows
**Purpose**: Legacy/deprecated workflow storage

**Status**: Being phased out in favor of workflow_env_map

**Key Columns**:
- `id` (UUID PK), `tenant_id`, `environment_id`
- `n8n_workflow_id`, `name`
- `workflow_data` (JSONB)
- `is_active`, `is_archived`

### canonical_workflows
**Purpose**: Git-backed source of truth

**Key Columns**:
- `id` (UUID PK), `tenant_id`
- `canonical_slug`: Human-readable ID
- `name`, `content_hash`
- `workflow_definition` (JSONB)
- `git_file_path`, `provider`

**Migration**: `dcd2f2c8774d_create_canonical_workflow_tables.py`

### workflow_env_map
**Purpose**: Junction table (canonical ↔ environment)

**Key Columns**:
- `id` (UUID PK, surrogate key added later)
- `canonical_id` (UUID FK, nullable)
- `environment_id` (UUID FK)
- `n8n_workflow_id` (text)
- `status`: linked/untracked/missing/ignored/deleted
- `env_content_hash`, `git_content_hash`
- `n8n_updated_at`, `workflow_name`
- `workflow_data` (JSONB, cached)

**Constraints**:
- Unique `(environment_id, n8n_workflow_id)`
- Unique `(canonical_id, environment_id)` WHERE canonical_id NOT NULL

**Indexes**: Performance indexes added in `bf7375f4eb69_add_performance_indexes.py`

**Migration**: `dcd2f2c8774d_create_canonical_workflow_tables.py` + enhancements

### workflow_git_state
**Purpose**: Git sync state tracking

**Key Columns**:
- `canonical_id`, `tenant_id`
- `last_commit_sha`, `last_synced_at`

---

## Execution Tables

### executions
**Purpose**: Workflow execution records

**Key Columns**:
- `id` (UUID PK), `tenant_id`, `environment_id`, `provider`
- `workflow_id`, `workflow_name`
- `n8n_execution_id`
- `normalized_status`: success/error/running/waiting
- `started_at`, `finished_at`, `execution_time` (ms)
- `error_message`, `error_node`
- `mode`: manual/trigger/webhook

**Indexes**: 
- `(tenant_id, environment_id, started_at)`
- `(tenant_id, workflow_id, started_at)`
- Validation index: `20260108_validate_execution_indexes.py`

**Migration**: Base + `20260107_182000_add_execution_analytics_columns.py`

### execution_analytics (deprecated/removed)
**Purpose**: Pre-computed analytics (may have been removed)

**Status**: Migration references exist but implementation unclear

---

## Promotion & Deployment Tables

### pipelines
**Purpose**: Promotion pipeline definitions

**Key Columns**:
- `id` (UUID PK), `tenant_id`, `provider`
- `name`, `description`
- `stages` (JSONB): Array of stage configs with gates
- `is_active` (bool)

### promotions
**Purpose**: Promotion execution records

**Key Columns**:
- `id` (UUID PK), `tenant_id`
- `pipeline_id` (UUID FK)
- `source_environment_id`, `target_environment_id`
- `status`: pending/pending_approval/approved/running/completed/failed
- `workflow_selections` (JSONB)
- `gate_results` (JSONB)
- `source_snapshot_id`, `target_pre_snapshot_id`, `target_post_snapshot_id`
- `execution_result` (JSONB): Results + rollback info
- `created_by`, `approved_by`

### deployments
**Purpose**: Deployment tracking (wrapper around promotions)

**Key Columns**:
- `id` (UUID PK), `tenant_id`
- `promotion_id` (UUID FK)
- `status`: pending/scheduled/running/completed/failed
- `scheduled_for` (timestamp, nullable)
- `started_at`, `finished_at`
- `summary_json` (JSONB)
- `is_deleted` (bool)

**Migration**: Base + `ebd702d672dc_add_deployment_scheduling.py`

### deployment_workflows
**Purpose**: Per-workflow deployment results

**Key Columns**:
- `id` (UUID PK)
- `deployment_id` (UUID FK)
- `workflow_id`, `workflow_name`
- `status`: success/failed/skipped
- `error_message`
- `promoted_at`

### snapshots
**Purpose**: Point-in-time backups

**Key Columns**:
- `id` (UUID PK), `tenant_id`, `environment_id`
- `snapshot_type`: pre_promotion/post_promotion/manual_backup
- `workflows` (JSONB): Workflow data
- `git_commit_sha`
- `created_by`, `created_at`

---

## Drift Management Tables

### drift_incidents
**Purpose**: Drift incident lifecycle

**Key Columns**:
- `id` (UUID PK), `tenant_id`, `environment_id`
- `status`: detected/acknowledged/stabilized/reconciled/closed
- `title`, `summary` (JSONB)
- `detected_at`, `acknowledged_at`, `stabilized_at`, `reconciled_at`, `closed_at`
- `detected_by`, `acknowledged_by`, ..., `closed_by`
- `owner_user_id`, `reason`, `ticket_ref`
- `expires_at`, `severity`: critical/high/medium/low
- `affected_workflows` (JSONB)
- `drift_snapshot` (JSONB): Immutable payload
- `resolution_type`, `resolution_details` (JSONB)
- `payload_purged_at`, `is_deleted`, `deleted_at`

**Migration**: `add_drift_incident_lifecycle.py`, `53259882566d_add_drift_fields_and_incidents.py`

### drift_policies
**Purpose**: Tenant-level drift governance

**Key Columns**:
- `id` (UUID PK), `tenant_id`, `environment_id` (nullable for tenant-wide)
- `severity_ttls` (JSONB): TTL per severity level
- `enforce_ttl`, `enforce_sla` (bool)
- `auto_create_incidents`, `block_on_active_drift` (bool)
- `closed_incident_retention_days`, `reconciliation_artifact_retention_days`

**Migration**: `add_drift_policies_and_approvals.py`, `bf7d3d3c6a89_add_retention_periods_to_drift_policies.py`

### drift_approvals
**Purpose**: Approval workflow for drift operations

**Key Columns**:
- `id` (UUID PK), `incident_id`
- `approval_type`: acknowledge/extend_ttl/close/reconcile
- `status`: pending/approved/rejected
- `requested_by`, `reviewed_by`
- `request_reason`, `review_notes`
- `ttl_extension_hours`
- `created_at`, `reviewed_at`

### drift_check_history
**Purpose**: Historical drift check log

**Key Columns**:
- `id` (UUID PK), `tenant_id`, `environment_id`
- `check_type`: scheduled/manual
- `drift_found` (bool)
- `workflows_checked`, `workflows_with_drift`
- `check_duration_ms`, `checked_at`

**Migration**: `c1a2b3c4d5e6_add_drift_check_history.py`

### reconciliation_artifacts
**Purpose**: Drift reconciliation metadata

**Key Columns**:
- `id` (UUID PK), `incident_id`
- `artifact_type`: snapshot/diff/script
- `artifact_data` (JSONB)
- `created_at`

**Migration**: `add_reconciliation_artifacts.py`

---

## Credential Tables

### credentials
**Purpose**: Credential metadata (NO secrets)

**Key Columns**:
- `id` (UUID PK), `tenant_id`, `environment_id`
- `n8n_credential_id`, `name`, `type`
- `shared_with_projects` (JSONB)

**Security**: Secrets stored in n8n only, never in this DB

### credential_health
**Purpose**: Credential status monitoring

**Key Columns**:
- `id` (UUID PK), `credential_id`
- `last_checked_at`, `status`: healthy/warning/error
- `error_message`

---

## Provider & Subscription Tables

### providers
**Purpose**: Provider definitions (n8n)

**Key Columns**:
- `id` (UUID PK)
- `name`: n8n
- `display_name`, `description`
- `is_active` (bool)

**Migration**: `add_provider_columns.py`

### provider_plans
**Purpose**: Plans per provider

**Key Columns**:
- `id` (UUID PK), `provider_id`
- `name`: free/pro/agency/enterprise
- `display_name`, `monthly_price`, `yearly_price`
- `stripe_price_id_monthly`, `stripe_price_id_yearly`
- `features` (JSONB)
- `is_active` (bool)

### tenant_provider_subscriptions
**Purpose**: Active subscriptions

**Key Columns**:
- `id` (UUID PK), `tenant_id`, `provider_id`, `plan_id`
- `stripe_subscription_id`, `stripe_customer_id`
- `status`: active/cancelled/past_due
- `current_period_start`, `current_period_end`
- `cancel_at_period_end` (bool)

---

## Entitlement Tables

### features
**Purpose**: Feature definitions

**Key Columns**:
- `feature_name` (text PK)
- `display_name`, `description`
- `feature_type`: flag/limit
- `default_value` (JSONB)

**RLS**: Enabled

**Migration**: `84876189e260_create_features_and_plan_features_tables.py`

### plans
**Purpose**: Plan tier definitions

**Key Columns**:
- `id` (UUID PK)
- `name`: free/pro/agency/enterprise
- `display_name`, `precedence` (int)

**Migration**: `f1e2d3c4b5a6_create_plans_table_and_seed.py`

### plan_features
**Purpose**: Feature→Plan mapping

**Key Columns**:
- `plan_id` (UUID FK), `feature_name` (text FK)
- `feature_value` (JSONB): flag (bool) or limit (int)

**RLS**: Enabled

### tenant_plans
**Purpose**: Active plan per tenant/provider

**Key Columns**:
- `tenant_id`, `provider` (composite PK)
- `plan_id` (UUID FK)
- `is_active` (bool)

**Sync**: Synced from `tenant_provider_subscriptions`

**Migration**: `af5ff910eede_sync_tenant_plans_from_provider_subs.py`

### tenant_feature_overrides
**Purpose**: Admin overrides

**Key Columns**:
- `id` (UUID PK), `tenant_id`, `feature_name`
- `override_value` (JSONB)
- `expires_at`, `reason`
- `created_by`, `created_at`

### downgrade_grace_periods
**Purpose**: Grace period tracking for downgrades

**Key Columns**:
- `id` (UUID PK), `tenant_id`
- `resource_type`: environment/team_member
- `resource_id`, `grace_period_days`
- `expires_at`, `status`: active/completed/cancelled
- `action`: read_only/disable/schedule_deletion
- `notified_at`

**Migration**: `380513d302f0_add_downgrade_grace_periods_table.py`

---

## Admin & Audit Tables

### audit_logs
**Purpose**: Comprehensive action audit trail

**Key Columns**:
- `id` (UUID PK), `tenant_id`
- `action_type`, `action`
- `actor_id`: User who performed action
- `impersonated_user_id`: If impersonation (nullable)
- `impersonation_session_id`: Session ID (nullable)
- `resource_type`, `resource_id`
- `old_value`, `new_value` (JSONB)
- `metadata` (JSONB)
- `ip_address`, `user_agent`
- `provider` (text)
- `created_at`

**Indexes**: `add_audit_log_impersonation_index.py`, `add_provider_to_audit_logs.py`

### platform_admins
**Purpose**: Platform admin designation

**Key Columns**:
- `user_id` (UUID PK)
- `created_at`

**Migration**: `98c25037a560_create_platform_admins_table.py`

### platform_impersonation_sessions
**Purpose**: Impersonation session tracking

**Key Columns**:
- `id` (UUID PK)
- `actor_user_id`, `impersonated_user_id`, `impersonated_tenant_id`
- `started_at`, `ended_at` (nullable while active)
- `ip_address`, `user_agent`

**Migration**: `9ed964cd8ba3_create_platform_impersonation_sessions.py`

---

## Background Job Tables

### background_jobs
**Purpose**: Async job tracking

**Key Columns**:
- `id` (UUID PK), `tenant_id`
- `job_type`: sync/promotion/deployment/onboarding
- `status`: pending/running/completed/failed
- `resource_type`, `resource_id`
- `progress` (JSONB): `{current, total, percentage, message}`
- `metadata` (JSONB)
- `started_at`, `completed_at`

**Migration**: `dd6be28dfaab_add_metadata_to_background_jobs.py`

---

## Support & Notification Tables

### support_tickets
**Purpose**: User support requests

**Key Columns**:
- `id` (UUID PK), `tenant_id`
- `ticket_type`: bug/feature/help
- `subject`, `description`
- `status`: open/in_progress/resolved/closed
- `priority`: low/medium/high/urgent
- `created_by`, `assigned_to`

**Migration**: `947a226f2ac2_add_support_storage_and_attachments.py`

### notification_channels
**Purpose**: Notification delivery config

**Key Columns**:
- `id` (UUID PK), `tenant_id`
- `channel_type`: slack/email/webhook
- `config` (JSONB): URL, credentials
- `is_enabled` (bool)

### notification_rules
**Purpose**: Event→Channel routing

**Key Columns**:
- `id` (UUID PK), `tenant_id`
- `event_type`: deployment.completed, drift.detected
- `channel_ids` (JSONB array)
- `is_enabled` (bool)

---

## Configuration Tables

### environment_types
**Purpose**: Tenant-configurable environment classes

**Key Columns**:
- `id` (UUID PK), `tenant_id`
- `name`, `slug`
- `is_default` (bool)

**Migration**: `6e708cffe3a7_create_environment_types_table.py`

### workflow_policy_matrix
**Purpose**: Action policies per environment class

**Key Columns**:
- `environment_class`, `action_type`
- `policy`: allowed/warning/blocked/requires_approval

**Migration**: `245ecb3e319b_create_workflow_policy_matrix.py`

### plan_feature_requirements
**Purpose**: Which features require which plans

**Key Columns**:
- `feature_name`, `minimum_plan_id`

**Migration**: `9bc1bdfc90a0_create_plan_feature_requirements.py`

### plan_limits
**Purpose**: Numeric limits per plan

**Key Columns**:
- `plan_id`, `limit_name`
- `limit_value` (int, -1 = unlimited)

**Migration**: `be70defcb0d7_create_plan_limits_and_retention.py`

---

## RLS Notes

**Status**: ✅ RLS documented (2026-01-08)

**Coverage**: 12 of 76 tables have RLS enabled (15.8%)

**Documentation**: [`n8n-ops-backend/docs/security/RLS_POLICIES.md`](../n8n-ops-backend/docs/security/RLS_POLICIES.md)

**Pattern**: Standard tenant isolation uses `tenant_id = current_setting('app.tenant_id', true)::uuid`

**Risk**: Configuration drift between Supabase dashboard and codebase

**Recommendation**: Export all RLS policies to SQL files for version control

---

## Key Constraints & Indexes

### Performance Indexes
**Migration**: `bf7375f4eb69_add_performance_indexes.py`
- Likely covers: executions (time-range queries), workflow_env_map (lookups), promotions

### Unique Constraints
- `(tenant_id, name)` on many tables (environments, pipelines, etc.)
- `(environment_id, n8n_workflow_id)` on workflow_env_map
- `(canonical_id, environment_id)` on workflow_env_map (when canonical_id NOT NULL)

### Foreign Keys
- All tables with `tenant_id` → `tenants(id)`
- Most tables with `environment_id` → `environments(id)`
- Cascading deletes NOT universally applied (risk of orphaned records)

---

## Migration Highlights

### Critical Migrations
1. `dcd2f2c8774d_create_canonical_workflow_tables.py` - Canonical system
2. `add_drift_incident_lifecycle.py` - Drift management
3. `9ed964cd8ba3_create_platform_impersonation_sessions.py` - Impersonation
4. `add_provider_columns.py` - Multi-provider architecture
5. `20260107_182000_add_execution_analytics_columns.py` - Execution analytics
6. `bf7375f4eb69_add_performance_indexes.py` - Performance optimization

### Merge Migrations
- `855f0d7fe1de_merge_analytics_and_features.py`
- `0d3cc810ee1a_merge_heads.py`
- `3c4da474d855_merge_provider_and_tenant_fix.py`

### Cleanup Migrations
- `f540a798f456_fix_mock_tenant_id_records.py` - Data cleanup
- `d393b8991c99_sync_tenant_plans_with_subscription_tier.py` - Data sync

---

## Gaps & Risks

1. **RLS Policies Not in Repo**: Critical security config not version-controlled

2. **Cascade Delete Unclear**: Foreign key cascades not comprehensively defined

3. **Index Coverage**: Performance indexes exist but coverage unclear for all query patterns

4. **JSONB Column Limits**: Max sizes for workflow_data, drift_snapshot, metadata columns untested

5. **Table Bloat**: No documented vacuum/analyze strategy for high-churn tables (executions, audit_logs)

