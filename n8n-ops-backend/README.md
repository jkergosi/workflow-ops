# N8N Ops Backend

FastAPI backend for N8N Ops - Multi-tenant n8n governance platform.

## Features

- **Environment Management**: Manage dev, staging, and production n8n environments
- **Workflow Management**: Fetch workflows directly from N8N API
- **Workflow Upload**: Upload workflow JSON files or ZIP archives to N8N
- **GitHub Integration**: Sync workflows to/from GitHub repositories
- **Workflow Snapshots**: Version control for workflows
- **Multi-tenant**: Support for multiple organizations

## Tech Stack

- **FastAPI**: Modern Python web framework
- **Supabase**: PostgreSQL database with real-time capabilities
- **N8N API**: Direct integration with n8n instances
- **GitHub API**: Workflow version control

## Setup

### 1. Install Dependencies

```bash
cd n8n-ops-backend
pip install -r requirements.txt
```

### 2. Configure Supabase

1. Go to [Supabase](https://supabase.com) and create a new project
2. Once the project is created, go to **SQL Editor**
3. Copy the contents of `database_schema.sql` and run it in the SQL Editor
4. Go to **Settings > API** to get your:
   - **Project URL** (SUPABASE_URL)
   - **anon/public key** (SUPABASE_KEY)
   - **service_role key** (SUPABASE_SERVICE_KEY)

### 3. Create .env File

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Update the following values in `.env`:

```env
# N8N Configuration (already configured)
N8N_API_URL=https://ns8i839t.rpcld.net
N8N_API_KEY=123

# Supabase Configuration (update these)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# Database (update this)
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.your-project.supabase.co:5432/postgres

# GitHub Configuration (optional, for workflow sync)
GITHUB_TOKEN=your-github-token
GITHUB_REPO_OWNER=your-org
GITHUB_REPO_NAME=your-repo
GITHUB_BRANCH=main

# Security (generate a secure key)
SECRET_KEY=your-secret-key-here-change-in-production
```

To generate a secure SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Insert Test Tenant

After setting up Supabase, insert a test tenant in the SQL Editor:

```sql
-- Insert test tenant
INSERT INTO tenants (id, name, email, subscription_tier)
VALUES ('00000000-0000-0000-0000-000000000000', 'Test Organization', 'test@example.com', 'pro');

-- Insert dev environment
INSERT INTO environments (tenant_id, name, type, base_url, api_key)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'Development',
    'dev',
    'https://ns8i839t.rpcld.net',
    '123'
);
```

### 5. Run Database Migrations

Before starting the server, ensure your database schema is up-to-date:

```bash
# Run migrations manually
alembic upgrade head

# Or use the startup script (recommended - runs migrations automatically)
python scripts/start_with_migrations.py
```

### 6. Run the Server

```bash
# Recommended: Automatically runs migrations before starting
python scripts/start_with_migrations.py

# Or manually (migrations must be run separately)
uvicorn app.main:app --reload --port 8000

# Or using Python
python -m uvicorn app.main:app --reload --port 8000
```

**Note:** The `start_with_migrations.py` script automatically runs `alembic upgrade head` before starting the application. This ensures your database schema is always up-to-date. If migrations fail, the application will not start.

The API will be available at:
- **API**: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Environments

- `GET /api/v1/environments` - List all environments
- `GET /api/v1/environments/{id}` - Get environment by ID
- `POST /api/v1/environments` - Create new environment
- `PATCH /api/v1/environments/{id}` - Update environment
- `DELETE /api/v1/environments/{id}` - Delete environment
- `POST /api/v1/environments/test-connection` - Test N8N connection
- `POST /api/v1/environments/{id}/update-connection-status` - Update last connected timestamp

### Workflows

- `GET /api/v1/workflows?environment=dev` - Get workflows from N8N
- `GET /api/v1/workflows/{id}?environment=dev` - Get workflow by ID
- `POST /api/v1/workflows/upload?environment=dev` - Upload workflow files (.json or .zip)
- `POST /api/v1/workflows/{id}/activate?environment=dev` - Activate workflow
- `POST /api/v1/workflows/{id}/deactivate?environment=dev` - Deactivate workflow
- `POST /api/v1/workflows/sync-from-github?environment=dev` - Sync workflows from GitHub

## Project Structure

```
n8n-ops-backend/
├── app/
│   ├── api/
│   │   └── endpoints/
│   │       ├── environments.py  # Environment CRUD
│   │       └── workflows.py     # Workflow management
│   ├── core/
│   │   └── config.py           # Configuration
│   ├── schemas/
│   │   ├── environment.py      # Pydantic models for environments
│   │   └── workflow.py         # Pydantic models for workflows
│   ├── services/
│   │   ├── database.py         # Supabase database service
│   │   ├── github_service.py   # GitHub integration
│   │   └── n8n_client.py       # N8N API client
│   └── main.py                 # FastAPI application
├── database_schema.sql         # Supabase schema
├── requirements.txt
├── .env.example
└── README.md
```

## Testing

### E2E Tests

Comprehensive end-to-end tests for critical MVP flows. See [`tests/e2e/README.md`](tests/e2e/README.md) for full documentation.

#### Running E2E Tests

```bash
cd n8n-ops-backend

# All E2E tests
pytest tests/e2e/ -v

# Specific flow
pytest tests/e2e/test_promotion_e2e.py -v

# With coverage
pytest tests/e2e/ --cov=app --cov-report=html
```

#### E2E Test Coverage

✅ **5 Critical Flows Covered**:
1. **Promotion Flow**: Pipeline creation → workflow promotion → verification
2. **Drift Detection**: Detect drift → incident lifecycle → reconciliation
3. **Canonical Onboarding**: Preflight → inventory → workflow linking
4. **Downgrade Flow**: Stripe webhook → over-limit detection → enforcement
5. **Impersonation**: Platform admin impersonation → audit → security checks

**Mock Strategy**: All external APIs (n8n, GitHub, Stripe) are mocked at HTTP boundary using `respx`. No real external dependencies required.

**Testkit**: Reusable factories and golden JSON fixtures in [`tests/testkit/`](tests/testkit/README.md)

### Unit & Integration Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_promotion_service.py -v

# With coverage report
pytest --cov=app --cov-report=html
```

### API Testing

#### Test N8N Connection

```bash
curl -X POST "http://localhost:8000/api/v1/environments/test-connection" \
  -H "Content-Type: application/json" \
  -d '{"base_url": "https://ns8i839t.rpcld.net", "api_key": "123"}'
```

#### Get Workflows

```bash
curl "http://localhost:8000/api/v1/workflows?environment=dev"
```

#### Upload Workflow

```bash
curl -X POST "http://localhost:8000/api/v1/workflows/upload?environment=dev" \
  -F "files=@workflow.json"
```

## MVP Pipeline Model

### Single-Hop Semantics

In the MVP release, pipelines follow a **single-hop model**. This means each pipeline connects exactly **two environments**: a source and a target.

**Key Constraints:**
- Each pipeline must have exactly **2 environments** (source → target)
- Each pipeline contains exactly **1 stage** (the promotion step between environments)
- Multi-stage pipelines (e.g., dev → staging → prod in a single pipeline) are **not supported**

**Why Single-Hop?**

Multi-stage pipelines add complexity that isn't necessary for MVP:
- Simpler mental model for users
- Clearer audit trail (each promotion is a discrete action)
- Easier to debug promotion failures
- More flexible composition (users can create custom paths by chaining single-hop pipelines)

**Example Valid Pipelines:**
```
Pipeline A: Development → Staging
Pipeline B: Staging → Production
```

**Example Invalid Pipeline (Rejected):**
```
Pipeline C: Development → Staging → Production  ❌
```

If you attempt to create a pipeline with more than 2 environments, the API will return:
```json
{
  "detail": "Multi-stage pipelines are not supported in MVP. Create separate pipelines for each hop."
}
```

### Creating a Pipeline

To promote workflows through multiple environments, create separate pipelines for each hop:

1. Create `dev-to-staging` pipeline (Development → Staging)
2. Create `staging-to-prod` pipeline (Staging → Production)
3. Promote workflow through each pipeline sequentially

This approach provides full traceability and allows different approval workflows at each stage.

## Troubleshooting

### Corrupted Python Packages

If you see warnings like:
```
WARNING: Ignoring invalid distribution ~angchain (F:\Python312\Lib\site-packages)
WARNING: Ignoring invalid distribution ~penai (F:\Python312\Lib\site-packages)
```

These indicate corrupted package installations. We provide automated fix scripts:

**Quick Fix (Python)**:
```bash
python fix_corrupted_packages.py
```

**Quick Fix (PowerShell)**:
```powershell
.\fix_corrupted_packages.ps1
```

For detailed information, see [FIX_CORRUPTED_PACKAGES_README.md](FIX_CORRUPTED_PACKAGES_README.md)

### Virtual Environment Recommended

To avoid future issues, use a virtual environment:
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

## Next Steps

1. Set up Supabase project and apply schema
2. Update .env with your Supabase credentials
3. Insert test tenant and environment data
4. Run the backend server
5. Test the endpoints using Swagger docs at http://localhost:8000/docs
6. Update the frontend to use the real API
