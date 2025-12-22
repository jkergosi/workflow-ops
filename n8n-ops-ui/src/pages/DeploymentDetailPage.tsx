// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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
import { useAuth } from '@/lib/auth';
import { ArrowLeft, ArrowRight, Clock, CheckCircle, AlertCircle, XCircle, Loader2, Rocket, Trash2, User, RotateCcw } from 'lucide-react';
import { useState, useEffect } from 'react';
import type { DeploymentWorkflow } from '@/types';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';

export function DeploymentDetailPage() {
  useEffect(() => {
    document.title = 'Deployment Details - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [rerunDialogOpen, setRerunDialogOpen] = useState(false);
  const [errorSheetOpen, setErrorSheetOpen] = useState(false);
  const [selectedWorkflow, setSelectedWorkflow] = useState<DeploymentWorkflow | null>(null);

  const { data: deploymentData, isLoading, error } = useQuery({
    queryKey: ['deployment', id],
    queryFn: () => apiClient.getDeployment(id!),
    enabled: !!id,
    // SSE handles real-time updates, so we can use longer stale time
    staleTime: 30000, // 30 seconds
    // Only refetch on window focus as a fallback
    refetchOnWindowFocus: true,
  });

  // Use SSE for real-time updates (replaces polling)
  const { isConnected: sseConnected } = useDeploymentsSSE({
    enabled: !isLoading && !!id,
    deploymentId: id,
  });

  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const { data: pipelines } = useQuery({
    queryKey: ['pipelines'],
    queryFn: () => apiClient.getPipelines(),
  });

  const deployment = deploymentData?.data;

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'success':
        return 'success';
      case 'failed':
        return 'destructive';
      case 'running':
        return 'secondary';
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
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'running':
        return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
      case 'pending':
        return <Clock className="h-5 w-5 text-amber-500" />;
      default:
        return <AlertCircle className="h-5 w-5 text-gray-500" />;
    }
  };

  const getEnvironmentName = (envId: string) => {
    return environments?.data?.find((e) => e.id === envId)?.name || envId;
  };

  const getPipelineName = (pipelineId?: string) => {
    if (!pipelineId) return 'N/A';
    return pipelines?.data?.find((p) => p.id === pipelineId)?.name || pipelineId;
  };

  const getProgress = () => {
    if (!deployment) return { current: 0, total: 0 };
    const total = deployment.progressTotal ?? deployment.summaryJson?.total ?? 0;
    const processed = deployment.progressCurrent ?? deployment.summaryJson?.processed ?? 0;
    const current =
      deployment.status === 'running' && total ? Math.min(processed + 1, total) : processed || total;
    return { current, total };
  };

  const formatDuration = (startedAt: string, finishedAt?: string) => {
    if (!finishedAt) return 'In progress...';
    const start = new Date(startedAt).getTime();
    const end = new Date(finishedAt).getTime();
    const seconds = Math.round((end - start) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const deleteMutation = useMutation({
    mutationFn: (deploymentId: string) => apiClient.deleteDeployment(deploymentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deployments'] });
      toast.success('Deployment deleted successfully');
      setDeleteDialogOpen(false);
      navigate('/deployments');
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
      navigate(`/deployments/${data.data.deploymentId}`);
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to rerun deployment');
    },
  });

  const canDeleteDeployment = () => {
    if (!deployment) return false;
    return deployment.status !== 'running';
  };

  const canRerunDeployment = () => {
    if (!deployment) return false;
    return ['failed', 'canceled', 'success'].includes(deployment.status);
  };

  const handleDeleteClick = () => {
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = () => {
    if (deployment) {
      deleteMutation.mutate(deployment.id);
    }
  };

  const handleRerunClick = () => {
    setRerunDialogOpen(true);
  };

  const handleConfirmRerun = () => {
    if (deployment) {
      rerunMutation.mutate(deployment.id);
    }
  };

  // Helper to display a friendly name for triggered by user
  const getTriggeredByDisplay = (userId?: string) => {
    if (!userId) return 'System';
    
    // Default mock UUID - show current user or "You"
    if (userId === '00000000-0000-0000-0000-000000000000') {
      return user?.name || user?.email || 'You';
    }
    
    // If it looks like an email, display it directly
    if (userId.includes('@')) {
      return userId;
    }
    
    // If it's the current user's ID, show their name
    if (user?.id === userId) {
      return user.name || user.email || 'You';
    }
    
    // Otherwise show a shortened UUID
    return userId.length > 8 ? `${userId.substring(0, 8)}...` : userId;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !deployment) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate('/deployments')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Deployments
        </Button>
        <div className="text-center py-8 text-muted-foreground">
          <AlertCircle className="h-12 w-12 mx-auto mb-4 opacity-20" />
          <p>Deployment not found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/deployments')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <Rocket className="h-6 w-6" />
              Deployment Details
            </h1>
            <p className="text-muted-foreground text-sm">
              ID: {deployment.id}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {getStatusIcon(deployment.status)}
          <Badge variant={getStatusVariant(deployment.status)} className="text-base px-3 py-1">
            {deployment.status}
          </Badge>
          {canRerunDeployment() && (
            <Button
              variant="default"
              onClick={handleRerunClick}
              disabled={rerunMutation.isPending}
            >
              <RotateCcw className="h-4 w-4 mr-2" />
              {rerunMutation.isPending ? 'Starting...' : 'Rerun'}
            </Button>
          )}
          {canDeleteDeployment() && (
            <Button
              variant="destructive"
              onClick={handleDeleteClick}
              disabled={deleteMutation.isPending}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-6 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">{getPipelineName(deployment.pipelineId)}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Stage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{getEnvironmentName(deployment.sourceEnvironmentId)}</Badge>
              <ArrowRight className="h-3 w-3" />
              <Badge variant="outline">{getEnvironmentName(deployment.targetEnvironmentId)}</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Started</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">{new Date(deployment.startedAt).toLocaleString()}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Duration</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">
              {formatDuration(deployment.startedAt, deployment.finishedAt)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Progress Section - Show when running */}
      {deployment.status === 'running' && (
        <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-950/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              Deployment in Progress
              {sseConnected && (
                <span className="text-xs text-green-500 font-normal ml-2">&#8226; Live</span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {(() => {
              const { current, total } = getProgress();
              return (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    Workflows are being transferred to the target environment. This page updates in real-time.
                  </p>
                  <p className="text-sm font-medium">
                    Progress: {current} of {total || '—'}
                    {deployment.currentWorkflowName ? ` (working on ${deployment.currentWorkflowName})` : ''}
                  </p>
                </div>
              );
            })()}
          </CardContent>
        </Card>
      )}

      {/* Summary Section */}
      {deployment.summaryJson && (
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">Deployment Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="flex flex-col items-center justify-center p-5 border rounded-md bg-background hover:bg-muted/50 transition-colors">
                <p className="text-3xl font-bold mb-2 text-foreground">{deployment.summaryJson.total}</p>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Total Workflows</p>
              </div>
              <div className="flex flex-col items-center justify-center p-5 border rounded-md bg-background border-green-500/30 dark:border-green-500/20 hover:bg-green-500/5 dark:hover:bg-green-500/10 transition-colors">
                <p className="text-3xl font-bold mb-2 text-green-700 dark:text-green-400">{deployment.summaryJson.created}</p>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Created</p>
              </div>
              <div className="flex flex-col items-center justify-center p-5 border rounded-md bg-background border-blue-500/30 dark:border-blue-500/20 hover:bg-blue-500/5 dark:hover:bg-blue-500/10 transition-colors">
                <p className="text-3xl font-bold mb-2 text-blue-700 dark:text-blue-400">{deployment.summaryJson.updated}</p>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Updated</p>
              </div>
              <div className="flex flex-col items-center justify-center p-5 border rounded-md bg-background border-amber-500/30 dark:border-amber-500/20 hover:bg-amber-500/5 dark:hover:bg-amber-500/10 transition-colors">
                <p className="text-3xl font-bold mb-2 text-amber-700 dark:text-amber-400">{deployment.summaryJson.skipped || 0}</p>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Skipped</p>
              </div>
              <div className="flex flex-col items-center justify-center p-5 border rounded-md bg-background border-red-500/30 dark:border-red-500/20 hover:bg-red-500/5 dark:hover:bg-red-500/10 transition-colors">
                <p className="text-3xl font-bold mb-2 text-red-700 dark:text-red-400">{deployment.summaryJson.failed}</p>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Failed</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Snapshots Section */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Pre-Deployment Snapshot</CardTitle>
          </CardHeader>
          <CardContent>
            {deployment.preSnapshotId ? (
              <Link
                to={`/snapshots?snapshot=${deployment.preSnapshotId}`}
                className="text-primary hover:underline"
              >
                {deployment.preSnapshotId.substring(0, 8)}...
              </Link>
            ) : (
              <p className="text-sm text-muted-foreground">No snapshot</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Post-Deployment Snapshot</CardTitle>
          </CardHeader>
          <CardContent>
            {deployment.postSnapshotId ? (
              <Link
                to={`/snapshots?snapshot=${deployment.postSnapshotId}`}
                className="text-primary hover:underline"
              >
                {deployment.postSnapshotId.substring(0, 8)}...
              </Link>
            ) : (
              <p className="text-sm text-muted-foreground">No snapshot</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Workflows Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Workflows
            {deployment.status === 'running' && (
              <Badge variant="secondary" className="text-xs">
                {getProgress().current} / {getProgress().total} processed
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {deployment.workflows && deployment.workflows.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8"></TableHead>
                  <TableHead>Workflow Name</TableHead>
                  <TableHead>Change Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deployment.workflows.map((workflow, index) => {
                  // Determine visual status based on deployment progress
                  const isCurrentlyProcessing = 
                    deployment.status === 'running' && 
                    deployment.currentWorkflowName === workflow.workflowNameAtTime;
                  const isPending = 
                    deployment.status === 'running' && 
                    workflow.status === 'pending';
                  const isCompleted = 
                    workflow.status === 'success' || workflow.status === 'failed';
                  
                  return (
                    <TableRow 
                      key={workflow.id}
                      className={isCurrentlyProcessing ? 'bg-blue-50/50 dark:bg-blue-950/30' : ''}
                    >
                      <TableCell className="w-8">
                        {isCurrentlyProcessing ? (
                          <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                        ) : workflow.status === 'success' ? (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        ) : workflow.status === 'failed' ? (
                          <XCircle className="h-4 w-4 text-red-500" />
                        ) : isPending ? (
                          <Clock className="h-4 w-4 text-muted-foreground" />
                        ) : null}
                      </TableCell>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          {workflow.workflowNameAtTime}
                          {isCurrentlyProcessing && (
                            <Badge variant="secondary" className="text-xs">
                              Processing...
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {workflow.changeType}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            workflow.status === 'success'
                              ? 'success'
                              : workflow.status === 'failed'
                              ? 'destructive'
                              : isCurrentlyProcessing
                              ? 'secondary'
                              : 'outline'
                          }
                        >
                          {isCurrentlyProcessing ? 'processing' : workflow.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-xs">
                        {workflow.errorMessage ? (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedWorkflow(workflow);
                              setErrorSheetOpen(true);
                            }}
                            className="text-primary hover:underline truncate block w-full text-left"
                          >
                            {workflow.errorMessage}
                          </button>
                        ) : (
                          '-'
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">
              No workflow details available
            </p>
          )}
        </CardContent>
      </Card>

      {/* Triggered By */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Triggered By</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-muted-foreground" />
            <span>{getTriggeredByDisplay(deployment.triggeredByUserId)}</span>
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Deployment</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this deployment? This action cannot be undone.
              {deployment && (
                <div className="mt-2 space-y-1">
                  <p className="font-medium">Deployment Details:</p>
                  <p className="text-sm">
                    {deployment.summaryJson?.total || 0} workflow(s) deployed from{' '}
                    {getEnvironmentName(deployment.sourceEnvironmentId)} to{' '}
                    {getEnvironmentName(deployment.targetEnvironmentId)}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Started: {new Date(deployment.startedAt).toLocaleString()}
                  </p>
                  {deployment.finishedAt && (
                    <p className="text-sm text-muted-foreground">
                      Finished: {new Date(deployment.finishedAt).toLocaleString()}
                    </p>
                  )}
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
      <AlertDialog open={rerunDialogOpen} onOpenChange={setRerunDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rerun Deployment</AlertDialogTitle>
            <AlertDialogDescription>
              This will create a new deployment using the same pipeline, source/target environments, and workflow selections as the original.
              All gates (drift check, credential preflight, approvals) will be re-run, and fresh pre/post snapshots will be created.
              {deployment && (
                <div className="mt-4 space-y-2">
                  <div className="p-3 bg-muted rounded-md space-y-1">
                    <p className="font-medium text-sm">Deployment Summary:</p>
                    <p className="text-sm">
                      <span className="font-medium">Pipeline:</span> {getPipelineName(deployment.pipelineId)}
                    </p>
                    <p className="text-sm">
                      <span className="font-medium">Stage:</span>{' '}
                      {getEnvironmentName(deployment.sourceEnvironmentId)} →{' '}
                      {getEnvironmentName(deployment.targetEnvironmentId)}
                    </p>
                    <p className="text-sm">
                      <span className="font-medium">Workflows:</span> {deployment.summaryJson?.total || 0} workflow(s)
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

      {/* Error Details Sheet */}
      <Sheet open={errorSheetOpen} onOpenChange={setErrorSheetOpen}>
        <SheetContent side="right" className="sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Error Details</SheetTitle>
            <SheetDescription>
              Full error information for workflow deployment
            </SheetDescription>
          </SheetHeader>
          {selectedWorkflow && (
            <div className="mt-6 space-y-6">
              {/* Workflow Information */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">Workflow Information</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Name:</span>
                    <p className="font-medium">{selectedWorkflow.workflowNameAtTime}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Workflow ID:</span>
                    <p className="font-mono text-xs">{selectedWorkflow.workflowId}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Change Type:</span>
                    <p className="font-medium capitalize">{selectedWorkflow.changeType}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Status:</span>
                    <Badge
                      variant={
                        selectedWorkflow.status === 'success'
                          ? 'success'
                          : selectedWorkflow.status === 'failed'
                          ? 'destructive'
                          : 'outline'
                      }
                      className="ml-2"
                    >
                      {selectedWorkflow.status}
                    </Badge>
                  </div>
                </div>
              </div>

              {/* Error Message */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">Error Message</h3>
                <div className="rounded-lg bg-muted p-4">
                  <pre className="whitespace-pre-wrap break-words text-sm font-mono">
                    {selectedWorkflow.errorMessage || 'No error message available'}
                  </pre>
                </div>
              </div>

              {/* Additional Context */}
              {deployment && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Deployment Context</h3>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Source Environment:</span>
                      <p className="font-medium">{getEnvironmentName(deployment.sourceEnvironmentId)}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Target Environment:</span>
                      <p className="font-medium">{getEnvironmentName(deployment.targetEnvironmentId)}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Deployment ID:</span>
                      <p className="font-mono text-xs">{deployment.id}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Started:</span>
                      <p className="font-medium">{new Date(deployment.startedAt).toLocaleString()}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
