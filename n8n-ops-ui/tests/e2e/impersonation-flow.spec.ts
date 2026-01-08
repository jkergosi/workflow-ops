/**
 * E2E tests for platform admin impersonation UI.
 * 
 * Tests the complete impersonation workflow:
 * - Platform admin login
 * - Start impersonation
 * - Verify impersonation banner
 * - Perform actions as target user
 * - End impersonation
 */
import { test, expect } from '@playwright/test';
import { MockApiClient } from '../testkit/mock-api';

test.describe('Impersonation Flow E2E', () => {
  let mockApi: MockApiClient;

  test.beforeEach(async ({ page }) => {
    mockApi = new MockApiClient(page);
  });

  test('complete impersonation flow', async ({ page }) => {
    // Login as platform admin
    await mockApi.mockAuth('platform_admin');
    await mockApi.mockEnvironments();
    await mockApi.mockImpersonationFlow();

    await page.goto('/');

    // Navigate to platform admin console
    await page.click('text=Platform Admin');
    await page.click('text=Impersonate User');

    // Select user to impersonate
    await page.fill('input[name="email"]', 'dev@test.com');
    await page.click('button:has-text("Search")');

    // Click impersonate button
    await page.click('button:has-text("Impersonate")');

    // Verify impersonation banner appears
    await expect(page.locator('[data-testid="impersonation-banner"]')).toBeVisible();
    await expect(page.locator('text=Impersonating: Developer User')).toBeVisible();

    // Perform action as impersonated user
    await page.goto('/environments');
    await page.click('button:has-text("New Environment")');

    // Should act as target user (developer permissions)
    // Fill form and submit
    await page.fill('input[name="name"]', 'Test Environment');
    await page.click('button:has-text("Create")');

    // End impersonation
    await page.click('[data-testid="end-impersonation"]');
    
    // Verify banner disappears
    await expect(page.locator('[data-testid="impersonation-banner"]')).not.toBeVisible();

    // Should be back to platform admin context
    await expect(page.locator('text=Platform Admin')).toBeVisible();
  });

  test('impersonation banner shows correct user info', async ({ page }) => {
    await mockApi.mockAuth('platform_admin');
    await mockApi.mockImpersonationFlow();

    await page.goto('/');
    
    // Mock active impersonation session
    await page.evaluate(() => {
      localStorage.setItem('impersonation_session', JSON.stringify({
        session_id: 'session-1',
        target_user: {
          id: '000003',
          name: 'Developer User',
          email: 'dev@test.com',
        },
      }));
    });

    await page.reload();

    // Banner should show impersonated user info
    const banner = page.locator('[data-testid="impersonation-banner"]');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText('Developer User');
    await expect(banner).toContainText('dev@test.com');
  });

  test('admin cannot impersonate another admin', async ({ page }) => {
    await mockApi.mockAuth('platform_admin');
    await mockApi.mockEnvironments();

    // Mock admin-to-admin block
    await page.route('**/api/v1/platform/impersonate', async (route) => {
      const requestBody = route.request().postDataJSON();
      if (requestBody.target_user_id === 'admin-id') {
        await route.fulfill({
          status: 403,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'Cannot impersonate another platform admin',
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto('/platform/impersonate');

    // Attempt to impersonate admin
    await page.fill('input[name="target_user_id"]', 'admin-id');
    await page.click('button:has-text("Impersonate")');

    // Should show error
    await expect(page.locator('text=Cannot impersonate another platform admin')).toBeVisible();
  });

  test('impersonation actions are visually distinguished', async ({ page }) => {
    await mockApi.mockAuth('platform_admin');
    await mockApi.mockImpersonationFlow();

    await page.goto('/');

    // Mock active impersonation
    await page.evaluate(() => {
      localStorage.setItem('impersonation_active', 'true');
    });

    await page.reload();

    // UI should have visual indicators
    // (e.g., different header color, warning indicators)
    const appContainer = page.locator('#app');
    await expect(appContainer).toHaveClass(/impersonation-active/);
  });
});

