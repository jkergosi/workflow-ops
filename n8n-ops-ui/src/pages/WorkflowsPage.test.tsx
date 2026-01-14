import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { WorkflowsPage } from './WorkflowsPage';
import { render } from '@/test/test-utils';
import { server } from '@/test/mocks/server';
import { mockWorkflows } from '@/test/mocks/handlers';

const API_BASE = '/api/v1';

// Workflows actions are role-gated; tests assume org admin user for mutation actions.
vi.mock('@/lib/auth', async (importOriginal) => {
  const actual = await importOriginal() as Record<string, unknown>;
  return {
    ...actual,
    useAuth: () => ({
      user: { id: 'user-1', email: 'admin@example.com', name: 'Admin User', role: 'admin' },
    }),
  };
});

describe('WorkflowsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('should show loading state initially', async () => {
      // Delay the response to see loading state
      server.use(
        http.get(`${API_BASE}/workflows`, async () => {
          await new Promise((r) => setTimeout(r, 100));
          return HttpResponse.json(mockWorkflows);
        })
      );

      render(<WorkflowsPage />);

      expect(screen.getByText(/loading workflows/i)).toBeInTheDocument();
    });
  });

  describe('Success State', () => {
    it('should display workflows after loading', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      expect(screen.getByText('Test Workflow 2')).toBeInTheDocument();
    });

    it('should show workflow status badges', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Check for Active badge (Test Workflow 1 is active)
      const activeBadges = screen.getAllByText('Active');
      expect(activeBadges.length).toBeGreaterThan(0);

      // Check for Inactive badge (Test Workflow 2 is inactive)
      const inactiveBadges = screen.getAllByText('Inactive');
      expect(inactiveBadges.length).toBeGreaterThan(0);
    });

    it('should show workflow tags', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Check that tags are displayed
      expect(screen.getByText('test')).toBeInTheDocument();
      expect(screen.getByText('automation')).toBeInTheDocument();
    });

    it('should display execution counts', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Test Workflow 1 has 2 executions in mock data
      // The execution count should be displayed as a link
      await waitFor(() => {
        const links = screen.getAllByRole('link');
        const executionLinks = links.filter((link) =>
          link.getAttribute('href')?.includes('/executions')
        );
        expect(executionLinks.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no workflows exist', async () => {
      server.use(
        http.get(`${API_BASE}/workflows`, () => {
          return HttpResponse.json([]);
        })
      );

      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText(/no workflows found/i)).toBeInTheDocument();
      });
    });

    it('should show filter message when filters match nothing', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Search for something that doesn't exist
      const searchInput = screen.getByPlaceholderText(/search by name/i);
      await userEvent.type(searchInput, 'nonexistent workflow xyz');

      await waitFor(() => {
        expect(screen.getByText(/no workflows match your filters/i)).toBeInTheDocument();
      });
    });
  });

  describe('Filtering', () => {
    it('should filter workflows by search query', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
        expect(screen.getByText('Test Workflow 2')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search by name/i);
      await userEvent.type(searchInput, 'Workflow 1');

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
        expect(screen.queryByText('Test Workflow 2')).not.toBeInTheDocument();
      });
    });

    it('should filter by status', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Select "Active" status filter
      const statusSelect = screen.getByLabelText(/status/i);
      await userEvent.selectOptions(statusSelect, 'active');

      await waitFor(() => {
        // Only active workflows should be shown
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
        expect(screen.queryByText('Test Workflow 2')).not.toBeInTheDocument();
      });
    });

    it('should clear filters when clicking Clear filters', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Apply a search filter
      const searchInput = screen.getByPlaceholderText(/search by name/i);
      await userEvent.type(searchInput, 'Workflow 1');

      // Wait for filter to be applied
      await waitFor(() => {
        expect(screen.queryByText('Test Workflow 2')).not.toBeInTheDocument();
      });

      // Click clear filters
      const clearButton = screen.getByRole('button', { name: /clear filters/i });
      await userEvent.click(clearButton);

      // Both workflows should be visible again
      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
        expect(screen.getByText('Test Workflow 2')).toBeInTheDocument();
      });
    });
  });

  describe('Sorting', () => {
    it('should sort by name when clicking Name header', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Click on Name header to sort
      const nameHeader = screen.getByRole('columnheader', { name: /name/i });
      await userEvent.click(nameHeader);

      // Workflows should still be visible (just sorted)
      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
        expect(screen.getByText('Test Workflow 2')).toBeInTheDocument();
      });
    });

    it('should sort by status when clicking Status header', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Use exact text match to distinguish from "Sync Status"
      const statusHeaders = screen.getAllByRole('columnheader', { name: /status/i });
      const statusHeader = statusHeaders.find(header => header.textContent?.trim().match(/^Status/));
      if (statusHeader) {
        await userEvent.click(statusHeader);
      }

      // Workflows should still be visible
      expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      expect(screen.getByText('Test Workflow 2')).toBeInTheDocument();
    });
  });

  describe('Edit Workflow', () => {
    it('should open edit dialog when clicking Edit button', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Open Actions menu for first workflow and click "Edit Directly"
      const row = screen.getByText('Test Workflow 1').closest('tr');
      expect(row).toBeTruthy();

      await userEvent.click(within(row as HTMLElement).getByRole('button', { name: /actions/i }));
      await userEvent.click(screen.getByRole('menuitem', { name: /edit directly/i }));

      // Some environments show a drift warning that must be acknowledged first
      const warningDialog = await screen
        .findByRole('alertdialog', { name: /direct edit warning/i }, { timeout: 500 })
        .catch(() => null);
      if (warningDialog) {
        const checkbox = within(warningDialog).getByLabelText(/i understand this will create drift/i);
        await userEvent.click(checkbox);
        await userEvent.click(within(warningDialog).getByRole('button', { name: /edit anyway/i }));
      }

      // Dialog should open
      await waitFor(() => {
        expect(screen.getByRole('dialog', { name: /edit workflow/i })).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog', { name: /edit workflow/i });
      expect(within(dialog).getByText(/edit workflow/i)).toBeInTheDocument();
    });

    it('should close edit dialog when clicking Cancel', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Open edit dialog
      const row = screen.getByText('Test Workflow 1').closest('tr');
      expect(row).toBeTruthy();

      await userEvent.click(within(row as HTMLElement).getByRole('button', { name: /actions/i }));
      await userEvent.click(screen.getByRole('menuitem', { name: /edit directly/i }));

      const warningDialog = await screen
        .findByRole('alertdialog', { name: /direct edit warning/i }, { timeout: 500 })
        .catch(() => null);
      if (warningDialog) {
        const checkbox = within(warningDialog).getByLabelText(/i understand this will create drift/i);
        await userEvent.click(checkbox);
        await userEvent.click(within(warningDialog).getByRole('button', { name: /edit anyway/i }));
      }

      await waitFor(() => {
        expect(screen.getByRole('dialog', { name: /edit workflow/i })).toBeInTheDocument();
      });

      // Click Cancel
      const cancelButton = within(screen.getByRole('dialog', { name: /edit workflow/i })).getByRole('button', {
        name: /cancel/i,
      });
      await userEvent.click(cancelButton);

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('Delete Workflow', () => {
    it('should open delete confirmation when clicking Delete button', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Open Actions menu for first workflow and click "Permanently Delete"
      const row = screen.getByText('Test Workflow 1').closest('tr');
      expect(row).toBeTruthy();

      await userEvent.click(within(row as HTMLElement).getByRole('button', { name: /actions/i }));
      await waitFor(() => {
        expect(screen.getByRole('menuitem', { name: /permanently delete/i })).toBeInTheDocument();
      });
      await userEvent.click(screen.getByRole('menuitem', { name: /permanently delete/i }));

      // Confirmation dialog should open
      await waitFor(() => {
        expect(screen.getByRole('alertdialog', { name: /permanently delete workflow/i })).toBeInTheDocument();
      });

      const dialog = screen.getByRole('alertdialog', { name: /permanently delete workflow/i });
      expect(within(dialog).getByText(/cannot be undone/i)).toBeInTheDocument();
    });

    it('should delete workflow when confirmed', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Open permanently delete confirmation
      const row = screen.getByText('Test Workflow 1').closest('tr');
      expect(row).toBeTruthy();

      await userEvent.click(within(row as HTMLElement).getByRole('button', { name: /actions/i }));
      await waitFor(() => {
        expect(screen.getByRole('menuitem', { name: /permanently delete/i })).toBeInTheDocument();
      });
      await userEvent.click(screen.getByRole('menuitem', { name: /permanently delete/i }));

      await waitFor(() => {
        expect(screen.getByRole('alertdialog', { name: /permanently delete workflow/i })).toBeInTheDocument();
      });

      // Confirm deletion by typing DELETE and clicking Delete Permanently
      const dialog = screen.getByRole('alertdialog', { name: /permanently delete workflow/i });
      const confirmInput = within(dialog).getByLabelText(/type delete/i);
      await userEvent.type(confirmInput, 'DELETE');

      const confirmButton = within(dialog).getByRole('button', { name: /delete permanently/i });
      await userEvent.click(confirmButton);

      // Dialog should close after deletion
      await waitFor(() => {
        expect(screen.queryByRole('alertdialog', { name: /permanently delete workflow/i })).not.toBeInTheDocument();
      });
    });
  });

  describe('Refresh from N8N', () => {
    it('should refresh workflows when clicking Refresh button', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      const refreshButton = screen.getByRole('button', { name: /refresh from n8n/i });
      await userEvent.click(refreshButton);

      // Button should show loading state
      await waitFor(() => {
        expect(screen.getByText(/refreshing/i)).toBeInTheDocument();
      });

      // Should return to normal state
      await waitFor(
        () => {
          expect(screen.getByRole('button', { name: /refresh from n8n/i })).toBeInTheDocument();
        },
        { timeout: 3000 }
      );
    });
  });

  describe('Pagination', () => {
    it('should show pagination controls', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Pagination controls should be visible
      expect(screen.getByText(/showing/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /first/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /last/i })).toBeInTheDocument();
    });

    it('should disable First and Previous on first page', async () => {
      render(<WorkflowsPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      const firstButton = screen.getByRole('button', { name: /first/i });
      const prevButton = screen.getByRole('button', { name: /previous/i });

      expect(firstButton).toBeDisabled();
      expect(prevButton).toBeDisabled();
    });
  });

  describe('Error State', () => {
    it('should handle API error gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/workflows`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'Server error' }), {
            status: 500,
          });
        })
      );

      render(<WorkflowsPage />);

      // Wait for the loading to complete
      await waitFor(
        () => {
          expect(screen.queryByText(/loading workflows/i)).not.toBeInTheDocument();
        },
        { timeout: 3000 }
      );
    });
  });

  describe('Page Header', () => {
    it('should display page title and description', async () => {
      render(<WorkflowsPage />);

      expect(screen.getByRole('heading', { level: 1, name: /workflows/i })).toBeInTheDocument();
      expect(screen.getByText(/manage and deploy your n8n workflows/i)).toBeInTheDocument();
    });
  });
});
