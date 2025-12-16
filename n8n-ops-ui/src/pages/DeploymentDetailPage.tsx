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
import { ArrowLeft, ArrowRight, Clock, CheckCircle, AlertCircle, XCircle, Loader2, Rocket } from 'lucide-react';

export function DeploymentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: deploymentData, isLoading, error } = useQuery({
    queryKey: ['deployment', id],
    queryFn: () => apiClient.getDeployment(id!),
    enabled: !!id,
    refetchInterval: (data) => {
      // Keep refetching if deployment is still running
      if (data?.data?.status === 'running') {
        return 2000; // Refetch every 2 seconds while running
      }
      return false;
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

  const deployment = deploymentData?.data;

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
        <Card className="border-blue-200 bg-blue-50/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              Deployment in Progress
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Workflows are being transferred to the target environment. This page will automatically update when complete.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Summary Section */}
      {deployment.summaryJson && (
        <Card>
          <CardHeader>
            <CardTitle>Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center p-4 bg-muted rounded-lg">
                <p className="text-2xl font-bold">{deployment.summaryJson.total}</p>
                <p className="text-sm text-muted-foreground">Total</p>
              </div>
              <div className="text-center p-4 bg-green-50 rounded-lg">
                <p className="text-2xl font-bold text-green-600">{deployment.summaryJson.created}</p>
                <p className="text-sm text-muted-foreground">Created</p>
              </div>
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <p className="text-2xl font-bold text-blue-600">{deployment.summaryJson.updated}</p>
                <p className="text-sm text-muted-foreground">Updated</p>
              </div>
              <div className="text-center p-4 bg-amber-50 rounded-lg">
                <p className="text-2xl font-bold text-amber-600">{deployment.summaryJson.skipped || 0}</p>
                <p className="text-sm text-muted-foreground">Skipped</p>
              </div>
              <div className="text-center p-4 bg-red-50 rounded-lg">
                <p className="text-2xl font-bold text-red-600">{deployment.summaryJson.failed}</p>
                <p className="text-sm text-muted-foreground">Failed</p>
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
          <CardTitle>Workflows</CardTitle>
        </CardHeader>
        <CardContent>
          {deployment.workflows && deployment.workflows.length > 0 ? (
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
                {deployment.workflows.map((workflow) => (
                  <TableRow key={workflow.id}>
                    <TableCell className="font-medium">
                      {workflow.workflowNameAtTime}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{workflow.changeType}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {workflow.status === 'success' && <CheckCircle className="h-4 w-4 text-green-500" />}
                        {workflow.status === 'failed' && <XCircle className="h-4 w-4 text-red-500" />}
                        {workflow.status === 'pending' && <Clock className="h-4 w-4 text-amber-500" />}
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
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                      {workflow.errorMessage || '-'}
                    </TableCell>
                  </TableRow>
                ))}
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
          <p>{deployment.triggeredByUserId || 'System'}</p>
        </CardContent>
      </Card>
    </div>
  );
}
