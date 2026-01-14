import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { TenantOverridesPage } from './TenantOverridesPage';

const API_BASE = 'http://localhost:4000/api/v1';

const mockTenants = [
  { id: 'tenant-1', name: 'Acme Corp', email: 'admin@acme.com', subscriptionPlan: 'pro', status: 'active' },
  { id: 'tenant-2', name: 'Test Org', email: 'admin@test.com', subscriptionPlan: 'free', status: 'active' },
];

const mockFeatures = [
  { key: 'max_workflows', name: 'Max Workflows', description: 'Maximum workflows allowed' },
  { key: 'max_environments', name: 'Max Environments', description: 'Maximum environments allowed' },
];

const mockOverrides = [
  {
    id: 'override-1',
    tenant_id: 'tenant-1',
    tenant_name: 'Acme Corp',
    feature_key: 'max_workflows',
    override_value: 200,
    reason: 'Enterprise upgrade pending',
    created_at: '2024-01-01T00:00:00Z',
    created_by: 'admin@test.com',
  },
];

describe('TenantOverridesPage', () => {
  beforeEach(() => {
    server.resetHandlers();

    server.use(
      http.get(`${API_BASE}/admin/entitlements/overrides`, () => {
        return HttpResponse.json({
          overrides: mockOverrides,
          total: 1,
        });
      }),
      http.get(`${API_BASE}/tenants`, () => {
        return HttpResponse.json({
          tenants: mockTenants,
          total: 2,
        });
      }),
      http.get(`${API_BASE}/admin/entitlements/features`, () => {
        return HttpResponse.json({
          features: mockFeatures,
        });
      }),
      http.get(`${API_BASE}/auth/status`, () => {
        return HttpResponse.json({
          authenticated: true,
          onboarding_required: false,
          has_environment: true,
          user: { id: 'user-1', email: 'admin@test.com', name: 'Admin User', role: 'admin' },
          tenant: { id: 'tenant-1', name: 'Test Org', subscription_tier: 'pro' },
          entitlements: { plan_name: 'pro', features: {} },
        });
      })
    );
  });

  describe('Page Header', () => {
    it('should display the page title', async () => {
      render(<TenantOverridesPage />);

      expect(screen.getByRole('heading', { level: 1, name: /tenant overrides/i })).toBeInTheDocument();
    });

    it('should display the page description', async () => {
      render(<TenantOverridesPage />);

      expect(screen.getByText(/manage feature overrides for specific tenants/i)).toBeInTheDocument();
    });
  });

  describe('Tenant Selection', () => {
    it('should display Select Tenant section', async () => {
      render(<TenantOverridesPage />);

      expect(screen.getByText('Select Tenant')).toBeInTheDocument();
    });

    it('should display tenant selection description', async () => {
      render(<TenantOverridesPage />);

      expect(screen.getByText(/choose a tenant to view and manage their feature overrides/i)).toBeInTheDocument();
    });

    it('should have tenant selector dropdown', async () => {
      render(<TenantOverridesPage />);

      expect(screen.getByText(/select a tenant/i)).toBeInTheDocument();
    });
  });

  describe('Action Buttons', () => {
    it('should display Refresh button (disabled initially)', async () => {
      render(<TenantOverridesPage />);

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      expect(refreshButton).toBeInTheDocument();
      expect(refreshButton).toBeDisabled();
    });

    it('should display Add Override button (disabled initially)', async () => {
      render(<TenantOverridesPage />);

      const addButton = screen.getByRole('button', { name: /add override/i });
      expect(addButton).toBeInTheDocument();
      expect(addButton).toBeDisabled();
    });
  });
});
