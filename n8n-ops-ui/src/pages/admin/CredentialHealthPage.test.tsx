import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { CredentialHealthPage } from './CredentialHealthPage';

const API_BASE = '/api/v1';

const mockEnvironments = [
  { id: 'env-1', tenant_id: 'tenant-1', n8n_name: 'Development', n8n_type: 'development', n8n_base_url: 'https://dev.n8n.example.com', is_active: true },
  { id: 'env-2', tenant_id: 'tenant-1', n8n_name: 'Production', n8n_type: 'production', n8n_base_url: 'https://prod.n8n.example.com', is_active: true },
];

const mockProviders = [
  { provider: 'n8n', displayName: 'n8n', isActive: true },
  { provider: 'local', displayName: 'Local', isActive: true },
];

const mockLogicalCredentials = [
  { id: 'logical-1', name: 'Slack API', requiredType: 'slackApi', description: 'Slack API credentials', tenantId: 'tenant-1' },
  { id: 'logical-2', name: 'GitHub Token', requiredType: 'githubApi', description: 'GitHub API credentials', tenantId: 'tenant-1' },
];

const mockCredentialMappings = [
  { id: 'mapping-1', logicalCredentialId: 'logical-1', environmentId: 'env-1', physicalCredentialId: 'physical-1', provider: 'n8n' },
];

describe('CredentialHealthPage', () => {
  beforeEach(() => {
    server.resetHandlers();

    server.use(
      http.get(`${API_BASE}/environments`, () => {
        return HttpResponse.json(mockEnvironments);
      }),
      http.get(`${API_BASE}/providers/active`, () => {
        return HttpResponse.json(mockProviders);
      }),
      http.get(`${API_BASE}/credentials/logical`, () => {
        return HttpResponse.json(mockLogicalCredentials);
      }),
      http.get(`${API_BASE}/credentials/mappings`, () => {
        return HttpResponse.json(mockCredentialMappings);
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
      render(<CredentialHealthPage />);

      expect(screen.getByRole('heading', { level: 1, name: /credential health/i })).toBeInTheDocument();
    });

    it('should display the page description', async () => {
      render(<CredentialHealthPage />);

      expect(screen.getByText(/manage credential aliases and their environment mappings/i)).toBeInTheDocument();
    });
  });

  describe('Selector Cards', () => {
    it('should display Environment card', async () => {
      render(<CredentialHealthPage />);

      expect(screen.getByText('Environment')).toBeInTheDocument();
    });

    it('should display Provider card', async () => {
      render(<CredentialHealthPage />);

      expect(screen.getByText('Provider')).toBeInTheDocument();
    });
  });

  describe('Credential Sections', () => {
    it('should display Credential Aliases section', async () => {
      render(<CredentialHealthPage />);

      expect(screen.getByText('Credential Aliases')).toBeInTheDocument();
    });

    it('should display Credential Mappings section', async () => {
      render(<CredentialHealthPage />);

      expect(screen.getByText('Credential Mappings')).toBeInTheDocument();
    });
  });
});
