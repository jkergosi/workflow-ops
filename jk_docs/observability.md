# WorkflowOps Observability — Revised Wireframe (v1)

This document defines a **production-ready observability page wireframe** for WorkflowOps, optimized for operator decision-making, fault diagnosis, and change-failure correlation.  
Scope: **layout, structure, and intent** (not visual styling).

---

## 0. Global Controls (Sticky Header)

```
[ Environment ▼ ] [ Time Range ▼ (24h | 7d | 30d | Custom) ]    [ Refresh ⟳ ]
Active filters: dev · last 30 days
```

**Rules**
- Applies to the *entire page*
- Always visible (sticky)
- Filter state explicitly displayed
- Filter state propagates to all drill-downs

---

## 1. System Status (Immediate Health Verdict)

**Primary question answered:** *Is anything broken right now?*

```
STATUS: ⚠ Degraded
• Failures ↑ 18% vs previous period
• 2 workflows failing repeatedly
• Last failed deployment: dev → staging (2h ago)
```

**Purpose**
- Single-glance operational verdict
- Human-readable synthesis of metrics + events
- Click → scoped deep dive (auto-filtered)

---

## 2. Key Health KPIs (With Trends)

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Executions   │ │ Success Rate │ │ Duration     │ │ Failures     │
│ 64           │ │ 73.4% ↓ 6.1% │ │ p50 95ms     │ │ 17 ↑ 5       │
│ ▁▃▅▂▆        │ │ ▁▂▃▁▂        │ │ p95 122ms    │ │ ▁▂▆▅▇        │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

**Rules**
- Sparkline required for every KPI
- Delta vs previous period required
- Threshold-based coloring (healthy / warning / critical)
- Click → scoped breakdown
- Duration defaults to p50 with p95 toggle

---

## 3. Error Intelligence (Core Diagnostic Section)

**Primary question answered:** *Why are things failing?*

```
Errors (last 30 days)

| Error Type        | Count | First Seen | Last Seen | Workflows |
|------------------|-------|------------|-----------|-----------|
| Credential Error | 9     | Dec 10     | 2h ago    | 2         |
| Timeout          | 5     | Dec 12     | 1d ago    | 1         |
| HTTP 500         | 3     | Dec 14     | 3d ago    | 1         |
```

**Rules**
- Errors grouped by root cause
- First/last seen timestamps mandatory
- Click error → affected workflows + executions
- This section replaces guesswork with diagnosis

---

## 4. Workflow Risk Table (Operator-Optimized)

**Primary question answered:** *Which workflows should I look at first?*

```
Workflows (sorted by risk)

| Workflow Name       | Runs | Fail % | Last Failure | Error Type        |
|--------------------|------|--------|--------------|-------------------|
| Invoice Sync       | 62   | 27.4%  | 2h ago       | Credential Error  |
| CRM Webhook Ingest | 2    | 0.0%   | —            | —                 |
```

**Rules**
- Default sort = risk (failure rate × execution volume)
- Workflow name displayed; ID available on hover
- Row click → workflow execution timeline
- “Last Failure” column is mandatory

---

## 5. Environment Health (Semantic, Not Cosmetic)

**Primary question answered:** *Is the environment actually healthy?*

```
Environment: dev     Status: ⚠ Degraded

• API Reachability: ✅
• Uptime: 100%
• Credential Health: ❌ 2 invalid
• Drift vs Source: ⚠ 3 workflows
• Last Snapshot: Dec 15, 2025
• Last Deployment: ❌ failed (dev → staging)
```

**Rules**
- Health is multi-dimensional (not uptime-only)
- Each line item is clickable
- Credential health and drift are first-class signals

---

## 6. Change Activity & Failure Correlation

### 6a. Promotions Summary

```
Promotions (last 7 days)

• Total: 12
• Successful: 5
• Failed: 7 ⚠
• Snapshots: 7
```

---

### 6b. Recent Deployments (With Impact)

```
Recent Deployments

[❌] dev → staging   2h ago
    ↳ Impacted: Invoice Sync

[❌] dev → staging   1d ago
    ↳ Impacted: Invoice Sync

[✅] dev → staging   3d ago
```

**Rules**
- Failed deployments explicitly list impacted workflows
- Click deployment → diff + affected workflows
- Change-failure correlation is explicit, not inferred

---

## 7. Drill-Down & Navigation Rules

All major elements support:

- Click → filtered deep dive
- Filter inheritance (env + time)
- Breadcrumb navigation back to Observability

**Example Paths**
- Error Type → Affected Workflows → Execution Timeline
- Workflow → Execution Timeline → Node Error
- Deployment → Diff → Impacted Workflows

---

## What This Wireframe Fixes

- ❌ Passive reporting → ✅ active diagnosis
- ❌ Metric overload → ✅ decision ordering
- ❌ Green health lies → ✅ semantic health
- ❌ Disconnected deploy data → ✅ causality

---

## Implementation Priority (Recommended)

1. Error Intelligence section
2. Workflow Risk Table improvements
3. KPI trends + deltas
4. Environment health semantics
5. Deployment → failure correlation
6. Insight summary automation

---

## Minimal Next Step

Implement **Sections 3 and 4** first.  
That alone moves WorkflowOps from *monitoring* to *operating*.
