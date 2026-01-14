import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@/test/test-utils';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { CredentialDiscovery } from './CredentialDiscovery';

const API_BASE = 'http://localhost:3000/api/v1';

const mockEnvironments = [
  { id: 'env-1', name: 'Development', type: 'development', n8n_name: 'Development', n8n_type: 'development' },
  { id: 'env-2', name: 'Production', type: 'production', n8n_name: 'Production', n8n_type: 'production' },
];

const mockDiscoveredCredentials = [
  { type: 'slackApi', name: 'prod-slack', logicalKey: 'slackApi:prod-slack', workflowCount: 3, workflows: [{ id: 'wf-1', name: 'Workflow 1' }], existingLogicalId: 'logical-1', mappingStatus: 'mapped' },
  { type: 'githubApi', name: 'gh-token', logicalKey: 'githubApi:gh-token', workflowCount: 2, workflows: [{ id: 'wf-2', name: 'Workflow 2' }], existingLogicalId: null, mappingStatus: 'unmapped' },
];

describe('CredentialDiscovery', () => {
  beforeEach(() => {
    server.resetHandlers();

    server.use(
      http.get(`${API_BASE}/environments`, () => {
        return HttpResponse.json(mockEnvironments);
      }),
      http.post(`${API_BASE}/admin/credentials/discover/:environmentId`, () => {
        return HttpResponse.json(mockDiscoveredCredentials);
      }),
      http.get(`${API_BASE}/auth/status`, () => {
        return HttpResponse.json({
          authenticated: true,
          onboarding_required: false,
          has_environment: true,
          user: { id: 'user-1', email: 'admin@test.com', name: 'Admin', role: 'admin' },
          tenant: { id: 'tenant-1', name: 'Test Org', subscription_tier: 'pro' },
          entitlements: { plan_name: 'pro', features: {} },
        });
      }),
      http.post(`${API_BASE}/admin/credentials/logical`, async ({ request }) => {
        const body = await request.json() as Record<string, unknown>;
        return HttpResponse.json({
          id: `logical-${Date.now()}`,
          ...body,
          created_at: new Date().toISOString(),
        }, { status: 201 });
      })
    );
  });

  describe('Rendering', () => {
    it('should display the credential discovery title', async () => {
      render(<CredentialDiscovery />);

      expect(screen.getByText('Credential Discovery')).toBeInTheDocument();
    });

    it('should display environment selector label', async () => {
      render(<CredentialDiscovery />);

      await waitFor(() => {
        expect(screen.getByText(/environment to scan/i)).toBeInTheDocument();
      });
    });

    it('should display Scan Workflows button', async () => {
      render(<CredentialDiscovery />);

      expect(screen.getByRole('button', { name: /scan workflows/i })).toBeInTheDocument();
    });

    it('should show description text', async () => {
      render(<CredentialDiscovery />);

      await waitFor(() => {
        expect(screen.getByText(/scan workflows to discover credential references/i)).toBeInTheDocument();
      });
    });
  });

  describe('Button States', () => {
    it('should disable Scan button when no environment selected', async () => {
      render(<CredentialDiscovery />);

      const scanButton = screen.getByRole('button', { name: /scan workflows/i });
      expect(scanButton).toBeDisabled();
    });
  });

  describe('Component Structure', () => {
    it('should have environment selector combobox', async () => {
      render(<CredentialDiscovery />);

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
    });

    it('should have select environment placeholder', async () => {
      render(<CredentialDiscovery />);

      await waitFor(() => {
        expect(screen.getByText(/select environment/i)).toBeInTheDocument();
      });
    });
  });
});
