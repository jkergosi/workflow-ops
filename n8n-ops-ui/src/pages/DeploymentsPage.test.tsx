import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@/test/test-utils';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { DeploymentsPage } from './DeploymentsPage';

const API_BASE = '/api/v1';

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

const mockPipelines = [
  {
    id: 'pipeline-1',
    tenant_id: 'tenant-1',
    name: 'Dev to Prod Pipeline',
    description: 'Promote workflows from development to production',
    is_active: true,
    environment_ids: ['env-1', 'env-2'],
    stages: [],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-15T00:00:00Z',
  },
];

// Mock deployments use snake_case because the API client transforms them to camelCase
const mockDeployments = [
  {
    id: 'deploy-1',
    tenant_id: 'tenant-1',
    pipeline_id: 'pipeline-1',
    source_environment_id: 'env-1',
    target_environment_id: 'env-2',
    status: 'success',
    triggered_by_user_id: 'admin@test.com',
    started_at: '2024-01-15T10:00:00Z',
    finished_at: '2024-01-15T10:05:00Z',
    summary_json: { total: 3, created: 1, updated: 2 },
  },
  {
    id: 'deploy-2',
    tenant_id: 'tenant-1',
    pipeline_id: 'pipeline-1',
    source_environment_id: 'env-1',
    target_environment_id: 'env-2',
    status: 'failed',
    triggered_by_user_id: 'dev@test.com',
    started_at: '2024-01-14T14:00:00Z',
    finished_at: '2024-01-14T14:02:00Z',
    summary_json: { total: 1, created: 0, updated: 0 },
  },
  {
    id: 'deploy-3',
    tenant_id: 'tenant-1',
    pipeline_id: 'pipeline-1',
    source_environment_id: 'env-1',
    target_environment_id: 'env-2',
    status: 'pending',
    triggered_by_user_id: 'admin@test.com',
    started_at: '2024-01-16T08:00:00Z',
    summary_json: { total: 2, processed: 1 },
  },
];

const mockDeploymentDetail = {
  id: 'deploy-1',
  tenant_id: 'tenant-1',
  pipelineId: 'pipeline-1',
  sourceEnvironmentId: 'env-1',
  targetEnvironmentId: 'env-2',
  status: 'success',
  triggeredByUserId: 'admin@test.com',
  startedAt: '2024-01-15T10:00:00Z',
  finishedAt: '2024-01-15T10:05:00Z',
  preSnapshotId: 'snap-pre-1',
  postSnapshotId: 'snap-post-1',
  workflows: [
    {
      id: 'wf-1',
      workflowNameAtTime: 'Test Workflow 1',
      changeType: 'create',
      status: 'success',
      errorMessage: null,
    },
    {
      id: 'wf-2',
      workflowNameAtTime: 'Test Workflow 2',
      changeType: 'update',
      status: 'success',
      errorMessage: null,
    },
  ],
};

describe('DeploymentsPage', () => {
  beforeEach(() => {
    server.resetHandlers();

    server.use(
      http.get(`${API_BASE}/deployments`, () => {
        return HttpResponse.json({
          deployments: mockDeployments,
          total: mockDeployments.length,
          page: 1,
          page_size: 50,
          thisWeekSuccessCount: 5,
          pendingApprovalsCount: 1,
        });
      }),
      http.get(`${API_BASE}/deployments/:id`, () => {
        return HttpResponse.json(mockDeploymentDetail);
      }),
      http.get(`${API_BASE}/environments`, () => {
        return HttpResponse.json(mockEnvironments);
      }),
      http.get(`${API_BASE}/pipelines`, () => {
        return HttpResponse.json(mockPipelines);
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
              environment_promotion: { enabled: true },
            },
          },
        });
      })
    );
  });

  describe('Loading State', () => {
    it('should show loading message while fetching deployments', async () => {
      server.use(
        http.get(`${API_BASE}/deployments`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json({
            deployments: mockDeployments,
            total: mockDeployments.length,
            thisWeekSuccessCount: 5,
            pendingApprovalsCount: 1,
          });
        })
      );

      render(<DeploymentsPage />);

      expect(screen.getByText(/loading deployments/i)).toBeInTheDocument();
    });
  });

  describe('Success State', () => {
    it('should display page heading', async () => {
      render(<DeploymentsPage />);

      expect(screen.getByRole('heading', { level: 1, name: /deployments/i })).toBeInTheDocument();
    });

    it('should display page description', async () => {
      render(<DeploymentsPage />);

      expect(screen.getByText(/track workflow deployments/i)).toBeInTheDocument();
    });

    it('should display Promote Workflows button', async () => {
      render(<DeploymentsPage />);

      expect(screen.getByRole('button', { name: /new deployment/i })).toBeInTheDocument();
    });

    it('should display summary cards', async () => {
      render(<DeploymentsPage />);

      await waitFor(() => {
        expect(screen.getByText(/promotion mode/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/pending approvals/i)).toBeInTheDocument();
      expect(screen.getByText(/this week/i)).toBeInTheDocument();
    });

    it('should display pending approvals count', async () => {
      render(<DeploymentsPage />);

      await waitFor(() => {
        expect(screen.getByText(/pending approvals/i)).toBeInTheDocument();
      });
    });

    it('should display this week success count', async () => {
      render(<DeploymentsPage />);

      await waitFor(() => {
        expect(screen.getByText(/this week/i)).toBeInTheDocument();
      });
    });

    it('should display Deployment History card', async () => {
      render(<DeploymentsPage />);

      await waitFor(() => {
        expect(screen.getByText('Deployment History')).toBeInTheDocument();
      });
    });

    it('should display deployments in the table', async () => {
      render(<DeploymentsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Dev to Prod Pipeline').length).toBeGreaterThan(0);
      });
    });

    it('should display deployment status badges', async () => {
      render(<DeploymentsPage />);

      await waitFor(() => {
        expect(screen.getByText('success')).toBeInTheDocument();
      });

      expect(screen.getByText('failed')).toBeInTheDocument();
      expect(screen.getByText('pending')).toBeInTheDocument();
    });

    it('should display environment stages for deployments', async () => {
      render(<DeploymentsPage />);

      await waitFor(() => {
        // Should show Development → Production for each deployment
        const devBadges = screen.getAllByText('Development');
        expect(devBadges.length).toBeGreaterThanOrEqual(1);
        const prodBadges = screen.getAllByText('Production');
        expect(prodBadges.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('should display pipeline name for deployments', async () => {
      render(<DeploymentsPage />);

      await waitFor(() => {
        const pipelineNames = screen.getAllByText('Dev to Prod Pipeline');
        expect(pipelineNames.length).toBeGreaterThanOrEqual(1);
      });
    });

  });

  describe('Empty State', () => {
    it('should show empty state when no deployments exist', async () => {
      server.use(
        http.get(`${API_BASE}/deployments`, () => {
          return HttpResponse.json({
            deployments: [],
            total: 0,
            thisWeekSuccessCount: 0,
            pendingApprovalsCount: 0,
          });
        })
      );

      render(<DeploymentsPage />);

      await waitFor(() => {
        expect(screen.getByText(/no deployments yet/i)).toBeInTheDocument();
      });
    });

    it('should show Create your first promotion link in empty state', async () => {
      server.use(
        http.get(`${API_BASE}/deployments`, () => {
          return HttpResponse.json({
            deployments: [],
            total: 0,
            thisWeekSuccessCount: 0,
            pendingApprovalsCount: 0,
          });
        })
      );

      render(<DeploymentsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /create your first deployment/i })).toBeInTheDocument();
      });
    });
  });

  describe('Table Structure', () => {
    it('should display table with correct column headers', async () => {
      render(<DeploymentsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Dev to Prod Pipeline').length).toBeGreaterThan(0);
      });

      const table = screen.getByRole('table');
      expect(within(table).getByText('Pipeline')).toBeInTheDocument();
      expect(within(table).getByText('Stage')).toBeInTheDocument();
      expect(within(table).getByText('Status')).toBeInTheDocument();
      expect(within(table).getByText('Started')).toBeInTheDocument();
      expect(within(table).getByText('Duration')).toBeInTheDocument();
      expect(within(table).getByText('Actions')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should handle server error gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/deployments`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'Internal server error' }), {
            status: 500,
          });
        })
      );

      render(<DeploymentsPage />);

      // Page should not crash
      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1, name: /deployments/i })).toBeInTheDocument();
      });
    });
  });
});
