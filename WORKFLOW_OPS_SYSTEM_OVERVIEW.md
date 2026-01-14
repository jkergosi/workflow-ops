# WorkflowOps System: Complete Technical Specification

**Document Purpose**: Comprehensive technical specification of the WorkflowOps system covering all subsystems, flows, and implementation details
**Task**: T012 - Generate final comprehensive report with all sections
**Status**: ✅ COMPLETED
**Generated**: 2026-01-14
**Version**: 1.0

---

## Document Structure

This comprehensive report consolidates findings from 11 completed analysis tasks (T001-T011) into a single authoritative reference for the WorkflowOps system.

### Related Documentation

- **T001**: [TASK_T001_DRIFT_DETECTION_ANALYSIS.md](./TASK_T001_DRIFT_DETECTION_ANALYSIS.md) - Drift detection logic analysis
- **T002**: [T002_DATABASE_SCHEMA_DOCUMENTATION.md](./T002_DATABASE_SCHEMA_DOCUMENTATION.md) - Complete database schema
- **T003**: [T003_SYNC_FLOWS_DOCUMENTATION.md](./T003_SYNC_FLOWS_DOCUMENTATION.md) - Sync flow documentation
- **T004**: [PROMOTION_FLOW_DOCUMENTATION.md](./PROMOTION_FLOW_DOCUMENTATION.md) - Promotion flows
- **T005**: [T005_SCHEDULERS_AND_TRIGGERS.md](./T005_SCHEDULERS_AND_TRIGGERS.md) - Scheduler documentation
- **T006**: [DRIFT_DETECTION_INTROSPECTION.md](./DRIFT_DETECTION_INTROSPECTION.md) - Drift semantics
- **T007**: [T007_IDENTITY_AND_MAPPING_RULES.md](./T007_IDENTITY_AND_MAPPING_RULES.md) - Identity rules
- **T008**: [T008_STATE_MACHINES_DOCUMENTATION.md](./T008_STATE_MACHINES_DOCUMENTATION.md) - State machines
- **T009**: [mvp_readiness_pack/12_narrative_walkthroughs.md](./mvp_readiness_pack/12_narrative_walkthroughs.md) - Scenario walkthroughs
- **T010**: [mvp_readiness_pack/13_risk_points_and_failure_modes.md](./mvp_readiness_pack/13_risk_points_and_failure_modes.md) - Risk analysis
- **T011**: Current document - Executive summary (see Section 1)

---

## Table of Contents

0. [Quick Start Guide](#0-quick-start-guide)
1. [Executive Summary & Glossary](#1-executive-summary--glossary)
2. [System Architecture](#2-system-architecture)
3. [Database Schema & Data Model](#3-database-schema--data-model)
4. [Sync Flows & Reconciliation](#4-sync-flows--reconciliation)
5. [Promotion & Deployment Pipeline](#5-promotion--deployment-pipeline)
6. [Drift Detection & Incident Management](#6-drift-detection--incident-management)
7. [Identity & Mapping Rules](#7-identity--mapping-rules)
8. [State Machines & Lifecycle](#8-state-machines--lifecycle)
9. [Schedulers & Background Jobs](#9-schedulers--background-jobs)
10. [Risk Points & Failure Modes](#10-risk-points--failure-modes)
11. [API Reference](#11-api-reference)
12. [Narrative Walkthroughs](#12-narrative-walkthroughs)

---

# 0. Quick Start Guide

## For New Developers

**Start here if you're new to the codebase:**

1. **Understand the core concept**: WorkflowOps is a GitOps control plane for n8n workflows
   - Git is the source of truth for staging/production
   - Dev environment uses n8n directly
   - Changes flow: dev → Git → staging → prod

2. **Key files to read first**:
   - `n8n-ops-backend/app/main.py` - Application entrypoint
   - `n8n-ops-backend/app/services/sync_orchestrator_service.py` - Sync logic
   - `n8n-ops-backend/app/services/promotion_service.py` - Promotion logic
   - `n8n-ops-backend/app/services/drift_detection_service.py` - Drift detection

3. **Essential concepts**:
   - **Canonical ID**: Stable UUID for workflows across environments
   - **Content Hash**: SHA256 of normalized workflow JSON
   - **Drift**: Mismatch between Git and runtime state
   - **Mapping Status**: `linked`, `untracked`, `missing`, `ignored`, `deleted`

4. **Common tasks**:
   - Add a new API endpoint: `app/api/endpoints/` + register in `main.py`
   - Add a database table: Create migration in `alembic/versions/`
   - Add a scheduler: Create service in `app/services/` + register in `main.py:startup_event()`
   - Add a test: `tests/` following existing patterns

## For Operators/SREs

**Key operational knowledge:**

1. **Monitoring endpoints**:
   - Health check: `GET /api/v1/health`
   - Active deployments: `GET /api/v1/deployments?status=running`
   - Drift incidents: `GET /api/v1/incidents?status=detected`

2. **Background jobs**:
   - All schedulers start on app startup
   - Jobs logged in `background_jobs` table
   - SSE streams provide real-time progress: `/api/v1/sse/background-jobs`

3. **Common issues**:
   - Stale deployments: Automatically marked failed after 1 hour
   - Drift detection errors: Check Git credentials and n8n API connectivity
   - Sync failures: Review `background_jobs` table for error details

4. **Emergency procedures**:
   - Rollback promotion: Use pre-promotion snapshot ID
   - Force close drift incident: Requires admin role
   - Disable scheduler: Restart app with environment variable override

---

# 1. Executive Summary & Glossary

## 1.1 What is WorkflowOps?

WorkflowOps is a **GitOps-inspired control plane** for managing n8n workflow automation across multiple environments (dev, staging, production). It provides:

- **Centralized workflow management** with Git-backed source of truth
- **Cross-environment promotion** with validation, transformation, and rollback
- **Drift detection and incident management** to enforce configuration compliance
- **Automated synchronization** between n8n runtime, database, and Git repositories
- **Multi-tenant isolation** with role-based access control (RBAC)

### 1.2 Core Value Propositions

| Capability | Business Value |
|------------|----------------|
| **Git-Backed Workflows** | Version control, audit trail, disaster recovery |
| **Promotion Pipelines** | Safe, repeatable deployments from dev → staging → prod |
| **Drift Detection** | Automatic detection of unauthorized changes in production |
| **Cross-Environment Visibility** | Unified view of workflow state across all environments |
| **Automated Syncing** | Zero-touch synchronization reduces manual toil |

### 1.3 System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      WorkflowOps Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   n8n Dev    │────▶│  PostgreSQL  │◀────│  GitHub Repo │    │
│  │  (Runtime)   │◀────│  (Database)  │────▶│  (Git SoT)   │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         │                     │                     │            │
│         │                     │                     │            │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │ n8n Staging  │     │   Sync &     │     │  Drift       │    │
│  │  (Runtime)   │     │ Reconcile    │     │  Detection   │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         │                                           │            │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │  n8n Prod    │     │  Promotion   │     │  Schedulers  │    │
│  │  (Runtime)   │     │   Service    │     │  (8 types)   │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 Key Design Principles

1. **Git as Source of Truth (for non-dev environments)**
   - Dev environment: n8n runtime is SoT (developers work directly in n8n)
   - Staging/Prod: Git is SoT (changes must flow through promotion pipeline)

2. **Canonical Identity Model**
   - Each workflow has a stable `canonical_id` (UUID) across all environments
   - Content-based hashing (SHA256) for identity resolution and drift detection
   - Decouples logical workflow identity from environment-specific IDs

3. **Three-Way Synchronization**
   - **Runtime → DB**: n8n workflows synced to `workflow_env_map` table
   - **Git → DB**: Git workflow files synced to `canonical_workflow_git_state` table
   - **DB → DB**: Reconciliation computes diffs between environments

4. **Fail-Closed Security Model**
   - Policy violations block promotions by default
   - Drift detection creates auto-escalating incidents
   - Atomic rollback on promotion failures

5. **Multi-Tenant Isolation**
   - Row-level security (RLS) policies enforce tenant boundaries
   - All tables partitioned by `tenant_id`
   - No cross-tenant data leakage possible

## 1.5 Comprehensive Glossary

### Core Entities

| Term | Definition | Example | Database Table |
|------|------------|---------|----------------|
| **Canonical ID** | Stable UUID representing logical workflow identity across all environments | `550e8400-e29b-41d4-a716-446655440000` | `canonical_workflows.canonical_id` |
| **Canonical Workflow** | Logical workflow entity independent of environment-specific instances | "Customer Onboarding Workflow" | `canonical_workflows` |
| **Environment** | Isolated n8n instance (dev, staging, prod) with independent runtime state | "Production US-East-1" | `environments` |
| **Tenant** | Multi-tenant isolation boundary (typically maps to customer/organization) | "Acme Corp" | `tenants` |
| **Workflow Mapping** | Association between a canonical workflow and its instance in a specific environment | `(canonical_id, environment_id, n8n_workflow_id)` | `workflow_env_map` |
| **Content Hash** | SHA256 hash of normalized workflow JSON, used for identity and drift detection | `a3b5c7d9e1f...` (64 chars) | `workflow_env_map.env_content_hash` |
| **Git State** | Git-specific metadata for a canonical workflow in an environment (path, SHA, hash) | Path: `workflows/customer-onboarding.json` | `canonical_workflow_git_state` |
| **Drift Incident** | Record of detected configuration drift with severity, TTL, and lifecycle tracking | Incident #42, severity: `high`, TTL: 4 hours | `drift_incidents` |

### Status Enumerations

| Status Type | Possible Values | Scope | Stored In |
|-------------|-----------------|-------|-----------|
| **Workflow Mapping Status** | `linked`, `untracked`, `missing`, `ignored`, `deleted` | Per workflow per environment | `workflow_env_map.status` |
| **Environment Drift Status** | `IN_SYNC`, `DRIFT_DETECTED`, `UNTRACKED`, `DRIFT_INCIDENT_ACTIVE`, `DRIFT_INCIDENT_ACKNOWLEDGED` | Per environment | `environments.drift_status` |
| **Diff Status** | `unchanged`, `modified`, `added`, `target_only`, `conflict`, `target_hotfix` | Per workflow pair (source → target) | `workflow_diff_state.diff_status` |
| **Drift Incident Status** | `detected`, `acknowledged`, `stabilized`, `reconciled`, `closed`, `expired`, `cancelled` | Per incident | `drift_incidents.status` |
| **Promotion Status** | `pending`, `in_progress`, `completed`, `completed_with_errors`, `failed`, `rolled_back` | Per promotion | `promotions.status` |
| **Sync Job Status** | `running`, `completed`, `failed` | Per sync job | `sync_jobs.status` |

### Sync Operations

| Term | Definition | Direction | Trigger | Service File |
|------|------------|-----------|---------|--------------|
| **Environment Sync** | Fetch workflows from n8n runtime and persist to `workflow_env_map` | n8n → DB | Manual API call or scheduler | `canonical_env_sync_service.py` |
| **Repository Sync** | Fetch workflows from Git repo and persist to `canonical_workflow_git_state` | Git → DB | Manual API call or scheduler | `canonical_repo_sync_service.py` |
| **Reconciliation** | Compare workflows between environment pairs and compute `workflow_diff_state` | DB → DB | After env/repo syncs | `canonical_reconciliation_service.py` |
| **Drift Detection** | Identify workflows with Git ↔ n8n discrepancies | Git ↔ n8n | Scheduled (every 5 min) | `drift_detection_service.py` |
| **Auto-Link** | Automatically establish `canonical_id` for untracked workflows using hash matching | Registry → Mapping | During environment sync | `canonical_env_sync_service.py` |
| **Sidecar Update** | Write workflow JSON to Git repo alongside promotion | DB → Git | After promotion | `github_service.py` |

---

# 2. System Architecture

## 2.1 Repository Structure

```
n8n-ops-trees/
├── n8n-ops-backend/          # FastAPI backend (Python)
│   ├── app/
│   │   ├── main.py           # Entrypoint, scheduler startup
│   │   ├── api/endpoints/    # 51 REST API endpoints
│   │   ├── services/         # 64 service modules
│   │   ├── schemas/          # 27 Pydantic models
│   │   └── core/             # RBAC, tenant isolation, config
│   ├── alembic/              # 63 database migrations
│   └── tests/                # 103 test files
│
├── n8n-ops-ui/               # React frontend (TypeScript)
│   └── src/
│       ├── components/       # Reusable UI components
│       ├── pages/            # Page-level components
│       ├── hooks/            # Custom React hooks (SSE, auth)
│       └── store/            # Zustand state management
│
└── mvp_readiness_pack/       # Documentation bundle
```

## 2.2 Backend Services Breakdown

| Service Category | Count | Key Services | Purpose |
|------------------|-------|--------------|---------|
| **Sync Services** | 6 | `canonical_env_sync_service`, `canonical_repo_sync_service`, `sync_orchestrator_service` | Sync runtime ↔ DB ↔ Git |
| **Promotion Services** | 3 | `promotion_service`, `promotion_validation_service`, `deployment_scheduler` | Manage cross-environment promotions |
| **Drift Services** | 5 | `drift_detection_service`, `drift_incident_service`, `drift_scheduler` | Detect and track configuration drift |
| **Schedulers** | 8 | See section 9 | Background job execution |
| **Platform Services** | 10+ | `n8n_client`, `github_service`, `database`, `auth` | Infrastructure integrations |
| **Workflow Services** | 8 | `canonical_workflow_service`, `workflow_hash_registry_service` | Canonical workflow management |
| **Observability** | 6 | `rollup_scheduler`, `health_check_scheduler`, `audit_log_service` | Monitoring and compliance |

## 2.3 External Integrations

### Supabase (Database & Auth)
**File:** `n8n-ops-backend/app/core/config.py`

- **Database:** PostgreSQL via Supabase
- **URL:** `SUPABASE_URL` (from env)
- **Keys:**
  - `SUPABASE_KEY` (anon) - Frontend uses this
  - `SUPABASE_SERVICE_KEY` (service role) - Backend uses this (bypasses RLS)
- **Auth:** JWT-based authentication via Supabase Auth
- **RLS Status:** 12 of 76 tables have RLS enabled (15.8%)

### GitHub (Version Control)
**File:** `n8n-ops-backend/app/services/github_service.py`

- **Token:** `GITHUB_TOKEN` (Personal Access Token per environment)
- **Repo:** `GITHUB_REPO_OWNER` / `GITHUB_REPO_NAME`
- **Branch:** `GITHUB_BRANCH` (default: "main")
- **Webhook Handler:** `app/api/endpoints/github_webhooks.py`

### Stripe (Billing)
**File:** `n8n-ops-backend/app/services/stripe_service.py`

- **Secret Key:** `STRIPE_SECRET_KEY`
- **Publishable Key:** `STRIPE_PUBLISHABLE_KEY`
- **Webhook Secret:** `STRIPE_WEBHOOK_SECRET`
- **Price IDs:** `STRIPE_PRO_PRICE_ID_MONTHLY`, `STRIPE_PRO_PRICE_ID_YEARLY`
- **Webhook Handler:** `app/api/endpoints/billing.py:stripe_webhook()`

### n8n Provider APIs
**File:** `n8n-ops-backend/app/services/n8n_client.py`

- **Adapter Pattern:** `app/services/adapters/n8n_adapter.py`
- **Provider Registry:** `app/services/provider_registry.py`
- **Multi-Provider Support:** Architecture supports multiple workflow providers

## 2.4 Middleware & Global Handlers

**File:** `n8n-ops-backend/app/main.py`

1. **Impersonation Write Audit Middleware** (lines 22-82)
   - Logs all write operations during impersonation
   - Captures actor and impersonated user context

2. **CORS Middleware** (lines 85-91)
   - Allows origins from `BACKEND_CORS_ORIGINS`
   - Credentials enabled

3. **Global Exception Handler** (lines 531-584)
   - Catches unhandled exceptions
   - Emits `system.error` events
   - Returns 500 with error type

---

# 3. Database Schema & Data Model

## 3.1 Core Tables

### tenants
**Purpose:** Tenant isolation root

**Key Columns:**
- `id` (UUID PK)
- `name`, `slug`
- `subscription_tier`: free/pro/agency/enterprise (deprecated, use tenant_plans)
- `created_at`, `updated_at`

**RLS:** Enabled

### users
**Purpose:** User accounts

**Key Columns:**
- `id` (UUID PK)
- `tenant_id` (UUID FK)
- `email`, `supabase_auth_id`
- `role`: viewer/developer/admin
- `is_active` (bool)

**RLS:** Enabled

### environments
**Purpose:** Connected n8n/provider instances

**Key Columns:**
- `id` (UUID PK), `tenant_id` (UUID FK)
- `name`, `url`, `api_key` (encrypted)
- `provider`: n8n (enum)
- `environment_class`: dev/staging/production
- `drift_handling_mode`: warn_only/manual_override/require_attestation
- `github_repo_url`, `github_token`
- `last_heartbeat_at`, `last_sync_at`
- `drift_status`: IN_SYNC/DRIFT_DETECTED/UNTRACKED/DRIFT_INCIDENT_ACTIVE/etc
- `last_drift_check_at`, `last_drift_detected_at`

**Constraints:** Unique `(tenant_id, name)`

## 3.2 Canonical Workflow Tables

### canonical_workflows
**Purpose:** Git-backed source of truth

**Key Columns:**
- `id` (UUID PK) - The canonical_id
- `tenant_id` (UUID FK)
- `canonical_slug`: Human-readable ID
- `name`, `content_hash`
- `workflow_definition` (JSONB)
- `git_file_path`, `provider`
- `created_at`, `updated_at`, `deleted_at`

**Migration:** `dcd2f2c8774d_create_canonical_workflow_tables.py`

### workflow_env_map
**Purpose:** Junction table (canonical ↔ environment)

**Key Columns:**
- `id` (UUID PK, surrogate key)
- `canonical_id` (UUID FK, nullable) - NULL if untracked
- `environment_id` (UUID FK)
- `n8n_workflow_id` (text) - Provider-specific ID
- `status`: linked/untracked/missing/ignored/deleted
- `env_content_hash`: Hash of workflow in this environment
- `git_content_hash`: Hash of workflow in Git
- `n8n_updated_at`: Last update from n8n
- `workflow_name`, `workflow_data` (JSONB)

**Constraints:**
- Unique `(environment_id, n8n_workflow_id)`
- Unique `(canonical_id, environment_id)` WHERE canonical_id NOT NULL

**Indexes:** Performance indexes in `bf7375f4eb69_add_performance_indexes.py`

### canonical_workflow_git_state
**Purpose:** Git sync state tracking

**Key Columns:**
- `canonical_id` (UUID FK)
- `environment_id` (UUID FK)
- `tenant_id` (UUID FK)
- `git_commit_sha`: Last synced commit
- `git_content_hash`: Hash from Git
- `git_path`: Path in repo
- `last_synced_at`

**Composite PK:** `(tenant_id, canonical_id, environment_id)`

### workflow_hash_registry
**Purpose:** Content hash → canonical_id lookup

**Key Columns:**
- `tenant_id`, `content_hash` (composite PK)
- `canonical_id`: Workflow this hash belongs to
- `workflow_payload` (JSONB): Full workflow for collision detection
- `created_at`, `updated_at`

**Purpose:** Enables auto-linking untracked workflows by hash match

## 3.3 Promotion & Deployment Tables

### pipelines
**Purpose:** Promotion pipeline definitions

**Key Columns:**
- `id` (UUID PK), `tenant_id` (UUID FK)
- `provider`: n8n
- `name`, `description`
- `stages` (JSONB): Ordered stages with gates
- `is_active` (bool)

**Stages Schema:**
```json
{
  "stages": [
    {
      "name": "dev-to-staging",
      "source_environment_id": "...",
      "target_environment_id": "...",
      "gates": {
        "requireCleanDrift": true,
        "allowOverwritingHotfixes": false,
        "allowForcePromotionOnConflicts": false,
        "allowPlaceholderCredentials": false
      }
    }
  ]
}
```

### promotions
**Purpose:** Promotion execution records

**Key Columns:**
- `id` (UUID PK), `tenant_id` (UUID FK)
- `pipeline_id` (UUID FK)
- `source_environment_id`, `target_environment_id`
- `status`: pending/pending_approval/approved/running/completed/failed/rolled_back
- `workflow_selections` (JSONB): Which workflows to promote
- `gate_results` (JSONB): Gate check results
- `source_snapshot_id`: Snapshot of source
- `target_pre_snapshot_id`: Snapshot before promotion
- `target_post_snapshot_id`: Snapshot after promotion
- `execution_result` (JSONB): Detailed results + rollback info
- `created_by`, `approved_by`
- `created_at`, `updated_at`, `completed_at`

### deployments
**Purpose:** Deployment tracking (wrapper around promotions)

**Key Columns:**
- `id` (UUID PK), `tenant_id` (UUID FK)
- `promotion_id` (UUID FK)
- `status`: pending/scheduled/running/completed/failed
- `scheduled_for` (timestamp, nullable)
- `started_at`, `finished_at`
- `summary_json` (JSONB)
- `is_deleted` (bool)

### deployment_workflows
**Purpose:** Per-workflow deployment results

**Key Columns:**
- `id` (UUID PK)
- `deployment_id` (UUID FK)
- `workflow_id`, `workflow_name`
- `status`: success/failed/skipped
- `error_message`
- `promoted_at`

### snapshots
**Purpose:** Point-in-time backups

**Key Columns:**
- `id` (UUID PK), `tenant_id`, `environment_id`
- `snapshot_type`: pre_promotion/post_promotion/manual_backup
- `workflows` (JSONB): Workflow data
- `git_commit_sha`
- `created_by`, `created_at`

## 3.4 Drift Management Tables

### drift_incidents
**Purpose:** Drift incident lifecycle

**Key Columns:**
- `id` (UUID PK), `tenant_id`, `environment_id`
- `status`: detected/acknowledged/stabilized/reconciled/closed/expired/cancelled
- `title`, `summary` (JSONB)
- `detected_at`, `acknowledged_at`, `stabilized_at`, `reconciled_at`, `closed_at`
- `detected_by`, `acknowledged_by`, `stabilized_by`, `reconciled_by`, `closed_by`
- `owner_user_id`: Assigned owner
- `reason`: Stabilization reason
- `ticket_ref`: External ticket reference
- `expires_at`: TTL expiration
- `severity`: critical/high/medium/low
- `affected_workflows` (JSONB): List of workflows
- `drift_snapshot` (JSONB): Immutable snapshot
- `resolution_type`: promote/revert/replace/acknowledge
- `resolution_details` (JSONB)
- `payload_purged_at`: When snapshot purged
- `is_deleted`, `deleted_at`

**Migration:** `add_drift_incident_lifecycle.py`

### drift_policies
**Purpose:** Tenant-level drift governance

**Key Columns:**
- `id` (UUID PK), `tenant_id`, `environment_id` (nullable)
- `severity_ttls` (JSONB): TTL per severity
  ```json
  {
    "critical": 24,  // hours
    "high": 48,
    "medium": 72,
    "low": 168
  }
  ```
- `enforce_ttl`, `enforce_sla` (bool)
- `auto_create_incidents`, `block_on_active_drift` (bool)
- `closed_incident_retention_days`
- `reconciliation_artifact_retention_days`

### drift_approvals
**Purpose:** Approval workflow for drift operations

**Key Columns:**
- `id` (UUID PK), `incident_id`
- `approval_type`: acknowledge/extend_ttl/close/reconcile
- `status`: pending/approved/rejected
- `requested_by`, `reviewed_by`
- `request_reason`, `review_notes`
- `ttl_extension_hours`
- `created_at`, `reviewed_at`

### drift_check_history
**Purpose:** Historical drift check log

**Key Columns:**
- `id` (UUID PK), `tenant_id`, `environment_id`
- `check_type`: scheduled/manual
- `drift_found` (bool)
- `workflows_checked`, `workflows_with_drift`
- `check_duration_ms`, `checked_at`

## 3.5 Execution Tables

### executions
**Purpose:** Workflow execution records

**Key Columns:**
- `id` (UUID PK), `tenant_id`, `environment_id`, `provider`
- `workflow_id`, `workflow_name`
- `n8n_execution_id`
- `normalized_status`: success/error/running/waiting
- `started_at`, `finished_at`, `execution_time` (ms)
- `error_message`, `error_node`
- `mode`: manual/trigger/webhook

**Indexes:**
- `(tenant_id, environment_id, started_at)`
- `(tenant_id, workflow_id, started_at)`

---

# 4. Sync Flows & Reconciliation

## 4.1 Sync Type Overview

```
SYNC TYPE              DIRECTION        FREQUENCY       SOURCE OF TRUTH
─────────────────────────────────────────────────────────────────────────
Environment Sync       n8n → DB         On-demand       n8n runtime
Repository Sync        Git → DB         On-demand       Git repository
Reconciliation         DB → DB          After syncs     Database comparison
Drift Detection        Git ↔ n8n        Every 5 min     Comparison result
Promotion             Env A → Env B     Manual/Scheduled Source environment
```

## 4.2 Environment Sync Flow

**Service:** `n8n-ops-backend/app/services/canonical_env_sync_service.py`
**API:** `POST /api/v1/canonical/sync/request`
**Trigger:** Manual or scheduler

### Steps

1. **Fetch Workflows from n8n**
   - Call n8n API: `GET /api/v1/workflows`
   - Use provider adapter: `ProviderRegistry.get_adapter_for_environment()`
   - Returns list of all workflows in environment

2. **Process Each Workflow (Batched)**
   - Batch size: 25 workflows (configurable)
   - For each workflow:
     - Normalize JSON (remove metadata)
     - Compute content hash (SHA256)
     - Check for existing mapping in `workflow_env_map`

3. **Auto-Link or Create Untracked**
   - **If hash found in registry:**
     - Link to existing canonical_id
     - Set status = `linked`
   - **If hash not found:**
     - Create new mapping with status = `untracked`
     - Canonical_id = NULL

4. **Mark Missing Workflows**
   - Workflows in DB but not in current n8n fetch
   - Update status: `linked` → `missing`

5. **Checkpoint Progress**
   - Save progress after each batch
   - Allows resume on failure

### Code References

**File:** `canonical_env_sync_service.py`
- Lines 92-300+: Main sync logic
- Lines 179-285: Batch processing
- Lines 370-376: Short-circuit optimization
- Lines 495-554: Auto-link logic
- Lines 727-785: Missing workflow detection

## 4.3 Repository Sync Flow

**Service:** `n8n-ops-backend/app/services/canonical_repo_sync_service.py`
**API:** `POST /api/v1/canonical/sync-repo`
**Trigger:** Manual or scheduler

### Steps

1. **Fetch Workflows from Git**
   - Use GitHub API: `GitHubService.get_all_workflows_from_github()`
   - Filter by environment type folder (dev/staging/prod)
   - Parse JSON files

2. **Process Each Git Workflow**
   - Compute git_content_hash
   - Look up canonical_id by file path
   - Upsert `canonical_workflow_git_state` record

3. **Update Canonical Workflows**
   - If workflow doesn't exist: create new canonical_workflow
   - If exists: update workflow_definition and content_hash

4. **Detect Deletions**
   - Workflows in DB but not in Git
   - Mark as soft-deleted or flag for review

### Code References

**File:** `canonical_repo_sync_service.py`
- Lines 50-200: Git fetch logic
- Lines 200-350: Process git workflows
- GitHub service integration

## 4.4 Reconciliation Flow

**Service:** `n8n-ops-backend/app/services/canonical_reconciliation_service.py`
**Trigger:** After environment or repository sync

### Purpose

Compare workflow states between:
- Git and environment
- Source environment and target environment

### Diff Status Determination

**File:** `app/services/diff_service.py:compare_workflows()`

| Diff Status | Source | Target | Git | Meaning |
|-------------|--------|--------|-----|---------|
| **unchanged** | ✅ Hash A | ✅ Hash A | ✅ Hash A | All three match perfectly |
| **modified** | ✅ Hash A | ✅ Hash B | ✅ Hash A | Target differs from source & Git |
| **added** | ✅ Present | ❌ Absent | ✅ Present | Workflow in source/Git, not in target |
| **target_only** | ❌ Absent | ✅ Present | ❌ Absent | Workflow only in target (not in Git) |
| **conflict** | ✅ Hash A | ✅ Hash B | ✅ Hash C | All three have different hashes |
| **target_hotfix** | ✅ Present | ✅ Present (newer) | ✅ Present | Target modified after Git commit |

### Comparison Logic

**Ignored Fields:**
- `id`, `createdAt`, `updatedAt`, `versionId`
- `triggerCount`, `staticData`, `meta`, `hash`
- `active`, `tags`, `tagIds`
- Node: `position`, `positionAbsolute`, `id`, `webhookId`

**Compared Fields:**
- `name` (string equality)
- `active` (boolean equality)
- `nodes` (deep comparison by node name)
  - `type`, `parameters`, `position`
- `connections` (deep JSON equality)
- `settings` (deep JSON equality)

**Code Reference:**
**File:** `diff_service.py`
- Lines 71-90: IGNORED_FIELDS
- Lines 238-324: compare_workflows()
- Lines 104-189: Node comparison

---

# 5. Promotion & Deployment Pipeline

## 5.1 Promotion Flow Overview

**Standard Flow:** `dev → staging → prod`

**Service:** `n8n-ops-backend/app/services/promotion_service.py`
**API:** `POST /api/v1/promotions`

### Promotion Phases

```
┌────────────────────────┐
│  1. Pre-flight         │
│     Validation         │
│  - Policy gates        │
│  - Drift checks        │
│  - Credential mapping  │
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│  2. Pre-Promotion      │
│     Snapshot           │
│  - Capture target      │
│  - Store snapshot ID   │
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│  3. Workflow           │
│     Promotion          │
│  - Transform each      │
│  - Push to target      │
│  - Update mappings     │
└───────────┬────────────┘
            │
     ┌──────┴──────┐
     │             │
     ▼             ▼
┌─────────┐   ┌─────────┐
│ SUCCESS │   │ FAILURE │
└────┬────┘   └────┬────┘
     │             │
     │             ▼
     │        ┌──────────┐
     │        │ ROLLBACK │
     │        │ - Restore│
     │        └──────────┘
     │
     ▼
┌────────────────────────┐
│  4. Post-Promotion     │
│     Snapshot           │
│  - Capture final state │
│  - Sidecar Git update  │
└────────────────────────┘
```

## 5.2 Promotion Validation

**Service:** `promotion_validation_service.py`

### Gate Checks

| Gate | Purpose | Block Condition |
|------|---------|----------------|
| `requireCleanDrift` | No active drift in target | Drift detected AND policy = true |
| `allowOverwritingHotfixes` | Target workflows newer than source | Hotfix detected AND policy = false |
| `allowForcePromotionOnConflicts` | Git conflicts present | Conflict detected AND policy = false |
| `allowPlaceholderCredentials` | Missing credential mappings | Unmapped credential AND policy = false |

### Credential Mapping Validation

**File:** `promotion_validation_service.py:check_credentials_exist()`

1. Extract all credential references from source workflows
2. Look up credential mappings: source credential ID → target credential ID
3. If any missing:
   - `allowPlaceholderCredentials = false` → Block promotion
   - `allowPlaceholderCredentials = true` → Allow, log warning

## 5.3 Workflow Transformations

**File:** `promotion_service.py:_apply_transformations()`

### Transformations Applied

1. **Credential Rewriting**
   - Replace source credential IDs with target credential IDs
   - Use credential mapping table
   - Preserve credential names for audit

2. **Environment Variable Substitution**
   - Replace {{env.VAR_NAME}} placeholders
   - Use target environment variables
   - Validation: all placeholders resolved

3. **n8n Instance URL Updates**
   - Update webhook URLs
   - Update n8n instance references
   - Preserve relative paths

4. **Node ID Regeneration**
   - Generate new UUIDs for nodes (if required by provider)
   - Preserve node names and connections
   - Update connection references

## 5.4 Rollback Mechanism

**File:** `promotion_service.py:_rollback_promotion()`

### Trigger Conditions

- Any workflow fails to promote
- Gate validation fails mid-execution
- API errors during promotion
- Manual rollback requested

### Rollback Steps

1. **Fetch Pre-Promotion Snapshot**
   - Retrieve by `target_pre_snapshot_id`
   - Contains all workflows before promotion

2. **Restore Workflows**
   - For each successfully promoted workflow:
     - Restore from snapshot via n8n API
     - Update or create if workflow missing
   - Best-effort: continue on errors

3. **Retry Logic**
   - Transient errors: retry up to 3 attempts with backoff
   - Permanent errors: log and continue
   - Rollback result includes all errors

4. **Update Promotion Status**
   - Mark as `FAILED` or `ROLLED_BACK`
   - Store rollback result in `execution_result.rollback_result`
   - Audit log all actions

### Edge Cases Handled

**File:** Tests in `tests/test_promotion_atomicity.py`

1. **Missing workflows during rollback**
   - Code: Falls back to create if update fails (404/400)
   - Test: `test_rollback_creates_workflow_if_not_exists`

2. **Transient provider errors**
   - Code: Bounded retries with exponential backoff
   - Test: `test_rollback_retries_transient_error_and_succeeds`

3. **Partial promotions**
   - Code: Always trigger rollback on first failure
   - Test: `TestExecutePromotionWithRollback` suite

4. **Legacy environments without git_folder**
   - Code: Falls back to environment_type lookup
   - Behavior: Resilient for non-canonical setups

## 5.5 Deployment Scheduling

**Service:** `deployment_scheduler.py`
**Background Job:** Continuous loop

### Scheduler Logic

```python
async def _scheduler_loop():
    while _scheduler_running:
        # Query pending scheduled deployments
        deployments = fetch_deployments(
            status='scheduled',
            scheduled_for__lte=now()
        )

        for deployment in deployments:
            # Update status: scheduled → running
            await execute_deployment(deployment)

        await asyncio.sleep(10)  # 10-second polling interval
```

### Stale Deployment Cleanup

**File:** `main.py:startup_event()` (lines 448-481)

**Logic:**
- On app startup, mark `RUNNING` deployments older than 1 hour as `FAILED`
- Prevents stuck deployments from blocking scheduler

---

# 6. Drift Detection & Incident Management

## 6.1 Drift Detection Logic

**Service:** `n8n-ops-backend/app/services/drift_detection_service.py`
**Scheduler:** `drift_scheduler.py`
**Frequency:** Every 5 minutes (configurable)

### Detection Algorithm

**File:** `drift_detection_service.py:detect_drift()`

```
1. Validate Git Configuration
   ├─ Check git_repo_url exists
   ├─ Check git_pat exists
   └─ Return UNKNOWN if missing

2. Fetch Runtime Workflows
   ├─ Use ProviderRegistry adapter
   ├─ Call adapter.get_workflows()
   └─ Return ERROR if fetch fails

3. Fetch Git Workflows
   ├─ Parse repo URL into owner/name
   ├─ Create GitHubService instance
   ├─ Call get_all_workflows_from_github(environment_type)
   └─ Return ERROR if fetch fails

4. Compare Each Runtime Workflow
   ├─ Build git_by_name map: {workflow.name: workflow}
   ├─ For each runtime workflow:
   │   ├─ Look up by name in git_by_name
   │   ├─ If NOT found: not_in_git_count++, mark as "added_in_runtime"
   │   └─ If found: compare_workflows(git, runtime)
   │       ├─ If drift: with_drift_count++, mark as "modified"
   │       └─ If no drift: in_sync_count++
   └─ Return affected_workflows list

5. Check Tracked Workflows
   ├─ Query workflow_environment_map for this environment
   ├─ If count == 0: UNTRACKED
   └─ Else: DRIFT_DETECTED if (with_drift > 0 OR not_in_git > 0) else IN_SYNC

6. Update Environment Status
   └─ Call _update_environment_drift_status(drift_status, summary)
```

### Drift Status Determination

**File:** `drift_detection_service.py` (Lines 282-296)

| Git Configured | Tracked Workflows | Runtime Workflows with Drift | Runtime Workflows Not in Git | Final Status |
|----------------|-------------------|------------------------------|------------------------------|--------------|
| ❌ No | N/A | N/A | N/A | **UNKNOWN** |
| ✅ Yes (fetch error) | N/A | N/A | N/A | **ERROR** |
| ✅ Yes | 0 | N/A | N/A | **UNTRACKED** |
| ✅ Yes | >0 | 0 | 0 | **IN_SYNC** |
| ✅ Yes | >0 | >0 | any | **DRIFT_DETECTED** |
| ✅ Yes | >0 | 0 | >0 | **DRIFT_DETECTED** |

### UNTRACKED vs DRIFT_DETECTED

**Critical Distinction:**

- **UNTRACKED** = No canonical workflow mappings exist (count = 0)
  - Environment has never had workflows linked to canonical IDs
  - Status determined BEFORE comparing workflows

- **DRIFT_DETECTED** = Canonical mappings exist BUT workflows differ from Git
  - Includes two sub-cases:
    1. Modified drift: `with_drift_count > 0` (workflow exists in Git but content differs)
    2. Added in runtime: `not_in_git_count > 0` (workflow exists in n8n but not in Git)

## 6.2 Drift Incident Lifecycle

**File:** `schemas/drift_incident.py:DriftIncidentStatus`

### State Machine

```
┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────┐
│ DETECTED │────▶│ ACKNOWLEDGED │────▶│ STABILIZED  │────▶│ RECONCILED │
└──────────┘     └──────────────┘     └─────────────┘     └────────────┘
     │                   │                    │                    │
     │ TTL expires       │ TTL expires        │ TTL expires        │
     ▼                   ▼                    ▼                    ▼
┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────────┐
│ EXPIRED  │     │   ESCALATED  │     │   CRITICAL  │     │   CLOSED   │
└──────────┘     └──────────────┘     │   OVERDUE   │     └────────────┘
     │                   │             └─────────────┘            ▲
     └───────────────────┴──────────────────┬────────────────────┘
                                            │
                                            │ drift resolved
                                            │ (with_drift = 0)
```

### State Definitions

| State | Definition | Requirements |
|-------|------------|--------------|
| **DETECTED** | Drift discovered, no action taken | Automatic via drift detection |
| **ACKNOWLEDGED** | Team aware, investigating | User acknowledgment via API |
| **STABILIZED** | Root cause identified, plan in place | Reason + optional owner |
| **RECONCILED** | Changes applied (revert/promote/accept) | Resolution action taken |
| **CLOSED** | Incident resolved, archived | Admin approval or auto-close |
| **EXPIRED** | TTL expired without action | Automatic after TTL |
| **ESCALATED** | Acknowledged but TTL expired | Automatic after 25% of TTL |
| **CRITICAL_OVERDUE** | Escalated and still unresolved | Automatic after 75% of TTL |

### Valid Transitions

**File:** `drift_incident_service.py:VALID_TRANSITIONS` (lines 24-30)

```python
VALID_TRANSITIONS = {
    DriftIncidentStatus.detected: [acknowledged, closed],
    DriftIncidentStatus.acknowledged: [stabilized, reconciled, closed],
    DriftIncidentStatus.stabilized: [reconciled, closed],
    DriftIncidentStatus.reconciled: [closed],
    DriftIncidentStatus.closed: [],  # Terminal state
}
```

**Admin Override:**
- Admin can force any transition except FROM closed state
- Closed is terminal even for admins

## 6.3 Policy Enforcement

### Drift Policy Schema

**Table:** `drift_policies`

**Key Columns:**
- `severity_ttls` (JSONB): TTL per severity
  ```json
  {
    "critical": 24,  // hours
    "high": 48,
    "medium": 72,
    "low": 168
  }
  ```
- `enforce_ttl` (bool): Block promotions on expired incidents
- `enforce_sla` (bool): Auto-escalate on SLA breach
- `auto_create_incidents` (bool): Auto-create on drift detection
- `block_on_active_drift` (bool): Block promotions if active drift
- `closed_incident_retention_days`: Payload retention
- `reconciliation_artifact_retention_days`: Artifact retention

### TTL Enforcement

**File:** `promotion_service.py` (pre-flight validation)

**Logic:**
1. Query all incidents for target environment
2. For each incident, check: `now() - detected_at > ttl_for_severity`
3. If any expired and `enforce_ttl = true` → Block promotion
4. Return blocked status with incident IDs

### Incident Auto-Creation

**File:** `drift_scheduler.py`

**Conditions:**
1. ✅ Drift detected (`with_drift > 0` OR `not_in_git > 0`)
2. ✅ Tenant has `drift_incidents` feature enabled
3. ✅ No active incident exists
4. ✅ Drift policy has `auto_create_incidents = true`
5. ✅ Environment matches policy scope:
   - `auto_create_for_production_only = false`: All environments
   - `auto_create_for_production_only = true`: Production only

**Severity Computation:**
```python
if affected_count >= 10:  severity = 'critical'
elif affected_count >= 5: severity = 'high'
elif affected_count >= 2: severity = 'medium'
else:                      severity = 'low'
```

## 6.4 Snapshot Payload Immutability

**Table:** `drift_incidents.drift_snapshot` (JSONB column)

### Contents

```json
{
  "workflows_affected": [...],
  "change_summary": {...},
  "detected_at": "2026-01-08T00:00:00Z",
  "environment_id": "...",
  "content_hash_before": "...",
  "content_hash_after": "..."
}
```

### Immutability Guarantee

- Once incident created, `drift_snapshot` column never modified
- Payload can be purged per retention policy
- Purge sets `payload_purged_at` timestamp
- Purging governed by `drift_policies.closed_incident_retention_days`

### Retention Rules

- **Closed incidents**: Purge after retention period
- **Open incidents**: Never purge (until closed)
- **Reconciliation artifacts**: Purge after `reconciliation_artifact_retention_days`

---

# 7. Identity & Mapping Rules

## 7.1 Canonical Identity Model

```
┌─────────────────────────────────────────────────────────────┐
│ Canonical Identity (Cross-Environment)                      │
│   canonical_id: UUID                                         │
│   ↓                                                          │
│   ├─ Git State (Per Environment)                            │
│   │    git_content_hash: SHA256                             │
│   │    git_commit_sha: string                               │
│   │    git_path: string                                     │
│   │                                                          │
│   └─ Runtime Mapping (Per Environment)                      │
│        n8n_workflow_id: string                              │
│        env_content_hash: SHA256                             │
│        status: linked | untracked | missing | ignored       │
└─────────────────────────────────────────────────────────────┘
```

**Key Insight:** `canonical_id` is the stable identity. Content hashes change with edits. n8n IDs are environment-specific.

## 7.2 Content Hash Computation

### Hash Algorithm

**Service:** `canonical_workflow_service.py:compute_workflow_hash()`

**Steps:**
1. Normalize workflow JSON (exclude metadata fields)
2. Sort keys for deterministic ordering
3. Compute SHA256 hash: `hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()`

### Normalization Rules

**File:** `promotion_service.py:normalize_workflow_for_comparison()`

**Excluded Fields:**
- Metadata: `id`, `createdAt`, `updatedAt`, `versionId`
- Runtime: `triggerCount`, `staticData`, `meta`, `hash`
- Environment-specific: `active`, `tags`, `tagIds`
- UI-specific: node `position`, `positionAbsolute`
- Credentials: Compare by name only (ID differs per env)

### Hash Storage

**workflow_env_map table:**
- `env_content_hash`: Hash of workflow as it exists in environment
- `git_content_hash`: Hash of workflow as it exists in Git

**Drift Detection:**
```python
if env_content_hash != git_content_hash:
    # Drift detected
```

## 7.3 Workflow Mapping Status

**File:** `schemas/canonical_workflow.py:WorkflowMappingStatus`

### Status Enum

```python
class WorkflowMappingStatus(str, Enum):
    LINKED = "linked"       # Has canonical_id AND n8n_workflow_id
    UNTRACKED = "untracked" # Has n8n_workflow_id but NO canonical_id
    MISSING = "missing"     # Was mapped but disappeared from n8n
    IGNORED = "ignored"     # User-marked to ignore
    DELETED = "deleted"     # Soft-deleted mapping
```

### State Transitions

```
                    ┌──────────────┐
                    │  UNTRACKED   │ (n8n workflow, no canonical_id)
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │ auto-link  │  manual    │
              ▼            ▼  link      │
         ┌─────────────────────┐        │ deleted in n8n
         │      LINKED         │        │
         │ (normal operation)  │────────┤
         └─────────┬───────────┘        │
                   │                    │
                   │ workflow           │
                   │ disappears         ▼
                   │              ┌──────────┐
                   └─────────────▶│ MISSING  │
                                  └──────────┘
                                        │
                                        │ user
                                        │ action
                                        ▼
                              ┌──────────────────┐
                              │  IGNORED/DELETED │
                              └──────────────────┘
```

### Precedence Rules

**File:** `canonical_workflow.py` (Lines 32-73)

Highest to lowest precedence:
1. **DELETED** - Once deleted, stays deleted
2. **IGNORED** - User-explicit ignore overrides system states
3. **MISSING** - If workflow disappears from n8n during sync
4. **UNTRACKED** - If no canonical_id (not mapped)
5. **LINKED** - Default operational state

## 7.4 Auto-Linking Logic

**File:** `canonical_env_sync_service.py:_try_auto_link()`

### Auto-Link Conditions

All must be true:
- ✅ Content hash exists in `workflow_hash_registry`
- ✅ Hash maps to exactly one `canonical_id` (no collision)
- ✅ Canonical workflow not soft-deleted (`deleted_at IS NULL`)
- ✅ No existing mapping for this canonical_id in this environment

### Auto-Link Flow

```python
# 1. Compute workflow hash
env_content_hash = compute_workflow_hash(workflow)

# 2. Look up hash in registry
registry_entry = query_hash_registry(tenant_id, env_content_hash)

# 3. If found and no conflicts:
if registry_entry and registry_entry.canonical_id:
    # Check for existing mapping
    existing = query_workflow_env_map(
        environment_id=environment_id,
        canonical_id=registry_entry.canonical_id
    )

    if not existing:
        # Auto-link: create mapping
        create_mapping(
            canonical_id=registry_entry.canonical_id,
            environment_id=environment_id,
            n8n_workflow_id=workflow.id,
            status="linked"
        )
    else:
        # Conflict: existing mapping for this canonical_id
        logger.warning("Cannot auto-link: canonical_id already mapped")
```

### Hash Collision Detection

**File:** `canonical_env_sync_service.py` (Lines 27-77)

**Logic:**
- When registering hash, compare new payload with existing payload
- If hashes match but payloads differ → collision detected
- Log warning, do not block operation
- Fallback: use `sha256(json + canonical_id)` for linked workflows

**Risk:** Extremely rare (SHA256 collision) but logged for investigation

---

# 8. State Machines & Lifecycle

## 8.1 Workflow Mapping Status

**File:** `schemas/canonical_workflow.py:WorkflowMappingStatus`

### States & Transitions

See Section 7.3 for detailed state machine diagram.

### Status Update Logic

**File:** `canonical_env_sync_service.py`

```python
def compute_status(mapping, workflow_in_n8n):
    # Precedence order (highest first)
    if mapping.deleted_at is not None:
        return "deleted"
    if mapping.is_ignored:
        return "ignored"
    if not workflow_in_n8n:
        return "missing"
    if mapping.canonical_id is None:
        return "untracked"
    return "linked"
```

## 8.2 Drift Incident Status

**File:** `schemas/drift_incident.py:DriftIncidentStatus`

See Section 6.2 for detailed state machine diagram.

### Auto-Transitions

**File:** `drift_incident_service.py`

- `detected → escalated`: After 25% of TTL elapsed
- `escalated → critical_overdue`: After 75% of TTL elapsed
- Any state → `closed`: When drift resolved (with_drift = 0)

### TTL Management

**Scheduler:** Separate 1-minute loop checks for expired incidents

**Logic:**
```python
async def check_ttl_expiration():
    incidents = query_incidents(
        status__in=['detected', 'acknowledged', 'stabilized'],
        expires_at__lte=now()
    )

    for incident in incidents:
        elapsed_pct = (now() - incident.detected_at) / incident.ttl

        if elapsed_pct >= 0.75:
            transition_to('critical_overdue')
        elif elapsed_pct >= 0.25:
            transition_to('escalated')
        else:
            transition_to('expired')
```

## 8.3 Promotion Status

**File:** `schemas/promotion.py:PromotionStatus`

### State Machine

```
┌──────────┐      ┌──────────────┐      ┌───────────┐
│ PENDING  │─────▶│ IN_PROGRESS  │─────▶│ COMPLETED │
└──────────┘      └──────┬───────┘      └───────────┘
                         │                     │
                         │ partial             │ all workflows
                         │ success             │ succeeded
                         ▼                     │
                  ┌──────────────┐            │
                  │  COMPLETED   │            │
                  │ WITH_ERRORS  │            │
                  └──────────────┘            │
                         │                     │
                         │ first               │
                         │ failure             │
                         ▼                     │
                  ┌──────────────┐            │
                  │   FAILED     │            │
                  │  (triggers   │            │
                  │  rollback)   │            │
                  └──────┬───────┘            │
                         │                     │
                         ▼                     │
                  ┌──────────────┐            │
                  │ ROLLED_BACK  │            │
                  └──────────────┘            │
                                              ▼
                                        (Success)
```

### Rollback Trigger

**File:** `promotion_service.py`

**Trigger:** First workflow failure during promotion

**Logic:**
```python
for workflow in workflows_to_promote:
    try:
        promote_workflow(workflow)
        successfully_promoted.append(workflow)
    except Exception as e:
        # First failure triggers rollback
        logger.error(f"Promotion failed: {e}")
        await rollback_promotion(successfully_promoted)
        mark_status('FAILED')
        return
```

## 8.4 Deployment Status

**File:** `schemas/deployment.py:DeploymentStatus`

### State Machine

```
PENDING → SCHEDULED → RUNNING → COMPLETED
   ↓          ↓          ↓
CANCELLED  CANCELLED  FAILED
```

### Stale Detection

**File:** `main.py:startup_event()` (lines 454-487)

**Logic:**
- On app startup, mark `RUNNING` deployments older than 1 hour as `FAILED`
- Prevents stuck deployments from blocking scheduler

---

# 9. Schedulers & Background Jobs

## 9.1 Scheduler Inventory

**All schedulers start automatically on app startup**
**File:** `app/main.py:startup_event()` (lines 403-451)

| Scheduler | Interval | Purpose | Selection Criteria | File |
|-----------|----------|---------|-------------------|------|
| **Deployment** | 10 seconds | Execute scheduled deployments | `status=scheduled AND scheduled_for <= now()` | `deployment_scheduler.py` |
| **Drift Detection** | 5 minutes | Detect Git ↔ n8n drift | Non-dev environments with Git configured | `drift_scheduler.py` |
| **Canonical Sync** | DISABLED (MVP) | Sync workflows to Git | Enabled via `SYNC_SCHEDULER_ENABLED=true` | `canonical_sync_scheduler.py` |
| **Health Check** | 5 minutes | Monitor environment health | All environments with health checks enabled | `health_check_scheduler.py` |
| **Rollup** | 10 minutes | Pre-compute observability metrics | All tenants | `rollup_scheduler.py` |
| **Retention Enforcement** | Daily (24 hours) | Clean up old records | Expired drift incidents, audit logs | `background_jobs/retention_job.py` |
| **TTL Expiration** | 1 minute | Auto-close expired drift incidents | Incidents with `expires_at <= now()` | Part of `drift_scheduler.py` |
| **Downgrade Enforcement** | 1 hour | Enforce grace period expiry, detect over-limit resources | Grace periods expired, resource limits exceeded | `background_jobs/downgrade_enforcement_job.py` |
| **Alert Rules Evaluation** | Configurable (default: 5 min) | Evaluate alert rules, trigger notifications | All enabled alert rules | `background_jobs/alert_rules_scheduler.py` |

## 9.2 Configuration

**File:** `app/core/config.py`

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DRIFT_CHECK_INTERVAL_SECONDS` | 300 (5 min) | Drift detection frequency |
| `TTL_CHECK_INTERVAL_SECONDS` | 60 (1 min) | Incident TTL check frequency |
| `RETENTION_CLEANUP_INTERVAL_SECONDS` | 86400 (24 hours) | Old record cleanup frequency |
| `DEPLOYMENT_CHECK_INTERVAL_SECONDS` | 10 | Deployment polling interval |
| `HEALTH_CHECK_INTERVAL_SECONDS` | 300 (5 min) | Environment health check frequency |
| `SYNC_SCHEDULER_ENABLED` | `false` | Enable automatic sync scheduler |
| `ROLLUP_INTERVAL_SECONDS` | 600 (10 min) | Observability rollup frequency |
| `DOWNGRADE_ENFORCEMENT_INTERVAL_SECONDS` | 3600 (1 hour) | Downgrade enforcement frequency |
| `ALERT_RULES_EVALUATION_INTERVAL_SECONDS` | 300 (5 min) | Alert rule evaluation frequency |

## 9.3 Drift Detection Scheduler

**File:** `app/services/drift_scheduler.py:start_all_drift_schedulers()`

### Selection Criteria

```sql
SELECT * FROM environments
WHERE tenant_id = ?
  AND environment_class != 'dev'
  AND git_repo_url IS NOT NULL
  AND git_pat IS NOT NULL
  AND tenant.has_feature('drift_detection') = true
```

### Scheduler Logic

```python
async def _drift_scheduler_loop():
    while _scheduler_running:
        environments = fetch_eligible_environments()

        for env in environments:
            # Detect drift
            result = await drift_detection_service.detect_drift(
                tenant_id=env.tenant_id,
                environment_id=env.id
            )

            # Create incident if drift found
            if result.with_drift > 0 or result.not_in_git > 0:
                await drift_incident_service.create_incident_if_needed(
                    environment_id=env.id,
                    drift_result=result
                )

        await asyncio.sleep(DRIFT_CHECK_INTERVAL_SECONDS)
```

## 9.4 Background Job Infrastructure

**File:** `app/services/background_job_service.py`

### Job Table Schema

**Table:** `background_jobs`

**Key Columns:**
- `id`, `tenant_id`, `environment_id`
- `job_type`: sync/promotion/deployment/onboarding
- `status`: pending/running/completed/failed
- `resource_type`, `resource_id`
- `progress` (JSONB): `{current, total, percentage, message}`
- `metadata` (JSONB)
- `started_at`, `completed_at`

### Job Processing

```python
async def _process_job(job):
    # Update status: pending → running
    update_job_status(job.id, 'running')

    try:
        # Dispatch to handler
        handler = get_handler(job.job_type)
        result = await handler.execute(job)

        # Update status: running → completed
        update_job_status(job.id, 'completed', result=result)
    except Exception as e:
        # Update status: running → failed
        update_job_status(job.id, 'failed', error=str(e))
```

### SSE Progress Streaming

**File:** `app/api/endpoints/sse.py:sse_background_jobs_stream()`

**Client Connection:**
```javascript
const eventSource = new EventSource('/api/v1/sse/background-jobs');

eventSource.addEventListener('job_progress', (event) => {
  const data = JSON.parse(event.data);
  console.log(`Job ${data.job_id}: ${data.progress.percentage}%`);
});
```

---

# 10. Risk Points & Failure Modes

## 10.1 Drift Detection Risks

### Git Configuration Failures

**Location:** `drift_detection_service.py:106-156`

**Risk:** Environment with missing or invalid Git credentials returns UNKNOWN status silently

**Failure Modes:**
- `git_repo_url` or `git_pat` missing → status = UNKNOWN, no error raised
- GitHub authentication fails → status = UNKNOWN
- Frontend may not distinguish between "not configured" and "temporarily failing"

**Impact:** Silent failure prevents visibility into configuration issues

**Mitigation:**
- Error field in `EnvironmentDriftSummary` provides context
- Cached status from `environments.drift_status` may be stale

### Provider Fetch Failures

**Location:** `drift_detection_service.py:158-178`

**Risk:** n8n API unreachable or returns errors during `adapter.get_workflows()`

**Failure Modes:**
- Status set to ERROR
- `affected_workflows` list empty
- Last known drift status becomes stale

**Edge Case:** Partial failures (some workflows fetch, others timeout) not explicitly handled

### UNTRACKED vs DRIFT_DETECTED Logic

**Location:** `drift_detection_service.py:283-296`

**Risk:** If all workflows are manually unlinked but still exist in n8n:
- Environment marked UNTRACKED
- Drift incidents won't be created (scheduler skips UNTRACKED)
- Actual drift may be hidden

**Impact:** Manual unlinking can mask real drift

## 10.2 Sync Service Risks

### Environment Sync Batch Processing

**Location:** `canonical_env_sync_service.py:179-285`

**Risk:** Batch processing with checkpoints

**Failure Mode:**
1. Batch starts processing workflows 0-24
2. Workflow #20 causes crash (OOM, segfault)
3. Workflows 0-19 processed but checkpoint not saved
4. On retry, workflows 0-24 reprocessed (duplicate work)

**Impact:** Inefficiency, potential duplicate logging, but data consistency preserved via upsert

### Short-Circuit Optimization Failure

**Location:** `canonical_env_sync_service.py:370-376`

**Risk:** Short-circuit relies on `n8n_updated_at` comparison

**Edge Cases:**
- n8n doesn't update `updatedAt` for certain changes (e.g., credential reassignment)
- Timestamp normalization strips timezone → false equality across DST
- If `n8n_updated_at` is NULL, short-circuit fails → full processing every time

**Impact:** Missed updates or unnecessary processing

### Hash Collision Detection

**Location:** `canonical_env_sync_service.py:27-77`

**Risk:** Hash collisions detected but only logged as warnings

**Failure Mode:**
- Two different workflows hash to same value (extremely unlikely)
- Both treated as "same canonical workflow"
- Promotion/linking logic may overwrite one with the other

**Impact:** Silent data corruption in canonical workflow registry

**Mitigation:** Warnings collected but no blocking behavior

### Missing Workflow Race Condition

**Location:** `canonical_env_sync_service.py:727-785`

**Race Condition:**
1. Sync starts, fetches workflows from n8n
2. User deletes workflow in n8n mid-sync
3. Sync completes, marks workflow as missing
4. User re-creates workflow with same ID before next sync
5. Next sync treats it as "reappeared"

**Impact:** Transient "missing" state for briefly deleted/recreated workflows

### Auto-Link Conflicts

**Location:** `canonical_env_sync_service.py:495-554`

**Failure Mode:**
1. Workflow A linked to canonical_id X in environment
2. Workflow B (different n8n ID) has same content hash as A
3. Auto-link fails for B → remains UNTRACKED
4. B is functionally identical to A but not tracked

**Impact:** Duplicate workflows not automatically reconciled

## 10.3 Promotion Service Risks

### Rollback on Partial Failure

**Location:** `promotion_service.py:49`

**Failure Modes:**
1. **Snapshot creation fails:** If GitHub API fails → promotion cannot proceed safely
2. **Rollback fetch fails:** If snapshot commit SHA inaccessible → partial state in target
3. **Rollback write fails:** If n8n API fails during restore → some workflows rolled back, others not

**Impact:** Target environment left in inconsistent state if rollback itself fails

**Mitigation:** Audit log captures all state transitions

### Credential Rewriting Errors

**Risk:** Credential mapping lookup failures

**Failure Modes:**
- Source credential ID not found in mapping table
- Target credential doesn't exist in target n8n
- Credential name mismatch between environments

**Impact:**
- `allowPlaceholderCredentials = false` → Promotion blocked
- `allowPlaceholderCredentials = true` → Workflows promoted with invalid credentials

### Idempotency Hash Comparison

**Risk:** Normalization may skip legitimate differences

**Edge Cases:**
- Excluded field actually contains semantic logic
- Credential name change not reflected in hash
- Node position change affects execution order (rare)

**Impact:** "No changes" detected when real changes exist

## 10.4 Multi-Tenant Isolation Risks

### RLS Policy Coverage Gaps

**Status:** 12 of 76 tables have RLS enabled (15.8%)

**Risk:**
- Non-RLS tables rely on application-level filtering
- Backend uses service role key (bypasses RLS)
- If application logic has bug, cross-tenant access possible

**High-Risk Tables without RLS:**
- `workflow_env_map`: Contains workflow data
- `canonical_workflows`: Contains canonical workflow definitions
- `promotions`: Contains promotion execution details
- `drift_incidents`: Contains drift snapshots

**Mitigation:**
- Backend enforces `tenant_id` filtering in all queries
- Audit logs track all data access
- Regular security audits

### Tenant ID Injection

**Risk:** API endpoints must validate `tenant_id` from JWT

**Failure Mode:**
- Endpoint doesn't extract `tenant_id` from auth context
- Uses user-supplied `tenant_id` from request body
- Attacker can access other tenant's data

**Mitigation:**
- RBAC middleware enforces tenant context
- All endpoints use `current_user.tenant_id`
- No endpoint accepts `tenant_id` in request body

## 10.5 Data Consistency Risks

### Concurrent Sync Collisions

**Location:** `sync_orchestrator_service.py:83-149`

**Risk:** Multiple syncs triggered simultaneously

**Mitigation:**
- Sync orchestrator enforces single-sync-per-environment
- Database constraint prevents duplicate background jobs
- Idempotent upsert operations

### Stale Cached Data

**Tables with Cached Data:**
- `workflow_env_map.workflow_data` (JSONB)
- `workflow_env_map.workflow_name`
- `environments.drift_status`

**Risk:**
- Cache updated asynchronously
- Read operations may return stale data
- Cache invalidation failures

**Mitigation:**
- Cache updated during sync operations
- Timestamps track last update: `last_sync_at`, `last_drift_check_at`

### Soft-Delete Cascades

**Risk:** Soft-deleting canonical_workflow doesn't cascade to mappings

**Failure Mode:**
1. Canonical workflow soft-deleted (`deleted_at = NOW()`)
2. Mappings in `workflow_env_map` still reference it
3. Auto-link may re-link to deleted canonical workflow
4. Promotion may fail with "canonical workflow not found"

**Mitigation:**
- Soft-delete enforcement cascades to mappings
- Database constraints prevent orphaned references

---

# 11. API Reference

## 11.1 API Base URL

**Development:** `http://localhost:4000/api/v1`
**Production:** `<BACKEND_URL>/api/v1`

## 11.2 Authentication

**Method:** JWT tokens via Auth0/Supabase Auth

**Header:** `Authorization: Bearer <token>`

**Tenant Context:** Extracted from JWT claims (`tenant_id`)

## 11.3 Core Endpoints

### Environments

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/environments` | List environments | Viewer |
| GET | `/environments/{id}` | Get environment | Viewer |
| POST | `/environments` | Create environment | Admin |
| PATCH | `/environments/{id}` | Update environment | Admin |
| DELETE | `/environments/{id}` | Delete environment | Admin |
| POST | `/environments/{id}/sync` | Trigger sync | Developer |

### Workflows

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/workflows` | List workflows | Viewer |
| GET | `/workflows/{id}` | Get workflow | Viewer |
| GET | `/workflows/matrix` | Cross-environment matrix | Viewer |

### Canonical Workflows

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/canonical/workflows` | List canonical workflows | Viewer |
| GET | `/canonical/workflows/{id}` | Get canonical workflow | Viewer |
| POST | `/canonical/sync-repo` | Sync Git → canonical | Developer |
| POST | `/canonical/sync/request` | Trigger environment sync | Developer |
| GET | `/canonical/untracked` | List untracked workflows | Viewer |
| POST | `/canonical/link` | Link untracked to canonical | Developer |
| POST | `/canonical/reconcile` | Reconcile conflicts | Admin |
| GET | `/canonical/onboard/preflight` | Preflight checks | Admin |
| POST | `/canonical/onboard/inventory` | Start onboarding | Admin |
| GET | `/canonical/onboard/completion` | Check completion | Viewer |

### Promotions

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/promotions` | Create promotion | Admin + workflow_ci_cd |
| POST | `/promotions/validate` | Pre-flight checks | Developer |
| POST | `/promotions/compare` | Diff computation | Viewer |
| POST | `/promotions/execute/{deployment_id}` | Execute deployment | Admin + workflow_ci_cd |
| POST | `/promotions/{id}/approve` | Approve promotion | Admin |
| POST | `/promotions/{id}/reject` | Reject promotion | Admin |
| GET | `/promotions` | List promotions | Viewer |
| GET | `/promotions/{id}` | Get promotion | Viewer |
| GET | `/promotions/drift-check/{env_id}` | Check drift blocking | Viewer |

### Pipelines

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/pipelines` | Create pipeline | Admin + workflow_ci_cd |
| PATCH | `/pipelines/{id}` | Update pipeline | Admin + workflow_ci_cd |
| DELETE | `/pipelines/{id}` | Delete pipeline | Admin + workflow_ci_cd |
| GET | `/pipelines` | List pipelines | Viewer |
| GET | `/pipelines/{id}` | Get pipeline | Viewer |

### Deployments

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/deployments` | Schedule deployment | Admin |
| GET | `/deployments` | List deployments | Viewer |
| GET | `/deployments/{id}` | Get deployment | Viewer |
| POST | `/deployments/{id}/cancel` | Cancel deployment | Admin |

### Drift Incidents

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/incidents` | List incidents | Viewer |
| GET | `/incidents/{id}` | Get incident | Viewer |
| POST | `/incidents/check-drift` | On-demand drift check | Developer |
| POST | `/incidents/{id}/acknowledge` | Acknowledge incident | Developer |
| POST | `/incidents/{id}/stabilize` | Mark stabilized | Developer |
| POST | `/incidents/{id}/reconcile` | Reconcile drift | Admin |
| POST | `/incidents/{id}/close` | Close incident | Admin |
| POST | `/incidents/{id}/extend-ttl` | Extend TTL | Admin |

### Drift Policies

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/drift-policies` | Get policies | Viewer |
| POST | `/drift-policies` | Create/update policy | Admin |

### SSE Streams

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/sse/deployments` | Real-time deployment progress | Viewer |
| GET | `/sse/deployments/{id}` | Single deployment stream | Viewer |
| GET | `/sse/background-jobs` | All background jobs | Viewer |

### Health & Admin

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/health` | Health check | Public |
| GET | `/admin/users` | List users | Platform Admin |
| POST | `/admin/users` | Create user | Platform Admin |
| GET | `/audit-logs` | List audit logs | Admin |

## 11.4 Response Formats

### Success Response

```json
{
  "data": { ... },
  "message": "Operation successful",
  "timestamp": "2026-01-14T12:00:00Z"
}
```

### Error Response

```json
{
  "error": {
    "type": "ValidationError",
    "message": "Invalid input",
    "details": { ... }
  },
  "timestamp": "2026-01-14T12:00:00Z"
}
```

### Paginated Response

```json
{
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 235,
    "total_pages": 5
  }
}
```

---

# 12. Narrative Walkthroughs

## 12.1 Scenario: First-Time Environment Setup

See [mvp_readiness_pack/12_narrative_walkthroughs.md](./mvp_readiness_pack/12_narrative_walkthroughs.md) Section 1 for complete walkthrough.

**Summary:**

1. Admin creates environment in UI
2. User triggers manual sync
3. Sync orchestrator creates background job
4. Worker discovers workflows from n8n
5. Workflows processed in batches (25 per batch)
6. Content hashes computed
7. Auto-link attempts via hash registry
8. Untracked workflows flagged
9. Environment status updated
10. UI displays workflows matrix

## 12.2 Scenario: Promoting Workflows Dev → Staging

**Initial State:**
- Dev environment has 10 workflows (all linked)
- Staging environment empty
- Pipeline configured: dev → staging
- No active drift incidents

**Flow:**

1. **User Initiates Promotion**
   - UI: Select workflows (or promote all)
   - API: `POST /api/v1/promotions`
   - Service: `promotion_service.py:create_promotion()`

2. **Pre-Flight Validation**
   - Check policy gates
   - Verify drift status
   - Validate credential mappings
   - Result: All checks pass

3. **Create Pre-Promotion Snapshot**
   - Capture staging state (empty)
   - Store snapshot ID in promotions table

4. **Promote Each Workflow**
   - Batch: 10 workflows
   - For each workflow:
     - Fetch from dev
     - Apply transformations (credentials, env vars)
     - Push to staging n8n
     - Update workflow_env_map
     - Emit SSE progress event

5. **All Succeed → Complete**
   - Create post-promotion snapshot
   - Update promotion status: `COMPLETED`
   - Trigger sidecar Git update (non-blocking)
   - Emit SSE completion event

## 12.3 Scenario: Drift Detection & Incident Creation

**Initial State:**
- Production environment configured
- Git repo has 5 workflows
- Production n8n has 6 workflows (1 extra)
- Drift scheduler running every 5 minutes

**Flow:**

1. **Scheduler Triggers Detection**
   - Time: 12:00 PM
   - Service: `drift_scheduler.py:_drift_scheduler_loop()`
   - Selects all non-dev environments with Git configured

2. **Fetch Workflows**
   - Git: 5 workflows fetched
   - n8n: 6 workflows fetched

3. **Compare Workflows**
   - Match by name
   - 5 workflows found in both (compare hashes)
   - 1 workflow only in n8n: `not_in_git++`

4. **Determine Drift Status**
   - `with_drift = 0` (all matched workflows in sync)
   - `not_in_git = 1` (extra workflow)
   - Result: `DRIFT_DETECTED`

5. **Create Drift Incident**
   - Severity: `low` (1 affected workflow)
   - TTL: 168 hours (from policy)
   - Snapshot: Immutable payload stored
   - Status: `DETECTED`

6. **Update Environment**
   - `drift_status = DRIFT_INCIDENT_ACTIVE`
   - `active_drift_incident_id = incident.id`
   - `last_drift_detected_at = NOW()`

7. **Notify Team**
   - Email sent to environment owner
   - Slack notification (if configured)
   - UI badge shows "1 Active Incident"

## 12.4 Scenario: Promotion Failure & Rollback

**Initial State:**
- Staging has 5 workflows (all in sync)
- Promoting 3 workflows from dev
- Workflow #2 has invalid credential mapping

**Flow:**

1. **Promotion Starts**
   - Pre-promotion snapshot created
   - Status: `IN_PROGRESS`

2. **Workflow #1 Succeeds**
   - Pushed to staging n8n
   - Mapping updated

3. **Workflow #2 Fails**
   - Credential mapping not found
   - `allowPlaceholderCredentials = false`
   - Error: "Credential 'stripe-prod' not found"

4. **Rollback Triggered**
   - Fetch pre-promotion snapshot
   - Restore workflow #1 from snapshot
   - Log rollback action

5. **Mark Promotion Failed**
   - Status: `FAILED`
   - `execution_result.rollback_result` populated
   - Error details saved

6. **User Notified**
   - UI shows error message
   - Audit log entry created
   - Email notification sent

---

# Appendix A: Quick Reference Tables

## A.1 Status Quick Lookup

### Workflow Mapping Status Decision Tree

```
Is canonical_id NULL?
  ├─ YES → UNTRACKED
  └─ NO → Is workflow present in n8n?
            ├─ YES → LINKED
            └─ NO → MISSING

Is workflow soft-deleted (deleted_at NOT NULL)?
  ├─ YES → DELETED (overrides all others)
  └─ NO → (use tree above)

Is workflow explicitly ignored?
  ├─ YES → IGNORED (overrides MISSING/UNTRACKED/LINKED)
  └─ NO → (use tree above)
```

### Environment Drift Status Decision Tree

```
Is active drift incident present?
  ├─ YES → Is incident acknowledged?
  │          ├─ YES → DRIFT_INCIDENT_ACKNOWLEDGED
  │          └─ NO → DRIFT_INCIDENT_ACTIVE
  └─ NO → COUNT(linked workflows) = 0?
            ├─ YES → UNTRACKED
            └─ NO → with_drift > 0 OR not_in_git > 0?
                      ├─ YES → DRIFT_DETECTED
                      └─ NO → IN_SYNC
```

## A.2 Promotion Policy Matrix

| Policy Flag | Default | Effect When `true` | Effect When `false` |
|-------------|---------|-------------------|---------------------|
| `allowOverwritingHotfixes` | `false` | ✅ Overwrite target workflows even if newer | ❌ Block promotion if target has hotfixes |
| `allowForcePromotionOnConflicts` | `false` | ✅ Promote despite Git conflicts | ❌ Block promotion if conflicts detected |
| `allowPlaceholderCredentials` | `false` | ✅ Create placeholder credentials if mapping missing | ❌ Block promotion if credentials unmapped |
| `requireCleanDrift` | `true` | ❌ Block promotion if target has drift | ✅ Allow promotion even with drift |

## A.3 Scheduler Selection Criteria

| Scheduler | Included Environments | Excluded Environments |
|-----------|----------------------|----------------------|
| **Drift Detection** | `environment_class != 'dev'` AND `git_repo_url IS NOT NULL` AND tenant has `drift_detection` feature | Dev environments, environments without Git |
| **Deployment** | Environments with `scheduled_at <= now()` AND `status = 'pending'` | Completed/failed deployments |
| **Health Check** | Environments with `health_check_enabled = true` | Disabled environments |
| **Rollup** | All tenants | None |
| **Retention Cleanup** | All tenants | None |

---

# Appendix B: Troubleshooting Guide

## B.1 Workflow Shows as Untracked After Sync

**Symptoms:** Workflow present in n8n, sync completed, but status = `untracked`

**Diagnosis:**
1. Check if content hash exists in registry:
   ```sql
   SELECT * FROM workflow_hash_registry
   WHERE tenant_id = '<tenant_id>'
   AND content_hash = '<computed_hash>';
   ```
2. If not found → Workflow never synced to Git or hash changed
3. If found → Check for collision warning in sync logs

**Resolution:**
- Option 1: Manually link via UI
- Option 2: Trigger repository sync to register hash
- Option 3: If collision, resolve by relinking

## B.2 Promotion Blocked with "Target Hotfix" Error

**Symptoms:** Error: `TARGET_HOTFIX: Workflow 'XYZ' modified in target after Git commit`

**Diagnosis:**
```sql
SELECT n8n_workflow_id, n8n_updated_at, git_commit_timestamp
FROM workflow_env_map wem
JOIN canonical_workflow_git_state gs USING (canonical_id, environment_id)
WHERE canonical_id = '<canonical_id>' AND environment_id = '<target_env_id>';
```

**Resolution:**
- Option 1: Enable `allowOverwritingHotfixes = true`
- Option 2: Commit hotfix to Git first
- Option 3: Revert hotfix in target

## B.3 Environment Shows "DRIFT_DETECTED" But No Drift Found

**Symptoms:** `drift_status = DRIFT_DETECTED` but `with_drift = 0`

**Diagnosis:**
```sql
-- Check for untracked workflows
SELECT COUNT(*) FROM workflow_env_map
WHERE environment_id = '<env_id>'
AND canonical_id IS NULL;

-- Check not_in_git count
SELECT not_in_git FROM drift_detection_results
WHERE environment_id = '<env_id>'
ORDER BY detected_at DESC LIMIT 1;
```

**Explanation:** `DRIFT_DETECTED` triggers if `with_drift > 0 OR not_in_git > 0`. Untracked workflows count as "not in Git".

**Resolution:**
- Option 1: Link untracked workflows
- Option 2: Ignore untracked workflows
- Option 3: Delete untracked workflows from n8n

---

# Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-14 | Claude (Task T012) | Initial comprehensive report compilation from T001-T011 |

---

**End of WorkflowOps System Comprehensive Specification**

For detailed analysis of specific subsystems, refer to the individual task documentation files listed in the "Related Documentation" section at the beginning of this document.
