import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { SnapshotsPage } from './SnapshotsPage';

const API_BASE = 'http://localhost:4000/api/v1';

const mockEnvironments = [
  {
    id: 'env-1',
    tenant_id: 'tenant-1',
    n8n_name: 'Development',
    name: 'Development',
    n8n_type: 'development',
    type: 'development',
    is_active: true,
  },
  {
    id: 'env-2',
    tenant_id: 'tenant-1',
    n8n_name: 'Production',
    name: 'Production',
    n8n_type: 'production',
    type: 'production',
    is_active: true,
  },
];

// Mock snapshots use snake_case because the API client transforms them to camelCase
const mockSnapshots = [
  {
    id: 'snap-1',
    tenant_id: 'tenant-1',
    environment_id: 'dev', // Match store default 'dev' - API client transforms to environmentId
    type: 'pre_promotion',
    git_commit_sha: 'abc123def456',
    created_by_user_id: 'admin@test.com',
    related_deployment_id: 'deploy-1',
    metadata_json: { reason: 'Before promotion to production' },
    created_at: '2024-01-15T10:00:00Z',
  },
  {
    id: 'snap-2',
    tenant_id: 'tenant-1',
    environment_id: 'dev',
    type: 'post_promotion',
    git_commit_sha: 'def456ghi789',
    created_by_user_id: 'admin@test.com',
    related_deployment_id: 'deploy-1',
    metadata_json: { reason: 'After promotion to production' },
    created_at: '2024-01-15T10:05:00Z',
  },
  {
    id: 'snap-3',
    tenant_id: 'tenant-1',
    environment_id: 'dev',
    type: 'manual_backup',
    git_commit_sha: 'ghi789jkl012',
    created_by_user_id: 'dev@test.com',
    related_deployment_id: null,
    metadata_json: { reason: 'Manual backup before changes' },
    created_at: '2024-01-14T16:00:00Z',
  },
  {
    id: 'snap-4',
    tenant_id: 'tenant-1',
    environment_id: 'dev',
    type: 'auto_backup',
    git_commit_sha: 'jkl012mno345',
    created_by_user_id: null,
    related_deployment_id: null,
    metadata_json: null,
    created_at: '2024-01-13T00:00:00Z',
  },
];

// Mock snapshot detail uses snake_case because the API client transforms it
const mockSnapshotDetail = {
  id: 'snap-1',
  tenant_id: 'tenant-1',
  environment_id: 'dev',
  type: 'pre_promotion',
  git_commit_sha: 'abc123def456',
  created_by_user_id: 'admin@test.com',
  related_deployment_id: 'deploy-1',
  metadata_json: { reason: 'Before promotion to production' },
  created_at: '2024-01-15T10:00:00Z',
};

describe('SnapshotsPage', () => {
  beforeEach(() => {
    server.resetHandlers();

    server.use(
      http.get(`${API_BASE}/snapshots`, () => {
        // Return all mock snapshots regardless of environment filter
        // The store's default selectedEnvironment may not match our mock env ids
        return HttpResponse.json(mockSnapshots);
      }),
      http.get(`${API_BASE}/snapshots/:id`, () => {
        return HttpResponse.json(mockSnapshotDetail);
      }),
      http.post(`${API_BASE}/snapshots/:id/restore`, () => {
        return HttpResponse.json({ message: 'Snapshot restored successfully' });
      }),
      http.get(`${API_BASE}/environments`, () => {
        return HttpResponse.json(mockEnvironments);
      }),
      http.get(`${API_BASE}/auth/status`, () => {
        return HttpResponse.json({
          authenticated: true,
          onboarding_required: false,
          has_environment: true,
          user: { id: 'user-1', email: 'admin@test.com', name: 'Admin', role: 'admin' },
          tenant: { id: 'tenant-1', name: 'Test Org', subscription_tier: 'pro' },
          entitlements: {
            plan_name: 'pro',
            features: {
              max_environments: { enabled: true, limit: 10 },
              git_integration: { enabled: true },
            },
          },
        });
      })
    );
  });

  describe('Loading State', () => {
    it('should show loading message while fetching snapshots', async () => {
      server.use(
        http.get(`${API_BASE}/snapshots`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockSnapshots);
        })
      );

      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText(/loading snapshots/i)).toBeInTheDocument();
      });
    });
  });

  describe('Success State', () => {
    it('should display page heading', async () => {
      render(<SnapshotsPage />);

      expect(screen.getByRole('heading', { level: 1, name: /snapshots/i })).toBeInTheDocument();
    });

    it('should display page description', async () => {
      render(<SnapshotsPage />);

      expect(screen.getByText(/version control and rollback for your workflows/i)).toBeInTheDocument();
    });

    it('should display Snapshot History card', async () => {
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Snapshot History')).toBeInTheDocument();
      });
    });

    it('should display snapshots in the table', async () => {
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      expect(screen.getByText('Post-promotion')).toBeInTheDocument();
      expect(screen.getByText('Manual backup')).toBeInTheDocument();
      expect(screen.getByText('Auto backup')).toBeInTheDocument();
    });

    it('should display snapshot types as badges', async () => {
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      // Check for all snapshot type badges
      expect(screen.getByText('Post-promotion')).toBeInTheDocument();
      expect(screen.getByText('Manual backup')).toBeInTheDocument();
      expect(screen.getByText('Auto backup')).toBeInTheDocument();
    });

    it('should display triggered by user for snapshots', async () => {
      render(<SnapshotsPage />);

      // Wait for snapshots to load (need to wait for environments first)
      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      }, { timeout: 5000 });

      // admin@test.com appears for snap-1 and snap-2
      expect(screen.getAllByText('admin@test.com').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('dev@test.com')).toBeInTheDocument();
      expect(screen.getByText('System')).toBeInTheDocument(); // For auto_backup with null createdByUserId
    });

    it('should display View and Restore buttons for each snapshot', async () => {
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      const viewButtons = screen.getAllByRole('button', { name: /view/i });
      expect(viewButtons.length).toBeGreaterThanOrEqual(4);

      const restoreButtons = screen.getAllByRole('button', { name: /restore/i });
      expect(restoreButtons.length).toBeGreaterThanOrEqual(4);
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no snapshots exist', async () => {
      server.use(
        http.get(`${API_BASE}/snapshots`, () => {
          return HttpResponse.json([]);
        })
      );

      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText(/no snapshots found/i)).toBeInTheDocument();
      });
    });
  });

  describe('User Interactions - View Snapshot Details', () => {
    it('should open snapshot detail dialog when clicking View button', async () => {
      const user = userEvent.setup();
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      const viewButtons = screen.getAllByRole('button', { name: /view/i });
      await user.click(viewButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByText(/snapshot details/i)).toBeInTheDocument();
    });

    it('should display snapshot information in detail dialog', async () => {
      const user = userEvent.setup();
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      const viewButtons = screen.getAllByRole('button', { name: /view/i });
      await user.click(viewButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByText('Environment')).toBeInTheDocument();
      expect(within(dialog).getByText('Type')).toBeInTheDocument();
      expect(within(dialog).getByText('Created At')).toBeInTheDocument();
      expect(within(dialog).getByText('Triggered By')).toBeInTheDocument();
      expect(within(dialog).getByText('Git Commit SHA')).toBeInTheDocument();
    });
  });

  describe('User Interactions - Restore Snapshot', () => {
    it('should open restore confirmation dialog when clicking Restore button', async () => {
      const user = userEvent.setup();
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      const restoreButtons = screen.getAllByRole('button', { name: /restore/i });
      await user.click(restoreButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('alertdialog')).toBeInTheDocument();
      });

      expect(screen.getByText(/confirm restore/i)).toBeInTheDocument();
    });

    it('should show restore warning message', async () => {
      const user = userEvent.setup();
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      const restoreButtons = screen.getAllByRole('button', { name: /restore/i });
      await user.click(restoreButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('alertdialog')).toBeInTheDocument();
      });

      expect(screen.getByText(/replace all workflows/i)).toBeInTheDocument();
    });

    it('should restore snapshot when confirmed', async () => {
      const user = userEvent.setup();
      let restoreCalled = false;

      server.use(
        http.post(`${API_BASE}/snapshots/:id/restore`, () => {
          restoreCalled = true;
          return HttpResponse.json({ message: 'Snapshot restored successfully' });
        })
      );

      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      const restoreButtons = screen.getAllByRole('button', { name: /restore/i });
      await user.click(restoreButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('alertdialog')).toBeInTheDocument();
      });

      // Find and click the Restore button in the alert dialog
      const alertDialog = screen.getByRole('alertdialog');
      const confirmButton = within(alertDialog).getByRole('button', { name: /^restore$/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(restoreCalled).toBe(true);
      });
    });

    it('should cancel restore when clicking Cancel', async () => {
      const user = userEvent.setup();
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      const restoreButtons = screen.getAllByRole('button', { name: /restore/i });
      await user.click(restoreButtons[0]);

      await waitFor(() => {
        expect(screen.getByRole('alertdialog')).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('Environment Selector', () => {
    it('should display environment selector when multiple environments exist', async () => {
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      // Should have environment selector
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });
  });

  describe('Table Structure', () => {
    it('should display table with correct column headers', async () => {
      render(<SnapshotsPage />);

      await waitFor(() => {
        expect(screen.getByText('Pre-promotion')).toBeInTheDocument();
      });

      const table = screen.getByRole('table');
      expect(within(table).getByText('Created At')).toBeInTheDocument();
      expect(within(table).getByText('Type')).toBeInTheDocument();
      expect(within(table).getByText('Triggered By')).toBeInTheDocument();
      expect(within(table).getByText('Deployment')).toBeInTheDocument();
      expect(within(table).getByText('Notes')).toBeInTheDocument();
      expect(within(table).getByText('Actions')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should handle server error gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/snapshots`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'Internal server error' }), {
            status: 500,
          });
        })
      );

      render(<SnapshotsPage />);

      // Page should not crash
      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1, name: /snapshots/i })).toBeInTheDocument();
      });
    });
  });
});
