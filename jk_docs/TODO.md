## TODOs

### Deployments Page
- ✅ **Rerun deployment (Azure DevOps-style)** — IMPLEMENTED
  - Add a "Rerun" action for past deployments (list + detail).
  - Rerun creates a **new deployment record** using the **same pipeline/stage, source/target, and workflow selections** as the original.
  - **Re-run all gates** on rerun (drift, credential preflight, approvals) and create **fresh pre/post snapshots** as applicable.
  - Only allow rerun for terminal states (failed/canceled; optionally success as "re-deploy").
  - Show a confirmation modal summarizing source/target, workflow count, and gates that will run.
  
### Pipelines (UI / IA)
- ✅ **Consolidate Pipelines page into Deployments page** — IMPLEMENTED
  - Move Pipelines into Deployments as a **Pipelines** tab.
  - Preserve deep links/redirects so `/pipelines` still works (redirect to `deployments?tab=pipelines` or keep route and link back).
- ❗ **Lazy-loading** — NOT IMPLEMENTED
  - Don't fetch pipeline data until the Pipelines tab is opened.
  - Ensure tab switch does not block Deployments load.
  - *Note: Currently pipelines are always fetched because Deployments tab needs pipeline names for display.*

### Executions Page
- ✅ **Fix incorrect header** — IMPLEMENTED
  - Fix "Executions in 2826513c-f995-4c05-8a7d-25180759f222" to show the environment name/type (not a raw UUID).
  - *Fixed: Uses `currentEnvironment?.name || currentEnvironment?.type` in header.*
- ❗ **Fix sync showing zero** — BUG/REGRESSION TO INVESTIGATE
  - Dev has executions but UI shows none.
  - Sync reports: "Synced 0 executions from N8N" but it previously worked.
  - Identify regression in backend sync (API path/permissions/date filtering/pagination) and restore correct import.

### Observability Page
- ✅ **Make fully functional using existing data** — IMPLEMENTED
  - Ensure all charts/cards load from real backend data (no placeholders).
  - Validate data coverage: deployments, executions, drift, credential health, etc. (whatever is already stored).
  - *Implemented: Uses apiClient to fetch real observability overview data with KPIs, sparklines, and environment health.*

### Alerts Page
- ✅ **Notification channel form** — IMPLEMENTED
  - In "Add notification channel", do **not** prefill a default value in **username**.
  - *Fixed: defaultSlackConfig.username is empty string ''.*

### Credentials Page
- ❗ **Fix credentials sync showing zero** — BUG/REGRESSION TO INVESTIGATE
  - Dev has credentials but UI shows none.
  - Sync reports: "Synced 0 credentials from N8N".
  - Identify regression and restore correct credential sync + display.

### N8N Users Page
- ❗ **Fix users sync showing zero** — BUG/REGRESSION TO INVESTIGATE
  - Dev has users but UI shows none.
  - Sync reports: "Synced 0 users from N8N".
  - Identify regression and restore correct users sync + display.

### Audit Logs Page
- ✅ **Make fully functional** — IMPLEMENTED
  - Ensure audit logs are written automatically for relevant site activity.
  - Ensure audit log list loads from real data with filters/sorting.
  - *Implemented: Uses apiClient.getAuditLogs with pagination, filters (action_type, provider, search).*
- ✅ **Audit log detail view** — IMPLEMENTED
  - Add a scalable detail viewer (recommended: side panel/drawer; alternative: detail sub-page).
  - Show: actor, timestamp, action type, target entity, before/after payload (where available), metadata, request context.
  - Ensure it performs well for large payloads (truncate + "view more" / expandable sections).
  - *Implemented: Sheet (side panel) component with full detail display.*

---

## ❗ Snapshot Mutability Policy (Implementation TODO) — NOT IMPLEMENTED

*The entire Snapshot Mutability Policy feature has not been implemented. All items below are pending.*

- ❗ **Add per-environment snapshot policy setting**
  - Store policy: `immutable | hide_only | mutable`.
  - Default new environments to `immutable`.
- ❗ **Add snapshot delete/hide behavior**
  - `immutable`: no delete/hide.
  - `hide_only`: allow soft delete (hide) only.
  - `mutable`: allow soft delete; allow hard delete only if not referenced by deployments.
- ❗ **Enforce deployment reference safeguards**
  - Block hard delete if snapshot is referenced by any deployment.
- ❗ **Add audit log records**
  - Log policy changes and snapshot hide/delete actions.
- ❗ **UI updates**
  - Show actions based on policy.
  - Provide "Show hidden" filter (admin-only if desired).
  - Add clear error messaging for forbidden actions.


---

# Product / Engineering TODOs

## ❗ Snapshot Mutability Policy (Per-Environment) — NOT IMPLEMENTED

### Overview
Snapshots are **environment-scoped system-of-record entries** used for auditability, rollback/restore, and operational backups. Since different environments may require different governance rules, **snapshot mutability is controlled by a tenant setting per environment**.

This policy controls **whether users can delete or hide snapshot records inside n8n Ops**. It does **not** change Git history.

### Key Principles
- Snapshots reference Git commits (`git_commit_sha`) and are best treated as records pointing to immutable history.
- Deleting a snapshot in n8n Ops affects the **snapshot record**, not the underlying Git commit or workflow files.

### Policies (Choose One Per Environment)

#### 1) Immutable (Audit Mode) — Recommended Default
- **Allowed**: View, list, restore, compare, link to deployments.
- **Not allowed**: Delete, hide, edit metadata.
- **Rationale**: Preserves audit trail integrity.

#### 2) Hide-Only (Ops Mode)
- **Allowed**: View, list, restore, compare.
- **Allowed (cleanup)**: "Delete" performs a **soft delete (hide)**.
- **Not allowed**: Hard delete of snapshot records.
- **Behavior**:
  - Hidden snapshots are excluded from default lists.
  - Optionally provide an admin-only "Show hidden" filter.
- **Rationale**: Keeps the UI clean while preserving history.

#### 3) Mutable (Cleanup Mode)
- **Allowed**: View, list, restore, compare.
- **Allowed (cleanup)**:
  - **Soft delete (hide)** is always allowed.
  - **Hard delete** is allowed only when safe (see safeguards).
- **Rationale**: Enables permanent removal of snapshot records when they are not needed.

### Safeguards (Apply to All Policies)

#### Deployment References
Snapshots may be referenced by deployments (e.g., `pre_snapshot_id` / `post_snapshot_id`).
- If a snapshot is **referenced by any deployment**, it is **protected**:
  - **Hard delete must be blocked**.
  - At most, allow **Hide** (soft delete), depending on policy.

#### Git History is Never Modified
Snapshot deletion/hiding must **not** attempt to delete or rewrite:
- Git commits
- Workflow JSON files in the repo
- Git tags/branches

#### Audit Logging
These actions must generate an audit log entry:
- Changing the snapshot policy for an environment
- Hiding a snapshot
- Hard-deleting a snapshot record (if permitted)

### UI/UX Guidance (High Level)
- **Immutable**: no delete/hide actions.
- **Hide-only**: show **Hide** (or "Delete (hide)").
- **Mutable**: show **Hide** always; show **Delete permanently** only when not referenced by deployments.
- Clear errors:
  - "Snapshots are immutable in this environment."
  - "Snapshot is referenced by a deployment and cannot be permanently deleted."

### Suggested Default
- New environments default to **Immutable (Audit Mode)** unless explicitly configured otherwise.


