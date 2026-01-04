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

## Server and Port Rules (MANDATORY)

**Ask before restarting servers:**
- If a change requires restarting the backend or frontend server, **ASK THE USER FIRST**
- Do not restart servers without explicit permission
- Explain why the restart is needed before asking

**NEVER change ports without permission:**
- Port configuration in `.env.local` is sacred - **NEVER modify without asking**
- Do not change `VITE_API_BASE_URL`, `BACKEND_PORT`, `FRONTEND_PORT`, or any port settings
- If you believe a port change is needed, explain why and get explicit approval first

## Quick Start

### 1. Check Ports
```bash
cat .env.local
```

### 2. Start Backend
```bash
cd n8n-ops-backend
python scripts/start_with_migrations.py
```

### 3. Start Frontend
```bash
cd n8n-ops-ui
npm run dev
```

### Stop Servers
```powershell
# Kill both ports 3000 and 4000
.\scripts\kill-ports.ps1

# Kill specific port
.\scripts\kill-ports.ps1 -Port 3000
```

## Hot-Reload vs Manual Restart

**Start servers once, let hot-reload handle changes.**

### ✅ Hot-Reload Handles (No Restart Needed)

| Frontend (Vite) | Backend (uvicorn --reload) |
|-----------------|---------------------------|
| `.tsx`, `.ts`, `.css` changes | `.py` file changes |
| Component updates | Route modifications |
| State management changes | Schema updates |

### ⚠️ Manual Restart Required

| Frontend | Backend |
|----------|---------|
| New npm packages | New Python packages |
| `vite.config.ts` changes | `requirements.txt` changes |
| `.env` file changes | `.env` file changes |
| `package.json` script changes | Database migrations (auto on start) |

### Troubleshooting

**Port already in use:** Run `.\scripts\kill-ports.ps1`

**Hot-reload not working:**
- Frontend: Hard refresh (Ctrl+Shift+R), check browser console
- Backend: Check terminal for reload messages, verify no syntax errors
- If still broken: `.\scripts\kill-ports.ps1` then restart

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
│   │   ├── api/endpoints/       # 38 API routers
│   │   ├── services/            # 28 business logic services
│   │   ├── schemas/             # 21 Pydantic model files
│   │   └── core/                # Config, feature gates
│   ├── alembic/                 # Alembic migrations
│   ├── migrations/              # SQL migrations
│   └── tests/                   # 35 pytest test files
├── n8n-ops-ui/                  # React frontend
│   ├── CLAUDE.md                # Frontend-specific docs
│   └── src/
│       ├── pages/               # 29 pages + 4 support + 16 admin pages
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

### Frontend
1. Add API method in `src/lib/api-client.ts`
2. Create page in `src/pages/`
3. Add route in `src/App.tsx`
4. Add nav item in `src/components/AppLayout.tsx`

## Common Commands

```bash
# Backend (with port enforcement & migrations)
cd n8n-ops-backend
pip install -r requirements.txt
python scripts/start_with_migrations.py

# Frontend (with port enforcement)
cd n8n-ops-ui
npm install
npm run dev
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
