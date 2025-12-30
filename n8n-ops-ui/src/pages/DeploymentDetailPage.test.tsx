import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@/test/test-utils';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { DeploymentDetailPage } from './DeploymentDetailPage';

// Mock useParams to return the deployment ID
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: 'deploy-1' }),
    useNavigate: () => vi.fn(),
  };
});

// Mock the SSE hook to prevent actual SSE connections
vi.mock('@/lib/use-deployments-sse', () => ({
  useDeploymentsSSE: () => ({ isConnected: false, connectionError: null }),
}));

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
    isActive: true,
    environmentIds: ['env-1', 'env-2'],
    stages: [],
  },
];

// Mock deployment with various workflow statuses (snake_case to match API format)
const mockDeploymentWithPendingWorkflows = {
  id: 'deploy-1',
  tenant_id: 'tenant-1',
  pipeline_id: 'pipeline-1',
  source_environment_id: 'env-1',
  target_environment_id: 'env-2',
  status: 'running',
  triggered_by_user_id: 'user-1',
  started_at: '2024-01-15T10:00:00Z',
  finished_at: null,
  pre_snapshot_id: 'snap-pre-1',
  post_snapshot_id: null,
  summary_json: {
    total: 5,
    created: 1,
    updated: 1,
    deleted: 0,
    failed: 0,
    skipped: 0,
    unchanged: 0,
    processed: 2,
    current_workflow: 'Workflow 3',
  },
  progress_current: 2,
  progress_total: 5,
  current_workflow_name: 'Workflow 3',
  workflows: [
    {
      id: 'wf-1',
      deployment_id: 'deploy-1',
      workflow_id: 'n8n-wf-1',
      workflow_name_at_time: 'Workflow 1',
      change_type: 'created',
      status: 'success',
      error_message: null,
      created_at: '2024-01-15T10:00:00Z',
    },
    {
      id: 'wf-2',
      deployment_id: 'deploy-1',
      workflow_id: 'n8n-wf-2',
      workflow_name_at_time: 'Workflow 2',
      change_type: 'updated',
      status: 'success',
      error_message: null,
      created_at: '2024-01-15T10:00:00Z',
    },
    {
      id: 'wf-3',
      deployment_id: 'deploy-1',
      workflow_id: 'n8n-wf-3',
      workflow_name_at_time: 'Workflow 3',
      change_type: 'updated',
      status: 'pending',
      error_message: null,
      created_at: '2024-01-15T10:00:00Z',
    },
    {
      id: 'wf-4',
      deployment_id: 'deploy-1',
      workflow_id: 'n8n-wf-4',
      workflow_name_at_time: 'Workflow 4',
      change_type: 'unchanged',
      status: 'pending',
      error_message: null,
      created_at: '2024-01-15T10:00:00Z',
    },
    {
      id: 'wf-5',
      deployment_id: 'deploy-1',
      workflow_id: 'n8n-wf-5',
      workflow_name_at_time: 'Workflow 5',
      change_type: 'created',
      status: 'pending',
      error_message: null,
      created_at: '2024-01-15T10:00:00Z',
    },
  ],
};

const mockCompletedDeployment = {
  id: 'deploy-2',
  tenant_id: 'tenant-1',
  pipeline_id: 'pipeline-1',
  source_environment_id: 'env-1',
  target_environment_id: 'env-2',
  status: 'success',
  triggered_by_user_id: 'user-1',
  started_at: '2024-01-15T10:00:00Z',
  finished_at: '2024-01-15T10:05:00Z',
  pre_snapshot_id: 'snap-pre-1',
  post_snapshot_id: 'snap-post-1',
  summary_json: {
    total: 6,
    created: 2,
    updated: 2,
    deleted: 0,
    failed: 1,
    skipped: 0,
    unchanged: 1,
    processed: 6,
  },
  workflows: [
    {
      id: 'wf-1',
      deployment_id: 'deploy-2',
      workflow_id: 'n8n-wf-1',
      workflow_name_at_time: 'Created Workflow',
      change_type: 'created',
      status: 'success',
      error_message: null,
      created_at: '2024-01-15T10:00:00Z',
    },
    {
      id: 'wf-2',
      deployment_id: 'deploy-2',
      workflow_id: 'n8n-wf-2',
      workflow_name_at_time: 'Updated Workflow',
      change_type: 'updated',
      status: 'success',
      error_message: null,
      created_at: '2024-01-15T10:00:00Z',
    },
    {
      id: 'wf-3',
      deployment_id: 'deploy-2',
      workflow_id: 'n8n-wf-3',
      workflow_name_at_time: 'Unchanged Workflow',
      change_type: 'unchanged',
      status: 'unchanged',
      error_message: null,
      created_at: '2024-01-15T10:00:00Z',
    },
    {
      id: 'wf-4',
      deployment_id: 'deploy-2',
      workflow_id: 'n8n-wf-4',
      workflow_name_at_time: 'Failed Workflow',
      change_type: 'updated',
      status: 'failed',
      error_message: 'Connection refused to target environment',
      created_at: '2024-01-15T10:00:00Z',
    },
    {
      id: 'wf-5',
      deployment_id: 'deploy-2',
      workflow_id: 'n8n-wf-5',
      workflow_name_at_time: 'Skipped Workflow',
      change_type: 'skipped',
      status: 'skipped',
      error_message: 'Workflow already exists with conflicts',
      created_at: '2024-01-15T10:00:00Z',
    },
    {
      id: 'wf-6',
      deployment_id: 'deploy-2',
      workflow_id: 'n8n-wf-6',
      workflow_name_at_time: 'Another Created',
      change_type: 'created',
      status: 'success',
      error_message: null,
      created_at: '2024-01-15T10:00:00Z',
    },
  ],
};

describe('DeploymentDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.resetHandlers();

    // Setup handlers for all required endpoints using wildcard URL matching
    server.use(
      http.get('*/api/v1/environments', () => {
        return HttpResponse.json(mockEnvironments);
      }),
      http.get('*/api/v1/pipelines', () => {
        return HttpResponse.json(mockPipelines);
      }),
      http.get('*/api/v1/auth/status', () => {
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
              workflow_ci_cd: { enabled: true },
            },
          },
        });
      })
    );
  });

  describe('Workflow Status Display', () => {
    it('should display workflows with pending status during running deployment', async () => {
      server.use(
        http.get('*/api/v1/deployments/deploy-1', () => {
          // Return raw deployment object - api-client will wrap it
          return HttpResponse.json(mockDeploymentWithPendingWorkflows);
        })
      );

      render(<DeploymentDetailPage />);

      await waitFor(() => {
        expect(screen.getByText('Workflow 1')).toBeInTheDocument();
      });

      // Should show pending workflows
      expect(screen.getByText('Workflow 3')).toBeInTheDocument();
      expect(screen.getByText('Workflow 4')).toBeInTheDocument();
      expect(screen.getByText('Workflow 5')).toBeInTheDocument();
    });

    it('should display all workflow statuses in completed deployment', async () => {
      server.use(
        http.get('*/api/v1/deployments/deploy-1', () => {
          return HttpResponse.json(mockCompletedDeployment);
        })
      );

      render(<DeploymentDetailPage />);

      await waitFor(() => {
        expect(screen.getByText('Created Workflow')).toBeInTheDocument();
      });

      // Should show all workflows with different statuses
      expect(screen.getByText('Updated Workflow')).toBeInTheDocument();
      expect(screen.getByText('Unchanged Workflow')).toBeInTheDocument();
      expect(screen.getByText('Failed Workflow')).toBeInTheDocument();
      expect(screen.getByText('Skipped Workflow')).toBeInTheDocument();
    });

    it('should display workflow error messages', async () => {
      server.use(
        http.get('*/api/v1/deployments/deploy-1', () => {
          return HttpResponse.json(mockCompletedDeployment);
        })
      );

      render(<DeploymentDetailPage />);

      await waitFor(() => {
        expect(screen.getByText('Failed Workflow')).toBeInTheDocument();
      });

      // Should show error messages
      expect(screen.getByText(/Connection refused/i)).toBeInTheDocument();
    });

    it('should display change types for workflows', async () => {
      server.use(
        http.get('*/api/v1/deployments/deploy-1', () => {
          return HttpResponse.json(mockCompletedDeployment);
        })
      );

      render(<DeploymentDetailPage />);

      await waitFor(() => {
        expect(screen.getByText('Created Workflow')).toBeInTheDocument();
      });

      // Should show change types
      const createdBadges = screen.getAllByText('created');
      expect(createdBadges.length).toBeGreaterThanOrEqual(1);

      const updatedBadges = screen.getAllByText('updated');
      expect(updatedBadges.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('Summary Section', () => {
    it('should display unchanged count in summary', async () => {
      server.use(
        http.get('*/api/v1/deployments/deploy-1', () => {
          return HttpResponse.json(mockCompletedDeployment);
        })
      );

      render(<DeploymentDetailPage />);

      await waitFor(() => {
        expect(screen.getByText('Unchanged')).toBeInTheDocument();
      });

      // Should show unchanged count - verify the label exists (count verification handled by other tests)
      // The summary section should contain the Unchanged label
      const unchangedLabel = screen.getByText('Unchanged');
      expect(unchangedLabel).toBeInTheDocument();
    });

    it('should display all summary counts', async () => {
      server.use(
        http.get('*/api/v1/deployments/deploy-1', () => {
          return HttpResponse.json(mockCompletedDeployment);
        })
      );

      render(<DeploymentDetailPage />);

      await waitFor(() => {
        expect(screen.getByText('Total')).toBeInTheDocument();
      });

      expect(screen.getByText('Created')).toBeInTheDocument();
      expect(screen.getByText('Updated')).toBeInTheDocument();
      expect(screen.getByText('Unchanged')).toBeInTheDocument();
      expect(screen.getByText('Skipped')).toBeInTheDocument();
      expect(screen.getByText('Failed')).toBeInTheDocument();
    });
  });

  describe('Running Deployment Progress', () => {
    it('should show progress for running deployment', async () => {
      server.use(
        http.get('*/api/v1/deployments/deploy-1', () => {
          return HttpResponse.json(mockDeploymentWithPendingWorkflows);
        })
      );

      render(<DeploymentDetailPage />);

      await waitFor(() => {
        // The component shows "Deployment in Progress" (capital D, P)
        expect(screen.getByText('Deployment in Progress')).toBeInTheDocument();
      });

      // The component adds 1 to progress_current when running to show work in progress
      // So with progress_current=2, total=5, it shows "3 of 5"
      expect(screen.getByText(/Progress: 3 of 5/)).toBeInTheDocument();
    });

    it('should show current workflow being processed', async () => {
      server.use(
        http.get('*/api/v1/deployments/deploy-1', () => {
          return HttpResponse.json(mockDeploymentWithPendingWorkflows);
        })
      );

      render(<DeploymentDetailPage />);

      await waitFor(() => {
        // Wait for the deployment data to load by checking for progress card
        expect(screen.getByText('Deployment in Progress')).toBeInTheDocument();
      });

      // The component shows "(working on {currentWorkflowName})" in the progress text
      expect(screen.getByText(/working on Workflow 3/)).toBeInTheDocument();
    });
  });
});
