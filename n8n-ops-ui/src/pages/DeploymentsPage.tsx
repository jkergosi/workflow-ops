// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
import { Rocket, ArrowRight, Clock, CheckCircle, AlertCircle, XCircle, Loader2, Trash2 } from 'lucide-react';
import type { Deployment } from '@/types';
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

export function DeploymentsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deploymentToDelete, setDeploymentToDelete] = useState<Deployment | null>(null);

  const { data: deploymentsData, isLoading } = useQuery({
    queryKey: ['deployments'],
    queryFn: () => apiClient.getDeployments(),
    refetchInterval: (query) => {
      // Check if any deployment is running
      const deployments = query.state.data?.data?.deployments || [];
      const hasRunning = deployments.some((d: Deployment) => d.status === 'running');
      return hasRunning ? 2000 : false; // Poll every 2 seconds if any are running
    },
  });

  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const { data: pipelines } = useQuery({
    queryKey: ['pipelines'],
    queryFn: () => apiClient.getPipelines(),
  });

  const deployments = deploymentsData?.data?.deployments || [];
  const summary = deploymentsData?.data || {
    thisWeekSuccessCount: 0,
    pendingApprovalsCount: 0,
  };

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'success':
        return 'default';
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
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'running':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-amber-500" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
  };

  const getEnvironmentName = (envId: string) => {
    return environments?.data?.find((e) => e.id === envId)?.name || envId;
  };

  const getPipelineName = (pipelineId?: string) => {
    if (!pipelineId) return '—';
    return pipelines?.data?.find((p) => p.id === pipelineId)?.name || pipelineId;
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

  const handleRowClick = (deployment: Deployment) => {
    navigate(`/deployments/${deployment.id}`);
  };

  const handlePromoteWorkflows = () => {
    navigate('/promote');
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Deployments</h1>
          <p className="text-muted-foreground">
            Track workflow deployments across environments
          </p>
        </div>
        <Button onClick={handlePromoteWorkflows}>
          <Rocket className="h-4 w-4 mr-2" />
          New Deployment
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-6 md:grid-cols-3">
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
              One-click promotion between environments
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
                  <TableHead>Workflow(s)</TableHead>
                  <TableHead>Pipeline</TableHead>
                  <TableHead>Stage</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Triggered By</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deployments.map((deployment) => {
                  const workflowCount = deployment.summaryJson?.total || 0;
                  const workflowName = deployment.summaryJson?.total === 1 
                    ? 'Single workflow' // Would need to fetch workflow name
                    : `${workflowCount} workflows`;

                  return (
                    <TableRow
                      key={deployment.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleRowClick(deployment)}
                    >
                      <TableCell className="font-medium">
                        <span className="text-primary hover:underline">
                          {workflowName}
                        </span>
                      </TableCell>
                      <TableCell>{getPipelineName(deployment.pipelineId)}</TableCell>
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
                        <div className="flex items-center gap-2">
                          {getStatusIcon(deployment.status)}
                          <Badge variant={getStatusVariant(deployment.status)}>
                            {deployment.status}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {deployment.triggeredByUserId}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(deployment.startedAt).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDuration(deployment.startedAt, deployment.finishedAt)}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteClick(e, deployment);
                          }}
                          disabled={deployment.status === 'running'}
                          className="h-8 w-8"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
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
    </div>
  );
}
