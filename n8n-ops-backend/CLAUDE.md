# N8N Ops Backend

FastAPI backend for N8N Ops platform.

## Running

### Quick Start Scripts (Windows PowerShell)

```powershell
# Start backend (automatically runs migrations first)
.\backend_cycle.ps1 -Action start

# Stop backend
.\backend_cycle.ps1 -Action stop

# Restart backend
.\backend_cycle.ps1 -Action restart
```

### Manual Start with Migrations (Recommended)

```bash
# Automatically runs migrations before starting the app
python scripts/start_with_migrations.py

# With custom port
python scripts/start_with_migrations.py --port 4000

# Production mode (no reload)
python scripts/start_with_migrations.py --no-reload
```

### Manual Start (Without Migrations - Not Recommended)

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port <BACKEND_PORT>
```

**Note:** The startup script (`start_with_migrations.py`) automatically runs `alembic upgrade head` before starting the application. This ensures your database schema is always up-to-date. If migrations fail, the application will not start.

Check port in `../.env.local` (default: 4000 for main worktree).

### Stop Server

```powershell
# Kill backend port
..\scripts\kill-ports.ps1 -Port 4000
```

## Hot-Reload vs Manual Restart

**Start server once, let hot-reload handle changes.**

### ✅ Hot-Reload Handles (No Restart Needed)
- Changes to `.py` files
- Route modifications
- Schema updates
- Most code changes

### ⚠️ Manual Restart Required
- Installing new Python packages
- Changes to `requirements.txt`
- Changes to `.env` files
- Major dependency updates

**Note:** Database migrations run automatically on start via `start_with_migrations.py`.

### Troubleshooting

**Hot-reload not working:**
- Check terminal for uvicorn reload messages
- Verify `--reload` flag is present (included in `start_with_migrations.py`)
- Check for Python syntax errors (reload won't work with syntax errors)
- If still broken: kill port and restart

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

### Drift & Incidents (`/incidents`, `/drift-policies`, `/drift-approvals`, `/drift-reports`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/incidents` | List drift incidents |
| GET | `/incidents/{id}` | Get incident details |
| POST | `/incidents/{id}/acknowledge` | Acknowledge incident |
| POST | `/incidents/{id}/resolve` | Resolve incident |
| GET | `/drift-policies` | Get tenant drift policy |
| PUT | `/drift-policies` | Update drift policy |
| GET | `/drift-policies/templates` | Get policy templates |
| GET | `/drift-approvals` | List pending approvals |
| POST | `/drift-approvals/{id}/approve` | Approve drift change |
| POST | `/drift-approvals/{id}/reject` | Reject drift change |
| GET | `/reports` | List drift check history |
| GET | `/reports/{id}` | Get drift report details |

### Environment Capabilities (`/environments/{id}/capabilities`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/{id}/capabilities` | Get environment action capabilities |

### Workflow Policy (`/workflows/policy`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/policy/{environment_id}` | Get action policy for environment |

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
| `background_jobs` | `/background-jobs` | Background job status |
| `health` | `/health` | Health check endpoint |

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
| `admin_retention` | `/admin/retention` | Drift data retention management |

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
| `drift_detection_service.py` | Automated drift monitoring between environments |
| `drift_incident_service.py` | Drift incident lifecycle management |
| `reconciliation_service.py` | Drift reconciliation and remediation |
| `drift_scheduler.py` | Scheduled drift detection jobs |
| `drift_retention_service.py` | Drift data retention and cleanup |
| `deployment_scheduler.py` | Scheduled deployment execution |
| `environment_action_guard.py` | Policy-based action validation per environment |

## Schemas (Pydantic Models)

| File | Key Models |
|------|------------|
| `environment.py` | `EnvironmentCreate`, `EnvironmentResponse`, `EnvironmentClass` |
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
| `drift_incident.py` | `DriftIncidentCreate`, `DriftIncidentResponse`, `DriftIncidentStatus` |
| `drift_policy.py` | `DriftPolicyCreate`, `DriftPolicyResponse`, `DriftPolicyTemplate` |
| `workflow_policy.py` | `WorkflowPolicyResponse`, `EnvironmentClass`, `ActionPermissions` |

## Database Tables

| Table | Purpose |
|-------|---------|
| `tenants` | Multi-tenant orgs (id, name, subscription_tier) |
| `users` | Team members (tenant_id, email, role) |
| `environments` | N8N instances (base_url, api_key, git config, environment_class) |
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
| `drift_incidents` | Drift incident records (status, severity, acknowledged_at) |
| `drift_policies` | TTL/SLA governance policies per tenant |
| `drift_approvals` | Pending approval requests for drift changes |
| `reconciliation_artifacts` | Artifacts from reconciliation attempts |
| `workflow_archive` | Archived/deleted workflow history |
| `drift_check_history` | Historical drift check results per environment |
| `drift_check_workflow_flags` | Per-workflow status in each drift check |

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
