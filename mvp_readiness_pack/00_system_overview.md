# 00 - System Overview

## Repository Structure

```
n8n-ops-trees/main/
├── n8n-ops-backend/          # FastAPI backend (Python 3.11+)
│   ├── app/
│   │   ├── main.py           # Application entry point, router registration
│   │   ├── api/endpoints/    # 51 endpoint modules (~327 routes)
│   │   ├── core/             # Config, entitlements, tenancy, provider enums
│   │   ├── schemas/          # Pydantic models (27 modules)
│   │   ├── services/         # Business logic (65 services + adapters)
│   │   └── seed/             # Database seed scripts
│   ├── alembic/              # Database migrations
│   │   └── versions/         # 61 migration files
│   ├── tests/                # 63 test files
│   └── scripts/              # Utility scripts
├── n8n-ops-ui/               # React frontend (TypeScript)
│   ├── src/
│   │   ├── main.tsx          # Frontend entry point
│   │   ├── App.tsx           # Root component with routing
│   │   ├── pages/            # ~70 page components
│   │   ├── components/       # Reusable UI components
│   │   ├── hooks/            # Custom React hooks
│   │   ├── lib/              # Utilities (API client, auth, features)
│   │   └── types/            # TypeScript types
│   └── tests/                # E2E tests (Playwright)
├── jk_docs/                  # Business docs (pricing, branding, strategy)
├── PRD.md                    # Original PRD
├── PRD_cursor.md             # Extended PRD with implementation status
└── scripts/                  # PowerShell port management scripts
```

---

## Technology Stack

### Backend
- **Framework**: FastAPI 
- **Language**: Python 3.11+
- **Database**: Supabase (PostgreSQL with row-level security)
- **ORM**: Direct Supabase client (no SQLAlchemy)
- **Migrations**: Alembic
- **Auth**: Supabase Auth + custom JWT validation
- **Payments**: Stripe
- **Git**: PyGithub for repository operations
- **Real-time**: Server-Sent Events (SSE)

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **State Management**: 
  - TanStack Query (server state)
  - Zustand (client state, see `src/store/use-app-store.ts`)
- **UI**: shadcn/ui + Tailwind CSS
- **Routing**: React Router
- **HTTP**: Axios with retry logic (`lib/api-client.ts`)
- **Visualization**: React Flow (workflow graphs)

### External Integrations
- **Supabase**: Auth, PostgreSQL, RLS
- **Stripe**: Subscriptions, webhooks (`billing.router` at `/api/v1/billing`)
- **GitHub**: Workflow backups, webhooks (`github_webhooks.router`)
- **n8n API**: Workflow sync via `N8NProviderAdapter`
- **SMTP**: Email notifications (configured in `config.py`)

---

## Backend Entry Points

### Main Application
**File**: `n8n-ops-backend/app/main.py`

- **App Initialization**: Lines 16-20 (FastAPI app with OpenAPI)
- **Middleware**: 
  - CORS (lines 84-91)
  - Impersonation audit middleware (lines 22-82) - logs all write actions during impersonation
- **Router Registration**: Lines 94-386 (43 router includes)
- **Global Exception Handler**: Lines 521-574 (emits `system.error` events)

### Startup Jobs (line 403-486)
Executed on `@app.on_event("startup")`:
1. Cleanup stale background jobs (max 24hr runtime)
2. Start deployment scheduler (`deployment_scheduler.start_scheduler()`)
3. Start drift detection scheduler (`drift_scheduler.start_all_drift_schedulers()`)
4. Start canonical sync schedulers (`canonical_sync_scheduler.start_canonical_sync_schedulers()`)
5. Start health check scheduler (`health_check_scheduler.start_health_check_scheduler()`)
6. Start rollup scheduler (`rollup_scheduler.start_rollup_scheduler()`)
7. Start retention scheduler (`retention_job.start_retention_scheduler()`)
8. Cleanup stale deployments (>1hr running, mark as failed)

### Shutdown Jobs (line 488-518)
Gracefully stops all schedulers.

### SSE Endpoints
**File**: `n8n-ops-backend/app/api/endpoints/sse.py`

- `/api/v1/sse/stream/{job_id}` - Background job progress
- `/api/v1/sse/deployments/{deployment_id}` - Deployment status
- `/api/v1/sse/counts/{tenant_id}` - Real-time count updates

---

## Frontend Entry Points

### Main Entry
**File**: `n8n-ops-ui/src/main.tsx`
- React 18 StrictMode wrapper
- Renders `<App />` component

### App Component
**File**: `n8n-ops-ui/src/App.tsx`
Primary routing and layout configuration:
- React Router with 70+ routes
- AuthProvider wrapping
- ThemeProvider (light/dark mode)
- RouteTracker (analytics)
- FeatureGate components
- Layout structure with AppLayout component

### Key Routes
- `/` - Dashboard
- `/environments` - Environment management
- `/workflows` - Workflow catalog
- `/canonical` - Canonical workflow system
- `/promotions` - Promotion pipeline
- `/deployments` - Deployment history
- `/drift` - Drift dashboard
- `/incidents` - Incident management
- `/observability` - Observability dashboard
- `/executions` - Execution analytics
- `/billing` - Subscription management
- `/platform/*` - Platform admin console
- `/admin/*` - Admin tools

---

## Core Subsystems

### 1. Multi-Provider Architecture
**Status**: n8n only (Make.com NOT implemented)

**Files**:
- `app/core/provider.py` - `Provider` enum (N8N, MAKE)
- `app/services/provider_registry.py` - `ProviderRegistry` class
- `app/services/adapters/n8n_adapter.py` - `N8NProviderAdapter` (only adapter)

**Design**:
- Provider enum defines `DEFAULT_PROVIDER = Provider.N8N`
- Registry pattern for dynamic adapter loading
- All workflow/credential operations go through adapter interface
- Make.com adapter stub exists but not implemented

### 2. Multi-Tenancy
**Files**:
- `app/core/tenant_isolation.py` - Isolation verification scanner
- `app/services/auth_service.py` - `get_current_user()` extracts tenant_id
- `app/services/database.py` - All queries filtered by tenant_id

**Pattern**: 
- User context contains `{"user": {...}, "tenant": {...}}`
- Tenant ID extracted from authenticated user (never from request params)
- RLS enforced at DB level + application level

### 3. Entitlements System
**Files**:
- `app/core/entitlements_gate.py` - Decorators (`require_entitlement()`)
- `app/core/feature_gate.py` - Feature flag logic
- `app/services/entitlements_service.py` - Resolution service

**Types**:
- **Flags**: Boolean features (e.g., `snapshots_enabled`)
- **Limits**: Numeric constraints (e.g., `environment_limits`)

### 4. Impersonation System
**Files**:
- `app/core/platform_admin.py` - Platform admin guards
- `app/api/endpoints/platform_impersonation.py` - Session management
- `app/services/auth_service.py` - Token prefix detection

**Mechanism**:
- Platform admins can impersonate users
- Impersonation token has special prefix
- Dual user context: `actor_user` (admin) + `user` (target)
- All write actions logged with dual attribution

### 5. Canonical Workflow System
**Files**:
- `app/services/canonical_workflow_service.py`
- `app/services/canonical_onboarding_service.py`
- `app/services/canonical_env_sync_service.py`
- `app/services/canonical_repo_sync_service.py`

**Tables**:
- `canonical_workflows` - Git-backed source of truth
- `workflow_env_map` - Junction table (workflow ↔ environment)
- `workflow_git_state` - Git sync state

### 6. Promotions & Deployments
**Files**:
- `app/services/promotion_service.py` - Core promotion logic
- `app/services/promotion_validation_service.py` - Pre-flight checks
- `app/services/diff_service.py` - Diff computation
- `app/services/deployment_scheduler.py` - Scheduled deployments

**State Machine**: PENDING → RUNNING → COMPLETED/FAILED

### 7. Drift Detection
**Files**:
- `app/services/drift_detection_service.py` - Detection logic
- `app/services/drift_incident_service.py` - Incident lifecycle
- `app/services/drift_scheduler.py` - Scheduled checks

**Lifecycle**: detected → acknowledged → stabilized → reconciled → closed

### 8. Observability
**Files**:
- `app/services/observability_service.py` - KPIs, sparklines, error intelligence
- `app/services/rollup_scheduler.py` - Materialized view refresh
- `app/services/health_check_scheduler.py` - Environment health polling

### 9. Background Jobs
**Files**:
- `app/services/background_job_service.py` - Job management
- `app/services/background_jobs/retention_job.py` - Data retention enforcement

**Types**: sync, promotion, deployment, onboarding, retention

### 10. Billing & Subscriptions
**Files**:
- `app/api/endpoints/billing.py` - Stripe integration
- `app/services/stripe_service.py` - Stripe SDK wrapper
- `app/services/downgrade_service.py` - Downgrade handling

**Plans**: Free, Pro, Agency, Enterprise (per provider)

---

## External Integration Points

### Supabase
- **Auth**: JWT validation, user management
- **Database**: PostgreSQL with RLS
- **Client**: `db_service.client` (global singleton in `database.py`)

### Stripe
- **Webhooks**: `/api/v1/billing/stripe-webhook`
- **Checkout**: Create sessions via `stripe_service`
- **Customer Portal**: Redirect to Stripe portal
- **Events**: `customer.subscription.updated`, `customer.subscription.deleted`

### GitHub
- **Operations**: Workflow backup/restore via PyGithub
- **Webhooks**: `/api/v1/webhooks/github` (signature validation)
- **Storage**: Workflows stored as JSON files in Git

### n8n API
- **Adapter**: `N8NProviderAdapter` in `services/adapters/n8n_adapter.py`
- **Operations**: 
  - Workflow CRUD
  - Credential metadata (secrets not exposed)
  - Execution retrieval
  - Tag management
  - User listing

### SMTP
- **Service**: `email_service.py`
- **Usage**: Team invitations, notifications
- **Config**: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER` in `config.py`

---

## Configuration

**Backend Config**: `n8n-ops-backend/app/core/config.py`
- Supabase credentials
- Stripe keys
- GitHub token
- SMTP settings
- Retention policies
- Feature flags

**Frontend Config**: `n8n-ops-ui/src/lib/supabase.ts`, `lib/api.ts`
- API base URL (`VITE_API_BASE_URL`)
- Supabase URL/key (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`)

---

## Database Migration System

**Tool**: Alembic
**Location**: `n8n-ops-backend/alembic/versions/`
**Count**: 61 migration files
**Helper**: `scripts/create_migration.py` - Creates new migrations with SQL

**Key Migrations**:
- Canonical workflow tables
- Drift incident lifecycle
- Platform impersonation sessions
- Provider architecture
- Execution analytics
- Performance indexes

---

## Testing Infrastructure

### Backend Tests
**Location**: `n8n-ops-backend/tests/`
**Count**: 63 test files
**Runner**: pytest
**Coverage**: Promotions, drift, canonical, security, billing, observability

### Frontend Tests
**Location**: `n8n-ops-ui/tests/`
**Runner**: Playwright (E2E)
**Coverage**: Component tests, page tests, E2E workflows

### Security Tests
**Location**: `n8n-ops-backend/tests/security/`
- `test_tenant_isolation.py` - Cross-tenant leakage tests
- `test_impersonation_audit.py` - Audit trail verification

---

## Known Limitations

1. **Make.com Provider**: Enum exists, adapter NOT implemented
2. **SSO/SCIM**: Feature flags exist, no actual integration
3. **Secret Vault**: Feature flag exists, no vault service
4. **Credential Remapping**: Admin matrix exists, no promotion-time remapping
5. **Scheduled Backups**: Feature flag exists, no backup scheduler service
6. **White-label**: Feature flags exist, no UI customization

See [PRD_cursor.md](../PRD_cursor.md) lines 16-28 for complete list.

---

## Performance Considerations

1. **Sparkline Optimization**: Single-query aggregation instead of N queries (90%+ improvement)
2. **Materialized Views**: Pre-computed rollups for execution analytics
3. **Indexes**: Performance indexes on high-traffic tables
4. **Batch Processing**: 25-30 workflow batches during sync
5. **SSE**: Real-time updates reduce polling overhead

---

## References

- [PRD.md](../PRD.md) - Original product requirements
- [PRD_cursor.md](../PRD_cursor.md) - Extended PRD with implementation status
- [n8n-ops-backend/README.md](../n8n-ops-backend/README.md) - Backend setup
- [n8n-ops-ui/README.md](../n8n-ops-ui/README.md) - Frontend setup

