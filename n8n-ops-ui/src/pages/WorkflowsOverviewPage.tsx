import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { RefreshCw, Filter } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api-client';
import { EnvironmentStatusBadge } from '@/components/workflow/EnvironmentStatusBadge';
import type {
  WorkflowMatrixResponse,
  WorkflowMatrixRow,
  WorkflowMatrixEnvironment,
  WorkflowMatrixCell,
} from '@/types';

/** Status filter options for the dropdown */
const STATUS_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: 'all', label: 'All Statuses' },
  { value: 'linked', label: 'Linked' },
  { value: 'untracked', label: 'Untracked' },
  { value: 'drift', label: 'Drift' },
  { value: 'out_of_date', label: 'Out-of-date' },
];

export function WorkflowsOverviewPage() {
  const navigate = useNavigate();
  const [matrixData, setMatrixData] = useState<WorkflowMatrixResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  // Track which cells are currently syncing (environmentId as key)
  const [syncingEnvs, setSyncingEnvs] = useState<Set<string>>(new Set());
  // Single status filter (client-side filtering)
  const [statusFilter, setStatusFilter] = useState<string>('all');
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(50); // Default page size

  useEffect(() => {
    document.title = 'Workflows Overview - WorkflowOps';
    loadMatrix();
  }, [currentPage]); // Reload when page changes

  const loadMatrix = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.getWorkflowMatrix(currentPage, pageSize);
      setMatrixData(response.data);
    } catch (error: any) {
      toast.error('Failed to load workflow matrix');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle sync action for a workflow in an environment.
   * Triggers sync, waits for completion, then reloads the entire matrix.
   */
  const handleSync = async (environmentId: string, environmentName: string) => {
    // Mark this environment as syncing
    setSyncingEnvs((prev) => new Set(prev).add(environmentId));

    try {
      // Trigger the sync
      const syncResponse = await apiClient.syncEnvironment(environmentId);
      const jobId = syncResponse.data.job_id;

      toast.info(`Syncing ${environmentName}...`);

      // Poll for job completion with exponential backoff
      let completed = false;
      let attempts = 0;
      const maxAttempts = 60;
      let delay = 1000; // Start at 1 second
      const maxDelay = 10000; // Max 10 seconds
      const backoffFactor = 1.5;

      while (!completed && attempts < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, delay));
        attempts++;

        try {
          const jobStatus = await apiClient.getBackgroundJob(jobId);
          const status = jobStatus.data.status;

          if (status === 'completed' || status === 'success') {
            completed = true;
            toast.success(`Sync completed for ${environmentName}`);
          } else if (status === 'failed' || status === 'error') {
            completed = true;
            const errorMessage = jobStatus.data.error_message || 'Sync failed';
            toast.error(`Sync failed for ${environmentName}: ${errorMessage}`);
          }
          // If status is 'pending' or 'running', continue polling with backoff
          delay = Math.min(delay * backoffFactor, maxDelay);
        } catch (pollError) {
          // If we can't get job status, assume it completed and reload
          console.error('Error polling job status:', pollError);
          completed = true;
        }
      }

      if (!completed) {
        toast.warning(`Sync for ${environmentName} is taking longer than expected. Refreshing matrix...`);
      }

      // Reload the entire matrix after sync completes
      await loadMatrix();
    } catch (error: any) {
      const message = error?.response?.data?.detail || error?.message || 'Unknown error';
      toast.error(`Failed to sync ${environmentName}: ${message}`);
      console.error('Sync error:', error);
    } finally {
      // Remove environment from syncing set
      setSyncingEnvs((prev) => {
        const next = new Set(prev);
        next.delete(environmentId);
        return next;
      });
    }
  };

  /**
   * Get the cell data for a specific workflow and environment.
   * Returns null if the workflow has no presence in that environment.
   */
  const getCellData = (
    canonicalId: string,
    environmentId: string
  ): WorkflowMatrixCell | null => {
    if (!matrixData) return null;
    return matrixData.matrix[canonicalId]?.[environmentId] ?? null;
  };

  /**
   * Handle Promote action for a workflow.
   * Navigates to the Promote page with the workflow pre-selected via query parameter.
   */
  const handlePromote = (canonicalId: string) => {
    navigate(`/promote?workflow=${encodeURIComponent(canonicalId)}`);
  };

  if (isLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  const workflows: WorkflowMatrixRow[] = matrixData?.workflows ?? [];
  const environments: WorkflowMatrixEnvironment[] = matrixData?.environments ?? [];

  /**
   * Filter workflows based on the selected status filter.
   * A workflow matches if ANY of its environment cells have the selected status.
   */
  const filteredWorkflows = useMemo(() => {
    if (statusFilter === 'all') {
      return workflows;
    }

    return workflows.filter((workflow) => {
      // Check if any environment has the selected status
      return environments.some((env) => {
        const cell = matrixData?.matrix[workflow.canonicalId]?.[env.id];
        return cell?.status === statusFilter;
      });
    });
  }, [workflows, environments, matrixData, statusFilter]);

  return (
    <div className="container mx-auto py-8">
      {/* Page Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Workflows Overview</h1>
          <p className="text-muted-foreground mt-2">
            View workflow deployment status across all environments
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadMatrix}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Status Filter */}
      <div className="mb-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Filter
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="flex items-center gap-4">
              <div className="w-48">
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="All Statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_FILTER_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {statusFilter !== 'all' && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setStatusFilter('all')}
                  className="text-muted-foreground"
                >
                  Clear filter
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Matrix Table */}
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>
              Workflow Matrix
              {statusFilter !== 'all' ? (
                <span className="text-muted-foreground font-normal ml-2">
                  ({filteredWorkflows.length} of {workflows.length})
                </span>
              ) : (
                <span className="text-muted-foreground font-normal ml-2">
                  ({workflows.length})
                </span>
              )}
            </CardTitle>
            <CardDescription>
              Canonical workflows and their status in each environment
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="min-w-[200px]">Workflow</TableHead>
                    {environments.map((env) => (
                      <TableHead key={env.id} className="text-center min-w-[120px]">
                        {env.name}
                      </TableHead>
                    ))}
                    <TableHead className="min-w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredWorkflows.length === 0 ? (
                    <TableRow>
                      <TableCell
                        colSpan={environments.length + 2}
                        className="text-center text-muted-foreground py-8"
                      >
                        {statusFilter !== 'all'
                          ? `No workflows with status "${STATUS_FILTER_OPTIONS.find(o => o.value === statusFilter)?.label || statusFilter}"`
                          : 'No canonical workflows found'}
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredWorkflows.map((workflow) => (
                      <TableRow key={workflow.canonicalId}>
                        {/* Workflow Name Column */}
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="font-medium">
                              {workflow.displayName || 'Unnamed Workflow'}
                            </span>
                            <span className="text-xs text-muted-foreground font-mono">
                              {workflow.canonicalId.substring(0, 8)}...
                            </span>
                          </div>
                        </TableCell>

                        {/* Environment Status Cells */}
                        {environments.map((env) => {
                          const cellData = getCellData(workflow.canonicalId, env.id);
                          const isSyncing = syncingEnvs.has(env.id);
                          return (
                            <TableCell key={env.id} className="text-center">
                              {cellData ? (
                                <div className="flex flex-col items-center gap-1">
                                  <EnvironmentStatusBadge
                                    status={cellData.status}
                                    showTooltip={true}
                                    showIcon={true}
                                  />
                                  {/* Sync button - available only for drift or out_of_date status */}
                                  {cellData.canSync && (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      className="h-6 px-2 text-xs"
                                      disabled={isSyncing}
                                      onClick={() => handleSync(env.id, env.name)}
                                    >
                                      {isSyncing ? (
                                        <>
                                          <RefreshCw className="mr-1 h-3 w-3 animate-spin" />
                                          Syncing...
                                        </>
                                      ) : (
                                        'Sync'
                                      )}
                                    </Button>
                                  )}
                                </div>
                              ) : (
                                <span className="text-xs text-muted-foreground">-</span>
                              )}
                            </TableCell>
                          );
                        })}

                        {/* Actions Column */}
                        <TableCell>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handlePromote(workflow.canonicalId)}
                          >
                            Promote
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>

            {/* Pagination Controls */}
            {matrixData?.pageMetadata && matrixData.pageMetadata.totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between border-t pt-4">
                <div className="text-sm text-muted-foreground">
                  Page {matrixData.pageMetadata.page} of {matrixData.pageMetadata.totalPages}
                  {' · '}
                  {matrixData.pageMetadata.totalWorkflows} total workflows
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(1)}
                  >
                    First
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(currentPage - 1)}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!matrixData.pageMetadata.hasMore}
                    onClick={() => setCurrentPage(currentPage + 1)}
                  >
                    Next
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!matrixData.pageMetadata.hasMore}
                    onClick={() => setCurrentPage(matrixData.pageMetadata.totalPages)}
                  >
                    Last
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
