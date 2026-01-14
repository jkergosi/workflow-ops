# Promotion End-to-End Flow with Transformations

**Task:** T004 - Document promotion end-to-end flow with transformations
**Primary File:** `app/services/promotion_service.py`
**Related Files:**
- `app/schemas/promotion.py` - Promotion data models and state machines
- `app/services/promotion_validation_service.py` - Pre-flight validation
- `app/services/adapters/n8n_adapter.py` - Credential rewrite logic
- `app/api/endpoints/promotions.py` - API orchestration
- `mvp_readiness_pack/02_promotions_deployments.md` - High-level overview

---

## Table of Contents

1. [Overview](#overview)
2. [Promotion State Machine](#promotion-state-machine)
3. [End-to-End Flow](#end-to-end-flow)
4. [Phase 1: Validation & Gate Checks](#phase-1-validation--gate-checks)
5. [Phase 2: Pre-Promotion Snapshot](#phase-2-pre-promotion-snapshot)
6. [Phase 3: Workflow Promotion (Atomic)](#phase-3-workflow-promotion-atomic)
7. [Phase 4: Post-Promotion Snapshot & Audit](#phase-4-post-promotion-snapshot--audit)
8. [Transformations](#transformations)
9. [Policy Enforcement](#policy-enforcement)
10. [Rollback Mechanism](#rollback-mechanism)
11. [Idempotency Strategy](#idempotency-strategy)
12. [Failure Modes & Edge Cases](#failure-modes--edge-cases)

---

## Overview

The promotion system implements **atomic, idempotent, auditable** workflow promotions between n8n environments (dev → staging → prod) with the following guarantees:

### Core Invariants

**File:** `app/services/promotion_service.py` (lines 10-50)

1. **SNAPSHOT-BEFORE-MUTATE (T002):**
   - Pre-promotion snapshots MUST be created before ANY target mutations
   - Enables deterministic rollback to known-good state

2. **ATOMIC ROLLBACK ON FAILURE (T003):**
   - All-or-nothing semantics
   - First failure triggers rollback of ALL successfully promoted workflows

3. **IDEMPOTENCY ENFORCEMENT (T004):**
   - Content hash comparison prevents duplicate promotions
   - Re-executing same promotion is safe

4. **CONFLICT POLICY ENFORCEMENT (T005, T006):**
   - `allowOverwritingHotfixes`: Controls overwriting target hotfixes
   - `allowForcePromotionOnConflicts`: Controls handling of conflicts
   - Policies strictly enforced during execution

5. **AUDIT TRAIL COMPLETENESS (T009):**
   - Snapshot IDs (pre/post), workflow states, failure reasons
   - Rollback outcomes, credential rewrites
   - All logged immutably

---

## Promotion State Machine

**File:** `app/schemas/promotion.py:PromotionStatus` (lines 7-16)

```
PENDING → PENDING_APPROVAL → APPROVED → RUNNING → COMPLETED
   ↓            ↓                          ↓
CANCELLED   REJECTED                   FAILED
```

### State Transitions

| From | To | Trigger | Condition |
|------|-----|---------|-----------|
| PENDING | PENDING_APPROVAL | API call | Requires approval gate enabled |
| PENDING | RUNNING | API call | No approval required |
| PENDING_APPROVAL | APPROVED | Approval action | Admin/approver approves |
| PENDING_APPROVAL | REJECTED | Approval action | Admin/approver rejects |
| APPROVED | RUNNING | Execute API call | Promotion execution starts |
| RUNNING | COMPLETED | All workflows succeed | No errors |
| RUNNING | FAILED | Any workflow fails | Triggers atomic rollback |
| PENDING | CANCELLED | Cancel API call | User cancels before execution |

**Implementation:** `app/services/promotion_service.py:PromotionService`

---

## End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. API: POST /promotions/initiate                                   │
│    - Validate pipeline stage                                        │
│    - Compare source vs target workflows                             │
│    - Run pre-flight validation                                      │
│    - Check drift policy enforcement                                 │
│    - Return promotion_id + gate_results                             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 2. API: POST /promotions/{id}/approve (if required)                │
│    - Admin reviews gate results                                     │
│    - Approves or rejects                                            │
│    - Status: PENDING_APPROVAL → APPROVED or REJECTED               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 3. API: POST /promotions/{id}/execute                              │
│    - Create pre-promotion snapshot (Phase 2)                        │
│    - Execute atomic promotion loop (Phase 3)                        │
│    - Create post-promotion snapshot (Phase 4)                       │
│    - Return execution result                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Validation & Gate Checks

**Entry Point:** `POST /promotions/initiate`
**File:** `app/api/endpoints/promotions.py` (lines 200-400)
**Service:** `app/services/promotion_validation_service.py`

### 1.1 Pipeline Gate Checks

**Checks Performed:**

#### Target Environment Health
- **Service:** `PromotionValidator.validate_target_environment_health()`
- **File:** `promotion_validation_service.py` (lines 38-200)
- **Logic:**
  ```python
  # Test connection with 5s timeout
  adapter = ProviderRegistry.get_adapter_for_environment(target_env)
  connection_healthy = await asyncio.wait_for(
      adapter.test_connection(),
      timeout=5.0
  )
  ```
- **Fail Mode:** Fail-closed (blocks promotion)
- **Error Types:**
  - `environment_not_found`: Environment missing from DB
  - `invalid_provider_config`: Base URL or API key invalid
  - `connection_failed`: Provider unreachable
  - `connection_timeout`: Timeout exceeded

#### Credential Availability
- **Service:** `PromotionValidator.validate_credentials_exist()`
- **Logic:**
  - Extract all credential references from workflow nodes
  - Check logical credential mappings exist for target environment
  - If missing and `allowPlaceholderCredentials=false` → BLOCK
  - If `allowPlaceholderCredentials=true` → Create placeholders, proceed

#### Drift Policy Enforcement
- **Service:** `drift_policy_enforcement_service.check_enforcement_with_override()`
- **File:** `app/services/drift_policy_enforcement.py`
- **Logic:**
  ```python
  # Check for blocking drift incidents
  if incident.expires_at < now:
      return EnforcementResult.BLOCKED_TTL_EXPIRED
  if incident.status == ACTIVE and policy.block_deployments_on_drift:
      return EnforcementResult.BLOCKED_ACTIVE_DRIFT
  ```
- **Fail Mode:** Fail-closed (blocks unless approval override exists)

#### Node Support Check
- Validate all node types in workflows are supported by target provider
- Check for breaking changes in node versions

#### Webhook Availability
- Verify webhook endpoints are available in target environment
- Check for URL conflicts

### 1.2 Workflow Comparison

**Service:** `promotion_service.compare_workflows()`
**File:** `promotion_service.py` (lines 753-905)

**Logic:**
1. Load workflows from GitHub for both source and target
2. Query `workflow_diff_state` table for CONFLICT status
3. Compare workflows using normalization:
   ```python
   source_normalized = normalize_workflow_for_comparison(source_wf)
   target_normalized = normalize_workflow_for_comparison(target_wf)
   source_json = json.dumps(source_normalized, sort_keys=True)
   target_json = json.dumps(target_normalized, sort_keys=True)
   ```
4. Classify change types:
   - **NEW:** Workflow exists only in source
   - **CHANGED:** Content differs, source newer
   - **STAGING_HOTFIX:** Content differs, target newer
   - **CONFLICT:** Both modified independently (from `workflow_diff_state`)
   - **UNCHANGED:** Identical content

**Fields Excluded from Comparison:**
- Metadata: `id`, `createdAt`, `updatedAt`, `versionId`, `hash`
- Runtime: `triggerCount`, `staticData`, `meta`, `active`
- UI: node `position`, `positionAbsolute`, `selected`
- Credentials: Compare by **name only** (IDs differ per env)
- Tags: `tags`, `tagIds` (different per environment)

### 1.3 Dependency Detection

**Service:** `promotion_service.detect_dependencies()`
**File:** `promotion_service.py` (lines 695-751)

**Extracts Dependencies:**
- Execute Workflow nodes: `n8n-nodes-base.executeWorkflow`
  - Looks for `parameters.workflowId` or `parameters.workflow.value`
- Sub-workflow references in node parameters

**Warning Conditions:**
- Dependency exists in source but missing in target
- Dependency differs between source and target
- Dependency not selected for promotion

**Output:** `dependency_warnings` dict mapping workflow_id → missing deps

---

## Phase 2: Pre-Promotion Snapshot

**Entry Point:** `POST /promotions/{id}/execute` (before mutations)
**Service:** `promotion_service.create_snapshot()`
**File:** `promotion_service.py` (lines 325-548)

### 2.1 Snapshot Creation Flow

```python
# 1. Export all workflows from target N8N instance
workflows = await target_adapter.get_workflows()

# 2. Write each workflow to GitHub
for workflow in workflows:
    full_workflow = await adapter.get_workflow(workflow_id)

    # For canonical workflows: use git_folder
    if git_folder:
        canonical_id = mapping.get("canonical_id")
        await github_service.write_workflow_file(
            canonical_id=canonical_id,
            workflow_data=full_workflow,
            git_folder=git_folder,
            commit_message=f"Auto backup before promotion: {reason}"
        )
    else:
        # Legacy: use environment_type
        await github_service.sync_workflow_to_github(
            workflow_id=workflow_id,
            workflow_name=full_workflow.get("name"),
            workflow_data=full_workflow,
            commit_message=f"Auto backup before promotion: {reason}",
            environment_type=env_type
        )

# 3. Get latest commit SHA from GitHub
commits = github_service.repo.get_commits(path=folder_path, sha=branch)
commit_sha = commits[0].sha

# 4. Store snapshot record in database
snapshot_data = {
    "id": snapshot_id,
    "tenant_id": tenant_id,
    "environment_id": environment_id,
    "git_commit_sha": commit_sha,  # CRITICAL for rollback
    "type": SnapshotType.PRE_PROMOTION,
    "metadata_json": {
        "reason": reason,
        "workflows_count": workflows_synced,
        "workflows": workflow_metadata  # [{workflow_id, workflow_name, active}]
    }
}
await db_service.create_snapshot(snapshot_data)

# 5. Emit snapshot.created event
await notification_service.emit_event(
    tenant_id=tenant_id,
    event_type="snapshot.created",
    environment_id=environment_id,
    metadata={...}
)
```

### 2.2 Snapshot Completeness Guarantee

**File:** `promotion_service.py` (lines 342-365)

A snapshot is **valid for rollback ONLY if:**
1. ✅ All workflows successfully exported from N8N
2. ✅ All workflows successfully committed to GitHub
3. ✅ Valid `git_commit_sha` obtained and stored
4. ✅ Snapshot record persisted in database

**Exception Handling:**
- ❌ NO swallowing of exceptions
- ❌ NO partial results returned
- ✅ Propagate all errors to caller
- ✅ Promotion MUST abort if snapshot fails

---

## Phase 3: Workflow Promotion (Atomic)

**Entry Point:** `promotion_service.execute_promotion()`
**File:** `promotion_service.py` (lines 1855-2642)

### 3.1 Execution Loop Structure

**Atomic Semantics:** (lines 2167-2180)

```python
successfully_promoted_workflow_ids = []  # Track for rollback

for selection in workflow_selections:
    if not selection.selected:
        workflows_skipped += 1
        continue

    try:
        # 1. Check conflict policies
        # 2. Load workflow from Git
        # 3. Run idempotency check
        # 4. Rewrite credentials
        # 5. Promote to target
        # 6. Update Git state & sidecar files

        successfully_promoted_workflow_ids.append(workflow_id)
        workflows_promoted += 1

    except Exception as e:
        # ON FIRST FAILURE → ATOMIC ROLLBACK
        rollback_result = await rollback_promotion(
            tenant_id=tenant_id,
            target_env_id=target_env_id,
            pre_promotion_snapshot_id=target_pre_snapshot_id,
            promoted_workflow_ids=successfully_promoted_workflow_ids,
            promotion_id=promotion_id
        )

        # Return FAILED immediately
        return PromotionExecutionResult(
            status=PromotionStatus.FAILED,
            rollback_result=rollback_result
        )
```

### 3.2 Policy Enforcement Checks

#### T005: allowOverwritingHotfixes

**File:** `promotion_service.py` (lines 2197-2212)

```python
if (selection.change_type == WorkflowChangeType.STAGING_HOTFIX and
    not policy_flags.get('allow_overwriting_hotfixes', False)):

    error_msg = (
        f"Policy violation for '{selection.workflow_name}': "
        f"Cannot overwrite target hotfix. The target environment has newer "
        f"changes that would be lost. Enable 'allow_overwriting_hotfixes' "
        f"policy flag or sync target changes to source first."
    )
    errors.append(error_msg)
    workflows_failed += 1
    continue  # Skip this workflow
```

**Detection:**
- Compare `updatedAt` timestamps
- If `target.updatedAt > source.updatedAt` → `STAGING_HOTFIX`

#### T006: allowForcePromotionOnConflicts

**File:** `promotion_service.py` (lines 2214-2252)

```python
# Check 1: Explicit CONFLICT change_type
if (selection.change_type == WorkflowChangeType.CONFLICT and
    not policy_flags.get('allow_force_promotion_on_conflicts', False)):

    error_msg = (
        f"Policy violation for '{selection.workflow_name}': "
        f"Git conflict detected. This workflow has been modified in both the source "
        f"environment and target Git independently. Promoting would overwrite target Git changes."
    )
    errors.append(error_msg)
    workflows_failed += 1
    continue

# Check 2: requires_overwrite flag (fallback)
if (selection.requires_overwrite and
    selection.change_type != WorkflowChangeType.CONFLICT and
    not policy_flags.get('allow_force_promotion_on_conflicts', False)):

    error_msg = (
        f"Policy violation for '{selection.workflow_name}': "
        f"Conflicting changes detected in target environment."
    )
    errors.append(error_msg)
    workflows_failed += 1
    continue
```

**CONFLICT Detection:**
- Query `workflow_diff_state` table
- Check if `diff_status = "conflict"` (both source env AND target Git modified)

### 3.3 Drift Policy Enforcement at Execution Time

**File:** `promotion_service.py` (lines 1997-2080)

```python
# Additional safety layer (complements pre-flight validation)
enforcement_decision = await drift_policy_enforcement_service.check_enforcement_with_override(
    tenant_id=tenant_id,
    environment_id=target_env_id,
    correlation_id=promotion_id
)

if not enforcement_decision.allowed:
    if enforcement_decision.result == EnforcementResult.BLOCKED_TTL_EXPIRED:
        error_msg = (
            f"Promotion blocked: Drift incident has expired TTL. "
            f"Please resolve the incident or extend TTL."
        )
    elif enforcement_decision.result == EnforcementResult.BLOCKED_ACTIVE_DRIFT:
        error_msg = (
            f"Promotion blocked: Active drift incident exists. "
            f"Please resolve or request deployment override approval."
        )

    return PromotionExecutionResult(
        status=PromotionStatus.FAILED,
        errors=[error_msg]
    )
```

**Fail Modes:**
- **Fail-closed:** Enforcement failures block promotion
- **Fail-open:** Internal errors (service unavailable) logged but allow promotion

### 3.4 Idempotency Check

**File:** `promotion_service.py` (lines 2260-2325)

**T004: Content Hash Comparison**

```python
from app.services.canonical_workflow_service import compute_workflow_hash

# Compute hash of source workflow (normalized)
source_workflow_hash = compute_workflow_hash(workflow_data)

# For NEW workflows: Check all target workflows
if selection.change_type == WorkflowChangeType.NEW:
    target_workflows = await target_adapter.get_workflows()
    for target_wf in target_workflows:
        target_hash = compute_workflow_hash(target_wf)
        if target_hash == source_workflow_hash:
            workflows_skipped += 1
            warnings.append(
                f"Workflow {selection.workflow_name} already exists in target "
                f"with identical content (hash: {source_workflow_hash[:12]}...)"
            )
            skip_due_to_idempotency = True
            break

# For UPDATE workflows: Check specific workflow by ID
else:
    existing_workflow = await target_adapter.get_workflow(workflow_id)
    if existing_workflow:
        target_hash = compute_workflow_hash(existing_workflow)
        if target_hash == source_workflow_hash:
            workflows_skipped += 1
            warnings.append(
                f"Workflow {selection.workflow_name} already has identical "
                f"content in target"
            )
            skip_due_to_idempotency = True
```

**Hash Algorithm:**
- Normalized workflow content → JSON string (sorted keys) → SHA256
- See: `app/services/canonical_workflow_service.compute_workflow_hash()`

---

## Transformations

### 4.1 Workflow Loading from Git

**Source of Truth:** Git repository (NOT source runtime)

**File:** `promotion_service.py` (lines 2081-2136)

```python
source_workflow_map: Dict[str, Any] = {}

# Canonical workflow system (git_folder configured)
if source_git_folder:
    canonical_workflows = await CanonicalWorkflowService.list_canonical_workflows(tenant_id)

    for canonical in canonical_workflows:
        canonical_id = canonical["canonical_id"]

        # Get Git state for source environment
        git_state = await CanonicalWorkflowService.get_canonical_workflow_git_state(
            tenant_id, source_env_id, canonical_id
        )

        # Load workflow from Git at specific commit SHA
        workflow_data = await source_github.get_file_content(
            git_state["git_path"],
            git_state.get("git_commit_sha") or source_env.get("git_branch", "main")
        )

        # Remove metadata (keep pure n8n format)
        workflow_data.pop("_comment", None)

        # Map to n8n_workflow_id for lookup
        mappings = await db_service.get_workflow_mappings(
            tenant_id=tenant_id,
            environment_id=source_env_id,
            canonical_id=canonical_id
        )
        n8n_id = mappings[0]["n8n_workflow_id"]
        source_workflow_map[n8n_id] = workflow_data

# Legacy system (environment_type)
else:
    source_workflow_map = await source_github.get_all_workflows_from_github(
        environment_type=source_env_type,
        commit_sha=source_env.get("git_branch", "main")
    )
```

### 4.2 Credential Rewriting

**Service:** `N8NProviderAdapter.rewrite_credentials_with_mappings()`
**File:** `app/services/adapters/n8n_adapter.py` (lines 163-204)

#### Credential Mapping Lookup Structure

**Preloaded:** (lines 2146-2163)

```python
# Load logical credentials
logical_creds = await db_service.list_logical_credentials(tenant_id)
logical_name_by_id = {lc.get("id"): lc.get("name") for lc in logical_creds}

# Load target environment credential mappings
target_mappings = await db_service.list_credential_mappings(
    tenant_id=tenant_id,
    environment_id=target_env_id,
    provider=target_provider
)

# Build lookup: logical_name → mapping
mapping_lookup = {}
for m in target_mappings:
    logical_name = logical_name_by_id.get(m.get("logical_credential_id"))
    if logical_name:
        mapping_lookup[logical_name] = m

# Example mapping_lookup entry:
# {
#   "httpBasicAuth:dev-api-key": {
#       "physical_name": "prod-api-key",
#       "physical_type": "httpBasicAuth",
#       "physical_credential_id": "cred_xyz_prod"
#   }
# }
```

#### Rewrite Logic

**File:** `n8n_adapter.py` (lines 163-204)

```python
def rewrite_credentials_with_mappings(
    workflow: Dict[str, Any],
    mapping_lookup: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Rewrite credential references in workflow nodes using logical mappings.

    Transformation:
    1. Extract credential reference from node: {type: "httpBasicAuth", name: "dev-api-key"}
    2. Build logical key: "httpBasicAuth:dev-api-key"
    3. Lookup mapping in mapping_lookup
    4. Rewrite to target credential: {type: "httpBasicAuth", name: "prod-api-key", id: "cred_xyz_prod"}
    """
    nodes = workflow.get("nodes", [])

    for node in nodes:
        node_credentials = node.get("credentials", {})

        for cred_type, cred_info in list(node_credentials.items()):
            # Extract credential name
            if isinstance(cred_info, dict):
                cred_name = cred_info.get("name", "Unknown")
            else:
                cred_name = str(cred_info) if cred_info else "Unknown"
                cred_info = {}

            # Build logical key
            logical_key = f"{cred_type}:{cred_name}"

            # Lookup mapping
            mapping = mapping_lookup.get(logical_key)
            if not mapping:
                continue  # No mapping found, keep original

            # Apply mapped values
            physical_name = mapping.get("physical_name") or cred_name
            physical_type = mapping.get("physical_type") or cred_type
            physical_id = mapping.get("physical_credential_id")

            # Rewrite credential reference
            cred_info["name"] = physical_name
            if physical_id:
                cred_info["id"] = physical_id

            # Handle credential type changes
            if physical_type != cred_type:
                node_credentials.pop(cred_type, None)
                node_credentials[physical_type] = cred_info
            else:
                node_credentials[cred_type] = cred_info

        node["credentials"] = node_credentials

    workflow["nodes"] = nodes
    return workflow
```

#### Audit Trail for Credential Rewrites

**File:** `promotion_service.py` (lines 2335-2383)

```python
# Track original credentials before rewrite
original_creds = {}
for node in workflow_data.get("nodes", []):
    node_id = node.get("id", "unknown")
    if "credentials" in node:
        original_creds[node_id] = node["credentials"].copy()

# Perform rewrite
workflow_data = N8NProviderAdapter.rewrite_credentials_with_mappings(
    workflow_data,
    mapping_lookup
)

# Track what changed
for node in workflow_data.get("nodes", []):
    node_id = node.get("id", "unknown")
    if node_id in original_creds:
        original = original_creds[node_id]
        current = node.get("credentials", {})

        for cred_type in set(original.keys()) | set(current.keys()):
            orig_val = original.get(cred_type)
            curr_val = current.get(cred_type)

            if orig_val != curr_val:
                all_credential_rewrites.append({
                    "workflow_id": selection.workflow_id,
                    "workflow_name": selection.workflow_name,
                    "node_id": node_id,
                    "credential_type": cred_type,
                    "logical_name": f"{cred_type}:{orig_val.get('name')}",
                    "original": orig_val,
                    "rewritten_to": curr_val
                })
```

**Audit Log Storage:**
- Passed to `_create_audit_log(credential_rewrites=all_credential_rewrites)`
- Stored in `deployments.execution_result` JSON field

### 4.3 Active/Disabled State Transformation

**File:** `promotion_service.py` (lines 2327-2333)

```python
# If placeholders were created, force disabled
if selection.workflow_id in workflows_with_placeholders:
    workflow_data["active"] = False
    warnings.append(f"Workflow {selection.workflow_name} disabled due to placeholder credentials")
else:
    workflow_data["active"] = selection.enabled_in_source
```

**Rules:**
1. **Placeholder credentials exist** → Force `active = False`
2. **Normal case** → Preserve source active state (`enabled_in_source`)

### 4.4 Workflow Write Operation

**File:** `promotion_service.py` (lines 2385-2411)

```python
workflow_id = workflow_data.get("id")
is_new_workflow = selection.change_type == WorkflowChangeType.NEW

if is_new_workflow:
    # Create new workflow in target
    logger.info(f"Creating new workflow: {selection.workflow_name}")
    await target_adapter.create_workflow(workflow_data)
else:
    # Try to update existing workflow, fall back to create if not found
    try:
        await target_adapter.update_workflow(workflow_id, workflow_data)
    except Exception as update_error:
        error_str = str(update_error).lower()
        if '404' in error_str or '400' in error_str:
            logger.info(f"Workflow {selection.workflow_name} not found in target, creating new")
            await target_adapter.create_workflow(workflow_data)
        else:
            raise

successfully_promoted_workflow_ids.append(selection.workflow_id)
```

**Graceful Degradation:**
- Attempt `update_workflow()` first for CHANGED workflows
- Fallback to `create_workflow()` if 404/400 (workflow doesn't exist)

### 4.5 Git State & Sidecar File Updates

**File:** `promotion_service.py` (lines 2413-2526)

**Purpose:** Synchronize Git metadata after successful promotion

```python
# Find canonical_id for promoted workflow
canonical_id = None
source_mappings = await db_service.get_workflow_mappings(
    tenant_id=tenant_id,
    environment_id=source_env_id
)
for mapping in source_mappings:
    if mapping.get("n8n_workflow_id") == selection.workflow_id:
        canonical_id = mapping.get("canonical_id")
        break

if canonical_id:
    # Get target n8n_workflow_id (from created/updated workflow)
    target_workflow = await target_adapter.get_workflow(workflow_id)
    target_n8n_id = target_workflow.get("id")

    # Compute content hash
    content_hash = compute_workflow_hash(workflow_data)

    # Update workflow_environment_map
    await CanonicalEnvSyncService._create_workflow_mapping(
        tenant_id=tenant_id,
        environment_id=target_env_id,
        canonical_id=canonical_id,
        n8n_workflow_id=target_n8n_id,
        content_hash=content_hash,
        status=WorkflowMappingStatus.LINKED
    )

    # Update sidecar file in Git (*.env-map.json)
    target_git_folder = target_env.get("git_folder")
    if target_git_folder:
        target_github = self._get_github_service(target_env)

        git_state = await CanonicalWorkflowService.get_canonical_workflow_git_state(
            tenant_id, target_env_id, canonical_id
        )

        sidecar_path = git_state["git_path"].replace('.json', '.env-map.json')

        # Get existing sidecar or create new
        sidecar_data = await target_github.get_file_content(sidecar_path) or {
            "canonical_workflow_id": canonical_id,
            "workflow_name": workflow_data.get("name", "Unknown"),
            "environments": {}
        }

        # Update target environment mapping
        sidecar_data["environments"][target_env_id] = {
            "n8n_workflow_id": target_n8n_id,
            "content_hash": f"sha256:{content_hash}",
            "last_seen_at": datetime.utcnow().isoformat()
        }

        # Write sidecar file to Git
        await target_github.write_sidecar_file(
            canonical_id=canonical_id,
            sidecar_data=sidecar_data,
            git_folder=target_git_folder,
            commit_message=f"Update sidecar after promotion: {workflow_data.get('name')}"
        )

        # Update canonical_workflow_git_state table
        db_service.client.table("canonical_workflow_git_state").upsert({
            "tenant_id": tenant_id,
            "environment_id": target_env_id,
            "canonical_id": canonical_id,
            "git_path": git_path,
            "git_content_hash": content_hash,
            "last_repo_sync_at": datetime.utcnow().isoformat()
        }, on_conflict="tenant_id,environment_id,canonical_id").execute()
```

**Non-Blocking:**
- Sidecar/git_state update failures are logged but **don't fail the promotion**
- Rationale: Promotion to n8n runtime succeeded; Git metadata can be repaired later

---

## Policy Enforcement

### Policy Flags

**Schema:** `app/schemas/pipeline.py:PipelineStageGates`

| Flag | Default | Purpose | Enforcement Point |
|------|---------|---------|-------------------|
| `allowOverwritingHotfixes` | `false` | Allow overwriting target workflows with newer timestamps | `execute_promotion()` lines 2197-2212 |
| `allowForcePromotionOnConflicts` | `false` | Force promotion despite Git conflicts | `execute_promotion()` lines 2214-2252 |
| `allowPlaceholderCredentials` | `false` | Allow promotion with missing credentials (create placeholders) | Pre-flight validation |
| `requireCleanDrift` | `true` | Block promotion if drift detected | Pre-flight + execution time |

### Enforcement Strictness

**T005 & T006: Fail-Closed Enforcement**

```python
# Policy check happens BEFORE workflow promotion
# If violated → Skip workflow, increment failures, continue to next

if policy_violated:
    errors.append(error_msg)
    workflows_failed += 1
    continue  # Next workflow

# NOT atomic: Individual policy violations don't trigger rollback
# Rollback only on provider errors (network, API, etc.)
```

**Design Decision:**
- Policy violations are **validation errors**, not runtime errors
- Atomic rollback reserved for **infrastructure failures**
- Allows partial success for mixed policy compliance

---

## Rollback Mechanism

**Entry Point:** `promotion_service.rollback_promotion()`
**File:** `promotion_service.py` (lines 1596-1830)

### 5.1 Rollback Trigger

**Automatic Trigger Conditions:**
1. Any workflow promotion fails (network error, API error, etc.)
2. First failure detected in execution loop
3. Immediately invoked before returning FAILED status

**Code:** (lines 2534-2611)

```python
except Exception as e:
    error_msg = f"Failed to promote {selection.workflow_name}: {str(e)}"
    errors.append(error_msg)
    workflows_failed += 1

    logger.error(f"Promotion failed. Triggering atomic rollback.")
    logger.info(f"Rolling back {len(successfully_promoted_workflow_ids)} successfully promoted workflows")

    # Trigger rollback
    rollback_result = await self.rollback_promotion(
        tenant_id=tenant_id,
        target_env_id=target_env_id,
        pre_promotion_snapshot_id=target_pre_snapshot_id,
        promoted_workflow_ids=successfully_promoted_workflow_ids,
        promotion_id=promotion_id
    )

    # Return FAILED immediately
    return PromotionExecutionResult(
        status=PromotionStatus.FAILED,
        rollback_result=rollback_result
    )
```

### 5.2 Rollback Process

**Guarantees:**
1. **Snapshot-based restore:** Loads workflows from Git commit SHA
2. **Best-effort semantics:** Attempts to restore all, logs errors but continues
3. **Audit completeness:** Returns structured `RollbackResult`

**Implementation:**

```python
async def rollback_promotion(
    tenant_id: str,
    target_env_id: str,
    pre_promotion_snapshot_id: str,
    promoted_workflow_ids: List[str],
    promotion_id: str
) -> RollbackResult:

    rollback_errors = []
    workflows_rolled_back = 0
    rollback_timestamp = datetime.utcnow()

    # 1. Load pre-promotion snapshot from database
    snapshot_record = await db_service.get_snapshot(pre_promotion_snapshot_id, tenant_id)
    if not snapshot_record:
        raise ValueError(f"Pre-promotion snapshot {pre_promotion_snapshot_id} not found")

    # 2. Extract Git commit SHA
    git_commit_sha = snapshot_record.get("git_commit_sha")
    if not git_commit_sha:
        raise ValueError(f"Snapshot has no git commit SHA. Cannot perform rollback.")

    logger.info(f"Using Git commit SHA {git_commit_sha[:8]} for rollback")

    # 3. Get target environment config
    target_env = await db_service.get_environment(target_env_id, tenant_id)
    github_service = self._get_github_service(target_env)
    target_adapter = ProviderRegistry.get_adapter_for_environment(target_env)

    # 4. Load snapshot metadata
    snapshot_metadata = snapshot_record.get("metadata_json", {})
    snapshot_workflows = snapshot_metadata.get("workflows", [])
    snapshot_workflow_map = {
        wf.get("workflow_id"): wf.get("workflow_name", "Unknown")
        for wf in snapshot_workflows
    }

    # 5. Restore each promoted workflow
    for workflow_id in promoted_workflow_ids:
        workflow_name = snapshot_workflow_map.get(workflow_id, "Unknown")

        try:
            logger.info(f"Rolling back workflow {workflow_name} (ID: {workflow_id})")

            # Load workflow content from Git at snapshot commit SHA
            git_folder = target_env.get("git_folder")

            if git_folder:
                # Canonical workflow system - find canonical_id
                mappings = await db_service.get_workflow_mappings(
                    tenant_id=tenant_id,
                    environment_id=target_env_id
                )
                mapping = next((m for m in mappings if m.get("n8n_workflow_id") == workflow_id), None)

                if mapping:
                    canonical_id = mapping.get("canonical_id")
                    git_path = f"workflows/{git_folder}/{canonical_id}.json"

                    # Load from Git at snapshot commit SHA
                    workflow_data = await github_service.get_file_content(
                        git_path,
                        git_commit_sha  # Load from pre-promotion snapshot commit
                    )
            else:
                # Legacy: Load from environment_type folder
                env_type = target_env.get("n8n_type")
                workflows_from_git = await github_service.get_all_workflows_from_github(
                    environment_type=env_type,
                    commit_sha=git_commit_sha
                )
                workflow_data = workflows_from_git.get(workflow_id)

            if not workflow_data:
                rollback_errors.append(f"Workflow {workflow_name} not found in snapshot commit")
                continue

            # Restore workflow to target N8N instance
            try:
                await self._execute_with_retry(
                    target_adapter.update_workflow,
                    workflow_id,
                    workflow_data
                )
            except Exception as update_error:
                if self._is_not_found_error(update_error):
                    # Workflow doesn't exist, create it
                    logger.info(f"Workflow {workflow_name} not found, creating during rollback")
                    await self._execute_with_retry(
                        target_adapter.create_workflow,
                        workflow_data
                    )
                else:
                    raise

            workflows_rolled_back += 1
            logger.info(f"Successfully rolled back {workflow_name}")

        except Exception as e:
            error_msg = f"Failed to rollback workflow {workflow_name}: {str(e)}"
            rollback_errors.append(error_msg)
            logger.error(error_msg)
            # Continue with remaining workflows (best-effort)

    # 6. Create audit log
    await self._create_audit_log(
        tenant_id=tenant_id,
        promotion_id=promotion_id,
        action="rollback",
        result={
            "workflows_rolled_back": workflows_rolled_back,
            "workflows_attempted": len(promoted_workflow_ids),
            "rollback_errors": rollback_errors,
            "snapshot_id": pre_promotion_snapshot_id,
            "git_commit_sha": git_commit_sha
        }
    )

    return RollbackResult(
        rollback_triggered=True,
        workflows_rolled_back=workflows_rolled_back,
        rollback_errors=rollback_errors,
        snapshot_id=pre_promotion_snapshot_id,
        rollback_method="git_restore",
        rollback_timestamp=rollback_timestamp
    )
```

### 5.3 Edge Cases Handled

**Test File:** `tests/test_promotion_atomicity.py`

| Edge Case | Behavior | Test Coverage |
|-----------|----------|---------------|
| Workflow not found (404/400) during rollback | Fallback to `create_workflow()` | `test_rollback_creates_workflow_if_not_exists` |
| Transient provider errors (timeouts, 5xx) | Retry with exponential backoff (3 attempts) | `test_rollback_retries_transient_error_and_succeeds` |
| Retry budget exhausted | Surface error, continue next workflow | `test_rollback_stops_after_bounded_retries` |
| Partial rollback failure | Return `rollback_errors` list, don't raise | `test_rollback_partial_failure` |
| Legacy environments (no `git_folder`) | Fallback to `environment_type` folder | Built into rollback logic |

### 5.4 Retry Logic

**File:** `promotion_service.py` (lines 297-323)

```python
async def _execute_with_retry(
    self,
    func,
    *args,
    attempts: int = 3,
    base_delay: float = 0.25,
    **kwargs
):
    """Execute provider call with bounded retries for transient errors."""
    for attempt in range(1, attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as err:
            is_transient = self._is_transient_provider_error(err)
            is_last_attempt = attempt == attempts

            if not is_transient or is_last_attempt:
                raise

            delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff
            logger.warning(
                f"Transient error on attempt {attempt}/{attempts}: {err}. "
                f"Retrying in {delay:.2f}s"
            )
            await asyncio.sleep(delay)
```

**Transient Error Detection:**

```python
def _is_transient_provider_error(error: Exception) -> bool:
    status_code = getattr(getattr(error, "response", None), "status_code", None)

    # Retry on: 408 (timeout), 429 (rate limit), 5xx (server errors)
    if status_code in (408, 429) or (status_code and 500 <= status_code < 600):
        return True

    # Retry on network errors
    if isinstance(error, (httpx.RequestError, asyncio.TimeoutError)):
        return True

    return False
```

---

## Idempotency Strategy

**Implementation:** T004
**File:** `promotion_service.py` (lines 2260-2325)

### 6.1 Content Hash Comparison

**Algorithm:**
1. Normalize workflow (exclude metadata, runtime fields)
2. Serialize to JSON with sorted keys
3. Compute SHA256 hash
4. Compare source hash vs target hash

**Normalization:** (lines 90-161)

```python
def normalize_workflow_for_comparison(workflow: Dict[str, Any]) -> Dict[str, Any]:
    normalized = json.loads(json.dumps(workflow))

    # Fields excluded from comparison
    exclude_fields = [
        'id', 'createdAt', 'updatedAt', 'versionId',
        'triggerCount', 'staticData', 'meta', 'hash',
        'executionOrder', 'homeProject', 'sharedWithProjects',
        '_comment', 'pinData', 'active', 'tags', 'tagIds',
        'shared', 'scopes', 'usedCredentials'
    ]

    for field in exclude_fields:
        normalized.pop(field, None)

    # Normalize settings
    if 'settings' in normalized:
        settings_exclude = [
            'executionOrder', 'saveDataErrorExecution', 'saveDataSuccessExecution',
            'callerPolicy', 'timezone', 'saveManualExecutions', 'availableInMCP'
        ]
        for field in settings_exclude:
            normalized['settings'].pop(field, None)

    # Normalize nodes
    if 'nodes' in normalized:
        for node in normalized['nodes']:
            # Remove UI fields
            ui_fields = [
                'position', 'positionAbsolute', 'selected', 'selectedNodes',
                'executionData', 'typeVersion', 'onError', 'id',
                'webhookId', 'extendsCredential', 'notesInFlow'
            ]
            for field in ui_fields:
                node.pop(field, None)

            # Normalize credentials - compare by name only
            if 'credentials' in node:
                normalized_creds = {}
                for cred_type, cred_ref in node['credentials'].items():
                    if isinstance(cred_ref, dict):
                        normalized_creds[cred_type] = {'name': cred_ref.get('name')}
                    else:
                        normalized_creds[cred_type] = cred_ref
                node['credentials'] = normalized_creds

        # Sort nodes by name for consistent order
        normalized['nodes'] = sorted(normalized['nodes'], key=lambda n: n.get('name', ''))

    return normalized
```

### 6.2 Idempotency Check Logic

**For NEW Workflows:**
- Check ALL target workflows for matching content hash
- More expensive (O(n) target workflows)
- Prevents duplicate workflow creation

**For UPDATE Workflows:**
- Check only the specific workflow by ID
- O(1) lookup
- Skip if content already matches

**Skip Behavior:**
```python
if skip_due_to_idempotency:
    workflows_skipped += 1
    warnings.append(f"Workflow already exists with identical content")
    continue  # Next workflow
```

**No Failure:** Idempotency violations are warnings, not errors

---

## Phase 4: Post-Promotion Snapshot & Audit

**Entry Point:** After successful `execute_promotion()`
**File:** `app/api/endpoints/promotions.py` (promotion execution endpoint)

### 7.1 Post-Promotion Snapshot

**Same as Pre-Promotion:** (lines 325-548)

```python
target_post_snapshot_id, post_commit_sha = await promotion_service.create_snapshot(
    tenant_id=tenant_id,
    environment_id=target_env_id,
    reason=f"Post-promotion snapshot for promotion {promotion_id}",
    metadata={
        "type": "post_promotion",
        "promotion_id": promotion_id,
        "workflows_promoted": execution_result.workflows_promoted
    }
)
```

**Purpose:** Record final state for audit/compliance

### 7.2 Audit Log Creation

**Service:** `promotion_service._create_audit_log()`
**File:** `promotion_service.py` (lines 2644-2722)

```python
async def _create_audit_log(
    tenant_id: str,
    promotion_id: str,
    action: str,  # "initiate", "approve", "reject", "execute", "rollback"
    result: Dict[str, Any],
    credential_rewrites: Optional[List[Dict[str, Any]]] = None
):
    audit_data = {
        "tenant_id": tenant_id,
        "action": action,
        "resource_type": "promotion",
        "resource_id": promotion_id,
        "result": result,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Add credential rewrite summary
    if credential_rewrites:
        audit_data["credential_rewrites"] = {
            "total_rewrites": len(credential_rewrites),
            "affected_workflows": list(set(r["workflow_id"] for r in credential_rewrites)),
            "rewrites": credential_rewrites
        }

    await db_service.create_audit_log(audit_data)
```

**Audit Log Contents:**
- **Action:** `initiate`, `approve`, `reject`, `execute`, `rollback`
- **Result:** Workflows promoted/failed/skipped, errors, warnings
- **Snapshots:** Pre/post snapshot IDs, Git commit SHAs
- **Credential Rewrites:** Full list with before/after values
- **Rollback:** If triggered, includes rollback result details

### 7.3 Notification Events

**Service:** `notification_service.emit_event()`

**Events Emitted:**
1. `snapshot.created` - When snapshot created
2. `sync.drift_detected` - If drift found during checks
3. `promotion.completed` - On successful promotion
4. `promotion.failed` - On failure (with rollback info)

---

## Failure Modes & Edge Cases

### 8.1 Pre-Promotion Snapshot Failure

**Impact:** Promotion BLOCKED (cannot proceed without valid snapshot)

**Failure Conditions:**
- N8N instance unreachable
- GitHub API unavailable
- Commit SHA not returned
- Database persistence fails

**Behavior:**
```python
# Exception propagated to caller
raise ValueError("Failed to create pre-promotion snapshot")
```

**Recovery:** Manual intervention required; fix infrastructure issues

### 8.2 Workflow Promotion Failure

**Impact:** Atomic rollback triggered

**Failure Conditions:**
- Network timeout to target N8N
- API error (4xx, 5xx)
- Invalid workflow JSON
- Credential mapping missing

**Behavior:**
```python
# First failure → immediate rollback
rollback_result = await rollback_promotion(...)
return PromotionExecutionResult(status=FAILED, rollback_result=rollback_result)
```

**Recovery:** Fix issue, retry promotion (idempotency prevents duplicates)

### 8.3 Partial Rollback Failure

**Impact:** Target environment in inconsistent state

**Example:** 3 workflows promoted, rollback fails for 1

**Behavior:**
```python
rollback_result = RollbackResult(
    workflows_rolled_back=2,
    rollback_errors=["Failed to rollback workflow X: timeout"]
)
```

**Logged:** Audit trail includes partial rollback details

**Recovery:** Manual fix required for failed workflow

### 8.4 Policy Violation

**Impact:** Workflow skipped, promotion continues

**Example:** `STAGING_HOTFIX` detected, `allowOverwritingHotfixes=false`

**Behavior:**
```python
errors.append("Policy violation: Cannot overwrite target hotfix")
workflows_failed += 1
continue  # Next workflow
```

**Result:** Partial promotion (some workflows succeed)

**Recovery:** Enable policy flag or resolve hotfix in source

### 8.5 Idempotency Collision

**Impact:** Workflow skipped, promotion continues

**Example:** Workflow with identical content already exists in target

**Behavior:**
```python
workflows_skipped += 1
warnings.append("Workflow already exists with identical content")
```

**Result:** Graceful skip, no error

### 8.6 Sidecar File Update Failure

**Impact:** Git metadata inconsistent, promotion succeeds

**Behavior:**
```python
try:
    await target_github.write_sidecar_file(...)
except Exception as e:
    logger.warning(f"Failed to update sidecar: {e}")
    # Don't fail promotion
```

**Rationale:** Workflow successfully promoted to n8n; Git can be repaired later

**Recovery:** Manual Git sync or repair job

### 8.7 Drift Policy Enforcement Internal Error

**Impact:** Promotion allowed (fail-open)

**Example:** Enforcement service database unavailable

**Behavior:**
```python
except Exception as e:
    logger.warning(f"Drift policy enforcement check failed (fail-open): {e}")
    # Continue with promotion
```

**Rationale:** Prevent enforcement service outages from blocking all promotions

**Audit:** Logged with correlation_id for investigation

---

## Summary

The promotion system implements a **4-phase atomic pipeline** with comprehensive transformations:

1. **Phase 1 - Validation:** Pre-flight checks (credentials, health, drift, policies)
2. **Phase 2 - Snapshot:** Git-backed pre-promotion snapshot for rollback
3. **Phase 3 - Promotion:** Atomic execution loop with credential rewriting, idempotency, and policy enforcement
4. **Phase 4 - Audit:** Post-snapshot and immutable audit trail

**Key Transformations:**
- **Credential Rewriting:** Logical mappings → physical credentials per environment
- **Active State:** Preserve source state, force disabled for placeholders
- **Git Metadata:** Update sidecar files and `canonical_workflow_git_state`
- **Workflow Normalization:** Exclude environment-specific fields for comparison

**Safety Guarantees:**
- **Atomicity:** First failure → rollback all succeeded workflows
- **Idempotency:** Content hash prevents duplicate promotions
- **Audit Completeness:** Every action logged with full context
- **Policy Enforcement:** Strict fail-closed checks for conflict policies

**Files Involved:**
- `promotion_service.py` (2722 lines) - Core implementation
- `promotion_validation_service.py` - Pre-flight checks
- `n8n_adapter.py` - Credential rewrite logic
- `promotions.py` (endpoints) - API orchestration
- `promotion.py` (schemas) - Data models and state machines

---

**Generated:** 2025-01-14
**Task:** T004 - Document promotion end-to-end flow with transformations
**Status:** ✅ Complete
