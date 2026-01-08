# Frontend E2E Testing Guide

Playwright E2E tests for N8N Ops UI critical flows.

## Overview

Frontend E2E tests cover 4 critical UI flows:
1. **Promotion Flow**: Navigate → create promotion → monitor progress
2. **Drift Incident Management**: View incidents → acknowledge → reconcile → close
3. **Canonical Onboarding**: Start wizard → select environment → complete
4. **Impersonation**: Start impersonation → verify banner → perform actions → end

## Running Tests Locally

### All E2E Tests (Headed)

```bash
cd n8n-ops-ui
npm run test:e2e
```

### Headless Mode

```bash
npm run test:e2e:headless
```

### Specific Test File

```bash
npx playwright test tests/e2e/promotion-flow.spec.ts
```

### With UI Mode (Interactive)

```bash
npx playwright test --ui
```

### Debug Mode

```bash
npx playwright test --debug
```

## Mock Strategy

All backend API calls are intercepted using Playwright's `page.route()`:

- Mock API responses defined in `tests/testkit/test-data.ts`
- Mock API helper methods in `tests/testkit/mock-api.ts`
- No real backend API calls made during tests

## Test Files

### 1. Promotion Flow (`promotion-flow.spec.ts`)

**Tests**:
- Complete promotion flow (happy path)
- Validation errors displayed
- Real-time progress updates (SSE simulation)

**Page Flow**:
```
/pipelines → Click pipeline → New Promotion → 
Select workflows → Start Promotion → Execute → 
Monitor progress → Verify completion
```

### 2. Drift Incident Management (`drift-flow.spec.ts`)

**Tests**:
- Complete incident lifecycle
- Severity badges displayed correctly
- Affected workflows shown

**Page Flow**:
```
/incidents → Click incident → Acknowledge → 
Stabilize → Reconcile → Close
```

### 3. Canonical Onboarding (`canonical-onboarding.spec.ts`)

**Tests**:
- Complete onboarding wizard
- Matrix view shows workflow status
- Link untracked workflow

**Page Flow**:
```
/canonical → Start Onboarding → Preflight checks → 
Select anchor environment → Monitor progress → 
Review untracked → Complete
```

### 4. Impersonation (`impersonation-flow.spec.ts`)

**Tests**:
- Complete impersonation flow
- Banner shows correct user info
- Admin-to-admin blocking
- Actions visually distinguished

**Page Flow**:
```
/ → Platform Admin → Impersonate User → 
Search user → Impersonate → Verify banner → 
Perform actions → End impersonation
```

## Test Structure

### Basic Test Pattern

```typescript
import { test, expect } from '@playwright/test';
import { MockApiClient } from '../testkit/mock-api';

test.describe('My Feature E2E', () => {
  let mockApi: MockApiClient;

  test.beforeEach(async ({ page }) => {
    mockApi = new MockApiClient(page);
    await mockApi.mockAuth('admin');
    await mockApi.mockEnvironments();
  });

  test('my test case', async ({ page }) => {
    // Setup mocks
    await mockApi.mockPromotionFlow();

    // Navigate
    await page.goto('/pipelines');

    // Interact
    await page.click('button:has-text("New Promotion")');

    // Assert
    await expect(page.locator('text=Promotion Created')).toBeVisible();
  });
});
```

### Using Test Data

```typescript
import { TestData } from '../testkit/test-data';

// Use predefined test data
await page.route('**/api/v1/pipelines', async (route) => {
  await route.fulfill({
    status: 200,
    json: TestData.pipelines.list,
  });
});
```

## Mock API Helper

### MockApiClient Methods

```typescript
const mockApi = new MockApiClient(page);

// Authentication
await mockApi.mockAuth('admin' | 'developer' | 'platform_admin');

// Core data
await mockApi.mockEnvironments();

// Flow-specific
await mockApi.mockPromotionFlow();
await mockApi.mockDriftFlow();
await mockApi.mockCanonicalFlow();
await mockApi.mockImpersonationFlow();
```

## CI Integration

GitHub Actions runs Playwright tests:

```yaml
- name: Run E2E tests
  run: |
    cd n8n-ops-ui
    npx playwright test tests/e2e/ --reporter=list,html
```

See `.github/workflows/e2e-tests.yml` for full CI configuration.

## Playwright Configuration

Configuration in `playwright.config.ts`:

```typescript
export default defineConfig({
  testDir: './tests',
  timeout: 60 * 1000,
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
```

## Writing New E2E Tests

### 1. Create Test File

```bash
touch n8n-ops-ui/tests/e2e/my-feature.spec.ts
```

### 2. Add Test Data

Update `tests/testkit/test-data.ts`:

```typescript
export const TestData = {
  myFeature: {
    item: {
      id: 'item-1',
      name: 'Test Item',
    },
  },
};
```

### 3. Add Mock API Method

Update `tests/testkit/mock-api.ts`:

```typescript
async mockMyFeature() {
  await this.page.route('**/api/v1/my-feature', async (route) => {
    await route.fulfill({
      status: 200,
      json: TestData.myFeature.item,
    });
  });
}
```

### 4. Write Test

```typescript
test('my feature works', async ({ page }) => {
  mockApi = new MockApiClient(page);
  await mockApi.mockAuth('admin');
  await mockApi.mockMyFeature();

  await page.goto('/my-feature');
  await expect(page.locator('h1')).toContainText('My Feature');
});
```

## Debugging Tips

### Visual Debugging

```bash
npx playwright test --debug
```

### Playwright Inspector

The test will pause and open inspector where you can:
- Step through test
- Inspect DOM
- View network requests
- See console logs

### Screenshots and Videos

On failure, Playwright automatically captures:
- Screenshots (`playwright-report/`)
- Videos (`test-results/`)
- Traces (`playwright-report/`)

### View Test Report

```bash
npx playwright show-report
```

### Selector Debugging

```typescript
// Pause at specific point
await page.pause();

// Log element info
const element = page.locator('button:has-text("Submit")');
console.log(await element.count());
console.log(await element.textContent());
```

## Best Practices

1. **Use Data Attributes**: Add `data-testid` attributes for reliable selectors
   ```typescript
   await page.click('[data-testid="create-promotion-button"]');
   ```

2. **Wait for Elements**: Use `await expect(...).toBeVisible()` instead of hardcoded waits
   ```typescript
   await expect(page.locator('text=Loading...')).not.toBeVisible();
   await expect(page.locator('text=Completed')).toBeVisible();
   ```

3. **Mock All API Calls**: Don't let tests hit real backend
   ```typescript
   test.beforeEach(async ({ page }) => {
    mockApi = new MockApiClient(page);
    await mockApi.mockAuth('admin');
    // Mock all APIs used in test
   });
   ```

4. **Test User Flows**: Test complete user journeys, not isolated interactions

5. **Independent Tests**: Each test should be independent and not rely on other tests

## Common Issues

### Flaky Tests

- Add explicit waits: `await expect(...).toBeVisible()`
- Increase timeout for slow operations
- Check for race conditions

### Element Not Found

- Check selector specificity
- Verify element is visible (not hidden)
- Wait for page load/navigation

### API Mocks Not Working

- Verify route pattern matches actual API calls
- Check route is set up before navigation
- Use `page.on('request')` to debug

## See Also

- [Backend E2E Tests](../../n8n-ops-backend/tests/e2e/README.md)
- [Playwright Documentation](https://playwright.dev/)
- [Test Testkit](../testkit/)

