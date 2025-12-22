import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@/test/test-utils';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';
import { CredentialMatrix } from './CredentialMatrix';

const API_BASE = 'http://localhost:3000/api/v1';

const mockMatrixData = {
  logical_credentials: [
    { id: 'logical-1', name: 'slackApi:prod-slack', requiredType: 'slackApi', description: 'Slack credentials' },
    { id: 'logical-2', name: 'githubApi:gh-token', requiredType: 'githubApi', description: 'GitHub credentials' },
  ],
  environments: [
    { id: 'env-1', name: 'Development', type: 'development' },
    { id: 'env-2', name: 'Production', type: 'production' },
  ],
  matrix: {
    'logical-1': {
      'env-1': { mappingId: 'mapping-1', physicalCredentialId: 'n8n-cred-1', physicalName: 'Dev Slack', physicalType: 'slackApi', status: 'valid' },
      'env-2': { mappingId: 'mapping-2', physicalCredentialId: 'n8n-cred-2', physicalName: 'Prod Slack', physicalType: 'slackApi', status: 'valid' },
    },
    'logical-2': {
      'env-1': { mappingId: 'mapping-3', physicalCredentialId: 'n8n-cred-3', physicalName: 'Dev GitHub', physicalType: 'githubApi', status: 'valid' },
      'env-2': null,
    },
  },
};

describe('CredentialMatrix', () => {
  beforeEach(() => {
    server.resetHandlers();

    server.use(
      http.get(`${API_BASE}/admin/credentials/matrix`, () => {
        return HttpResponse.json(mockMatrixData);
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
      })
    );
  });

  describe('Rendering', () => {
    it('should display the credential matrix title', async () => {
      render(<CredentialMatrix />);

      await waitFor(() => {
        expect(screen.getByText('Mapping')).toBeInTheDocument();
      });
    });

    it('should display environment column headers', async () => {
      render(<CredentialMatrix />);

      await waitFor(() => {
        expect(screen.getByText('Development')).toBeInTheDocument();
        expect(screen.getByText('Production')).toBeInTheDocument();
      });
    });

    it('should display credential alias rows', async () => {
      render(<CredentialMatrix />);

      await waitFor(() => {
        expect(screen.getByText('slackApi:prod-slack')).toBeInTheDocument();
        expect(screen.getByText('githubApi:gh-token')).toBeInTheDocument();
      });
    });

    it('should display mapped credentials with their names', async () => {
      render(<CredentialMatrix />);

      await waitFor(() => {
        expect(screen.getByText('Dev Slack')).toBeInTheDocument();
        expect(screen.getByText('Prod Slack')).toBeInTheDocument();
        expect(screen.getByText('Dev GitHub')).toBeInTheDocument();
      });
    });

    it('should display environment type badges', async () => {
      render(<CredentialMatrix />);

      await waitFor(() => {
        expect(screen.getByText('development')).toBeInTheDocument();
        expect(screen.getByText('production')).toBeInTheDocument();
      });
    });
  });

  describe('Status Indicators', () => {
    it('should display Map button for unmapped cells', async () => {
      render(<CredentialMatrix />);

      await waitFor(() => {
        // logical-2 has no mapping for env-2 (production)
        const mapButtons = screen.getAllByRole('button', { name: /map/i });
        expect(mapButtons.length).toBeGreaterThan(0);
      });
    });

    it('should display legend with status indicators', async () => {
      render(<CredentialMatrix />);

      await waitFor(() => {
        expect(screen.getByText('Valid')).toBeInTheDocument();
        expect(screen.getByText('Invalid')).toBeInTheDocument();
        expect(screen.getByText('Stale')).toBeInTheDocument();
        expect(screen.getByText('Not Mapped')).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no credential aliases exist', async () => {
      server.use(
        http.get(`${API_BASE}/admin/credentials/matrix`, () => {
          return HttpResponse.json({
            logical_credentials: [],
            environments: [],
            matrix: {},
          });
        })
      );

      render(<CredentialMatrix />);

      await waitFor(() => {
        expect(screen.getByText(/no credential aliases defined/i)).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('should show loading state while fetching matrix', async () => {
      server.use(
        http.get(`${API_BASE}/admin/credentials/matrix`, async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(mockMatrixData);
        })
      );

      render(<CredentialMatrix />);

      // Should show loading spinner initially
      expect(document.querySelector('.animate-spin')).toBeInTheDocument();
    });
  });
});
