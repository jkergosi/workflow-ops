import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RequestFeaturePage } from './RequestFeaturePage';
import { render } from '@/test/test-utils';

describe('RequestFeaturePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should display page heading', async () => {
      render(<RequestFeaturePage />);

      expect(screen.getByRole('heading', { level: 1, name: /request a feature/i })).toBeInTheDocument();
    });

    it('should display title input field', async () => {
      render(<RequestFeaturePage />);

      expect(screen.getByLabelText(/title/i)).toBeInTheDocument();
    });

    it('should display problem/goal textarea', async () => {
      render(<RequestFeaturePage />);

      // The label is "Problem / Goal" with asterisk
      expect(screen.getByLabelText(/problem \/ goal/i)).toBeInTheDocument();
    });

    it('should display desired outcome textarea', async () => {
      render(<RequestFeaturePage />);

      expect(screen.getByLabelText(/desired outcome/i)).toBeInTheDocument();
    });

    it('should display priority select', async () => {
      render(<RequestFeaturePage />);

      expect(screen.getByText(/priority/i)).toBeInTheDocument();
    });

    it('should display submit button', async () => {
      render(<RequestFeaturePage />);

      expect(screen.getByRole('button', { name: /submit feature request/i })).toBeInTheDocument();
    });

    it('should display cancel button', async () => {
      render(<RequestFeaturePage />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });
  });

  describe('Form Validation', () => {
    it('should have title field', async () => {
      render(<RequestFeaturePage />);

      const titleInput = screen.getByLabelText(/title/i);
      expect(titleInput).toBeInTheDocument();
    });

    it('should allow typing in title field', async () => {
      render(<RequestFeaturePage />);

      const titleInput = screen.getByLabelText(/title/i);
      await userEvent.type(titleInput, 'New feature idea');

      expect(titleInput).toHaveValue('New feature idea');
    });

    it('should allow typing in problem/goal field', async () => {
      render(<RequestFeaturePage />);

      const problemInput = screen.getByLabelText(/problem \/ goal/i);
      await userEvent.type(problemInput, 'I need a way to do X');

      expect(problemInput).toHaveValue('I need a way to do X');
    });

    it('should allow typing in desired outcome field', async () => {
      render(<RequestFeaturePage />);

      const outcomeInput = screen.getByLabelText(/desired outcome/i);
      await userEvent.type(outcomeInput, 'A button that does Y');

      expect(outcomeInput).toHaveValue('A button that does Y');
    });
  });

  describe('Acceptance Criteria', () => {
    it('should display acceptance criteria section', async () => {
      render(<RequestFeaturePage />);

      expect(screen.getByText(/acceptance criteria/i)).toBeInTheDocument();
    });

    it('should display add criteria input', async () => {
      render(<RequestFeaturePage />);

      expect(screen.getByPlaceholderText(/add a criterion/i)).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    it('should have submit button enabled after filling required fields', async () => {
      render(<RequestFeaturePage />);

      // Fill in required fields
      await userEvent.type(screen.getByLabelText(/title/i), 'New feature request');
      await userEvent.type(screen.getByLabelText(/problem \/ goal/i), 'Need to track metrics');
      await userEvent.type(screen.getByLabelText(/desired outcome/i), 'Dashboard with charts');

      // Submit button should be enabled
      const submitButton = screen.getByRole('button', { name: /submit feature request/i });
      expect(submitButton).not.toBeDisabled();
    });
  });

  describe('Navigation', () => {
    it('should have a cancel button', async () => {
      render(<RequestFeaturePage />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      expect(cancelButton).toBeInTheDocument();
    });
  });
});
