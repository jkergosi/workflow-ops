# 03 - Drift Detection & Incident Management

## Drift Detection Triggers

### Scheduled Detection
- **File**: `n8n-ops-backend/app/services/drift_scheduler.py`
- **Function**: `start_all_drift_schedulers()`
- **Schedule**: Configurable per environment (default: daily)
- **Scope**: All non-DEV environments
- **Logic**: Compares workflow content hashes between environments

### On-Demand Detection
- **File**: `services/drift_detection_service.py:check_drift()`
- **API**: `POST /api/v1/incidents/check-drift`
- **Trigger**: User-initiated
- **Scope**: Single environment or workflow

### Detection Algorithm
1. Fetch canonical workflow state from `workflow_env_map`
2. Fetch current workflow from n8n API
3. Normalize both (exclude metadata fields)
4. Compute content hash
5. Compare hashes: `env_content_hash != git_content_hash` → Drift detected
6. Create incident if drift found

**Code**: `drift_detection_service.py` lines 50-150 (estimated)

---

## Incident Lifecycle

### State Machine

**File**: `schemas/drift_incident.py:DriftIncidentStatus`

```
DETECTED → ACKNOWLEDGED → STABILIZED → RECONCILED → CLOSED
```

**State Definitions**:
- **DETECTED**: Drift discovered, no action taken
- **ACKNOWLEDGED**: Team aware, investigating
- **STABILIZED**: Root cause identified, plan in place
- **RECONCILED**: Changes applied (revert/promote/accept)
- **CLOSED**: Incident resolved, archived

### Transition Rules

**File**: `services/drift_incident_service.py`

| From | To | Requirements | API Endpoint |
|------|-----|--------------|--------------|
| DETECTED | ACKNOWLEDGED | User acknowledgment | `POST /incidents/{id}/acknowledge` |
| ACKNOWLEDGED | STABILIZED | Reason + optional owner | `POST /incidents/{id}/stabilize` |
| STABILIZED | RECONCILED | Resolution action taken | `POST /incidents/{id}/reconcile` |
| RECONCILED | CLOSED | Admin approval or auto-close | `POST /incidents/{id}/close` |
| Any | Any | Admin force flag | `force_transition=true` |

**Validation**: `drift_incident_service.py:validate_state_transition()`

**Test**: `tests/test_drift_incident_service.py`

**Gap**: State transition validation incomplete (unknown edge cases)

---

## Snapshot Payload Immutability

### Drift Snapshot Storage

**Table**: `drift_incidents.drift_snapshot` (JSONB column)

**Contents**:
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

**Immutability Guarantee**: Once incident created, `drift_snapshot` column never modified

**Purging**: Payload can be purged per retention policy, setting `payload_purged_at` timestamp

**File**: `services/drift_retention_service.py:purge_drift_payloads()`

**Retention Rules**:
- **Closed incidents**: Purge after `drift_policies.closed_incident_retention_days`
- **Open incidents**: Never purge (until closed)
- **Reconciliation artifacts**: Purge after `drift_policies.reconciliation_artifact_retention_days`

**Test**: `tests/test_drift_retention_service.py`

**Risk**: JSONB max size (~1GB theoretical, but practical limit ~100MB) - large workflows may hit limit

---

## Policy Enforcement (TTL/SLA)

### Drift Policy Schema

**Table**: `drift_policies`

**Key Columns**:
- `tenant_id`: Policy owner
- `environment_id`: Specific environment or NULL (tenant-wide)
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

**File**: `schemas/drift_policy.py`

### TTL Enforcement

**When**: During promotion pre-flight checks

**Logic**:
1. Query all incidents for target environment
2. For each incident, check: `now() - detected_at > ttl_for_severity`
3. If any expired and `enforce_ttl = true` → Block promotion
4. Return blocked status with incident IDs

**API**: `GET /api/v1/promotions/drift-check/{env_id}`

**File**: `api/endpoints/promotions.py:check_drift_policy_blocking()`

**Test**: Unknown

**Risk**: TTL calculation assumes UTC consistency across DB and app server

### SLA Enforcement

**Logic**: Unknown (likely similar to TTL)

**Escalation**: Auto-escalate severity or notify on SLA breach

**Test**: Unknown

**Gap**: SLA enforcement implementation unclear

---

## Approvals

### Drift Approval Workflow

**Table**: `drift_approvals`

**Key Columns**:
- `id`: Primary key
- `incident_id`: FK to drift_incidents
- `approval_type`: acknowledge, extend_ttl, close, reconcile
- `status`: pending, approved, rejected
- `requested_by`, `reviewed_by`: User IDs
- `request_reason`, `review_notes`: Text
- `ttl_extension_hours`: For extend_ttl requests
- `created_at`, `reviewed_at`: Timestamps

**Approval Types**:
- **acknowledge**: Request to acknowledge incident
- **extend_ttl**: Request additional time before TTL expiry
- **close**: Request to close incident early
- **reconcile**: Request to reconcile drift

**Workflow**:
1. User requests approval: `POST /drift-approvals`
2. Admin/approver reviews: `POST /drift-approvals/{id}/approve` or `/reject`
3. If approved, incident state updated accordingly

**File**: `api/endpoints/drift_approvals.py`

**Test**: Unknown

**Gap**: Approval workflow atomicity untested (concurrent requests?)

---

## Endpoints, Tables & Tests

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/incidents` | List incidents with filters |
| GET | `/incidents/{id}` | Get incident details |
| POST | `/incidents/check-drift` | On-demand drift check |
| POST | `/incidents/{id}/acknowledge` | Acknowledge incident |
| POST | `/incidents/{id}/stabilize` | Mark stabilized |
| POST | `/incidents/{id}/reconcile` | Reconcile drift |
| POST | `/incidents/{id}/close` | Close incident |
| POST | `/incidents/{id}/extend-ttl` | Extend TTL |
| GET | `/drift-policies` | Get policies |
| POST | `/drift-policies` | Create/update policy |
| GET | `/drift-approvals` | List approval requests |
| POST | `/drift-approvals` | Request approval |
| POST | `/drift-approvals/{id}/approve` | Approve request |
| POST | `/drift-approvals/{id}/reject` | Reject request |

### Database Tables

#### drift_incidents

**Purpose**: Track drift incidents through lifecycle

**Key Columns**:
- `id`, `tenant_id`, `environment_id`
- `status`: DriftIncidentStatus enum
- `title`, `summary`: Metadata
- `detected_at`, `acknowledged_at`, `stabilized_at`, `reconciled_at`, `closed_at`: Lifecycle timestamps
- `detected_by`, `acknowledged_by`, `stabilized_by`, `reconciled_by`, `closed_by`: User attribution
- `owner_user_id`: Assigned owner
- `reason`: Stabilization reason
- `ticket_ref`: External ticket reference
- `expires_at`: TTL expiration (calculated)
- `severity`: critical/high/medium/low
- `affected_workflows` (JSONB): List of workflows
- `drift_snapshot` (JSONB): Immutable snapshot
- `resolution_type`: promote/revert/replace/acknowledge
- `resolution_details` (JSONB): Resolution metadata
- `payload_purged_at`: When snapshot purged
- `is_deleted`: Soft delete
- `deleted_at`: Deletion timestamp

**Indexes**: Likely on `(tenant_id, environment_id, status)`, `(expires_at)`

#### drift_policies

**Purpose**: Configure drift governance per tenant/environment

**Key Columns**: See "Policy Enforcement" section above

#### drift_approvals

**Purpose**: Track approval requests for drift operations

**Key Columns**: See "Approvals" section above

#### drift_check_history

**Purpose**: Historical log of drift checks

**Key Columns**:
- `id`, `tenant_id`, `environment_id`
- `check_type`: scheduled/manual
- `drift_found` (bool)
- `workflows_checked`, `workflows_with_drift`
- `check_duration_ms`
- `checked_at`: Timestamp

**Purpose**: Audit trail + analytics

#### reconciliation_artifacts

**Purpose**: Store reconciliation action metadata

**Key Columns**:
- `id`, `incident_id`
- `artifact_type`: snapshot/diff/script
- `artifact_data` (JSONB)
- `created_at`

**Retention**: Purged per policy

---

## Tests

| Test File | Coverage |
|-----------|----------|
| `test_drift_detection_service.py` | Detection logic, hash comparison |
| `test_drift_incident_service.py` | Incident lifecycle, state transitions |
| `test_drift_retention_service.py` | Payload purging, retention |

**Gaps**: No tests for approvals, SLA enforcement, TTL blocking during promotions

---

## Risk Areas

### High Risk

1. **TTL Enforcement Timing**: Relies on accurate UTC timestamps. Clock skew between app/DB could cause false positives/negatives.

2. **Payload Size Limits**: JSONB max size unclear. Large workflows (1000+ nodes) may hit limits.

3. **State Transition Validation**: Validation incomplete. Concurrent transitions or invalid state jumps untested.

### Medium Risk

1. **Drift Detection Performance**: Checking 1000+ workflows may cause performance issues.

2. **Scheduled Detection Reliability**: Scheduler runs in-process. If process crashes, scheduled checks missed.

3. **Approval Workflow Atomicity**: Concurrent approval requests untested. Race conditions possible.

### Low Risk

1. **Payload Purging**: Purging timing vs retention policy sync (minor edge cases).

2. **Reconciliation Cleanup**: Reconciliation artifacts may accumulate if cleanup job fails.

---

## Gaps & Missing Features

### Not Implemented

1. **Auto-Severity Classification**: Severity is manually assigned. No automatic classification based on change type.

2. **SLA Auto-Escalation**: SLA enforcement policy exists, but auto-escalation logic unclear.

3. **Drift Trends Analytics**: No trend analysis or drift frequency metrics.

4. **Multi-Workflow Incident Grouping**: Each drift detected as separate incident. No grouping by root cause.

### Unclear Behavior

1. **Concurrent Incident Creation**: Can same workflow have multiple open incidents? De-duplication logic unknown.

2. **Reconciliation Idempotency**: Can reconcile action be retried safely? Idempotency untested.

3. **Approval Delegation**: No delegation or escalation chain for approvals.

---

## Drift Handling Modes

**File**: `environments.drift_handling_mode` (column)

**Modes**:
- `warn_only`: Detect and log, don't block
- `manual_override`: Block by default, allow admin override
- `require_attestation`: Block and require formal attestation before overriding

**Enforcement**: `services/drift_detection_service.py` (environment mode check)

**Test**: Unknown

**Gap**: Mode enforcement during promotions untested

---

## Recommendations

### Must Fix Before MVP Launch

1. Test TTL enforcement during promotions comprehensively
2. Document payload size limits and handling for large workflows
3. Test state transition validation edge cases
4. Implement approval workflow atomicity tests

### Should Fix Post-MVP

1. Auto-severity classification based on change type
2. Multi-workflow incident grouping
3. Drift trends analytics
4. SLA auto-escalation implementation

### Nice to Have

1. Drift pattern detection (recurring issues)
2. Approval delegation/escalation chains
3. Drift impact analysis (affected downstream workflows)
4. Reconciliation preview/dry-run

