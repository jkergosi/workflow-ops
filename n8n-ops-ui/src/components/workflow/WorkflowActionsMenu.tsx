/**
 * WorkflowActionsMenu - Dropdown menu for workflow actions
 *
 * Replaces inline Edit/Delete buttons with a unified actions dropdown
 * that respects environment-based governance policies.
 */

import {
  ChevronDown,
  Eye,
  ExternalLink,
  Rocket,
  AlertTriangle,
  AlertCircle,
  Edit,
  Archive,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Badge } from '@/components/ui/badge';
import { useWorkflowActionPolicy } from '@/hooks/useWorkflowActionPolicy';
import type { Environment, Workflow } from '@/types';

interface WorkflowActionsMenuProps {
  workflow: Workflow;
  environment: Environment | null;
  onViewDetails: () => void;
  onEdit: () => void;
  onSoftDelete: () => void;       // Archive workflow
  onHardDelete: () => void;       // Permanently delete (admin-only)
  onOpenInN8N: () => void;
  onCreateDeployment: () => void;
  onViewDriftIncident?: () => void;
  onCreateDriftIncident?: () => void;
}

export function WorkflowActionsMenu({
  workflow,
  environment,
  onViewDetails,
  onEdit,
  onSoftDelete,
  onHardDelete,
  onOpenInN8N,
  onCreateDeployment,
  onViewDriftIncident,
  onCreateDriftIncident,
}: WorkflowActionsMenuProps) {
  const policy = useWorkflowActionPolicy(environment, workflow);

  const isDevEnvironment = environment?.environmentClass?.toLowerCase() === 'dev';
  const hasDrift = workflow.syncStatus === 'local_changes' || workflow.syncStatus === 'conflict';
  const hasActiveIncident = environment?.driftStatus === 'DRIFT_INCIDENT_ACTIVE';

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          Actions <ChevronDown className="h-3 w-3 ml-1" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        {/* =============================================
            ALWAYS AVAILABLE
            ============================================= */}
        <DropdownMenuItem onClick={onViewDetails}>
          <Eye className="h-4 w-4 mr-2" />
          View Details
        </DropdownMenuItem>
        <DropdownMenuItem onClick={onOpenInN8N}>
          <ExternalLink className="h-4 w-4 mr-2" />
          Open in n8n
        </DropdownMenuItem>
        <DropdownMenuSeparator />

        {/* =============================================
            GOVERNANCE PATH (Primary)
            ============================================= */}
        <DropdownMenuItem onClick={onCreateDeployment}>
          <Rocket className="h-4 w-4 mr-2" />
          Create Deployment
        </DropdownMenuItem>

        {/* =============================================
            DRIFT INCIDENT PATH (not applicable for dev environments)
            ============================================= */}
        {!isDevEnvironment && policy.canCreateDriftIncident && hasDrift && !hasActiveIncident && onCreateDriftIncident && (
          <DropdownMenuItem onClick={onCreateDriftIncident}>
            <AlertTriangle className="h-4 w-4 mr-2" />
            Create Drift Incident
            {policy.driftIncidentRequired && (
              <Badge variant="outline" className="ml-2 text-xs">Required</Badge>
            )}
          </DropdownMenuItem>
        )}
        {!isDevEnvironment && hasActiveIncident && onViewDriftIncident && (
          <DropdownMenuItem onClick={onViewDriftIncident}>
            <AlertCircle className="h-4 w-4 mr-2" />
            View Drift Incident
          </DropdownMenuItem>
        )}

        {/* =============================================
            DIRECT MUTATION (Gated)
            ============================================= */}
        {(policy.canEditDirectly || policy.canSoftDelete || policy.canHardDelete) && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              {isDevEnvironment ? 'Direct Actions' : 'Direct Actions (creates drift)'}
            </DropdownMenuLabel>
          </>
        )}

        {policy.canEditDirectly && (
          <DropdownMenuItem onClick={onEdit}>
            <Edit className="h-4 w-4 mr-2" />
            Edit Directly
          </DropdownMenuItem>
        )}

        {policy.canSoftDelete && (
          <DropdownMenuItem onClick={onSoftDelete}>
            <Archive className="h-4 w-4 mr-2" />
            Archive Workflow
          </DropdownMenuItem>
        )}

        {policy.canHardDelete && (
          <DropdownMenuItem onClick={onHardDelete} className="text-destructive">
            <Trash2 className="h-4 w-4 mr-2" />
            Permanently Delete
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
