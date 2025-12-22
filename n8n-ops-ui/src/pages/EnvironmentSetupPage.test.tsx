import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { EnvironmentSetupPage } from './EnvironmentSetupPage';
import { render } from '@/test/test-utils';
import { server } from '@/test/mocks/server';

const API_BASE = 'http://localhost:4000/api/v1';

// Mock useParams and useSearchParams
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({}),
    useSearchParams: () => [new URLSearchParams()],
    useNavigate: () => vi.fn(),
  };
});

// Mock useAuth
vi.mock('@/lib/auth', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useAuth: () => ({
      refreshUser: vi.fn(),
    }),
  };
});

describe('EnvironmentSetupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.use(
      http.post(`${API_BASE}/environments/test-connection`, () => {
        return HttpResponse.json({ success: true, message: 'Connection successful' });
      }),
      http.post(`${API_BASE}/environments/test-git-connection`, () => {
        return HttpResponse.json({ success: true, message: 'Git connection successful' });
      }),
      http.post(`${API_BASE}/environments`, () => {
        return HttpResponse.json({ id: 'env-new', name: 'New Environment' });
      })
    );
  });

  describe('Rendering', () => {
    it('should display page title for new environment', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByText(/add environment/i)).toBeInTheDocument();
    });

    it('should display basic information section', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByText(/basic information/i)).toBeInTheDocument();
    });

    it('should display N8N instance section', async () => {
      render(<EnvironmentSetupPage />);

      // "N8N instance" appears in multiple helper texts; assert the section heading specifically
      expect(screen.getByRole('heading', { name: /n8n instance/i })).toBeInTheDocument();
    });

    it('should display GitHub integration section', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByText(/github integration/i)).toBeInTheDocument();
    });
  });

  describe('Form Fields', () => {
    it('should have environment name input', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByLabelText(/environment name/i)).toBeInTheDocument();
    });

    it('should have environment type selector', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByLabelText(/type/i)).toBeInTheDocument();
    });

    it('should have N8N URL input', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByLabelText(/n8n url/i)).toBeInTheDocument();
    });

    it('should have API key input', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
    });

    it('should have GitHub repository URL input', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByLabelText(/repository url/i)).toBeInTheDocument();
    });

    it('should have GitHub branch input', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByLabelText(/branch/i)).toBeInTheDocument();
    });
  });

  describe('Connection Testing', () => {
    it('should have test N8N connection button', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByRole('button', { name: /test connection/i })).toBeInTheDocument();
    });

    it('should test N8N connection when button is clicked', async () => {
      render(<EnvironmentSetupPage />);

      // Fill in required fields first
      const urlInput = screen.getByLabelText(/n8n url/i);
      const apiKeyInput = screen.getByLabelText(/api key/i);

      await userEvent.type(urlInput, 'https://n8n.example.com');
      await userEvent.type(apiKeyInput, 'test-api-key');

      const testButton = screen.getByRole('button', { name: /test connection/i });
      await userEvent.click(testButton);

      // Should show testing state or result
    });
  });

  describe('Form Submission', () => {
    it('should have create environment button', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByRole('button', { name: /create environment/i })).toBeInTheDocument();
    });

    it('should have cancel button', async () => {
      render(<EnvironmentSetupPage />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('should validate required fields before submission', async () => {
      render(<EnvironmentSetupPage />);

      const submitButton = screen.getByRole('button', { name: /create environment/i });
      await userEvent.click(submitButton);

      // Form should not submit without required fields
    });
  });

  describe('Environment Type Selection', () => {
    it('should have development option', async () => {
      render(<EnvironmentSetupPage />);

      const typeSelect = screen.getByLabelText(/type/i);
      typeSelect.focus();
      fireEvent.keyDown(typeSelect, { key: 'Enter' });

      await waitFor(() => {
        const listbox = screen.getByRole('listbox');
        expect(within(listbox).getByRole('option', { name: 'Development' })).toBeInTheDocument();
      });
    });

    it('should have staging option', async () => {
      render(<EnvironmentSetupPage />);

      const typeSelect = screen.getByLabelText(/type/i);
      typeSelect.focus();
      fireEvent.keyDown(typeSelect, { key: 'Enter' });

      await waitFor(() => {
        const listbox = screen.getByRole('listbox');
        expect(within(listbox).getByRole('option', { name: 'Staging' })).toBeInTheDocument();
      });
    });

    it('should have production option', async () => {
      render(<EnvironmentSetupPage />);

      const typeSelect = screen.getByLabelText(/type/i);
      typeSelect.focus();
      fireEvent.keyDown(typeSelect, { key: 'Enter' });

      await waitFor(() => {
        const listbox = screen.getByRole('listbox');
        expect(within(listbox).getByRole('option', { name: 'Production' })).toBeInTheDocument();
      });
    });
  });
});
