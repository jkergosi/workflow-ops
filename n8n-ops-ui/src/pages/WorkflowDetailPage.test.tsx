import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { WorkflowDetailPage } from './WorkflowDetailPage';
import { render } from '@/test/test-utils';
import { server } from '@/test/mocks/server';

const API_BASE = '/api/v1';

// Comprehensive mock workflow with full analysis data matching WorkflowAnalysis interface
const mockWorkflow = {
  id: 'wf-1',
  n8n_workflow_id: 'n8n-wf-1',
  name: 'Test Workflow',
  active: true,
  environment_id: 'env-1',
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-15T00:00:00Z',
  nodes: [
    { id: 'node-1', name: 'Schedule Trigger', type: 'n8n-nodes-base.scheduleTrigger', position: [0, 0] },
    { id: 'node-2', name: 'HTTP Request', type: 'n8n-nodes-base.httpRequest', position: [200, 0] },
  ],
  connections: {
    'Schedule Trigger': { main: [[{ node: 'HTTP Request', type: 'main', index: 0 }]] },
  },
  tags: [{ id: 'tag-1', name: 'production' }],
  settings: {},
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-15T00:00:00Z',
  analysis: {
    graph: {
      nodeCount: 2,
      edgeCount: 1,
      complexityScore: 25,
      complexityLevel: 'simple',
      maxDepth: 2,
      maxBranching: 1,
      isLinear: true,
      hasFanOut: false,
      hasFanIn: false,
      hasCycles: false,
      triggerCount: 1,
      sinkCount: 1,
    },
    nodes: [
      { id: 'node-1', name: 'Schedule Trigger', type: 'n8n-nodes-base.scheduleTrigger', category: 'trigger', isCredentialed: false, isTrigger: true },
      { id: 'node-2', name: 'HTTP Request', type: 'n8n-nodes-base.httpRequest', category: 'network', isCredentialed: false, isTrigger: false },
    ],
    dependencies: [
      { name: 'External API', type: 'api', nodeCount: 1, nodes: ['HTTP Request'] },
    ],
    summary: {
      purpose: 'Scheduled HTTP request workflow',
      executionSummary: 'Triggers on schedule and makes HTTP request',
      triggerTypes: ['Schedule Trigger'],
      externalSystems: ['HTTP API'],
    },
    reliability: {
      score: 75,
      level: 'good',
      continueOnFailCount: 0,
      errorHandlingNodes: 0,
      retryNodes: 0,
      missingErrorHandling: [],
      failureHotspots: [],
      recommendations: [],
    },
    performance: {
      score: 85,
      level: 'good',
      hasParallelism: false,
      estimatedComplexity: 'low',
      sequentialBottlenecks: [],
      redundantCalls: [],
      largePayloadRisks: [],
      recommendations: [],
    },
    cost: {
      level: 'low',
      triggerFrequency: 'scheduled',
      apiHeavyNodes: [],
      llmNodes: [],
      costAmplifiers: [],
      throttlingCandidates: [],
      recommendations: [],
    },
    security: {
      score: 80,
      level: 'good',
      credentialCount: 0,
      credentialTypes: [],
      hardcodedSecretSignals: [],
      overPrivilegedRisks: [],
      secretReuseRisks: [],
      recommendations: [],
    },
    maintainability: {
      score: 70,
      level: 'good',
      namingConsistency: 80,
      logicalGroupingScore: 75,
      readabilityScore: 85,
      missingDescriptions: [],
      missingAnnotations: [],
      nodeReuseOpportunities: [],
      recommendations: [],
    },
    governance: {
      score: 85,
      level: 'good',
      auditability: 85,
      environmentPortability: 70,
      promotionSafety: true,
      piiExposureRisks: [],
      retentionIssues: [],
      recommendations: [],
    },
    drift: {
      hasGitMismatch: false,
      environmentDivergence: [],
      duplicateSuspects: [],
      partialCopies: [],
      recommendations: [],
    },
    optimizations: [],
  },
};

// Mock react-router-dom hooks
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: 'wf-1' }),
    useSearchParams: () => [new URLSearchParams({ environment: 'development' })],
  };
});

describe('WorkflowDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.resetHandlers();

    // Setup handlers for all required endpoints
    server.use(
      http.get(`${API_BASE}/workflows/wf-1`, () => {
        return HttpResponse.json(mockWorkflow);
      }),
      http.get(`${API_BASE}/workflows/:id/drift`, () => {
        return HttpResponse.json({ data: { has_drift: false } });
      }),
      http.get(`${API_BASE}/environments`, () => {
        return HttpResponse.json([
          {
            id: 'env-1',
            tenant_id: 'tenant-1',
            n8n_name: 'Development',
            n8n_type: 'development',
            n8n_base_url: 'https://dev.example.com',
            is_active: true,
          },
        ]);
      }),
      http.get(`${API_BASE}/executions`, () => {
        return HttpResponse.json([]);
      }),
      http.get(`${API_BASE}/admin/credentials/workflows/:id/dependencies`, () => {
        return HttpResponse.json({ credentials: [] });
      }),
      http.get(`${API_BASE}/auth/status`, () => {
        return HttpResponse.json({
          authenticated: true,
          onboarding_required: false,
          has_environment: true,
          user: { id: 'user-1', email: 'test@test.com', name: 'Test', role: 'admin' },
          tenant: { id: 'tenant-1', name: 'Test Org', subscription_tier: 'pro' },
          entitlements: { plan_name: 'pro', features: {} },
        });
      })
    );
  });

  describe('Loading State', () => {
    it('should show loading state initially', async () => {
      server.use(
        http.get(`${API_BASE}/workflows/wf-1`, async () => {
          await new Promise((r) => setTimeout(r, 100));
          return HttpResponse.json(mockWorkflow);
        })
      );

      render(<WorkflowDetailPage />);
      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
  });

  describe('Success State', () => {
    it('should display workflow name after loading', async () => {
      render(<WorkflowDetailPage />);

      await waitFor(
        () => {
          expect(screen.getByText('Test Workflow')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });

    it('should display page title', async () => {
      render(<WorkflowDetailPage />);

      await waitFor(
        () => {
          expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('Error State', () => {
    it('should handle workflow not found', async () => {
      server.use(
        http.get(`${API_BASE}/workflows/wf-1`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'Not found' }), { status: 404 });
        })
      );

      render(<WorkflowDetailPage />);

      await waitFor(
        () => {
          expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });

    it('should handle API errors gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/workflows/wf-1`, () => {
          return new HttpResponse(null, { status: 500 });
        })
      );

      render(<WorkflowDetailPage />);

      await waitFor(
        () => {
          expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('Tabs', () => {
    it('should display tab navigation', async () => {
      render(<WorkflowDetailPage />);

      await waitFor(
        () => {
          expect(screen.getByText('Test Workflow')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByRole('tab', { name: /overview/i })).toBeInTheDocument();
    });

    it('should display analysis tab', async () => {
      render(<WorkflowDetailPage />);

      await waitFor(
        () => {
          expect(screen.getByText('Test Workflow')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByRole('tab', { name: /analysis/i })).toBeInTheDocument();
    });

    it('should display governance tab', async () => {
      render(<WorkflowDetailPage />);

      await waitFor(
        () => {
          expect(screen.getByText('Test Workflow')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByRole('tab', { name: /governance/i })).toBeInTheDocument();
    });
  });

  describe('Actions', () => {
    it('should have workflow action buttons', async () => {
      render(<WorkflowDetailPage />);

      await waitFor(
        () => {
          expect(screen.getByText('Test Workflow')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(1);
    });
  });

  describe('Workflow Tags', () => {
    it('should display workflow tags', async () => {
      render(<WorkflowDetailPage />);

      await waitFor(
        () => {
          expect(screen.getByText('Test Workflow')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByText('production')).toBeInTheDocument();
    });
  });

  describe('Environment Context', () => {
    it('should render workflow in environment context', async () => {
      render(<WorkflowDetailPage />);

      await waitFor(
        () => {
          expect(screen.getByText('Test Workflow')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });
});
