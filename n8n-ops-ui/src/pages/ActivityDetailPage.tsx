// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api-client';
import { useBackgroundJobsSSE } from '@/lib/use-background-jobs-sse';
import type { LogMessage } from '@/lib/use-background-jobs-sse';
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
  FileText,
  Circle,
  CircleDot,
  ChevronDown,
  ChevronRight,
  Terminal
} from 'lucide-react';
import { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';

export function ActivityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = 'Activity Details - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
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
    refetchInterval: (query) => {
      const job = query.state.data;
      if (!job) return 2000;
      // Only poll if job is still active, with exponential backoff
      if (job.status === 'pending' || job.status === 'running') {
        // Start at 2s, increase based on job age, max 10s
        const elapsed = Date.now() - new Date(job.created_at || Date.now()).getTime();
        const interval = Math.min(2000 + Math.floor(elapsed / 30000) * 2000, 10000);
        return interval;
      }
      return false; // Stop polling when complete/failed
    },
  });

  const job = jobData;

  // Live log messages state
  const [logMessages, setLogMessages] = useState<LogMessage[]>([]);
  const [isLogOpen, setIsLogOpen] = useState(true);
  const logContainerRef = useRef<HTMLDivElement>(null);
  
  // Handler for log messages from SSE
  const handleLogMessage = useCallback((message: LogMessage) => {
    setLogMessages(prev => {
      // Avoid duplicate consecutive messages
      if (prev.length > 0 && prev[prev.length - 1].message === message.message) {
        return prev;
      }
      // Keep last 100 messages
      const newMessages = [...prev, message];
      if (newMessages.length > 100) {
        return newMessages.slice(-100);
      }
      return newMessages;
    });
  }, []);
  
  // Auto-scroll log to bottom when new messages arrive
  useEffect(() => {
    if (logContainerRef.current && isLogOpen) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logMessages, isLogOpen]);

  // Subscribe to real-time updates if job is running
  useBackgroundJobsSSE({
    enabled: !isLoading && !!id && (job?.status === 'running' || job?.status === 'pending'),
    jobId: id,  // Pass job ID to filter SSE events for this specific job
    onLogMessage: handleLogMessage,
  });

  // Fetch environment name if resource_type is environment
  const { data: environmentData } = useQuery({
    queryKey: ['environment', job?.resource_id],
    queryFn: () => apiClient.getEnvironment(job!.resource_id),
    enabled: !!job?.resource_id && job?.resource_type === 'environment',
  });

  const environmentName = environmentData?.data?.name || job?.resource_id;
  const environmentClass = environmentData?.data?.environment_class?.toLowerCase() || '';
  const isDevEnvironment = environmentClass === 'dev';

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
      case 'canonical_env_sync':
        return 'Canonical Sync';
      case 'dev_git_sync':
        return 'DEV Git Sync';
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

  // Live duration counter for running jobs
  const [liveDuration, setLiveDuration] = useState<string>('—');
  
  useEffect(() => {
    if (!job?.started_at) {
      setLiveDuration('—');
      return;
    }
    
    // If job is completed, show final duration
    if (job.completed_at) {
      setLiveDuration(formatDuration(job.started_at, job.completed_at));
      return;
    }
    
    // For running jobs, update every second
    const updateDuration = () => {
      setLiveDuration(formatDuration(job.started_at, undefined));
    };
    
    updateDuration(); // Initial update
    const interval = setInterval(updateDuration, 1000);
    
    return () => clearInterval(interval);
  }, [job?.started_at, job?.completed_at, job?.status]);

  // Define sync phases for the timeline - differs by environment type
  // DEV: n8n → DB → Git (no drift concept)
  // Non-DEV: Git → DB, then detect drift against n8n
  const SYNC_PHASES_DEV = [
    { key: 'initializing', label: 'Initializing', order: 0 },
    { key: 'discovering_workflows', label: 'Discovering workflows from n8n', order: 1 },
    { key: 'updating_environment_state', label: 'Syncing n8n → Database', order: 2 },
    { key: 'persisting_to_git', label: 'Persisting to Git', order: 3 },
    { key: 'finalizing_sync', label: 'Finalizing', order: 4 },
    { key: 'completed', label: 'Completed', order: 5 },
  ];
  
  const SYNC_PHASES_NON_DEV = [
    { key: 'initializing', label: 'Initializing', order: 0 },
    { key: 'discovering_workflows', label: 'Discovering workflows', order: 1 },
    { key: 'updating_environment_state', label: 'Capturing n8n state', order: 2 },
    { key: 'reconciling_drift', label: 'Detecting drift (n8n vs Git)', order: 3 },
    { key: 'finalizing_sync', label: 'Finalizing', order: 4 },
    { key: 'completed', label: 'Completed', order: 5 },
  ];
  
  const SYNC_PHASES = isDevEnvironment ? SYNC_PHASES_DEV : SYNC_PHASES_NON_DEV;

  // Determine phase status for timeline
  const getPhaseStatus = (phaseKey: string, currentStep?: string) => {
    if (!currentStep) return 'pending';
    
    const currentPhase = SYNC_PHASES.find(p => p.key === currentStep);
    const targetPhase = SYNC_PHASES.find(p => p.key === phaseKey);
    
    if (!currentPhase || !targetPhase) return 'pending';
    
    if (job?.status === 'completed') {
      return 'completed';
    }
    if (job?.status === 'failed') {
      if (targetPhase.order < currentPhase.order) return 'completed';
      if (targetPhase.order === currentPhase.order) return 'failed';
      return 'pending';
    }
    
    if (targetPhase.order < currentPhase.order) return 'completed';
    if (targetPhase.order === currentPhase.order) return 'active';
    return 'pending';
  };

  const formatDateTime = (dateString?: string) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleString();
  };

  // Phase labels for canonical sync jobs - context-aware for DEV vs non-DEV
  const getPhaseLabel = (currentStep?: string): string => {
    if (!currentStep) return 'Unknown';
    
    // DEV-specific labels (n8n is source of truth)
    const devPhaseMap: Record<string, string> = {
      'discovering_workflows': 'Discovering workflows from n8n',
      'updating_environment_state': 'Syncing n8n → Database',
      'persisting_to_git': 'Persisting to Git',
      'finalizing_sync': 'Finalizing sync',
      'completed': 'Completed',
      'failed': 'Failed',
      'initializing': 'Initializing'
    };
    
    // Non-DEV labels (Git is source of truth, detecting drift)
    const nonDevPhaseMap: Record<string, string> = {
      'discovering_workflows': 'Discovering workflows',
      'updating_environment_state': 'Capturing n8n state',
      'reconciling_drift': 'Detecting drift (n8n vs Git)',
      'finalizing_sync': 'Finalizing sync',
      'completed': 'Completed',
      'failed': 'Failed',
      'initializing': 'Initializing'
    };
    
    const phaseMap = isDevEnvironment ? devPhaseMap : nonDevPhaseMap;
    return phaseMap[currentStep] || currentStep;
  };

  // Format progress message with counts
  const formatProgressMessage = (progress: any, currentStep?: string): string => {
    if (!progress) return '';
    
    const { current, total, message } = progress;
    
    // If message already contains phase info, use it
    if (message && !message.includes('batch') && !message.includes('Completed batch')) {
      return message;
    }
    
    // For phase-based steps, show counts
    if (currentStep && current !== undefined && total !== undefined && total > 0) {
      const phaseLabel = getPhaseLabel(currentStep);
      return `${phaseLabel}: ${current} / ${total} workflows`;
    }
    
    return message || '';
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

  // Normalize progress - handle both camelCase and snake_case
  const rawProgress = job.progress || {};
  const progress = {
    ...rawProgress,
    current_step: rawProgress.current_step || rawProgress.currentStep,
    currentStep: rawProgress.current_step || rawProgress.currentStep,
  };
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
              <p className="text-sm mt-1 font-mono tabular-nums">
                {liveDuration}
                {(job.status === 'running' || job.status === 'pending') && !job.completed_at && (
                  <span className="ml-1 text-blue-500 animate-pulse">●</span>
                )}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Progress */}
      {progress && (progress.current !== undefined || progress.total !== undefined || progress.current_step) && (
        <Card>
          <CardHeader>
            <CardTitle>Progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {job.status === 'completed' && result?.completion_summary ? (
              // Completion Summary Card
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  <h3 className="font-semibold">Sync complete</h3>
                </div>
                <div className="space-y-2 pl-7">
                  <p className="text-sm">
                    <span className="font-medium">{result.completion_summary.workflows_processed}</span> workflow(s) processed
                  </p>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <span>{result.completion_summary.workflows_linked} linked</span>
                    {result.completion_summary.workflows_untracked > 0 && (
                      <span>· {result.completion_summary.workflows_untracked} untracked</span>
                    )}
                    {result.completion_summary.workflows_missing > 0 && (
                      <span>· {result.completion_summary.workflows_missing} missing</span>
                    )}
                    {result.completion_summary.workflows_skipped > 0 && (
                      <span>· {result.completion_summary.workflows_skipped} skipped</span>
                    )}
                  </div>
                  {/* DEV environment: show Git persist status (no drift concept for DEV) */}
                  {isDevEnvironment && (
                    <>
                      {result.workflows_persisted !== undefined && result.workflows_persisted > 0 ? (
                        <p className="text-sm text-green-600 dark:text-green-400">
                          {result.workflows_persisted} workflow(s) persisted to Git
                        </p>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          Git is in sync with n8n (no changes to persist)
                        </p>
                      )}
                    </>
                  )}
                  {/* Non-DEV environment: show drift detection (Git is source of truth) */}
                  {!isDevEnvironment && result.completion_summary.drift_detected_count > 0 && (
                    <p className="text-sm text-yellow-600 dark:text-yellow-400">
                      Drift detected in {result.completion_summary.drift_detected_count} workflow(s)
                    </p>
                  )}
                  {!isDevEnvironment && result.completion_summary.drift_detected_count === 0 && (
                    <p className="text-sm text-green-600 dark:text-green-400">
                      No drift detected - n8n matches Git
                    </p>
                  )}
                </div>
              </div>
            ) : job.status === 'failed' ? (
              // Failed Job Summary
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <XCircle className="h-5 w-5 text-red-500" />
                  <h3 className="font-semibold text-red-600 dark:text-red-400">Job failed</h3>
                </div>
                <div className="space-y-2 pl-7">
                  {progress.current_step && (
                    <p className="text-sm">
                      Failed during: <span className="font-medium">{getPhaseLabel(progress.current_step)}</span>
                    </p>
                  )}
                  {progress.current !== undefined && progress.total !== undefined && progress.total > 0 && (
                    <p className="text-sm text-muted-foreground">
                      Processed {progress.current} of {progress.total} workflow(s) before failure
                    </p>
                  )}
                  {progress.message && (
                    <p className="text-sm text-muted-foreground">
                      {progress.message}
                    </p>
                  )}
                </div>
              </div>
            ) : (
              // Running Progress
              <>
                {progress.current_step && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium">
                      {getPhaseLabel(progress.current_step)}
                    </p>
                    {progress.current !== undefined && progress.total !== undefined && progress.total > 0 && (
                      <p className="text-xs text-muted-foreground">
                        {progress.current} / {progress.total} workflows
                      </p>
                    )}
                  </div>
                )}
                {progress.current !== undefined && progress.total !== undefined && progress.total > 0 && (
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
                {formatProgressMessage(progress, progress.current_step) && (
                  <p className="text-sm text-muted-foreground">
                    {formatProgressMessage(progress, progress.current_step)}
                  </p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Sync Phase Timeline */}
      {(job.job_type === 'canonical_env_sync' || job.job_type === 'environment_sync') && (
        <Card>
          <CardHeader>
            <CardTitle>Sync Phases</CardTitle>
            <CardDescription>Timeline of sync operation phases</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="relative">
              {/* Vertical line */}
              <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-border" />
              
              <div className="space-y-4">
                {SYNC_PHASES.filter(p => p.key !== 'completed').map((phase, index) => {
                  const status = getPhaseStatus(phase.key, progress?.current_step);
                  const isActive = status === 'active';
                  const isCompleted = status === 'completed';
                  const isFailed = status === 'failed';
                  
                  return (
                    <div key={phase.key} className="relative flex items-start gap-4 pl-0">
                      {/* Phase indicator */}
                      <div className={`relative z-10 flex items-center justify-center w-6 h-6 rounded-full border-2 ${
                        isCompleted ? 'bg-green-500 border-green-500' :
                        isActive ? 'bg-blue-500 border-blue-500' :
                        isFailed ? 'bg-red-500 border-red-500' :
                        'bg-background border-muted-foreground/30'
                      }`}>
                        {isCompleted && <CheckCircle2 className="h-4 w-4 text-white" />}
                        {isActive && <Loader2 className="h-3 w-3 text-white animate-spin" />}
                        {isFailed && <XCircle className="h-4 w-4 text-white" />}
                        {!isCompleted && !isActive && !isFailed && (
                          <Circle className="h-3 w-3 text-muted-foreground/50" />
                        )}
                      </div>
                      
                      {/* Phase content */}
                      <div className="flex-1 min-w-0 pb-4">
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-medium ${
                            isActive ? 'text-blue-600 dark:text-blue-400' :
                            isCompleted ? 'text-foreground' :
                            'text-muted-foreground'
                          }`}>
                            {phase.label}
                          </span>
                          {isActive && (
                            <Badge variant="secondary" className="text-xs">
                              In Progress
                            </Badge>
                          )}
                        </div>
                        
                        {/* Show progress details for active phase */}
                        {isActive && progress?.current !== undefined && progress?.total !== undefined && progress.total > 0 && (
                          <div className="mt-2 space-y-1">
                            <Progress 
                              value={(progress.current / progress.total) * 100} 
                              className="h-1.5 w-48" 
                            />
                            <p className="text-xs text-muted-foreground">
                              {progress.current} / {progress.total} items
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Live Log Section - Show for all job types that emit SSE progress events */}
      {(job.job_type === 'canonical_env_sync' ||
        job.job_type === 'environment_sync' ||
        job.job_type === 'github_sync_to' ||
        job.job_type === 'github_sync_from' ||
        job.job_type === 'promotion_execute' ||
        job.job_type === 'restore_execute' ||
        job.job_type === 'snapshot_restore' ||
        job.job_type === 'dev_git_sync') && (
        <Card>
          <Collapsible open={isLogOpen} onOpenChange={setIsLogOpen}>
            <CardHeader className="pb-2">
              <CollapsibleTrigger asChild>
                <div className="flex items-center justify-between cursor-pointer hover:bg-muted/50 -mx-4 -my-2 px-4 py-2 rounded-lg transition-colors">
                  <div className="flex items-center gap-2">
                    <Terminal className="h-5 w-5" />
                    <CardTitle>Live Log</CardTitle>
                    {(job.status === 'running' || job.status === 'pending') && (
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                      </span>
                    )}
                    <Badge variant="outline" className="text-xs ml-2">
                      {logMessages.length} entries
                    </Badge>
                  </div>
                  {isLogOpen ? (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              </CollapsibleTrigger>
              <CardDescription>Real-time operation log</CardDescription>
            </CardHeader>
            <CollapsibleContent>
              <CardContent className="pt-2">
                <div 
                  ref={logContainerRef}
                  className="bg-zinc-950 text-zinc-100 rounded-lg p-4 font-mono text-xs overflow-auto max-h-80 min-h-32"
                >
                  {logMessages.length === 0 ? (
                    <div className="text-zinc-500 italic">
                      {(job.status === 'running' || job.status === 'pending')
                        ? 'Connecting to live updates...'
                        : 'No log messages captured for this job.'}
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {logMessages.map((log, idx) => {
                        const time = new Date(log.timestamp).toLocaleTimeString();
                        const levelColor = {
                          info: 'text-blue-400',
                          warn: 'text-yellow-400',
                          error: 'text-red-400',
                          debug: 'text-zinc-500',
                        }[log.level] || 'text-zinc-400';
                        
                        const phaseColor = {
                          discovering_workflows: 'text-purple-400',
                          updating_environment_state: 'text-cyan-400',
                          reconciling_drift: 'text-orange-400',
                          persisting_to_git: 'text-green-400',
                          finalizing_sync: 'text-emerald-400',
                          backup: 'text-blue-400',
                          restore: 'text-amber-400',
                        }[log.phase || ''] || 'text-zinc-500';
                        
                        return (
                          <div key={idx} className="flex gap-2 leading-5">
                            <span className="text-zinc-500 shrink-0">{time}</span>
                            <span className={`shrink-0 uppercase ${levelColor}`}>
                              [{log.level}]
                            </span>
                            {log.phase && (
                              <span className={`shrink-0 ${phaseColor}`}>
                                [{log.phase.replace(/_/g, ' ')}]
                              </span>
                            )}
                            <span className="text-zinc-200 break-all">{log.message}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
                {logMessages.length > 0 && (
                  <div className="flex justify-end mt-2">
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={() => setLogMessages([])}
                      className="text-xs text-muted-foreground"
                    >
                      Clear log
                    </Button>
                  </div>
                )}
              </CardContent>
            </CollapsibleContent>
          </Collapsible>
        </Card>
      )}

      {/* Results - Only show if not already shown in completion summary */}
      {job.status === 'completed' && result && Object.keys(result).length > 0 && !result.completion_summary && (
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

