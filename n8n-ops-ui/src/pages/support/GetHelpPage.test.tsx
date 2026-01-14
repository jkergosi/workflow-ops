import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GetHelpPage } from './GetHelpPage';
import { render } from '@/test/test-utils';

describe('GetHelpPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should display page heading', async () => {
      render(<GetHelpPage />);

      expect(screen.getByRole('heading', { level: 1, name: /get help/i })).toBeInTheDocument();
    });

    it('should display title input field', async () => {
      render(<GetHelpPage />);

      expect(screen.getByLabelText(/title/i)).toBeInTheDocument();
    });

    it('should display details textarea', async () => {
      render(<GetHelpPage />);

      // Label is "Question / Details"
      expect(screen.getByLabelText(/question \/ details/i)).toBeInTheDocument();
    });

    it('should display diagnostics toggle', async () => {
      render(<GetHelpPage />);

      expect(screen.getByText(/include diagnostics/i)).toBeInTheDocument();
    });

    it('should display submit button', async () => {
      render(<GetHelpPage />);

      // Button text is "Submit Request"
      expect(screen.getByRole('button', { name: /submit request/i })).toBeInTheDocument();
    });

    it('should display cancel button', async () => {
      render(<GetHelpPage />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });
  });

  describe('Form Input', () => {
    it('should allow typing in title field', async () => {
      render(<GetHelpPage />);

      const titleInput = screen.getByLabelText(/title/i);
      await userEvent.type(titleInput, 'How do I configure X?');

      expect(titleInput).toHaveValue('How do I configure X?');
    });

    it('should allow typing in details field', async () => {
      render(<GetHelpPage />);

      const detailsInput = screen.getByLabelText(/question \/ details/i);
      await userEvent.type(detailsInput, 'I need help understanding the workflow setup');

      expect(detailsInput).toHaveValue('I need help understanding the workflow setup');
    });
  });

  describe('Form Submission', () => {
    it('should have submit button enabled after filling required fields', async () => {
      render(<GetHelpPage />);

      // Fill in required fields
      await userEvent.type(screen.getByLabelText(/title/i), 'Help needed');
      await userEvent.type(screen.getByLabelText(/question \/ details/i), 'I need assistance');

      // Submit button should be enabled
      const submitButton = screen.getByRole('button', { name: /submit request/i });
      expect(submitButton).not.toBeDisabled();
    });
  });

  describe('Navigation', () => {
    it('should have a cancel button', async () => {
      render(<GetHelpPage />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      expect(cancelButton).toBeInTheDocument();
    });
  });
});
