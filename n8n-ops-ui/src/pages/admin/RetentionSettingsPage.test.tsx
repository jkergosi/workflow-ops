import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@/test/test-utils';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { RetentionSettingsPage } from './RetentionSettingsPage';

const API_BASE = '/api/v1';

describe('RetentionSettingsPage', () => {
  beforeEach(() => {
    server.resetHandlers();

    server.use(
      http.get(`${API_BASE}/retention/policy`, () => {
        return HttpResponse.json({
          retention_days: 90,
          is_enabled: true,
          min_executions_to_keep: 100,
          last_cleanup_at: '2024-03-15T02:00:00.000Z',
          last_cleanup_deleted_count: 45000,
        });
      }),
      http.get(`${API_BASE}/auth/status`, () => {
        return HttpResponse.json({
          authenticated: true,
          onboarding_required: false,
          has_environment: true,
          user: { id: 'user-1', email: 'admin@test.com', name: 'Admin User', role: 'admin' },
          tenant: { id: 'tenant-1', name: 'Test Org', subscription_tier: 'pro' },
          entitlements: { plan_name: 'pro', features: {} },
        });
      })
    );
  });

  describe('Page Header', () => {
    it('should display the page title', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1, name: /retention settings/i })).toBeInTheDocument();
      });
    });

    it('should display the page description', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText(/manage execution data retention policies/i)).toBeInTheDocument();
      });
    });
  });

  describe('Status Overview Cards', () => {
    it('should display Status card showing enabled state', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Status')).toBeInTheDocument();
        expect(screen.getByText('Enabled')).toBeInTheDocument();
      });
    });

    it('should display Retention Period card', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Retention Period')).toBeInTheDocument();
        expect(screen.getByText('90 days')).toBeInTheDocument();
      });
    });

    it('should display Last Cleanup card', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Last Cleanup')).toBeInTheDocument();
        expect(screen.getByText('45,000 deleted')).toBeInTheDocument();
      });
    });
  });

  describe('Configuration Card', () => {
    it('should display Retention Configuration section', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Retention Configuration')).toBeInTheDocument();
      });
    });

    it('should display Enable Automatic Retention switch', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Enable Automatic Retention')).toBeInTheDocument();
      });
    });

    it('should display Retention Period input field', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/retention period \(days\)/i)).toBeInTheDocument();
      });
    });

    it('should display Minimum Executions input field', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/minimum executions to keep/i)).toBeInTheDocument();
      });
    });

    it('should display Save Changes button (disabled initially)', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        const saveButton = screen.getByRole('button', { name: /save changes/i });
        expect(saveButton).toBeInTheDocument();
        expect(saveButton).toBeDisabled();
      });
    });

    it('should display retention info banner', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText(/about retention cleanup/i)).toBeInTheDocument();
      });
    });
  });

  describe('Manual Actions Card', () => {
    it('should display Manual Actions section', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByText('Manual Actions')).toBeInTheDocument();
      });
    });

    it('should display Preview Cleanup button', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /preview cleanup/i })).toBeInTheDocument();
      });
    });

    it('should display Run Cleanup Now button', async () => {
      render(<RetentionSettingsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /run cleanup now/i })).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('should display loading spinner while fetching policy', async () => {
      server.use(
        http.get(`${API_BASE}/retention/policy`, async () => {
          // Delay response to test loading state
          await new Promise(resolve => setTimeout(resolve, 100));
          return HttpResponse.json({
            retention_days: 90,
            is_enabled: true,
            min_executions_to_keep: 100,
          });
        })
      );

      render(<RetentionSettingsPage />);

      expect(screen.getByText(/loading retention settings/i)).toBeInTheDocument();
    });
  });
});
