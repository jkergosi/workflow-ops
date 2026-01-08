/**
 * E2E tests for drift incident management UI.
 * 
 * Tests the complete drift workflow through the UI:
 * - View incidents list
 * - Acknowledge incident
 * - Stabilize with notes
 * - Reconcile drift
 * - Close incident
 */
import { test, expect } from '@playwright/test';
import { MockApiClient } from '../testkit/mock-api';

test.describe('Drift Incident Flow E2E', () => {
  let mockApi: MockApiClient;

  test.beforeEach(async ({ page }) => {
    mockApi = new MockApiClient(page);
    await mockApi.mockAuth('admin');
    await mockApi.mockEnvironments();
  });

  test('complete drift incident lifecycle', async ({ page }) => {
    await mockApi.mockDriftFlow();

    // Navigate to incidents page
    await page.goto('/incidents');

    // Wait for incidents to load
    await expect(page.locator('h1')).toContainText('Drift Incidents');

    // Click on an incident
    await page.click('text=Drift detected in Customer Onboarding');

    // Step 1: Acknowledge incident
    await page.click('button:has-text("Acknowledge")');
    await page.fill('textarea[name="notes"]', 'Investigating the issue');
    await page.click('button:has-text("Submit")');

    await expect(page.locator('text=Acknowledged')).toBeVisible();

    // Step 2: Stabilize incident
    await page.click('button:has-text("Stabilize")');
    await page.fill('textarea[name="reason"]', 'Root cause identified');
    await page.click('button:has-text("Submit")');

    await expect(page.locator('text=Stabilized')).toBeVisible();

    // Step 3: Reconcile drift
    await page.click('button:has-text("Reconcile")');
    await page.selectOption('select[name="resolution_type"]', 'promote');
    await page.click('button:has-text("Reconcile")');

    await expect(page.locator('text=Reconciled')).toBeVisible();

    // Step 4: Close incident
    await page.click('button:has-text("Close Incident")');
    await expect(page.locator('text=Closed')).toBeVisible();
  });

  test('incident severity displayed correctly', async ({ page }) => {
    await mockApi.mockDriftFlow();

    await page.goto('/incidents');

    // High severity should have appropriate styling
    const highSeverityBadge = page.locator('[data-severity="high"]');
    await expect(highSeverityBadge).toBeVisible();
    await expect(highSeverityBadge).toHaveClass(/severity-high/);
  });

  test('drift details show affected workflows', async ({ page }) => {
    await mockApi.mockDriftFlow();

    await page.goto('/incidents/incident-1');

    // Affected workflows section
    await expect(page.locator('text=Affected Workflows')).toBeVisible();
    await expect(page.locator('text=wf-1')).toBeVisible();
  });
});

