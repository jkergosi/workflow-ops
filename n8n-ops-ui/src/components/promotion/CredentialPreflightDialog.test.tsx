import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { CredentialPreflightDialog } from './CredentialPreflightDialog';
import type { CredentialPreflightResult } from '@/types/credentials';

const mockPreflightResultValid: CredentialPreflightResult = {
  valid: true,
  blocking_issues: [],
  warnings: [],
  resolved_mappings: [
    {
      logical_key: 'slackApi:notifications',
      source_physical_name: 'Dev Slack',
      target_physical_name: 'Prod Slack',
      target_physical_id: 'n8n-cred-1',
    },
  ],
};

const mockPreflightResultWithBlockingIssues: CredentialPreflightResult = {
  valid: false,
  blocking_issues: [
    {
      workflow_id: 'wf-1',
      workflow_name: 'Notification Workflow',
      logical_credential_key: 'slackApi:alerts',
      issue_type: 'missing_mapping',
      message: 'No mapping found for target environment',
      is_blocking: true,
    },
  ],
  warnings: [],
  resolved_mappings: [],
};

const mockPreflightResultWithWarnings: CredentialPreflightResult = {
  valid: true,
  blocking_issues: [],
  warnings: [
    {
      workflow_id: 'wf-2',
      workflow_name: 'Backup Workflow',
      logical_credential_key: 'awsApi:s3-backup',
      issue_type: 'mapped_missing_in_target',
      message: 'Credential exists but not verified in target',
      is_blocking: false,
    },
  ],
  resolved_mappings: [
    {
      logical_key: 'postgresApi:main-db',
      source_physical_name: 'Dev DB',
      target_physical_name: 'Prod DB',
      target_physical_id: 'n8n-cred-2',
    },
  ],
};

describe('CredentialPreflightDialog', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    onProceed: vi.fn(),
    onCancel: vi.fn(),
  };

  describe('Rendering', () => {
    it('should display success state when no issues', async () => {
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultValid}
        />
      );

      expect(screen.getByText('Credentials Ready')).toBeInTheDocument();
      expect(screen.getByText('Continue to Deploy')).toBeInTheDocument();
    });

    it('should display blocking issues with clear messaging', async () => {
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultWithBlockingIssues}
        />
      );

      expect(screen.getByText('Credential Check Failed')).toBeInTheDocument();
      expect(screen.getByText(/1 credential mapping.*must be fixed/i)).toBeInTheDocument();
      expect(screen.getByText('Fix Issues to Continue')).toBeInTheDocument();
    });

    it('should display warnings with proceed option', async () => {
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultWithWarnings}
        />
      );

      expect(screen.getByText('Credential Warnings')).toBeInTheDocument();
      expect(screen.getByText('Proceed with Warnings')).toBeInTheDocument();
    });

    it('should show summary cards with counts', async () => {
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultWithWarnings}
        />
      );

      expect(screen.getByText('Blocking')).toBeInTheDocument();
      expect(screen.getByText('Warnings')).toBeInTheDocument();
      expect(screen.getByText('Resolved')).toBeInTheDocument();
    });

    it('should display workflow name and credential key in issues', async () => {
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultWithBlockingIssues}
        />
      );

      expect(screen.getByText('Notification Workflow')).toBeInTheDocument();
      expect(screen.getByText('slackApi:alerts')).toBeInTheDocument();
    });

    it('should display resolved mappings with source and target', async () => {
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultValid}
        />
      );

      // Click on Resolved tab
      const user = userEvent.setup();
      const resolvedTab = screen.getByRole('tab', { name: /resolved/i });
      await user.click(resolvedTab);

      await waitFor(() => {
        expect(screen.getByText('slackApi:notifications')).toBeInTheDocument();
        expect(screen.getByText(/dev slack/i)).toBeInTheDocument();
        expect(screen.getByText('Prod Slack')).toBeInTheDocument();
      });
    });
  });

  describe('Map Now Action', () => {
    it('should show Map Now button for mapping issues', async () => {
      const onMapCredential = vi.fn();
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultWithBlockingIssues}
          onMapCredential={onMapCredential}
        />
      );

      expect(screen.getByRole('button', { name: /map now/i })).toBeInTheDocument();
    });

    it('should call onMapCredential when Map Now is clicked', async () => {
      const onMapCredential = vi.fn();
      const user = userEvent.setup();

      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultWithBlockingIssues}
          onMapCredential={onMapCredential}
        />
      );

      const mapButton = screen.getByRole('button', { name: /map now/i });
      await user.click(mapButton);

      expect(onMapCredential).toHaveBeenCalledWith(
        expect.objectContaining({
          workflow_name: 'Notification Workflow',
          logical_credential_key: 'slackApi:alerts',
        })
      );
    });

    it('should show quick fix hint when blocking issues exist', async () => {
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultWithBlockingIssues}
          onMapCredential={vi.fn()}
        />
      );

      expect(screen.getByText(/quick fix/i)).toBeInTheDocument();
      expect(screen.getByText(/credential matrix/i)).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('should disable proceed button when blocking issues exist', async () => {
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultWithBlockingIssues}
        />
      );

      const proceedButton = screen.getByRole('button', { name: /fix issues/i });
      expect(proceedButton).toBeDisabled();
    });

    it('should enable proceed button when only warnings', async () => {
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultWithWarnings}
        />
      );

      const proceedButton = screen.getByRole('button', { name: /proceed with warnings/i });
      expect(proceedButton).not.toBeDisabled();
    });

    it('should call onProceed when proceed button is clicked', async () => {
      const onProceed = vi.fn();
      const user = userEvent.setup();

      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultValid}
          onProceed={onProceed}
        />
      );

      const proceedButton = screen.getByRole('button', { name: /continue to deploy/i });
      await user.click(proceedButton);

      expect(onProceed).toHaveBeenCalled();
    });

    it('should call onCancel when cancel button is clicked', async () => {
      const onCancel = vi.fn();
      const user = userEvent.setup();

      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultValid}
          onCancel={onCancel}
        />
      );

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
    });
  });

  describe('Loading State', () => {
    it('should show loading state when isLoading is true', async () => {
      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={mockPreflightResultValid}
          isLoading={true}
        />
      );

      expect(screen.getByText(/processing/i)).toBeInTheDocument();
    });
  });

  describe('No Credentials', () => {
    it('should show message when no credentials are required', async () => {
      const emptyResult: CredentialPreflightResult = {
        valid: true,
        blocking_issues: [],
        warnings: [],
        resolved_mappings: [],
      };

      render(
        <CredentialPreflightDialog
          {...defaultProps}
          preflightResult={emptyResult}
        />
      );

      expect(screen.getByText(/no credentials required/i)).toBeInTheDocument();
    });
  });
});
