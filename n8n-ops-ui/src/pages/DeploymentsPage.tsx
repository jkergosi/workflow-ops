// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { apiClient } from '@/lib/api-client';
import { useDeploymentsSSE } from '@/lib/use-deployments-sse';
import { useFeatures } from '@/lib/features';
import { SmartEmptyState } from '@/components/SmartEmptyState';
import { Rocket, ArrowRight, Clock, CheckCircle, AlertCircle, XCircle, Loader2, Trash2, Radio, RotateCcw, GitBranch, Plus, Edit, Copy, PlayCircle, PauseCircle } from 'lucide-react';
import type { Deployment, Pipeline } from '@/types';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

export function DeploymentsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deploymentToDelete, setDeploymentToDelete] = useState<Deployment | null>(null);
  const [rerunDialogOpen, setRerunDialogOpen] = useState(false);
  const [deploymentToRerun, setDeploymentToRerun] = useState<Deployment | null>(null);
  const [deletePipelineDialogOpen, setDeletePipelineDialogOpen] = useState(false);
  const [pipelineToDelete, setPipelineToDelete] = useState<Pipeline | null>(null);
  const [showInactivePipelines, setShowInactivePipelines] = useState(true);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [deploymentToCancel, setDeploymentToCancel] = useState<Deployment | null>(null);
  
  const activeTab = searchParams.get('tab') || 'deployments';
  
  // Get plan for terminology suppression (Pipeline: ❌ Free, ⚠️ Pro, ✅ Agency+)
  const { planName } = useFeatures();
  const planLower = planName?.toLowerCase() || 'free';
  const canSeePipelines = planLower !== 'free'; // Free cannot see, Pro+ can see
  
  // Redirect free users away from pipelines tab
  useEffect(() => {
    if (activeTab === 'pipelines' && !canSeePipelines) {
      setSearchParams({ tab: 'deployments' }, { replace: true });
    }
  }, [activeTab, canSeePipelines, setSearchParams]);

  // Force refetch when navigating to this page (e.g., after creating a deployment)
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['deployments'] });
  }, [location.key, queryClient]);

  useEffect(() => {
    document.title = 'Deployments - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const { data: deploymentsData, isLoading, error, refetch } = useQuery({
    queryKey: ['deployments'],
    queryFn: () => apiClient.getDeployments(),
    // SSE handles real-time updates, so we can use longer stale time
    staleTime: 30000, // 30 seconds
    // Only refetch on window focus as a fallback
    refetchOnWindowFocus: true,
    retry: (failureCount, error) => {
      // Don't retry on 503 - service is down
      if ((error as any)?.response?.status === 503) return false;
      return failureCount < 2;
    },
    keepPreviousData: true, // Cached data fallback
  });

  // Use SSE for real-time updates (replaces polling)
  const { isConnected: sseConnected } = useDeploymentsSSE({ enabled: !isLoading });

  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const { data: pipelines, isLoading: pipelinesLoading } = useQuery({
    queryKey: ['pipelines', showInactivePipelines],
    queryFn: () => apiClient.getPipelines({ includeInactive: showInactivePipelines }),
    // Fetch pipelines for both tabs: deployments needs names, pipelines tab needs full data
  });

  const deployments = deploymentsData?.data?.deployments || [];
  const summary = deploymentsData?.data || {
    thisWeekSuccessCount: 0,
    pendingApprovalsCount: 0,
    runningCount: 0,
  };

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'success':
        return 'success';
      case 'failed':
        return 'destructive';
      case 'running':
        return 'secondary';
      case 'scheduled':
        return 'default';
      case 'pending':
        return 'outline';
      case 'canceled':
        return 'outline';
      default:
        return 'outline';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'running':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case 'scheduled':
        return <Clock className="h-4 w-4 text-blue-500" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-amber-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  const formatScheduledTime = (scheduledAt: string) => {
    const scheduled = new Date(scheduledAt);
    const now = new Date();
    const diffMs = scheduled.getTime() - now.getTime();
    
    if (diffMs < 0) {
      return 'Overdue';
    }
    
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffDays > 0) {
      return `In ${diffDays} day${diffDays !== 1 ? 's' : ''}`;
    } else if (diffHours > 0) {
      return `In ${diffHours} hour${diffHours !== 1 ? 's' : ''}`;
    } else if (diffMins > 0) {
      return `In ${diffMins} minute${diffMins !== 1 ? 's' : ''}`;
    } else {
      return 'Starting soon';
    }
  };

  const getEnvironmentName = (envId: string) => {
    return environments?.data?.find((e) => e.id === envId)?.name || envId;
  };

  const getPipelineName = (pipelineId?: string) => {
    if (!pipelineId) return '—';
    return pipelines?.data?.find((p) => p.id === pipelineId)?.name || pipelineId;
  };

  const getProgress = (deployment: Deployment) => {
    // Use backend-calculated progress fields if available
    // For completed deployments, backend calculates successful (created + updated)
    // For running deployments, backend calculates processed count
    const total = deployment.progressTotal ?? deployment.summaryJson?.total ?? 0;
    let current = deployment.progressCurrent;
    
    // Fallback to calculating from summary_json if backend fields not available
    if (current === undefined) {
      const summary = deployment.summaryJson || {};
      if (deployment.status === 'success' || deployment.status === 'failed') {
        // For completed: successful = created + updated
        current = (summary.created || 0) + (summary.updated || 0);
      } else if (deployment.status === 'running') {
        // For running: use processed count
        current = summary.processed || 0;
        if (total) {
          current = Math.min(current + 1, total);
        }
      } else {
        current = 0;
      }
    }
    
    return { current, total };
  };

  const formatDuration = (startedAt: string, finishedAt?: string) => {
    const start = new Date(startedAt).getTime();
    const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
    const seconds = Math.round((end - start) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const handlePromoteWorkflows = () => {
    navigate('/deployments/new');
  };

  const deleteMutation = useMutation({
    mutationFn: (deploymentId: string) => apiClient.deleteDeployment(deploymentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deployments'] });
      toast.success('Deployment deleted successfully');
      setDeleteDialogOpen(false);
      setDeploymentToDelete(null);
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to delete deployment');
    },
  });

  const rerunMutation = useMutation({
    mutationFn: (deploymentId: string) => apiClient.rerunDeployment(deploymentId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['deployments'] });
      toast.success(data.data.message || 'Deployment rerun started successfully');
      setRerunDialogOpen(false);
      setDeploymentToRerun(null);
      navigate(`/deployments/${data.data.deploymentId}`);
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to rerun deployment');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (deploymentId: string) => apiClient.cancelScheduledDeployment(deploymentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deployments'] });
      toast.success('Scheduled deployment cancelled successfully');
      setCancelDialogOpen(false);
      setDeploymentToCancel(null);
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to cancel scheduled deployment');
    },
  });

  const handleDeleteClick = (e: React.MouseEvent, deployment: Deployment) => {
    e.stopPropagation();
    setDeploymentToDelete(deployment);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = () => {
    if (deploymentToDelete) {
      deleteMutation.mutate(deploymentToDelete.id);
    }
  };

  const handleRerunClick = (e: React.MouseEvent, deployment: Deployment) => {
    e.stopPropagation();
    setDeploymentToRerun(deployment);
    setRerunDialogOpen(true);
  };

  const handleConfirmRerun = () => {
    if (deploymentToRerun) {
      rerunMutation.mutate(deploymentToRerun.id);
    }
  };

  const handleCancelClick = (e: React.MouseEvent, deployment: Deployment) => {
    e.stopPropagation();
    setDeploymentToCancel(deployment);
    setCancelDialogOpen(true);
  };

  const handleConfirmCancel = () => {
    if (deploymentToCancel) {
      cancelMutation.mutate(deploymentToCancel.id);
    }
  };

  const canRerunDeployment = (deployment: Deployment) => {
    return ['failed', 'canceled', 'success'].includes(deployment.status);
  };

  const deletePipelineMutation = useMutation({
    mutationFn: (id: string) => apiClient.deletePipeline(id),
    onSuccess: () => {
      toast.success('Pipeline deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
      setDeletePipelineDialogOpen(false);
      setPipelineToDelete(null);
    },
    onError: () => {
      toast.error('Failed to delete pipeline');
    },
  });

  const togglePipelineActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      apiClient.updatePipeline(id, { isActive }),
    onSuccess: (_, variables) => {
      toast.success(`Pipeline ${variables.isActive ? 'activated' : 'deactivated'} successfully`);
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
    },
    onError: () => {
      toast.error('Failed to update pipeline status');
    },
  });

  const duplicatePipelineMutation = useMutation({
    mutationFn: (pipeline: Pipeline) =>
      apiClient.createPipeline({
        name: `${pipeline.name} (Copy)`,
        description: pipeline.description,
        isActive: false,
        environmentIds: pipeline.environmentIds,
        stages: pipeline.stages,
      }),
    onSuccess: () => {
      toast.success('Pipeline duplicated successfully');
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
    },
    onError: () => {
      toast.error('Failed to duplicate pipeline');
    },
  });

  const getEnvironmentPath = (pipeline: Pipeline): string => {
    if (!environments?.data || !pipeline.environmentIds || pipeline.environmentIds.length === 0) return 'N/A';
    const envNames = pipeline.environmentIds
      .map((id) => {
        const env = environments.data.find((e) => e.id === id);
        return env?.name || id;
      })
      .join(' → ');
    return envNames;
  };

  const handleDeletePipelineClick = (pipeline: Pipeline) => {
    setPipelineToDelete(pipeline);
    setDeletePipelineDialogOpen(true);
  };

  const handleDeletePipelineConfirm = () => {
    if (pipelineToDelete) {
      deletePipelineMutation.mutate(pipelineToDelete.id);
    }
  };

  const handleTabChange = (value: string) => {
    setSearchParams({ tab: value });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Deployments</h1>
          <p className="text-muted-foreground">
            {canSeePipelines 
              ? 'Track workflow deployments and manage pipelines'
              : 'Track workflow deployments'}
          </p>
        </div>
        {activeTab === 'deployments' && (
          <Button onClick={handlePromoteWorkflows}>
            <Rocket className="h-4 w-4 mr-2" />
            New Deployment
          </Button>
        )}
        {activeTab === 'pipelines' && canSeePipelines && (
          <Button onClick={() => navigate('/pipelines/new')}>
            <Plus className="h-4 w-4 mr-2" />
            Create Pipeline
          </Button>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
        <TabsList>
          <TabsTrigger value="deployments" className="flex items-center gap-2">
            <Rocket className="h-4 w-4" />
            Deployments
          </TabsTrigger>
          {canSeePipelines && (
            <TabsTrigger value="pipelines" className="flex items-center gap-2">
              <GitBranch className="h-4 w-4" />
              Pipelines
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="deployments" className="space-y-6">

      {/* Summary Cards */}
      <div className="grid gap-6 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Running Now</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {summary.runningCount > 0 ? (
                <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
              ) : (
                <Radio className="h-5 w-5 text-muted-foreground" />
              )}
              <span className="text-2xl font-bold">{summary.runningCount || 0}</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Active deployments
              {sseConnected && <span className="ml-1 text-green-500">&#8226; Live</span>}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">This Week</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <span className="text-2xl font-bold">{summary.thisWeekSuccessCount}</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Successful deployments
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Pending Approvals</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-amber-500" />
              <span className="text-2xl font-bold">{summary.pendingApprovalsCount}</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Workflows awaiting approval
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Promotion Mode</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Rocket className="h-5 w-5 text-blue-500" />
              <span className="text-lg font-semibold">Manual</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              One-click promotion
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Deployment History Table */}
      <Card>
        <CardHeader>
          <CardTitle>Deployment History</CardTitle>
          <CardDescription>Recent workflow deployments and promotions</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading deployments...</div>
          ) : deployments.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Rocket className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>No deployments yet</p>
              <Button variant="link" onClick={handlePromoteWorkflows} className="mt-2">
                Create your first deployment
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Pipeline</TableHead>
                  <TableHead>Stage</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deployments.map((deployment) => {
                  const { current: progressCurrent, total: progressTotal } = getProgress(deployment);
                  const progressText = progressTotal > 0 ? `${progressCurrent} of ${progressTotal}` : null;

                  return (
                    <TableRow key={deployment.id}>
                      <TableCell>
                        <Link
                          to={`/deployments/${deployment.id}`}
                          className="text-primary hover:underline"
                        >
                          {getPipelineName(deployment.pipelineId)}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">
                            {getEnvironmentName(deployment.sourceEnvironmentId)}
                          </Badge>
                          <ArrowRight className="h-3 w-3" />
                          <Badge variant="outline">
                            {getEnvironmentName(deployment.targetEnvironmentId)}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col items-center gap-1">
                          <Badge variant={getStatusVariant(deployment.status)} className="flex items-center gap-1">
                            {getStatusIcon(deployment.status)}
                            {deployment.status}
                          </Badge>
                          {deployment.status === 'scheduled' && (deployment as any).scheduledAt && (
                            <span className="text-xs text-muted-foreground">
                              {formatScheduledTime((deployment as any).scheduledAt)}
                            </span>
                          )}
                          {progressText && deployment.status !== 'scheduled' && (
                            <span className="text-xs text-muted-foreground">
                              {progressText}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {deployment.status === 'scheduled' && deployment.scheduledAt ? (
                          <div className="flex flex-col">
                            <span>{new Date(deployment.scheduledAt).toLocaleString()}</span>
                            <span className="text-xs">{formatScheduledTime(deployment.scheduledAt)}</span>
                          </div>
                        ) : (
                          deployment.startedAt ? new Date(deployment.startedAt).toLocaleString() : '—'
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {deployment.status === 'scheduled' ? '—' : formatDuration(deployment.startedAt, deployment.finishedAt)}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {deployment.status === 'scheduled' && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={(e) => handleCancelClick(e, deployment)}
                              disabled={cancelMutation.isPending}
                              className="h-8 w-8"
                              title="Cancel scheduled deployment"
                            >
                              <XCircle className="h-4 w-4" />
                            </Button>
                          )}
                          {canRerunDeployment(deployment) && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={(e) => handleRerunClick(e, deployment)}
                              disabled={rerunMutation.isPending}
                              className="h-8 w-8"
                              title="Rerun deployment"
                            >
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            onClick={(e) => handleDeleteClick(e, deployment)}
                            disabled={deployment.status === 'running' || deployment.status === 'scheduled'}
                            className="h-8 w-8"
                            title="Delete deployment"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Deployment</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this deployment? This action cannot be undone.
              {deploymentToDelete && (
                <div className="mt-2 space-y-1">
                  <p className="font-medium">Deployment Details:</p>
                  <p className="text-sm">
                    {deploymentToDelete.summaryJson?.total || 0} workflow(s) deployed from{' '}
                    {getEnvironmentName(deploymentToDelete.sourceEnvironmentId)} to{' '}
                    {getEnvironmentName(deploymentToDelete.targetEnvironmentId)}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Started: {new Date(deploymentToDelete.startedAt).toLocaleString()}
                  </p>
                </div>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              disabled={deleteMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Rerun Confirmation Dialog */}
      <AlertDialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Scheduled Deployment</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to cancel this scheduled deployment? This action cannot be undone.
              {deploymentToCancel && deploymentToCancel.scheduledAt && (
                <div className="mt-2 p-2 bg-muted rounded text-sm">
                  Scheduled for: {new Date(deploymentToCancel.scheduledAt).toLocaleString()}
                </div>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Scheduled</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmCancel}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {cancelMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Cancelling...
                </>
              ) : (
                'Cancel Deployment'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={rerunDialogOpen} onOpenChange={setRerunDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rerun Deployment</AlertDialogTitle>
            <AlertDialogDescription>
              This will create a new deployment using the same pipeline, source/target environments, and workflow selections as the original.
              All gates (drift check, credential preflight, approvals) will be re-run, and fresh pre/post snapshots will be created.
              {deploymentToRerun && (
                <div className="mt-4 space-y-2">
                  <div className="p-3 bg-muted rounded-md space-y-1">
                    <p className="font-medium text-sm">Deployment Summary:</p>
                    <p className="text-sm">
                      <span className="font-medium">Pipeline:</span> {getPipelineName(deploymentToRerun.pipelineId)}
                    </p>
                    <p className="text-sm">
                      <span className="font-medium">Stage:</span>{' '}
                      {getEnvironmentName(deploymentToRerun.sourceEnvironmentId)} →{' '}
                      {getEnvironmentName(deploymentToRerun.targetEnvironmentId)}
                    </p>
                    <p className="text-sm">
                      <span className="font-medium">Workflows:</span> {deploymentToRerun.summaryJson?.total || 0} workflow(s)
                    </p>
                  </div>
                  <div className="p-3 bg-blue-50 dark:bg-blue-950/30 rounded-md">
                    <p className="text-sm font-medium text-blue-900 dark:text-blue-100">Gates that will run:</p>
                    <ul className="text-sm text-blue-800 dark:text-blue-200 mt-1 list-disc list-inside space-y-0.5">
                      <li>Drift check</li>
                      <li>Credential preflight validation</li>
                      <li>Approvals (if required)</li>
                    </ul>
                  </div>
                </div>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmRerun}
              disabled={rerunMutation.isPending}
            >
              {rerunMutation.isPending ? 'Starting...' : 'Rerun Deployment'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
        </TabsContent>

        <TabsContent value="pipelines" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Deployment Pipelines</CardTitle>
                  <CardDescription>
                    Manage pipelines that define how workflows are deployed between environments
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="show-inactive"
                    checked={showInactivePipelines}
                    onCheckedChange={(checked) => setShowInactivePipelines(checked === true)}
                  />
                  <Label
                    htmlFor="show-inactive"
                    className="text-sm font-normal cursor-pointer text-muted-foreground"
                  >
                    Show inactive pipelines
                  </Label>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {pipelinesLoading ? (
                <div className="text-center py-8">Loading pipelines...</div>
              ) : !pipelines?.data || pipelines.data.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <p className="mb-4">No pipelines found</p>
                  <Button onClick={() => navigate('/pipelines/new')}>
                    <Plus className="h-4 w-4 mr-2" />
                    Create Your First Pipeline
                  </Button>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Pipeline Name</TableHead>
                      <TableHead>Environment Path</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last Modified</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pipelines.data.map((pipeline) => (
                      <TableRow 
                        key={pipeline.id}
                        className={!pipeline.isActive ? 'opacity-60' : ''}
                      >
                        <TableCell className="font-medium">
                          <Link
                            to={`/pipelines/${pipeline.id}`}
                            className={`${!pipeline.isActive ? 'text-muted-foreground' : 'text-primary'} hover:underline`}
                          >
                            {pipeline.name}
                          </Link>
                          {pipeline.description && (
                            <p className="text-sm text-muted-foreground mt-1">
                              {pipeline.description}
                            </p>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2 text-sm">
                            {getEnvironmentPath(pipeline)}
                          </div>
                        </TableCell>
                        <TableCell>
                          {pipeline.isActive ? (
                            <Badge variant="success" className="flex items-center gap-1 w-fit">
                              <PlayCircle className="h-3 w-3" />
                              Active
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="flex items-center gap-1 w-fit">
                              <PauseCircle className="h-3 w-3" />
                              Inactive
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(pipeline.lastModifiedAt || pipeline.updatedAt).toLocaleDateString()}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => navigate(`/pipelines/${pipeline.id}`)}
                              title="Edit pipeline"
                            >
                              <Edit className="h-3 w-3 mr-1" />
                              Edit
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => duplicatePipelineMutation.mutate(pipeline)}
                              title="Duplicate pipeline"
                              disabled={duplicatePipelineMutation.isPending}
                            >
                              <Copy className="h-3 w-3 mr-1" />
                              Duplicate
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => togglePipelineActiveMutation.mutate({ id: pipeline.id, isActive: !pipeline.isActive })}
                              title={pipeline.isActive ? 'Deactivate' : 'Activate'}
                              disabled={togglePipelineActiveMutation.isPending}
                            >
                              {pipeline.isActive ? (
                                <>
                                  <PauseCircle className="h-3 w-3 mr-1" />
                                  Deactivate
                                </>
                              ) : (
                                <>
                                  <PlayCircle className="h-3 w-3 mr-1" />
                                  Activate
                                </>
                              )}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleDeletePipelineClick(pipeline)}
                              title="Delete pipeline"
                            >
                              <Trash2 className="h-3 w-3 mr-1" />
                              Delete
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Delete Pipeline Confirmation Dialog */}
          <Dialog open={deletePipelineDialogOpen} onOpenChange={setDeletePipelineDialogOpen}>
            <DialogContent className="max-w-md">
              <DialogHeader>
                <DialogTitle>Delete Pipeline</DialogTitle>
                <DialogDescription>
                  Are you sure you want to delete "{pipelineToDelete?.name}"? This action cannot be undone.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => setDeletePipelineDialogOpen(false)}>
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleDeletePipelineConfirm}
                  disabled={deletePipelineMutation.isPending}
                >
                  {deletePipelineMutation.isPending ? 'Deleting...' : 'Yes, Delete'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>
      </Tabs>
    </div>
  );
}
