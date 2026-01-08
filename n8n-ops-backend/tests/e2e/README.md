# E2E Testing Guide

End-to-end tests for critical MVP flows in the N8N Ops Backend.

## Overview

E2E tests cover 5 critical flows:
1. **Promotion Flow**: Create pipeline → promote workflows → verify
2. **Drift Detection**: Detect drift → create incident → reconcile
3. **Canonical Onboarding**: Preflight → inventory → link workflows
4. **Downgrade Flow**: Stripe webhook → over-limit detection → enforcement
5. **Impersonation**: Start session → perform actions → audit → end session

## Running Tests Locally

### All E2E Tests

```bash
cd n8n-ops-backend
pytest tests/e2e/ -v
```

### Specific Flow

```bash
# Promotion flow
pytest tests/e2e/test_promotion_e2e.py -v

# Drift detection
pytest tests/e2e/test_drift_e2e.py -v

# Canonical onboarding
pytest tests/e2e/test_canonical_e2e.py -v

# Downgrade flow
pytest tests/e2e/test_downgrade_e2e.py -v

# Impersonation
pytest tests/e2e/test_impersonation_e2e.py -v
```

### With Coverage

```bash
pytest tests/e2e/ --cov=app --cov-report=html
```

### Specific Test Case

```bash
pytest tests/e2e/test_promotion_e2e.py::TestPromotionFlowE2E::test_full_promotion_happy_path -v
```

## Mock Strategy

All external APIs are mocked at HTTP boundary using `respx`:

- **n8n API**: No real n8n instances contacted
- **GitHub API**: No real GitHub API calls
- **Stripe API**: No real Stripe webhooks or API calls

Tests use golden JSON fixtures from `tests/testkit/fixtures/` for stable, repeatable data.

## Test Structure

### Flow 1: Promotion E2E

**File**: `test_promotion_e2e.py`

**Tests**:
- Happy path: Full promotion from creation to completion
- n8n timeout handling
- n8n 404 errors (missing workflows)
- n8n rate limiting (429)
- Pre-flight validation
- Rollback on partial failure
- Snapshot integrity

**Mocks**:
- n8n API (workflows list, create, update)
- Database records (tenant, environments, pipelines)

### Flow 2: Drift Detection E2E

**File**: `test_drift_e2e.py`

**Tests**:
- Drift detection creates incident
- Complete incident lifecycle (detect → acknowledge → stabilize → reconcile → close)
- TTL enforcement blocks promotions
- n8n unavailable during drift check
- Malformed drift snapshot handling

**Mocks**:
- n8n API with drifted workflows
- Drift policies and TTL settings

### Flow 3: Canonical Onboarding E2E

**File**: `test_canonical_e2e.py`

**Tests**:
- Complete onboarding flow (preflight → inventory → completion)
- Matrix view generation
- Link untracked workflow
- GitHub timeout during sync
- Git merge conflict handling
- Canonical ID collision

**Mocks**:
- n8n API (workflows in anchor environment)
- GitHub API (repo, commits, file content)

### Flow 4: Downgrade E2E

**File**: `test_downgrade_e2e.py`

**Tests**:
- Complete downgrade flow (Stripe webhook → over-limit → grace period → enforcement)
- Grace period tracking
- Resource selection strategy
- Invalid Stripe signature
- Malformed Stripe event
- Unknown plan name

**Mocks**:
- Stripe webhooks with valid signatures
- Subscription downgrade events

### Flow 5: Impersonation E2E

**File**: `test_impersonation_e2e.py`

**Tests**:
- Complete impersonation flow (start → actions → end)
- Write operations audited with dual attribution
- Tenant isolation during impersonation
- Admin-to-admin blocking (403)
- Expired token rejection
- Invalid token rejection
- Self-impersonation blocking
- Audit log completeness
- Blocked attempts audited

**Mocks**:
- Platform admin authentication
- Target users and sessions

## CI Integration

GitHub Actions runs the same commands as local:

```yaml
- name: Run E2E tests
  run: |
    cd n8n-ops-backend
    pytest tests/e2e/ -v --tb=short --maxfail=5 --timeout=60
  env:
    N8N_API_KEY: fake-key-for-tests
    GITHUB_TOKEN: fake-token-for-tests
    STRIPE_WEBHOOK_SECRET: whsec_test_secret
```

See `.github/workflows/e2e-tests.yml` for full CI configuration.

**No external credentials required** - all tests use mocks.

## Error Scenarios Covered

### HTTP Errors
- **Timeouts**: Simulate slow/unresponsive APIs
- **429 Rate Limits**: Test backoff/retry behavior
- **500 Server Errors**: Handle transient failures
- **404 Not Found**: Missing resources

### Data Errors
- **Malformed JSON**: Invalid response payloads
- **Missing Fields**: Incomplete data
- **Unknown Values**: Unrecognized plan names, statuses

### Security Errors
- **Invalid Signatures**: Stripe webhook verification
- **Expired Tokens**: Impersonation token expiry
- **Permission Denied**: Admin-to-admin impersonation block

## Writing New E2E Tests

### 1. Choose Test File

Create or add to existing E2E test file in `tests/e2e/`:
- `test_promotion_e2e.py`
- `test_drift_e2e.py`
- `test_canonical_e2e.py`
- `test_downgrade_e2e.py`
- `test_impersonation_e2e.py`

### 2. Use Test Structure

```python
import pytest
from tests.testkit import N8nHttpMock, N8nResponseFactory, DatabaseSeeder

pytestmark = pytest.mark.asyncio

class TestMyFlowE2E:
    """E2E tests for my flow."""
    
    async def test_happy_path(self, async_client, testkit):
        # 1. Setup: Create database records
        setup = testkit.db.create_full_tenant_setup()
        
        # 2. Mock: Setup HTTP mocks
        with testkit.http.n8n(setup["environments"]["dev"]["n8n_base_url"]) as mock:
            mock.mock_get_workflows([testkit.n8n.workflow()])
            
            # 3. Execute: Make API calls
            response = await async_client.post("/api/v1/my-endpoint", json={...})
            
            # 4. Verify: Check outcomes
            assert response.status_code == 200
    
    async def test_error_scenario(self, async_client, testkit):
        # Test error handling
        pass
```

### 3. Add Golden Fixtures

For new API responses, add golden fixture:

```bash
# Add fixture file
echo '{...}' > tests/testkit/fixtures/n8n/my_new_response.json

# Add factory method in testkit/factories/n8n_factory.py
@staticmethod
def my_new_response():
    return load_fixture("n8n/my_new_response.json")
```

### 4. Test Error Scenarios

Always include error scenario tests:

```python
async def test_timeout_handling(self, async_client, testkit):
    with testkit.http.n8n("https://dev.n8n.example.com") as mock:
        mock.mock_timeout("/workflows")
        
        response = await async_client.post("/api/v1/environments/sync")
        assert response.status_code in [500, 503, 504]
```

## Debugging Tips

### Verbose Output

```bash
pytest tests/e2e/ -vv --tb=long
```

### Show Print Statements

```bash
pytest tests/e2e/ -s
```

### Run Single Test with Debugging

```bash
pytest tests/e2e/test_promotion_e2e.py::TestPromotionFlowE2E::test_full_promotion_happy_path -vv --pdb
```

### Check HTTP Mock Calls

Add logging to see what HTTP calls were made:

```python
with N8nHttpMock(url) as mock:
    mock.mock_get_workflows([...])
    
    # Make requests
    response = await async_client.post(...)
    
    # Check mock calls
    print(mock.router.calls)
```

## Common Issues

### Import Errors

Set PYTHONPATH:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/n8n-ops-backend"
```

### Tests Hang

Add timeout:
```bash
pytest tests/e2e/ --timeout=60
```

### HTTP Mocks Not Working

Ensure context manager:
```python
# ✅ Correct
with N8nHttpMock(url) as mock:
    # setup mocks
    # make requests

# ❌ Wrong (missing context manager)
mock = N8nHttpMock(url)
mock.mock_get_workflows([...])
```

## See Also

- [Testkit Documentation](../testkit/README.md)
- [GitHub Actions CI](../../.github/workflows/e2e-tests.yml)
- [Frontend E2E Tests](../../n8n-ops-ui/tests/e2e/README.md)

