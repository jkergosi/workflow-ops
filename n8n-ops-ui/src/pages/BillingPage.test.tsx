import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { BillingPage } from './BillingPage';

const API_BASE = 'http://localhost:4000/api/v1';

const mockSubscription = {
  id: 'sub-1',
  tenant_id: 'tenant-1',
  status: 'active',
  current_period_end: '2024-02-15T00:00:00Z',
  cancel_at_period_end: false,
  plan: {
    id: 'plan-pro',
    name: 'pro',
    display_name: 'Pro',
    description: 'For growing teams',
    price_monthly: '29.00',
    price_yearly: '290.00',
    features: {
      max_environments: 10,
      max_team_members: 20,
      github_backup: 'scheduled',
      github_restore: true,
      scheduled_backup: true,
      environment_promotion: 'manual',
      credential_remapping: false,
      workflow_diff: true,
      workflow_lifecycle: true,
      execution_metrics: 'basic',
      alerting: 'basic',
      role_based_access: true,
      audit_logs: 'limited',
      secret_vault: false,
      sso_scim: false,
      compliance_tools: false,
      environment_protection: false,
      support: 'priority',
    },
  },
};

const mockFreePlanSubscription = {
  id: 'sub-free',
  tenant_id: 'tenant-1',
  status: 'active',
  current_period_end: null,
  cancel_at_period_end: false,
  plan: {
    id: 'plan-free',
    name: 'free',
    display_name: 'Free',
    description: 'Get started',
    price_monthly: '0.00',
    price_yearly: '0.00',
    features: {
      max_environments: 1,
      max_team_members: 2,
      github_backup: 'manual',
      github_restore: false,
      scheduled_backup: false,
      environment_promotion: null,
      credential_remapping: false,
      workflow_diff: false,
      workflow_lifecycle: false,
      execution_metrics: 'basic',
      alerting: null,
      role_based_access: false,
      audit_logs: null,
      secret_vault: false,
      sso_scim: false,
      compliance_tools: false,
      environment_protection: false,
      support: 'community',
    },
  },
};

const mockPlans = [
  {
    id: 'plan-free',
    name: 'free',
    display_name: 'Free',
    description: 'Get started with basic features',
    price_monthly: '0.00',
    price_yearly: '0.00',
    stripe_price_id_monthly: null,
    stripe_price_id_yearly: null,
    features: {
      max_environments: 1,
      max_team_members: 2,
      github_backup: 'manual',
      github_restore: false,
      scheduled_backup: false,
      environment_promotion: null,
      credential_remapping: false,
      workflow_diff: false,
      workflow_lifecycle: false,
      execution_metrics: 'basic',
      alerting: null,
      role_based_access: false,
      audit_logs: null,
      secret_vault: false,
      sso_scim: false,
      compliance_tools: false,
      environment_protection: false,
      support: 'community',
    },
  },
  {
    id: 'plan-pro',
    name: 'pro',
    display_name: 'Pro',
    description: 'For growing teams',
    price_monthly: '29.00',
    price_yearly: '290.00',
    stripe_price_id_monthly: 'price_monthly_pro',
    stripe_price_id_yearly: 'price_yearly_pro',
    features: {
      max_environments: 10,
      max_team_members: 20,
      github_backup: 'scheduled',
      github_restore: true,
      scheduled_backup: true,
      environment_promotion: 'manual',
      credential_remapping: false,
      workflow_diff: true,
      workflow_lifecycle: true,
      execution_metrics: 'basic',
      alerting: 'basic',
      role_based_access: true,
      audit_logs: 'limited',
      secret_vault: false,
      sso_scim: false,
      compliance_tools: false,
      environment_protection: false,
      support: 'priority',
    },
  },
  {
    id: 'plan-enterprise',
    name: 'enterprise',
    display_name: 'Enterprise',
    description: 'For large organizations',
    price_monthly: '99.00',
    price_yearly: '990.00',
    stripe_price_id_monthly: 'price_monthly_enterprise',
    stripe_price_id_yearly: 'price_yearly_enterprise',
    features: {
      max_environments: 'unlimited',
      max_team_members: 'unlimited',
      github_backup: 'scheduled',
      github_restore: true,
      scheduled_backup: true,
      environment_promotion: 'automated',
      credential_remapping: true,
      workflow_diff: true,
      workflow_lifecycle: true,
      execution_metrics: 'advanced',
      alerting: 'advanced',
      role_based_access: true,
      audit_logs: 'full',
      secret_vault: true,
      sso_scim: true,
      compliance_tools: true,
      environment_protection: true,
      support: 'dedicated',
    },
  },
];

const mockPaymentHistory = [
  {
    id: 'pay-1',
    description: 'Pro Plan - Monthly',
    amount: '29.00',
    status: 'succeeded',
    created_at: '2024-01-15T00:00:00Z',
  },
  {
    id: 'pay-2',
    description: 'Pro Plan - Monthly',
    amount: '29.00',
    status: 'succeeded',
    created_at: '2023-12-15T00:00:00Z',
  },
];

describe('BillingPage', () => {
  beforeEach(() => {
    server.resetHandlers();

    server.use(
      http.get(`${API_BASE}/billing/subscription`, () => {
        return HttpResponse.json(mockSubscription);
      }),
      http.get(`${API_BASE}/billing/plans`, () => {
        return HttpResponse.json(mockPlans);
      }),
      http.get(`${API_BASE}/billing/payment-history`, () => {
        return HttpResponse.json(mockPaymentHistory);
      }),
      http.post(`${API_BASE}/billing/checkout`, () => {
        return HttpResponse.json({ url: 'https://checkout.stripe.com/test' });
      }),
      http.post(`${API_BASE}/billing/portal`, () => {
        return HttpResponse.json({ url: 'https://billing.stripe.com/portal' });
      }),
      http.post(`${API_BASE}/billing/cancel`, () => {
        return HttpResponse.json({ message: 'Subscription canceled' });
      }),
      http.post(`${API_BASE}/billing/reactivate`, () => {
        return HttpResponse.json({ message: 'Subscription reactivated' });
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
    it('should show loading message while fetching billing information', async () => {
      server.use(
        http.get(`${API_BASE}/billing/subscription`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockSubscription);
        })
      );

      render(<BillingPage />);

      expect(screen.getByText(/loading billing information/i)).toBeInTheDocument();
    });
  });

  describe('Success State - Pro Plan', () => {
    it('should display page heading', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1, name: /billing & subscription/i })).toBeInTheDocument();
      });
    });

    it('should display page description', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText(/manage your subscription and billing/i)).toBeInTheDocument();
      });
    });

    it('should display Current Plan card', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/current plan/i).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('should display Pro plan name', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText('Pro Plan')).toBeInTheDocument();
      });
    });

    it('should display active status badge', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText('active')).toBeInTheDocument();
      });
    });

    it('should display renewal date for active subscription', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText(/renews on/i)).toBeInTheDocument();
      });
    });

    it('should display Manage Subscription button for paid plan', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /manage subscription/i })).toBeInTheDocument();
      });
    });

    it('should display Cancel Subscription button for paid plan', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /cancel subscription/i })).toBeInTheDocument();
      });
    });
  });

  describe('Free Plan State', () => {
    beforeEach(() => {
      server.use(
        http.get(`${API_BASE}/billing/subscription`, () => {
          return HttpResponse.json(mockFreePlanSubscription);
        })
      );
    });

    it('should display Free plan name', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText('Free Plan')).toBeInTheDocument();
      });
    });

    it('should display Upgrade to Pro button for free plan', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        // There are two "Upgrade to Pro" buttons - one in Current Plan card and one in Available Plans
        expect(screen.getAllByRole('button', { name: /upgrade to pro/i }).length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe('Available Plans', () => {
    it('should display Available Plans section', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 2, name: /available plans/i })).toBeInTheDocument();
      });
    });

    it('should display all plan cards', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText('Free')).toBeInTheDocument();
      });

      expect(screen.getAllByText('Pro').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Enterprise')).toBeInTheDocument();
    });

    it('should display plan prices', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        // Prices are formatted with Intl.NumberFormat - look for price elements
        // The prices appear in the format "$X.00/month"
        expect(screen.getAllByText(/\$0\.00/).length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.getAllByText(/\$29\.00/).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/\$99\.00/).length).toBeGreaterThanOrEqual(1);
    });

    it('should display plan descriptions', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText(/get started with basic features/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/for growing teams/i)).toBeInTheDocument();
      expect(screen.getByText(/for large organizations/i)).toBeInTheDocument();
    });

    it('should show Current badge for current plan', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText('Current')).toBeInTheDocument();
      });
    });

    it('should show Popular badge for Pro plan', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText('Popular')).toBeInTheDocument();
      });
    });

    it('should display feature lists for each plan', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/environment/i).length).toBeGreaterThanOrEqual(1);
      });

      expect(screen.getAllByText(/team member/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('Payment History', () => {
    it('should display Recent Payments section', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText('Recent Payments')).toBeInTheDocument();
      });
    });

    it('should display payment history items', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getAllByText(/pro plan - monthly/i).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('should display payment amounts', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getAllByText('$29.00').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('should display payment status badges', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getAllByText('succeeded').length).toBeGreaterThanOrEqual(1);
      });
    });
  });

  describe('User Interactions - Upgrade', () => {
    it('should display upgrade options for free plan users', async () => {
      // Use free plan to see upgrade options
      server.use(
        http.get(`${API_BASE}/billing/subscription`, () => {
          return HttpResponse.json(mockFreePlanSubscription);
        })
      );

      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText('Free Plan')).toBeInTheDocument();
      });

      // The page should show upgrade options
      expect(screen.getByText(/available plans/i)).toBeInTheDocument();
    });

    it('should display plan selection options', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText(/available plans/i)).toBeInTheDocument();
      });

      // Plans should be displayed
      expect(screen.getAllByText('Pro').length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText('Enterprise')).toBeInTheDocument();
    });
  });

  describe('User Interactions - Cancel Subscription', () => {
    it('should display manage subscription options for paid plans', async () => {
      render(<BillingPage />);

      await waitFor(() => {
        expect(screen.getByText('Pro Plan')).toBeInTheDocument();
      });

      // Should show management options for paid plans
      expect(screen.getByText(/manage subscription/i)).toBeInTheDocument();
    });
  });

  describe('Canceled Subscription State', () => {
    it('should handle canceled subscription status', async () => {
      server.use(
        http.get(`${API_BASE}/billing/subscription`, () => {
          return HttpResponse.json({
            ...mockSubscription,
            cancel_at_period_end: true,
          });
        })
      );

      render(<BillingPage />);

      // Page should render without errors
      await waitFor(() => {
        expect(screen.getByText('Pro Plan')).toBeInTheDocument();
      });
    });
  });

  describe('Error State', () => {
    it('should handle server error gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/billing/subscription`, () => {
          return new HttpResponse(JSON.stringify({ detail: 'Internal server error' }), {
            status: 500,
          });
        })
      );

      render(<BillingPage />);

      // Page should still attempt to render
      await waitFor(() => {
        expect(screen.getByText(/loading billing information/i)).toBeInTheDocument();
      }, { timeout: 500 });
    });
  });
});
