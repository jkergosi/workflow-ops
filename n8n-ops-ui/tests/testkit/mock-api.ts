/**
 * Mock API helpers for Playwright E2E tests.
 * 
 * Provides utilities to intercept and mock backend API calls.
 */
import { Page } from '@playwright/test';
import { TestData } from './test-data';

export class MockApiClient {
  constructor(private page: Page) {}

  /**
   * Mock the promotion flow APIs
   */
  async mockPromotionFlow() {
    // Mock pipeline list
    await this.page.route('**/api/v1/pipelines', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.pipelines.list),
      });
    });

    // Mock promotion creation
    await this.page.route('**/api/v1/promotions', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(TestData.promotions.created),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(TestData.promotions.list),
        });
      }
    });

    // Mock promotion execution
    await this.page.route('**/api/v1/promotions/*/execute', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.promotions.executing),
      });
    });

    // Mock SSE for real-time updates
    await this.page.route('**/api/v1/sse/deployments/*', async (route) => {
      // For SSE, we need to simulate a stream
      // This is simplified - real implementation would stream events
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"status":"running","progress":50}\n\n',
      });
    });
  }

  /**
   * Mock the drift detection APIs
   */
  async mockDriftFlow() {
    // Mock drift incidents list
    await this.page.route('**/api/v1/incidents', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.drift.incidents),
      });
    });

    // Mock incident acknowledgment
    await this.page.route('**/api/v1/incidents/*/acknowledge', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.drift.acknowledged),
      });
    });

    // Mock incident stabilization
    await this.page.route('**/api/v1/incidents/*/stabilize', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.drift.stabilized),
      });
    });

    // Mock reconciliation
    await this.page.route('**/api/v1/incidents/*/reconcile', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.drift.reconciled),
      });
    });
  }

  /**
   * Mock canonical onboarding APIs
   */
  async mockCanonicalFlow() {
    // Mock preflight check
    await this.page.route('**/api/v1/canonical/onboard/preflight', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.canonical.preflightSuccess),
      });
    });

    // Mock inventory phase
    await this.page.route('**/api/v1/canonical/onboard/inventory', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.canonical.inventoryStarted),
      });
    });

    // Mock untracked workflows
    await this.page.route('**/api/v1/canonical/untracked', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.canonical.untrackedWorkflows),
      });
    });

    // Mock matrix view
    await this.page.route('**/api/v1/workflows/matrix', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.canonical.matrix),
      });
    });
  }

  /**
   * Mock impersonation APIs
   */
  async mockImpersonationFlow() {
    // Mock start impersonation
    await this.page.route('**/api/v1/platform/impersonate', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.impersonation.started),
      });
    });

    // Mock end impersonation
    await this.page.route('**/api/v1/platform/end-impersonation', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.impersonation.ended),
      });
    });
  }

  /**
   * Mock authentication
   */
  async mockAuth(role: 'admin' | 'developer' | 'platform_admin' = 'admin') {
    await this.page.route('**/api/v1/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.auth[role]),
      });
    });
  }

  /**
   * Mock environments API
   */
  async mockEnvironments() {
    await this.page.route('**/api/v1/environments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(TestData.environments.list),
      });
    });
  }
}

