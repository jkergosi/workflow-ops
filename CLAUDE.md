# N8N Ops Platform

Multi-tenant workflow governance platform for managing n8n workflows across environments (dev, staging, production).

## Testing Requirements (MANDATORY)

**IMPORTANT: Always test changes before telling the user to test them.**

Before reporting that a change is complete or asking the user to test:

1. **Backend changes**: Run `pytest` or relevant test file to verify no regressions
2. **Frontend changes**: Run `npm run build` to catch TypeScript/compilation errors
3. **API changes**: Use `curl` or test the endpoint directly to verify it works
4. **Full-stack changes**: Verify both backend and frontend compile/pass tests

If tests fail, fix the issues before reporting completion. Do not hand off broken code to the user.

## Server Restart Policy (MANDATORY)

**When changes require a server restart, ASK the user to restart:**

### Changes That Require Backend Restart:
- Installing new Python packages (`pip install`)
- Changes to `requirements.txt`
- Changes to `.env` files
- Changes to `app/main.py` router registration
- Database migration changes (though migrations auto-run on start)

### Changes That Require Frontend Restart:
- Installing new npm packages (`npm install`)
- Changes to `vite.config.ts`
- Changes to `package.json` scripts
- Changes to `.env` files

### Changes That DO NOT Require Restart (Hot-Reload):
- Backend: `.py` file changes, route modifications, schema updates
- Frontend: `.tsx`, `.ts`, `.css` file changes, component updates

**Format:** "This change requires a [backend/frontend] restart to take effect. Please restart the [backend/frontend] server when convenient."

## Port Configuration

| Worktree | Frontend | Backend |
|----------|----------|---------|
| main     | 3000     | 4000    |
| f1       | 3001     | 4001    |
| f2       | 3002     | 4002    |
| f3       | 3003     | 4003    |
| f4       | 3004     | 4004    |

Port configuration is in `.env.local` (root) and should not be modified without user approval.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: React + TanStack Query + Zustand + shadcn/ui         │
│  n8n-ops-ui/ (port 3000)                                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API (axios)
┌──────────────────────────▼──────────────────────────────────────┐
│  Backend: FastAPI + Pydantic + httpx                            │
│  n8n-ops-backend/ (port 4000)                                   │
└──────┬─────────────────────┬─────────────────────┬──────────────┘
       │                     │                     │
┌──────▼──────┐    ┌─────────▼─────────┐   ┌──────▼──────┐
│  Supabase   │    │  N8N Instances    │   │   GitHub    │
│  PostgreSQL │    │  REST API         │   │   Repos     │
└─────────────┘    └───────────────────┘   └─────────────┘
```

## Key Features

- **Environments**: Manage multiple N8N instances (dev/staging/prod) with environment classes
- **Workflows**: View, upload, sync, activate/deactivate workflows with action policies
- **Credentials**: View and manage N8N credentials across environments
- **Executions**: Monitor workflow execution history
- **GitHub Sync**: Backup/restore workflows to Git repositories
- **Pipelines**: Define promotion flows between environments
- **Promotions**: Move workflows with gates, approvals, drift detection
- **Drift Detection**: Automated drift monitoring, incidents, and reconciliation
- **Drift Policies**: TTL/SLA-based governance with enterprise controls
- **Drift Reports**: Comprehensive drift reporting and history tracking
- **Drift Retention**: Configurable retention policies for drift data
- **Incident Management**: Lifecycle tracking for drift incidents (open/acknowledged/resolved)
- **Environment Capabilities**: Policy-based action guards per environment class
- **Snapshots**: Git-backed environment state versioning
- **Restore**: Restore workflows from snapshots
- **Deployments**: Track promotion history, scheduling, and rollback
- **Observability**: Health monitoring, alerts, execution analytics
- **Alerts**: Configurable alerting for workflow failures
- **Team Management**: Role-based access (admin, developer, viewer)
- **Billing**: Stripe integration with free/pro/enterprise tiers
- **Support**: Ticket system for user assistance
- **Entitlements**: Plan-based feature access with overrides
- **Admin Portal**: 16 admin pages for system management
- **Real-time Updates**: SSE-based live notifications
- **Canonical Workflows**: Repository-based workflow management with environment synchronization
- **Background Jobs**: Async task execution with progress tracking
- **Live Log Streaming**: SSE-based real-time log streaming for sync/backup/restore operations
- **Health Monitoring**: Automated health checks with heartbeat tracking for environments
- **Service Recovery**: Automatic detection and handling of backend connectivity issues
- **Bulk Operations**: Batch sync, backup, and restore across multiple environments
- **Untracked Workflows**: Detection and management of workflows not in canonical system
- **Workflow Matrix**: Cross-environment workflow status overview
- **Execution Analytics**: Advanced execution metrics and performance insights
- **Credential Health**: Monitoring and tracking of credential status across environments
- **Promotion Validation**: Pre-promotion validation with rollback state tracking

## Dev Mode Authentication

Auth0 is disabled for local development:
- Auto-login as first user in database
- Falls back to dummy dev user if no users exist
- Endpoints: `/api/v1/auth/dev/users`, `/api/v1/auth/dev/login-as/{id}`

## Project Structure

```
n8n-ops/
├── CLAUDE.md                    # This file (overview)
├── .env.local                   # Port configuration
├── n8n-ops-backend/             # FastAPI backend
│   ├── CLAUDE.md                # Backend-specific docs
│   ├── app/
│   │   ├── main.py              # App entry, router registration
│   │   ├── api/endpoints/       # 50+ API routers
│   │   ├── services/            # 44+ business logic services
│   │   ├── schemas/             # 26+ Pydantic model files
│   │   └── core/                # Config, feature gates
│   ├── alembic/                 # Alembic migrations
│   ├── migrations/              # SQL migrations
│   └── tests/                   # 49+ pytest test files
├── n8n-ops-ui/                  # React frontend
│   ├── CLAUDE.md                # Frontend-specific docs
│   └── src/
│       ├── pages/               # 62+ pages (core + support + admin)
│       ├── components/          # UI, workflow, pipeline components
│       ├── hooks/               # Custom React hooks
│       ├── lib/                 # API client, auth, features
│       ├── store/               # Zustand state
│       └── types/               # TypeScript definitions
└── docs/                        # Additional documentation
```

## API Conventions

- **Base URL**: `http://localhost:<BACKEND_PORT>/api/v1`
- **Auth Header**: `Authorization: Bearer <token>`
- **Multi-tenant**: All queries filtered by `tenant_id`
- **Errors**: `{ "detail": "Error message" }`

## Environment Files

| File | Purpose |
|------|---------|
| `.env.local` | Port configuration (root) |
| `n8n-ops-backend/.env` | Backend secrets (Supabase, Stripe, GitHub) |
| `n8n-ops-ui/.env` | Frontend config (`VITE_API_BASE_URL`) |

## Adding New Features

### Backend
1. Create schema in `app/schemas/`
2. Add endpoint in `app/api/endpoints/`
3. Register router in `app/main.py`
4. Add DB methods in `app/services/database.py`
5. Write tests in `tests/`

### Frontend
1. Add API method in `src/lib/api-client.ts`
2. Create page in `src/pages/`
3. Add route in `src/App.tsx`
4. Add nav item in `src/components/AppLayout.tsx`
5. Add types in `src/types/index.ts`

## Common Commands

```bash
# Backend testing
cd n8n-ops-backend && pytest                    # All tests
cd n8n-ops-backend && pytest tests/test_file.py # Specific test

# Frontend testing
cd n8n-ops-ui && npm test                       # Run tests
cd n8n-ops-ui && npm test -- --coverage         # With coverage
cd n8n-ops-ui && npm run build                  # Type check & build
cd n8n-ops-ui && npm run lint                   # Lint check
```

## Resources

- Backend docs: `n8n-ops-backend/CLAUDE.md`
- Frontend docs: `n8n-ops-ui/CLAUDE.md`
- API docs: `http://localhost:4000/docs`
- [FastAPI](https://fastapi.tiangolo.com/) | [N8N API](https://docs.n8n.io/api/) | [Supabase](https://supabase.com/docs) | [TanStack Query](https://tanstack.com/query) | [shadcn/ui](https://ui.shadcn.com/)

---

## Active Instruction Context: Unqork Documentation Crawling

> **When working on Unqork docs.unqork.io crawling diagnostics, use `rnd/rnd.md` as the active instruction file.**

### Scope

The `rnd/rnd.md` file contains specialized guidance for diagnosing and debugging documentation crawling issues specific to `docs.unqork.io`. This includes:

- Debug playbook and practical checklist
- Edge case handling (404 pages, WAF/bot-challenge detection)
- Classification verification (NOT_FOUND, AUTH_REQUIRED, BLOCKED, RATE_LIMITED)
- Incremental crawling and anti-bot hygiene rules
- Output contract recommendations

### Constraints (Diagnostic-Only Mode)

When `rnd.md` is the active context, the following constraints apply:

- **No new URL discovery** — Work only with known/provided URLs
- **No URL guessing** — Do not infer or construct URLs
- **Diagnostic-only mode** — Focus on analyzing and debugging existing crawl results

### Supporting Documents

| Document | Purpose |
|----------|---------|
| `rnd/rnd.md` | Active instruction file — debug playbook and edge cases |
| `rnd/1_extract.md` | Extraction rules and content processing guidelines |
| `rnd/2_reconcile.md` | Reconciliation rules for comparing crawl results |

### Usage

For Unqork crawling diagnostic sessions, reference `rnd/rnd.md` first. The core N8N Ops platform instructions above remain applicable for all other development work.
