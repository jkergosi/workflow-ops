# Deployments & Snapshots — New Functionality Spec (v1)

Pipelines + promotion flow are now the “source of truth” for how workflows move between environments.  
**Deployments** = records of promotions.  
**Snapshots** = Git-backed environment states created during sync/promotion.

This document replaces any previous Deployments/Snapshots behavior.

---

## 0. Shared Concepts (Backend + UI)

### Environment
- Existing concept: `dev`, `staging`, `prod`, etc.

### Snapshot (DB record)
- Represents **one Git commit** that stores the **full workflow state for a single environment** at a point in time.
- DB holds metadata only; actual workflow JSON is stored in GitHub.

Suggested fields:
- `id`
- `environment_id`
- `git_commit_sha`
- `type` (enum: `auto_backup`, `pre_promotion`, `post_promotion`, `manual_backup`)
- `created_at`
- `created_by_user_id`
- `related_deployment_id` (nullable)
- `metadata_json` (optional; counts, notes, etc.)

### Deployment (DB record)
- Represents **one execution of a pipeline stage** (e.g. `dev → staging`).
- May involve one or many workflows.

Suggested fields:
- `id`
- `pipeline_id`
- `source_environment_id`
- `target_environment_id`
- `status` (enum: `pending`, `running`, `success`, `failed`, `canceled`)
- `triggered_by_user_id`
- `approved_by_user_id` (nullable, for future approvals)
- `started_at`
- `finished_at`
- `pre_snapshot_id` (FK to Snapshots)
- `post_snapshot_id` (FK to Snapshots)
- `summary_json` (counts, errors, etc.)

### DeploymentWorkflow (DB record)
- Per-workflow result within a deployment.

Suggested fields:
- `id`
- `deployment_id`
- `workflow_id`
- `workflow_name_at_time`
- `change_type` (enum: `created`, `updated`, `deleted`, `skipped`, `unchanged`)
- `status` (enum: `success`, `failed`, `skipped`)
- `error_message` (nullable)

---

## 1. Deployments — UI Requirements (v1)

### 1.1 Page Purpose

- Show **history of promotions** (deployments) across environments.
- Allow user to:
  - Start a new promotion (re-using existing promotion wizard).
  - Inspect what was promoted, by whom, and whether it succeeded.
  - Navigate to related snapshots.

### 1.2 Layout

1. **Header**
   - Title: `Deployments`
   - Subtitle: `Track workflow deployments and promote across environments`.
   - Primary button: **Promote Workflows** (opens existing promotion wizard).

2. **Summary Cards (simple, using backend aggregates)**
   - Card 1: `Promotion Mode`
     - Label: `Manual`
     - Caption: `One-click promotion between environments`
   - Card 2: `Pending Approvals`
     - Count from backend (can be 0 in v1).
     - Enterprise-only behavior later; for now, just a number.
   - Card 3: `This Week`
     - Number of successful deployments in the last 7 days.

3. **Deployment History Table**

Columns (for v1):

- `Workflow(s)`
  - If 1 workflow: show its name.
  - If >1: `3 workflows` with link to details.
- `Pipeline`
  - Pipeline name (e.g., `Mainline`).
- `Stage`
  - Text: `dev → staging`, `staging → prod`, etc.
- `Status`
  - Badge: `success`, `running`, `failed`, `canceled`.
- `Triggered By`
  - User email or display name.
- `Started`
  - Timestamp.
- `Duration`
  - `(finished_at - started_at)` in seconds or `—` if running.

Row click:
- Opens a **Deployment Detail** drawer/page (can be basic in v1):

Deployment Detail view (v1 minimal):
- Top section:
  - Pipeline
  - Stage `dev → staging`
  - Status
  - Triggered by
  - Started / Finished
- Middle section:
  - Pre snapshot ID (link to Snapshots page)
  - Post snapshot ID (link to Snapshots page)
- Table of workflows:
  - Workflow name
  - Change type (`created/updated/deleted/skipped`)
  - Status (`success/failed/skipped`)
  - Error message (if any)

Filtering (optional v1+):
- Filter by Environment, Pipeline, Status, Date range.

---

## 2. Deployments — Backend Requirements (v1)

### 2.1 Creation Flow (tie into existing promotion logic)

When a promotion is triggered and runs through the pipeline:

1. **Create Deployment record**
   - Status: `pending` → then `running`.

2. **Pre-promotion snapshot**
   - Export target environment workflows.
   - Commit to GitHub.
   - Create `Snapshot` DB record (`type = pre_promotion`).
   - Store `pre_snapshot_id` on Deployment.

3. **Promotion execution**
   - For each workflow selected:
     - Perform required API operations.
     - Create `DeploymentWorkflow` row with:
       - `change_type`
       - `status`
       - `error_message` if failed.
   - When done:
     - Set Deployment `status` to `success` / `failed`.

4. **Post-promotion snapshot**
   - Export target environment again.
   - Commit to GitHub.
   - Create `Snapshot` (`type = post_promotion`).
   - Set `post_snapshot_id` on Deployment.

5. **Update summary_json**
   - Example:
     ```json
     {
       "total": 5,
       "created": 1,
       "updated": 3,
       "deleted": 1,
       "failed": 0
     }
     ```

### 2.2 API Endpoints (example shapes)

- `GET /deployments`
  - Query params: `status`, `pipeline_id`, `environment_id`, `from`, `to`, `page`, `page_size`.
  - Returns list for history table + summary cards.

- `GET /deployments/{id}`
  - Returns Deployment + DeploymentWorkflows + linked snapshot IDs.

Backend should also provide aggregate counts for:
- `this_week_success_count`
- `pending_approvals_count` (can be 0 in v1).

---

## 3. Snapshots — UI Requirements (v1)

### 3.1 Page Purpose

- Provide a **version history view** for environment states.
- Allow operators to:
  - See when backups and promotion-related snapshots were taken.
  - See which deployment a snapshot belongs to.
  - Initiate rollback (even if rollback is simple in v1).

### 3.2 Layout

1. **Header**
   - Title: `Snapshots`
   - Subtitle: `Version control and rollback for your workflows`.

   Use existing **environment selector** in the top bar (`Environment: dev`) as the active context.

2. **Snapshot History Table** (environment-scoped)

For the **currently selected environment**, show a table:

Columns:

- `Created At`
  - Timestamp.
- `Type`
  - `Auto backup`, `Pre-promotion`, `Post-promotion`, `Manual backup`.
- `Triggered By`
  - User/email.
- `Deployment`
  - If associated: show deployment ID or a label like `#123 (dev → staging)` linking to the Deployment Detail.
  - If none: show `—`.
- `Notes` (optional)
  - Short text from metadata (e.g., “Pre-promotion for dev → staging”).

Row actions (v1):

- `View Details` (drawer or separate page)
  - Show:
    - Environment
    - Type
    - Created at
    - Triggered by
    - Git commit SHA (optional for advanced users)
    - Linked Deployment (if any)
- `Restore` (optional toggle by plan/role)
  - Calls backend rollback endpoint for this environment to restore it to the snapshot’s state.
  - Requires confirmation dialog.

No need to show per-workflow diffs in v1; that can be added later.

---

## 4. Snapshots — Backend Requirements (v1)

### 4.1 Creating Snapshots

Snapshots are created at three main times:

1. **Auto backup**
   - Before promotion (already spec’d in promotion flow).
   - `type = auto_backup` (or you can use `pre_promotion` if shared).

2. **Pre-promotion**
   - Target environment snapshot just before workflows are applied.
   - `type = pre_promotion`.
   - `related_deployment_id` set.

3. **Post-promotion**
   - Target environment snapshot right after promotion completes.
   - `type = post_promotion`.
   - `related_deployment_id` set.

4. **Manual backup**
   - From any explicit “Backup now” UI (e.g., from Environments or Workflows page).
   - `type = manual_backup`.

All of these:
- Export **full workflow set** for an environment.
- Commit to GitHub.
- Store commit SHA + metadata in `snapshots` table.

### 4.2 Rollback (v1 minimal behavior)

Endpoint:

- `POST /snapshots/{id}/restore`
  - Validates environment & permissions.
  - Pulls workflows from GitHub at `git_commit_sha`.
  - Pushes them to that environment’s n8n instance (overwrite).
  - Optionally:
    - Creates a new Snapshot (`type = manual_backup`) after rollback.

Rollback should also create an **implicit Deployment** if you want full traceability, but that can be deferred.

### 4.3 API Endpoints

- `GET /snapshots`
  - Params: `environment_id`, `type`, `from`, `to`, `page`, `page_size`.
  - Returns list for the Snapshots table.

- `GET /snapshots/{id}`
  - Returns one snapshot + metadata + related deployment (if any).

- `POST /snapshots/{id}/restore`
  - Executes rollback (see above).

---

## 5. How It All Fits Together (Summary for the Team)

- **Pipelines**  
  Define *where* and *how* promotions may happen (stages, gates, policies).

- **Deployments**  
  Each time a pipeline stage is run, a Deployment is created:
  - Tracks source/target, status, user, and which workflows were changed.
  - Links **pre** and **post** environment snapshots.

- **Snapshots**  
  Every backup or promotion event creates a Snapshot:
  - Full environment state in GitHub.
  - Viewable and restorable from the Snapshots page.
  - Cross-linked to the relevant Deployment when created during a promotion.

For v1, **Deployments = “runs”**, **Snapshots = “history and rollback”**, with clear, minimal UI and straightforward backend models that match your promotion engine.
