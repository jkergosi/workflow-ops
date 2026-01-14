import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  FileQuestion,
  Loader2,
  Server,
  ChevronDown,
  ChevronRight
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api-client';
import type {
  UntrackedWorkflowsResponse,
  EnvironmentUntrackedWorkflows,
  OnboardWorkflowItem
} from '@/types';

interface SelectedWorkflow {
  environmentId: string;
  n8nWorkflowId: string;
}

export function UntrackedWorkflowsPage() {
  const [data, setData] = useState<UntrackedWorkflowsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [isOnboarding, setIsOnboarding] = useState(false);
  const [selectedWorkflows, setSelectedWorkflows] = useState<SelectedWorkflow[]>([]);
  const [expandedEnvironments, setExpandedEnvironments] = useState<Set<string>>(new Set());
  const [lastScanError, setLastScanError] = useState<string | null>(null);

  useEffect(() => {
    document.title = 'Untracked Workflows - WorkflowOps';
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const response = await apiClient.getUntrackedWorkflows();
      setData(response.data);

      // Auto-expand environments with untracked workflows
      const envIds = new Set(response.data.environments.map(e => e.environment_id));
      setExpandedEnvironments(envIds);
    } catch (error: any) {
      toast.error('Failed to load untracked workflows');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleScan = async () => {
    setIsScanning(true);
    setLastScanError(null);
    try {
      const response = await apiClient.scanEnvironmentsForUntracked();
      const { environments_scanned, environments_failed, results } = response.data;

      if (environments_failed > 0) {
        const failedEnvs = results
          .filter(r => r.status === 'failed')
          .map(r => `${r.environment_name}: ${r.error}`)
          .join('; ');
        setLastScanError(`${environments_failed} environment(s) failed to scan: ${failedEnvs}`);
        toast.warning(`Scanned ${environments_scanned} environments, ${environments_failed} failed`);
      } else {
        toast.success(`Scanned ${environments_scanned} environment(s) successfully`);
      }

      // Reload data after scan
      await loadData();
    } catch (error: any) {
      toast.error('Failed to scan environments');
      setLastScanError(error.message || 'Unknown error');
      console.error(error);
    } finally {
      setIsScanning(false);
    }
  };

  const handleOnboard = async () => {
    if (selectedWorkflows.length === 0) {
      toast.warning('Select at least one workflow to onboard');
      return;
    }

    setIsOnboarding(true);
    try {
      const workflows: OnboardWorkflowItem[] = selectedWorkflows.map(sw => ({
        environment_id: sw.environmentId,
        n8n_workflow_id: sw.n8nWorkflowId
      }));

      const response = await apiClient.onboardWorkflows(workflows);
      const { total_onboarded, total_skipped, total_failed } = response.data;

      if (total_failed > 0) {
        toast.warning(`Onboarded ${total_onboarded}, skipped ${total_skipped}, failed ${total_failed}`);
      } else if (total_onboarded > 0) {
        toast.success(`Successfully onboarded ${total_onboarded} workflow(s)`);
      } else {
        toast.info(`${total_skipped} workflow(s) were already onboarded`);
      }

      // Clear selection and reload
      setSelectedWorkflows([]);
      await loadData();
    } catch (error: any) {
      toast.error('Failed to onboard workflows');
      console.error(error);
    } finally {
      setIsOnboarding(false);
    }
  };

  const toggleEnvironmentExpanded = (envId: string) => {
    setExpandedEnvironments(prev => {
      const next = new Set(prev);
      if (next.has(envId)) {
        next.delete(envId);
      } else {
        next.add(envId);
      }
      return next;
    });
  };

  const isWorkflowSelected = (envId: string, workflowId: string) => {
    return selectedWorkflows.some(
      sw => sw.environmentId === envId && sw.n8nWorkflowId === workflowId
    );
  };

  const toggleWorkflowSelection = (envId: string, workflowId: string) => {
    setSelectedWorkflows(prev => {
      const exists = prev.some(
        sw => sw.environmentId === envId && sw.n8nWorkflowId === workflowId
      );
      if (exists) {
        return prev.filter(
          sw => !(sw.environmentId === envId && sw.n8nWorkflowId === workflowId)
        );
      } else {
        return [...prev, { environmentId: envId, n8nWorkflowId: workflowId }];
      }
    });
  };

  const toggleAllInEnvironment = (env: EnvironmentUntrackedWorkflows) => {
    const envWorkflows = env.untracked_workflows;
    const allSelected = envWorkflows.every(w =>
      isWorkflowSelected(env.environment_id, w.n8n_workflow_id)
    );

    if (allSelected) {
      // Deselect all in this environment
      setSelectedWorkflows(prev =>
        prev.filter(sw => sw.environmentId !== env.environment_id)
      );
    } else {
      // Select all in this environment
      const newSelections = envWorkflows
        .filter(w => !isWorkflowSelected(env.environment_id, w.n8n_workflow_id))
        .map(w => ({
          environmentId: env.environment_id,
          n8nWorkflowId: w.n8n_workflow_id
        }));
      setSelectedWorkflows(prev => [...prev, ...newSelections]);
    }
  };

  const selectAll = () => {
    if (!data) return;
    const allWorkflows: SelectedWorkflow[] = [];
    for (const env of data.environments) {
      for (const workflow of env.untracked_workflows) {
        allWorkflows.push({
          environmentId: env.environment_id,
          n8nWorkflowId: workflow.n8n_workflow_id
        });
      }
    }
    setSelectedWorkflows(allWorkflows);
  };

  const deselectAll = () => {
    setSelectedWorkflows([]);
  };

  if (isLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Untracked Workflows</h1>
          <p className="text-muted-foreground mt-2">
            Workflows in n8n that are not yet tracked in the canonical system
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handleScan}
            disabled={isScanning}
          >
            {isScanning ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Scan Environments
          </Button>
          <Button
            onClick={handleOnboard}
            disabled={isOnboarding || selectedWorkflows.length === 0}
          >
            {isOnboarding ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-2 h-4 w-4" />
            )}
            Onboard Selected ({selectedWorkflows.length})
          </Button>
        </div>
      </div>

      {lastScanError && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{lastScanError}</AlertDescription>
        </Alert>
      )}

      {data && data.total_untracked === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <CheckCircle2 className="h-12 w-12 text-green-500 mb-4" />
            <h3 className="text-lg font-medium mb-2">All Workflows Tracked</h3>
            <p className="text-muted-foreground text-center max-w-md">
              All workflows in your environments are tracked in the canonical system.
              Click "Scan Environments" to check for new workflows.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Selection controls */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <FileQuestion className="h-5 w-5" />
                    Untracked Workflows ({data?.total_untracked || 0})
                  </CardTitle>
                  <CardDescription>
                    Select workflows to onboard into the canonical system
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={selectAll}>
                    Select All
                  </Button>
                  <Button variant="ghost" size="sm" onClick={deselectAll}>
                    Deselect All
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {data?.environments.map(env => (
                <div key={env.environment_id} className="border rounded-lg mb-4 last:mb-0">
                  {/* Environment header */}
                  <div
                    className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted/50"
                    onClick={() => toggleEnvironmentExpanded(env.environment_id)}
                  >
                    <div className="flex items-center gap-3">
                      {expandedEnvironments.has(env.environment_id) ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                      <Server className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium">{env.environment_name}</span>
                      <Badge variant="outline" className="text-xs">
                        {env.environment_class}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">
                        {env.untracked_workflows.length} untracked
                      </Badge>
                      <Checkbox
                        checked={env.untracked_workflows.every(w =>
                          isWorkflowSelected(env.environment_id, w.n8n_workflow_id)
                        )}
                        onCheckedChange={() => toggleAllInEnvironment(env)}
                        onClick={e => e.stopPropagation()}
                      />
                    </div>
                  </div>

                  {/* Workflow table */}
                  {expandedEnvironments.has(env.environment_id) && (
                    <div className="border-t">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-12"></TableHead>
                            <TableHead>Workflow Name</TableHead>
                            <TableHead>n8n ID</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Created</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {env.untracked_workflows.map(workflow => (
                            <TableRow key={workflow.n8n_workflow_id}>
                              <TableCell>
                                <Checkbox
                                  checked={isWorkflowSelected(
                                    env.environment_id,
                                    workflow.n8n_workflow_id
                                  )}
                                  onCheckedChange={() =>
                                    toggleWorkflowSelection(
                                      env.environment_id,
                                      workflow.n8n_workflow_id
                                    )
                                  }
                                />
                              </TableCell>
                              <TableCell className="font-medium">
                                {workflow.name}
                              </TableCell>
                              <TableCell className="font-mono text-xs text-muted-foreground">
                                {workflow.n8n_workflow_id}
                              </TableCell>
                              <TableCell>
                                <Badge
                                  variant={workflow.active ? 'default' : 'secondary'}
                                >
                                  {workflow.active ? 'Active' : 'Inactive'}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-muted-foreground">
                                {workflow.created_at
                                  ? new Date(workflow.created_at).toLocaleDateString()
                                  : '-'}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
