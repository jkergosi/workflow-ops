# N8N Ops Platform

Multi-tenant workflow governance platform for managing n8n workflows across environments (dev, staging, production).

## Quick Start

### 1. Check Ports
```bash
cat .env.local
```

### 2. Start Backend
```bash
cd n8n-ops-backend
python -m uvicorn app.main:app --reload --port <BACKEND_PORT>
```

### 3. Start Frontend
```bash
cd n8n-ops-ui
npm run dev -- --port <FRONTEND_PORT>
```

## Port Configuration

**Always read `.env.local` for ports. Never use defaults (8000, 5173).**

| Worktree | Frontend | Backend |
|----------|----------|---------|
| main     | 3000     | 4000    |
| f1       | 3001     | 4001    |
| f2       | 3002     | 4002    |
| f3       | 3003     | 4003    |
| f4       | 3004     | 4004    |

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

- **Environments**: Manage multiple N8N instances (dev/staging/prod)
- **Workflows**: View, upload, sync, activate/deactivate workflows
- **Credentials**: View and manage N8N credentials across environments
- **Executions**: Monitor workflow execution history
- **GitHub Sync**: Backup/restore workflows to Git repositories
- **Pipelines**: Define promotion flows between environments
- **Promotions**: Move workflows with gates, approvals, drift detection
- **Snapshots**: Git-backed environment state versioning
- **Restore**: Restore workflows from snapshots
- **Deployments**: Track promotion history and rollback
- **Observability**: Health monitoring, alerts, execution analytics
- **Alerts**: Configurable alerting for workflow failures
- **Team Management**: Role-based access (admin, developer, viewer)
- **Billing**: Stripe integration with free/pro/enterprise tiers
- **Support**: Ticket system for user assistance
- **Entitlements**: Plan-based feature access with overrides
- **Admin Portal**: 15 admin pages for system management
- **Real-time Updates**: SSE-based live notifications

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
│   │   ├── api/endpoints/       # 29 API routers
│   │   ├── services/            # 21 business logic services
│   │   ├── schemas/             # 18 Pydantic model files
│   │   └── core/                # Config, feature gates
│   ├── migrations/              # SQL migrations
│   └── tests/                   # 30 pytest test files
├── n8n-ops-ui/                  # React frontend
│   ├── CLAUDE.md                # Frontend-specific docs
│   └── src/
│       ├── pages/               # 23 pages + 15 admin pages
│       ├── components/          # UI, workflow, pipeline components
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

### Frontend
1. Add API method in `src/lib/api-client.ts`
2. Create page in `src/pages/`
3. Add route in `src/App.tsx`
4. Add nav item in `src/components/AppLayout.tsx`

## Common Commands

```bash
# Backend
cd n8n-ops-backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 4000

# Frontend
cd n8n-ops-ui
npm install
npm run dev -- --port 3000
npm run build
npm run lint

# Testing
cd n8n-ops-backend && pytest                    # Backend tests
cd n8n-ops-ui && npm test                       # Frontend tests
cd n8n-ops-ui && npm test -- --coverage         # With coverage
```

## Resources

- Backend docs: `n8n-ops-backend/CLAUDE.md`
- Frontend docs: `n8n-ops-ui/CLAUDE.md`
- API docs: `http://localhost:4000/docs`
- [FastAPI](https://fastapi.tiangolo.com/) | [N8N API](https://docs.n8n.io/api/) | [Supabase](https://supabase.com/docs) | [TanStack Query](https://tanstack.com/query) | [shadcn/ui](https://ui.shadcn.com/)
