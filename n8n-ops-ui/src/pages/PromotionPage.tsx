// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { apiClient } from '@/lib/api-client';
import { ArrowLeft, Play, AlertTriangle, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import type { Pipeline, Environment, WorkflowSelection, WorkflowChangeType } from '@/types';
import type { CredentialPreflightResult } from '@/types/credentials';
import { CredentialPreflightDialog } from '@/components/promotion/CredentialPreflightDialog';

export function PromotionPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [selectedPipelineId, setSelectedPipelineId] = useState<string>('');
  const [selectedStageIndex, setSelectedStageIndex] = useState<number>(-1);
  const [workflowSelections, setWorkflowSelections] = useState<WorkflowSelection[]>([]);
  const [showReviewDialog, setShowReviewDialog] = useState(false);
  const [promotionId, setPromotionId] = useState<string | null>(null);
  const [dependencyWarnings, setDependencyWarnings] = useState<Record<string, Array<{workflowId: string; workflowName: string; reason: string; message: string}>>>({});
  const [isLoadingWorkflows, setIsLoadingWorkflows] = useState(false);

  // Credential preflight state
  const [showPreflightDialog, setShowPreflightDialog] = useState(false);
  const [preflightResult, setPreflightResult] = useState<CredentialPreflightResult | null>(null);

  const { data: pipelines } = useQuery({
    queryKey: ['pipelines'],
    queryFn: () => apiClient.getPipelines(),
  });

  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const selectedPipeline = useMemo(() => {
    return pipelines?.data?.find(p => p.id === selectedPipelineId);
  }, [pipelines, selectedPipelineId]);

  // Get the active stage from the selected pipeline and stage index
  const activeStage = useMemo(() => {
    if (!selectedPipeline || selectedStageIndex < 0) return null;
    return selectedPipeline.stages[selectedStageIndex] || null;
  }, [selectedPipeline, selectedStageIndex]);

  // Derive source and target environment IDs from the selected stage
  const sourceEnvId = activeStage?.sourceEnvironmentId || null;
  const targetEnvId = activeStage?.targetEnvironmentId || null;

  const sourceEnv = useMemo(() => {
    return environments?.data?.find(e => e.id === sourceEnvId);
  }, [environments, sourceEnvId]);

  const targetEnv = useMemo(() => {
    return environments?.data?.find(e => e.id === targetEnvId);
  }, [environments, targetEnvId]);

  // Reset stage selection when pipeline changes
  useEffect(() => {
    setSelectedStageIndex(-1);
    setWorkflowSelections([]);
  }, [selectedPipelineId]);

  // Helper to get environment name by ID
  const getEnvName = (envId: string) => {
    return environments?.data?.find(e => e.id === envId)?.name || 'Unknown';
  };

  // Load workflows from source environment when stage is selected
  useEffect(() => {
    const loadWorkflows = async () => {
      if (!sourceEnvId || !targetEnvId || !sourceEnv) {
        setWorkflowSelections([]);
        return;
      }

      setIsLoadingWorkflows(true);
      try {
        // Fetch workflows from source environment
        const sourceWorkflows = await apiClient.getWorkflows(sourceEnvId);

        // Fetch workflows from target environment for comparison
        let targetWorkflows: any[] = [];
        try {
          const targetResponse = await apiClient.getWorkflows(targetEnvId);
          targetWorkflows = targetResponse.data || [];
        } catch {
          // Target might not have workflows yet, that's ok
        }

        // Create a map of target workflows by name for comparison
        const targetWorkflowMap = new Map(
          targetWorkflows.map(w => [w.name, w])
        );

        // Transform to WorkflowSelection format
        const selections: WorkflowSelection[] = (sourceWorkflows.data || []).map(workflow => {
          const targetWorkflow = targetWorkflowMap.get(workflow.name);
          let changeType: WorkflowChangeType = 'new';

          if (targetWorkflow) {
            // Workflow exists in target - check if it's changed
            // For now, simple check - in production you'd compare hashes/content
            changeType = 'changed';
          }

          return {
            workflowId: workflow.id,
            workflowName: workflow.name,
            changeType,
            enabledInSource: workflow.active || false,
            enabledInTarget: targetWorkflow?.active,
            selected: changeType !== 'conflict',
            requiresOverwrite: !!targetWorkflow,
          };
        });

        setWorkflowSelections(selections);
      } catch (error) {
        console.error('Failed to load workflows:', error);
        toast.error('Failed to load workflows from source environment');
        setWorkflowSelections([]);
      } finally {
        setIsLoadingWorkflows(false);
      }
    };

    loadWorkflows();
  }, [sourceEnvId, targetEnvId, sourceEnv]);

  const initiateMutation = useMutation({
    mutationFn: () => {
      if (!selectedPipelineId || !sourceEnvId || !targetEnvId) {
        throw new Error('Missing required parameters');
      }
      return apiClient.initiatePromotion({
        pipelineId: selectedPipelineId,
        sourceEnvironmentId: sourceEnvId,
        targetEnvironmentId: targetEnvId,
        workflowSelections: workflowSelections.filter(ws => ws.selected),
      });
    },
    onSuccess: (data) => {
      const promotionId = data.data.promotion_id;

      if (data.data.requires_approval) {
        toast.info('Deployment started - requires approval');
      } else {
        toast.success('Deployment started successfully');
        // Auto-execute in background if no approval needed
        apiClient.executePromotion(promotionId).catch(() => {
          // Error will be visible on deployments page
        });
      }

      // Redirect to deployments page immediately so user can monitor progress
      queryClient.invalidateQueries({ queryKey: ['deployments'] });
      navigate('/deployments');
    },
    onError: (error: any) => {
      const detail = error.response?.data?.detail;
      // Handle validation errors (array of objects) vs string errors
      const message = Array.isArray(detail)
        ? detail.map((e: any) => e.msg || e.message).join(', ')
        : (typeof detail === 'string' ? detail : 'Failed to initiate deployment');
      toast.error(message);
    },
  });

  const executeMutation = useMutation({
    mutationFn: (id: string) => apiClient.executePromotion(id),
    onSuccess: () => {
      toast.success('Deployment executed successfully');
      queryClient.invalidateQueries({ queryKey: ['promotions'] });
      navigate('/deployments');
    },
    onError: (error: any) => {
      const detail = error.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map((e: any) => e.msg || e.message).join(', ')
        : (typeof detail === 'string' ? detail : 'Failed to execute deployment');
      toast.error(message);
    },
  });

  // Credential preflight mutation
  const preflightMutation = useMutation({
    mutationFn: () => {
      if (!sourceEnvId || !targetEnvId) {
        throw new Error('Missing environment IDs');
      }
      const selectedWorkflowIds = workflowSelections
        .filter(ws => ws.selected)
        .map(ws => ws.workflowId);
      return apiClient.credentialPreflightCheck({
        source_environment_id: sourceEnvId,
        target_environment_id: targetEnvId,
        workflow_ids: selectedWorkflowIds,
        provider: sourceEnv?.provider || 'n8n',
      });
    },
    onSuccess: (data) => {
      setPreflightResult(data.data);
      // If there are any issues (blocking or warnings), show the dialog
      if (data.data.blocking_issues.length > 0 || data.data.warnings.length > 0) {
        setShowPreflightDialog(true);
      } else {
        // No issues, proceed directly to initiation
        initiateMutation.mutate();
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to run credential preflight check');
      // Still allow proceeding if preflight fails (graceful degradation)
      initiateMutation.mutate();
    },
  });

  const handleWorkflowToggle = (workflowId: string, selected: boolean) => {
    setWorkflowSelections(prev =>
      prev.map(ws =>
        ws.workflowId === workflowId ? { ...ws, selected } : ws
      )
    );
  };

  const handleInitiate = () => {
    if (!selectedPipelineId) {
      toast.error('Please select a pipeline');
      return;
    }

    if (workflowSelections.filter(ws => ws.selected).length === 0) {
      toast.error('Please select at least one workflow to deploy');
      return;
    }

    // Skip preflight for now and go straight to initiation
    // TODO: Re-enable preflight check once endpoint is working
    // preflightMutation.mutate();
    initiateMutation.mutate();
  };

  const handlePreflightProceed = () => {
    setShowPreflightDialog(false);
    initiateMutation.mutate();
  };

  const handlePreflightCancel = () => {
    setShowPreflightDialog(false);
    setPreflightResult(null);
  };

  const getChangeTypeBadge = (changeType: WorkflowChangeType) => {
    const variants: Record<WorkflowChangeType, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
      new: { variant: 'default', label: 'New to Target' },
      changed: { variant: 'secondary', label: 'Will Update' },
      staging_hotfix: { variant: 'destructive', label: 'Target Hotfix' },
      conflict: { variant: 'destructive', label: 'Conflict' },
      unchanged: { variant: 'outline', label: 'Unchanged' },
    };

    const config = variants[changeType];
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };


  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/deployments')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold">New Deployment</h1>
            <p className="text-muted-foreground">
              Deploy workflows from {sourceEnv?.name || 'source'} to {targetEnv?.name || 'target'}
            </p>
          </div>
        </div>
      </div>

      {/* Pipeline Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Pipeline & Stage Selection</CardTitle>
          <CardDescription>
            Select a pipeline and the stage (environment transition) you want to deploy
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="pipeline">Pipeline</Label>
              <Select value={selectedPipelineId} onValueChange={setSelectedPipelineId}>
                <SelectTrigger id="pipeline">
                  <SelectValue placeholder="Select a pipeline..." />
                </SelectTrigger>
                <SelectContent>
                  {pipelines?.data
                    ?.filter(p => p.isActive)
                    .map(pipeline => (
                      <SelectItem key={pipeline.id} value={pipeline.id}>
                        {pipeline.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>

            {selectedPipeline && selectedPipeline.stages.length > 0 && (
              <div className="space-y-2">
                <Label htmlFor="stage">Promotion Stage</Label>
                <Select
                  value={selectedStageIndex >= 0 ? String(selectedStageIndex) : ''}
                  onValueChange={(val) => setSelectedStageIndex(parseInt(val, 10))}
                >
                  <SelectTrigger id="stage">
                    <SelectValue placeholder="Select a stage to deploy..." />
                  </SelectTrigger>
                  <SelectContent>
                    {selectedPipeline.stages.map((stage, index) => (
                      <SelectItem key={index} value={String(index)}>
                        {getEnvName(stage.sourceEnvironmentId)} → {getEnvName(stage.targetEnvironmentId)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {selectedPipeline && selectedPipeline.stages.length === 0 && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  This pipeline has no stages configured. Please edit the pipeline to add stages.
                </AlertDescription>
              </Alert>
            )}

            {activeStage && (
              <Alert>
                <CheckCircle className="h-4 w-4" />
                <AlertDescription>
                  Ready to deploy: {sourceEnv?.name} → {targetEnv?.name}
                  {activeStage.approvals?.requireApproval && (
                    <span className="ml-2 text-muted-foreground">
                      (Requires approval)
                    </span>
                  )}
                </AlertDescription>
              </Alert>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Workflow Selection */}
      {selectedPipelineId && activeStage && (
        <Card>
          <CardHeader>
            <CardTitle>Workflow Selection</CardTitle>
            <CardDescription>
              Select workflows to deploy. Only workflows with changes in the source environment are shown by default.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingWorkflows ? (
              <div className="text-center py-8">
                <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                <p className="text-muted-foreground">Loading workflow comparisons...</p>
              </div>
            ) : workflowSelections.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p>No workflows to compare. Workflows will be loaded after selecting a pipeline.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <Checkbox
                        checked={workflowSelections.every(ws => ws.selected || ws.changeType === 'conflict')}
                        onCheckedChange={(checked) => {
                          setWorkflowSelections(prev =>
                            prev.map(ws => ({
                              ...ws,
                              selected: ws.changeType === 'conflict' ? false : checked === true,
                            }))
                          );
                        }}
                      />
                    </TableHead>
                    <TableHead>Workflow Name</TableHead>
                    <TableHead>Change Type</TableHead>
                    <TableHead>Source Status</TableHead>
                    <TableHead>Target Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {workflowSelections
                    .filter(ws => ws.changeType !== 'unchanged') // Only show changed workflows by default
                    .map((workflow) => (
                  <TableRow key={workflow.workflowId}>
                    <TableCell>
                      <Checkbox
                        checked={workflow.selected}
                        onCheckedChange={(checked) =>
                          handleWorkflowToggle(workflow.workflowId, checked === true)
                        }
                        disabled={workflow.changeType === 'conflict' || (workflow.changeType === 'staging_hotfix' && !activeStage?.policyFlags?.allowOverwritingHotfixes)}
                      />
                    </TableCell>
                    <TableCell className="font-medium">{workflow.workflowName}</TableCell>
                    <TableCell>{getChangeTypeBadge(workflow.changeType)}</TableCell>
                    <TableCell>
                      {workflow.enabledInSource ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <Badge variant="outline">Inactive</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {workflow.enabledInTarget !== undefined ? (
                        workflow.enabledInTarget ? (
                          <Badge variant="success">Active</Badge>
                        ) : (
                          <Badge variant="outline">Inactive</Badge>
                        )
                      ) : (
                        <span className="text-muted-foreground">N/A</span>
                      )}
                    </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            {workflowSelections.some(ws => ws.changeType === 'conflict') && (
              <Alert className="mt-4" variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Some workflows have conflicts and cannot be deployed. Please resolve conflicts manually in the source environment.
                </AlertDescription>
              </Alert>
            )}

            {workflowSelections.some(ws => ws.changeType === 'staging_hotfix' && !activeStage?.policyFlags?.allowOverwritingHotfixes) && (
              <Alert className="mt-4">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Some workflows were modified in the target environment (hotfixes). Overwriting hotfixes is not allowed by this pipeline's policy.
                </AlertDescription>
              </Alert>
            )}

            {/* Dependency Warnings */}
            {Object.keys(dependencyWarnings).length > 0 && (
              <div className="mt-4 space-y-3">
                <h4 className="font-semibold text-sm">Dependency Warnings</h4>
                {Object.entries(dependencyWarnings).map(([workflowId, deps]) => {
                  const workflow = workflowSelections.find(ws => ws.workflowId === workflowId);
                  return (
                    <Alert key={workflowId} className="border-yellow-500">
                      <AlertTriangle className="h-4 w-4 text-yellow-600" />
                      <AlertDescription>
                        <div className="space-y-2">
                          <p className="font-medium">
                            {workflow?.workflowName || workflowId} depends on:
                          </p>
                          <ul className="list-disc list-inside space-y-1 ml-4">
                            {deps.map((dep, idx) => (
                              <li key={idx} className="text-sm">
                                {dep.workflowName} - {dep.message}
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="ml-2 h-6 text-xs"
                                  onClick={() => {
                                    // Add dependency to selections
                                    const depWorkflow = workflowSelections.find(ws => ws.workflowId === dep.workflowId);
                                    if (depWorkflow && !depWorkflow.selected) {
                                      handleWorkflowToggle(dep.workflowId, true);
                                      toast.info(`Added ${dep.workflowName} to promotion`);
                                    }
                                  }}
                                >
                                  Include
                                </Button>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </AlertDescription>
                    </Alert>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      {selectedPipelineId && activeStage && (
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => navigate('/deployments')}>
            Cancel
          </Button>
          <Button
            onClick={handleInitiate}
            disabled={preflightMutation.isPending || initiateMutation.isPending || workflowSelections.filter(ws => ws.selected).length === 0}
          >
            {preflightMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Checking Credentials...
              </>
            ) : initiateMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Initiating...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Create Deployment
              </>
            )}
          </Button>
        </div>
      )}

      {/* Review/Approval Dialog */}
      <Dialog open={showReviewDialog} onOpenChange={setShowReviewDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Deployment Review</DialogTitle>
            <DialogDescription>
              Review the deployment details and gate results
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <h4 className="font-semibold mb-2">Selected Workflows</h4>
              <ul className="list-disc list-inside space-y-1">
                {workflowSelections.filter(ws => ws.selected).map(ws => (
                  <li key={ws.workflowId}>
                    {ws.workflowName} ({getChangeTypeBadge(ws.changeType).props.children})
                  </li>
                ))}
              </ul>
            </div>

            {/* Dependency Warnings */}
            {Object.keys(dependencyWarnings).length > 0 && (
              <div>
                <h4 className="font-semibold mb-2">Dependency Warnings</h4>
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    {Object.values(dependencyWarnings).flat().length} dependency warning(s) found.
                    Review the workflow selection to ensure all dependencies are included.
                  </AlertDescription>
                </Alert>
              </div>
            )}

            {/* Gate Results */}
            {initiateMutation.data?.data?.gate_results && (
              <div>
                <h4 className="font-semibold mb-2">Pre-flight Validation</h4>
                <div className="space-y-2">
                  {initiateMutation.data.data.gate_results.warnings?.map((warning: string, i: number) => (
                    <Alert key={i}>
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>{warning}</AlertDescription>
                    </Alert>
                  ))}
                  {initiateMutation.data.data.gate_results.errors?.map((error: string, i: number) => (
                    <Alert key={i} variant="destructive">
                      <XCircle className="h-4 w-4" />
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  ))}
                  {initiateMutation.data.data.gate_results.errors?.length === 0 && 
                   initiateMutation.data.data.gate_results.warnings?.length === 0 && (
                    <Alert>
                      <CheckCircle className="h-4 w-4" />
                      <AlertDescription>All gates passed. Ready to deploy.</AlertDescription>
                    </Alert>
                  )}
                </div>
              </div>
            )}

            {/* Schedule Check */}
            {activeStage?.schedule?.restrictPromotionTimes && (
              <div>
                <h4 className="font-semibold mb-2">Schedule</h4>
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    Promotions are restricted to: {activeStage.schedule.allowedDays?.join(', ')} 
                    between {activeStage.schedule.startTime} and {activeStage.schedule.endTime}
                  </AlertDescription>
                </Alert>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowReviewDialog(false)}>
              Cancel
            </Button>
            {promotionId && (
              <Button onClick={() => executeMutation.mutate(promotionId)}>
                Execute Deployment
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Credential Preflight Dialog */}
      <CredentialPreflightDialog
        open={showPreflightDialog}
        onOpenChange={setShowPreflightDialog}
        preflightResult={preflightResult}
        onProceed={handlePreflightProceed}
        onCancel={handlePreflightCancel}
        isLoading={initiateMutation.isPending}
      />
    </div>
  );
}

