import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { RestorePage } from './RestorePage';
import { render } from '@/test/test-utils';
import { server } from '@/test/mocks/server';

const API_BASE = '/api/v1';

const mockPreview = {
  environment_id: 'env-1',
  environment_name: 'Development',
  github_repo: 'org/repo',
  github_branch: 'main',
  total_new: 3,
  total_update: 2,
  has_encryption_key: true,
  workflows: [
    {
      workflow_id: 'wf-1',
      name: 'New Workflow 1',
      status: 'new',
      nodes_count: 5,
    },
    {
      workflow_id: 'wf-2',
      name: 'Existing Workflow',
      status: 'update',
      nodes_count: 10,
    },
    {
      workflow_id: 'wf-3',
      name: 'New Workflow 2',
      status: 'new',
      nodes_count: 3,
    },
  ],
};

// Mock useParams
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: 'env-1' }),
    useNavigate: () => vi.fn(),
  };
});

describe('RestorePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.use(
      http.get(`${API_BASE}/restore/preview/env-1`, () => {
        return HttpResponse.json(mockPreview);
      }),
      http.post(`${API_BASE}/restore/env-1`, () => {
        return HttpResponse.json({
          success: true,
          workflows_created: 3,
          workflows_updated: 2,
          workflows_failed: 0,
          snapshots_created: 2,
          results: [],
          errors: [],
        });
      })
    );
  });

  describe('Loading State', () => {
    it('should show loading state initially', async () => {
      server.use(
        http.get(`${API_BASE}/restore/preview/env-1`, async () => {
          await new Promise((r) => setTimeout(r, 100));
          return HttpResponse.json(mockPreview);
        })
      );

      render(<RestorePage />);

      expect(screen.getByText(/loading restore preview/i)).toBeInTheDocument();
    });
  });

  describe('Success State', () => {
    it('should display page heading', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1, name: /restore from github/i })).toBeInTheDocument();
      });
    });

    it('should display environment name', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText(/development/i)).toBeInTheDocument();
      });
    });

    it('should display back button', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument();
      });
    });
  });

  describe('Source Repository Section', () => {
    it('should display repository info', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText(/source repository/i)).toBeInTheDocument();
      });
    });

    it('should display repository URL', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText('org/repo')).toBeInTheDocument();
      });
    });

    it('should display branch name', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText('main')).toBeInTheDocument();
      });
    });
  });

  describe('Summary Cards', () => {
    it('should display new workflows count', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText(/new workflows/i)).toBeInTheDocument();
      });
    });

    it('should display updates count', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText(/updates/i)).toBeInTheDocument();
      });
    });

    it('should display total selected count', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText(/total selected/i)).toBeInTheDocument();
      });
    });
  });

  describe('Restore Options', () => {
    it('should display restore options section', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText(/restore options/i)).toBeInTheDocument();
      });
    });

    it('should have workflows checkbox', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/workflows/i)).toBeInTheDocument();
      });
    });

    it('should have credentials checkbox', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/credentials/i)).toBeInTheDocument();
      });
    });

    it('should have tags checkbox', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/tags/i)).toBeInTheDocument();
      });
    });

    it('should have create snapshots checkbox', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/create snapshots/i)).toBeInTheDocument();
      });
    });
  });

  describe('Workflows Table', () => {
    it('should display workflows table', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(
          screen.getByRole('heading', { name: /workflows to restore/i })
        ).toBeInTheDocument();
      });
    });

    it('should display workflow names', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText('New Workflow 1')).toBeInTheDocument();
      });

      expect(screen.getByText('Existing Workflow')).toBeInTheDocument();
      expect(screen.getByText('New Workflow 2')).toBeInTheDocument();
    });

    it('should have select all button', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /select all|deselect all/i })).toBeInTheDocument();
      });
    });

    it('should display workflow status badges', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText('New Workflow 1')).toBeInTheDocument();
      });

      expect(screen.getAllByText(/new|update/i).length).toBeGreaterThan(0);
    });
  });

  describe('Actions', () => {
    it('should have restore button', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /restore/i })).toBeInTheDocument();
      });
    });

    it('should have cancel button', async () => {
      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      });
    });
  });

  describe('Error State', () => {
    it('should handle preview error gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/restore/preview/env-1`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'GitHub not configured' }), {
            status: 400,
          });
        })
      );

      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText(/error loading preview|failed to load/i)).toBeInTheDocument();
      });
    });

    it('should have try again button on error', async () => {
      server.use(
        http.get(`${API_BASE}/restore/preview/env-1`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'GitHub not configured' }), {
            status: 400,
          });
        })
      );

      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no workflows found', async () => {
      server.use(
        http.get(`${API_BASE}/restore/preview/env-1`, () => {
          return HttpResponse.json({
            ...mockPreview,
            workflows: [],
            total_new: 0,
            total_update: 0,
          });
        })
      );

      render(<RestorePage />);

      await waitFor(() => {
        expect(screen.getByText(/no workflows found/i)).toBeInTheDocument();
      });
    });
  });
});
