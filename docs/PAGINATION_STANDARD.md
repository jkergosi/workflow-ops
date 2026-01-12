# Pagination Standard

**Version:** 1.0
**Last Updated:** 2024-01-12
**Status:** Active

---

## Table of Contents

1. [Overview](#overview)
2. [When to Use Pagination](#when-to-use-pagination)
3. [API Contract](#api-contract)
4. [Backend Implementation](#backend-implementation)
5. [Frontend Implementation](#frontend-implementation)
6. [Code Examples](#code-examples)
7. [Best Practices](#best-practices)
8. [Testing Guidelines](#testing-guidelines)
9. [Migration Guide](#migration-guide)

---

## Overview

This document defines the standard pagination approach for all list endpoints in the n8n-ops platform. Consistent pagination ensures predictable API behavior, optimal performance, and a unified user experience across the application.

### Goals

- **Performance:** Prevent loading large datasets that can degrade response times and memory usage
- **Consistency:** Provide a standardized API contract across all paginated endpoints
- **User Experience:** Deliver fast, responsive list views with intuitive navigation controls
- **Scalability:** Support datasets that grow from hundreds to millions of records

### Key Principles

1. **Server-side pagination required** for all medium-to-high-risk list endpoints
2. **Standardized envelope format** for all paginated responses
3. **Deterministic ordering** to prevent duplicate/missing items across pages
4. **Reusable UI components** for consistent frontend pagination controls

---

## When to Use Pagination

Use the decision tree below to determine if an endpoint requires pagination:

```
┌─────────────────────────────────────┐
│ Does endpoint return a collection?  │
└─────────────┬───────────────────────┘
              │ Yes
              ▼
┌─────────────────────────────────────┐
│ Expected record count?               │
└─────────────┬───────────────────────┘
              │
      ┌───────┴────────┐
      │                │
      ▼                ▼
  < 20 records    20+ records
      │                │
      ▼                ▼
  ┌─────────┐    ┌──────────────┐
  │ No      │    │ PAGINATION   │
  │ Pagination │ │ REQUIRED     │
  └─────────┘    └──────────────┘
```

### Risk Assessment Table

| Risk Level | Expected Records | Examples | Action |
|------------|------------------|----------|--------|
| **High** | 1,000+ | Executions, Activity logs, Deployments, Snapshots | **MUST** paginate |
| **Medium** | 100-1,000 | Workflows, Canonical workflows, Workflow mappings, Diff states, Billing invoices | **SHOULD** paginate |
| **Low** | < 100 | Environments, Credentials, Team members, Notification channels | **MAY** skip pagination |

### When Pagination is NOT Required

- **Dropdown/Select options:** Small static lists (< 20 items) like environment types, status enums
- **Metadata endpoints:** Single record responses (e.g., GET /workflow/{id})
- **Aggregated data:** Summary statistics that return fixed-size results
- **Real-time feeds:** SSE/WebSocket streams with different data delivery patterns

---

## API Contract

### Standard Pagination Envelope

All paginated endpoints MUST return responses conforming to this envelope:

```json
{
  "items": [...],       // Array of data items for current page
  "total": 0,           // Total count across all pages (int >= 0)
  "page": 1,            // Current page number (int >= 1, 1-indexed)
  "pageSize": 50,       // Items per page (int, 1-100)
  "totalPages": 0,      // Total number of pages (int >= 0)
  "hasMore": false      // Boolean indicating more pages exist
}
```

### Query Parameters

All paginated endpoints MUST accept these standard query parameters:

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `page` | integer | `1` | >= 1 | Page number (1-indexed) |
| `page_size` | integer | `50` | 1-100 | Items per page |

### Constants

The following constants are defined in `app/schemas/pagination.py`:

```python
DEFAULT_PAGE_SIZE = 50   # Default items per page
MAX_PAGE_SIZE = 100      # Maximum allowed items per page
MIN_PAGE_SIZE = 1        # Minimum items per page
```

### Endpoint URL Pattern

Paginated endpoints follow this pattern:

```
GET /api/v1/{resource}?page={page}&page_size={page_size}&{filters}
```

**Examples:**
- `GET /api/v1/canonical-workflows?page=1&page_size=50`
- `GET /api/v1/workflow-mappings?page=2&page_size=25&environment_id={uuid}`
- `GET /api/v1/executions/paginated?page=1&page_size=50&status_filter=error`

---

## Backend Implementation

### 1. Import Pagination Schema

```python
from app.schemas.pagination import (
    PaginatedResponse,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE
)
```

### 2. Define Endpoint with Pagination

```python
@router.get("/resources", response_model=PaginatedResponse[ResourceResponse])
async def list_resources(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    filter_param: Optional[str] = None,
    user_info: dict = Depends(get_current_user),
    _: dict = Depends(require_entitlement("resource_read"))
):
    """
    List resources with server-side pagination.

    Query params:
        page: Page number (1-indexed, default 1)
        page_size: Items per page (default 50, max 100)
        filter_param: Optional filter

    Returns:
        Standardized pagination envelope
    """
```

### 3. Build Database Query with Pagination

```python
# Limit page_size to prevent abuse
page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

# Calculate offset
offset = (page - 1) * page_size

# Build query with count
query = (
    db_service.client.table("resources")
    .select("*", count="exact")
    .eq("tenant_id", tenant_id)
)

# Apply filters
if filter_param:
    query = query.eq("filter_field", filter_param)

# Add deterministic ordering (CRITICAL!)
query = query.order("created_at", desc=True).order("id", desc=False)

# Apply pagination
query = query.range(offset, offset + page_size - 1)

# Execute query
response = query.execute()

items = response.data or []
total = response.count if response.count is not None else 0
```

### 4. Return Paginated Response

```python
# Return using factory method (auto-computes totalPages and hasMore)
return PaginatedResponse.create(
    items=items,
    page=page,
    page_size=page_size,
    total=total
)
```

### 5. Deterministic Ordering (CRITICAL)

**Always include explicit ORDER BY clauses to ensure deterministic ordering.**

Without deterministic ordering, database queries may return items in random order, causing:
- Duplicate items across pages
- Missing items when paginating
- Inconsistent results between requests

**Good Examples:**
```python
# Time-based ordering with ID as tiebreaker
.order("created_at", desc=True).order("id", desc=False)

# For updates/modifications
.order("updated_at", desc=True).order("id", desc=False)

# For timestamp-based data
.order("last_sync_at", desc=True).order("canonical_id", desc=False)

# For alphabetical lists
.order("name", desc=False).order("id", desc=False)
```

**Bad Examples (DO NOT USE):**
```python
# ❌ No ordering - non-deterministic
.select("*")

# ❌ Only one sort field - non-deterministic when values are equal
.order("created_at", desc=True)

# ❌ Ordering by nullable field only
.order("deleted_at", desc=True)  # Many NULL values cause random order
```

---

## Frontend Implementation

### 1. Import Types and Component

```typescript
import { PaginationControls } from '@/components/ui/pagination-controls';
import type { PaginatedResponse } from '@/types';
```

### 2. Setup State

```typescript
// Pagination state
const [currentPage, setCurrentPage] = useState(1);
const [pageSize, setPageSize] = useState(50);
const [totalItems, setTotalItems] = useState(0);
const [totalPages, setTotalPages] = useState(0);
const [isLoading, setIsLoading] = useState(false);

// Data state
const [items, setItems] = useState<ResourceType[]>([]);
```

### 3. Fetch Data with Pagination

```typescript
const loadData = async () => {
  setIsLoading(true);
  try {
    const response = await apiClient.getResources({
      page: currentPage,
      pageSize: pageSize,
      // ...other filters
    });

    const paginatedData = response.data as PaginatedResponse<ResourceType>;
    setItems(paginatedData.items);
    setTotalItems(paginatedData.total);
    setTotalPages(paginatedData.totalPages);
  } catch (error) {
    toast.error('Failed to load data');
  } finally {
    setIsLoading(false);
  }
};

// Re-fetch when page or pageSize changes
useEffect(() => {
  loadData();
}, [currentPage, pageSize]);
```

### 4. Add Pagination Controls to UI

```tsx
<PaginationControls
  currentPage={currentPage}
  totalPages={totalPages}
  total={totalItems}
  pageSize={pageSize}
  onPageChange={setCurrentPage}
  onPageSizeChange={(newSize) => {
    setPageSize(newSize);
    setCurrentPage(1); // Reset to first page when page size changes
  }}
  isLoading={isLoading}
  itemLabel="workflows"
/>
```

### 5. Handle Filter Changes

When applying filters, always reset to page 1:

```typescript
const handleFilterChange = (filterValue: string) => {
  setFilterValue(filterValue);
  setCurrentPage(1); // Reset to first page
};
```

---

## Code Examples

### Example 1: Basic Paginated Endpoint

**Backend (Python/FastAPI):**

```python
# app/api/endpoints/workflows.py
from fastapi import APIRouter, Depends
from typing import Optional
from app.schemas.pagination import PaginatedResponse, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.schemas.workflow import WorkflowResponse
from app.services.database import db_service
from app.services.auth_service import get_current_user

router = APIRouter()

@router.get("/workflows", response_model=PaginatedResponse[WorkflowResponse])
async def list_workflows(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    user_info: dict = Depends(get_current_user)
):
    """List workflows with pagination"""
    tenant_id = user_info["tenant"]["id"]

    # Limit page_size
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

    # Query with pagination
    query = (
        db_service.client.table("workflows")
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

**Frontend (TypeScript/React):**

```typescript
// pages/WorkflowsPage.tsx
import { useState, useEffect } from 'react';
import { PaginationControls } from '@/components/ui/pagination-controls';
import { apiClient } from '@/lib/api-client';
import type { Workflow, PaginatedResponse } from '@/types';

export function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    loadWorkflows();
  }, [currentPage, pageSize]);

  const loadWorkflows = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.get('/workflows', {
        params: { page: currentPage, page_size: pageSize }
      });

      const data = response.data as PaginatedResponse<Workflow>;
      setWorkflows(data.items);
      setTotalItems(data.total);
      setTotalPages(data.totalPages);
    } catch (error) {
      console.error('Failed to load workflows:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <Table>
        {/* Table content */}
      </Table>

      <PaginationControls
        currentPage={currentPage}
        totalPages={totalPages}
        total={totalItems}
        pageSize={pageSize}
        onPageChange={setCurrentPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setCurrentPage(1);
        }}
        isLoading={isLoading}
        itemLabel="workflows"
      />
    </div>
  );
}
```

### Example 2: Paginated Endpoint with Filters

**Backend:**

```python
@router.get("/workflow-mappings", response_model=PaginatedResponse[WorkflowEnvMapResponse])
async def list_workflow_mappings(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    environment_id: Optional[str] = None,
    canonical_id: Optional[str] = None,
    status: Optional[str] = None,
    user_info: dict = Depends(get_current_user)
):
    """List workflow mappings with filters and pagination"""
    tenant_id = user_info["tenant"]["id"]
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

    # Build query with filters
    query = (
        db_service.client.table("workflow_env_map")
        .select("*", count="exact")
        .eq("tenant_id", tenant_id)
    )

    # Apply optional filters
    if environment_id:
        query = query.eq("environment_id", environment_id)
    if canonical_id:
        query = query.eq("canonical_id", canonical_id)
    if status:
        query = query.eq("status", status)

    # Deterministic ordering
    query = (
        query
        .order("last_env_sync_at", desc=True)
        .order("canonical_id", desc=False)
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

**Frontend:**

```typescript
const loadMappings = async () => {
  setIsLoading(true);
  try {
    const response = await apiClient.get('/workflow-mappings', {
      params: {
        page: currentPage,
        page_size: pageSize,
        environment_id: selectedEnv || undefined,
        status: statusFilter || undefined
      }
    });

    const data = response.data as PaginatedResponse<WorkflowEnvMap>;
    setMappings(data.items);
    setTotalItems(data.total);
    setTotalPages(data.totalPages);
  } catch (error) {
    toast.error('Failed to load mappings');
  } finally {
    setIsLoading(false);
  }
};

// When filter changes, reset to page 1
const handleFilterChange = (newFilter: string) => {
  setStatusFilter(newFilter);
  setCurrentPage(1);
};
```

### Example 3: API Client Method

**TypeScript:**

```typescript
// lib/api-client.ts

class ApiClient {
  // Generic paginated GET
  async getPaginated<T>(
    endpoint: string,
    params: {
      page?: number;
      pageSize?: number;
      [key: string]: any;
    } = {}
  ): Promise<PaginatedResponse<T>> {
    const response = await this.client.get(endpoint, {
      params: {
        page: params.page || 1,
        page_size: params.pageSize || 50,
        ...params
      }
    });
    return response.data;
  }

  // Specific method for canonical workflows
  async getCanonicalWorkflows(params: {
    page?: number;
    pageSize?: number;
    includeDeleted?: boolean;
  } = {}) {
    return this.getPaginated<CanonicalWorkflow>(
      '/canonical/canonical-workflows',
      {
        page: params.page,
        pageSize: params.pageSize,
        include_deleted: params.includeDeleted
      }
    );
  }

  // Specific method for workflow mappings
  async getWorkflowMappings(params: {
    page?: number;
    pageSize?: number;
    environmentId?: string;
    canonicalId?: string;
    status?: string;
  } = {}) {
    return this.getPaginated<WorkflowEnvMap>(
      '/canonical/workflow-mappings',
      {
        page: params.page,
        pageSize: params.pageSize,
        environment_id: params.environmentId,
        canonical_id: params.canonicalId,
        status: params.status
      }
    );
  }
}
```

---

## Best Practices

### Backend Best Practices

1. **Always validate and cap page_size:**
   ```python
   page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
   ```

2. **Use deterministic ordering:**
   ```python
   .order("created_at", desc=True).order("id", desc=False)
   ```

3. **Use `count="exact"` for accurate totals:**
   ```python
   .select("*", count="exact")
   ```

4. **Handle edge cases gracefully:**
   - Empty results: `total=0, items=[], totalPages=0, hasMore=false`
   - Page beyond total: Return empty items with correct metadata
   - Invalid params: Clamp to valid ranges

5. **Add endpoint documentation:**
   - Document all query parameters
   - Specify default values
   - Show example requests/responses

6. **Consider performance:**
   - Add database indexes on sort columns
   - Avoid complex JOINs in paginated queries
   - Consider caching for high-traffic endpoints

### Frontend Best Practices

1. **Reset to page 1 when filters change:**
   ```typescript
   const handleFilterChange = (filter: string) => {
     setFilter(filter);
     setCurrentPage(1); // Important!
   };
   ```

2. **Show loading states:**
   ```tsx
   <PaginationControls isLoading={isLoading} ... />
   ```

3. **Use meaningful item labels:**
   ```tsx
   itemLabel="workflows"  // Not "items"
   ```

4. **Handle errors gracefully:**
   ```typescript
   try {
     await loadData();
   } catch (error) {
     toast.error('Failed to load data');
     // Consider showing empty state or retry button
   }
   ```

5. **Debounce search inputs:**
   ```typescript
   const debouncedSearch = useMemo(
     () => debounce((query: string) => {
       setSearchQuery(query);
       setCurrentPage(1);
     }, 300),
     []
   );
   ```

### API Client Best Practices

1. **Use consistent parameter naming:**
   - Backend: `page_size` (snake_case)
   - Frontend: `pageSize` (camelCase)
   - API Client: Transform between conventions

2. **Provide typed methods:**
   ```typescript
   async getWorkflows(params: {
     page?: number;
     pageSize?: number;
   }): Promise<PaginatedResponse<Workflow>>
   ```

3. **Set sensible defaults:**
   ```typescript
   page: params.page || 1,
   page_size: params.pageSize || 50
   ```

---

## Testing Guidelines

### Backend Tests

Test the following scenarios for each paginated endpoint:

```python
# test_pagination.py

async def test_pagination_first_page():
    """Test first page returns correct items"""
    response = await client.get("/resources?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 10
    assert data["page"] == 1
    assert data["pageSize"] == 10
    assert data["total"] >= 0
    assert data["totalPages"] >= 0
    assert isinstance(data["hasMore"], bool)

async def test_pagination_empty_results():
    """Test empty results return valid envelope"""
    response = await client.get("/resources?page=1&page_size=10")
    data = response.json()
    if data["total"] == 0:
        assert data["items"] == []
        assert data["totalPages"] == 0
        assert data["hasMore"] == False

async def test_pagination_page_beyond_total():
    """Test requesting page beyond total returns empty items"""
    response = await client.get("/resources?page=999&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["page"] == 999

async def test_pagination_max_page_size():
    """Test page_size is capped at MAX_PAGE_SIZE"""
    response = await client.get("/resources?page=1&page_size=999")
    assert response.status_code == 200
    data = response.json()
    assert data["pageSize"] <= 100  # MAX_PAGE_SIZE

async def test_pagination_deterministic_ordering():
    """Test same page returns same items on multiple requests"""
    response1 = await client.get("/resources?page=1&page_size=10")
    response2 = await client.get("/resources?page=1&page_size=10")

    data1 = response1.json()
    data2 = response2.json()

    # Should return identical results
    assert data1["items"] == data2["items"]

async def test_pagination_no_duplicates():
    """Test no items appear on multiple pages"""
    page1 = await client.get("/resources?page=1&page_size=10")
    page2 = await client.get("/resources?page=2&page_size=10")

    data1 = page1.json()
    data2 = page2.json()

    # Extract IDs
    ids1 = {item["id"] for item in data1["items"]}
    ids2 = {item["id"] for item in data2["items"]}

    # No overlap
    assert len(ids1 & ids2) == 0

async def test_pagination_with_filters():
    """Test pagination works with filters"""
    response = await client.get(
        "/resources?page=1&page_size=10&filter_param=value"
    )
    assert response.status_code == 200
    data = response.json()
    # Verify items match filter
    for item in data["items"]:
        assert item["filter_field"] == "value"
```

### Frontend Tests

```typescript
// WorkflowsPage.test.tsx

describe('WorkflowsPage Pagination', () => {
  it('loads first page on mount', async () => {
    render(<WorkflowsPage />);
    await waitFor(() => {
      expect(screen.getByText(/Page 1 of/)).toBeInTheDocument();
    });
  });

  it('navigates to next page', async () => {
    render(<WorkflowsPage />);
    const nextButton = screen.getByLabelText('Go to next page');
    fireEvent.click(nextButton);
    await waitFor(() => {
      expect(screen.getByText(/Page 2 of/)).toBeInTheDocument();
    });
  });

  it('changes page size', async () => {
    render(<WorkflowsPage />);
    const pageSizeSelect = screen.getByLabelText('Rows per page:');
    fireEvent.change(pageSizeSelect, { target: { value: '25' } });
    await waitFor(() => {
      // Should reset to page 1
      expect(screen.getByText(/Page 1 of/)).toBeInTheDocument();
    });
  });

  it('resets to page 1 when filter changes', async () => {
    render(<WorkflowsPage />);
    // Navigate to page 2
    const nextButton = screen.getByLabelText('Go to next page');
    fireEvent.click(nextButton);

    // Apply filter
    const filterInput = screen.getByPlaceholderText('Filter...');
    fireEvent.change(filterInput, { target: { value: 'test' } });

    // Should reset to page 1
    await waitFor(() => {
      expect(screen.getByText(/Page 1 of/)).toBeInTheDocument();
    });
  });
});
```

---

## Migration Guide

### Migrating Existing Endpoints to Pagination

Follow these steps to add pagination to an existing endpoint:

#### Step 1: Update Backend Endpoint

**Before:**
```python
@router.get("/resources")
async def list_resources(user_info: dict = Depends(get_current_user)):
    resources = await db_service.get_all_resources(tenant_id)
    return {"resources": resources}
```

**After:**
```python
from app.schemas.pagination import PaginatedResponse, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

@router.get("/resources", response_model=PaginatedResponse[ResourceResponse])
async def list_resources(
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    user_info: dict = Depends(get_current_user)
):
    tenant_id = user_info["tenant"]["id"]
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

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

#### Step 2: Update API Client

**Before:**
```typescript
async getResources() {
  const response = await this.client.get('/resources');
  return response.data.resources;
}
```

**After:**
```typescript
async getResources(params: {
  page?: number;
  pageSize?: number;
} = {}) {
  return this.getPaginated<Resource>('/resources', {
    page: params.page,
    pageSize: params.pageSize
  });
}
```

#### Step 3: Update Frontend Component

**Before:**
```typescript
const [resources, setResources] = useState<Resource[]>([]);

useEffect(() => {
  loadResources();
}, []);

const loadResources = async () => {
  const data = await apiClient.getResources();
  setResources(data);
};
```

**After:**
```typescript
const [resources, setResources] = useState<Resource[]>([]);
const [currentPage, setCurrentPage] = useState(1);
const [pageSize, setPageSize] = useState(50);
const [totalItems, setTotalItems] = useState(0);
const [totalPages, setTotalPages] = useState(0);
const [isLoading, setIsLoading] = useState(false);

useEffect(() => {
  loadResources();
}, [currentPage, pageSize]);

const loadResources = async () => {
  setIsLoading(true);
  try {
    const response = await apiClient.getResources({
      page: currentPage,
      pageSize: pageSize
    });

    const data = response.data as PaginatedResponse<Resource>;
    setResources(data.items);
    setTotalItems(data.total);
    setTotalPages(data.totalPages);
  } finally {
    setIsLoading(false);
  }
};
```

#### Step 4: Add Pagination Controls

```tsx
<PaginationControls
  currentPage={currentPage}
  totalPages={totalPages}
  total={totalItems}
  pageSize={pageSize}
  onPageChange={setCurrentPage}
  onPageSizeChange={(size) => {
    setPageSize(size);
    setCurrentPage(1);
  }}
  isLoading={isLoading}
  itemLabel="resources"
/>
```

### Backward Compatibility

If you need to maintain backward compatibility with existing consumers:

```python
@router.get("/resources")
async def list_resources(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    user_info: dict = Depends(get_current_user)
):
    """
    List resources with optional pagination.

    If page/page_size are provided, returns paginated response.
    Otherwise, returns legacy format (all items).
    """
    tenant_id = user_info["tenant"]["id"]

    # Legacy mode: return all items
    if page is None and page_size is None:
        resources = await db_service.get_all_resources(tenant_id)
        return {"resources": resources}  # Legacy format

    # Paginated mode
    page = page or 1
    page_size = page_size or DEFAULT_PAGE_SIZE
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

    # ... pagination logic ...

    return PaginatedResponse.create(...)  # New format
```

---

## Summary

### Quick Checklist for New Endpoints

- [ ] Endpoint returns 100+ records? → Add pagination
- [ ] Added `page` and `page_size` query parameters
- [ ] Response uses `PaginatedResponse[T]` envelope
- [ ] Query includes deterministic ordering (ORDER BY)
- [ ] Page size capped at MAX_PAGE_SIZE (100)
- [ ] Frontend uses `PaginationControls` component
- [ ] API client method added with typed parameters
- [ ] Filter changes reset page to 1
- [ ] Tests cover edge cases (empty, beyond total, duplicates)
- [ ] Documentation updated in PAGINATION_INVENTORY.md

### Key Takeaways

1. **Server-side pagination is non-negotiable** for endpoints with 100+ records
2. **Deterministic ordering prevents data integrity issues** across pages
3. **Standardized envelope ensures consistency** across all paginated endpoints
4. **Reusable UI components deliver uniform UX** and reduce code duplication
5. **Comprehensive testing prevents pagination bugs** in production

---

## Related Documentation

- [PAGINATION_INVENTORY.md](./PAGINATION_INVENTORY.md) - Complete list of endpoints and pagination status
- [API Design Guidelines](./API_DESIGN_GUIDELINES.md) - General API design patterns
- [Database Query Optimization](./DATABASE_OPTIMIZATION.md) - Performance tips for paginated queries

---

**Questions or Issues?**
Contact the platform team or open an issue in the repository.
