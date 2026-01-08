# WorkflowOps Platform - Product Requirements Document

## Document Information

| Field | Value |
|-------|-------|
| Product Name | WorkflowOps (formerly N8N Ops) |
| Version | 2.0 |
| Last Updated | January 2026 |
| Status | Production |

---

## ❗ Implementation Status Summary

The following features are **NOT YET IMPLEMENTED** (marked with ❗ throughout this document):

| Feature | Status | Notes |
|---------|--------|-------|
| Make.com Provider | ❗ NOT IMPLEMENTED | Only n8n adapter exists |
| SSO/SCIM | ❗ NOT IMPLEMENTED | Feature flags exist, no actual integration |
| Secret Vault Integration | ❗ NOT IMPLEMENTED | Feature flag exists, no vault service |
| Credential Remapping (User-facing) | ❗ NOT IMPLEMENTED | Admin matrix exists, but no promotion-time remapping |
| White-label/Custom Branding | ❗ NOT IMPLEMENTED | Feature flags exist, no UI customization |
| Scheduled Backups | ❗ NOT IMPLEMENTED | Feature flag exists, no backup scheduler service |
| SOC 2 Type II Compliance | ❗ NOT IMPLEMENTED | Planned |
| Regular Security Audits | ❗ NOT IMPLEMENTED | Planned |
| Penetration Testing | ❗ NOT IMPLEMENTED | Planned |

---

## 1. Executive Summary

### 1.1 Product Vision

WorkflowOps is a **multi-tenant, multi-provider** workflow governance and lifecycle management platform that enables enterprises to manage automation workflows across multiple environments (development, staging, production). The platform supports multiple workflow automation providers (n8n, with Make.com planned) and provides policy-based promotion, drift detection, credential management, and comprehensive observability for workflow automation infrastructure.

### 1.2 Problem Statement

Organizations using workflow automation platforms face critical challenges:

1. **Environment Sprawl**: Managing workflows across multiple instances is manual and error-prone
2. **No Promotion Controls**: Moving workflows between environments lacks governance, approvals, and audit trails
3. **Configuration Drift**: Changes made directly in production go untracked, creating compliance risks
4. **Credential Management**: Mapping credentials across environments is complex and insecure
5. **Limited Visibility**: No centralized view of workflow health, execution metrics, or deployment history
6. **No Version Control**: Workflow changes aren't tracked in Git, making rollback impossible
7. **Multi-Provider Lock-in**: Organizations using multiple automation platforms have no unified management

### 1.3 Solution Overview

WorkflowOps provides:

- **Multi-Provider Support**: Unified management for n8n (production) with Make.com ❗(NOT IMPLEMENTED)
- **Centralized Management**: Single pane of glass for all workflow automation environments
- **Governed Promotions**: Pipeline-based workflow promotions with gates and approvals
- **Drift Detection**: Automated monitoring with incident lifecycle management
- **Git Integration**: Full version control with canonical workflow tracking and snapshots
- **Execution Analytics**: Comprehensive metrics, KPIs, and health monitoring
- **Multi-Tenancy**: Complete data isolation with role-based access control
- **Enterprise Features**: ❗SSO (NOT IMPLEMENTED), audit logging, compliance tools, and SLA enforcement
- **Platform Administration**: Support console with impersonation capabilities

---

## 2. User Personas

### 2.1 DevOps Engineer / Platform Lead

**Demographics**: Technical lead responsible for workflow automation infrastructure

**Goals**:
- Ensure workflow governance across all environments
- Minimize production incidents from uncontrolled changes
- Maintain compliance and audit readiness
- Reduce manual deployment overhead

**Key Features Used**:
- Environment management and configuration
- Promotion pipeline design
- Drift policies and TTL configuration
- Admin dashboards and audit logs
- Canonical workflow tracking

### 2.2 Workflow Developer

**Demographics**: Developer building and maintaining automation workflows

**Goals**:
- Deploy workflows safely to production
- Understand what's required for promotion
- Track workflow execution and performance
- Quickly identify and fix issues

**Key Features Used**:
- Workflow management and upload
- Promotion execution
- Drift dashboard and diff viewer
- Execution analytics
- Snapshot restore

### 2.3 Security/Compliance Officer

**Demographics**: Responsible for security, compliance, and access control

**Goals**:
- Maintain audit trail of all changes
- Control who can access what
- Ensure drift is detected and remediated
- Verify credential security

**Key Features Used**:
- Audit logs with retention policies
- Role-based access control
- Drift incident management with SLA enforcement
- Credential health monitoring

### 2.4 System Administrator (Multi-tenant)

**Demographics**: Platform administrator managing multiple customer tenants

**Goals**:
- Manage customer subscriptions and billing
- Configure feature access per customer
- Handle support requests efficiently
- Monitor platform-wide health

**Key Features Used**:
- Tenant administration
- Feature overrides and entitlements
- Support console with impersonation
- Usage analytics

### 2.5 Platform Administrator

**Demographics**: Super admin with full platform access

**Goals**:
- Manage platform-wide configuration
- Provide customer support via impersonation
- Monitor platform health and billing
- Configure providers and plans

**Key Features Used**:
- Platform admin dashboard
- Impersonation system
- Provider and plan management
- System-wide audit logs

---

## 3. Feature Requirements

### 3.1 Environment Management

#### 3.1.1 Environment Configuration

**Description**: Connect and configure multiple workflow provider instances as managed environments

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| ENV-001 | Create environment with name, URL, and API key | P0 | ✅ Done |
| ENV-002 | Test connection before saving | P0 | ✅ Done |
| ENV-003 | Configure GitHub repository for backups | P1 | ✅ Done |
| ENV-004 | Test GitHub connection | P1 | ✅ Done |
| ENV-005 | Assign environment class (dev/staging/production) | P0 | ✅ Done |
| ENV-006 | View environment list with sync status | P0 | ✅ Done |
| ENV-007 | Delete environment with confirmation | P1 | ✅ Done |
| ENV-008 | View environment limits based on plan | P1 | ✅ Done |
| ENV-009 | Provider selection (n8n, Make) | P0 | ✅ Done |
| ENV-010 | Environment type customization (tenant-configurable) | P1 | ✅ Done |
| ENV-011 | Drift handling mode per environment | P1 | ✅ Done |
| ENV-012 | Environment health heartbeat tracking | P1 | ✅ Done |

**Environment Classes** (deterministic for policy enforcement):
- `dev` - Development environment
- `staging` - Staging/QA environment
- `production` - Production environment

#### 3.1.2 Environment Synchronization

**Description**: Sync workflow data from provider instances

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| ENV-013 | Full sync: workflows, credentials, tags, users | P0 | ✅ Done |
| ENV-014 | Selective sync: workflows only | P1 | ✅ Done |
| ENV-015 | Selective sync: credentials only | P1 | ✅ Done |
| ENV-016 | Selective sync: executions only | P1 | ✅ Done |
| ENV-017 | Background job with progress tracking | P0 | ✅ Done |
| ENV-018 | Live log streaming during sync via SSE | P1 | ✅ Done |
| ENV-019 | Canonical environment sync integration | P0 | ✅ Done |

#### 3.1.3 Environment Capabilities (Policy-Based Action Guards)

**Description**: Policy-based action guards per environment class

**Environment Class Policies**:
| Action | Development | Staging | Production |
|--------|-------------|---------|------------|
| Direct Edit | ✅ Allowed | ⚠️ Warning | ❌ Blocked |
| Activate/Deactivate | ✅ Allowed | ✅ Allowed | 🔒 Requires Approval |
| Delete | ✅ Allowed | ⚠️ Warning | 🔒 Requires Approval |
| Upload | ✅ Allowed | ✅ Allowed | ❌ Blocked |
| Soft Delete (Archive) | ✅ Allowed | ✅ Allowed | 🔒 Admin Only |
| Hard Delete | ❌ Blocked | ❌ Blocked | 🔒 Admin Only |

### 3.2 Multi-Provider Support

#### 3.2.1 Provider Architecture

**Description**: Support for multiple workflow automation platforms

**Supported Providers**:
| Provider | Status | Description |
|----------|--------|-------------|
| n8n | ✅ Production | Full support for n8n instances |
| Make.com | ❗ NOT IMPLEMENTED | Future support for Make.com (formerly Integromat) - adapter not built |

**Provider Features**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PROV-001 | Provider-specific adapters | P0 | ✅ Done |
| PROV-002 | Provider registry for dynamic loading | P0 | ✅ Done |
| PROV-003 | Provider-scoped entitlements | P0 | ✅ Done |
| PROV-004 | Provider-specific workflows, credentials, tags | P0 | ✅ Done |
| PROV-005 | Provider selection in environment setup | P0 | ✅ Done |

#### 3.2.2 Provider Subscriptions

**Description**: Tenants can subscribe to multiple providers independently

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PROV-006 | Per-provider subscription management | P0 | ✅ Done |
| PROV-007 | Provider-specific plans (Free, Pro, Agency, Enterprise) | P0 | ✅ Done |
| PROV-008 | Stripe checkout for provider subscriptions | P0 | ✅ Done |
| PROV-009 | Provider entitlements API | P0 | ✅ Done |
| PROV-010 | Free plan auto-subscription | P1 | ✅ Done |

### 3.3 Workflow Management

#### 3.3.1 Workflow Catalog

**Description**: Browse and manage workflows across environments

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| WF-001 | List all workflows with search | P0 | ✅ Done |
| WF-002 | Filter by environment, tags, status | P0 | ✅ Done |
| WF-003 | View workflow details (nodes, connections) | P0 | ✅ Done |
| WF-004 | Interactive workflow graph visualization | P1 | ✅ Done |
| WF-005 | Workflow complexity analysis | P2 | ✅ Done |
| WF-006 | Bulk selection and actions | P1 | ✅ Done |
| WF-007 | Workflow action policy enforcement | P0 | ✅ Done |
| WF-008 | Sync status tracking (in_sync, local_changes, etc.) | P1 | ✅ Done |

#### 3.3.2 Workflow Operations

**Description**: Perform actions on workflows with policy enforcement

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| WF-009 | Upload workflows (JSON/ZIP) | P0 | ✅ Done |
| WF-010 | Activate/deactivate workflows | P0 | ✅ Done |
| WF-011 | Soft delete (archive) workflows | P0 | ✅ Done |
| WF-012 | Hard delete with confirmation | P1 | ✅ Done |
| WF-013 | Download workflows as ZIP | P1 | ✅ Done |
| WF-014 | Tag management | P1 | ✅ Done |
| WF-015 | Workflow restore from archive | P1 | ✅ Done |

#### 3.3.3 GitHub Integration

**Description**: Version control workflows in Git

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| WF-016 | Backup workflows to GitHub | P1 | ✅ Done |
| WF-017 | Restore workflows from GitHub | P1 | ✅ Done |
| WF-018 | View Git drift status | P1 | ✅ Done |
| WF-019 | Automatic backup on promotion | P1 | ✅ Done |
| WF-020 | GitHub webhook integration | P2 | ✅ Done |

### 3.4 Canonical Workflow System

#### 3.4.1 Canonical Workflow Management

**Description**: Git-backed source of truth for workflows with cross-environment tracking

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| CAN-001 | Track canonical workflow definitions | P1 | ✅ Done |
| CAN-002 | Map workflows to environments via workflow_env_map | P1 | ✅ Done |
| CAN-003 | Sync Git repository to canonical state | P1 | ✅ Done |
| CAN-004 | Sync environment to canonical state | P1 | ✅ Done |
| CAN-005 | Reconcile Git and environment state | P1 | ✅ Done |
| CAN-006 | Content hash tracking for drift detection | P1 | ✅ Done |

#### 3.4.2 Untracked Workflow Detection

**Description**: Identify workflows not in the canonical system

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| CAN-007 | Detect untracked workflows | P1 | ✅ Done |
| CAN-008 | List untracked workflows by environment | P1 | ✅ Done |
| CAN-009 | Onboard untracked workflows | P1 | ✅ Done |
| CAN-010 | Bulk onboarding | P2 | ✅ Done |
| CAN-011 | Scan environments for new workflows | P1 | ✅ Done |

#### 3.4.3 Workflow Matrix

**Description**: Cross-environment workflow status view

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| CAN-012 | Matrix view of workflows across environments | P1 | ✅ Done |
| CAN-013 | Show sync status per environment (linked, untracked, drift, out_of_date) | P1 | ✅ Done |
| CAN-014 | Identify missing deployments | P1 | ✅ Done |
| CAN-015 | Action buttons per cell (Sync, View) | P1 | ✅ Done |

#### 3.4.4 Onboarding Flow

**Description**: Guided onboarding for canonical workflow system

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| CAN-016 | Preflight checks for onboarding readiness | P1 | ✅ Done |
| CAN-017 | Inventory phase (read-only scan) | P1 | ✅ Done |
| CAN-018 | Migration PR creation | P2 | ✅ Done |
| CAN-019 | Completion check API | P1 | ✅ Done |

### 3.5 Promotion Pipeline System

#### 3.5.1 Pipeline Definition

**Description**: Define promotion paths between environments

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PIPE-001 | Create pipeline with name and description | P0 | ✅ Done |
| PIPE-002 | Define ordered stages (source → target) | P0 | ✅ Done |
| PIPE-003 | Configure gates per stage | P1 | ✅ Done |
| PIPE-004 | Configure approval requirements | P1 | ✅ Done |
| PIPE-005 | Set scheduled promotion windows | P2 | ✅ Done |
| PIPE-006 | Visual pipeline editor | P1 | ✅ Done |
| PIPE-007 | Provider-scoped pipelines | P0 | ✅ Done |

**Gate Types**:
- `requireCleanDrift` - No active drift incidents
- `runPreFlightValidation` - Validate workflow structure
- `credentialsExistInTarget` - Required credentials available
- `nodesSupportedInTarget` - All nodes compatible
- `webhooksAvailable` - Webhook endpoints configured
- `targetEnvironmentHealthy` - Target reachable
- `maxAllowedRiskLevel` - Risk threshold (Low/Medium/High)

**Stage Policy Flags**:
- `allowPlaceholderCredentials` - Allow missing credentials
- `allowOverwritingHotfixes` - Override target changes
- `allowForcePromotionOnConflicts` - Force promotion

#### 3.5.2 Promotion Execution

**Description**: Execute workflow promotions through pipelines

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PROMO-001 | Initiate promotion with workflow selection | P0 | ✅ Done |
| PROMO-002 | Pre-flight validation (drift, credentials) | P0 | ✅ Done |
| PROMO-003 | Display diff between environments | P0 | ✅ Done |
| PROMO-004 | Submit for approval if required | P1 | ✅ Done |
| PROMO-005 | Execute promotion atomically | P0 | ✅ Done |
| PROMO-006 | Create pre-promotion snapshot | P0 | ✅ Done |
| PROMO-007 | Rollback on failure | P1 | ✅ Done |
| PROMO-008 | Check drift policy blocking | P1 | ✅ Done |
| PROMO-009 | Risk level calculation per workflow | P1 | ✅ Done |

**Promotion States**:
```
PENDING → PENDING_APPROVAL → APPROVED → RUNNING → COMPLETED
                                    ↘ FAILED
                          ↘ REJECTED
            ↘ CANCELLED
```

**Diff Status Types**:
| Status | Description |
|--------|-------------|
| ADDED | Workflow only in source |
| MODIFIED | Exists in both, source is newer |
| TARGET_ONLY | Workflow only in target |
| UNCHANGED | Identical content |
| TARGET_HOTFIX | Target has newer version (conflict) |

**Risk Levels**:
| Level | Triggers |
|-------|----------|
| Low | Rename only, minor changes |
| Medium | Error handling, settings changes |
| High | Credentials, expressions, triggers, HTTP, code, routing |

#### 3.5.3 Deployment Tracking

**Description**: Track deployment history and status

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DEP-001 | List all deployments with filters | P0 | ✅ Done |
| DEP-002 | View deployment details | P0 | ✅ Done |
| DEP-003 | View per-workflow deployment results | P1 | ✅ Done |
| DEP-004 | Schedule future deployments | P2 | ✅ Done |
| DEP-005 | Cancel pending deployments | P1 | ✅ Done |
| DEP-006 | Soft delete deployments | P1 | ✅ Done |
| DEP-007 | Stale deployment cleanup on startup | P1 | ✅ Done |
| DEP-008 | Real-time progress via SSE | P1 | ✅ Done |

### 3.6 Drift Detection & Incident Management

#### 3.6.1 Drift Detection

**Description**: Identify configuration drift between environments

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| DRIFT-001 | Scheduled drift detection | P1 | ✅ Done |
| DRIFT-002 | On-demand drift check | P0 | ✅ Done |
| DRIFT-003 | Compare workflow JSON with detailed diff | P0 | ✅ Done |
| DRIFT-004 | Detect untracked changes in production | P1 | ✅ Done |
| DRIFT-005 | Skip drift detection for DEV environments | P1 | ✅ Done |
| DRIFT-006 | Drift handling modes (warn_only, manual_override, require_attestation) | P1 | ✅ Done |
| DRIFT-007 | Drift check history tracking | P2 | ✅ Done |

#### 3.6.2 Incident Management

**Description**: Manage drift incidents through full lifecycle

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| INC-001 | Create incident when drift detected | P0 | ✅ Done |
| INC-002 | Incident severity levels (critical/high/medium/low) | P1 | ✅ Done |
| INC-003 | Acknowledge incidents | P0 | ✅ Done |
| INC-004 | Stabilize incidents | P1 | ✅ Done |
| INC-005 | Reconcile incidents | P1 | ✅ Done |
| INC-006 | Close incidents with resolution tracking | P0 | ✅ Done |
| INC-007 | Incident dashboard with filters | P1 | ✅ Done |
| INC-008 | Affected workflows tracking | P1 | ✅ Done |
| INC-009 | Drift snapshot payload | P1 | ✅ Done |
| INC-010 | Owner assignment | P2 | ✅ Done |
| INC-011 | Ticket reference linking | P2 | ✅ Done |

**Incident Lifecycle States**:
```
DETECTED → ACKNOWLEDGED → STABILIZED → RECONCILED → CLOSED
```

**Resolution Types**:
- `promote` - Promote changes from source
- `revert` - Revert to previous state
- `replace` - Replace with canonical version
- `acknowledge` - Accept drift as-is

#### 3.6.3 Drift Policies (Agency/Enterprise)

**Description**: Configure drift governance policies

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| POL-001 | Set TTL per severity level | P2 | ✅ Done |
| POL-002 | Configure SLA enforcement | P2 | ✅ Done |
| POL-003 | Auto-create incidents setting | P2 | ✅ Done |
| POL-004 | Block deployments on expired incidents | P2 | ✅ Done |
| POL-005 | Block deployments on active drift | P2 | ✅ Done |
| POL-006 | Notification thresholds | P2 | ✅ Done |
| POL-007 | Expiration warning hours | P2 | ✅ Done |
| POL-008 | Retention policies for closed incidents | P2 | ✅ Done |
| POL-009 | Retention for reconciliation artifacts | P2 | ✅ Done |
| POL-010 | Retention for approvals | P2 | ✅ Done |

**Default TTL Configuration**:
| Severity | Default TTL |
|----------|-------------|
| Critical | 24 hours |
| High | 48 hours |
| Medium | 72 hours |
| Low | 168 hours (1 week) |

#### 3.6.4 Drift Approvals

**Description**: Approval workflow for drift operations

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| APPR-001 | Request approval for drift actions | P2 | ✅ Done |
| APPR-002 | Approval types (acknowledge, extend_ttl, close, reconcile) | P2 | ✅ Done |
| APPR-003 | Approval/rejection workflow | P2 | ✅ Done |
| APPR-004 | TTL extension requests | P2 | ✅ Done |
| APPR-005 | Approval audit trail | P2 | ✅ Done |

### 3.7 Snapshots & Restore

#### 3.7.1 Snapshot Management

**Description**: Version control for environment state

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| SNAP-001 | Create manual snapshots | P1 | ✅ Done |
| SNAP-002 | Auto-snapshot before promotions | P0 | ✅ Done |
| SNAP-003 | List snapshots by environment | P0 | ✅ Done |
| SNAP-004 | View snapshot metadata | P1 | ✅ Done |
| SNAP-005 | Git-backed snapshot storage | P1 | ✅ Done |
| SNAP-006 | Post-promotion snapshots | P1 | ✅ Done |

**Snapshot Types**:
- `auto_backup` - ❗ Scheduled automatic backup (NOT IMPLEMENTED - no backup scheduler exists)
- `pre_promotion` - Before promotion execution
- `post_promotion` - After successful promotion
- `manual_backup` - User-initiated backup

#### 3.7.2 Restore Operations

**Description**: Restore workflows from snapshots

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| SNAP-007 | Restore single workflow | P1 | ✅ Done |
| SNAP-008 | Restore multiple workflows | P1 | ✅ Done |
| SNAP-009 | Full environment restore | P2 | ✅ Done |
| SNAP-010 | Preview restore diff | P1 | ✅ Done |
| SNAP-011 | Rollback state tracking | P1 | ✅ Done |
| SNAP-012 | Compare two snapshots | P1 | ✅ Done |

### 3.8 Execution Analytics

#### 3.8.1 Execution Monitoring

**Description**: Track workflow execution history

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| EXEC-001 | List executions with filters | P0 | ✅ Done |
| EXEC-002 | Filter by workflow, environment, status | P0 | ✅ Done |
| EXEC-003 | View execution details | P1 | ✅ Done |
| EXEC-004 | View execution error messages | P1 | ✅ Done |
| EXEC-005 | Execution sync from provider | P0 | ✅ Done |

#### 3.8.2 Analytics Dashboard

**Description**: Execution metrics and trends

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| EXEC-006 | Total executions count | P1 | ✅ Done |
| EXEC-007 | Success rate calculation | P1 | ✅ Done |
| EXEC-008 | Average execution duration | P1 | ✅ Done |
| EXEC-009 | P50/P95 duration percentiles | P2 | ✅ Done |
| EXEC-010 | Per-workflow analytics | P1 | ✅ Done |
| EXEC-011 | Last failure tracking per workflow | P2 | ✅ Done |
| EXEC-012 | Time window filtering (7d, 30d, 90d) | P1 | ✅ Done |

### 3.9 Observability Dashboard

#### 3.9.1 System Status

**Description**: Real-time system health monitoring

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| OBS-001 | System health status (healthy/degraded/critical) | P1 | ✅ Done |
| OBS-002 | Actionable insights with severity | P1 | ✅ Done |
| OBS-003 | Failure delta percentage | P2 | ✅ Done |
| OBS-004 | Failing workflows count | P1 | ✅ Done |
| OBS-005 | Last failed deployment tracking | P1 | ✅ Done |

#### 3.9.2 KPI Metrics with Sparklines

**Description**: Key performance indicators with trend visualization

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| OBS-006 | Total executions with sparkline | P1 | ✅ Done |
| OBS-007 | Success rate with sparkline | P1 | ✅ Done |
| OBS-008 | Average duration with sparkline | P1 | ✅ Done |
| OBS-009 | P95 duration | P2 | ✅ Done |
| OBS-010 | Delta metrics (change from previous period) | P2 | ✅ Done |
| OBS-011 | Time range selection (1h, 6h, 24h, 7d, 30d) | P1 | ✅ Done |

#### 3.9.3 Error Intelligence

**Description**: Aggregated error analysis

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| OBS-012 | Error grouping by type | P1 | ✅ Done |
| OBS-013 | Error count per group | P1 | ✅ Done |
| OBS-014 | First/last seen timestamps | P1 | ✅ Done |
| OBS-015 | Affected workflow count | P1 | ✅ Done |
| OBS-016 | Sample error messages | P2 | ✅ Done |

#### 3.9.4 Environment Health

**Description**: Per-environment health with credential status

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| OBS-017 | Environment status (healthy/degraded/unreachable) | P1 | ✅ Done |
| OBS-018 | API latency tracking | P1 | ✅ Done |
| OBS-019 | Uptime percentage | P1 | ✅ Done |
| OBS-020 | Active/total workflow counts | P1 | ✅ Done |
| OBS-021 | Last deployment status | P1 | ✅ Done |
| OBS-022 | Drift state indicator | P1 | ✅ Done |
| OBS-023 | Credential health summary | P2 | ✅ Done |
| OBS-024 | Scheduled health check polling | P1 | ✅ Done |

### 3.10 Credentials Management

#### 3.10.1 Credential Viewing

**Description**: View credential metadata (not secrets)

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| CRED-001 | List credentials by environment | P0 | ✅ Done |
| CRED-002 | View credential type and usage | P1 | ✅ Done |
| CRED-003 | Identify workflows using credential | P1 | ✅ Done |
| CRED-004 | Sync credentials from provider | P0 | ✅ Done |

#### 3.10.2 Credential Health

**Description**: Monitor credential status

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| CRED-005 | Track credential health status | P1 | ✅ Done |
| CRED-006 | Cross-environment credential matrix | P2 | ✅ Done |
| CRED-007 | Missing credential detection during promotion | P1 | ✅ Done |

### 3.11 Bulk Operations

**Description**: Batch operations on multiple resources

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| BULK-001 | Bulk sync multiple environments | P1 | ✅ Done |
| BULK-002 | Bulk backup to Git | P1 | ✅ Done |
| BULK-003 | Bulk restore from snapshots | P2 | ✅ Done |
| BULK-004 | Progress tracking per operation | P1 | ✅ Done |
| BULK-005 | Partial failure handling | P1 | ✅ Done |

### 3.12 Team & Access Management

#### 3.12.1 Team Management

**Description**: Manage team members and roles

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| TEAM-001 | Invite team members by email | P0 | ✅ Done |
| TEAM-002 | Assign roles (admin/developer/viewer) | P0 | ✅ Done |
| TEAM-003 | Remove team members | P0 | ✅ Done |
| TEAM-004 | View team member list | P0 | ✅ Done |
| TEAM-005 | Team member limits per plan | P1 | ✅ Done |
| TEAM-006 | Pending invitation status | P1 | ✅ Done |

#### 3.12.2 Role-Based Access Control

**Description**: Permission system based on roles

**Role Permissions**:
| Permission | Viewer | Developer | Admin |
|------------|--------|-----------|-------|
| View workflows | ✅ | ✅ | ✅ |
| View executions | ✅ | ✅ | ✅ |
| View observability | ✅ | ✅ | ✅ |
| Upload workflows | ❌ | ✅ | ✅ |
| Execute promotions | ❌ | ✅ | ✅ |
| Configure pipelines | ❌ | ❌ | ✅ |
| Manage team | ❌ | ❌ | ✅ |
| Access billing | ❌ | ❌ | ✅ |
| View audit logs | ❌ | ❌ | ✅ |
| Configure drift policies | ❌ | ❌ | ✅ |
| Hard delete workflows | ❌ | ❌ | ✅ |

### 3.13 Billing & Subscriptions

#### 3.13.1 Provider-Based Subscriptions

**Description**: Stripe-based billing per automation provider

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| BILL-001 | View current subscriptions per provider | P0 | ✅ Done |
| BILL-002 | Subscribe to provider plans | P0 | ✅ Done |
| BILL-003 | Upgrade/downgrade plans | P0 | ✅ Done |
| BILL-004 | Update payment method | P0 | ✅ Done |
| BILL-005 | View billing history | P1 | ✅ Done |
| BILL-006 | Cancel subscription | P0 | ✅ Done |
| BILL-007 | Stripe checkout integration | P0 | ✅ Done |
| BILL-008 | Stripe webhook handling | P0 | ✅ Done |
| BILL-009 | Customer portal access | P1 | ✅ Done |
| BILL-010 | Upcoming invoice preview | P2 | ✅ Done |

#### 3.13.2 Plan Tiers (Per Provider)

| Feature | Free | Pro | Agency | Enterprise |
|---------|------|-----|--------|------------|
| **Price** | $0 | $299/mo | Custom | Custom |
| **Environments** | 2 | 10 | Unlimited | Unlimited |
| **Team Members** | 3 | 10 | Unlimited | Unlimited |
| **Workflows** | Unlimited | Unlimited | Unlimited | Unlimited |
| GitHub Backup/Restore | ❌ | ✅ | ✅ | ✅ |
| Environment Promotion | ❌ | ✅ | ✅ | ✅ |
| Scheduled Backups | ❌ | ❗ NOT IMPLEMENTED | ❗ NOT IMPLEMENTED | ❗ NOT IMPLEMENTED |
| Workflow Diff | ❌ | ✅ | ✅ | ✅ |
| Full Drift Diff | ❌ | ❌ | ✅ | ✅ |
| Drift TTL/SLA | ❌ | ❌ | ✅ | ✅ |
| Drift Policies | ❌ | ❌ | ❌ | ✅ |
| Execution Metrics | ❌ | ✅ | ✅ | ✅ |
| Alerting | ❌ | ✅ | ✅ | ✅ |
| Role-Based Access | ❌ | ✅ | ✅ | ✅ |
| Audit Logs | ❌ | 90 days | 180 days | Unlimited |
| Credential Remapping | ❌ | ❌ | ❌ | ❗ NOT IMPLEMENTED |
| SSO/SCIM | ❌ | ❌ | ❌ | ❗ NOT IMPLEMENTED |
| **Support** | Community | Email | Priority | Dedicated |

### 3.14 Entitlements & Feature Management

#### 3.14.1 Feature-Based Access Control

**Description**: Plan-based feature gating

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| ENT-001 | Feature flags per plan | P0 | ✅ Done |
| ENT-002 | Limit-based entitlements | P0 | ✅ Done |
| ENT-003 | Tenant entitlements API | P0 | ✅ Done |
| ENT-004 | Provider-scoped entitlements | P0 | ✅ Done |
| ENT-005 | Plan feature requirements | P1 | ✅ Done |

#### 3.14.2 Admin Feature Management

**Description**: Administrative control over features and plans

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| ENT-006 | Feature matrix view | P1 | ✅ Done |
| ENT-007 | Plan management | P1 | ✅ Done |
| ENT-008 | Tenant feature overrides | P2 | ✅ Done |
| ENT-009 | Override expiration | P2 | ✅ Done |
| ENT-010 | Feature config audit log | P2 | ✅ Done |
| ENT-011 | Feature access logging | P2 | ✅ Done |

### 3.15 Notifications & Alerts

#### 3.15.1 Notification Channels

**Description**: Configure notification delivery methods

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| NOTIF-001 | Slack webhook integration | P1 | ✅ Done |
| NOTIF-002 | Email notifications | P1 | ✅ Done |
| NOTIF-003 | Custom webhook integration | P2 | ✅ Done |
| NOTIF-004 | Channel enable/disable | P1 | ✅ Done |
| NOTIF-005 | Test channel connectivity | P2 | ✅ Done |

#### 3.15.2 Notification Rules

**Description**: Configure which events trigger notifications

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| NOTIF-006 | Event-based rules | P1 | ✅ Done |
| NOTIF-007 | Channel selection per event type | P1 | ✅ Done |
| NOTIF-008 | Rule enable/disable | P1 | ✅ Done |
| NOTIF-009 | Event catalog | P1 | ✅ Done |

**Event Types**:
- `deployment.started` / `deployment.completed` / `deployment.failed`
- `drift.detected` / `drift.resolved`
- `incident.created` / `incident.acknowledged` / `incident.resolved`
- `system.error`
- `backup.completed` / `backup.failed`

### 3.16 Admin Portal

#### 3.16.1 Tenant Administration

**Description**: Manage customer tenants

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| ADMIN-001 | Tenant list with search and filters | P1 | ✅ Done |
| ADMIN-002 | Tenant detail view | P1 | ✅ Done |
| ADMIN-003 | Tenant notes | P2 | ✅ Done |
| ADMIN-004 | Usage statistics per tenant | P1 | ✅ Done |
| ADMIN-005 | Provider subscriptions view | P1 | ✅ Done |
| ADMIN-006 | Tenant settings management | P2 | ✅ Done |

#### 3.16.2 System Administration

**Description**: Platform-wide administration

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| ADMIN-007 | System billing overview | P1 | ✅ Done |
| ADMIN-008 | Plan configuration | P1 | ✅ Done |
| ADMIN-009 | Global usage statistics | P1 | ✅ Done |
| ADMIN-010 | Top tenants by metric | P2 | ✅ Done |
| ADMIN-011 | Tenants at limit | P2 | ✅ Done |
| ADMIN-012 | Audit log queries | P1 | ✅ Done |
| ADMIN-013 | Provider management | P1 | ✅ Done |
| ADMIN-014 | Provider plan management | P1 | ✅ Done |
| ADMIN-015 | Environment types configuration | P2 | ✅ Done |
| ADMIN-016 | Data retention configuration | P2 | ✅ Done |

### 3.17 Platform Administration

#### 3.17.1 Platform Admin System

**Description**: Super admin capabilities for platform operators

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PLAT-001 | Platform admin designation | P1 | ✅ Done |
| PLAT-002 | Add/remove platform admins | P1 | ✅ Done |
| PLAT-003 | Platform admin dashboard | P1 | ✅ Done |
| PLAT-004 | Cross-tenant visibility | P1 | ✅ Done |

#### 3.17.2 Impersonation System

**Description**: Support capability to access customer accounts

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PLAT-005 | Start impersonation session | P1 | ✅ Done |
| PLAT-006 | End impersonation session | P1 | ✅ Done |
| PLAT-007 | Impersonation audit logging | P1 | ✅ Done |
| PLAT-008 | Write action auditing during impersonation | P1 | ✅ Done |
| PLAT-009 | Cannot impersonate other platform admins | P1 | ✅ Done |
| PLAT-010 | Impersonation session tracking | P1 | ✅ Done |

#### 3.17.3 Support Console

**Description**: Customer support interface

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| PLAT-011 | Tenant search by name/slug/ID | P1 | ✅ Done |
| PLAT-012 | User search within tenant | P1 | ✅ Done |
| PLAT-013 | Quick impersonation from search | P1 | ✅ Done |
| PLAT-014 | Tenant user roles view | P1 | ✅ Done |

### 3.18 Support System

#### 3.18.1 Support Tickets

**Description**: User support ticket management

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| SUPP-001 | Submit bug reports | P1 | ✅ Done |
| SUPP-002 | Request features | P1 | ✅ Done |
| SUPP-003 | Get help with issues | P1 | ✅ Done |
| SUPP-004 | Attach files to tickets | P2 | ✅ Done |
| SUPP-005 | Track ticket status | P1 | ✅ Done |
| SUPP-006 | Admin support console | P1 | ✅ Done |

### 3.19 Real-Time Updates

#### 3.19.1 Server-Sent Events (SSE)

**Description**: Live updates for long-running operations

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| SSE-001 | Background job progress streaming | P0 | ✅ Done |
| SSE-002 | Live log output during operations | P1 | ✅ Done |
| SSE-003 | Deployment status updates | P1 | ✅ Done |
| SSE-004 | Auto-reconnect on disconnect | P1 | ✅ Done |
| SSE-005 | Sync progress events | P1 | ✅ Done |
| SSE-006 | Backup progress events | P1 | ✅ Done |
| SSE-007 | Counts update events | P1 | ✅ Done |

### 3.20 Health Monitoring

**Description**: System health and connectivity monitoring

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| HEALTH-001 | Backend health check endpoint | P0 | ✅ Done |
| HEALTH-002 | Environment heartbeat tracking | P1 | ✅ Done |
| HEALTH-003 | Connection status indicator | P1 | ✅ Done |
| HEALTH-004 | Technical difficulties page | P1 | ✅ Done |
| HEALTH-005 | Scheduled health check polling | P1 | ✅ Done |
| HEALTH-006 | Per-environment health checks | P1 | ✅ Done |

### 3.21 Security Features

#### 3.21.1 API Key Management

**Description**: Secure API key handling

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| SEC-001 | Tenant API keys | P1 | ✅ Done |
| SEC-002 | API key rotation | P2 | ✅ Done |
| SEC-003 | API key encryption at rest | P0 | ✅ Done |

#### 3.21.2 Audit Logging

**Description**: Comprehensive action audit trail

**Requirements**:
| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| SEC-004 | All mutation actions logged | P0 | ✅ Done |
| SEC-005 | Actor identification | P0 | ✅ Done |
| SEC-006 | IP address tracking | P1 | ✅ Done |
| SEC-007 | Old/new value tracking | P1 | ✅ Done |
| SEC-008 | Provider context in audit logs | P1 | ✅ Done |
| SEC-009 | Audit log retention by plan | P1 | ✅ Done |
| SEC-010 | Audit log search and filters | P1 | ✅ Done |

---

## 4. Technical Architecture

### 4.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: React + TanStack Query + Zustand + shadcn/ui        │
│  n8n-ops-ui/ (Vite, TypeScript)                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API + SSE
┌──────────────────────────▼──────────────────────────────────────┐
│  Backend: FastAPI + Pydantic + httpx                           │
│  n8n-ops-backend/ (Python 3.11+, async)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Provider Registry → N8NProviderAdapter                 │   │
│  │                    → ❗MakeAdapter (NOT IMPLEMENTED)     │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────┬─────────────────────┬─────────────────────┬──────────────┘
       │                     │                     │
┌──────▼──────┐    ┌─────────▼─────────┐   ┌──────▼──────┐
│  Supabase   │    │  Provider APIs    │   │   GitHub    │
│  PostgreSQL │    │  (n8n only ✅)    │   │   Repos     │
└─────────────┘    │  (Make ❗)        │   └─────────────┘
       │           └───────────────────┘
┌──────▼──────┐
│   Stripe    │
│  Payments   │
└─────────────┘
```

### 4.2 Technology Stack

**Frontend**:
- React 18 with TypeScript
- TanStack Query (server state management)
- Zustand (client state management)
- shadcn/ui + Tailwind CSS
- React Flow (workflow graph visualization)
- Vite (build tool)
- Axios (HTTP client with retry logic)

**Backend**:
- FastAPI (Python 3.11+)
- Pydantic (validation and serialization)
- httpx (async HTTP client)
- PyGithub (Git integration)
- Background job service (async task processing)
- SSE (Server-Sent Events for real-time updates)

**Database**:
- Supabase (PostgreSQL)
- Row-level security
- JSONB for flexible data storage
- Alembic migrations

**External Services**:
- Stripe (payments and subscriptions)
- Supabase Auth (authentication)
- GitHub (version control and webhooks)

### 4.3 Provider Abstraction

The system uses a provider registry pattern for multi-provider support:

```python
class Provider(str, Enum):
    N8N = "n8n"
    MAKE = "make"  # ❗ NOT IMPLEMENTED - Future provider

DEFAULT_PROVIDER = Provider.N8N
```

**Provider Adapter Interface**:
- Connection testing (✅ n8n only)
- Workflow CRUD operations (✅ n8n only)
- Credential management (✅ n8n only)
- Execution retrieval (✅ n8n only)
- Tag management (✅ n8n only)
- User management (✅ n8n only)

> ⚠️ **Note**: Only `N8NProviderAdapter` is implemented. Make.com adapter does not exist.

### 4.4 Multi-Tenancy

- Complete data isolation per tenant
- All queries filtered by `tenant_id`
- Row-level security in database
- Per-tenant feature configuration via entitlements
- Provider subscriptions per tenant
- Isolated background job processing

### 4.5 Security

- JWT-based authentication via Supabase Auth
- Role-based access control (Viewer/Developer/Admin)
- API key encryption at rest
- Comprehensive audit logging
- No credential secret exposure
- Impersonation audit trail
- Platform admin separation

---

## 5. API Summary

### 5.1 API Endpoint Categories

| Category | Endpoint Count | Description |
|----------|----------------|-------------|
| Auth | 13 | Authentication, user management |
| Environments | 17 | Environment CRUD, sync, capabilities |
| Workflows | 17 | Workflow management, backup/restore |
| Canonical Workflows | 13 | Canonical system, matrix, untracked |
| Pipelines | 7 | Pipeline configuration |
| Promotions | 12 | Promotion execution, diff, compare |
| Deployments | 5 | Deployment tracking |
| Snapshots | 6 | Snapshot management |
| Drift & Incidents | 12 | Drift detection, incident lifecycle |
| Drift Policies | 6 | Policy configuration |
| Drift Approvals | 6 | Approval workflows |
| Bulk Operations | 4 | Batch processing |
| Executions | 3 | Execution data |
| Observability | 6 | Metrics and health |
| Credentials | 8 | Credential viewing |
| Tags | 2 | Tag management |
| Teams | 7 | Team management |
| Billing | 14 | Subscription management |
| Providers | 18 | Provider subscriptions |
| Notifications | 13 | Alert configuration |
| Admin Entitlements | 18 | Feature management |
| Admin Audit | 4 | Audit log queries |
| Admin Billing | 10 | System billing |
| Admin Usage | 5 | Usage analytics |
| Admin Other | 15 | Environment types, retention, etc. |
| Platform | 10 | Impersonation, console |
| Support | 6 | Support tickets |
| Health | 3 | Health checks |
| SSE | 3 | Real-time streams |
| **Total** | **~327** | |

### 5.2 Database Tables Summary

| Category | Tables | Description |
|----------|--------|-------------|
| Core | 4 | tenants, users, environments, workflow_env_map |
| Workflows | 5 | workflows, canonical_workflows, workflow_git_state, tags, etc. |
| Executions | 2 | executions, execution_analytics |
| Promotion & Deployment | 5 | pipelines, promotions, deployments, deployment_workflows |
| Drift Management | 6 | drift_incidents, drift_policies, drift_approvals, drift_check_history |
| Snapshots | 2 | snapshots, reconciliation_artifacts |
| Credentials | 2 | credentials, credential_health |
| Providers | 4 | providers, provider_plans, tenant_provider_subscriptions |
| Entitlements | 5 | features, plans, plan_features, tenant_plans, tenant_feature_overrides |
| Billing | 3 | subscription_plans, payment_history, invoices |
| Admin & Audit | 5 | audit_logs, platform_admins, impersonation_sessions |
| Support | 3 | support_tickets, support_attachments |
| Notifications | 3 | notification_channels, notification_rules, alert_events |
| Config | 3 | environment_types, background_jobs, plan_limits |
| **Total** | **~52** | |

---

## 6. Non-Functional Requirements

### 6.1 Performance

| Metric | Target |
|--------|--------|
| API Response Time (p95) | < 500ms |
| Page Load Time | < 2s |
| Sync Operation (100 workflows) | < 30s |
| Search Response Time | < 200ms |

### 6.2 Scalability

| Metric | Target |
|--------|--------|
| Concurrent Users | 1,000+ |
| Workflows per Tenant | 10,000+ |
| Environments per Tenant | 100+ |
| API Requests per Second | 1,000+ |

### 6.3 Availability

| Metric | Target |
|--------|--------|
| Uptime SLA | 99.9% |
| Planned Maintenance Window | 4 hours/month |
| Recovery Time Objective (RTO) | 1 hour |
| Recovery Point Objective (RPO) | 1 hour |

### 6.4 Security

- ❗ SOC 2 Type II compliance (NOT IMPLEMENTED - planned)
- GDPR compliance
- Data encryption at rest and in transit
- ❗ Regular security audits (NOT IMPLEMENTED - planned)
- ❗ Penetration testing annually (NOT IMPLEMENTED - planned)

---

## 7. Success Metrics

### 7.1 Product Metrics

| Metric | Target |
|--------|--------|
| Monthly Active Users (MAU) | Track growth |
| Promotions Executed | 1,000+/month |
| Drift Incidents Detected | Track trend |
| Mean Time to Resolve Drift | < 24 hours |
| Snapshot Restore Success Rate | > 99% |

### 7.2 Business Metrics

| Metric | Target |
|--------|--------|
| Free to Paid Conversion | > 5% |
| Monthly Recurring Revenue (MRR) | Track growth |
| Customer Churn Rate | < 5% |
| Net Promoter Score (NPS) | > 40 |

---

## 8. Roadmap

### Phase 1: Foundation ✅ Complete
- Environment management
- Workflow synchronization
- Basic promotion pipelines
- GitHub backup/restore
- Multi-tenancy
- Role-based access

### Phase 2: Governance ✅ Complete
- Drift detection and incidents
- Approval workflows
- Audit logging
- Snapshot and restore
- Credential management

### Phase 3: Enterprise ✅ Complete
- Drift policies and TTL/SLA
- Canonical workflow system
- Bulk operations
- Execution analytics
- Advanced admin portal
- Multi-provider architecture

### Phase 4: Platform ✅ Complete
- Provider subscriptions model
- Platform admin system
- Impersonation capabilities
- Support console
- Feature entitlements system

### Phase 5: Scale (Planned) ❗ NOT IMPLEMENTED
- ❗ Make.com provider implementation
- ❗ Secret vault integration
- ❗ SSO/SCIM
- ❗ Advanced compliance tools
- ❗ Custom integrations
- ❗ White-label options

---

## 9. Appendix

### 9.1 Glossary

| Term | Definition |
|------|------------|
| **Provider** | A workflow automation platform (n8n, Make.com) |
| **Environment** | A connected provider instance (dev, staging, production) |
| **Environment Class** | Deterministic classification (dev/staging/production) for policy enforcement |
| **Workflow** | An automation workflow from a provider |
| **Canonical Workflow** | Git-backed source of truth for a workflow |
| **Promotion** | Moving a workflow from one environment to another |
| **Pipeline** | A defined path for promotions (e.g., dev → staging → prod) |
| **Gate** | A validation step required before promotion |
| **Drift** | Differences between expected and actual workflow configuration |
| **Snapshot** | A point-in-time backup of environment state |
| **Tenant** | An isolated customer organization |
| **Platform Admin** | Super administrator with cross-tenant access |
| **Impersonation** | Support capability to access customer accounts |
| **Entitlement** | Feature or limit granted by a subscription plan |

### 9.2 Environment Variables

**Backend**:
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_KEY` - Supabase service role key
- `STRIPE_SECRET_KEY` - Stripe API key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing secret
- `GITHUB_APP_ID` - GitHub App ID (optional)

**Frontend**:
- `VITE_API_BASE_URL` - Backend API URL
- `VITE_SUPABASE_URL` - Supabase project URL
- `VITE_SUPABASE_ANON_KEY` - Supabase anonymous key

---

*Document maintained by the WorkflowOps Platform Team*

