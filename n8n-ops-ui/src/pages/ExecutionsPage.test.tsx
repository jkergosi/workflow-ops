import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { ExecutionsPage } from './ExecutionsPage';
import { render } from '@/test/test-utils';
import { server } from '@/test/mocks/server';
// mockEnvironments imported for type reference if needed
// import { mockEnvironments } from '@/test/mocks/handlers';

const API_BASE = '/api/v1';

const mockExecutions = [
  {
    id: 'exec-1',
    workflowId: 'wf-1',
    workflowName: 'Test Workflow 1',
    status: 'success',
    startedAt: '2024-01-15T10:00:00Z',
    stoppedAt: '2024-01-15T10:01:00Z',
    executionTime: 60000,
  },
  {
    id: 'exec-2',
    workflowId: 'wf-2',
    workflowName: 'Test Workflow 2',
    status: 'error',
    startedAt: '2024-01-15T09:00:00Z',
    stoppedAt: '2024-01-15T09:00:30Z',
    executionTime: 30000,
  },
  {
    id: 'exec-3',
    workflowId: 'wf-1',
    workflowName: 'Test Workflow 1',
    status: 'running',
    startedAt: '2024-01-15T11:00:00Z',
    stoppedAt: null,
    executionTime: null,
  },
];

describe('ExecutionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.use(
      http.get(`${API_BASE}/executions`, () => {
        return HttpResponse.json(mockExecutions);
      })
    );
  });

  describe('Loading State', () => {
    it('should show loading state initially', async () => {
      server.use(
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
        http.get(`${API_BASE}/executions`, async () => {
          await new Promise((r) => setTimeout(r, 100));
          return HttpResponse.json(mockExecutions);
        })
      );

      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText(/loading executions/i)).toBeInTheDocument();
      });
    });
  });

  describe('Success State', () => {
    it('should display page heading', async () => {
      render(<ExecutionsPage />);

      expect(screen.getByRole('heading', { level: 1, name: /executions/i })).toBeInTheDocument();
    });

    it('should display executions after loading', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Test Workflow 1').length).toBeGreaterThan(0);
      });

      expect(screen.getAllByText('Test Workflow 2').length).toBeGreaterThan(0);
    });

    it('should show execution status badges', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Test Workflow 1').length).toBeGreaterThan(0);
      });

      // Check for status badges
      const successBadges = screen.getAllByText(/success/i);
      expect(successBadges.length).toBeGreaterThan(0);

      const errorBadges = screen.getAllByText(/error/i);
      expect(errorBadges.length).toBeGreaterThan(0);
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no executions exist', async () => {
      server.use(
        http.get(`${API_BASE}/executions`, () => {
          return HttpResponse.json([]);
        })
      );

      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getByText(/no executions/i)).toBeInTheDocument();
      });
    });
  });

  describe('Filtering', () => {
    it('should filter executions by status', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Test Workflow 1').length).toBeGreaterThan(0);
      });

      // Select status filter
      const statusSelect = screen.getByLabelText(/status/i);
      await userEvent.selectOptions(statusSelect, 'success');

      await waitFor(() => {
        // Success executions should be visible
        const rows = screen.getAllByRole('row');
        expect(rows.length).toBeGreaterThan(1);
      });
    });

    it('should have search input', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Test Workflow 1').length).toBeGreaterThan(0);
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      expect(searchInput).toBeInTheDocument();
    });
  });

  describe('Sorting', () => {
    it('should have sortable column headers', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Test Workflow 1').length).toBeGreaterThan(0);
      });

      // Check for sortable headers
      const workflowHeader = screen.getByRole('columnheader', { name: /workflow/i });
      expect(workflowHeader).toBeInTheDocument();
    });
  });

  describe('Pagination', () => {
    it('should show pagination controls', async () => {
      render(<ExecutionsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Test Workflow 1').length).toBeGreaterThan(0);
      });

      expect(screen.getByText(/showing/i)).toBeInTheDocument();
    });
  });

  describe('Environment Selection', () => {
    it('should have environment selector', async () => {
      render(<ExecutionsPage />);

      const environmentSelect = screen.getByLabelText(/environment/i);
      expect(environmentSelect).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should handle API error gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/executions`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'Server error' }), {
            status: 500,
          });
        })
      );

      render(<ExecutionsPage />);

      await waitFor(
        () => {
          expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
        },
        { timeout: 3000 }
      );
    });
  });
});
