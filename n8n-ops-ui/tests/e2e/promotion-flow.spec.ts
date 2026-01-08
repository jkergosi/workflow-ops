/**
 * E2E tests for promotion flow UI.
 * 
 * Tests the complete promotion workflow through the UI:
 * - Navigate to pipelines
 * - Create new promotion
 * - Monitor execution
 * - Verify success state
 */
import { test, expect } from '@playwright/test';
import { MockApiClient } from '../testkit/mock-api';

test.describe('Promotion Flow E2E', () => {
  let mockApi: MockApiClient;

  test.beforeEach(async ({ page }) => {
    mockApi = new MockApiClient(page);
    
    // Mock authentication
    await mockApi.mockAuth('admin');
    await mockApi.mockEnvironments();
  });

  test('complete promotion flow - happy path', async ({ page }) => {
    // Setup mocks
    await mockApi.mockPromotionFlow();

    // Navigate to pipelines page
    await page.goto('/pipelines');

    // Wait for pipelines to load
    await expect(page.locator('h1')).toContainText('Pipelines');

    // Click on a pipeline to view details
    await page.click('text=Dev to Prod');

    // Click "New Promotion" button
    await page.click('button:has-text("New Promotion")');

    // Select workflows to promote
    await page.check('input[type="checkbox"][value="wf-1"]');
    await page.check('input[type="checkbox"][value="wf-2"]');

    // Click "Start Promotion"
    await page.click('button:has-text("Start Promotion")');

    // Wait for promotion creation
    await expect(page.locator('text=Promotion Created')).toBeVisible();

    // Execute promotion
    await page.click('button:has-text("Execute")');

    // Monitor progress
    await expect(page.locator('text=Running')).toBeVisible();

    // Wait for completion
    await expect(page.locator('text=Completed')).toBeVisible({ timeout: 10000 });

    // Verify success message
    await expect(page.locator('text=Promotion successful')).toBeVisible();
  });

  test('promotion validation errors displayed', async ({ page }) => {
    // Mock validation failure
    await page.route('**/api/v1/promotions/validate', async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          errors: ['Missing credentials in target environment'],
        }),
      });
    });

    await page.goto('/pipelines');
    await page.click('text=Dev to Prod');
    await page.click('button:has-text("New Promotion")');

    // Validation errors should be displayed
    await expect(page.locator('text=Missing credentials')).toBeVisible();
  });

  test('promotion real-time progress updates', async ({ page }) => {
    await mockApi.mockPromotionFlow();

    await page.goto('/promotions/promotion-1');

    // Should show progress bar
    await expect(page.locator('[role="progressbar"]')).toBeVisible();

    // Progress updates should be reflected
    // (In real test, SSE would update this)
    await expect(page.locator('text=50%')).toBeVisible();
  });
});

