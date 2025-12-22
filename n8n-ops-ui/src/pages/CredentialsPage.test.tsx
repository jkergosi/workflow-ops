import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { CredentialsPage } from './CredentialsPage';

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
  },
];

const mockCredentials = [
  {
    id: 'cred-1',
    tenant_id: 'tenant-1',
    n8n_credential_id: 'n8n-cred-1',
    name: 'Slack Production',
    type: 'slackApi',
    environment_id: 'env-2',
    environment: {
      id: 'env-2',
      name: 'Production',
      type: 'production',
      n8n_base_url: 'https://prod.n8n.example.com',
    },
    used_by_workflows: [
      { id: 'wf-1', name: 'Notification Workflow', n8n_workflow_id: 'n8n-wf-1' },
      { id: 'wf-2', name: 'Alert Workflow', n8n_workflow_id: 'n8n-wf-2' },
    ],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-15T00:00:00Z',
  },
  {
    id: 'cred-2',
    tenant_id: 'tenant-1',
    n8n_credential_id: 'n8n-cred-2',
    name: 'GitHub API Token',
    type: 'githubApi',
    environment_id: 'env-1',
    environment: {
      id: 'env-1',
      name: 'Development',
      type: 'development',
      n8n_base_url: 'https://dev.n8n.example.com',
    },
    used_by_workflows: [
      { id: 'wf-3', name: 'CI/CD Workflow', n8n_workflow_id: 'n8n-wf-3' },
    ],
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-16T00:00:00Z',
  },
  {
    id: 'cred-3',
    tenant_id: 'tenant-1',
    n8n_credential_id: 'n8n-cred-3',
    name: 'PostgreSQL Dev DB',
    type: 'postgresApi',
    environment_id: 'env-1',
    environment: {
      id: 'env-1',
      name: 'Development',
      type: 'development',
      n8n_base_url: 'https://dev.n8n.example.com',
    },
    used_by_workflows: [],
    created_at: '2024-01-03T00:00:00Z',
    updated_at: '2024-01-17T00:00:00Z',
  },
];

describe('CredentialsPage', () => {
  beforeEach(() => {
    server.resetHandlers();

    server.use(
      http.get(`${API_BASE}/credentials`, () => {
        return HttpResponse.json(mockCredentials);
      }),
      http.get(`${API_BASE}/environments`, () => {
        return HttpResponse.json(mockEnvironments);
      }),
      http.post(`${API_BASE}/credentials`, () => {
        return HttpResponse.json({
          id: 'cred-new',
          name: 'New Credential',
          type: 'slackApi',
          environment_id: 'env-1',
        }, { status: 201 });
      }),
      http.patch(`${API_BASE}/credentials/:id`, () => {
        return HttpResponse.json({
          ...mockCredentials[0],
          name: 'Updated Credential',
        });
      }),
      http.delete(`${API_BASE}/credentials/:id`, () => {
        return new HttpResponse(null, { status: 204 });
      }),
      http.post(`${API_BASE}/environments/:id/sync-credentials`, () => {
        return HttpResponse.json({ synced: 5 });
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
            features: {},
          },
        });
      })
    );
  });

  describe('Loading State', () => {
    it('should show loading message while fetching credentials', async () => {
      server.use(
        http.get(`${API_BASE}/credentials`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockCredentials);
        })
      );

      render(<CredentialsPage />);

      expect(screen.getByText(/loading credentials/i)).toBeInTheDocument();
    });
  });

  describe('Success State', () => {
    it('should display page heading', async () => {
      render(<CredentialsPage />);

      expect(screen.getByRole('heading', { level: 1, name: /credentials/i })).toBeInTheDocument();
    });

    it('should display page description', async () => {
      render(<CredentialsPage />);

      expect(screen.getByText(/manage physical credentials/i)).toBeInTheDocument();
    });

    it('should display Refresh button', async () => {
      render(<CredentialsPage />);

      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });

    it('should display Sync from N8N button', async () => {
      render(<CredentialsPage />);

      expect(screen.getByRole('button', { name: /sync from n8n/i })).toBeInTheDocument();
    });

    it('should display Create Physical Credential button', async () => {
      render(<CredentialsPage />);

      expect(screen.getByRole('button', { name: /create physical credential/i })).toBeInTheDocument();
    });

    it('should display Credentials card', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('Credentials').length).toBeGreaterThan(0);
      });
    });

    it('should display credentials in the table', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      expect(screen.getByText('GitHub API Token')).toBeInTheDocument();
      expect(screen.getByText('PostgreSQL Dev DB')).toBeInTheDocument();
    });

    it('should display credential types', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        // formatNodeType('slackApi') returns "Slack Api"
        // Types appear both in table and in the type filter dropdown
        expect(screen.getAllByText(/slack api/i).length).toBeGreaterThanOrEqual(1);
      });

      // formatNodeType('githubApi') returns "Github Api"
      expect(screen.getAllByText(/github api/i).length).toBeGreaterThanOrEqual(1);
      // formatNodeType('postgresApi') returns "Postgres Api"
      expect(screen.getAllByText(/postgres api/i).length).toBeGreaterThanOrEqual(1);
    });

    it('should display environment badges', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getAllByText('production').length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.getAllByText('development').length).toBeGreaterThanOrEqual(1);
    });

    it('should display workflow links for credentials', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Notification Workflow')).toBeInTheDocument();
      });

      expect(screen.getByText('Alert Workflow')).toBeInTheDocument();
      expect(screen.getByText('CI/CD Workflow')).toBeInTheDocument();
    });

    it('should display info banner about credential security', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText(/credential secrets are encrypted/i)).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no credentials exist', async () => {
      server.use(
        http.get(`${API_BASE}/credentials`, () => {
          return HttpResponse.json([]);
        })
      );

      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText(/no credentials found/i)).toBeInTheDocument();
      });
    });

    it('should show create first credential button in empty state', async () => {
      server.use(
        http.get(`${API_BASE}/credentials`, () => {
          return HttpResponse.json([]);
        })
      );

      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /create your first credential/i })).toBeInTheDocument();
      });
    });
  });

  describe('Filters', () => {
    it('should have search input', async () => {
      render(<CredentialsPage />);

      expect(screen.getByPlaceholderText(/search by name or type/i)).toBeInTheDocument();
    });

    it('should filter credentials by search query', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search by name or type/i);
      await user.type(searchInput, 'GitHub');

      await waitFor(() => {
        expect(screen.getByText('GitHub API Token')).toBeInTheDocument();
        expect(screen.queryByText('Slack Production')).not.toBeInTheDocument();
      });
    });

    it('should show no results message when filters match nothing', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search by name or type/i);
      await user.type(searchInput, 'nonexistent credential xyz');

      await waitFor(() => {
        expect(screen.getByText(/no credentials match your filters/i)).toBeInTheDocument();
      });
    });

    it('should have environment filter dropdown', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      // Check for environment filter
      const environmentSelect = screen.getByDisplayValue('All Environments');
      expect(environmentSelect).toBeInTheDocument();
    });

    it('should have type filter dropdown', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      // Check for type filter
      const typeSelect = screen.getByDisplayValue('All Types');
      expect(typeSelect).toBeInTheDocument();
    });
  });

  describe('Sorting', () => {
    it('should have sortable column headers', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      const table = screen.getByRole('table');
      expect(within(table).getByText('Name')).toBeInTheDocument();
      expect(within(table).getByText('Type')).toBeInTheDocument();
      expect(within(table).getByText('Environment')).toBeInTheDocument();
    });

    it('should sort credentials when clicking column header', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      const table = screen.getByRole('table');
      const nameHeader = within(table).getByText('Name');
      await user.click(nameHeader);

      // Credentials should still be displayed (just sorted)
      expect(screen.getByText('Slack Production')).toBeInTheDocument();
    });
  });

  describe('User Interactions - Create Physical Credential', () => {
    it('should open create dialog when clicking Create Physical Credential button', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create physical credential/i });
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByText(/create physical credential/i)).toBeInTheDocument();
    });

    it('should have name input in create dialog', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create physical credential/i });
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    });

    it('should have environment selector in create dialog', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create physical credential/i });
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByText(/environment/i)).toBeInTheDocument();
    });

    it('should have type selector in create dialog', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create physical credential/i });
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      // "Type" appears as a label in the dialog
      expect(within(dialog).getAllByText(/type/i).length).toBeGreaterThanOrEqual(1);
    });

    it('should close create dialog when clicking Cancel', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      const createButton = screen.getByRole('button', { name: /create physical credential/i });
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const cancelButton = within(screen.getByRole('dialog')).getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('User Interactions - Edit Physical Credential', () => {
    it('should have dropdown menu with Edit option for each credential', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      // Click the dropdown menu trigger
      const menuTriggers = screen.getAllByRole('button', { name: '' });
      const dropdownTrigger = menuTriggers.find(btn => btn.querySelector('svg'));
      if (dropdownTrigger) {
        await user.click(dropdownTrigger);
      }

      await waitFor(() => {
        expect(screen.getByText('Edit')).toBeInTheDocument();
      });
    });

    it('should open edit dialog when clicking Edit', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      // Click the dropdown menu trigger
      const menuTriggers = screen.getAllByRole('button', { name: '' });
      const dropdownTrigger = menuTriggers.find(btn => btn.querySelector('svg'));
      if (dropdownTrigger) {
        await user.click(dropdownTrigger);
      }

      await waitFor(() => {
        expect(screen.getByText('Edit')).toBeInTheDocument();
      });

      const editMenuItem = screen.getByText('Edit');
      await user.click(editMenuItem);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByText(/edit physical credential/i)).toBeInTheDocument();
    });
  });

  describe('User Interactions - Delete Physical Credential', () => {
    it('should have dropdown menu with Delete option for each credential', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      // Click the dropdown menu trigger
      const menuTriggers = screen.getAllByRole('button', { name: '' });
      const dropdownTrigger = menuTriggers.find(btn => btn.querySelector('svg'));
      if (dropdownTrigger) {
        await user.click(dropdownTrigger);
      }

      await waitFor(() => {
        expect(screen.getByText('Delete')).toBeInTheDocument();
      });
    });

    it('should open delete confirmation dialog', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      // Click the dropdown menu trigger
      const menuTriggers = screen.getAllByRole('button', { name: '' });
      const dropdownTrigger = menuTriggers.find(btn => btn.querySelector('svg'));
      if (dropdownTrigger) {
        await user.click(dropdownTrigger);
      }

      await waitFor(() => {
        expect(screen.getByText('Delete')).toBeInTheDocument();
      });

      const deleteMenuItem = screen.getByText('Delete');
      await user.click(deleteMenuItem);

      await waitFor(() => {
        expect(screen.getByRole('alertdialog')).toBeInTheDocument();
      });

      expect(screen.getByText(/delete physical credential/i)).toBeInTheDocument();
    });

    it('should show warning for credentials used by workflows', async () => {
      const user = userEvent.setup();
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      // Click the dropdown menu trigger for first credential (used by 2 workflows)
      const menuTriggers = screen.getAllByRole('button', { name: '' });
      const dropdownTrigger = menuTriggers.find(btn => btn.querySelector('svg'));
      if (dropdownTrigger) {
        await user.click(dropdownTrigger);
      }

      await waitFor(() => {
        expect(screen.getByText('Delete')).toBeInTheDocument();
      });

      const deleteMenuItem = screen.getByText('Delete');
      await user.click(deleteMenuItem);

      await waitFor(() => {
        expect(screen.getByRole('alertdialog')).toBeInTheDocument();
      });

      // The warning text appears in the alert dialog
      // "used by" appears in both table and warning - use getAllByText
      expect(screen.getAllByText(/used by.*workflow/i).length).toBeGreaterThanOrEqual(1);
    });

    it('should delete credential when confirmed', async () => {
      const user = userEvent.setup();
      let deleteCalled = false;

      server.use(
        http.delete(`${API_BASE}/credentials/:id`, () => {
          deleteCalled = true;
          return new HttpResponse(null, { status: 204 });
        })
      );

      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      // Click the dropdown menu trigger
      const menuTriggers = screen.getAllByRole('button', { name: '' });
      const dropdownTrigger = menuTriggers.find(btn => btn.querySelector('svg'));
      if (dropdownTrigger) {
        await user.click(dropdownTrigger);
      }

      await waitFor(() => {
        expect(screen.getByText('Delete')).toBeInTheDocument();
      });

      const deleteMenuItem = screen.getByText('Delete');
      await user.click(deleteMenuItem);

      await waitFor(() => {
        expect(screen.getByRole('alertdialog')).toBeInTheDocument();
      });

      const alertDialog = screen.getByRole('alertdialog');
      const confirmButton = within(alertDialog).getByRole('button', { name: /delete/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(deleteCalled).toBe(true);
      });
    });
  });

  describe('Table Structure', () => {
    it('should display table with correct column headers', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      const table = screen.getByRole('table');
      expect(within(table).getByText('Name')).toBeInTheDocument();
      expect(within(table).getByText('Type')).toBeInTheDocument();
      expect(within(table).getByText('Environment')).toBeInTheDocument();
      expect(within(table).getByText('Used by Workflows')).toBeInTheDocument();
      expect(within(table).getByText('Actions')).toBeInTheDocument();
    });
  });

  describe('Results Count', () => {
    it('should display showing X of Y credentials', async () => {
      render(<CredentialsPage />);

      await waitFor(() => {
        expect(screen.getByText('Slack Production')).toBeInTheDocument();
      });

      expect(screen.getByText(/showing 3 of 3 credentials/i)).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should handle server error gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/credentials`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'Internal server error' }), {
            status: 500,
          });
        })
      );

      render(<CredentialsPage />);

      // Page should not crash
      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1, name: /credentials/i })).toBeInTheDocument();
      });
    });
  });
});
