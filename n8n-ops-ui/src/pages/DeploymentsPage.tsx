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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { apiClient } from '@/lib/api-client';
import { Rocket, ArrowRight, Clock, CheckCircle, AlertCircle, XCircle, Loader2 } from 'lucide-react';
import type { Deployment, DeploymentDetail } from '@/types';
import { Link } from 'react-router-dom';

export function DeploymentsPage() {
  const navigate = useNavigate();
  const [selectedDeployment, setSelectedDeployment] = useState<DeploymentDetail | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);

  const { data: deploymentsData, isLoading } = useQuery({
    queryKey: ['deployments'],
    queryFn: () => apiClient.getDeployments(),
  });

  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const { data: pipelines } = useQuery({
    queryKey: ['pipelines'],
    queryFn: () => apiClient.getPipelines(),
  });

  // Fetch deployment detail when selected
  const { data: deploymentDetail } = useQuery({
    queryKey: ['deployment', selectedDeployment?.id],
    queryFn: () => apiClient.getDeployment(selectedDeployment!.id),
    enabled: !!selectedDeployment,
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
    if (!finishedAt) return '—';
    const start = new Date(startedAt).getTime();
    const end = new Date(finishedAt).getTime();
    const seconds = Math.round((end - start) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const handleRowClick = async (deployment: Deployment) => {
    const detail = await apiClient.getDeployment(deployment.id);
    setSelectedDeployment(detail.data);
    setDetailDialogOpen(true);
  };

  const handlePromoteWorkflows = () => {
    navigate('/promote');
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
                        {workflowCount === 1 ? (
                          workflowName
                        ) : (
                          <Link
                            to="#"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRowClick(deployment);
                            }}
                            className="text-primary hover:underline"
                          >
                            {workflowName}
                          </Link>
                        )}
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
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Deployment Detail Dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Deployment Details</DialogTitle>
            <DialogDescription>
              View detailed information about this deployment
            </DialogDescription>
          </DialogHeader>

          {deploymentDetail?.data && (
            <div className="space-y-6">
              {/* Top Section */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Pipeline</p>
                  <p className="text-base">{getPipelineName(deploymentDetail.data.pipelineId)}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Stage</p>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">
                      {getEnvironmentName(deploymentDetail.data.sourceEnvironmentId)}
                    </Badge>
                    <ArrowRight className="h-3 w-3" />
                    <Badge variant="outline">
                      {getEnvironmentName(deploymentDetail.data.targetEnvironmentId)}
                    </Badge>
                  </div>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Status</p>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(deploymentDetail.data.status)}
                    <Badge variant={getStatusVariant(deploymentDetail.data.status)}>
                      {deploymentDetail.data.status}
                    </Badge>
                  </div>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Triggered By</p>
                  <p className="text-base">{deploymentDetail.data.triggeredByUserId}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Started</p>
                  <p className="text-base">
                    {new Date(deploymentDetail.data.startedAt).toLocaleString()}
                  </p>
                </div>
                {deploymentDetail.data.finishedAt && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Finished</p>
                    <p className="text-base">
                      {new Date(deploymentDetail.data.finishedAt).toLocaleString()}
                    </p>
                  </div>
                )}
              </div>

              {/* Middle Section - Snapshots */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-2">Pre Snapshot</p>
                  {deploymentDetail.data.preSnapshotId ? (
                    <Link
                      to={`/snapshots?snapshot=${deploymentDetail.data.preSnapshotId}`}
                      className="text-primary hover:underline"
                    >
                      {deploymentDetail.data.preSnapshotId.substring(0, 8)}...
                    </Link>
                  ) : (
                    <p className="text-sm text-muted-foreground">—</p>
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-2">Post Snapshot</p>
                  {deploymentDetail.data.postSnapshotId ? (
                    <Link
                      to={`/snapshots?snapshot=${deploymentDetail.data.postSnapshotId}`}
                      className="text-primary hover:underline"
                    >
                      {deploymentDetail.data.postSnapshotId.substring(0, 8)}...
                    </Link>
                  ) : (
                    <p className="text-sm text-muted-foreground">—</p>
                  )}
                </div>
              </div>

              {/* Workflows Table */}
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-2">Workflows</p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Workflow Name</TableHead>
                      <TableHead>Change Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Error</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {deploymentDetail.data.workflows.map((workflow) => (
                      <TableRow key={workflow.id}>
                        <TableCell className="font-medium">
                          {workflow.workflowNameAtTime}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{workflow.changeType}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              workflow.status === 'success'
                                ? 'default'
                                : workflow.status === 'failed'
                                ? 'destructive'
                                : 'outline'
                            }
                          >
                            {workflow.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {workflow.errorMessage || '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
