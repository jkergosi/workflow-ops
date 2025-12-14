# Support Section – Intake-Only Specification (JSM as System of Record)

This document **replaces all previous Support UI requirements**.

It reflects the final agreed model:

- **Workflow Ops** = request creation (intake only)
- **Jira Service Management (JSM)** = request management, history, notifications, status
- **Jira Software** = engineering execution
- **No in-app request history or request detail views**

The **Issue Contract v1** is assumed to be available and must be used for all submissions.

---

## Design Principles (Non-Negotiable)

1. **No request history UI in Workflow Ops**
2. **No request detail pages in Workflow Ops**
3. **All customer history, updates, and notifications live in JSM**
4. Workflow Ops only:
   - creates requests
   - shows the returned JSM key
   - links users to the JSM portal

This keeps the product lean and avoids rebuilding a support system.

---

## Navigation

Add a top-level navigation item:

Support

---

## Pages to Implement

### 1. Support Home

**Route:** `/support`

**Purpose:** Entry point for all support actions.

**UI Elements**
- Report a bug
- Request a feature
- Get help
- Divider
- View my support requests (external link → JSM portal)

No lists. No tables. No data loading.

---

### 2. Report a Bug

**Route:** `/support/bug/new`

**Purpose:** Submit a bug report that creates a **JSM request**.

**Form Fields**

Required:
- Title
- What happened?
- What did you expect?

Optional:
- Steps to reproduce
- Severity (sev1–sev4)
- Frequency (once / intermittent / always)
- Screenshot upload
- Include diagnostics (toggle, default ON)

Diagnostics automatically include:
- app_id
- environment
- route
- app version
- git SHA
- correlation/request ID
- FullStory session URL (if available)

**Submission Behavior**
1. Build Issue Contract v1 (`intent.kind = bug`)
2. POST to `POST /api/support/requests`
3. Backend forwards to n8n
4. n8n creates JSM Bug Report
5. Backend returns `{ "jsmRequestKey": "SUP-123" }`

**Success State**
- Show confirmation
- Display JSM key
- Button: Open in support portal

---

### 3. Request a Feature

**Route:** `/support/feature/new`

**Purpose:** Submit a feature idea as a **JSM Feature Request**.

**Form Fields**
- Title
- Problem / goal
- Desired outcome
- Optional priority and acceptance criteria

---

### 4. Get Help

**Route:** `/support/help/new`

**Purpose:** Non-bug, non-feature support.

---

## Jira Service Management Widget (Optional)

- Used for quick ad-hoc support
- Placed on Support Home or floating Help button
- Widget submissions still route through n8n

---

## Backend API

### POST /api/support/requests
- Input: Issue Contract v1
- Output: `{ jsmRequestKey }`

No other support endpoints are required.

---

## Explicit Non-Goals

- No request history UI
- No request detail pages
- No in-app comments or status tracking
- No Jira UI exposure

---

## Definition of Done

- User submits request in under 60 seconds
- JSM key returned immediately
- All history/notifications handled by JSM

---

**This spec is final and should be followed exactly by Claude Code.**
