# Provider Abstraction Design Specification  
**File:** `provider_abstraction.md`  
**Target:** Claude Code  
**System:** Workflow Ops (React frontend, Python backend, Supabase Postgres)

---

## 1. Purpose and Scope

### 1.1 Purpose

Workflow Ops currently integrates directly with **n8n** as its only workflow provider. Logic for listing workflows, deploying, checking executions, and managing alerts is tightly coupled to n8n across backend and frontend.

The purpose of this design is to:

1. Introduce a **provider abstraction** so Workflow Ops can support multiple automation backends (e.g., n8n now, Make.com later) without structural rewrites.
2. Keep **runtime behavior unchanged** for the initial phase:
   - Only `n8n` is supported.
   - No provider selection appears in the UI.
3. Ensure the architecture is ready to add new providers with localized changes (new adapters) instead of system-wide refactors.

### 1.2 Scope

This specification covers:

- High-level provider abstraction architecture.
- Data model updates (Postgres).
- Backend architecture changes (Python services and integrations).
- Frontend architecture changes (React types, calls, state).
- Cross-cutting concerns that must be provider-aware.
- Migration and rollout at an architectural level (no file-by-file detail).

This document is **architectural**, not a step-by-step coding guide. Claude Code should use it to design and implement the provider layer in a maintainable, incremental way.

---

## 2. Current System Overview

### 2.1 Functional Context

Workflow Ops provides operations and governance around an n8n instance, including:

- Environments and connections to n8n servers.
- Workflow discovery and listing.
- Deployments (promoting workflows between environments).
- Snapshots / versions of workflows.
- Executions / logs viewing.
- Alerts / observability (health, failures, etc.).
- Pipelines and promotions (CI/CD workflows).
- GitHub integration for version control.

### 2.2 Technical Context

- **Frontend:** React (TypeScript), talking to a Python API.
- **Backend:** Python application (FastAPI), with:
  - REST endpoints for UI.
  - Service layer for business logic.
  - n8n integration layer (`N8NClient` class with 38 direct instantiations across 7 files).
  - GitHub service for workflow version control.
- **Database:** Supabase Postgres, with tables for:
  - `environments` (with `n8n_base_url`, `n8n_api_key`, etc.)
  - `workflows` (with `n8n_workflow_id`)
  - `deployments`
  - `snapshots`
  - `credentials` (with `n8n_credential_id`)
  - `executions`
  - `pipelines`
  - `promotions`
  - `deployment_workflows`
  - `tags`
  - `n8n_users`
  - `notification_channels` and `notification_rules`

**Current State:**
- Provider is implicitly "n8n everywhere" and not explicitly modeled.
- All provider-specific fields use `n8n_` prefix.
- `N8NClient` is instantiated directly throughout the codebase (endpoints and services).

---

## 3. Target Architecture: Provider Abstraction

### 3.1 Design Principle

All external workflow automation platforms (n8n, Make, future platforms) are treated as **providers** behind a stable internal interface.

Key ideas:

- The **service layer** (core business logic) is **provider-agnostic**.
- Each provider is encapsulated in a **Provider Adapter**.
- A **Provider Registry** resolves the correct adapter for a given entity.
- The **database** stores which provider each entity belongs to.

### 3.2 Conceptual Architecture

```
React UI
  ↓
Python API (REST)
  ↓
Service Layer (provider-agnostic business logic)
  ↓
Provider Registry (lookup)
  ↓
Provider Adapter (n8n / make / future)
  ↓
External Workflow Provider (n8n API, Make API, etc.)
```

The service layer never calls n8n-specific code directly. It always goes through a provider adapter resolved from the database.

---

## 4. Data Model Changes (Postgres)

### 4.1 Provider as a First-Class Attribute

Any entity that is directly or indirectly tied to a workflow backend must be provider-scoped. That includes:

**Provider-scoped tables (need `provider` column):**
- `environments`
- `workflows`
- `deployments`
- `snapshots` (note: table is named `snapshots`, not `workflow_snapshots`)
- `credentials`
- `executions`
- `pipelines` (promotion pipelines)
- `promotions` (promotion records)
- `deployment_workflows` (per-workflow deployment results)
- `tags` (workflow tags)
- `provider_users` (provider instance users; currently `n8n_users` table)
- `notification_channels` and `notification_rules` (alerting infrastructure)
- `health_checks` (environment health monitoring)

**System-scoped tables (NO provider column needed):**
- `tenants` - organization-level, not provider-specific
- `users` - team members, not tied to providers
- `git_configs` - tenant-level git configuration
- `events` - audit log (may include provider context in metadata)

**Legacy table:**
- `workflow_snapshots` - legacy table that should be deprecated in favor of `snapshots`  

### 4.2 Provider Field Definition

Add a `provider` column:

- Type: `TEXT`
- Nullability: `NOT NULL`
- Default: `'n8n'`
- Values validated in backend (`'n8n'`, `'make'` later)

Example:

```sql
ALTER TABLE environments
  ADD COLUMN provider TEXT NOT NULL DEFAULT 'n8n';

ALTER TABLE workflows
  ADD COLUMN provider TEXT NOT NULL DEFAULT 'n8n';
```

#### 4.2.1 Provider-Specific Configuration

The current system uses provider-specific field names (e.g., `n8n_base_url`, `n8n_api_key`, `n8n_encryption_key`). For provider abstraction, consider two approaches:

**Option A: Generic JSONB Configuration (Recommended)**
- Add a `provider_config` JSONB column to `environments` table
- Store provider-specific connection details as JSON
- Allows flexible configuration per provider without schema changes

```sql
ALTER TABLE environments
  ADD COLUMN provider_config JSONB DEFAULT '{}'::jsonb;

-- Migration: Move existing n8n fields to provider_config
UPDATE environments
SET provider_config = jsonb_build_object(
  'base_url', n8n_base_url,
  'api_key', n8n_api_key,
  'encryption_key', n8n_encryption_key
)
WHERE provider = 'n8n';
```

**Option B: Keep Provider-Specific Columns**
- Maintain current `n8n_*` prefixed columns
- Add provider-specific columns as new providers are added
- Less flexible but more explicit

**Recommendation:** Use Option A (JSONB) for flexibility, but maintain backward compatibility by keeping `n8n_*` columns during migration period.

### 4.3 Indexing

Composite indexes recommended for efficient provider-scoped queries:

```sql
-- Core indexes
CREATE INDEX idx_environments_provider_tenant ON environments(provider, tenant_id);
CREATE INDEX idx_workflows_provider_env ON workflows(provider, environment_id);
CREATE INDEX idx_workflows_provider_tenant ON workflows(provider, tenant_id);
CREATE INDEX idx_executions_provider_env ON executions(provider, environment_id);
CREATE INDEX idx_credentials_provider_env ON credentials(provider, environment_id);

-- Additional indexes for common query patterns
CREATE INDEX idx_deployments_provider_tenant ON deployments(provider, tenant_id);
CREATE INDEX idx_snapshots_provider_env ON snapshots(provider, environment_id);
CREATE INDEX idx_promotions_provider_tenant ON promotions(provider, tenant_id);

-- If keeping n8n_ prefixed fields for backward compatibility
CREATE INDEX idx_workflows_provider_n8n_id ON workflows(provider, n8n_workflow_id) 
  WHERE provider = 'n8n';
```

---

## 5. Backend Architecture (Python)

### 5.1 Provider Enum

Single source of truth:

```python
class Provider(str, Enum):
    N8N = "n8n"
    MAKE = "make"  # future
```

### 5.2 Provider Adapter Interface

The adapter interface must cover all provider-specific operations currently handled by `N8NClient`. The adapter is instantiated with environment configuration, so methods don't need an environment parameter:

```python
class ProviderAdapter(Protocol):
    """
    Provider adapter interface. Implementations are instantiated with config:
    adapter = N8NProviderAdapter(base_url=env.n8n_base_url, api_key=env.n8n_api_key)
    """

    # Workflow operations
    async def get_workflows(self) -> List[Dict[str, Any]]: ...
    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]: ...
    async def create_workflow(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]: ...
    async def update_workflow(self, workflow_id: str, workflow_data: Dict[str, Any]) -> Dict[str, Any]: ...
    async def delete_workflow(self, workflow_id: str) -> bool: ...
    async def activate_workflow(self, workflow_id: str) -> Dict[str, Any]: ...
    async def deactivate_workflow(self, workflow_id: str) -> Dict[str, Any]: ...

    # Execution operations
    async def get_executions(self, limit: int = 100) -> List[Dict[str, Any]]: ...
    # Note: Individual execution lookup is done from cached DB data, not provider API

    # Credential operations
    async def get_credentials(self) -> List[Dict[str, Any]]: ...
    async def get_credential(self, credential_id: str) -> Dict[str, Any]: ...
    async def create_credential(self, credential_data: Dict[str, Any]) -> Dict[str, Any]: ...
    async def update_credential(self, credential_id: str, credential_data: Dict[str, Any]) -> Dict[str, Any]: ...
    async def delete_credential(self, credential_id: str) -> bool: ...
    async def get_credential_types(self) -> List[Dict[str, Any]]: ...

    # User operations
    async def get_users(self) -> List[Dict[str, Any]]: ...

    # Tag operations
    async def get_tags(self) -> List[Dict[str, Any]]: ...
    async def update_workflow_tags(self, workflow_id: str, tag_ids: List[str]) -> Dict[str, Any]: ...

    # Connection and health
    async def test_connection(self) -> bool: ...
    async def get_health_status(self) -> Dict[str, Any]: ...  # Placeholder for future providers

    # Observability (placeholder for future providers)
    async def get_workflow_performance(self, workflow_id: str) -> Dict[str, Any]: ...  # Placeholder
```

**Implementation Notes:**
- All methods are async to match existing `N8NClient` patterns
- `get_health_status()` and `get_workflow_performance()` are placeholders for future providers; n8n implementation returns `NotImplementedError`
- The adapter is instantiated per-request with environment config, not passed per-method

### 5.3 Provider Registry

```python
class ProviderRegistry:
    _adapters = {
        Provider.N8N: N8NProviderAdapter(),
        # Provider.MAKE: MakeProviderAdapter() later
    }

    @classmethod
    def get_adapter(cls, provider: Provider):
        return cls._adapters[provider]
```

### 5.4 Service Layer Refactor

Every service method must:

1. Load entity  
2. Read `provider` field  
3. Convert to enum  
4. Fetch adapter from registry  
5. Delegate logic to adapter  

No service function should call n8n directly.

### 5.5 Encapsulating n8n Logic

All existing n8n HTTP logic moves into `N8NProviderAdapter`.

The service layer becomes clean and provider-agnostic.

**Migration Scope Note:**

The current codebase has **38 direct instantiations** of `N8NClient` across 7 files:

| File | Instantiations |
|------|----------------|
| `workflows.py` | 13 |
| `promotion_service.py` | 7 |
| `credentials.py` | 6 |
| `environments.py` | 5 |
| `restore.py` | 3 |
| `snapshots.py` | 1 |
| `observability_service.py` | 1 |
| `n8n_client.py` | 1 (global, unused) |
| **Total** | **38** |

**Recommended Migration Approach:**
1. Create `N8NProviderAdapter` that wraps `N8NClient`
2. Refactor endpoints first (higher visibility, easier to test)
3. Refactor services second (business logic layer)
4. Consider a phased rollout with feature flags to validate each phase

---

## 6. Frontend Architecture (React)

### 6.1 Types

The frontend uses flat fields (not nested `providerConfig`) to minimize migration disruption:

```ts
type Provider = "n8n" | "make";

interface Environment {
  id: string;
  tenantId: string;
  provider: Provider;  // ADD: new field
  name: string;
  type?: string;
  baseUrl: string;           // Keep flat (not nested in providerConfig)
  apiKey?: string;           // Keep flat
  n8nEncryptionKey?: string; // Keep flat (consider renaming to encryptionKey)
  isActive: boolean;
  allowUpload: boolean;
  lastConnected?: string;
  lastBackup?: string;
  workflowCount: number;
  gitRepoUrl?: string;
  gitBranch?: string;
  gitPat?: string;
  createdAt: string;
  updatedAt: string;
}

interface Workflow {
  id: string;
  provider: Provider;  // ADD: new field
  name: string;
  active: boolean;
  nodes: WorkflowNode[];
  connections: Record<string, any>;
  settings: Record<string, any>;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  environment: EnvironmentType;
  // ... rest unchanged
}
```

**Note:** The API client (`api-client.ts`) already transforms snake_case → camelCase. The new `provider` field should be added to this transformation layer. During migration, the backend will return `provider: "n8n"` for all existing records.

### 6.2 API Integration

- Read provider from API responses  
- Preserve provider through state  
- For create flows:
  - send `provider: "n8n"` OR rely on backend default

### 6.3 UI Behavior

No visible changes:

- No provider dropdowns  
- No provider filters  
- No new routes  

Frontend is “provider aware” but not “provider exposed”.

---

## 7. Cross-Cutting Concerns

### 7.1 Logging

Add provider to logs for:

- Deployments
- Executions
- Alerts
- Errors

### 7.2 RBAC

If permissions depend on workflow/environment:

- Ensure provider field is available in authorization context.

### 7.3 Multi-Tenancy

Future tenants may use different providers:

- Provider scoping supports this naturally.

### 7.4 GitHub Integration

GitHub sync is currently tightly coupled to n8n workflows. Clarify:

- **Option A:** GitHub integration is provider-agnostic (workflows from any provider can sync to GitHub)
- **Option B:** GitHub integration is provider-specific (each provider has its own sync mechanism)

**Recommendation:** Make GitHub integration provider-agnostic at the service layer, but allow provider adapters to handle workflow format transformations if needed.

### 7.5 Workflow Analysis

The `workflow_analysis_service` performs complexity analysis on workflows. Consider:

- Whether analysis logic is provider-agnostic (works on any workflow JSON structure)
- Or if each provider needs its own analysis adapter

**Recommendation:** Keep analysis provider-agnostic if possible, but allow provider-specific analysis extensions.

### 7.6 Observability and Alerts

The system uses:
- `notification_channels` and `notification_rules` for alerting infrastructure
- `observability_service` for health checks

Clarify which components are provider-scoped:
- **Provider-scoped:** Health checks, workflow performance metrics (tied to specific provider instances)
- **System-scoped:** Notification channels, rules (may apply across providers)

**Recommendation:** Health checks and workflow metrics are provider-scoped. Notification infrastructure is system-scoped but can filter by provider.

---

## 8. Migration & Rollout

### 8.1 High-Level Sequence

0. **Audit and Planning**
   - Audit all `N8NClient` usages (38 locations identified across 7 files)
   - Create migration checklist with priorities
   - Identify test coverage gaps
   - Plan phased rollout strategy

1. **Data Model Migration**  
   - Add provider columns to all identified tables
   - Add composite indexes for provider-scoped queries
   - Migrate existing data: set `provider = 'n8n'` for all records
   - Add `provider_config` JSONB column to `environments` (if using Option A)
   - Backfill `provider_config` from existing `n8n_*` fields

2. **Backend Abstraction Layer**  
   - Create `Provider` Enum
   - Create `ProviderAdapter` Protocol interface
   - Create `ProviderRegistry` class
   - Implement `N8NProviderAdapter` wrapping existing `N8NClient`

3. **Refactor Service Layer**  
   - Update service methods to load provider from database
   - Replace direct `N8NClient` calls with `ProviderRegistry.get_adapter()`
   - Start with endpoints (higher visibility, easier to test)
   - Then refactor services (business logic layer)
   - Use feature flags for phased rollout

4. **Frontend Update**  
   - Add `Provider` type
   - Update interfaces to include `provider` field
   - Update API client to handle both old and new field formats (backward compatibility)
   - Preserve provider through state management

5. **Regression Validation**  
   - Ensure unchanged UX for n8n-only phase
   - Validate all workflows, deployments, executions still work
   - Test promotion flows, snapshots, credentials
   - Verify observability and alerts functionality

### 8.2 Behavioral Guarantees

After rollout:

- System behaves exactly as n8n-only.  
- All entities tagged with `provider = "n8n"`.  
- System architecturally supports adding Make with minimal changes.  

---

## 9. Definition of Done (Architectural)

The provider abstraction is complete when:

- All tables have a provider column.  
- Backend uses Provider Enum + Registry + Adapter exclusively.  
- No direct n8n calls exist outside the adapter.  
- Frontend carries provider in all relevant types.  
- Logging includes provider.  
- No UX changes are observable.  

This completes the architectural foundation for multi-provider Workflow Ops.

