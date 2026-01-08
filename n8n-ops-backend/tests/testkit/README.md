# Testkit Documentation

The testkit provides HTTP-boundary mocking, factories, and golden fixtures for E2E testing in the N8N Ops Backend.

## Overview

The testkit enables:
- **HTTP-boundary mocking**: Mock external API calls (n8n, GitHub, Stripe) at the HTTP layer using `respx`
- **Factory pattern**: Generate consistent test data using factories
- **Golden fixtures**: Canonical JSON responses stored as files
- **Database seeding**: Helper functions to create test database records

## Structure

```
tests/testkit/
├── factories/          # Factory classes for generating test data
│   ├── n8n_factory.py
│   ├── github_factory.py
│   ├── stripe_factory.py
│   └── database_factory.py
├── fixtures/           # Golden JSON files (canonical responses)
│   ├── n8n/
│   ├── github/
│   └── stripe/
└── http_mocks/         # HTTP mock helpers using respx
    ├── n8n_mock.py
    ├── github_mock.py
    └── stripe_mock.py
```

## Usage

### Basic Usage with Factories

```python
from tests.testkit import N8nResponseFactory

# Generate a simple workflow
workflow = N8nResponseFactory.workflow({"id": "test-1", "name": "My Workflow"})

# Generate a complex workflow (10+ nodes)
complex_workflow = N8nResponseFactory.workflow_complex()

# Generate error responses
error_404 = N8nResponseFactory.error_404()
error_rate_limit = N8nResponseFactory.error_rate_limit()
```

### HTTP Mocking

```python
from tests.testkit import N8nHttpMock, N8nResponseFactory

async def test_workflow_promotion(async_client):
    # Create workflows
    workflows = [
        N8nResponseFactory.workflow({"id": "wf-1"}),
        N8nResponseFactory.workflow({"id": "wf-2"})
    ]
    
    # Mock n8n API
    with N8nHttpMock("https://dev.n8n.example.com") as mock:
        mock.mock_get_workflows(workflows)
        mock.mock_create_workflow(workflows[0])
        
        # Make API calls - they will be mocked
        response = await async_client.post("/api/v1/environments/sync")
        assert response.status_code == 200
```

### Error Scenarios

```python
async def test_n8n_timeout(async_client):
    with N8nHttpMock("https://dev.n8n.example.com") as mock:
        # Mock timeout
        mock.mock_timeout("/workflows")
        
        # This will simulate a timeout
        response = await async_client.post("/api/v1/environments/sync")
        assert response.status_code in [500, 503, 504]
```

### Database Seeding

```python
from tests.testkit import DatabaseSeeder

# Create full tenant setup (tenant + 2 envs + pipeline)
setup = DatabaseSeeder.create_full_tenant_setup()
tenant = setup["tenant"]
dev_env = setup["environments"]["dev"]
prod_env = setup["environments"]["prod"]
pipeline = setup["pipeline"]

# Create individual records
user = DatabaseSeeder.user(tenant["id"], role="admin")
workflow = DatabaseSeeder.workflow(tenant["id"], dev_env["id"], "wf-1")
```

### Using Testkit Fixture

```python
async def test_something(testkit):
    # testkit combines all factories
    workflow = testkit.n8n.workflow({"id": "test"})
    event = testkit.stripe.subscription_created()
    setup = testkit.db.create_full_tenant_setup()
```

## Golden Fixtures

Golden fixtures are canonical JSON responses stored in `fixtures/` directory.

### Adding New Fixtures

1. Create JSON file in appropriate subdirectory:
   ```
   tests/testkit/fixtures/n8n/my_new_fixture.json
   ```

2. Add factory method in corresponding factory:
   ```python
   @staticmethod
   def my_new_response():
       return load_fixture("n8n/my_new_fixture.json")
   ```

3. Use in tests:
   ```python
   response = N8nResponseFactory.my_new_response()
   ```

## HTTP Mock Helpers

### N8nHttpMock

Mock n8n API endpoints:

```python
mock = N8nHttpMock("https://dev.n8n.example.com")
with mock:
    mock.mock_get_workflows([...])          # GET /workflows
    mock.mock_get_workflow("wf-1", {...})   # GET /workflows/wf-1
    mock.mock_create_workflow({...})         # POST /workflows
    mock.mock_update_workflow("wf-1", {...}) # PUT /workflows/wf-1
    mock.mock_delete_workflow("wf-1")        # DELETE /workflows/wf-1
    mock.mock_workflow_404("wf-missing")     # 404 error
    mock.mock_rate_limit()                   # 429 error
    mock.mock_server_error()                 # 500 error
    mock.mock_timeout()                      # Timeout exception
```

### GitHubHttpMock

Mock GitHub API endpoints:

```python
mock = GitHubHttpMock()
with mock:
    mock.mock_get_repo("owner", "repo")
    mock.mock_get_commits("owner", "repo")
    mock.mock_get_file_content("owner", "repo", "path/to/file.json")
    mock.mock_404("owner", "repo", "missing/file.json")
    mock.mock_timeout("/repos/owner/repo")
```

### StripeWebhookMock

Mock Stripe webhook events with valid signatures:

```python
from tests.testkit import StripeEventFactory, StripeWebhookMock

event = StripeEventFactory.subscription_updated_downgrade()
payload = json.dumps(event)

webhook_mock = StripeWebhookMock("whsec_test_secret")
headers = webhook_mock.create_webhook_headers(payload)

# Send webhook with valid signature
response = await client.post("/api/v1/billing/stripe-webhook", content=payload, headers=headers)
```

## Best Practices

1. **Use Golden Fixtures**: Store complex responses in JSON files rather than inline
2. **HTTP-Boundary Mocking**: Mock at HTTP layer, not service layer
3. **Reusable Factories**: Create factory methods for common patterns
4. **Error Scenarios**: Test timeouts, rate limits, server errors
5. **Realistic Data**: Use realistic workflow structures with 5-10 nodes
6. **Consistent IDs**: Use predictable IDs in tests ("wf-1", "env-dev", etc.)

## Common Patterns

### Full E2E Flow

```python
async def test_full_promotion_flow(testkit, async_client):
    # 1. Setup: Create database records
    setup = testkit.db.create_full_tenant_setup()
    
    # 2. Mock: Setup HTTP mocks
    workflows = [testkit.n8n.workflow({"id": "wf-1"})]
    with testkit.http.n8n(setup["environments"]["dev"]["n8n_base_url"]) as mock:
        mock.mock_get_workflows(workflows)
        
        # 3. Execute: Make API calls
        response = await async_client.post("/api/v1/promotions", json={...})
        
        # 4. Verify: Check outcomes
        assert response.status_code == 201
```

### Error Scenario Testing

```python
@pytest.mark.parametrize("error_type,mock_method", [
    ("timeout", "mock_timeout"),
    ("rate_limit", "mock_rate_limit"),
    ("server_error", "mock_server_error"),
])
async def test_error_handling(error_type, mock_method, testkit, async_client):
    setup = testkit.db.create_full_tenant_setup()
    
    with testkit.http.n8n(setup["environments"]["dev"]["n8n_base_url"]) as mock:
        getattr(mock, mock_method)("/workflows")
        
        response = await async_client.post("/api/v1/environments/sync")
        assert response.status_code in [500, 503, 504]
```

## Troubleshooting

### Import Errors

If you see import errors, ensure pytest can find the testkit:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/n8n-ops-backend"
pytest tests/e2e/
```

### HTTP Mocks Not Working

Ensure you're using the context manager:
```python
# ✅ Correct
with N8nHttpMock(url) as mock:
    mock.mock_get_workflows([...])
    # make requests here

# ❌ Wrong
mock = N8nHttpMock(url)
mock.mock_get_workflows([...])  # Won't work without context manager
```

### Fixture Not Found

Check the fixture path:
```python
# Paths are relative to tests/testkit/fixtures/
load_fixture("n8n/workflow_simple.json")  # ✅
load_fixture("workflow_simple.json")       # ❌
```

## See Also

- [E2E Test Documentation](../e2e/README.md)
- [GitHub Actions CI](.github/workflows/e2e-tests.yml)
- [Conftest Fixtures](../conftest.py)

