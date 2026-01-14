import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { TeamPage } from './TeamPage';

const API_BASE = '/api/v1';

// Mock team members for different scenarios
const mockTeamMembers = [
  {
    id: 'user-1',
    email: 'admin@example.com',
    name: 'Admin User',
    role: 'admin',
    status: 'active',
    createdAt: '2024-01-01T00:00:00Z',
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'user-2',
    email: 'dev@example.com',
    name: 'Developer',
    role: 'developer',
    status: 'active',
    createdAt: '2024-01-02T00:00:00Z',
    created_at: '2024-01-02T00:00:00Z',
  },
  {
    id: 'user-3',
    email: 'pending@example.com',
    name: 'Pending User',
    role: 'viewer',
    status: 'pending',
    createdAt: '2024-01-03T00:00:00Z',
    created_at: '2024-01-03T00:00:00Z',
  },
];

const mockTeamLimits = {
  max_members: 10,
  current_members: 3,
  can_add_more: true,
};

describe('TeamPage', () => {
  beforeEach(() => {
    // Reset to default handlers
    server.resetHandlers();

    // Set up default team handlers
    server.use(
      http.get(`${API_BASE}/teams/`, () => {
        return HttpResponse.json(mockTeamMembers);
      }),
      http.get(`${API_BASE}/teams/limits`, () => {
        return HttpResponse.json(mockTeamLimits);
      })
    );
  });

  describe('Loading State', () => {
    it('should show loading message while fetching team members', async () => {
      // Use a delayed response to see loading state
      server.use(
        http.get(`${API_BASE}/teams/`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockTeamMembers);
        })
      );

      render(<TeamPage />);

      // Should show loading text
      expect(screen.getByText(/loading team members/i)).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no team members exist', async () => {
      server.use(
        http.get(`${API_BASE}/teams/`, () => {
          return HttpResponse.json([]);
        })
      );

      render(<TeamPage />);

      await waitFor(() => {
        expect(
          screen.getByText(/no team members yet/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('Success State', () => {
    it('should display team members in a table', async () => {
      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Check all team members are displayed
      expect(screen.getByText('admin@example.com')).toBeInTheDocument();
      expect(screen.getByText('Developer')).toBeInTheDocument();
      expect(screen.getByText('dev@example.com')).toBeInTheDocument();
      expect(screen.getByText('Pending User')).toBeInTheDocument();
    });

    it('should display role badges for each member', async () => {
      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Check role badges exist
      expect(screen.getByText('admin')).toBeInTheDocument();
      expect(screen.getByText('developer')).toBeInTheDocument();
      expect(screen.getByText('viewer')).toBeInTheDocument();
    });

    it('should display status badges for each member', async () => {
      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Check status badges exist (active appears multiple times)
      const activeBadges = screen.getAllByText('active');
      expect(activeBadges.length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText('pending')).toBeInTheDocument();
    });

    it('should display team limits card', async () => {
      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText(/team members: 3/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/7 slots remaining/i)).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should handle server error gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/teams/`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'Internal server error' }), {
            status: 500,
          });
        })
      );

      render(<TeamPage />);

      // After loading completes, should not crash
      await waitFor(() => {
        // The page should still render the structure - use heading level 1
        expect(screen.getByRole('heading', { level: 1, name: /team/i })).toBeInTheDocument();
      });
    });
  });

  describe('User Interactions - Invite Member', () => {
    it('should open invite dialog when clicking Invite Member button', async () => {
      const user = userEvent.setup();
      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Click invite button
      const inviteButton = screen.getByRole('button', { name: /invite member/i });
      await user.click(inviteButton);

      // Dialog should open
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/invite team member/i)).toBeInTheDocument();
    });

    it('should successfully invite a new team member', async () => {
      const user = userEvent.setup();

      // Mock the create endpoint
      server.use(
        http.post(`${API_BASE}/teams/`, async ({ request }) => {
          const body = await request.json() as { email: string; name: string; role: string };
          return HttpResponse.json({
            id: 'new-user-id',
            email: body.email,
            name: body.name,
            role: body.role,
            status: 'pending',
            createdAt: new Date().toISOString(),
          });
        })
      );

      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Open invite dialog
      const inviteButton = screen.getByRole('button', { name: /invite member/i });
      await user.click(inviteButton);

      // Fill in the form
      const emailInput = screen.getByLabelText(/email address/i);
      const nameInput = screen.getByLabelText(/full name/i);

      await user.type(emailInput, 'newuser@example.com');
      await user.type(nameInput, 'New User');

      // Submit the form
      const sendButton = screen.getByRole('button', { name: /send invitation/i });
      await user.click(sendButton);

      // Dialog should close (wait for mutation to complete)
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    it('should prevent invite when at member limit', async () => {
      const user = userEvent.setup();

      server.use(
        http.get(`${API_BASE}/teams/limits`, () => {
          return HttpResponse.json({
            max_members: 3,
            current_members: 3,
            can_add_more: false,
          });
        })
      );

      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Click invite button
      const inviteButton = screen.getByRole('button', { name: /invite member/i });
      await user.click(inviteButton);

      // Dialog should NOT open - check toast message would appear instead
      // The dialog should not be present
      await waitFor(() => {
        // The page should show upgrade prompt
        expect(screen.getByText(/upgrade to add more members/i)).toBeInTheDocument();
      });
    });
  });

  describe('User Interactions - Edit Member', () => {
    it('should open edit dialog when clicking edit button', async () => {
      const user = userEvent.setup();
      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Find the first edit button
      const editButtons = screen.getAllByRole('button', { name: /edit/i });
      await user.click(editButtons[0]);

      // Dialog should open
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/edit team member/i)).toBeInTheDocument();
    });

    it('should successfully update team member', async () => {
      const user = userEvent.setup();

      server.use(
        http.patch(`${API_BASE}/teams/:id`, async ({ request }) => {
          const body = await request.json() as { name?: string };
          return HttpResponse.json({
            ...mockTeamMembers[0],
            name: body.name || mockTeamMembers[0].name,
          });
        })
      );

      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Open edit dialog
      const editButtons = screen.getAllByRole('button', { name: /edit/i });
      await user.click(editButtons[0]);

      // Wait for dialog to open
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Change the name
      const nameInput = screen.getByLabelText(/full name/i);
      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Admin Name');

      // Save changes
      const saveButton = screen.getByRole('button', { name: /save changes/i });
      await user.click(saveButton);

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('User Interactions - Delete Member', () => {
    it('should open delete confirmation dialog', async () => {
      const user = userEvent.setup();
      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Find the first remove button
      const removeButtons = screen.getAllByRole('button', { name: /remove/i });
      await user.click(removeButtons[0]);

      // Confirmation dialog should open
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/remove team member/i)).toBeInTheDocument();
    });

    it('should successfully delete team member when confirmed', async () => {
      const user = userEvent.setup();

      server.use(
        http.delete(`${API_BASE}/teams/:id`, () => {
          return new HttpResponse(null, { status: 204 });
        })
      );

      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Open delete dialog
      const removeButtons = screen.getAllByRole('button', { name: /remove/i });
      await user.click(removeButtons[0]);

      // Confirm deletion
      const confirmButton = screen.getByRole('button', { name: /yes, remove/i });
      await user.click(confirmButton);

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    it('should cancel deletion when clicking cancel', async () => {
      const user = userEvent.setup();
      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Open delete dialog
      const removeButtons = screen.getAllByRole('button', { name: /remove/i });
      await user.click(removeButtons[0]);

      // Cancel deletion
      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      // Dialog should close
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });

      // User should still be in the list
      expect(screen.getByText('Admin User')).toBeInTheDocument();
    });
  });

  describe('User Interactions - Resend Invite', () => {
    it('should show resend button for pending members', async () => {
      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Pending User')).toBeInTheDocument();
      });

      // Find the row with the pending user
      const pendingRow = screen.getByText('Pending User').closest('tr');
      expect(pendingRow).toBeInTheDocument();

      // Check for resend button in that row
      if (pendingRow) {
        const resendButton = within(pendingRow).getByRole('button', { name: /resend/i });
        expect(resendButton).toBeInTheDocument();
      }
    });

    it('should not show resend button for active members', async () => {
      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText('Admin User')).toBeInTheDocument();
      });

      // Find the row with the active admin user
      const adminRow = screen.getByText('Admin User').closest('tr');
      expect(adminRow).toBeInTheDocument();

      // Check that there's no resend button in that row
      if (adminRow) {
        const resendButton = within(adminRow).queryByRole('button', { name: /resend/i });
        expect(resendButton).not.toBeInTheDocument();
      }
    });
  });

  describe('Permission-gated Behavior', () => {
    it('should show upgrade button when at team limit', async () => {
      server.use(
        http.get(`${API_BASE}/teams/limits`, () => {
          return HttpResponse.json({
            max_members: 3,
            current_members: 3,
            can_add_more: false,
          });
        })
      );

      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /upgrade plan/i })).toBeInTheDocument();
      });
    });

    it('should display limit warning card when at limit', async () => {
      server.use(
        http.get(`${API_BASE}/teams/limits`, () => {
          return HttpResponse.json({
            max_members: 3,
            current_members: 3,
            can_add_more: false,
          });
        })
      );

      render(<TeamPage />);

      await waitFor(() => {
        expect(screen.getByText(/upgrade to add more members/i)).toBeInTheDocument();
      });
    });
  });
});
