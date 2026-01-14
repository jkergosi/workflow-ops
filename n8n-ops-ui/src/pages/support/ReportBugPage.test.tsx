import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReportBugPage } from './ReportBugPage';
import { render } from '@/test/test-utils';

describe('ReportBugPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should display page heading', async () => {
      render(<ReportBugPage />);

      expect(screen.getByRole('heading', { level: 1, name: /report a bug/i })).toBeInTheDocument();
    });

    it('should display title input field', async () => {
      render(<ReportBugPage />);

      expect(screen.getByLabelText(/title/i)).toBeInTheDocument();
    });

    it('should display what happened textarea', async () => {
      render(<ReportBugPage />);

      expect(screen.getByLabelText(/what happened\?/i)).toBeInTheDocument();
    });

    it('should display expected behavior textarea', async () => {
      render(<ReportBugPage />);

      expect(screen.getByLabelText(/what did you expect\?/i)).toBeInTheDocument();
    });

    it('should display severity select', async () => {
      render(<ReportBugPage />);

      expect(screen.getByText(/severity \(optional\)/i)).toBeInTheDocument();
    });

    it('should display frequency select', async () => {
      render(<ReportBugPage />);

      expect(screen.getByText(/frequency \(optional\)/i)).toBeInTheDocument();
    });

    it('should display diagnostics toggle', async () => {
      render(<ReportBugPage />);

      expect(screen.getByText(/include diagnostics/i)).toBeInTheDocument();
    });

    it('should display submit button', async () => {
      render(<ReportBugPage />);

      expect(screen.getByRole('button', { name: /submit bug report/i })).toBeInTheDocument();
    });

    it('should display cancel button', async () => {
      render(<ReportBugPage />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });
  });

  describe('Form Input', () => {
    it('should allow typing in title field', async () => {
      render(<ReportBugPage />);

      const titleInput = screen.getByLabelText(/title/i);
      await userEvent.type(titleInput, 'Test bug title');

      expect(titleInput).toHaveValue('Test bug title');
    });

    it('should allow typing in what happened field', async () => {
      render(<ReportBugPage />);

      const whatHappenedInput = screen.getByLabelText(/what happened\?/i);
      await userEvent.type(whatHappenedInput, 'Something went wrong');

      expect(whatHappenedInput).toHaveValue('Something went wrong');
    });

    it('should allow typing in expected behavior field', async () => {
      render(<ReportBugPage />);

      const expectedInput = screen.getByLabelText(/what did you expect\?/i);
      await userEvent.type(expectedInput, 'It should work correctly');

      expect(expectedInput).toHaveValue('It should work correctly');
    });
  });

  describe('Form Submission', () => {
    it('should have submit button enabled after filling required fields', async () => {
      render(<ReportBugPage />);

      // Fill in required fields
      await userEvent.type(screen.getByLabelText(/title/i), 'Test bug');
      await userEvent.type(screen.getByLabelText(/what happened\?/i), 'Something broke');
      await userEvent.type(screen.getByLabelText(/what did you expect\?/i), 'Should work');

      // Submit button should be enabled
      const submitButton = screen.getByRole('button', { name: /submit bug report/i });
      expect(submitButton).not.toBeDisabled();
    });
  });

  describe('Navigation', () => {
    it('should have a cancel button', async () => {
      render(<ReportBugPage />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      expect(cancelButton).toBeInTheDocument();
    });
  });
});
