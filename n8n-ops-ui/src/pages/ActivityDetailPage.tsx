// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api-client';
import { useBackgroundJobsSSE } from '@/lib/use-background-jobs-sse';
import { 
  ArrowLeft, 
  Activity, 
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  AlertTriangle,
  Server,
  Calendar,
  User,
  FileText
} from 'lucide-react';
import { useEffect } from 'react';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';

export function ActivityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = 'Activity Details - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  // Fetch job details
  const { data: jobData, isLoading, error } = useQuery({
    queryKey: ['background-job', id],
    queryFn: async () => {
      if (!id) return null;
      const response = await apiClient.getBackgroundJob(id);
      return response.data;
    },
    enabled: !!id,
    refetchInterval: (data) => {
      // Poll every 2 seconds if job is running, otherwise every 10 seconds
      return data?.status === 'running' || data?.status === 'pending' ? 2000 : 10000;
    },
  });

  const job = jobData;

  // Subscribe to real-time updates if job is running
  useBackgroundJobsSSE({
    enabled: !isLoading && !!id && (job?.status === 'running' || job?.status === 'pending'),
  });

  // Fetch environment name if resource_type is environment
  const { data: environmentData } = useQuery({
    queryKey: ['environment', job?.resource_id],
    queryFn: () => apiClient.getEnvironment(job!.resource_id),
    enabled: !!job?.resource_id && job?.resource_type === 'environment',
  });

  const environmentName = environmentData?.data?.name || job?.resource_id;

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
      case 'pending':
        return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'cancelled':
        return <Clock className="h-5 w-5 text-gray-500" />;
      default:
        return null;
    }
  };

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'running':
      case 'pending':
        return 'secondary';
      case 'completed':
        return 'default';
      case 'failed':
        return 'destructive';
      case 'cancelled':
        return 'outline';
      default:
        return 'outline';
    }
  };

  const getJobTypeLabel = (jobType: string) => {
    switch (jobType) {
      case 'environment_sync':
        return 'Environment Sync';
      case 'github_sync_to':
        return 'GitHub Backup';
      case 'github_sync_from':
        return 'GitHub Restore';
      case 'promotion_execute':
        return 'Deployment';
      case 'restore_execute':
        return 'Restore';
      case 'snapshot_restore':
        return 'Snapshot Restore';
      default:
        return jobType;
    }
  };

  const formatDuration = (startedAt?: string, completedAt?: string) => {
    if (!startedAt) return '—';
    const start = new Date(startedAt);
    const end = completedAt ? new Date(completedAt) : new Date();
    const seconds = Math.round((end.getTime() - start.getTime()) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const formatDateTime = (dateString?: string) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleString();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="container mx-auto p-6">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-8">
              <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
              <h2 className="text-xl font-semibold mb-2">Activity not found</h2>
              <p className="text-muted-foreground mb-4">
                The activity you're looking for doesn't exist or you don't have access to it.
              </p>
              <Button onClick={() => navigate('/activity')} variant="outline">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Activity Center
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const progress = job.progress || {};
  const result = job.result || {};
  const errorDetails = job.error_details || {};

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/activity')}
            className="mt-1"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3 mb-2">
              <Activity className="h-8 w-8" />
              {getJobTypeLabel(job.job_type)}
            </h1>
            <div className="flex items-center gap-2 mt-2">
              <Badge variant={getStatusVariant(job.status)} className="flex items-center gap-1">
                {getStatusIcon(job.status)}
                {job.status}
              </Badge>
              {job.resource_type === 'environment' && (
                <Link to={`/environments/${job.resource_id}`}>
                  <Badge variant="outline" className="flex items-center gap-1 hover:bg-muted cursor-pointer">
                    <Server className="h-3 w-3" />
                    {environmentName}
                  </Badge>
                </Link>
              )}
              {job.resource_type === 'promotion' && (
                <Link to={`/deployments/${job.resource_id}`}>
                  <Badge variant="outline" className="flex items-center gap-1 hover:bg-muted cursor-pointer">
                    <Activity className="h-3 w-3" />
                    Deployment {job.resource_id.slice(0, 8)}...
                  </Badge>
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Status Card */}
      <Card>
        <CardHeader>
          <CardTitle>Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="text-sm font-medium text-muted-foreground">Status</label>
              <div className="flex items-center gap-2 mt-1">
                {getStatusIcon(job.status)}
                <span className="font-medium">{job.status}</span>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Started</label>
              <p className="text-sm mt-1">{formatDateTime(job.started_at)}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Completed</label>
              <p className="text-sm mt-1">{formatDateTime(job.completed_at)}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-muted-foreground">Duration</label>
              <p className="text-sm mt-1">{formatDuration(job.started_at, job.completed_at)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Progress */}
      {progress && (progress.current !== undefined || progress.total !== undefined) && (
        <Card>
          <CardHeader>
            <CardTitle>Progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {progress.current !== undefined && progress.total !== undefined && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>Progress</span>
                  <span>
                    {progress.current} / {progress.total} ({progress.percentage || Math.round((progress.current / progress.total) * 100)}%)
                  </span>
                </div>
                <Progress 
                  value={progress.percentage || (progress.total > 0 ? (progress.current / progress.total) * 100 : 0)} 
                  className="h-2" 
                />
              </div>
            )}
            {progress.message && (
              <p className="text-sm text-muted-foreground">
                <span className="font-medium">Current step:</span> {progress.message}
              </p>
            )}
            {progress.current_step && (
              <p className="text-sm text-muted-foreground">
                <span className="font-medium">Step:</span> {progress.current_step}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {job.status === 'completed' && result && Object.keys(result).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Results</CardTitle>
            <CardDescription>Summary of completed operations</CardDescription>
          </CardHeader>
          <CardContent>
            {result.workflows && (
              <div className="space-y-2 mb-4">
                <h4 className="font-medium flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  Workflows
                </h4>
                <div className="pl-6 space-y-1">
                  <p className="text-sm">Synced: {result.workflows.synced || 0}</p>
                  {result.workflows.errors && result.workflows.errors.length > 0 && (
                    <div className="text-sm text-red-600 dark:text-red-400">
                      <p className="font-medium">Errors:</p>
                      <ul className="list-disc list-inside ml-2">
                        {result.workflows.errors.map((error: string, idx: number) => (
                          <li key={idx}>{error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
            {result.executions && (
              <div className="space-y-2 mb-4">
                <h4 className="font-medium flex items-center gap-2">
                  <Activity className="h-4 w-4" />
                  Executions
                </h4>
                <div className="pl-6">
                  <p className="text-sm">Synced: {result.executions.synced || 0}</p>
                  {result.executions.errors && result.executions.errors.length > 0 && (
                    <div className="text-sm text-red-600 dark:text-red-400 mt-1">
                      <p className="font-medium">Errors:</p>
                      <ul className="list-disc list-inside ml-2">
                        {result.executions.errors.map((error: string, idx: number) => (
                          <li key={idx}>{error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
            {result.credentials && (
              <div className="space-y-2 mb-4">
                <h4 className="font-medium flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  Credentials
                </h4>
                <div className="pl-6">
                  <p className="text-sm">Synced: {result.credentials.synced || 0}</p>
                  {result.credentials.errors && result.credentials.errors.length > 0 && (
                    <div className="text-sm text-red-600 dark:text-red-400 mt-1">
                      <p className="font-medium">Errors:</p>
                      <ul className="list-disc list-inside ml-2">
                        {result.credentials.errors.map((error: string, idx: number) => (
                          <li key={idx}>{error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
            {result.users && (
              <div className="space-y-2 mb-4">
                <h4 className="font-medium flex items-center gap-2">
                  <User className="h-4 w-4" />
                  Users
                </h4>
                <div className="pl-6">
                  <p className="text-sm">Synced: {result.users.synced || 0}</p>
                  {result.users.errors && result.users.errors.length > 0 && (
                    <div className="text-sm text-red-600 dark:text-red-400 mt-1">
                      <p className="font-medium">Errors:</p>
                      <ul className="list-disc list-inside ml-2">
                        {result.users.errors.map((error: string, idx: number) => (
                          <li key={idx}>{error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
            {result.tags && (
              <div className="space-y-2">
                <h4 className="font-medium flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  Tags
                </h4>
                <div className="pl-6">
                  <p className="text-sm">Synced: {result.tags.synced || 0}</p>
                  {result.tags.errors && result.tags.errors.length > 0 && (
                    <div className="text-sm text-red-600 dark:text-red-400 mt-1">
                      <p className="font-medium">Errors:</p>
                      <ul className="list-disc list-inside ml-2">
                        {result.tags.errors.map((error: string, idx: number) => (
                          <li key={idx}>{error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}
            {/* Generic result display for other job types */}
            {!result.workflows && !result.executions && !result.credentials && !result.users && !result.tags && (
              <div className="space-y-2">
                <pre className="text-xs bg-muted p-4 rounded overflow-auto">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Errors */}
      {(job.status === 'failed' || job.error_message || (errorDetails && Object.keys(errorDetails).length > 0)) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-600 dark:text-red-400">
              <AlertTriangle className="h-5 w-5" />
              Errors
            </CardTitle>
          </CardHeader>
          <CardContent>
            {job.error_message && (
              <Alert variant="destructive" className="mb-4">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription className="text-foreground">
                  <p className="font-medium">{job.error_message}</p>
                </AlertDescription>
              </Alert>
            )}
            {errorDetails && Object.keys(errorDetails).length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium">Error Details</h4>
                <pre className="text-xs bg-muted p-4 rounded overflow-auto">
                  {JSON.stringify(errorDetails, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Raw Data (for debugging) */}
      <Card>
        <CardHeader>
          <CardTitle>Raw Data</CardTitle>
          <CardDescription>Complete job record for diagnostics</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="text-xs bg-muted p-4 rounded overflow-auto max-h-96">
            {JSON.stringify(job, null, 2)}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}

