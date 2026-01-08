/**
 * E2E tests for canonical onboarding wizard UI.
 * 
 * Tests the complete onboarding workflow:
 * - Start onboarding wizard
 * - Select anchor environment
 * - Monitor progress
 * - Link untracked workflows
 * - View canonical matrix
 */
import { test, expect } from '@playwright/test';
import { MockApiClient } from '../testkit/mock-api';

test.describe('Canonical Onboarding Flow E2E', () => {
  let mockApi: MockApiClient;

  test.beforeEach(async ({ page }) => {
    mockApi = new MockApiClient(page);
    await mockApi.mockAuth('admin');
    await mockApi.mockEnvironments();
  });

  test('complete onboarding wizard', async ({ page }) => {
    await mockApi.mockCanonicalFlow();

    // Navigate to canonical workflows
    await page.goto('/canonical');

    // Start onboarding wizard
    await page.click('button:has-text("Start Onboarding")');

    // Step 1: Preflight checks
    await expect(page.locator('h2')).toContainText('Preflight Checks');
    await expect(page.locator('text=All checks passed')).toBeVisible();
    await page.click('button:has-text("Next")');

    // Step 2: Select anchor environment
    await expect(page.locator('h2')).toContainText('Select Anchor Environment');
    await page.selectOption('select[name="anchor_environment"]', 'env-prod');
    await page.click('button:has-text("Start Inventory")');

    // Step 3: Monitor progress
    await expect(page.locator('text=Running inventory')).toBeVisible();
    await expect(page.locator('[role="progressbar"]')).toBeVisible();

    // Wait for completion
    await expect(page.locator('text=Inventory complete')).toBeVisible({ timeout: 10000 });

    // Step 4: Review untracked workflows
    await page.click('button:has-text("Next")');
    await expect(page.locator('text=Untracked Workflows')).toBeVisible();

    // Step 5: Complete onboarding
    await page.click('button:has-text("Complete Onboarding")');
    await expect(page.locator('text=Onboarding successful')).toBeVisible();
  });

  test('canonical matrix view shows workflow status', async ({ page }) => {
    await mockApi.mockCanonicalFlow();

    await page.goto('/canonical/matrix');

    // Matrix should show workflows across environments
    await expect(page.locator('text=Customer Onboarding')).toBeVisible();

    // Drift indicator
    await expect(page.locator('[data-status="drift"]')).toBeVisible();

    // Synced indicator
    await expect(page.locator('[data-status="linked"]')).toBeVisible();
  });

  test('link untracked workflow', async ({ page }) => {
    await mockApi.mockCanonicalFlow();

    await page.goto('/canonical/untracked');

    // Click link button for untracked workflow
    await page.click('button[data-workflow-id="wf-untracked"]:has-text("Link")');

    // Select canonical workflow
    await page.selectOption('select[name="canonical_id"]', 'canonical-1');
    await page.click('button:has-text("Link Workflow")');

    await expect(page.locator('text=Workflow linked successfully')).toBeVisible();
  });
});

