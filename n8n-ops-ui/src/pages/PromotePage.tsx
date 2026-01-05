// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
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
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { apiClient } from '@/lib/api-client';
import { ArrowLeft, Play, AlertTriangle, CheckCircle, XCircle, Loader2, GitCompare, ChevronRight, Info, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';
import type { Pipeline, Environment } from '@/types';
import type { CredentialPreflightResult, CredentialIssue } from '@/types/credentials';
import { CredentialPreflightDialog } from '@/components/promotion/CredentialPreflightDialog';
import { InlineMappingDialog } from '@/components/promotion/InlineMappingDialog';
import { WorkflowDiffDialog } from '@/components/promotion/WorkflowDiffDialog';

// Types for the new backend compare response
type DiffStatus = 'added' | 'modified' | 'deleted' | 'unchanged' | 'target_hotfix';
type RiskLevel = 'low' | 'medium' | 'high';

interface WorkflowCompareResult {
  workflowId: string;
  name: string;
  diffStatus: DiffStatus;
  riskLevel: RiskLevel;
  changeCategories: string[];
  diffHash?: string;
  detailsAvailable: boolean;
  sourceUpdatedAt?: string;
  targetUpdatedAt?: string;
  enabledInSource: boolean;
  enabledInTarget?: boolean;
}

interface CompareSummary {
  total: number;
  added: number;
  modified: number;
  deleted: number;
  unchanged: number;
  targetHotfix: number;
}

interface CompareResult {
  pipelineId: string;
  stageId: string;
  sourceEnvId: string;
  targetEnvId: string;
  summary: CompareSummary;
  workflows: WorkflowCompareResult[];
}

// Selection state for workflows
interface WorkflowSelectionState {
  workflowId: string;
  selected: boolean;
}

export function PromotePage() {
  useEffect(() => {
    document.title = 'Promote Workflows - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [selectedPipelineId, setSelectedPipelineId] = useState<string>('');
  const [selectedStageIndex, setSelectedStageIndex] = useState<number>(-1);
  const [workflowSelections, setWorkflowSelections] = useState<Map<string, boolean>>(new Map());
  const [showReviewDialog, setShowReviewDialog] = useState(false);
  const [deploymentId, setDeploymentId] = useState<string | null>(null);
  const [initiateResponse, setInitiateResponse] = useState<any>(null);
  const [dependencyWarnings, setDependencyWarnings] = useState<Record<string, Array<{workflowId: string; workflowName: string; reason: string; message: string}>>>({});

  // View toggles
  const [showUnchanged, setShowUnchanged] = useState(false);
  const [showTargetOnly, setShowTargetOnly] = useState(false);
  const [targetOnlyExpanded, setTargetOnlyExpanded] = useState(false);

  // Credential preflight state
  const [showPreflightDialog, setShowPreflightDialog] = useState(false);
  const [executionMode, setExecutionMode] = useState<'now' | 'schedule'>('now');
  const [scheduledDateTime, setScheduledDateTime] = useState<string>('');
  const [preflightResult, setPreflightResult] = useState<CredentialPreflightResult | null>(null);
  const [showMappingDialog, setShowMappingDialog] = useState(false);
  const [selectedIssue, setSelectedIssue] = useState<CredentialIssue | null>(null);
  const [showDiffDialog, setShowDiffDialog] = useState(false);
  const [selectedWorkflowForDiff, setSelectedWorkflowForDiff] = useState<WorkflowCompareResult | null>(null);

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
    setWorkflowSelections(new Map());
  }, [selectedPipelineId]);

  // Helper to get environment name by ID
  const getEnvName = (envId: string) => {
    return environments?.data?.find(e => e.id === envId)?.name || 'Unknown';
  };

  // Use the backend compare endpoint
  const {
    data: compareResult,
    isLoading: isLoadingCompare,
    error: compareError,
  } = useQuery({
    queryKey: ['promotion-compare', selectedPipelineId, selectedStageIndex],
    queryFn: async () => {
      if (!selectedPipelineId || selectedStageIndex < 0 || !activeStage) {
        return null;
      }
      // Use stage index as the stage_id (backend will match by index)
      // Ensure we're passing a clean numeric string
      const stageId = String(selectedStageIndex);
      if (isNaN(selectedStageIndex) || selectedStageIndex < 0) {
        throw new Error(`Invalid stage index: ${selectedStageIndex}`);
      }
      const result = await apiClient.compareEnvironments(selectedPipelineId, stageId);
      return result.data as CompareResult;
    },
    enabled: !!selectedPipelineId && selectedStageIndex >= 0 && !!activeStage,
  });

  // Initialize selections when compare result changes
  // Pre-select only 'added' and 'modified' workflows
  useEffect(() => {
    if (compareResult?.workflows) {
      const newSelections = new Map<string, boolean>();
      compareResult.workflows.forEach(w => {
        // Only pre-select added and modified
        // NOT pre-selected: unchanged, target_hotfix, deleted
        const shouldSelect = w.diffStatus === 'added' || w.diffStatus === 'modified';
        newSelections.set(w.workflowId, shouldSelect);
      });
      setWorkflowSelections(newSelections);
    }
  }, [compareResult]);

  // Categorize workflows for display
  const categorizedWorkflows = useMemo(() => {
    if (!compareResult?.workflows) {
      return { actionable: [], unchanged: [], targetOnly: [] };
    }

    const actionable: WorkflowCompareResult[] = [];
    const unchanged: WorkflowCompareResult[] = [];
    const targetOnly: WorkflowCompareResult[] = [];

    compareResult.workflows.forEach(w => {
      if (w.diffStatus === 'unchanged') {
        unchanged.push(w);
      } else if (w.diffStatus === 'deleted') {
        targetOnly.push(w);
      } else {
        // added, modified, target_hotfix
        actionable.push(w);
      }
    });

    return { actionable, unchanged, targetOnly };
  }, [compareResult]);

  // Count selected workflows (excluding target-only which are never selectable)
  const selectedCount = useMemo(() => {
    if (!compareResult?.workflows) return 0;
    return compareResult.workflows.filter(w =>
      w.diffStatus !== 'deleted' && workflowSelections.get(w.workflowId)
    ).length;
  }, [compareResult, workflowSelections]);

  const initiateMutation = useMutation({
    mutationFn: () => {
      if (!selectedPipelineId || !sourceEnvId || !targetEnvId) {
        throw new Error('Missing required parameters');
      }
      // Transform compare results to workflow selections for initiate
      const selections = compareResult?.workflows
        .filter(w => w.diffStatus !== 'deleted' && workflowSelections.get(w.workflowId))
        .map(w => ({
          workflowId: w.workflowId,
          workflowName: w.name,
          changeType: w.diffStatus === 'added' ? 'new' :
                      w.diffStatus === 'modified' ? 'changed' :
                      w.diffStatus === 'target_hotfix' ? 'staging_hotfix' : 'unchanged',
          enabledInSource: w.enabledInSource,
          enabledInTarget: w.enabledInTarget,
          selected: true,
          requiresOverwrite: w.diffStatus !== 'added',
        })) || [];

      return apiClient.initiateDeployment({
        pipelineId: selectedPipelineId,
        sourceEnvironmentId: sourceEnvId,
        targetEnvironmentId: targetEnvId,
        workflowSelections: selections,
      });
    },
    onSuccess: (data) => {
      const deploymentId = data.data.deployment_id || data.data.promotion_id;
      setDeploymentId(deploymentId);
      setInitiateResponse(data.data);

      // Store dependency warnings from the response
      if (data.data.dependency_warnings) {
        setDependencyWarnings(data.data.dependency_warnings);
      }

      // Check for critical errors that should block execution
      const hasErrors = data.data.gate_results?.errors?.length > 0;
      const requiresApproval = data.data.requires_approval;

      // If there are blocking errors, show review dialog
      if (hasErrors) {
        setShowReviewDialog(true);
        return;
      }

      // If approval required, show review dialog
      if (requiresApproval) {
        setShowReviewDialog(true);
        return;
      }

      // Otherwise, execute immediately with the scheduling choice from the main page
      const scheduledAt = executionMode === 'schedule' && scheduledDateTime
        ? new Date(scheduledDateTime).toISOString()
        : undefined;

      executeMutation.mutate({ id: deploymentId, scheduledAt });
    },
    onError: (error: any) => {
      const detail = error.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map((e: any) => e.msg || e.message).join(', ')
        : (typeof detail === 'string' ? detail : 'Failed to initiate promotion');
      toast.error(message);
    },
  });

  const executeMutation = useMutation({
    mutationFn: ({ id, scheduledAt }: { id: string; scheduledAt?: string }) =>
      apiClient.executeDeployment(id, scheduledAt),
    onSuccess: (data) => {
      const jobId = data.data.job_id;
      const promotionId = data.data.promotion_id;
      const scheduledAt = data.data.scheduled_at;

      // Reset review dialog state
      setShowReviewDialog(false);
      setExecutionMode('now');
      setScheduledDateTime('');
      setInitiateResponse(null);

      if (scheduledAt) {
        const scheduledDate = new Date(scheduledAt);
        toast.success(`Promotion scheduled for ${scheduledDate.toLocaleString()}`);
      } else if (jobId && promotionId) {
        toast.success('Promotion started successfully');
      } else {
        toast.success('Promotion executed successfully');
      }

      // Always redirect to deployments page - it has working progress tracking
      queryClient.invalidateQueries({ queryKey: ['promotions'] });
      queryClient.invalidateQueries({ queryKey: ['deployments'] });
      navigate('/deployments');
    },
    onError: (error: any) => {
      const detail = error.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map((e: any) => e.msg || e.message).join(', ')
        : (typeof detail === 'string' ? detail : 'Failed to execute promotion');
      toast.error(message);
      // Re-open review dialog on error so user can try again
      setShowReviewDialog(true);
    },
  });

  // Credential preflight mutation
  const preflightMutation = useMutation({
    mutationFn: () => {
      if (!sourceEnvId || !targetEnvId) {
        throw new Error('Missing environment IDs');
      }
      const selectedWorkflowIds = compareResult?.workflows
        .filter(w => w.diffStatus !== 'deleted' && workflowSelections.get(w.workflowId))
        .map(w => w.workflowId) || [];
      return apiClient.credentialPreflightCheck({
        source_environment_id: sourceEnvId,
        target_environment_id: targetEnvId,
        workflow_ids: selectedWorkflowIds,
        provider: sourceEnv?.provider || 'n8n',
      });
    },
    onSuccess: (data) => {
      setPreflightResult(data.data);
      if (data.data.blocking_issues.length > 0 || data.data.warnings.length > 0) {
        setShowPreflightDialog(true);
      } else {
        initiateMutation.mutate();
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to run credential preflight check');
      initiateMutation.mutate();
    },
  });

  const handleWorkflowToggle = (workflowId: string, selected: boolean) => {
    setWorkflowSelections(prev => {
      const newMap = new Map(prev);
      newMap.set(workflowId, selected);
      return newMap;
    });
  };

  const handleSelectAll = (checked: boolean) => {
    if (!compareResult?.workflows) return;
    setWorkflowSelections(prev => {
      const newMap = new Map(prev);
      // Only toggle selectable workflows (not deleted/target-only)
      compareResult.workflows
        .filter(w => w.diffStatus !== 'deleted')
        .forEach(w => newMap.set(w.workflowId, checked));
      return newMap;
    });
  };

  const handleInitiate = () => {
    if (!selectedPipelineId) {
      toast.error('Please select a pipeline');
      return;
    }

    if (selectedCount === 0) {
      toast.error('Please select at least one workflow to promote');
      return;
    }

    // Only run credential preflight check if the gate is enabled in stage settings
    if (activeStage?.gates?.credentialsExistInTarget) {
      preflightMutation.mutate();
    } else {
      initiateMutation.mutate();
    }
  };

  const handleMapCredential = (issue: CredentialIssue) => {
    setSelectedIssue(issue);
    setShowMappingDialog(true);
  };

  const handleMappingCreated = () => {
    preflightMutation.mutate();
  };

  const handlePreflightProceed = () => {
    setShowPreflightDialog(false);
    initiateMutation.mutate();
  };

  const handlePreflightCancel = () => {
    setShowPreflightDialog(false);
    setPreflightResult(null);
  };

  const getStatusBadge = (diffStatus: DiffStatus) => {
    const variants: Record<DiffStatus, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string; className: string }> = {
      added: { variant: 'default', label: 'Added', className: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200' },
      modified: { variant: 'secondary', label: 'Modified', className: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' },
      deleted: { variant: 'outline', label: 'Target-only', className: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
      unchanged: { variant: 'outline', label: 'Unchanged', className: 'bg-gray-50 text-gray-500 dark:bg-gray-900 dark:text-gray-500' },
      target_hotfix: { variant: 'destructive', label: 'Target Modified', className: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' },
    };

    const config = variants[diffStatus];
    return <Badge className={config.className}>{config.label}</Badge>;
  };

  const getRiskBadge = (riskLevel: RiskLevel) => {
    const variants: Record<RiskLevel, { className: string; label: string }> = {
      low: { className: 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-300', label: 'Low Risk' },
      medium: { className: 'bg-yellow-50 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300', label: 'Medium Risk' },
      high: { className: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300', label: 'High Risk' },
    };
    const config = variants[riskLevel];
    return <Badge variant="outline" className={config.className}>{config.label}</Badge>;
  };

  // Check if all selectable workflows are selected
  const allSelectableSelected = useMemo(() => {
    if (!compareResult?.workflows) return false;
    const selectable = compareResult.workflows.filter(w => w.diffStatus !== 'deleted');
    if (selectable.length === 0) return false;
    return selectable.every(w => workflowSelections.get(w.workflowId));
  }, [compareResult, workflowSelections]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/deployments')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold">Promote Workflows</h1>
            <p className="text-muted-foreground">
              Promote workflows from {sourceEnv?.name || 'source'} to {targetEnv?.name || 'target'}
            </p>
          </div>
        </div>
      </div>

      {/* Pipeline Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Pipeline & Stage Selection</CardTitle>
          <CardDescription>
            Select a pipeline and the stage (environment transition) for promotion
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
                <Label htmlFor="stage">Stage</Label>
                <Select
                  value={selectedStageIndex >= 0 ? String(selectedStageIndex) : ''}
                  onValueChange={(val) => setSelectedStageIndex(parseInt(val, 10))}
                >
                  <SelectTrigger id="stage">
                    <SelectValue placeholder="Select a stage to promote..." />
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
                  Ready to promote: {sourceEnv?.name} → {targetEnv?.name}
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

      {/* Summary Header */}
      {compareResult && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Comparison Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
              <div className="text-center p-3 rounded-lg bg-muted">
                <div className="text-2xl font-bold">{compareResult.summary.total}</div>
                <div className="text-xs text-muted-foreground">Total</div>
              </div>
              <div className="text-center p-3 rounded-lg bg-green-50 dark:bg-green-900/20">
                <div className="text-2xl font-bold text-green-700 dark:text-green-300">{compareResult.summary.added}</div>
                <div className="text-xs text-green-600 dark:text-green-400">Added</div>
              </div>
              <div className="text-center p-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
                <div className="text-2xl font-bold text-yellow-700 dark:text-yellow-300">{compareResult.summary.modified}</div>
                <div className="text-xs text-yellow-600 dark:text-yellow-400">Modified</div>
              </div>
              <div className="text-center p-3 rounded-lg bg-red-50 dark:bg-red-900/20">
                <div className="text-2xl font-bold text-red-700 dark:text-red-300">{compareResult.summary.targetHotfix}</div>
                <div className="text-xs text-red-600 dark:text-red-400">Target Modified</div>
              </div>
              <div className="text-center p-3 rounded-lg bg-gray-50 dark:bg-gray-800">
                <div className="text-2xl font-bold text-gray-500">{compareResult.summary.unchanged}</div>
                <div className="text-xs text-gray-400">Unchanged</div>
              </div>
              <div className="text-center p-3 rounded-lg bg-gray-100 dark:bg-gray-700">
                <div className="text-2xl font-bold text-gray-600 dark:text-gray-300">{compareResult.summary.deleted}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Target-only</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Workflow Selection */}
      {selectedPipelineId && activeStage && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Workflow Selection</CardTitle>
                <CardDescription>
                  Select workflows to promote. Added and Modified workflows are pre-selected.
                </CardDescription>
              </div>
              {/* Filter toggles */}
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Switch
                    id="show-unchanged"
                    checked={showUnchanged}
                    onCheckedChange={setShowUnchanged}
                  />
                  <Label htmlFor="show-unchanged" className="text-sm cursor-pointer">
                    {showUnchanged ? <Eye className="h-4 w-4 inline mr-1" /> : <EyeOff className="h-4 w-4 inline mr-1" />}
                    Unchanged ({compareResult?.summary.unchanged || 0})
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    id="show-target-only"
                    checked={showTargetOnly}
                    onCheckedChange={setShowTargetOnly}
                  />
                  <Label htmlFor="show-target-only" className="text-sm cursor-pointer">
                    {showTargetOnly ? <Eye className="h-4 w-4 inline mr-1" /> : <EyeOff className="h-4 w-4 inline mr-1" />}
                    Target-only ({compareResult?.summary.deleted || 0})
                  </Label>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isLoadingCompare ? (
              <div className="text-center py-8">
                <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
                <p className="text-muted-foreground">Comparing environments...</p>
              </div>
            ) : compareError ? (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Failed to compare environments: {(compareError as any)?.message || 'Unknown error'}
                </AlertDescription>
              </Alert>
            ) : !compareResult || compareResult.workflows.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <p>No workflows found. Select a pipeline stage to compare environments.</p>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Actionable Workflows (Added, Modified, Target Hotfix) */}
                {categorizedWorkflows.actionable.length > 0 && (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">
                          <Checkbox
                            checked={allSelectableSelected}
                            onCheckedChange={(checked) => handleSelectAll(checked === true)}
                          />
                        </TableHead>
                        <TableHead>Workflow Name</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Risk</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {categorizedWorkflows.actionable.map((workflow) => (
                        <TableRow key={workflow.workflowId}>
                          <TableCell>
                            <Checkbox
                              checked={workflowSelections.get(workflow.workflowId) || false}
                              onCheckedChange={(checked) =>
                                handleWorkflowToggle(workflow.workflowId, checked === true)
                              }
                              disabled={workflow.diffStatus === 'target_hotfix' && !activeStage?.policyFlags?.allowOverwritingHotfixes}
                            />
                          </TableCell>
                          <TableCell className="font-medium">{workflow.name}</TableCell>
                          <TableCell>{getStatusBadge(workflow.diffStatus)}</TableCell>
                          <TableCell>
                            {workflow.diffStatus !== 'added' && getRiskBadge(workflow.riskLevel)}
                          </TableCell>
                          <TableCell>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setSelectedWorkflowForDiff(workflow);
                                setShowDiffDialog(true);
                              }}
                            >
                              <GitCompare className="h-3 w-3 mr-1" />
                              View Diff
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}

                {/* Unchanged Workflows (hidden by default) */}
                {showUnchanged && categorizedWorkflows.unchanged.length > 0 && (
                  <div className="border-t pt-4">
                    <h4 className="font-medium mb-3 text-muted-foreground">Unchanged Workflows</h4>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-12">
                            <Checkbox disabled />
                          </TableHead>
                          <TableHead>Workflow Name</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {categorizedWorkflows.unchanged.map((workflow) => (
                          <TableRow key={workflow.workflowId} className="opacity-60">
                            <TableCell>
                              <Checkbox
                                checked={workflowSelections.get(workflow.workflowId) || false}
                                onCheckedChange={(checked) =>
                                  handleWorkflowToggle(workflow.workflowId, checked === true)
                                }
                              />
                            </TableCell>
                            <TableCell className="font-medium">{workflow.name}</TableCell>
                            <TableCell>{getStatusBadge(workflow.diffStatus)}</TableCell>
                            <TableCell>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => {
                                  setSelectedWorkflowForDiff(workflow);
                                  setShowDiffDialog(true);
                                }}
                              >
                                <GitCompare className="h-3 w-3 mr-1" />
                                View Details
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}

                {/* Target-only Workflows (separate section, never selectable) */}
                {showTargetOnly && categorizedWorkflows.targetOnly.length > 0 && (
                  <Collapsible open={targetOnlyExpanded} onOpenChange={setTargetOnlyExpanded} className="border-t pt-4">
                    <CollapsibleTrigger className="flex items-center gap-2 w-full text-left py-2 hover:bg-muted/50 rounded px-2 -mx-2">
                      <ChevronRight className={`h-4 w-4 transition-transform ${targetOnlyExpanded ? 'rotate-90' : ''}`} />
                      <span className="font-medium">Target-only Workflows ({categorizedWorkflows.targetOnly.length})</span>
                      <span className="text-sm text-muted-foreground ml-2">Not affected by promotion</span>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <Alert className="my-4">
                        <Info className="h-4 w-4" />
                        <AlertDescription>
                          These workflows exist in the target environment but not in source.
                          Promotions do not delete workflows - these are shown for visibility only.
                        </AlertDescription>
                      </Alert>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Workflow Name</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {categorizedWorkflows.targetOnly.map((workflow) => (
                            <TableRow key={workflow.workflowId} className="opacity-60">
                              {/* No checkbox - target-only workflows are never selectable */}
                              <TableCell className="font-medium">{workflow.name}</TableCell>
                              <TableCell>{getStatusBadge(workflow.diffStatus)}</TableCell>
                              <TableCell>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => {
                                    setSelectedWorkflowForDiff(workflow);
                                    setShowDiffDialog(true);
                                  }}
                                >
                                  View Details
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </CollapsibleContent>
                  </Collapsible>
                )}

                {/* Warnings */}
                {categorizedWorkflows.actionable.some(w => w.diffStatus === 'target_hotfix' && !activeStage?.policyFlags?.allowOverwritingHotfixes) && (
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
                      const workflow = compareResult?.workflows.find(w => w.workflowId === workflowId);
                      return (
                        <Alert key={workflowId} className="border-yellow-500">
                          <AlertTriangle className="h-4 w-4 text-yellow-600" />
                          <AlertDescription>
                            <div className="space-y-2">
                              <p className="font-medium">
                                {workflow?.name || workflowId} depends on:
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
                                        handleWorkflowToggle(dep.workflowId, true);
                                        toast.info(`Added ${dep.workflowName} to promotion`);
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
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      {selectedPipelineId && activeStage && compareResult && (
        <Card>
          <CardHeader>
            <CardTitle>Promotion Options</CardTitle>
            <CardDescription>
              Choose when to execute this promotion
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Execution Mode Selection */}
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <input
                  type="radio"
                  id="run-now-main"
                  name="execution-mode-main"
                  value="now"
                  checked={executionMode === 'now'}
                  onChange={() => {
                    setExecutionMode('now');
                    setScheduledDateTime('');
                  }}
                  className="h-4 w-4"
                />
                <Label htmlFor="run-now-main" className="cursor-pointer font-medium">
                  Run Now
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="radio"
                  id="schedule-main"
                  name="execution-mode-main"
                  value="schedule"
                  checked={executionMode === 'schedule'}
                  onChange={() => setExecutionMode('schedule')}
                  className="h-4 w-4"
                />
                <Label htmlFor="schedule-main" className="cursor-pointer font-medium">
                  Schedule for Later
                </Label>
              </div>
              {executionMode === 'schedule' && (
                <div className="ml-6 space-y-2">
                  <Label htmlFor="scheduled-datetime-main">Scheduled Date & Time</Label>
                  <Input
                    type="datetime-local"
                    id="scheduled-datetime-main"
                    value={scheduledDateTime}
                    onChange={(e) => setScheduledDateTime(e.target.value)}
                    min={new Date().toISOString().slice(0, 16)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Promotion will start at the specified time
                  </p>
                </div>
              )}
            </div>

            {/* Summary */}
            <div className="pt-2 border-t">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Selected Workflows:</span>
                <span className="font-medium">
                  {selectedCount} of {compareResult.summary.total - compareResult.summary.deleted}
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => navigate('/deployments')}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  if (executionMode === 'schedule' && !scheduledDateTime) {
                    toast.error('Please select a date and time for scheduling');
                    return;
                  }
                  handleInitiate();
                }}
                disabled={preflightMutation.isPending || initiateMutation.isPending || executeMutation.isPending || selectedCount === 0}
              >
                {preflightMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Checking Credentials...
                  </>
                ) : initiateMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    {executionMode === 'schedule' ? 'Scheduling...' : 'Creating...'}
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    {executionMode === 'schedule' ? 'Schedule Promotion' : `Promote to ${targetEnv?.name || 'Target'}`}
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Review/Approval Dialog */}
      <Dialog open={showReviewDialog} onOpenChange={setShowReviewDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Promotion Review</DialogTitle>
            <DialogDescription>
              Review the promotion details and gate results
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {/* Summary */}
            <div>
              <p className="text-sm text-muted-foreground mb-3">
                {selectedCount} workflow(s) selected for promotion
              </p>
            </div>

            {/* Gate Results */}
            {initiateResponse?.gate_results && (
              (initiateResponse.gate_results.errors?.length > 0 ||
               initiateResponse.gate_results.warnings?.length > 0) && (
                <div>
                  <h4 className="font-semibold mb-2">Pre-flight Validation</h4>
                  <div className="space-y-2">
                    {initiateResponse.gate_results.warnings?.map((warning: string, i: number) => (
                      <Alert key={i}>
                        <AlertTriangle className="h-4 w-4" />
                        <AlertDescription>{warning}</AlertDescription>
                      </Alert>
                    ))}
                    {initiateResponse.gate_results.errors?.map((error: string, i: number) => (
                      <Alert key={i} variant="destructive">
                        <XCircle className="h-4 w-4" />
                        <AlertDescription>{error}</AlertDescription>
                      </Alert>
                    ))}
                  </div>
                </div>
              )
            )}

            {/* Approval Notice */}
            {initiateResponse?.requires_approval && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  This promotion requires approval before it can be executed.
                </AlertDescription>
              </Alert>
            )}

            {/* Schedule Check */}
            {activeStage?.schedule?.restrictPromotionTimes && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Promotions are restricted to: {activeStage.schedule.allowedDays?.join(', ')}
                  between {activeStage.schedule.startTime} and {activeStage.schedule.endTime}
                </AlertDescription>
              </Alert>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowReviewDialog(false);
              setInitiateResponse(null);
              setDeploymentId(null);
            }}>
              {initiateResponse?.gate_results?.errors?.length > 0 ? 'Close' : 'Cancel'}
            </Button>
            {deploymentId && initiateResponse?.gate_results?.errors?.length === 0 && (
              <Button
                onClick={() => {
                  const scheduledAt = executionMode === 'schedule' && scheduledDateTime
                    ? new Date(scheduledDateTime).toISOString()
                    : undefined;

                  if (executionMode === 'schedule' && !scheduledDateTime) {
                    toast.error('Please select a date and time for scheduling');
                    return;
                  }

                  setShowReviewDialog(false);
                  executeMutation.mutate({ id: deploymentId, scheduledAt });
                }}
                disabled={executeMutation.isPending || (initiateResponse?.requires_approval && executionMode === 'now')}
              >
                {executeMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    {executionMode === 'schedule' ? 'Scheduling...' : 'Starting...'}
                  </>
                ) : initiateResponse?.requires_approval && executionMode === 'now' ? (
                  'Requires Approval'
                ) : (
                  executionMode === 'schedule' ? 'Schedule Promotion' : 'Execute Promotion'
                )}
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
        onMapCredential={handleMapCredential}
        isLoading={initiateMutation.isPending}
        targetEnvironmentName={targetEnv?.name}
      />

      {/* Inline Mapping Dialog */}
      <InlineMappingDialog
        open={showMappingDialog}
        onOpenChange={setShowMappingDialog}
        issue={selectedIssue}
        targetEnvironmentId={targetEnvId || ''}
        targetEnvironmentName={targetEnv?.name || 'Target'}
        onMappingCreated={handleMappingCreated}
      />

      {/* Workflow Diff Dialog */}
      {selectedWorkflowForDiff && (
        <WorkflowDiffDialog
          open={showDiffDialog}
          onOpenChange={setShowDiffDialog}
          workflowId={selectedWorkflowForDiff.workflowId}
          workflowName={selectedWorkflowForDiff.name}
          sourceEnvironmentId={sourceEnvId || ''}
          targetEnvironmentId={targetEnvId || ''}
          sourceEnvironmentName={sourceEnv?.name}
          targetEnvironmentName={targetEnv?.name}
        />
      )}
    </div>
  );
}
