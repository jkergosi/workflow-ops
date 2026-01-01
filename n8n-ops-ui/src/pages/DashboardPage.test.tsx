import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@/test/test-utils';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { DashboardPage } from './DashboardPage';

const API_BASE = 'http://localhost:3000/api/v1';

const mockEnvironments = [
  {
    id: 'env-1',
    tenant_id: 'tenant-1',
    n8n_name: 'Development',
    name: 'Development',
    n8n_type: 'development',
    type: 'development',
    n8n_base_url: 'https://dev.n8n.example.com',
    is_active: true,
    isActive: true,
    workflow_count: 5,
    workflowCount: 5,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
  },
  {
    id: 'env-2',
    tenant_id: 'tenant-1',
    n8n_name: 'Production',
    name: 'Production',
    n8n_type: 'production',
    type: 'production',
    n8n_base_url: 'https://prod.n8n.example.com',
    is_active: true,
    isActive: true,
    workflow_count: 12,
    workflowCount: 12,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-16T10:00:00Z',
  },
];

const mockExecutions = [
  { id: 'exec-1', workflowId: 'wf-1', status: 'success', startedAt: '2024-01-01T00:00:00Z' },
  { id: 'exec-2', workflowId: 'wf-1', status: 'success', startedAt: '2024-01-02T00:00:00Z' },
  { id: 'exec-3', workflowId: 'wf-2', status: 'error', startedAt: '2024-01-03T00:00:00Z' },
];

describe('DashboardPage', () => {
  beforeEach(() => {
    server.resetHandlers();

    server.use(
      http.get(`${API_BASE}/environments`, () => {
        return HttpResponse.json(mockEnvironments);
      }),
      http.get(`${API_BASE}/executions`, () => {
        return HttpResponse.json(mockExecutions);
      }),
      http.get(`${API_BASE}/snapshots`, () => {
        return HttpResponse.json([]);
      }),
      http.get(`${API_BASE}/auth/status`, () => {
        return HttpResponse.json({
          authenticated: true,
          onboarding_required: false,
          has_environment: true,
          user: { id: 'user-1', email: 'admin@test.com', name: 'Admin User', role: 'admin' },
          tenant: { id: 'tenant-1', name: 'Test Org', subscription_tier: 'pro' },
          entitlements: {
            plan_name: 'pro',
            features: {
              max_environments: { enabled: true, limit: 10 },
              workflow_ci_cd: { enabled: true },
            },
          },
        });
      })
    );
  });

  describe('Loading State', () => {
    it('should show loading state initially', async () => {
      server.use(
        http.get(`${API_BASE}/environments`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockEnvironments);
        })
      );

      render(<DashboardPage />);

      // Page heading should still be visible
      expect(screen.getByRole('heading', { level: 1, name: /dashboard/i })).toBeInTheDocument();
    });
  });

  describe('Empty State (No Environments)', () => {
    it('should show get started prompt when no environments exist', async () => {
      server.use(
        http.get(`${API_BASE}/environments`, () => {
          return HttpResponse.json([]);
        })
      );

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText(/get started with workflowops/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/create your first environment/i)).toBeInTheDocument();
    });

    it('should show onboarding steps when no environments exist', async () => {
      server.use(
        http.get(`${API_BASE}/environments`, () => {
          return HttpResponse.json([]);
        })
      );

      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText(/1\. connect n8n/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/2\. sync workflows/i)).toBeInTheDocument();
      expect(screen.getByText(/3\. monitor & manage/i)).toBeInTheDocument();
    });
  });

  describe('Success State (With Environments)', () => {
    it('should display welcome message with user name', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText(/welcome back/i)).toBeInTheDocument();
      });
    });

    it('should display dashboard heading', async () => {
      render(<DashboardPage />);

      expect(screen.getByRole('heading', { level: 1, name: /dashboard/i })).toBeInTheDocument();
    });

    it('should display Add Environment button', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /add environment/i })).toBeInTheDocument();
      });
    });

    it('should display statistics cards', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Total Workflows')).toBeInTheDocument();
      });

      expect(screen.getByText('Recent Executions')).toBeInTheDocument();
      expect(screen.getByText('Environments')).toBeInTheDocument();
    });

    it('should display workflow count from environments', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        // 5 + 12 = 17 workflows
        expect(screen.getByText('17')).toBeInTheDocument();
      });
    });

    it('should display execution count', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        // 3 executions
        expect(screen.getByText('3')).toBeInTheDocument();
      });
    });

    it('should display environment count', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        // 2 environments
        expect(screen.getByText('2')).toBeInTheDocument();
      });
    });

    it('should display Environment Status section', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText(/environment status/i)).toBeInTheDocument();
      });
    });

    it('should list environments in status section', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText('Development')).toBeInTheDocument();
      });

      expect(screen.getByText('Production')).toBeInTheDocument();
    });

    it('should display Recommended Next Step section', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText(/recommended next step/i)).toBeInTheDocument();
      });
    });

    it('should show Pro → Agency upgrade trigger when pro has 2+ environments', async () => {
      render(<DashboardPage />);

      await waitFor(() => {
        expect(screen.getByText(/deliver changes safely as a team/i)).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /upgrade to agency/i })).toBeInTheDocument();
      expect(screen.getAllByRole('button', { name: /upgrade/i }).length).toBe(1);
    });
  });

  describe('Error State', () => {
    it('should handle server error gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/environments`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'Internal server error' }), {
            status: 500,
          });
        })
      );

      render(<DashboardPage />);

      // Page should not crash
      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1, name: /dashboard/i })).toBeInTheDocument();
      });
    });
  });
});
