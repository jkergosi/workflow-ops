/**
 * Activity Center - Unified view of all background jobs (sync, backup, restore, deployments)
 */

import { useEffect, useState, useRef, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
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
import { apiClient } from '@/lib/api-client';
import { useBackgroundJobsSSE } from '@/lib/use-background-jobs-sse';
import { Activity, Loader2, CheckCircle2, XCircle, Clock, RefreshCw, Server, AlertTriangle } from 'lucide-react';

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
  resource_type: string;
  resource_id: string;
  progress: {
    current: number;
    total: number;
    percentage: number;
    message: string;
  };
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

export function ActivityCenterPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [jobTypeFilter, setJobTypeFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const selectedJobIdRef = useRef<string | null>(null);

  // Get job_id from URL query param for pre-selection
  const jobIdFromUrl = searchParams.get('jobId') || searchParams.get('job_id');

  useEffect(() => {
    document.title = 'Activity Center - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  // Subscribe to real-time updates
  useBackgroundJobsSSE({ enabled: true });

  // Fetch environments to get names
  const { data: environmentsData } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const environments = environmentsData?.data || [];

  const getEnvironmentName = (envId: string) => {
    return environments.find((e) => e.id === envId)?.name || envId;
  };

  // Fetch all background jobs
  const { data: jobsData, isLoading, refetch, error } = useQuery({
    queryKey: ['all-background-jobs', jobTypeFilter, statusFilter],
    queryFn: async () => {
      try {
        const params: any = {
          limit: 50,
        };
        
        if (jobTypeFilter !== 'all') {
          params.job_type = jobTypeFilter;
        }
        
        if (statusFilter !== 'all') {
          params.status = statusFilter;
        }
        
        const response = await apiClient.getAllBackgroundJobs(params);
        console.log('[ActivityCenter] Query params:', params);
        console.log('[ActivityCenter] Full API response:', JSON.stringify(response, null, 2));
        console.log('[ActivityCenter] response.data:', response.data);
        console.log('[ActivityCenter] response.data type:', typeof response.data);
        console.log('[ActivityCenter] response.data is array:', Array.isArray(response.data));
        console.log('[ActivityCenter] Jobs array:', response.data?.jobs);
        console.log('[ActivityCenter] Total count:', response.data?.total);
        
        // Handle both response formats (array or object)
        if (Array.isArray(response.data)) {
          console.warn('[ActivityCenter] WARNING: Response is an array, not an object with jobs/total');
          return response.data;
        }
        return response.data?.jobs || [];
      } catch (err) {
        console.error('[ActivityCenter] Error fetching jobs:', err);
        throw err;
      }
    },
    refetchInterval: 5000, // Poll every 5 seconds
  });

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
    refetchInterval: 2000, // Poll every 2 seconds if job is running
  });

  // Merge selected job into jobs list if it's not already there
  const allJobs = jobsData || [];
  const jobs = useMemo(() => {
    console.log('[ActivityCenter] Processing jobs - allJobs:', allJobs.length, 'selectedJobData:', !!selectedJobData, 'jobIdFromUrl:', jobIdFromUrl);
    if (selectedJobData && jobIdFromUrl) {
      const exists = allJobs.find((j) => j.id === jobIdFromUrl);
      console.log('[ActivityCenter] Selected job exists in list:', !!exists);
      if (!exists) {
        console.log('[ActivityCenter] Adding selected job to list');
        return [selectedJobData, ...allJobs];
      }
    }
    console.log('[ActivityCenter] Returning jobs list with', allJobs.length, 'items');
    return allJobs;
  }, [allJobs, selectedJobData, jobIdFromUrl]);

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
            View all background jobs, syncs, backups, and deployments
          </p>
        </div>
        <Button onClick={() => refetch()} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

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
                  <SelectItem value="environment_sync">Sync</SelectItem>
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
                Background jobs will appear here when you run sync, backup, or restore operations.
              </p>
            </div>
          ) : (
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
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow 
                    key={job.id} 
                    id={`job-${job.id}`}
                    className={`cursor-pointer hover:bg-muted/50 ${job.id === jobIdFromUrl ? 'bg-blue-50 dark:bg-blue-950/30' : ''}`}
                    onClick={() => navigate(`/activity/${job.id}`)}
                  >
                    <TableCell className="font-medium">
                      {getJobTypeLabel(job.job_type)}
                    </TableCell>
                    <TableCell>
                      {job.resource_type === 'environment' ? (
                        <Link
                          to={`/environments/${job.resource_id}`}
                          className="flex items-center gap-2 text-sm text-primary hover:underline"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Server className="h-4 w-4 text-muted-foreground" />
                          {getEnvironmentName(job.resource_id)}
                        </Link>
                      ) : job.resource_type === 'promotion' ? (
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
                      {job.progress ? (
                        <div className="space-y-1">
                          <div className="text-sm">
                            {job.progress.current} / {job.progress.total} ({job.progress.percentage}%)
                          </div>
                          {job.progress.message && (
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
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

