# N8N Ops Backend

FastAPI backend for N8N Ops platform.

## Running

### Quick Start Scripts (Windows PowerShell)

```powershell
# Start backend
.\start-backend.ps1

# Stop backend
.\stop-backend.ps1

# Restart backend
.\restart-backend.ps1
```

### Manual Start

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port <BACKEND_PORT>
```

Check port in `../.env.local` (default: 4000 for main worktree).

## API Endpoints

All endpoints prefixed with `/api/v1`.

### Auth (`/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/me` | Get current user info |
| GET | `/status` | Check auth status, onboarding needed |
| PATCH | `/me` | Update user profile |
| POST | `/onboarding` | Complete onboarding |
| GET | `/dev/users` | [DEV] List all users |
| POST | `/dev/login-as/{id}` | [DEV] Login as user |
| POST | `/dev/create-user` | [DEV] Create user + tenant |

### Environments (`/environments`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all environments |
| POST | `/` | Create environment |
| GET | `/{id}` | Get environment details |
| PUT | `/{id}` | Update environment |
| DELETE | `/{id}` | Delete environment |
| POST | `/test-connection` | Test N8N connection |
| POST | `/test-git-connection` | Test GitHub connection |
| GET | `/limits` | Get plan-based limits |
| POST | `/{id}/sync` | Full sync from N8N |
| POST | `/{id}/sync-users` | Sync N8N users only |
| POST | `/{id}/sync-executions` | Sync executions only |
| POST | `/{id}/sync-tags` | Sync tags only |

### Workflows (`/workflows`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List workflows (cached) |
| GET | `/{id}` | Get workflow details |
| PUT | `/{id}` | Update workflow |
| DELETE | `/{id}` | Delete workflow |
| POST | `/upload` | Upload JSON/ZIP files |
| POST | `/{id}/activate` | Activate workflow |
| POST | `/{id}/deactivate` | Deactivate workflow |
| PUT | `/{id}/tags` | Update workflow tags |
| GET | `/{id}/drift` | Check Git drift |
| POST | `/sync-to-github` | Backup to GitHub |
| POST | `/sync-from-github` | Import from GitHub |
| GET | `/download` | Download as ZIP |

### Pipelines (`/pipelines`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List pipelines |
| POST | `/` | Create pipeline |
| GET | `/{id}` | Get pipeline details |
| PATCH | `/{id}` | Update pipeline |
| DELETE | `/{id}` | Delete pipeline |

### Promotions (`/promotions`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List promotions |
| POST | `/initiate` | Start promotion (drift check, gates) |
| GET | `/{id}` | Get promotion details |
| POST | `/{id}/approve` | Approve promotion |
| POST | `/{id}/reject` | Reject promotion |
| POST | `/{id}/execute` | Execute approved promotion |

### Deployments (`/deployments`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List deployments (paginated, filtered) |
| GET | `/{id}` | Get deployment with workflows, snapshots |

### Snapshots (`/snapshots`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List snapshots (filtered by env, type) |
| GET | `/{id}` | Get snapshot details |
| POST | `/{id}/restore` | Restore snapshot |

### Other Endpoints
| Router | Prefix | Description |
|--------|--------|-------------|
| `executions` | `/executions` | Execution history |
| `tags` | `/tags` | Workflow tags |
| `credentials` | `/credentials` | Credential metadata |
| `n8n_users` | `/n8n-users` | N8N instance users |
| `teams` | `/teams` | Team member management |
| `billing` | `/billing` | Stripe subscriptions |
| `tenants` | `/tenants` | Tenant admin |
| `restore` | `/restore` | Restore operations |
| `dev` | `/dev` | Dev mode helpers |
| `observability` | `/observability` | Health metrics, analytics |
| `notifications` | `/notifications` | User notifications |
| `support` | `/support` | Support tickets |
| `sse` | `/sse` | Server-sent events |
| `providers` | `/providers` | Workflow automation providers |

### Admin Endpoints
| Router | Prefix | Description |
|--------|--------|-------------|
| `admin_billing` | `/admin/billing` | System billing management |
| `admin_audit` | `/admin/audit` | Audit log queries |
| `admin_usage` | `/admin/usage` | Usage statistics |
| `admin_providers` | `/admin/providers` | Provider management |
| `admin_support` | `/admin/support` | Support ticket admin |
| `admin_entitlements` | `/admin/entitlements` | Feature entitlements |
| `admin_environment_types` | `/admin/environment-types` | Environment type config |
| `admin_credentials` | `/admin/credentials` | Credential health monitoring |

## Services

| File | Purpose |
|------|---------|
| `database.py` | Supabase client - all DB operations |
| `n8n_client.py` | N8N REST API client (httpx async) |
| `github_service.py` | GitHub sync (PyGithub) |
| `auth_service.py` | JWT verification, user lookup |
| `promotion_service.py` | Promotion flow, snapshots, drift |
| `feature_service.py` | Plan-based feature access |
| `stripe_service.py` | Stripe payments |
| `diff_service.py` | JSON diff for drift detection |
| `sync_status_service.py` | Workflow sync status |
| `workflow_analysis_service.py` | Workflow complexity analysis |
| `observability_service.py` | Execution analytics, health metrics |
| `notification_service.py` | User notification management |
| `audit_service.py` | Audit logging |
| `email_service.py` | Email notifications |
| `support_service.py` | Support ticket handling |
| `entitlements_service.py` | Feature entitlement logic |
| `background_job_service.py` | Async background tasks |
| `sse_pubsub_service.py` | Real-time event publishing |
| `provider_adapter.py` | Multi-provider workflow abstraction |
| `provider_registry.py` | Provider registration system |

## Schemas (Pydantic Models)

| File | Key Models |
|------|------------|
| `environment.py` | `EnvironmentCreate`, `EnvironmentResponse` |
| `workflow.py` | `WorkflowResponse`, `WorkflowUpload` |
| `pipeline.py` | `PipelineStage`, `PipelineResponse` |
| `promotion.py` | `PromotionInitiateRequest`, `PromotionStatus` |
| `deployment.py` | `DeploymentResponse`, `SnapshotResponse` |
| `billing.py` | `SubscriptionResponse`, `CheckoutSession` |
| `team.py` | `TeamMemberResponse`, `UserRole` |
| `tenant.py` | `TenantResponse`, `SubscriptionPlan` |
| `execution.py` | `ExecutionResponse` |
| `tag.py` | `TagResponse` |
| `credential.py` | `CredentialResponse`, `CredentialHealth` |
| `notification.py` | `NotificationResponse`, `NotificationCreate` |
| `support.py` | `SupportTicketCreate`, `SupportTicketResponse` |
| `entitlements.py` | `EntitlementOverride`, `FeatureMatrix` |
| `observability.py` | `HealthMetrics`, `ExecutionAnalytics` |
| `sse.py` | `SSEEvent`, `SSEMessage` |
| `environment_type.py` | `EnvironmentTypeResponse` |
| `provider.py` | `ProviderConfig`, `ProviderResponse` |

## Database Tables

| Table | Purpose |
|-------|---------|
| `tenants` | Multi-tenant orgs (id, name, subscription_tier) |
| `users` | Team members (tenant_id, email, role) |
| `environments` | N8N instances (base_url, api_key, git config) |
| `workflows` | Cached workflow data (n8n_workflow_id, workflow_data JSONB) |
| `executions` | Execution history |
| `tags` | Workflow tags |
| `credentials` | Credential metadata |
| `n8n_users` | N8N instance users |
| `pipelines` | Promotion pipelines (stages JSONB) |
| `promotions` | Promotion records (status, gates, approvals) |
| `deployments` | Deployment tracking (source/target env, status) |
| `snapshots` | Git-backed env snapshots (commit_sha, type) |
| `deployment_workflows` | Per-workflow deployment results |

## Core Patterns

### Multi-Tenancy
```python
# All queries filter by tenant_id
environments = await db_service.get_environments(tenant_id)
```

### Feature Gates
```python
from app.core.feature_gate import require_feature

@router.get("/")
@require_feature("environment_promotion")
async def get_pipelines(...):
    ...
```

### Auth Dependency
```python
from app.services.auth_service import get_current_user

@router.get("/me")
async def get_user(user_info: dict = Depends(get_current_user)):
    user = user_info["user"]
    tenant = user_info["tenant"]
```

### Error Handling
```python
from fastapi import HTTPException, status

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Environment not found"
)
```

## Environment Variables

```env
# N8N
N8N_API_URL=https://your-n8n.com
N8N_API_KEY=xxx

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
SUPABASE_SERVICE_KEY=xxx
DATABASE_URL=postgresql://...

# GitHub
GITHUB_TOKEN=xxx

# Auth0
AUTH0_DOMAIN=xxx
AUTH0_API_AUDIENCE=xxx

# Stripe
STRIPE_SECRET_KEY=sk_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx

# Security
SECRET_KEY=xxx
```

## Adding New Endpoints

1. Create schema in `app/schemas/newfeature.py`
2. Create endpoint in `app/api/endpoints/newfeature.py`
3. Register in `app/main.py`:
   ```python
   from app.api.endpoints import newfeature
   app.include_router(
       newfeature.router,
       prefix=f"{settings.API_V1_PREFIX}/newfeature",
       tags=["newfeature"]
   )
   ```
4. Add DB methods in `app/services/database.py`
