/**
 * Activity Center - Unified view of all background jobs (sync, backup, restore, deployments)
 */

import { useEffect, useState, useRef, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
import { Label } from '@/components/ui/label';
import { apiClient } from '@/lib/api-client';
import { useBackgroundJobsSSE } from '@/lib/use-background-jobs-sse';
import { Activity, Loader2, CheckCircle2, XCircle, Clock, RefreshCw, Server, AlertTriangle, Ban, GitBranch } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

// Helper function to format relative time
function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return `${diffSecs} second${diffSecs !== 1 ? 's' : ''} ago`;
  if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
  return date.toLocaleDateString();
}

interface Job {
  id: string;
  job_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  resource_type?: string;
  resource_id?: string;
  progress?: {
    current: number;
    total: number;
    percentage: number;
    message: string;
    current_step?: string;
  };
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  result?: unknown;
  error_details?: unknown;
}

export function ActivityCenterPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [jobTypeFilter, setJobTypeFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [jobToCancel, setJobToCancel] = useState<Job | null>(null);
  const selectedJobIdRef = useRef<string | null>(null);

  // Environment filter state
  const [selectedEnvironmentId, setSelectedEnvironmentId] = useState<string>('');

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  // Fetch environments to get names (must be before useEffect that uses it)
  const { data: environmentsData } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const environments = environmentsData?.data || [];

  // Read env_id URL parameter on mount and set selected environment
  useEffect(() => {
    const envIdParam = searchParams.get('env_id');
    if (envIdParam && envIdParam !== selectedEnvironmentId) {
      // Validate that env_id exists in available environments
      const envExists = environments?.some(env => env.id === envIdParam);
      if (envExists) {
        setSelectedEnvironmentId(envIdParam);
        // Reset to page 1 when environment filter changes
        setCurrentPage(1);
      } else {
        // Invalid env_id: remove from URL and fall back to "All Environments"
        const newSearchParams = new URLSearchParams(searchParams);
        newSearchParams.delete('env_id');
        setSearchParams(newSearchParams, { replace: true });
        setSelectedEnvironmentId('');
        setCurrentPage(1);
      }
    }
  }, [searchParams, environments]);

  // Get job_id from URL query param for pre-selection
  const jobIdFromUrl = searchParams.get('jobId') || searchParams.get('job_id');

  // Cancel job mutation
  const cancelJobMutation = useMutation({
    mutationFn: (jobId: string) => apiClient.cancelBackgroundJob(jobId),
    onSuccess: () => {
      toast({
        title: 'Job cancelled',
        description: 'The job has been cancelled successfully.',
      });
      // Invalidate and refetch jobs
      queryClient.invalidateQueries({ queryKey: ['all-background-jobs'] });
      queryClient.invalidateQueries({ queryKey: ['background-job'] });
      setJobToCancel(null);
    },
    onError: (error: any) => {
      toast({
        title: 'Failed to cancel job',
        description: error?.response?.data?.detail || error?.message || 'An error occurred',
        variant: 'destructive',
      });
      setJobToCancel(null);
    },
  });

  useEffect(() => {
    document.title = 'Activity Center - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  // Subscribe to real-time updates
  useBackgroundJobsSSE({ enabled: true });

  const getEnvironmentName = (envId: string) => {
    return environments.find((e) => e.id === envId)?.name || envId;
  };

  // Fetch all background jobs with server-side pagination
  const { data: jobsResponse, isLoading, isFetching, refetch, error } = useQuery({
    queryKey: ['all-background-jobs', jobTypeFilter, statusFilter, selectedEnvironmentId, currentPage, pageSize],
    queryFn: async () => {
      const params: {
        page?: number;
        pageSize?: number;
        jobType?: string;
        status?: string;
      } = {
        page: currentPage,
        pageSize: pageSize,
      };

      if (jobTypeFilter !== 'all') {
        params.jobType = jobTypeFilter;
      }

      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }

      // Note: Environment filtering will be added to the backend API in a future task (T025-T027)
      // For now, we include it in the queryKey so the query refetches when the filter changes

      const response = await apiClient.getAllBackgroundJobs(params);
      return response.data;
    },
    placeholderData: keepPreviousData,
    refetchInterval: 5000, // Poll every 5 seconds
  });

  // Extract pagination data from response
  const jobsData: Job[] = (jobsResponse as { items?: Job[] })?.items || [];
  const totalJobs = (jobsResponse as { total?: number })?.total || 0;
  const totalPages = (jobsResponse as { totalPages?: number })?.totalPages || 1;

  // Reset to page 1 when filters change
  // Note: selectedEnvironmentId resets are handled explicitly in onChange and URL sync useEffect
  useEffect(() => {
    setCurrentPage(1);
  }, [jobTypeFilter, statusFilter]);

  // If job_id is in URL but not in the list, fetch it individually
  const { data: selectedJobData } = useQuery({
    queryKey: ['background-job', jobIdFromUrl],
    queryFn: async () => {
      if (!jobIdFromUrl) return null;
      try {
        const response = await apiClient.getBackgroundJob(jobIdFromUrl);
        console.log('[ActivityCenter] Fetched specific job:', response.data);
        return response.data;
      } catch (err) {
        console.error('[ActivityCenter] Error fetching specific job:', err);
        return null;
      }
    },
    enabled: !!jobIdFromUrl,
    // Smart polling: only poll active jobs, with exponential backoff
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job) return false;
      // Only poll if job is still active
      if (job.status === 'pending' || job.status === 'running') {
        // Start at 2s, max 10s based on how long job has been running
        const elapsed = Date.now() - new Date(job.created_at || Date.now()).getTime();
        const interval = Math.min(2000 + Math.floor(elapsed / 30000) * 2000, 10000);
        return interval;
      }
      return false; // Stop polling when complete
    },
  });

  // Merge selected job into jobs list if it's not already there
  const jobs: Job[] = useMemo(() => {
    if (selectedJobData && jobIdFromUrl) {
      const exists = jobsData.find((j: Job) => j.id === jobIdFromUrl);
      if (!exists) {
        return [selectedJobData as Job, ...jobsData];
      }
    }
    return jobsData;
  }, [jobsData, selectedJobData, jobIdFromUrl]);

  // Scroll to selected job when it loads
  useEffect(() => {
    if (jobIdFromUrl && jobs.length > 0) {
      const job = jobs.find((j) => j.id === jobIdFromUrl);
      if (job && selectedJobIdRef.current !== jobIdFromUrl) {
        selectedJobIdRef.current = jobIdFromUrl;
        // Scroll to the job row after a brief delay to ensure it's rendered
        setTimeout(() => {
          const element = document.getElementById(`job-${jobIdFromUrl}`);
          if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            element.classList.add('bg-blue-50', 'dark:bg-blue-950/30');
            setTimeout(() => {
              element.classList.remove('bg-blue-50', 'dark:bg-blue-950/30');
            }, 3000);
          }
        }, 100);
      }
    }
  }, [jobIdFromUrl, jobs]);

  const getJobTypeLabel = (jobType: string) => {
    switch (jobType) {
      case 'environment_sync':
        return 'Environment Refresh';
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
      case 'canonical_env_sync':
        return 'Refresh';
      case 'dev_git_sync':
        return 'Refresh';
      default:
        return jobType;
    }
  };

  const hasGitSideEffect = (job: Job): boolean => {
    // Check if this is a dev_git_sync job with Git persisted workflows
    if (job.job_type === 'dev_git_sync' && job.status === 'completed' && job.result) {
      const result = job.result as { workflows_persisted?: number };
      return (result.workflows_persisted ?? 0) > 0;
    }
    return false;
  };

  const getPhaseLabelForJob = (currentStep?: string): string => {
    if (!currentStep) return 'Unknown';
    
    const phaseMap: Record<string, string> = {
      'discovering_workflows': 'Discovering workflows',
      'updating_environment_state': 'Updating environment state',
      'reconciling_drift': 'Reconciling drift',
      'finalizing_sync': 'Finalizing refresh',
      'persisting_to_git': 'Persisting to Git',
      'completed': 'Completed',
      'failed': 'Failed',
      'initializing': 'Initializing'
    };
    
    return phaseMap[currentStep] || currentStep;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
      case 'pending':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'cancelled':
        return <Clock className="h-4 w-4 text-gray-500" />;
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Activity className="h-8 w-8" />
            Activity Center
          </h1>
          <p className="text-muted-foreground">
            View all background jobs, refreshes, backups, and deployments
          </p>
        </div>
        <Button onClick={() => refetch()} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Environment Filter */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filter by Environment</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="space-y-2 flex-1">
              <Label htmlFor="environment">Environment</Label>
              <select
                id="environment"
                value={selectedEnvironmentId}
                onChange={(e) => {
                  const newEnvId = e.target.value;
                  setSelectedEnvironmentId(newEnvId);

                  // Reset to page 1 when environment filter changes
                  setCurrentPage(1);

                  // Sync selection to URL env_id param
                  const newSearchParams = new URLSearchParams(searchParams);
                  if (newEnvId) {
                    newSearchParams.set('env_id', newEnvId);
                  } else {
                    newSearchParams.delete('env_id');
                  }
                  setSearchParams(newSearchParams, { replace: true });
                }}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="" className="bg-background text-foreground">All Environments</option>
                {environments?.map((env) => (
                  <option key={env.id} value={env.id} className="bg-background text-foreground">
                    {env.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Background Jobs</CardTitle>
              <CardDescription>
                All long-running operations across your environments
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Select value={jobTypeFilter} onValueChange={setJobTypeFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Filter by type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="environment_sync">Refresh</SelectItem>
                  <SelectItem value="github_sync_to">Backup</SelectItem>
                  <SelectItem value="github_sync_from">Restore</SelectItem>
                  <SelectItem value="promotion_execute">Deployment</SelectItem>
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="running">Running</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="text-center py-8 text-red-600 dark:text-red-400">
              <p>Error loading jobs: {error instanceof Error ? error.message : 'Unknown error'}</p>
              <Button onClick={() => refetch()} variant="outline" size="sm" className="mt-4">
                Retry
              </Button>
            </div>
          ) : isLoading ? (
            <div className="text-center py-8">Loading jobs...</div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>No background jobs found.</p>
              <p className="text-sm mt-2">
                Background jobs will appear here when you run refresh, backup, or restore operations.
              </p>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Resource</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Progress</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead>Error</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobs.map((job) => {
                    const canCancel = job.status === 'pending' || job.status === 'running';
                    return (
                    <TableRow
                      key={job.id}
                      id={`job-${job.id}`}
                      className={`${job.id === jobIdFromUrl ? 'bg-blue-50 dark:bg-blue-950/30' : ''}`}
                    >
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <span>{getJobTypeLabel(job.job_type)}</span>
                          {hasGitSideEffect(job) && (
                            <Badge variant="outline" className="flex items-center gap-1 text-xs">
                              <GitBranch className="h-3 w-3" />
                              Git updated
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {job.resource_type === 'environment' && job.resource_id ? (
                          <Link
                            to={`/environments/${job.resource_id}`}
                            className="flex items-center gap-2 text-sm text-primary hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Server className="h-4 w-4 text-muted-foreground" />
                            {getEnvironmentName(job.resource_id)}
                          </Link>
                        ) : job.resource_type === 'promotion' && job.resource_id ? (
                          <Link
                            to={`/deployments/${job.resource_id}`}
                            className="text-sm text-primary hover:underline flex items-center gap-1"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Activity className="h-4 w-4 text-muted-foreground" />
                            Deployment {job.resource_id.slice(0, 8)}...
                          </Link>
                        ) : (
                          <div className="text-sm text-muted-foreground">
                            {job.resource_type || '—'}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={getStatusVariant(job.status)} className="flex items-center gap-1 w-fit">
                          {getStatusIcon(job.status)}
                          {job.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {job.status === 'completed' ? (
                          <div className="space-y-1">
                            <div className="text-sm font-medium text-green-600 dark:text-green-400">
                              Completed
                            </div>
                            {job.progress?.current !== undefined && job.progress?.total !== undefined && job.progress.total > 0 && (
                              <div className="text-xs text-muted-foreground">
                                {job.progress.total} workflow{job.progress.total !== 1 ? 's' : ''} processed
                              </div>
                            )}
                          </div>
                        ) : job.status === 'failed' ? (
                          <div className="space-y-1">
                            <div className="text-sm font-medium text-red-600 dark:text-red-400">
                              Failed
                            </div>
                            {job.progress?.current_step && (
                              <div className="text-xs text-muted-foreground">
                                During: {getPhaseLabelForJob(job.progress.current_step)}
                              </div>
                            )}
                          </div>
                        ) : job.progress ? (
                          <div className="space-y-1">
                            {job.progress.current_step ? (
                              <div className="text-sm font-medium">
                                {getPhaseLabelForJob(job.progress.current_step)}
                              </div>
                            ) : null}
                            {job.progress.current !== undefined && job.progress.total !== undefined && job.progress.total > 0 ? (
                              <div className="text-sm">
                                {job.progress.current} / {job.progress.total} ({job.progress.percentage || Math.round((job.progress.current / job.progress.total) * 100)}%)
                              </div>
                            ) : null}
                            {job.progress.message && !job.progress.message.includes('batch') && !job.progress.message.includes('Completed batch') && (
                              <div className="text-xs text-muted-foreground">
                                {job.progress.message}
                              </div>
                            )}
                          </div>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDuration(job.started_at, job.completed_at)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatRelativeTime(new Date(job.created_at))}
                      </TableCell>
                      <TableCell>
                        {job.error_message ? (
                          <div className="flex items-center gap-1 text-red-600 dark:text-red-400">
                            <AlertTriangle className="h-4 w-4" />
                            <span className="text-xs truncate max-w-[200px]" title={job.error_message}>
                              {job.error_message}
                            </span>
                          </div>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/activity/${job.id}`);
                            }}
                          >
                            View
                          </Button>
                          {canCancel && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => {
                                e.stopPropagation();
                                setJobToCancel(job);
                              }}
                              disabled={cancelJobMutation.isPending}
                            >
                              <Ban className="h-4 w-4 mr-1" />
                              Cancel
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                    );
                  })}
                </TableBody>
              </Table>

              {/* Pagination Controls */}
              <div className="mt-4 flex items-center justify-between border-t pt-4">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="pageSize" className="text-sm text-muted-foreground">
                      Rows per page:
                    </Label>
                    <select
                      id="pageSize"
                      value={pageSize}
                      onChange={(e) => {
                        setPageSize(Number(e.target.value));
                        setCurrentPage(1);
                      }}
                      className="h-8 w-20 rounded-md border border-input bg-background text-foreground px-2 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    >
                      <option value={10} className="bg-background text-foreground">10</option>
                      <option value={25} className="bg-background text-foreground">25</option>
                      <option value={50} className="bg-background text-foreground">50</option>
                      <option value={100} className="bg-background text-foreground">100</option>
                    </select>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Showing {totalJobs > 0 ? ((currentPage - 1) * pageSize) + 1 : 0} to {Math.min(currentPage * pageSize, totalJobs)} of {totalJobs} jobs
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {isFetching && (
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1 || isFetching}
                  >
                    First
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(currentPage - 1)}
                    disabled={currentPage === 1 || isFetching}
                  >
                    Previous
                  </Button>
                  <div className="flex items-center gap-1">
                    <span className="text-sm">
                      Page {currentPage} of {totalPages}
                    </span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(currentPage + 1)}
                    disabled={currentPage >= totalPages || isFetching}
                  >
                    Next
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage >= totalPages || isFetching}
                  >
                    Last
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Cancel Confirmation Dialog */}
      <AlertDialog open={!!jobToCancel} onOpenChange={(open) => !open && setJobToCancel(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Job</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to cancel this job?
              <br />
              <br />
              <strong>Job Type:</strong> {jobToCancel && getJobTypeLabel(jobToCancel.job_type)}
              <br />
              <strong>Status:</strong> {jobToCancel?.status}
              <br />
              <br />
              <span className="text-xs text-muted-foreground">
                Note: The job will be marked as cancelled in the database. Workers must cooperatively check the status and exit gracefully. This does not forcefully terminate running processes.
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>No, keep running</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (jobToCancel) {
                  cancelJobMutation.mutate(jobToCancel.id);
                }
              }}
              className="bg-red-600 hover:bg-red-700"
            >
              Yes, cancel job
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

