# T002: Database Schema Documentation
## Workflows, Environments, and Mappings

**Task ID**: T002
**Description**: Document database schema for workflows, environments, and mappings
**Primary Files**: `alembic/versions/*.py`, `app/schemas/*.py`
**Migration References**: See inline citations throughout document

---

## Table of Contents

1. [Core Canonical Workflow System](#1-core-canonical-workflow-system)
2. [Environment Tables](#2-environment-tables)
3. [Drift Management Tables](#3-drift-management-tables)
4. [Deployment & Promotion Tables](#4-deployment--promotion-tables)
5. [Background Jobs & Sync](#5-background-jobs--sync)
6. [Identity & Mapping Rules](#6-identity--mapping-rules)
7. [Foreign Key Relationships](#7-foreign-key-relationships)
8. [Indexes & Performance](#8-indexes--performance)
9. [Migration Timeline](#9-migration-timeline)

---

## 1. Core Canonical Workflow System

The canonical workflow system is the heart of the WorkflowOps architecture, providing Git-backed source of truth for workflows across multiple environments.

### 1.1 `canonical_workflows`

**Purpose**: Identity-only table for canonical workflows. Represents the universal identity of a workflow that can exist across multiple environments.

**Migration**: `dcd2f2c8774d_create_canonical_workflow_tables.py` (lines 46-57)

**Table Structure**:
```sql
CREATE TABLE canonical_workflows (
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    canonical_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by_user_id UUID NULL,
    display_name TEXT NULL,
    deleted_at TIMESTAMPTZ NULL,
    PRIMARY KEY (tenant_id, canonical_id)
);
```

**Key Columns**:
- `tenant_id` (UUID, FK): Tenant isolation root
- `canonical_id` (UUID): Universal workflow identifier across environments
- `created_at` (TIMESTAMPTZ): Workflow creation timestamp
- `created_by_user_id` (UUID, nullable): User who created this canonical workflow
- `display_name` (TEXT, nullable): Human-readable workflow name
- `deleted_at` (TIMESTAMPTZ, nullable): Soft delete timestamp

**Constraints**:
- Primary Key: `(tenant_id, canonical_id)`
- Foreign Key: `tenant_id → tenants(id)` with CASCADE delete
- RLS: Enabled with tenant isolation policy (line 213-220)

**Indexes**:
- `idx_canonical_workflows_tenant` on `tenant_id` (line 137-139)
- `idx_canonical_workflows_created_at` on `created_at DESC` (line 140-143)
- `idx_canonical_workflows_deleted_at` on `deleted_at` WHERE NOT NULL (line 144-147)

**Schema Reference**: `app/schemas/canonical_workflow.py:102-123`

---

### 1.2 `canonical_workflow_git_state`

**Purpose**: Per-environment Git state tracking for canonical workflows. Stores Git-specific metadata including commit SHA, content hash, and file path.

**Migration**: `dcd2f2c8774d_create_canonical_workflow_tables.py` (lines 59-74)

**Table Structure**:
```sql
CREATE TABLE canonical_workflow_git_state (
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    canonical_id UUID NOT NULL,
    git_path TEXT NOT NULL,
    git_commit_sha TEXT NULL,
    git_content_hash TEXT NOT NULL,
    last_repo_sync_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, environment_id, canonical_id),
    FOREIGN KEY (tenant_id, canonical_id)
        REFERENCES canonical_workflows(tenant_id, canonical_id)
        ON DELETE CASCADE
);
```

**Key Columns**:
- `tenant_id` (UUID, FK): Tenant isolation
- `environment_id` (UUID, FK): Which environment's Git repo this state refers to
- `canonical_id` (UUID, FK): Reference to canonical workflow identity
- `git_path` (TEXT): File path in Git repository (e.g., `workflows/dev/my-workflow.json`)
- `git_commit_sha` (TEXT, nullable): Last Git commit SHA where this workflow was synced
- `git_content_hash` (TEXT): Content-based hash for change detection
- `last_repo_sync_at` (TIMESTAMPTZ): Timestamp of last Git sync operation

**Constraints**:
- Primary Key: `(tenant_id, environment_id, canonical_id)`
- Foreign Key: `tenant_id → tenants(id)` CASCADE
- Foreign Key: `environment_id → environments(id)` CASCADE
- Foreign Key: `(tenant_id, canonical_id) → canonical_workflows` CASCADE
- RLS: Enabled with tenant isolation policy (line 222-229)

**Indexes**:
- `idx_canonical_git_state_tenant_env` on `(tenant_id, environment_id)` (line 150-153)
- `idx_canonical_git_state_canonical` on `canonical_id` (line 154-157)

**Schema Reference**: `app/schemas/canonical_workflow.py:127-145`

---

### 1.3 `workflow_env_map`

**Purpose**: Environment mapping table that connects canonical workflows to runtime n8n instances. This is the junction table that enables multi-environment workflow tracking.

**Migrations**:
- Base: `dcd2f2c8774d_create_canonical_workflow_tables.py` (lines 76-93)
- Surrogate PK: `3e894b287688_add_surrogate_pk_to_workflow_env_map.py` (lines 20-82)
- Workflow Data: `6a78a8d07b5e_add_workflow_data_to_env_map.py` (lines 18-31)
- n8n timestamp: `d27bdb540fcc_add_n8n_updated_at_to_workflow_env_map.py`
- Query optimization: `20260107_075803_optimize_workflow_env_map_queries.py`

**Table Structure** (final state):
```sql
CREATE TABLE workflow_env_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- Added in 3e894b287688
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    canonical_id UUID NULL, -- Nullable: NULL = UNTRACKED workflow
    n8n_workflow_id TEXT NULL,
    env_content_hash TEXT NOT NULL,
    last_env_sync_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    linked_at TIMESTAMPTZ NULL,
    linked_by_user_id UUID NULL,
    status TEXT NULL CHECK (status IN ('linked', 'ignored', 'deleted', 'untracked', 'missing')),
    workflow_data JSONB NULL, -- Added in 6a78a8d07b5e, cached full workflow JSON
    n8n_updated_at TIMESTAMPTZ NULL, -- Added in d27bdb540fcc
    FOREIGN KEY (tenant_id, canonical_id)
        REFERENCES canonical_workflows(tenant_id, canonical_id)
        ON DELETE CASCADE
);
```

**Key Columns**:
- `id` (UUID): Surrogate primary key (added 2026-01-06, replaced composite PK)
- `tenant_id` (UUID, FK): Tenant isolation
- `environment_id` (UUID, FK): Which n8n environment this workflow exists in
- `canonical_id` (UUID, FK, **NULLABLE**): Canonical workflow reference; NULL = UNTRACKED
- `n8n_workflow_id` (TEXT, nullable): n8n runtime workflow ID (string/numeric)
- `env_content_hash` (TEXT): Hash of workflow content in this environment
- `last_env_sync_at` (TIMESTAMPTZ): Last sync from n8n runtime to DB
- `linked_at` (TIMESTAMPTZ, nullable): When workflow was linked to canonical identity
- `linked_by_user_id` (UUID, nullable): User who performed linking action
- `status` (TEXT ENUM, nullable): Workflow mapping status (see Status Enum below)
- `workflow_data` (JSONB, nullable): Cached full workflow JSON for UI rendering
- `n8n_updated_at` (TIMESTAMPTZ, nullable): Last modified timestamp from n8n

**Status Enum Values** (from `app/schemas/canonical_workflow.py:7-80`):

| Status | Meaning | canonical_id | n8n_workflow_id | Use Case |
|--------|---------|--------------|-----------------|----------|
| `linked` | Canonically tracked workflow | NOT NULL | NOT NULL | Normal operational state |
| `untracked` | Runtime workflow without canonical identity | NULL | NOT NULL | New workflow awaiting linking |
| `missing` | Previously mapped but disappeared from n8n | any | any | Workflow deleted in n8n |
| `ignored` | Explicitly excluded from tracking | any | any | User-marked ignore |
| `deleted` | Soft-deleted mapping | any | any | Audit trail retention |

**Status Precedence Rules** (app/schemas/canonical_workflow.py:33-54):
1. **DELETED** (highest) - Takes precedence over all other states
2. **IGNORED** - User-explicit ignore overrides operational states
3. **MISSING** - Workflow disappeared from n8n during sync
4. **UNTRACKED** - No canonical_id assigned
5. **LINKED** (default) - Has both canonical_id and n8n_workflow_id

**Constraints**:
- Primary Key: `id` (UUID)
- Unique: `(tenant_id, environment_id, canonical_id)` (original composite key maintained as unique index)
- Foreign Key: `tenant_id → tenants(id)` CASCADE
- Foreign Key: `environment_id → environments(id)` CASCADE
- Foreign Key: `(tenant_id, canonical_id) → canonical_workflows` CASCADE
- RLS: Enabled with tenant isolation policy (line 231-238)

**Indexes**:
- `idx_workflow_env_map_tenant_env` on `(tenant_id, environment_id)` (line 160-163)
- `idx_workflow_env_map_canonical` on `canonical_id` (line 164-167)
- `idx_workflow_env_map_n8n_id` on `n8n_workflow_id` WHERE NOT NULL (line 168-172)
- `idx_workflow_env_map_status` on `status` WHERE NOT NULL (line 173-177)
- `idx_workflow_env_map_last_sync` on `last_env_sync_at DESC` (line 178-181)
- `idx_workflow_env_map_workflow_data` (GIN) on `workflow_data` WHERE NOT NULL (6a78a8d07b5e:27-30)

**Schema Reference**: `app/schemas/canonical_workflow.py:149-187`

**Identity Rules**:
- **UNTRACKED workflows**: `canonical_id IS NULL AND n8n_workflow_id IS NOT NULL`
- **LINKED workflows**: `canonical_id IS NOT NULL AND n8n_workflow_id IS NOT NULL AND status = 'linked'`
- **Drift detection**: Compare `env_content_hash` vs `git_content_hash` from canonical_workflow_git_state

---

### 1.4 `workflow_link_suggestions`

**Purpose**: Auto-generated suggestions for linking UNTRACKED workflows to canonical identities based on similarity scoring.

**Migration**: `dcd2f2c8774d_create_canonical_workflow_tables.py` (lines 95-115)

**Table Structure**:
```sql
CREATE TABLE workflow_link_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    environment_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    n8n_workflow_id TEXT NOT NULL,
    canonical_id UUID NOT NULL,
    score NUMERIC NOT NULL,
    reason TEXT NULL,
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'accepted', 'rejected', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ NULL,
    resolved_by_user_id UUID NULL,
    FOREIGN KEY (tenant_id, canonical_id)
        REFERENCES canonical_workflows(tenant_id, canonical_id)
        ON DELETE CASCADE,
    UNIQUE(tenant_id, environment_id, n8n_workflow_id, canonical_id)
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id`, `environment_id` (UUID, FK): Location context
- `n8n_workflow_id` (TEXT): UNTRACKED workflow in runtime
- `canonical_id` (UUID, FK): Suggested canonical workflow to link
- `score` (NUMERIC): Similarity score (0.0-1.0, higher = more confident)
- `reason` (TEXT, nullable): Explanation for suggestion (e.g., "Name match: 95%")
- `status` (TEXT ENUM): open, accepted, rejected, expired
- `created_at` (TIMESTAMPTZ): When suggestion was generated
- `resolved_at` (TIMESTAMPTZ, nullable): When user acted on suggestion
- `resolved_by_user_id` (UUID, nullable): User who resolved suggestion

**Constraints**:
- Unique: `(tenant_id, environment_id, n8n_workflow_id, canonical_id)`
- Foreign Key: `tenant_id → tenants(id)` CASCADE
- Foreign Key: `(tenant_id, canonical_id) → canonical_workflows` CASCADE
- RLS: Enabled with tenant isolation policy (line 240-247)

**Indexes**:
- `idx_workflow_link_suggestions_tenant_env` on `(tenant_id, environment_id)` (line 184-187)
- `idx_workflow_link_suggestions_status` on `status` WHERE status = 'open' (line 188-192)
- `idx_workflow_link_suggestions_created` on `created_at DESC` (line 193-196)

**Schema Reference**: `app/schemas/canonical_workflow.py:189-224`

---

### 1.5 `workflow_diff_state`

**Purpose**: Cached diff computation between source and target environments for promotion workflows. Enables incremental diff updates.

**Migrations**:
- Base: `dcd2f2c8774d_create_canonical_workflow_tables.py` (lines 117-133)
- Hash columns: `20260111_add_workflow_diff_state_columns.py` (lines 24-69)

**Table Structure**:
```sql
CREATE TABLE workflow_diff_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_env_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    target_env_id UUID NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    canonical_id UUID NOT NULL,
    diff_status TEXT NOT NULL
        CHECK (diff_status IN ('unchanged', 'modified', 'added', 'target_only', 'target_hotfix', 'conflict')),
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_git_hash TEXT NULL,      -- Added in 20260111
    target_git_hash TEXT NULL,      -- Added in 20260111
    source_env_hash TEXT NULL,      -- Added in 20260111
    target_env_hash TEXT NULL,      -- Added in 20260111
    conflict_metadata JSONB NULL,   -- Added in 20260111
    FOREIGN KEY (tenant_id, canonical_id)
        REFERENCES canonical_workflows(tenant_id, canonical_id)
        ON DELETE CASCADE,
    UNIQUE(tenant_id, source_env_id, target_env_id, canonical_id)
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id`, `source_env_id`, `target_env_id` (UUID, FK): Comparison context
- `canonical_id` (UUID, FK): Workflow being compared
- `diff_status` (TEXT ENUM): Diff computation result
- `computed_at` (TIMESTAMPTZ): Last diff computation timestamp
- `source_git_hash` (TEXT, nullable): Git content hash at source
- `target_git_hash` (TEXT, nullable): Git content hash at target
- `source_env_hash` (TEXT, nullable): Runtime content hash at source
- `target_env_hash` (TEXT, nullable): Runtime content hash at target
- `conflict_metadata` (JSONB, nullable): Conflict resolution metadata

**Diff Status Values** (app/schemas/canonical_workflow.py:90-98):

| Status | Meaning | Promotion Action |
|--------|---------|------------------|
| `unchanged` | Content identical in source and target | Skip promotion |
| `modified` | Changes exist in source vs target | Promote changes |
| `added` | New in source, not in target | Add to target |
| `target_only` | Exists in target but not source | Potential orphan |
| `target_hotfix` | Target has changes not in source (drift) | Conflict warning |
| `conflict` | Both source and target have divergent changes | Manual resolution required |

**Constraints**:
- Unique: `(tenant_id, source_env_id, target_env_id, canonical_id)`
- Foreign Key: `tenant_id → tenants(id)` CASCADE
- Foreign Key: `source_env_id → environments(id)` CASCADE
- Foreign Key: `target_env_id → environments(id)` CASCADE
- Foreign Key: `(tenant_id, canonical_id) → canonical_workflows` CASCADE
- RLS: Enabled with tenant isolation policy (line 249-256)

**Indexes**:
- `idx_workflow_diff_state_tenant_envs` on `(tenant_id, source_env_id, target_env_id)` (line 199-202)
- `idx_workflow_diff_state_canonical` on `canonical_id` (line 203-206)
- `idx_workflow_diff_state_computed` on `computed_at DESC` (line 207-210)
- `idx_workflow_diff_state_conflict` on `diff_status` WHERE diff_status = 'conflict' (20260111:64-68)

**Schema Reference**: `app/schemas/canonical_workflow.py:226-249`

---

## 2. Environment Tables

### 2.1 `environments`

**Purpose**: Connected n8n/provider runtime instances. Each environment represents a separate n8n deployment (dev, staging, production).

**Migrations**:
- Base table: (Not found in scanned migrations; likely pre-canonical)
- Drift fields: `53259882566d_add_drift_fields_and_incidents.py` (line 20)
- Git folder: `dcd2f2c8774d_create_canonical_workflow_tables.py` (lines 40-44)
- Environment class: `add_environment_class.py` (lines 20-36)
- Policy flags: `10bc9f88fc9c_add_policy_flags_to_environments.py` (line 20)
- Drift handling mode: `76c6e9c7f4fe_add_drift_handling_mode_to_environments.py`
- Timestamps: `f1b00536558e_add_environment_timestamp_columns.py`

**Table Structure** (inferred from migrations + schemas):
```sql
CREATE TABLE environments (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    n8n_name TEXT NOT NULL,
    n8n_type TEXT NULL, -- Optional metadata for display/sorting only
    n8n_base_url TEXT NOT NULL,
    n8n_api_key TEXT NULL,
    n8n_encryption_key TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    allow_upload BOOLEAN NOT NULL DEFAULT FALSE,
    environment_class TEXT NOT NULL DEFAULT 'dev', -- dev/staging/production
    git_repo_url TEXT NULL,
    git_branch TEXT NULL,
    git_pat TEXT NULL,
    git_folder TEXT NULL, -- Added in dcd2f2c8774d
    last_connected TIMESTAMPTZ NULL,
    last_backup TIMESTAMPTZ NULL,
    last_heartbeat_at TIMESTAMPTZ NULL,
    last_drift_check_at TIMESTAMPTZ NULL,
    last_sync_at TIMESTAMPTZ NULL,
    drift_status TEXT NOT NULL DEFAULT 'IN_SYNC', -- Added in 53259882566d
    last_drift_detected_at TIMESTAMPTZ NULL,      -- Added in 53259882566d
    active_drift_incident_id UUID NULL,            -- Added in 53259882566d
    drift_handling_mode TEXT NOT NULL DEFAULT 'warn_only',
    policy_flags JSONB NOT NULL DEFAULT '{}'::jsonb, -- Added in 10bc9f88fc9c
    workflow_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, n8n_name)
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID, FK): Tenant isolation
- `n8n_name` (TEXT): Display name for environment
- `n8n_type` (TEXT, nullable): Optional metadata (deprecated for policy enforcement)
- `n8n_base_url` (TEXT): n8n API endpoint
- `n8n_api_key` (TEXT, nullable): Encrypted API key
- `n8n_encryption_key` (TEXT, nullable): n8n credential encryption key
- `is_active` (BOOLEAN): Whether environment is enabled
- `allow_upload` (BOOLEAN): Feature flag for workflow uploads
- `environment_class` (TEXT ENUM): **ONLY source of truth for policy enforcement** (dev/staging/production)
- `git_repo_url` (TEXT, nullable): GitHub repository URL
- `git_branch` (TEXT, nullable): Git branch for this environment
- `git_pat` (TEXT, nullable): GitHub Personal Access Token
- `git_folder` (TEXT, nullable): Subfolder in Git repo for this environment's workflows
- `drift_status` (TEXT): Current drift state (IN_SYNC, DRIFT_DETECTED, DRIFT_INCIDENT_ACTIVE, etc.)
- `last_drift_detected_at` (TIMESTAMPTZ, nullable): Last time drift was detected
- `active_drift_incident_id` (UUID, nullable): FK to active drift incident
- `drift_handling_mode` (TEXT): warn_only, manual_override, require_attestation
- `policy_flags` (JSONB): Tenant-specific policy overrides
- `workflow_count` (INTEGER): Cached workflow count for this environment

**Environment Class** (app/schemas/environment.py:17-21):
```python
class EnvironmentClass(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"
```

**CRITICAL NOTE** (from migration `add_environment_class.py:7-8`):
> "environment_class is the ONLY source of truth for policy enforcement. After this migration, NEVER infer environment class at runtime."

**Drift Status Values** (from `app/schemas/environment.py:81`):
- `IN_SYNC`: No drift detected
- `DRIFT_DETECTED`: Drift detected but no incident created
- `DRIFT_INCIDENT_ACTIVE`: Active drift incident exists

**Constraints**:
- Unique: `(tenant_id, n8n_name)`
- Foreign Key: `tenant_id → tenants(id)`

**Schema Reference**: `app/schemas/environment.py:23-101`

---

### 2.2 `environment_types`

**Purpose**: Tenant-configurable environment type ordering and labels (UI customization).

**Migration**: `6e708cffe3a7_create_environment_types_table.py` (lines 22-45)

**Table Structure**:
```sql
CREATE TABLE environment_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    key TEXT NOT NULL,
    label TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, key)
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID, FK): Tenant isolation
- `key` (TEXT): Environment type key (e.g., "dev", "staging", "production")
- `label` (TEXT): Display label (e.g., "Development", "Staging", "Production")
- `sort_order` (INTEGER): Sort order for UI display
- `is_active` (BOOLEAN): Whether this type is active

**Default Seed Values** (from `app/services/database.py:150-154`):
```python
defaults = [
    {"tenant_id": tenant_id, "key": "dev", "label": "Development", "sort_order": 10, "is_active": True},
    {"tenant_id": tenant_id, "key": "staging", "label": "Staging", "sort_order": 20, "is_active": True},
    {"tenant_id": tenant_id, "key": "production", "label": "Production", "sort_order": 30, "is_active": True},
]
```

**Constraints**:
- Unique: `(tenant_id, key)`

**Indexes**:
- `environment_types_tenant_key_unique` on `(tenant_id, key)` (line 36-39)
- `environment_types_tenant_sort_idx` on `(tenant_id, sort_order)` (line 42-45)

**Schema Reference**: `app/schemas/environment_type.py`

---

## 3. Drift Management Tables

### 3.1 `drift_incidents`

**Purpose**: Drift incident lifecycle management. Tracks when runtime workflows diverge from Git source of truth.

**Migrations**:
- Base: `53259882566d_add_drift_fields_and_incidents.py` (line 20)
- Lifecycle: `add_drift_incident_lifecycle.py` (lines 18-62)
- Payloads: `d2e3f4a5b6c7_add_incident_payloads_and_soft_delete.py`

**Table Structure**:
```sql
CREATE TABLE drift_incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    environment_id UUID NOT NULL,
    status TEXT NOT NULL DEFAULT 'detected',
    title TEXT NULL,
    summary JSONB NULL,
    created_by UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Lifecycle timestamps
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ NULL,
    acknowledged_by UUID NULL,
    stabilized_at TIMESTAMPTZ NULL,
    stabilized_by UUID NULL,
    reconciled_at TIMESTAMPTZ NULL,
    reconciled_by UUID NULL,
    closed_at TIMESTAMPTZ NULL,
    closed_by UUID NULL,

    -- Ownership and metadata
    owner_user_id UUID NULL,
    reason TEXT NULL,
    ticket_ref TEXT NULL,

    -- Agency+ fields (TTL/SLA)
    expires_at TIMESTAMPTZ NULL,
    severity VARCHAR(20) NULL,
    expiration_warning_sent BOOLEAN DEFAULT false,

    -- Drift snapshot data
    affected_workflows JSONB NOT NULL DEFAULT '[]',
    drift_snapshot JSONB NULL,

    -- Resolution tracking
    resolution_type VARCHAR(50) NULL,
    resolution_details JSONB NULL,

    -- Retention/soft-delete
    payload_purged_at TIMESTAMPTZ NULL,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMPTZ NULL
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id`, `environment_id` (UUID, FK): Location context
- `status` (TEXT ENUM): Incident lifecycle state (see Status Lifecycle below)
- `title` (TEXT, nullable): Human-readable incident title
- `summary` (JSONB, nullable): Incident summary metadata
- `detected_at` (TIMESTAMPTZ): When drift was first detected
- `acknowledged_at/by` (TIMESTAMPTZ/UUID, nullable): When incident was acknowledged
- `stabilized_at/by` (TIMESTAMPTZ/UUID, nullable): When drift stabilized (stopped changing)
- `reconciled_at/by` (TIMESTAMPTZ/UUID, nullable): When reconciliation completed
- `closed_at/by` (TIMESTAMPTZ/UUID, nullable): When incident was closed
- `owner_user_id` (UUID, nullable): Assigned owner
- `reason` (TEXT, nullable): Explanation for incident
- `ticket_ref` (TEXT, nullable): External ticket reference
- `expires_at` (TIMESTAMPTZ, nullable): Agency+ TTL expiration
- `severity` (VARCHAR ENUM, nullable): Severity level (critical/high/medium/low)
- `affected_workflows` (JSONB): List of workflows affected by drift
- `drift_snapshot` (JSONB, nullable): Immutable snapshot of drift state at detection
- `resolution_type` (VARCHAR ENUM, nullable): How incident was resolved
- `resolution_details` (JSONB, nullable): Detailed resolution metadata
- `payload_purged_at` (TIMESTAMPTZ, nullable): Timestamp when drift_snapshot was purged per retention policy

**Status Lifecycle** (app/schemas/drift_incident.py:8-14):
```python
class DriftIncidentStatus(str, Enum):
    detected = "detected"         # Initial state: drift detected
    acknowledged = "acknowledged" # User has acknowledged incident
    stabilized = "stabilized"     # Drift has stopped changing
    reconciled = "reconciled"     # Drift resolved (promoted/reverted/replaced)
    closed = "closed"             # Incident closed
```

**Severity Levels** (app/schemas/drift_incident.py:17-23):
```python
class DriftSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"
```

**Resolution Types** (app/schemas/drift_incident.py:25-31):
```python
class ResolutionType(str, Enum):
    promote = "promote"       # Runtime changes promoted to Git
    revert = "revert"         # Runtime reverted to match Git
    replace = "replace"       # Git updated via external process
    acknowledge = "acknowledge"  # Drift accepted (no reconciliation)
```

**State Transition Rules** (from `app/schemas/drift_incident.py`):
- `detected` → `acknowledged`: User acknowledges incident
- `acknowledged` → `stabilized`: Drift stops changing
- `stabilized` → `reconciled`: Reconciliation action taken
- `reconciled` → `closed`: Incident closed with resolution
- Any state → `closed` (with admin_override flag)

**Indexes**:
- `idx_drift_incidents_tenant` on `tenant_id` (add_drift_lifecycle:58)
- `idx_drift_incidents_environment` on `environment_id` (add_drift_lifecycle:59)
- `idx_drift_incidents_status` on `status` (add_drift_lifecycle:60)
- `idx_drift_incidents_detected_at` on `detected_at` (add_drift_lifecycle:61)

**Schema Reference**: `app/schemas/drift_incident.py:42-177`

---

### 3.2 `drift_policies`

**Purpose**: Tenant-level drift governance policies (TTL/SLA enforcement, auto-incident creation, deployment blocking).

**Migrations**:
- Base: `add_drift_policies_and_approvals.py` (lines 20-50)
- Retention: `bf7d3d3c6a89_add_retention_periods_to_drift_policies.py`

**Table Structure**:
```sql
CREATE TABLE drift_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL UNIQUE,

    -- TTL settings by severity (in hours)
    default_ttl_hours INTEGER DEFAULT 72,
    critical_ttl_hours INTEGER DEFAULT 24,
    high_ttl_hours INTEGER DEFAULT 48,
    medium_ttl_hours INTEGER DEFAULT 72,
    low_ttl_hours INTEGER DEFAULT 168,

    -- Auto-incident creation
    auto_create_incidents BOOLEAN DEFAULT false,
    auto_create_for_production_only BOOLEAN DEFAULT true,

    -- Enforcement settings
    block_deployments_on_expired BOOLEAN DEFAULT false,
    block_deployments_on_drift BOOLEAN DEFAULT false,

    -- Notification settings
    notify_on_detection BOOLEAN DEFAULT true,
    notify_on_expiration_warning BOOLEAN DEFAULT true,
    expiration_warning_hours INTEGER DEFAULT 24,

    -- Retention periods (added in bf7d3d3c6a89)
    closed_incident_retention_days INTEGER DEFAULT 90,
    reconciliation_artifact_retention_days INTEGER DEFAULT 30,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID, UNIQUE): One policy per tenant
- `default_ttl_hours` (INTEGER): Default time-to-live for drift incidents
- `critical_ttl_hours` ... `low_ttl_hours` (INTEGER): TTL per severity level
- `auto_create_incidents` (BOOLEAN): Automatically create incidents on drift detection
- `auto_create_for_production_only` (BOOLEAN): Only auto-create for production environments
- `block_deployments_on_expired` (BOOLEAN): Block promotions if TTL expired
- `block_deployments_on_drift` (BOOLEAN): Block promotions if active drift exists
- `notify_on_detection` (BOOLEAN): Send notifications on drift detection
- `notify_on_expiration_warning` (BOOLEAN): Warn before TTL expiration
- `expiration_warning_hours` (INTEGER): Hours before expiration to send warning
- `closed_incident_retention_days` (INTEGER): Days to retain closed incidents
- `reconciliation_artifact_retention_days` (INTEGER): Days to retain reconciliation artifacts

**Constraints**:
- Unique: `tenant_id`

**Indexes**:
- `idx_drift_policies_tenant` on `tenant_id` (add_drift_policies:50)

**Predefined Templates** (add_drift_policies:99-124):
- **Strict**: 24hr default TTL, blocks deployments on drift
- **Standard**: 72hr default TTL, blocks deployments on expired TTL only
- **Relaxed**: 168hr default TTL, no blocking

---

### 3.3 `drift_approvals`

**Purpose**: Approval workflow for drift operations (acknowledge, extend TTL, close, reconcile).

**Migration**: `add_drift_policies_and_approvals.py` (lines 52-78)

**Table Structure**:
```sql
CREATE TABLE drift_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    incident_id UUID NOT NULL REFERENCES drift_incidents(id) ON DELETE CASCADE,

    approval_type VARCHAR(20) NOT NULL,  -- 'acknowledge', 'extend_ttl', 'close', 'reconcile'
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'cancelled'

    requested_by UUID NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_reason TEXT,

    decided_by UUID NULL,
    decided_at TIMESTAMPTZ NULL,
    decision_notes TEXT NULL,

    -- For TTL extensions
    extension_hours INTEGER NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID, FK): Tenant isolation
- `incident_id` (UUID, FK): Reference to drift incident
- `approval_type` (VARCHAR ENUM): acknowledge, extend_ttl, close, reconcile
- `status` (VARCHAR ENUM): pending, approved, rejected, cancelled
- `requested_by` (UUID): User requesting approval
- `requested_at` (TIMESTAMPTZ): Request timestamp
- `request_reason` (TEXT, nullable): Justification for request
- `decided_by` (UUID, nullable): User who approved/rejected
- `decided_at` (TIMESTAMPTZ, nullable): Decision timestamp
- `decision_notes` (TEXT, nullable): Approval/rejection notes
- `extension_hours` (INTEGER, nullable): Hours to extend TTL (for extend_ttl type)

**Constraints**:
- Foreign Key: `incident_id → drift_incidents(id)` CASCADE delete

**Indexes**:
- `idx_drift_approvals_tenant` on `tenant_id` (add_drift_policies:76)
- `idx_drift_approvals_incident` on `incident_id` (add_drift_policies:77)
- `idx_drift_approvals_status` on `status` (add_drift_policies:78)

---

### 3.4 `drift_reconciliation_artifacts`

**Purpose**: Tracks reconciliation actions taken to resolve drift incidents (promote, revert, replace).

**Migration**: `add_reconciliation_artifacts.py` (lines 19-48)

**Table Structure**:
```sql
CREATE TABLE drift_reconciliation_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    incident_id UUID NOT NULL REFERENCES drift_incidents(id) ON DELETE CASCADE,

    type VARCHAR(20) NOT NULL,  -- 'promote', 'revert', 'replace'
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'in_progress', 'success', 'failed'

    started_at TIMESTAMPTZ NULL,
    started_by UUID NULL,
    finished_at TIMESTAMPTZ NULL,

    -- External references (hidden from UI, but tracked)
    external_refs JSONB DEFAULT '{}',
    -- { commit_sha, pr_url, deployment_run_id, etc. }

    -- Affected workflows for this reconciliation
    affected_workflows JSONB DEFAULT '[]',

    error_message TEXT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID, FK): Tenant isolation
- `incident_id` (UUID, FK): Reference to drift incident
- `type` (VARCHAR ENUM): promote, revert, replace
- `status` (VARCHAR ENUM): pending, in_progress, success, failed
- `started_at/by` (TIMESTAMPTZ/UUID, nullable): Reconciliation start
- `finished_at` (TIMESTAMPTZ, nullable): Reconciliation completion
- `external_refs` (JSONB): External references (commit SHA, PR URL, deployment run ID)
- `affected_workflows` (JSONB): List of workflows reconciled
- `error_message` (TEXT, nullable): Error message if failed

**Constraints**:
- Foreign Key: `incident_id → drift_incidents(id)` CASCADE delete

**Indexes**:
- `idx_reconciliation_artifacts_tenant` on `tenant_id` (add_recon_artifacts:45)
- `idx_reconciliation_artifacts_incident` on `incident_id` (add_recon_artifacts:46)
- `idx_reconciliation_artifacts_status` on `status` (add_recon_artifacts:47)

**Schema Reference**: `app/schemas/drift_incident.py:186-219`

---

### 3.5 `drift_check_history`

**Purpose**: Historical log of drift check executions for audit and performance tracking.

**Migration**: `c1a2b3c4d5e6_add_drift_check_history.py`

**Table Structure** (inferred from migration reference):
```sql
CREATE TABLE drift_check_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    environment_id UUID NOT NULL,
    check_type VARCHAR(20) NOT NULL, -- 'scheduled', 'manual'
    drift_found BOOLEAN NOT NULL,
    workflows_checked INTEGER NOT NULL,
    workflows_with_drift INTEGER NOT NULL,
    check_duration_ms INTEGER NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id`, `environment_id` (UUID, FK): Location context
- `check_type` (VARCHAR ENUM): scheduled, manual
- `drift_found` (BOOLEAN): Whether any drift was detected
- `workflows_checked` (INTEGER): Total workflows checked
- `workflows_with_drift` (INTEGER): Count of workflows with drift
- `check_duration_ms` (INTEGER): Duration of check in milliseconds
- `checked_at` (TIMESTAMPTZ): Check execution timestamp

---

## 4. Deployment & Promotion Tables

### 4.1 `deployments`

**Purpose**: Deployment tracking (wrapper around promotions for scheduling and lifecycle management).

**Migrations**:
- Base: (Not found in scanned migrations; likely pre-canonical)
- Scheduling: `ebd702d672dc_add_deployment_scheduling.py` (lines 23-38)

**Table Structure** (inferred):
```sql
CREATE TABLE deployments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    promotion_id UUID NULL REFERENCES promotions(id),
    status TEXT NOT NULL, -- 'pending', 'scheduled', 'running', 'completed', 'failed'
    scheduled_at TIMESTAMPTZ NULL, -- Added in ebd702d672dc
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    summary_json JSONB NULL,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMPTZ NULL,
    deleted_by_user_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID, FK): Tenant isolation
- `promotion_id` (UUID, FK, nullable): Reference to promotion record
- `status` (TEXT ENUM): pending, scheduled, running, completed, failed
- `scheduled_at` (TIMESTAMPTZ, nullable): When deployment is scheduled to execute (NULL = immediate)
- `started_at` (TIMESTAMPTZ, nullable): Actual start timestamp
- `finished_at` (TIMESTAMPTZ, nullable): Completion timestamp
- `summary_json` (JSONB, nullable): Deployment summary and results
- `is_deleted` (BOOLEAN): Soft delete flag
- `deleted_at` (TIMESTAMPTZ, nullable): Soft delete timestamp
- `deleted_by_user_id` (UUID, nullable): User who deleted

**Constraints**:
- Foreign Key: `tenant_id → tenants(id)`
- Foreign Key: `promotion_id → promotions(id)`

**Indexes**:
- `idx_deployments_scheduled_at` on `scheduled_at` WHERE scheduled_at IS NOT NULL AND status = 'scheduled' (ebd702d672dc:32-34)

**Service Reference**: `app/services/database.py:240-269`

---

### 4.2 `promotions`

**Purpose**: Promotion execution records (moving workflows from source environment to target environment).

**Migrations**:
- Base: (Not found in scanned migrations; likely pre-canonical)
- Scheduling: `ebd702d672dc_add_deployment_scheduling.py` (lines 27-29)

**Table Structure** (inferred from mvp_readiness_pack/08):
```sql
CREATE TABLE promotions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    pipeline_id UUID NULL REFERENCES pipelines(id),
    source_environment_id UUID NOT NULL REFERENCES environments(id),
    target_environment_id UUID NOT NULL REFERENCES environments(id),
    status TEXT NOT NULL, -- 'pending', 'pending_approval', 'approved', 'running', 'completed', 'failed'
    workflow_selections JSONB NULL,
    gate_results JSONB NULL,
    source_snapshot_id UUID NULL,
    target_pre_snapshot_id UUID NULL,
    target_post_snapshot_id UUID NULL,
    execution_result JSONB NULL,
    created_by UUID NULL,
    approved_by UUID NULL,
    scheduled_at TIMESTAMPTZ NULL, -- Added in ebd702d672dc
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID, FK): Tenant isolation
- `pipeline_id` (UUID, FK, nullable): Reference to pipeline definition
- `source_environment_id` (UUID, FK): Source environment
- `target_environment_id` (UUID, FK): Target environment
- `status` (TEXT ENUM): Promotion lifecycle status
- `workflow_selections` (JSONB, nullable): Which workflows to promote
- `gate_results` (JSONB, nullable): Gating logic results
- `source_snapshot_id`, `target_pre_snapshot_id`, `target_post_snapshot_id` (UUID, nullable): Snapshot references
- `execution_result` (JSONB, nullable): Detailed results and rollback info
- `created_by` (UUID, nullable): User who initiated promotion
- `approved_by` (UUID, nullable): User who approved promotion
- `scheduled_at` (TIMESTAMPTZ, nullable): Scheduled execution time

**Constraints**:
- Foreign Key: `tenant_id → tenants(id)`
- Foreign Key: `pipeline_id → pipelines(id)`
- Foreign Key: `source_environment_id → environments(id)`
- Foreign Key: `target_environment_id → environments(id)`

**Schema Reference**: `app/schemas/promotion.py`

---

### 4.3 `deployment_workflows`

**Purpose**: Per-workflow deployment results (granular tracking within a deployment).

**Migration**: (Not found in scanned migrations; likely pre-canonical)

**Table Structure** (inferred):
```sql
CREATE TABLE deployment_workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deployment_id UUID NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL,
    workflow_name TEXT NOT NULL,
    status TEXT NOT NULL, -- 'success', 'failed', 'skipped'
    error_message TEXT NULL,
    promoted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `deployment_id` (UUID, FK): Reference to parent deployment
- `workflow_id` (UUID): Workflow identifier
- `workflow_name` (TEXT): Workflow display name
- `status` (TEXT ENUM): success, failed, skipped
- `error_message` (TEXT, nullable): Error details if failed
- `promoted_at` (TIMESTAMPTZ, nullable): Promotion timestamp

**Constraints**:
- Foreign Key: `deployment_id → deployments(id)` CASCADE delete

**Service Reference**: `app/services/database.py:298-301`

---

### 4.4 `snapshots`

**Purpose**: Point-in-time backups of environment state for rollback and audit trail.

**Migration**: (Not found in scanned migrations; likely pre-canonical)

**Table Structure** (inferred):
```sql
CREATE TABLE snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    environment_id UUID NOT NULL REFERENCES environments(id),
    snapshot_type TEXT NOT NULL, -- 'pre_promotion', 'post_promotion', 'manual_backup'
    workflows JSONB NOT NULL,
    git_commit_sha TEXT NULL,
    created_by UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id`, `environment_id` (UUID, FK): Location context
- `snapshot_type` (TEXT ENUM): pre_promotion, post_promotion, manual_backup
- `workflows` (JSONB): Snapshot of all workflows in environment
- `git_commit_sha` (TEXT, nullable): Git commit at snapshot time
- `created_by` (UUID, nullable): User who created snapshot
- `created_at` (TIMESTAMPTZ): Snapshot timestamp

**Service Reference**: `app/services/database.py:272-295`

---

### 4.5 `pipelines`

**Purpose**: Promotion pipeline definitions (stage configurations, approval gates).

**Migration**: (Not found in scanned migrations; likely pre-canonical)

**Table Structure** (inferred):
```sql
CREATE TABLE pipelines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    provider TEXT NOT NULL DEFAULT 'n8n',
    name TEXT NOT NULL,
    description TEXT NULL,
    stages JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID, FK): Tenant isolation
- `provider` (TEXT): Provider type (n8n)
- `name` (TEXT): Pipeline name
- `description` (TEXT, nullable): Pipeline description
- `stages` (JSONB): Array of stage configs with gates
- `is_active` (BOOLEAN): Whether pipeline is enabled

**Constraints**:
- Unique: `(tenant_id, name)`

**Schema Reference**: `app/schemas/pipeline.py`

---

## 5. Background Jobs & Sync

### 5.1 `background_jobs`

**Purpose**: Async job tracking for sync operations, promotions, deployments, and onboarding.

**Migrations**:
- Base: (Not found in scanned migrations; likely pre-canonical)
- Metadata: `dd6be28dfaab_add_metadata_to_background_jobs.py`
- Sync unique constraint: `20260112_add_sync_job_unique_constraint.py` (lines 28-45)

**Table Structure** (inferred):
```sql
CREATE TABLE background_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    job_type TEXT NOT NULL, -- 'sync', 'promotion', 'deployment', 'onboarding', 'canonical_env_sync', 'canonical_repo_sync', 'environment_sync'
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    resource_type TEXT NULL, -- 'environment', 'deployment', 'tenant'
    resource_id UUID NULL,
    progress JSONB NULL, -- {current, total, percentage, message}
    metadata JSONB NULL,
    error_message TEXT NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Key Columns**:
- `id` (UUID): Primary key
- `tenant_id` (UUID, FK): Tenant isolation
- `job_type` (TEXT): Type of background job
- `status` (TEXT ENUM): Job lifecycle status
- `resource_type` (TEXT, nullable): Type of resource being processed
- `resource_id` (UUID, nullable): ID of resource being processed
- `progress` (JSONB, nullable): Progress tracking `{current, total, percentage, message}`
- `metadata` (JSONB, nullable): Job-specific metadata
- `error_message` (TEXT, nullable): Error details if failed
- `started_at` (TIMESTAMPTZ, nullable): Job start timestamp
- `completed_at` (TIMESTAMPTZ, nullable): Job completion timestamp

**Job Types**:
- `canonical_env_sync`: Sync from n8n runtime to DB
- `canonical_repo_sync`: Sync from Git to DB
- `environment_sync`: Legacy sync operation
- `promotion`: Promotion job
- `deployment`: Deployment job
- `onboarding`: Onboarding inventory job

**Unique Constraint** (20260112:28-37):
- **Partial unique index** to prevent duplicate active sync jobs:
  ```sql
  CREATE UNIQUE INDEX idx_background_jobs_active_sync_unique
  ON background_jobs (resource_id, job_type)
  WHERE resource_type = 'environment'
    AND job_type IN ('canonical_env_sync', 'canonical_repo_sync', 'environment_sync')
    AND status IN ('pending', 'running')
  ```
- **Purpose**: Ensures only ONE sync job can be pending or running for a given environment at a time
- **Race-safe**: Enforced at DB level

**Indexes**:
- `idx_background_jobs_active_sync_unique` (partial, see above)
- `idx_background_jobs_active_by_env` on `(tenant_id, resource_id, job_type, status)` WHERE resource_type = 'environment' AND status IN ('pending', 'running') (20260112:39-45)

---

## 6. Identity & Mapping Rules

### 6.1 Canonical Workflow Identity

**Identity Definition**:
- Each canonical workflow has a universal `canonical_id` (UUID) that remains constant across all environments
- A workflow can exist in 0, 1, or many environments with the same canonical identity
- The `canonical_workflows` table stores ONLY identity metadata (no content)

**Content Storage**:
- Git state: `canonical_workflow_git_state` table (per-environment)
- Runtime state: `workflow_env_map.workflow_data` (per-environment, cached)

**Identity Assignment**:
1. **Manual creation**: User creates canonical workflow explicitly
2. **Auto-linking during onboarding**: System assigns canonical_id based on similarity
3. **Untracked workflows**: `workflow_env_map` entry with `canonical_id = NULL`

---

### 6.2 Environment Mapping Rules

**Mapping States**:

| Status | canonical_id | n8n_workflow_id | Meaning |
|--------|--------------|-----------------|---------|
| `linked` | NOT NULL | NOT NULL | Canonically tracked workflow |
| `untracked` | NULL | NOT NULL | Runtime workflow without canonical identity |
| `missing` | any | any | Previously mapped but disappeared from n8n |
| `ignored` | any | any | Explicitly excluded from tracking |
| `deleted` | any | any | Soft-deleted mapping |

**Mapping Uniqueness**:
1. **Per-environment uniqueness**: `(tenant_id, environment_id, canonical_id)` UNIQUE
   - A canonical workflow can appear at most ONCE per environment
2. **Per-workflow uniqueness**: `(tenant_id, environment_id, n8n_workflow_id)` UNIQUE (inferred)
   - Each n8n workflow ID maps to at most ONE canonical workflow per environment

---

### 6.3 Git Metadata Storage

**Git Metadata Location**: `canonical_workflow_git_state` table

**Key Git Fields**:
- `git_path` (TEXT): Relative file path in Git repo (e.g., `workflows/dev/my-workflow.json`)
- `git_commit_sha` (TEXT): Last commit SHA where workflow was synced
- `git_content_hash` (TEXT): Content-based hash for change detection
- `last_repo_sync_at` (TIMESTAMPTZ): Last Git sync timestamp

**Git Configuration** (per-environment):
- `environments.git_repo_url` (TEXT): GitHub repository URL
- `environments.git_branch` (TEXT): Git branch for this environment
- `environments.git_pat` (TEXT): GitHub Personal Access Token
- `environments.git_folder` (TEXT): Subfolder in repo for this environment's workflows

**Folder Structure**:
- Anchor environment: `environments.git_folder` typically NULL or root
- Non-anchor environments: `environments.git_folder` typically `workflows/{env_type}/`

---

### 6.4 Drift Detection Rules

**Drift Comparison**:
```
Drift Detected = (workflow_env_map.env_content_hash != canonical_workflow_git_state.git_content_hash)
```

**Drift Status Determination** (environment-level):
1. **IN_SYNC**: No drift detected across any workflows
2. **DRIFT_DETECTED**: Drift detected but no active incident
3. **DRIFT_INCIDENT_ACTIVE**: Active drift incident exists (`environments.active_drift_incident_id NOT NULL`)

**Workflow-Level Status** (from `workflow_env_map.status`):
- **LINKED**: Workflow is tracked and in sync (or not checked yet)
- **UNTRACKED**: Workflow exists in runtime but not canonically tracked
- **MISSING**: Workflow previously existed but disappeared from runtime

**Drift vs. UNTRACKED**:
- **Drift**: LINKED workflow where content differs between runtime and Git
- **UNTRACKED**: Workflow has no canonical identity (`canonical_id IS NULL`)

---

## 7. Foreign Key Relationships

### 7.1 Core Relationships

**Tenant Hierarchy**:
```
tenants (id)
  ├─> environments (tenant_id)
  ├─> canonical_workflows (tenant_id)
  ├─> drift_incidents (tenant_id)
  ├─> drift_policies (tenant_id)
  ├─> deployments (tenant_id)
  ├─> promotions (tenant_id)
  ├─> background_jobs (tenant_id)
  └─> snapshots (tenant_id)
```

**Canonical Workflow Relationships**:
```
canonical_workflows (tenant_id, canonical_id)
  ├─> canonical_workflow_git_state (tenant_id, canonical_id) CASCADE
  ├─> workflow_env_map (tenant_id, canonical_id) CASCADE
  ├─> workflow_link_suggestions (tenant_id, canonical_id) CASCADE
  └─> workflow_diff_state (tenant_id, canonical_id) CASCADE
```

**Environment Relationships**:
```
environments (id)
  ├─> canonical_workflow_git_state (environment_id) CASCADE
  ├─> workflow_env_map (environment_id) CASCADE
  ├─> drift_incidents (environment_id)
  ├─> promotions (source_environment_id, target_environment_id)
  └─> snapshots (environment_id)
```

**Drift Incident Relationships**:
```
drift_incidents (id)
  ├─> drift_approvals (incident_id) CASCADE
  └─> drift_reconciliation_artifacts (incident_id) CASCADE
```

**Deployment Relationships**:
```
deployments (id)
  └─> deployment_workflows (deployment_id) CASCADE

promotions (id)
  └─> deployments (promotion_id)
```

---

### 7.2 Cascade Delete Rules

**CASCADE Deletes**:
- `canonical_workflows` → `canonical_workflow_git_state` (CASCADE)
- `canonical_workflows` → `workflow_env_map` (CASCADE)
- `canonical_workflows` → `workflow_link_suggestions` (CASCADE)
- `canonical_workflows` → `workflow_diff_state` (CASCADE)
- `environments` → `canonical_workflow_git_state` (CASCADE)
- `drift_incidents` → `drift_approvals` (CASCADE)
- `drift_incidents` → `drift_reconciliation_artifacts` (CASCADE)
- `deployments` → `deployment_workflows` (CASCADE)

**SET NULL Deletes**:
- `tenants.canonical_anchor_environment_id` → `environments(id)` (SET NULL)

**No Cascade / Risk of Orphans**:
- `workflow_env_map` → `environments` (likely CASCADE but not confirmed)
- `drift_incidents` → `environments` (likely no cascade; incident retained for audit)
- `promotions` → `environments` (likely no cascade; promotion history retained)

---

## 8. Indexes & Performance

### 8.1 Performance Indexes

**Migration**: `bf7375f4eb69_add_performance_indexes.py`

**Canonical Workflow Indexes**:
- `idx_canonical_workflows_tenant` on `tenant_id`
- `idx_canonical_workflows_created_at` on `created_at DESC`
- `idx_canonical_workflows_deleted_at` on `deleted_at` (partial: WHERE deleted_at IS NOT NULL)

**Git State Indexes**:
- `idx_canonical_git_state_tenant_env` on `(tenant_id, environment_id)`
- `idx_canonical_git_state_canonical` on `canonical_id`

**Workflow Env Map Indexes**:
- `idx_workflow_env_map_tenant_env` on `(tenant_id, environment_id)`
- `idx_workflow_env_map_canonical` on `canonical_id`
- `idx_workflow_env_map_n8n_id` on `n8n_workflow_id` (partial: WHERE NOT NULL)
- `idx_workflow_env_map_status` on `status` (partial: WHERE NOT NULL)
- `idx_workflow_env_map_last_sync` on `last_env_sync_at DESC`
- `idx_workflow_env_map_workflow_data` (GIN) on `workflow_data` (partial: WHERE NOT NULL)

**Link Suggestion Indexes**:
- `idx_workflow_link_suggestions_tenant_env` on `(tenant_id, environment_id)`
- `idx_workflow_link_suggestions_status` on `status` (partial: WHERE status = 'open')
- `idx_workflow_link_suggestions_created` on `created_at DESC`

**Diff State Indexes**:
- `idx_workflow_diff_state_tenant_envs` on `(tenant_id, source_env_id, target_env_id)`
- `idx_workflow_diff_state_canonical` on `canonical_id`
- `idx_workflow_diff_state_computed` on `computed_at DESC`
- `idx_workflow_diff_state_conflict` on `diff_status` (partial: WHERE diff_status = 'conflict')

**Drift Incident Indexes**:
- `idx_drift_incidents_tenant` on `tenant_id`
- `idx_drift_incidents_environment` on `environment_id`
- `idx_drift_incidents_status` on `status`
- `idx_drift_incidents_detected_at` on `detected_at`

**Drift Policy Indexes**:
- `idx_drift_policies_tenant` on `tenant_id`

**Drift Approval Indexes**:
- `idx_drift_approvals_tenant` on `tenant_id`
- `idx_drift_approvals_incident` on `incident_id`
- `idx_drift_approvals_status` on `status`

**Reconciliation Artifact Indexes**:
- `idx_reconciliation_artifacts_tenant` on `tenant_id`
- `idx_reconciliation_artifacts_incident` on `incident_id`
- `idx_reconciliation_artifacts_status` on `status`

**Deployment Indexes**:
- `idx_deployments_scheduled_at` on `scheduled_at` (partial: WHERE scheduled_at IS NOT NULL AND status = 'scheduled')

**Background Job Indexes**:
- `idx_background_jobs_active_sync_unique` on `(resource_id, job_type)` (partial: WHERE resource_type = 'environment' AND job_type IN (...) AND status IN ('pending', 'running'))
- `idx_background_jobs_active_by_env` on `(tenant_id, resource_id, job_type, status)` (partial: WHERE resource_type = 'environment' AND status IN ('pending', 'running'))

---

### 8.2 JSONB Indexes

**GIN Indexes** (for JSONB column queries):
- `workflow_env_map.workflow_data` (GIN index)

**JSONB Columns Without Indexes** (potential performance risk):
- `drift_incidents.affected_workflows`
- `drift_incidents.drift_snapshot`
- `drift_incidents.resolution_details`
- `environments.policy_flags`
- `promotions.workflow_selections`
- `promotions.gate_results`
- `promotions.execution_result`
- `background_jobs.progress`
- `background_jobs.metadata`
- `workflow_diff_state.conflict_metadata`

---

### 8.3 Unique Constraints

**Composite Unique Constraints**:
- `canonical_workflows`: `(tenant_id, canonical_id)` PK
- `canonical_workflow_git_state`: `(tenant_id, environment_id, canonical_id)` PK
- `workflow_env_map`: `id` PK (surrogate), `(tenant_id, environment_id, canonical_id)` UNIQUE
- `workflow_link_suggestions`: `(tenant_id, environment_id, n8n_workflow_id, canonical_id)` UNIQUE
- `workflow_diff_state`: `(tenant_id, source_env_id, target_env_id, canonical_id)` UNIQUE
- `environments`: `(tenant_id, n8n_name)` UNIQUE
- `environment_types`: `(tenant_id, key)` UNIQUE
- `drift_policies`: `tenant_id` UNIQUE
- `pipelines`: `(tenant_id, name)` UNIQUE

---

## 9. Migration Timeline

### Phase 1: Pre-Canonical (Before 2025-12-29)
- Base tables: `tenants`, `users`, `environments`, `workflows` (legacy)
- Promotions, deployments, pipelines established
- Drift detection added to environments

### Phase 2: Drift Management (2025-12-30)
- `53259882566d_add_drift_fields_and_incidents.py`: Drift fields on environments, drift_incidents table
- `add_drift_incident_lifecycle.py`: Lifecycle timestamps, severity, TTL
- `add_reconciliation_artifacts.py`: Reconciliation tracking
- `add_drift_policies_and_approvals.py`: Policy engine, approval workflows

### Phase 3: Canonical Workflow System (2026-01-05 to 2026-01-06)
- `dcd2f2c8774d_create_canonical_workflow_tables.py`: Core canonical tables (canonical_workflows, canonical_workflow_git_state, workflow_env_map, workflow_link_suggestions, workflow_diff_state)
- `6a78a8d07b5e_add_workflow_data_to_env_map.py`: Add workflow_data JSONB cache to workflow_env_map
- `3e894b287688_add_surrogate_pk_to_workflow_env_map.py`: Add surrogate UUID primary key to workflow_env_map
- `dd6be28dfaab_add_metadata_to_background_jobs.py`: Metadata field for background jobs

### Phase 4: Optimization & Refinement (2026-01-07 to 2026-01-12)
- `20260107_075803_optimize_workflow_env_map_queries.py`: Query optimization for workflow_env_map
- `20260107_182000_add_execution_analytics_columns.py`: Execution analytics enhancements
- `20260111_add_workflow_diff_state_columns.py`: Hash columns and conflict metadata for workflow_diff_state
- `20260112_add_sync_job_unique_constraint.py`: Partial unique constraint to prevent duplicate sync jobs

### Merge Migrations
- `0d3cc810ee1a_merge_heads.py`
- `855f0d7fe1de_merge_analytics_and_features.py`
- `3c4da474d855_merge_provider_and_tenant_fix.py`
- `d0ead040adb3_merge_mv_tracking_and_gated_actions.py`

---

## Summary

The WorkflowOps database schema implements a **Git-backed canonical workflow system** with multi-environment tracking, drift detection, and promotion workflows. Key architectural decisions:

1. **Identity Separation**: `canonical_workflows` stores ONLY identity; content lives in `canonical_workflow_git_state` (Git) and `workflow_env_map` (runtime)
2. **UNTRACKED Workflows**: Nullable `canonical_id` in `workflow_env_map` enables tracking of non-canonical workflows
3. **Drift Management**: Four-table system (incidents, policies, approvals, artifacts) with lifecycle tracking
4. **Race-Safe Sync**: Partial unique constraint on `background_jobs` prevents duplicate sync jobs at DB level
5. **Performance**: Comprehensive indexing on composite keys, JSONB GIN indexes, partial indexes for filtered queries
6. **Soft Deletes**: `deleted_at` timestamps on canonical_workflows, deployments, drift_incidents
7. **Cascading Deletes**: Canonical workflow deletion cascades to all related tables (git_state, env_map, suggestions, diff_state)

**Critical Tables for WorkflowOps**:
- `canonical_workflows`: Universal workflow identity
- `workflow_env_map`: Environment-specific runtime state (THE junction table)
- `canonical_workflow_git_state`: Git-backed source of truth
- `environments`: n8n runtime instances with drift tracking
- `drift_incidents`: Drift lifecycle management
- `background_jobs`: Async sync job orchestration

---

**Document Version**: 1.0
**Last Updated**: 2026-01-14
**Migration Range Covered**: Pre-canonical through `20260112_add_sync_job_unique_constraint.py`
