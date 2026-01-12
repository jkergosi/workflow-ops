# Pagination Inventory

**Version:** 1.0
**Last Updated:** 2024-01-12
**Status:** Active

---

## Table of Contents

1. [Overview](#overview)
2. [Pagination Status Summary](#pagination-status-summary)
3. [Complete Endpoint Inventory](#complete-endpoint-inventory)
4. [Risk Assessment Matrix](#risk-assessment-matrix)
5. [Implementation Priority](#implementation-priority)
6. [Recently Implemented](#recently-implemented)
7. [Maintenance Guidelines](#maintenance-guidelines)

---

## Overview

This document provides a comprehensive inventory of all list/collection endpoints in the n8n-ops platform, tracking their pagination status, risk levels, and implementation priorities. It serves as the single source of truth for pagination coverage and helps prevent future pagination gaps.

### Purpose

- **Track pagination coverage** across all list endpoints
- **Identify high-risk endpoints** that require immediate pagination
- **Prevent regression** by documenting expected pagination status
- **Guide new development** with clear risk assessment criteria

### Related Documentation

- [PAGINATION_STANDARD.md](./PAGINATION_STANDARD.md) - Implementation standards and patterns
- Backend pagination schemas: `app/schemas/pagination.py`
- Frontend pagination component: `n8n-ops-ui/src/components/ui/pagination-controls.tsx`

---

## Pagination Status Summary

| Status | Count | Description |
|--------|-------|-------------|
| ✅ **Implemented** | 13 | Endpoints with full server-side pagination |
| ⚠️ **Partial** | 8 | Has limit/offset but no standard PaginatedResponse |
| ❌ **Missing** | 24 | No pagination implementation |
| **Total Endpoints** | **45** | All list/collection endpoints |

### By Risk Level

| Risk Level | Total | Implemented | Partial | Missing |
|------------|-------|-------------|---------|---------|
| 🔴 **HIGH** | 11 | 1 | 9 | 1 |
| 🟡 **MEDIUM** | 15 | 7 | 2 | 6 |
| 🟢 **LOW** | 19 | 5 | 0 | 14 |

---

## Complete Endpoint Inventory

### 🔴 HIGH RISK (1,000+ records expected)

Endpoints that could exceed 1,000 rows and **MUST** have pagination.

| # | Endpoint | Method | Pagination Status | Risk Justification | Notes |
|---|----------|--------|-------------------|-------------------|-------|
| 1 | `/api/v1/executions` | GET | ⚠️ **Partial** | Millions of executions over time | Has `limit` (default 100) but no `page`/`pageSize`, no `PaginatedResponse` envelope |
| 2 | `/api/v1/deployments` | GET | ❌ **Missing** | 1000s of deployments for large teams | Unbounded `.select("*")` |
| 3 | `/api/v1/snapshots` | GET | ❌ **Missing** | Many workflows × many snapshots | Unbounded per workflow |
| 4 | `/api/v1/admin/audit-logs` | GET | ✅ **Implemented** | Enterprise audit logging (10k+ rows) | **Reference implementation**: page/page_size (1-100) |
| 5 | `/api/v1/admin/billing/recent-charges` | GET | ⚠️ **Partial** | Payment transactions accumulate | Has `limit` (50, max 100) but no pagination metadata |
| 6 | `/api/v1/admin/billing/failed-payments` | GET | ⚠️ **Partial** | Failed payment history | Has `limit` (50, max 100) but no pagination metadata |
| 7 | `/api/v1/background-jobs` | GET | ⚠️ **Partial** | Long-running job history | Has `limit`/`offset` but no standard `PaginatedResponse` |
| 8 | `/api/v1/notifications/events` | GET | ⚠️ **Partial** | Alert event history (1000s) | Has `limit` (50, max 200) but no `page`/`total` |
| 9 | `/api/v1/notifications/alert-rules/{id}/history` | GET | ⚠️ **Partial** | Alert evaluation history | Has `limit`/`offset`, could be 1000s of evaluations |
| 10 | `/api/v1/drift-approvals` | GET | ⚠️ **Partial** | Drift approval history | Has `limit`/`offset` but no `page`/`total` |
| 11 | `/api/v1/incidents` | GET | ⚠️ **Partial** | Drift incident history | Has `limit`/`offset`/`total` but no `page` number |

### 🟡 MEDIUM RISK (100-1,000 records expected)

Endpoints that could have 100-1,000 rows and **SHOULD** have pagination.

| # | Endpoint | Method | Pagination Status | Risk Justification | Notes |
|---|----------|--------|-------------------|-------------------|-------|
| 12 | `/api/v1/canonical/canonical-workflows` | GET | ✅ **Implemented** | 100-500 canonical workflows | **Recently added**: page/page_size, deterministic ordering by `created_at` DESC |
| 13 | `/api/v1/canonical/workflow-mappings` | GET | ✅ **Implemented** | 100-1000 workflow mappings | **Recently added**: page/page_size, filters (env_id, canonical_id, status) |
| 14 | `/api/v1/canonical/diff-states` | GET | ✅ **Implemented** | 100-1000 diff states | **Recently added**: page/page_size, deterministic ordering by `computed_at` DESC |
| 15 | `/api/v1/canonical/untracked` | GET | ❌ **Missing** | Untracked workflows across envs | Unbounded, could have 100s |
| 16 | `/api/v1/promotions` | GET | ❌ **Missing** | CI/CD promotions (100s) | Unbounded, heavy CI/CD tenants |
| 17 | `/api/v1/billing/invoices` | GET | ✅ **Implemented** | Billing invoices accumulate | **Recently added**: page/page_size with Stripe cursor handling |
| 18 | `/api/v1/billing/payment-history` | GET | ✅ **Implemented** | Payment transaction history | **Recently added**: page/page_size, ordered by `created_at` DESC |
| 19 | `/api/v1/restore/snapshots/{workflow_id}` | GET | ✅ **Implemented** | Workflow snapshots (per workflow) | **Recently added**: page/page_size, ordered by `created_at` DESC, `version` DESC |
| 20 | `/api/v1/admin/billing/tenants/{id}/invoices` | GET | ⚠️ **Partial** | Tenant invoices (admin view) | Has `limit` (20, max 100) but no pagination |
| 21 | `/api/v1/admin/tenants` | GET | ✅ **Implemented** | Multi-tenant platform | **Reference implementation**: page/page_size (1-100) |
| 22 | `/api/v1/admin/tenants/{id}/users` | GET | ✅ **Implemented** | Tenant users | **Reference implementation**: page/page_size |
| 23 | `/api/v1/admin/tenants/{id}/audit-logs` | GET | ✅ **Implemented** | Tenant config audit logs | **Reference implementation**: page/page_size |
| 24 | `/api/v1/admin/tenants/{id}/access-logs` | GET | ✅ **Implemented** | Tenant feature access logs | **Reference implementation**: page/page_size |
| 25 | `/api/v1/tenants/{id}/notes` | GET | ❌ **Missing** | Tenant notes | Unbounded but typically <100 notes |
| 26 | `/api/v1/workflows` | GET | ❌ **Missing** | All workflows (legacy) | Unbounded, could have 200-500 workflows |

### 🟢 LOW RISK (<100 records expected)

Endpoints with small result sets where pagination is optional but recommended for consistency.

| # | Endpoint | Method | Pagination Status | Risk Justification | Notes |
|---|----------|--------|-------------------|-------------------|-------|
| 27 | `/api/v1/environments` | GET | ❌ **Missing** | Typically 1-10 per tenant | Low priority |
| 28 | `/api/v1/credentials` | GET | ❌ **Missing** | Typically <50 per tenant | Low priority |
| 29 | `/api/v1/teams` | GET | ❌ **Missing** | Typically 1-100 users | Low priority |
| 30 | `/api/v1/pipelines` | GET | ❌ **Missing** | Typically 1-10 pipelines | Low priority |
| 31 | `/api/v1/notifications/channels` | GET | ❌ **Missing** | Typically <20 channels | Low priority |
| 32 | `/api/v1/notifications/rules` | GET | ❌ **Missing** | Typically <50 rules | Low priority |
| 33 | `/api/v1/notifications/alert-rules` | GET | ❌ **Missing** | Typically <100 rules | Low priority |
| 34 | `/api/v1/admin/billing/plan-distribution` | GET | ❌ **Missing** | Small: count by plan (5-10 items) | Aggregated data |
| 35 | `/api/v1/admin/billing/dunning` | GET | ❌ **Missing** | Small: only problematic tenants | Low priority |
| 36 | `/api/v1/tags` | GET | ❌ **Missing** | Typically <100 tags | Low priority |
| 37 | `/api/v1/n8n-users` | GET | ❌ **Missing** | Small: users per environment | Low priority |
| 38 | `/api/v1/observability/workflow-performance` | GET | ⚠️ **Partial** | Analytics endpoint | Has `limit` (default 10) |
| 39 | `/api/v1/observability/environment-health` | GET | ❌ **Missing** | Small: one per environment | Low priority |
| 40 | `/api/v1/admin/tenants/{id}/overrides` | GET | ❌ **Missing** | Typically <50 overrides | Low priority |
| 41 | `/api/v1/drift-approvals/pending` | GET | ❌ **Missing** | Typically <50 pending | Low priority |
| 42 | `/api/v1/canonical/link-suggestions` | GET | ❌ **Missing** | Typically <100 suggestions | Low priority |
| 43 | `/api/v1/billing/plans` | GET | ❌ **Missing** | Small: 5-10 plans | Static data |
| 44 | `/api/v1/admin/environment-types` | GET | ❌ **Missing** | Small: enumeration (<10) | Static data |
| 45 | `/api/v1/health` | GET | N/A | Health check endpoint | Not a list endpoint |

---

## Risk Assessment Matrix

### Risk Level Criteria

| Risk Level | Expected Records | Performance Impact | Data Growth Rate | Action Required |
|------------|------------------|-------------------|------------------|-----------------|
| 🔴 **HIGH** | 1,000+ | Critical (OOM, timeouts) | Continuous | **MUST** paginate immediately |
| 🟡 **MEDIUM** | 100-1,000 | Moderate (slow responses) | Regular | **SHOULD** paginate |
| 🟢 **LOW** | <100 | Minimal | Slow | **MAY** skip pagination |

### Determining Risk Level

Use this decision tree to classify new endpoints:

```
┌────────────────────────────────────────┐
│ Will this endpoint exceed 100 records? │
└────────────┬───────────────────────────┘
             │
      ┌──────┴────────┐
      │ YES           │ NO
      ▼               ▼
┌─────────────┐   ┌────────────┐
│ Exceeds     │   │ LOW RISK   │
│ 1,000?      │   │ Optional   │
└──────┬──────┘   └────────────┘
       │
   ┌───┴────┐
   │ YES    │ NO
   ▼        ▼
┌────────┐ ┌────────────┐
│ HIGH   │ │ MEDIUM     │
│ RISK   │ │ RISK       │
│ MUST   │ │ SHOULD     │
└────────┘ └────────────┘
```

---

## Implementation Priority

### 🔥 Critical Priority (Immediate Action)

Endpoints with **HIGH** risk and **missing/partial** pagination:

1. **Executions** (`/api/v1/executions`) - **CRITICAL**
   - Current: Has `limit` but no proper pagination
   - Impact: Could have millions of executions
   - Action: Implement full `PaginatedResponse` with `page`/`page_size`

2. **Deployments** (`/api/v1/deployments`) - **HIGH**
   - Current: Completely unbounded
   - Impact: Large teams could have 1000s of deployments
   - Action: Implement full pagination

3. **Snapshots** (`/api/v1/snapshots`) - **HIGH**
   - Current: Unbounded per workflow
   - Impact: Multiple workflows × many snapshots = huge dataset
   - Action: Implement full pagination

### 🟡 High Priority (Next Sprint)

Standardize **partial** implementations to use `PaginatedResponse`:

4. **Background Jobs** (`/api/v1/background-jobs`)
5. **Notification Events** (`/api/v1/notifications/events`)
6. **Alert Rule History** (`/api/v1/notifications/alert-rules/{id}/history`)
7. **Drift Approvals** (`/api/v1/drift-approvals`)
8. **Incidents** (`/api/v1/incidents`)

### 🟢 Medium Priority (Future Enhancement)

Complete **MEDIUM** risk endpoints:

9. **Untracked Workflows** (`/api/v1/canonical/untracked`)
10. **Promotions** (`/api/v1/promotions`)
11. **Legacy Workflows** (`/api/v1/workflows`)

### ⚪ Low Priority (Optional)

**LOW** risk endpoints - implement as needed for consistency.

---

## Recently Implemented

The following endpoints were recently updated to include pagination (completed in current feature implementation):

### ✅ T002: Canonical Workflows
- **Endpoint:** `GET /api/v1/canonical/canonical-workflows`
- **File:** `n8n-ops-backend/app/api/endpoints/canonical_workflows.py` (lines 189-311)
- **Implementation:**
  - Query params: `page` (default 1), `page_size` (default 50, max 100), `include_deleted` (bool)
  - Response model: `PaginatedResponse[CanonicalWorkflowResponse]`
  - Deterministic ordering: `ORDER BY created_at DESC`
  - Includes collision detection enrichment
- **Frontend:** Updated `CanonicalWorkflowsPage.tsx` to use `PaginationControls` component

### ✅ T003: Workflow Mappings
- **Endpoint:** `GET /api/v1/canonical/workflow-mappings`
- **File:** `n8n-ops-backend/app/api/endpoints/canonical_workflows.py` (lines 379-467)
- **Implementation:**
  - Query params: `page`, `page_size`, `environment_id`, `canonical_id`, `status`
  - Response model: `PaginatedResponse[WorkflowEnvMapResponse]`
  - Deterministic ordering: `ORDER BY last_env_sync_at DESC, canonical_id ASC`
  - Supports multiple filter combinations
- **Frontend:** Updated `WorkflowMappingsPage.tsx` to use `PaginationControls` component

### ✅ T004: Diff States
- **Endpoint:** `GET /api/v1/canonical/diff-states`
- **File:** `n8n-ops-backend/app/api/endpoints/canonical_workflows.py` (lines 1580-1667)
- **Implementation:**
  - Query params: `page`, `page_size`, `source_env_id`, `target_env_id`, `canonical_id`
  - Response model: `PaginatedResponse[WorkflowDiffStateResponse]`
  - Deterministic ordering: `ORDER BY computed_at DESC, canonical_id ASC`
  - Environment-aware filtering
- **Frontend:** Updated `DiffStatesPage.tsx` to use `PaginationControls` component

### ✅ T005: Workflow Snapshots
- **Endpoint:** `GET /api/v1/restore/snapshots/{workflow_id}`
- **File:** `n8n-ops-backend/app/api/endpoints/restore.py` (lines 431-519)
- **Implementation:**
  - Path param: `workflow_id`
  - Query params: `page` (default 1), `page_size` (default 50, max 100)
  - Response model: `PaginatedResponse[SnapshotResponse]`
  - Deterministic ordering: `ORDER BY created_at DESC, version DESC`
  - Per-workflow snapshot history
- **Frontend:** Ready for integration with `PaginationControls` component

### ✅ T006: Billing Invoices
- **Endpoint:** `GET /api/v1/billing/invoices`
- **File:** `n8n-ops-backend/app/api/endpoints/billing.py` (lines 539-637)
- **Implementation:**
  - Query params: `page` (default 1), `page_size` (default 50, max 100)
  - Response model: `PaginatedResponse[InvoiceResponse]`
  - Stripe cursor-based pagination handling
  - Date-based ordering (newest first)
- **Frontend:** Updated `BillingPage.tsx` to use paginated invoices

### ✅ T007: Payment History
- **Endpoint:** `GET /api/v1/billing/payment-history`
- **File:** `n8n-ops-backend/app/api/endpoints/billing.py` (lines 679-733)
- **Implementation:**
  - Query params: `page` (default 1), `page_size` (default 50, max 100)
  - Response model: `PaginatedResponse[PaymentHistoryResponse]`
  - Database-level pagination
  - Deterministic ordering: `ORDER BY created_at DESC`
- **Frontend:** Updated `BillingPage.tsx` to use paginated payment history

---

## Maintenance Guidelines

### For New Endpoints

When creating a new list/collection endpoint, follow these steps:

1. **Assess Risk Level:**
   - Use the [Risk Assessment Matrix](#risk-assessment-matrix) decision tree
   - Document your assessment in the endpoint's docstring

2. **Implement Pagination (if required):**
   - Follow the [PAGINATION_STANDARD.md](./PAGINATION_STANDARD.md) implementation guide
   - Use `PaginatedResponse[T]` response model from `app/schemas/pagination.py`
   - Add deterministic ordering (e.g., `ORDER BY created_at DESC, id ASC`)
   - Validate and cap `page_size` to `MAX_PAGE_SIZE` (100)

3. **Update This Inventory:**
   - Add your endpoint to the appropriate risk category
   - Include implementation details and file location
   - Document any special considerations (filters, ordering, etc.)

4. **Frontend Integration:**
   - Use the `PaginationControls` component from `n8n-ops-ui/src/components/ui/pagination-controls.tsx`
   - Reset to page 1 when filters change
   - Handle loading and empty states

### Quarterly Review

Conduct a quarterly audit to ensure this inventory remains accurate:

- ✅ Verify pagination status for all endpoints
- ✅ Reassess risk levels based on actual data growth
- ✅ Update implementation priorities
- ✅ Document any new endpoints
- ✅ Review and update [PAGINATION_STANDARD.md](./PAGINATION_STANDARD.md) based on lessons learned

### Review Checklist

```markdown
- [ ] All HIGH-risk endpoints have pagination
- [ ] All MEDIUM-risk endpoints are prioritized for pagination
- [ ] New endpoints are documented in this inventory
- [ ] Pagination implementations follow the standard
- [ ] Frontend components use PaginationControls consistently
- [ ] Database queries include deterministic ordering
```

---

## Reference Implementation

### Good Examples to Follow

These endpoints serve as reference implementations for pagination:

1. **Admin Audit Logs** (`/api/v1/admin/audit-logs`)
   - File: `n8n-ops-backend/app/api/endpoints/admin_audit.py`
   - Features: Full pagination, filters, date-based ordering

2. **Canonical Workflows** (`/api/v1/canonical/canonical-workflows`)
   - File: `n8n-ops-backend/app/api/endpoints/canonical_workflows.py` (lines 189-311)
   - Features: Pagination, filters, deterministic ordering, enrichment

3. **Billing Invoices** (`/api/v1/billing/invoices`)
   - File: `n8n-ops-backend/app/api/endpoints/billing.py` (lines 539-637)
   - Features: Stripe cursor pagination, page number conversion

### Backend Pattern

```python
from app.schemas.pagination import PaginatedResponse, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

@router.get("/resources", response_model=PaginatedResponse[ResourceResponse])
async def list_resources(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    user_info: dict = Depends(get_current_user)
):
    # Validate and cap page_size
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

    # Query with deterministic ordering
    query = (
        db_service.client.table("resources")
        .select("*", count="exact")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .order("id", desc=False)
        .range(offset, offset + page_size - 1)
    )

    response = query.execute()

    return PaginatedResponse.create(
        items=response.data or [],
        page=page,
        page_size=page_size,
        total=response.count or 0
    )
```

### Frontend Pattern

```typescript
import { PaginationControls } from '@/components/ui/pagination-controls';

const [currentPage, setCurrentPage] = useState(1);
const [pageSize, setPageSize] = useState(50);
const [totalItems, setTotalItems] = useState(0);
const [totalPages, setTotalPages] = useState(0);

useEffect(() => {
  loadData();
}, [currentPage, pageSize]);

<PaginationControls
  currentPage={currentPage}
  totalPages={totalPages}
  total={totalItems}
  pageSize={pageSize}
  onPageChange={setCurrentPage}
  onPageSizeChange={(size) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to first page
  }}
  isLoading={isLoading}
  itemLabel="workflows"
/>
```

---

## Summary Statistics

### Overall Coverage

- **Total List Endpoints:** 45
- **Pagination Implemented:** 13 (28.9%)
- **Pagination Partial:** 8 (17.8%)
- **Pagination Missing:** 24 (53.3%)

### By Risk Level

- **HIGH Risk:**
  - Total: 11
  - Implemented: 1 (9.1%)
  - **Action Required:** 10 endpoints need immediate attention

- **MEDIUM Risk:**
  - Total: 15
  - Implemented: 7 (46.7%)
  - **Action Required:** 8 endpoints should be prioritized

- **LOW Risk:**
  - Total: 19
  - Implemented: 5 (26.3%)
  - **Action Required:** Optional based on consistency needs

### Recent Progress

In the current feature implementation (Tasks T002-T007), **6 MEDIUM-risk endpoints** were successfully updated to include pagination:
- ✅ Canonical Workflows
- ✅ Workflow Mappings
- ✅ Diff States
- ✅ Workflow Snapshots
- ✅ Billing Invoices
- ✅ Payment History

---

**Next Steps:**
1. Address **3 CRITICAL** high-risk endpoints (Executions, Deployments, Snapshots)
2. Standardize **8 partial implementations** to use `PaginatedResponse`
3. Continue quarterly audits to maintain inventory accuracy

---

**Questions or Updates?**
Contact the platform team or update this document via pull request.
