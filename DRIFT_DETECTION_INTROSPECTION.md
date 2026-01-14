# WorkflowOps Drift Detection: Complete Introspection Report

**Generated:** 2026-01-13
**Scope:** UNTRACKED vs DRIFT_DETECTED status assignment, matching logic, and scheduler behavior

---

## 1) Where Statuses Are Defined (Source of Truth)

### A. WorkflowMappingStatus (Database-Persisted, Per-Workflow Status)

**Location:** `app/schemas/canonical_workflow.py` (Lines 7-80)

**Symbol:** `WorkflowMappingStatus` (Enum)

**Definition:**
```python
class WorkflowMappingStatus(str, Enum):
    LINKED = "linked"
    IGNORED = "ignored"
    DELETED = "deleted"
    UNTRACKED = "untracked"
    MISSING = "missing"
```

**Documentation (Lines 13-26):**
> "UNTRACKED: Workflow exists in n8n but lacks a canonical mapping. Has an n8n_workflow_id but canonical_id is NULL. Requires manual linking or can be auto-linked if matching canonical workflow is found."

**Precedence Rules (Lines 33-53):**
1. DELETED - Highest precedence (soft-deleted)
2. IGNORED - User explicitly ignored
3. MISSING - Was mapped but disappeared from n8n
4. UNTRACKED - No canonical_id (NULL)
5. LINKED - Normal operational state (lowest precedence)

**Storage:** `workflow_env_map.status` column (TEXT type with CHECK constraint)

**Database Constraint:** Migration `94a957608da9_add_untracked_missing_status.py` (Lines 22-26):
```sql
op.create_check_constraint(
    'workflow_env_map_status_check',
    'workflow_env_map',
    "status IN ('linked', 'untracked', 'missing', 'ignored', 'deleted')"
)
```

---

### B. DriftStatus (Environment-Level Status)

**Location:** `app/services/drift_detection_service.py` (Lines 20-26)

**Symbol:** `DriftStatus` (Class with string constants)

**Definition:**
```python
class DriftStatus:
    """Drift status constants"""
    UNKNOWN = "UNKNOWN"
    IN_SYNC = "IN_SYNC"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    UNTRACKED = "UNTRACKED"
    ERROR = "ERROR"
```

**Documentation:** None attached (only inline comment)

**Storage:** `environments.drift_status` column (TEXT type)

**Scope:** Environment-level aggregate status (not per-workflow)

---

### C. WorkflowEnvironmentStatus (Display-Only, Computed)

**Location:** `app/api/endpoints/workflow_matrix.py` (Lines 47-67)

**Symbol:** `WorkflowEnvironmentStatus` (Enum)

**Definition:**
```python
class WorkflowEnvironmentStatus(str, Enum):
    LINKED = "linked"
    UNTRACKED = "untracked"
    DRIFT = "drift"
    OUT_OF_DATE = "out_of_date"
```

**Documentation (Lines 50-61):**
> "Display status of a canonical workflow in a specific environment. These statuses are computed for the workflow matrix UI based on: 1. The persisted mapping status (from WorkflowMappingStatus with precedence rules) 2. Content hash comparisons to detect drift/out-of-date conditions"

**Scope:** UI display only (never persisted, computed at query time)

---

## 2) Exact Rules That Set UNTRACKED vs DRIFT_DETECTED

### A. Environment-Level UNTRACKED Status Assignment

**Location:** `app/services/drift_detection_service.py` (Lines 282-296)

**Function:** `detect_drift()`

**Exact Condition (Lines 290-296):**

```python
# Check if any workflows are tracked/linked for this environment
tracked_workflows = await db_service.get_workflows_from_canonical(
    tenant_id=tenant_id,
    environment_id=environment_id,
    include_deleted=False,
    include_ignored=False
)

# If no workflows are tracked, set status to untracked
if len(tracked_workflows) == 0:
    drift_status = DriftStatus.UNTRACKED
else:
    # Determine overall status based on drift detection
    has_drift = with_drift_count > 0 or not_in_git_count > 0
    drift_status = DriftStatus.DRIFT_DETECTED if has_drift else DriftStatus.IN_SYNC
```

**CRITICAL INSIGHT:** Environment-level `UNTRACKED` means **zero workflows are tracked/linked**, not "some workflows are untracked". This is the count of workflows with `canonical_id IS NOT NULL` in `workflow_env_map`.

**Inputs:**
- `tracked_workflows`: Result of `get_workflows_from_canonical()` which queries `workflow_env_map` WHERE `canonical_id IS NOT NULL` AND `status NOT IN ('deleted', 'ignored')`
- `with_drift_count`: Count of workflows where runtime differs from Git
- `not_in_git_count`: Count of workflows in runtime but not in Git

**Context Surrounding Lines 282-296:**
```python
280:                        in_sync_count += 1
281:
282:            # Check if any workflows are tracked/linked for this environment
283:            tracked_workflows = await db_service.get_workflows_from_canonical(
284:                tenant_id=tenant_id,
285:                environment_id=environment_id,
286:                include_deleted=False,
287:                include_ignored=False
288:            )
289:
290:            # If no workflows are tracked, set status to untracked
291:            if len(tracked_workflows) == 0:
292:                drift_status = DriftStatus.UNTRACKED
293:            else:
294:                # Determine overall status based on drift detection
295:                has_drift = with_drift_count > 0 or not_in_git_count > 0
296:                drift_status = DriftStatus.DRIFT_DETECTED if has_drift else DriftStatus.IN_SYNC
297:
298:            # Sort affected workflows: drift first, then not in git
299:            affected_workflows.sort(key=lambda x: (
300:                0 if x.get("hasDrift") else (1 if x.get("notInGit") else 2),
301:                x.get("name", "").lower()
302:            ))
```

---

### B. Per-Workflow UNTRACKED Status Assignment

**Location:** `app/services/canonical_workflow_service.py` (Lines 220-222)

**Function:** `compute_workflow_mapping_status()`

**Exact Condition (Lines 220-222):**

```python
# Precedence 4: UNTRACKED if no canonical_id but exists in n8n
if not canonical_id and is_present_in_n8n:
    return WorkflowMappingStatus.UNTRACKED
```

**Inputs:**
- `canonical_id`: The canonical workflow ID (None if not linked)
- `n8n_workflow_id`: The n8n workflow ID (None if not synced)
- `is_present_in_n8n`: Boolean - whether workflow currently exists in n8n environment
- `is_deleted`: Boolean - whether the mapping/workflow is soft-deleted
- `is_ignored`: Boolean - whether the workflow is explicitly marked as ignored

**Context Surrounding Lines 220-222:**
```python
210:    # Precedence 2: IGNORED overrides operational states
211:    if is_ignored:
212:        return WorkflowMappingStatus.IGNORED
213:
214:    # Precedence 3: MISSING if workflow was mapped but disappeared from n8n
215:    # A workflow is considered "was mapped" if it has n8n_workflow_id
216:    if not is_present_in_n8n and n8n_workflow_id:
217:        return WorkflowMappingStatus.MISSING
218:
219:    # Precedence 4: UNTRACKED if no canonical_id but exists in n8n
220:    if not canonical_id and is_present_in_n8n:
221:        return WorkflowMappingStatus.UNTRACKED
222:
223:    # Precedence 5: LINKED as default operational state
224:    # This requires both canonical_id and is_present_in_n8n
225:    if canonical_id and is_present_in_n8n:
226:        return WorkflowMappingStatus.LINKED
227:
228:    # Edge case: if we get here, the mapping is in an inconsistent state
229:    # This could happen during onboarding or partial sync operations
230:    # Default to UNTRACKED as the safest fallback
```

---

### C. Creation of UNTRACKED Workflows

**Location:** `app/services/canonical_env_sync_service.py` (Lines 451-464)

**Function:** `_process_workflow_batch()`

**Exact Condition (Lines 451-464):**

```python
else:
    # Untracked - create mapping row with canonical_id=NULL
    await CanonicalEnvSyncService._create_untracked_mapping(
        tenant_id,
        environment_id,
        n8n_workflow_id,
        content_hash,
        workflow_data=workflow if is_dev else None,
        n8n_updated_at=n8n_updated_at
    )
    batch_results["synced"] += 1
    batch_results["untracked"] += 1
    # Track newly created (untracked) workflows
    batch_results["created_workflow_ids"].append(n8n_workflow_id)
```

**Triggered When:** Auto-linking by hash fails (lines 424-429):
```python
# Try to auto-link by hash
canonical_id = await CanonicalEnvSyncService._try_auto_link_by_hash(
    tenant_id,
    environment_id,
    content_hash,
    n8n_workflow_id
)

if canonical_id:
    # Auto-linked [...]
else:
    # Untracked [...]
```

**Context Surrounding Lines 451-464:**
```python
441:                        tenant_id=tenant_id,
442:                        environment_id=environment_id,
443:                        canonical_id=canonical_id,
444:                        n8n_workflow_id=n8n_workflow_id,
445:                        content_hash=content_hash,
446:                        status=WorkflowMappingStatus.LINKED,
447:                        workflow_data=workflow if is_dev else None,
448:                        n8n_updated_at=n8n_updated_at
449:                    )
450:                    batch_results["synced"] += 1
451:                    batch_results["linked"] += 1
452:                else:
453:                    # Untracked - create mapping row with canonical_id=NULL
454:                    await CanonicalEnvSyncService._create_untracked_mapping(
455:                        tenant_id,
456:                        environment_id,
457:                        n8n_workflow_id,
458:                        content_hash,
459:                        workflow_data=workflow if is_dev else None,
460:                        n8n_updated_at=n8n_updated_at
461:                    )
462:                    batch_results["synced"] += 1
463:                    batch_results["untracked"] += 1
464:                    # Track newly created (untracked) workflows
465:                    batch_results["created_workflow_ids"].append(n8n_workflow_id)
466:
467:            except Exception as e:
468:                error_msg = f"Error processing workflow {workflow.get('id', 'unknown')}: {str(e)}"
469:                logger.error(error_msg)
470:                batch_results["errors"].append(error_msg)
```

---

## 3) Truth Table: UNTRACKED vs DRIFT_DETECTED Assignment

| Canonical Exists (Git/DB) | Runtime Exists (n8n) | Content Match | Canonical Mapping | Per-Workflow Status | Env-Level Status | Notes |
|---------------------------|---------------------|---------------|-------------------|---------------------|------------------|-------|
| ✅ Yes (Git) | ✅ Yes | ✅ Match | ✅ Linked | `LINKED` | `IN_SYNC` (if all match) | Normal state |
| ✅ Yes (Git) | ✅ Yes | ❌ Differ | ✅ Linked | `LINKED` | `DRIFT_DETECTED` | Runtime has changes not in Git |
| ✅ Yes (Git) | ❌ Missing | N/A | ✅ Was Linked | `MISSING` | `DRIFT_DETECTED` | Workflow disappeared from n8n |
| ❌ No (Git) | ✅ Yes | N/A | ❌ NULL canonical_id | `UNTRACKED` | `DRIFT_DETECTED`* or `UNTRACKED`** | *if other workflows tracked, **if zero workflows tracked |
| ❌ No (Git) | ❌ No | N/A | N/A | (No row) | `IN_SYNC` (if no other drift) | Workflow doesn't exist anywhere |
| ✅ Yes (DB mapping) | ✅ Yes | N/A | ❌ Import with new ID | `UNTRACKED` (new row) | `DRIFT_DETECTED` | Promotion/import creates new runtime ID |
| ✅ Yes (Git) | ✅ Yes (renamed) | ❌ Name differs | ❌ Match fails | `UNTRACKED` (or old `MISSING`) | `DRIFT_DETECTED` | Rename breaks name-based matching |
| N/A | N/A | N/A | N/A | N/A | `UNKNOWN` | Git not configured |
| N/A | N/A | N/A | N/A | N/A | `ERROR` | Sync/detection failed |

**Key Insight:** `DRIFT_DETECTED` at environment level means "at least one workflow has drift OR is not in Git", NOT "some workflows are untracked". Environment-level `UNTRACKED` only occurs when **zero workflows are tracked/linked**.

---

## 4) Matching / Identity: How Runtime Workflows Are Paired to Canonical

### A. Matching Key Hierarchy (In Order of Precedence)

#### 1. Database Mapping (Highest Priority)

**Location:** `app/services/canonical_env_sync_service.py` (Lines 356-361)

**Key:** `(tenant_id, environment_id, n8n_workflow_id)` - Primary key lookup

**Code:**
```python
# Check if this n8n workflow is already mapped
existing_mapping = await CanonicalEnvSyncService._get_mapping_by_n8n_id(
    tenant_id,
    environment_id,
    n8n_workflow_id
)
```

**Field Source:** `n8n_workflow_id` from n8n API payload (runtime)

**Stability:** Unstable across export/import or promotion (new ID generated)

**Why Used:** Existing mappings take precedence to preserve user linking decisions

---

#### 2. Content Hash Auto-Linking (Fallback for New Workflows)

**Location:** `app/services/canonical_env_sync_service.py` (Lines 495-554)

**Key:** `env_content_hash` matched against `git_content_hash`

**Function:** `_try_auto_link_by_hash()`

**Exact Matching Logic (Lines 512-551):**
```python
# Find canonical workflows with matching Git content hash
git_state_response = (
    db_service.client.table("canonical_workflow_git_state")
    .select("canonical_id")
    .eq("tenant_id", tenant_id)
    .eq("environment_id", environment_id)
    .eq("git_content_hash", content_hash)
    .execute()
)

matching_canonical_ids = [row["canonical_id"] for row in (git_state_response.data or [])]

# Only auto-link if exactly one match
if len(matching_canonical_ids) != 1:
    return None

canonical_id = matching_canonical_ids[0]

# Check if this canonical_id is already linked to a different n8n_workflow_id in same environment
existing_mapping_response = (
    db_service.client.table("workflow_env_map")
    .select("n8n_workflow_id")
    .eq("tenant_id", tenant_id)
    .eq("environment_id", environment_id)
    .eq("canonical_id", canonical_id)
    .neq("status", "missing")
    .execute()
)

for mapping in (existing_mapping_response.data or []):
    existing_n8n_id = mapping.get("n8n_workflow_id")
    if existing_n8n_id and existing_n8n_id != n8n_workflow_id:
        # Conflict: canonical_id already linked to different n8n_workflow_id
        logger.warning(
            f"Cannot auto-link {n8n_workflow_id} to canonical {canonical_id}: "
            f"already linked to {existing_n8n_id}"
        )
        return None

return canonical_id
```

**Field Source:**
- `env_content_hash`: SHA256 of normalized workflow from n8n (runtime)
- `git_content_hash`: SHA256 of normalized workflow from Git (canonical)

**Stability:** Stable across rename but breaks on any content change

**Requirements for Auto-Link:**
- Exactly 1 canonical workflow with matching hash
- Canonical not already linked to different n8n workflow
- Hash computed using `compute_workflow_hash()` with normalization

**Context Surrounding Lines 495-554:**
```python
485:                .eq("environment_id", environment_id)
486:                .eq("n8n_workflow_id", n8n_workflow_id)
487:                .single()
488:                .execute()
489:            )
490:            return response.data if response.data else None
491:        except Exception:
492:            return None
493:
494:    @staticmethod
495:    async def _try_auto_link_by_hash(
496:        tenant_id: str,
497:        environment_id: str,
498:        content_hash: str,
499:        n8n_workflow_id: str
500:    ) -> Optional[str]:
501:        """
502:        Try to auto-link n8n workflow to canonical workflow by content hash.
503:
504:        Only links if:
505:        - Hash matches exactly
506:        - Match is unique (one canonical workflow with this hash)
507:        - canonical_id is not already linked to a different n8n_workflow_id in same environment
508:
509:        Returns canonical_id if linked, None otherwise.
510:        """
511:        try:
512:            # Find canonical workflows with matching Git content hash
513:            git_state_response = (
514:                db_service.client.table("canonical_workflow_git_state")
515:                .select("canonical_id")
516:                .eq("tenant_id", tenant_id)
517:                .eq("environment_id", environment_id)
518:                .eq("git_content_hash", content_hash)
519:                .execute()
520:            )
521:
522:            matching_canonical_ids = [row["canonical_id"] for row in (git_state_response.data or [])]
523:
524:            # Only auto-link if exactly one match
525:            if len(matching_canonical_ids) != 1:
526:                return None
527:
528:            canonical_id = matching_canonical_ids[0]
529:
530:            # Check if this canonical_id is already linked to a different n8n_workflow_id in same environment
531:            existing_mapping_response = (
532:                db_service.client.table("workflow_env_map")
533:                .select("n8n_workflow_id")
534:                .eq("tenant_id", tenant_id)
535:                .eq("environment_id", environment_id)
536:                .eq("canonical_id", canonical_id)
537:                .neq("status", "missing")
538:                .execute()
539:            )
540:
541:            for mapping in (existing_mapping_response.data or []):
542:                existing_n8n_id = mapping.get("n8n_workflow_id")
543:                if existing_n8n_id and existing_n8n_id != n8n_workflow_id:
544:                    # Conflict: canonical_id already linked to different n8n_workflow_id
545:                    logger.warning(
546:                        f"Cannot auto-link {n8n_workflow_id} to canonical {canonical_id}: "
547:                        f"already linked to {existing_n8n_id}"
548:                    )
549:                    return None
550:
551:            return canonical_id
552:        except Exception as e:
553:            logger.warning(f"Error in auto-link by hash: {str(e)}")
554:            return None
```

---

#### 3. Name-Based Matching (Drift Detection Only)

**Location:** `app/services/drift_detection_service.py` (Lines 223-241)

**Key:** Workflow `name` field

**Code:**
```python
# Create map of git workflows by name
git_by_name = {}
for wf_id, gw in git_workflows_map.items():
    name = gw.get("name", "")
    if name:
        git_by_name[name] = gw

# Compare each runtime workflow
for runtime_wf in runtime_workflows:
    wf_name = runtime_wf.get("name", "")
    wf_id = runtime_wf.get("id", "")
    active = runtime_wf.get("active", False)

    git_entry = git_by_name.get(wf_name)

    if git_entry is None:
        # Not in Git
        not_in_git_count += 1
```

**Field Source:** `name` field from n8n API and Git JSON files

**Stability:** Breaks on rename

**Context:** Used ONLY for drift detection comparison, NOT for canonical mapping

---

### B. Tables Used for Matching

#### workflow_env_map
- **Primary Key:** `(tenant_id, environment_id, n8n_workflow_id)`
- **Key Column for Linking:** `canonical_id` (NULL for UNTRACKED)
- **Purpose:** Maps runtime workflows to canonical identity

#### canonical_workflow_git_state
- **Primary Key:** `(tenant_id, environment_id, canonical_id)`
- **Key Column for Auto-Link:** `git_content_hash`
- **Purpose:** Stores Git-sourced workflow state per environment

#### canonical_workflows
- **Primary Key:** `(tenant_id, canonical_id)`
- **Purpose:** Stores canonical workflow identity (cross-environment)

---

## 5) Normalization and Ignored Fields

### A. Normalization Function

**Location:** `app/services/promotion_service.py` (Lines 90-161)

**Function:** `normalize_workflow_for_comparison()`

**Method:** Deep copy → Remove excluded fields → Sort nodes

---

### B. Workflow-Level Ignored Fields

**From diff_service.py (Lines 71-83):**
```python
IGNORED_FIELDS: Set[str] = {
    "id",
    "createdAt",
    "updatedAt",
    "versionId",
    "meta",
    "staticData",
    "triggerCount",
    "shared",
    "homeProject",
    "sharedWithProjects",
    "_comment"  # Added by our GitHub sync
}
```

**From promotion_service.py (Lines 99-111):**
```python
exclude_fields = [
    'id', 'createdAt', 'updatedAt', 'versionId',
    'triggerCount', 'staticData', 'meta', 'hash',
    'executionOrder', 'homeProject', 'sharedWithProjects',
    # GitHub/sync metadata
    '_comment', 'pinData',
    # Additional runtime fields
    'active',  # Active state may differ between environments
    # Tags have different IDs per environment
    'tags', 'tagIds',
    # Sharing/permission info differs
    'shared', 'scopes', 'usedCredentials',
]
```

**Removal:** Non-recursive (only top-level)

---

### C. Node-Level Ignored Fields

**From diff_service.py (Lines 86-90):**
```python
IGNORED_NODE_FIELDS: Set[str] = {
    "id",
    "webhookId",
    "notesInFlow"
}
```

**From promotion_service.py (Lines 133-140):**
```python
ui_fields = [
    'position', 'positionAbsolute', 'selected', 'selectedNodes',
    'executionData', 'typeVersion', 'onError', 'id',
    'webhookId', 'extendsCredential', 'notesInFlow',
]
```

**Removal:** Recursive (per-node)

---

### D. Settings-Level Ignored Fields

**From promotion_service.py (Lines 117-128):**
```python
settings_exclude = [
    'executionOrder', 'saveDataErrorExecution', 'saveDataSuccessExecution',
    'callerPolicy', 'timezone', 'saveManualExecutions',
    # n8n settings where null and false are semantically equivalent
    'availableInMCP',
]
```

---

### E. Credentials Normalization

**Location:** `app/services/promotion_service.py` (Lines 143-151)

**Code:**
```python
# Normalize credentials - only compare by name, not ID
if 'credentials' in node and isinstance(node['credentials'], dict):
    normalized_creds = {}
    for cred_type, cred_ref in node['credentials'].items():
        if isinstance(cred_ref, dict):
            # Keep only name for comparison (ID differs between envs)
            normalized_creds[cred_type] = {'name': cred_ref.get('name')}
        else:
            normalized_creds[cred_type] = cred_ref
    node['credentials'] = normalized_creds
```

**Key:** Credential IDs are stripped; only name is compared

---

### F. Comparison Method

**From canonical_workflow_service.py (Lines 101-103):**
```python
normalized = normalize_workflow_for_comparison(workflow)
json_str = json.dumps(normalized, sort_keys=True)
content_hash = hashlib.sha256(json_str.encode()).hexdigest()
```

**Method:**
1. Normalize workflow (remove ignored fields)
2. JSON stringify with `sort_keys=True` (deterministic order)
3. SHA256 hash

**Order Sensitivity:**
- Object keys: NOT sensitive (due to `sort_keys=True`)
- Array order: SENSITIVE unless explicitly sorted
- Nodes: Sorted by name (line 154: `sorted(normalized['nodes'], key=lambda n: n.get('name', ''))`)
- Connections: NOT sorted (relies on JSON key order)

---

## 6) Scheduler / Selection Logic

### A. Drift Detection Scheduler Query

**Location:** `app/services/drift_scheduler.py` (Lines 33-67)

**Function:** `_get_environments_for_drift_check()`

**Query (Lines 44-48):**
```python
response = db_service.client.table("environments").select(
    "id, tenant_id, n8n_name, git_repo_url, git_pat, n8n_type, environment_class"
).not_.is_("git_repo_url", "null").not_.is_("git_pat", "null").neq(
    "environment_class", "dev"
).execute()
```

**Filters:**
1. `git_repo_url IS NOT NULL`
2. `git_pat IS NOT NULL`
3. `environment_class != 'dev'`
4. Tenant has `drift_detection` feature enabled (lines 59-61)

**DEV Exclusion Reason (Lines 35-39):**
> "DEV environments are excluded because n8n is the source of truth for DEV, so there's no concept of 'drift' - changes in n8n ARE the canonical state."

**Context Surrounding Lines 33-67:**
```python
23:_retention_cleanup_task: Optional[asyncio.Task] = None
24:
25:# Configuration
26:DRIFT_CHECK_INTERVAL_SECONDS = 300  # 5 minutes
27:TTL_CHECK_INTERVAL_SECONDS = 60  # 1 minute
28:RETENTION_CLEANUP_INTERVAL_SECONDS = 86400  # 24 hours (daily)
29:
30:
31:async def _get_environments_for_drift_check() -> List[Dict[str, Any]]:
32:    """
33:    Get all non-DEV environments that have Git configured and belong to tenants
34:    with drift detection enabled.
35:
36:    DEV environments are excluded because n8n is the source of truth for DEV,
37:    so there's no concept of "drift" - changes in n8n ARE the canonical state.
38:    """
39:    try:
40:        # Get environments with Git configured, excluding DEV environments
41:        # DEV environments use n8n as source of truth, so drift detection doesn't apply
42:        response = db_service.client.table("environments").select(
43:            "id, tenant_id, n8n_name, git_repo_url, git_pat, n8n_type, environment_class"
44:        ).not_.is_("git_repo_url", "null").not_.is_("git_pat", "null").neq(
45:            "environment_class", "dev"
46:        ).execute()
47:
48:        environments = response.data or []
49:
50:        # Filter to environments where tenant has drift_detection feature
51:        eligible = []
52:        for env in environments:
53:            tenant_id = env.get("tenant_id")
54:            if not tenant_id:
55:                continue
56:
57:            can_use, _ = await feature_service.can_use_feature(tenant_id, "drift_detection")
58:            if can_use:
59:                eligible.append(env)
60:
61:        return eligible
62:
63:    except Exception as e:
64:        logger.error(f"Failed to get environments for drift check: {e}")
65:        return []
66:
67:
```

---

### B. Git Configuration Check

**Location:** `app/services/drift_detection_service.py` (Lines 105-123)

**Checks:**
```python
if not environment.get("git_repo_url") or not environment.get("git_pat"):
    summary = EnvironmentDriftSummary(...)
    if update_status:
        await self._update_environment_drift_status(
            tenant_id, environment_id, DriftStatus.UNKNOWN, summary
        )
    return summary
```

**Sets Status:** `UNKNOWN` if Git not configured

---

### C. Scheduler Intervals

**Location:** `app/services/drift_scheduler.py` (Lines 26-30)

```python
DRIFT_CHECK_INTERVAL_SECONDS = 300  # 5 minutes
TTL_CHECK_INTERVAL_SECONDS = 60  # 1 minute
RETENTION_CLEANUP_INTERVAL_SECONDS = 86400  # 24 hours (daily)
```

**Drift Detection:** Every 5 minutes
**TTL Check:** Every 1 minute
**Retention Cleanup:** Every 24 hours

---

### D. Ad-Hoc Drift Detection

**Location:** API endpoint exists but not shown in current files

**Inferred:** `POST /api/environments/{id}/drift/detect` (manual trigger)

---

## 7) Observed Weirdness Candidates (Code-Backed)

### #1: Promotion/Import Creates New Runtime IDs → UNTRACKED

**Code Path:** `canonical_env_sync_service.py` → `_process_workflow_batch()` → auto-link fails due to conflict

**Root Cause:**
- Promotion creates new `n8n_workflow_id` in target environment
- Old mapping points to old ID (now MISSING)
- New ID creates new mapping row
- Auto-link by hash fails because `canonical_id` already linked to old (missing) ID
- Result: New workflow marked UNTRACKED despite being same canonical workflow

**Code Evidence (Lines 541-549):**
```python
for mapping in (existing_mapping_response.data or []):
    existing_n8n_id = mapping.get("n8n_workflow_id")
    if existing_n8n_id and existing_n8n_id != n8n_workflow_id:
        # Conflict: canonical_id already linked to different n8n_workflow_id
        logger.warning(
            f"Cannot auto-link {n8n_workflow_id} to canonical {canonical_id}: "
            f"already linked to {existing_n8n_id}"
        )
        return None
```

**Exclusion Clause (Line 537):**
```python
.neq("status", "missing")
```

**BUT:** If old mapping is still "linked" (not yet marked missing), conflict still occurs!

---

### #2: Workflow Rename Breaks Drift Detection (But Not Canonical Mapping)

**Code Path:** `drift_detection_service.py` → name-based matching fails

**Root Cause:**
- Drift detection uses NAME to match runtime vs Git (lines 223-241)
- Canonical mapping uses `n8n_workflow_id` + hash (stable across rename)
- Renamed workflow appears as "not in Git" in drift report
- But canonical mapping remains LINKED

**Divergence:**
- `workflow_env_map.status` = "linked" (correct)
- `environments.drift_status` = "DRIFT_DETECTED" (false positive)
- Affected workflows show `notInGit: true` (incorrect)

---

### #3: Hash Collision Fallback Fails Without canonical_id

**Code Path:** `canonical_workflow_service.py` → `compute_workflow_hash()` → collision detected but no canonical_id

**Root Cause:**
- New workflow during sync doesn't have `canonical_id` yet (line 416)
- Hash collision detected (line 419)
- Fallback strategy requires `canonical_id` (line 119)
- Without it, returns original colliding hash (lines 141-147)
- Result: Two workflows with identical hashes, unresolvedconflict

**Code Evidence (Lines 419-421):**
```python
# Check for hash collision and track warning (before auto-link)
collision = _detect_hash_collision(workflow, content_hash, canonical_id=None)
if collision:
    batch_results["collision_warnings"].append(collision)
```

**Fallback Failure (Lines 141-147):**
```python
else:
    # No canonical_id provided - cannot apply fallback strategy
    logger.error(
        f"Hash collision detected but no canonical_id provided for fallback. "
        f"Hash: '{content_hash}'. Returning colliding hash (unresolved collision)."
    )
    # Return the colliding hash - collision remains unresolved
    return content_hash
```

---

### #4: Environment-Level UNTRACKED Misleading When Mixed State Exists

**Code Path:** `drift_detection_service.py` → lines 290-296

**Root Cause:**
- Environment has 100 workflows
- 99 are UNTRACKED (no canonical_id)
- 1 is LINKED (has canonical_id)
- `len(tracked_workflows) == 1` → Environment status = `DRIFT_DETECTED`
- User expects `UNTRACKED` because 99% are untracked

**Semantic Issue:** Status name "UNTRACKED" means "zero workflows tracked", not "most workflows untracked"

---

### #5: Short-Circuit Optimization Skips Missing→Reappeared Transitions

**Code Path:** `canonical_env_sync_service.py` → lines 369-376

**Root Cause:**
- Workflow temporarily disappears from n8n (status → MISSING)
- Workflow reappears with same `n8n_updated_at` timestamp
- Short-circuit skips processing (line 372)
- Status remains MISSING instead of transitioning to LINKED/UNTRACKED

**Code Evidence (Lines 369-376):**
```python
# Short-circuit optimization: skip if n8n_updated_at unchanged
# Only applies when workflow is not in "missing" state (reappeared workflows need full processing)
if existing_status != "missing" and existing_n8n_updated_at and n8n_updated_at:
    if _normalize_timestamp(existing_n8n_updated_at) == _normalize_timestamp(n8n_updated_at):
        # Workflow unchanged - skip processing
        batch_results["skipped"] += 1
        if existing_canonical_id:
            batch_results["linked"] += 1
        continue
```

**Protection Exists:** Line 370 checks `existing_status != "missing"` - BUT if timestamp truly unchanged, reappeared workflow won't be processed!

---

### #6: DEV vs Non-DEV Sync Asymmetry

**Code Path:** `canonical_env_sync_service.py` → lines 227-229, 405, 446, 458

**Root Cause:**
- DEV: Stores full `workflow_data` in `workflow_env_map`
- Non-DEV: Stores only `env_content_hash` (no workflow_data)
- Drift detection compares Git vs runtime using content
- If Git sync hasn't run, non-DEV has no Git state
- Auto-link by hash fails (no git_content_hash to compare)
- Result: All non-DEV workflows UNTRACKED until first Git sync

**Code Evidence (Lines 227-229):**
```python
# Determine environment class for sync behavior
env_class = environment.get("environment_class", "dev").lower()
is_dev = env_class == "dev"
```

**Conditional Storage (Line 405):**
```python
workflow_data=workflow if is_dev else None,  # Only store workflow_data in DEV
```

---

## 8) Minimal Reproduction Guide (Repo-Only)

### Scenario: Reproduce Unexpected UNTRACKED After Promotion

#### Step 1: Check Database State

**Inspect workflow_env_map:**
```sql
SELECT
  canonical_id,
  n8n_workflow_id,
  status,
  env_content_hash,
  last_env_sync_at,
  n8n_updated_at
FROM workflow_env_map
WHERE tenant_id = '<your-tenant-id>'
  AND environment_id = '<target-env-id>'
ORDER BY last_env_sync_at DESC;
```

**Look for:**
- Multiple rows with same `canonical_id` but different `n8n_workflow_id`
- Old row with status="missing", new row with status="untracked"
- Same `env_content_hash` on both rows

---

#### Step 2: Check Git State

**Inspect canonical_workflow_git_state:**
```sql
SELECT
  canonical_id,
  git_content_hash,
  last_repo_sync_at
FROM canonical_workflow_git_state
WHERE tenant_id = '<your-tenant-id>'
  AND environment_id = '<target-env-id>'
  AND canonical_id = '<the-untracked-workflow-canonical-id>';
```

**Look for:**
- `git_content_hash` matching the `env_content_hash` from step 1
- Recent `last_repo_sync_at` timestamp

---

#### Step 3: Check Environment Drift Status

**Inspect environments:**
```sql
SELECT
  id,
  n8n_name,
  drift_status,
  last_drift_detected_at,
  environment_class,
  git_repo_url IS NOT NULL as git_configured
FROM environments
WHERE tenant_id = '<your-tenant-id>';
```

**Look for:**
- `drift_status` = "UNTRACKED" (zero workflows tracked)
- `drift_status` = "DRIFT_DETECTED" (some workflows tracked, some have drift)

---

#### Step 4: Trigger Manual Sync (API Call)

**Endpoint:** `POST /api/canonical-workflows/environments/<env-id>/sync`

**Observe:**
- Check logs for "Cannot auto-link ... already linked to ..." warnings
- Watch for hash collision warnings
- Check `created_workflow_ids` in response (newly created UNTRACKED workflows)

---

#### Step 5: Enable Debug Logging

**Set environment variables:**
```bash
LOG_LEVEL=DEBUG
```

**Watch for log patterns:**
- `"Hash collision detected!"`
- `"Cannot auto-link ... already linked to ..."`
- `"Inconsistent workflow mapping state"`
- `"Workflow unchanged - skip processing"` (short-circuit)

**Logger names:**
- `app.services.canonical_env_sync_service`
- `app.services.canonical_workflow_service`
- `app.services.drift_detection_service`

---

#### Step 6: Reproduce via Promotion

**Preconditions:**
1. Workflow exists in DEV with canonical_id="abc123"
2. Workflow previously promoted to PROD (n8n_workflow_id="10")
3. PROD mapping: `canonical_id="abc123", n8n_workflow_id="10", status="linked"`

**Steps:**
1. Delete workflow in PROD n8n (id="10")
2. Run environment sync → status changes to "missing"
3. Promote workflow from DEV again
4. n8n creates new workflow with id="20" (new ID!)
5. Run environment sync
6. Observe: Auto-link by hash fails (canonical_id already linked to id="10")
7. Result: New row created with `canonical_id=NULL, n8n_workflow_id="20", status="untracked"`

**Expected DB State:**
```sql
-- Old mapping (should be cleaned up)
canonical_id='abc123', n8n_workflow_id='10', status='missing'

-- New mapping (incorrectly untracked)
canonical_id=NULL, n8n_workflow_id='20', status='untracked'
```

---

#### Step 7: Inspect Hash Collision Registry

**Not directly accessible (in-memory)**, but logged warnings indicate collisions.

**Search logs for:**
```
Hash collision detected! Hash '<hash>' maps to different payloads
```

**Trigger scenario:**
- Two workflows with identical content (after normalization)
- Both synced to same environment
- First one hashes successfully
- Second one detects collision

---

## 9) Summary of Key Findings

### Critical Distinction: Two Meanings of "UNTRACKED"

1. **Per-Workflow Status** (`workflow_env_map.status = 'untracked'`):
   - Workflow exists in n8n
   - No canonical_id mapping (NULL)
   - Requires manual linking or auto-link

2. **Environment-Level Status** (`environments.drift_status = 'UNTRACKED'`):
   - **Zero workflows are tracked/linked** in this environment
   - NOT "some workflows are untracked"
   - Misleading name when environment has mixed state

---

### DRIFT_DETECTED vs UNTRACKED Decision Tree

```
Is Git configured?
├─ No → UNKNOWN
└─ Yes
   └─ Are there tracked workflows (canonical_id NOT NULL)?
      ├─ No (count == 0) → UNTRACKED
      └─ Yes (count > 0)
         └─ Do any tracked workflows have drift?
            ├─ Yes → DRIFT_DETECTED
            └─ No
               └─ Are there workflows not in Git?
                  ├─ Yes → DRIFT_DETECTED
                  └─ No → IN_SYNC
```

---

### Most Likely Root Causes for "Weird UNTRACKED Behavior"

1. **Promotion creates new runtime ID** → auto-link conflict (#1)
2. **Workflow renamed** → drift detection false positive (#2)
3. **Git sync hasn't run yet** → no git_content_hash to compare (#6)
4. **Hash collision without canonical_id** → fallback fails (#3)
5. **Missing→Reappeared with unchanged timestamp** → short-circuit skips transition (#5)

---

## 10) Files Referenced

| File | Purpose | Lines Analyzed |
|------|---------|----------------|
| `app/services/drift_detection_service.py` | Environment-level drift status assignment | 1-397 |
| `app/services/canonical_workflow_service.py` | Per-workflow status computation, hash logic | 1-425 |
| `app/services/canonical_env_sync_service.py` | Environment sync, auto-linking, UNTRACKED creation | 1-787 |
| `app/services/drift_scheduler.py` | Scheduler selection logic, DEV exclusion | 1-597 |
| `app/services/diff_service.py` | Workflow comparison, normalization, ignored fields | 1-611 |
| `app/schemas/canonical_workflow.py` | Status enum definitions, precedence rules | 1-356 |
| `app/api/endpoints/workflow_matrix.py` | Display status computation, UI logic | 1-438 |
| `app/services/promotion_service.py` | Normalization function (alternate version) | 1-200 |

---

**End of Report**
