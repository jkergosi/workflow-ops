// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { api } from '@/lib/api';
import { apiClient } from '@/lib/api-client';
import { useAppStore } from '@/store/use-app-store';
import { useAuth } from '@/lib/auth';
import { cn, getErrorMessage } from '@/lib/utils';
import { Plus, Server, RefreshCw, Edit, RefreshCcw, CheckCircle2, AlertCircle, Loader2, XCircle, MoreVertical, Clock } from 'lucide-react';
import { toast } from 'sonner';
import type { Environment, EnvironmentType, EnvironmentTypeConfig } from '@/types';
import { useFeatures } from '@/lib/features';
import { useEffect } from 'react';
import { useBackgroundJobsSSE } from '@/lib/use-background-jobs-sse';
import { SmartEmptyState } from '@/components/SmartEmptyState';
import { useEnvironmentTypes, getEnvironmentTypeLabel } from '@/hooks/useEnvironmentTypes';

export function EnvironmentsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { refreshEntitlements } = useAuth();
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);
  const [editingEnv, setEditingEnv] = useState<Environment | null>(null);
  const [isAddMode, setIsAddMode] = useState(false);
  
  // Refresh entitlements on mount to ensure we have latest values
  useEffect(() => {
    refreshEntitlements();
  }, [refreshEntitlements]);

  useEffect(() => {
    document.title = 'Environments - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);
  const [testingInDialog, setTestingInDialog] = useState(false);
  const [syncConfirmDialogOpen, setSyncConfirmDialogOpen] = useState(false);

  const { environmentTypes } = useEnvironmentTypes();
  const [selectedEnvForAction, setSelectedEnvForAction] = useState<Environment | null>(null);
  const [syncingEnvId, setSyncingEnvId] = useState<string | null>(null);
  const [activeJobs, setActiveJobs] = useState<Record<string, {
    jobId: string;
    jobType: 'sync';
    status: 'running' | 'completed' | 'failed';
    currentStep?: string;
    current: number;
    total: number;
    message?: string;
    currentWorkflowName?: string;
    errors?: any;
  }>>({});
  const [formData, setFormData] = useState<{
    name: string;
    type?: string;
    baseUrl: string;
    apiKey: string;
    allowUpload: boolean;
    gitRepoUrl: string;
    gitBranch: string;
    gitPat: string;
  }>({
    name: '',
    type: undefined,
    baseUrl: '',
    apiKey: '',
    allowUpload: true,
    gitRepoUrl: '',
    gitBranch: 'main',
    gitPat: '',
  });
  const [testingGitInDialog, setTestingGitInDialog] = useState(false);

  const { data: environments, isLoading, error, refetch } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.getEnvironments(),
    retry: (failureCount, error) => {
      // Don't retry on 503 - service is down
      if ((error as any)?.response?.status === 503) return false;
      return failureCount < 2;
    },
    keepPreviousData: true, // Cached data fallback
  });

  // Fetch environment health data for status and drift
  const { data: healthData } = useQuery({
    queryKey: ['environment-health'],
    queryFn: () => apiClient.getEnvironmentHealthData(),
    enabled: !isLoading && !!environments?.data?.length,
  });

  // Subscribe to background job updates for all environments
  useBackgroundJobsSSE({
    enabled: !isLoading && !!environments?.data?.length,
  });

  // Fetch active jobs for each environment
  const environmentIds = environments?.data?.map((e: Environment) => e.id) || [];
  const jobsQueries = useQuery({
    queryKey: ['environment-jobs', environmentIds],
    queryFn: async () => {
      const jobsMap: Record<string, any> = {};
      for (const envId of environmentIds) {
        try {
          const jobs = await apiClient.getEnvironmentJobs(envId);
          const runningJob = jobs.data?.find((j: any) => 
            j.status === 'running' || j.status === 'pending'
          );
          if (runningJob && runningJob.job_type === 'environment_sync') {
            jobsMap[envId] = {
              jobId: runningJob.id,
              jobType: 'sync',
              status: runningJob.status === 'pending' ? 'running' : runningJob.status,
              current: runningJob.progress?.current || 0,
              total: runningJob.progress?.total || 1,
              message: runningJob.progress?.message,
              currentStep: runningJob.progress?.currentStep,
            };
          }
        } catch (error) {
          // Ignore errors for individual environment job fetches
        }
      }
      return jobsMap;
    },
    enabled: environmentIds.length > 0,
    refetchInterval: 10000, // Poll every 10 seconds as fallback
  });

  // Update active jobs when queries update
  useEffect(() => {
    if (jobsQueries.data) {
      setActiveJobs((prev) => {
        // Merge with existing to preserve SSE updates
        return { ...prev, ...jobsQueries.data };
      });
    }
  }, [jobsQueries.data]);

  // Listen to SSE events and update active jobs
  useEffect(() => {
    const handleSSEEvent = (eventType: string) => (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data);
        const envId = payload.environmentId || payload.environment_id;
        
        if (envId) {
          console.log('[SSE] Received event:', eventType, payload);
          setActiveJobs((prev) => ({
            ...prev,
            [envId]: {
              jobId: payload.jobId || payload.job_id,
              jobType: eventType === 'sync.progress' ? 'sync' : 
                       eventType === 'backup.progress' ? 'backup' : 'restore',
              status: payload.status || 'running',
              currentStep: payload.currentStep || payload.current_step,
              current: payload.current || 0,
              total: payload.total || 1,
              message: payload.message,
              currentWorkflowName: payload.currentWorkflowName || payload.current_workflow_name,
              errors: payload.errors,
            },
          }));

          // Remove from active jobs if completed or failed (after a delay)
          if (payload.status === 'completed' || payload.status === 'failed') {
            setTimeout(() => {
              setActiveJobs((prev) => {
                const next = { ...prev };
                delete next[envId];
                return next;
              });
            }, 10000); // Keep for 10 seconds to show completion message
          }
        }
      } catch (error) {
        console.error('[SSE] Failed to parse event:', error, event.data);
      }
    };

    // Create EventSource connection for background jobs
    // EventSource can't send custom headers, so we pass token as query parameter
    // VITE_API_BASE_URL already includes /api/v1, so we just add /sse/stream
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
    const token = localStorage.getItem('auth_token');
    const url = token 
      ? `${baseUrl}/sse/stream?token=${encodeURIComponent(token)}`
      : `${baseUrl}/sse/stream`;
    console.log('[SSE] Connecting to background jobs stream:', url.replace(token || '', '***'));
    
    const eventSource = new EventSource(url, { withCredentials: true });

    eventSource.onopen = () => {
      console.log('[SSE] Connected to background jobs stream');
    };

    eventSource.onerror = (error) => {
      console.error('[SSE] Connection error:', error);
      console.error('[SSE] EventSource readyState:', eventSource.readyState);
      // readyState: 0 = CONNECTING, 1 = OPEN, 2 = CLOSED
    };

    eventSource.addEventListener('sync.progress', handleSSEEvent('sync.progress'));
    eventSource.addEventListener('backup.progress', handleSSEEvent('backup.progress'));
    eventSource.addEventListener('restore.progress', handleSSEEvent('restore.progress'));

    // Also listen for generic 'message' events as fallback
    eventSource.onmessage = (event) => {
      console.log('[SSE] Received message event:', event);
    };

    return () => {
      console.log('[SSE] Closing background jobs stream');
      eventSource.close();
    };
  }, []);

  const testMutation = useMutation({
    mutationFn: ({ baseUrl, apiKey }: { baseUrl: string; apiKey: string }) =>
      api.testEnvironmentConnection(baseUrl, apiKey),
    onSuccess: (result) => {
      if (result.data.success) {
        toast.success('Connection test successful', {
          icon: <CheckCircle2 className="h-5 w-5" />,
        });
      } else {
        toast.error(result.data.message || 'Connection test failed', {
          icon: <AlertCircle className="h-5 w-5" />,
        });
      }
    },
    onError: () => {
      toast.error('Connection test failed', {
        icon: <AlertCircle className="h-5 w-5" />,
      });
    },
    onSettled: () => {
      setTestingInDialog(false);
    },
  });


  const updateMutation = useMutation({
    mutationFn: (data: { id: string; updates: { name?: string; type?: string; base_url?: string; api_key?: string; git_repo_url?: string; git_branch?: string; git_pat?: string } }) =>
      api.updateEnvironment(data.id, data.updates),
    onSuccess: () => {
      toast.success('Environment updated successfully');
      queryClient.invalidateQueries({ queryKey: ['environments'] });
      handleClose();
    },
    onError: (error: any) => {
      toast.error(getErrorMessage(error, 'Failed to update environment'));
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: { name: string; type: any; base_url: string; api_key: string; git_repo_url?: string; git_branch?: string; git_pat?: string }) =>
      api.createEnvironment(data),
    onSuccess: () => {
      toast.success('Environment created successfully');
      queryClient.invalidateQueries({ queryKey: ['environments'] });
      handleClose();
    },
    onError: (error: any) => {
      toast.error(getErrorMessage(error, 'Failed to create environment'));
    },
  });

  const syncMutation = useMutation({
    mutationFn: (environmentId: string) => api.syncEnvironment(environmentId),
    onSuccess: (result, environmentId) => {
      setSyncingEnvId(null);
      const { job_id, status, message } = result.data;

      // Accept both 'pending' and 'running' as valid statuses
      if (job_id && (status === 'running' || status === 'pending')) {
        toast.success('Sync started in background');
        // Job progress will be updated via SSE
        setActiveJobs((prev) => ({
          ...prev,
          [environmentId]: {
            jobId: job_id,
            jobType: 'sync',
            status: 'running', // Always set to 'running' for UI consistency
            current: 0,
            total: 5, // workflows, executions, credentials, users, tags
            message: 'Starting sync...',
          },
        }));
      } else {
        toast.error(message || 'Failed to start sync');
      }

      queryClient.invalidateQueries({ queryKey: ['environments'] });
    },
    onError: (error: any) => {
      setSyncingEnvId(null);
      toast.error(getErrorMessage(error, 'Failed to sync environment'));
    },
  });

  const handleEdit = (env: Environment) => {
    setIsAddMode(false);
    setEditingEnv(env);
    setFormData({
      name: env.name,
      type: env.type,
      baseUrl: env.baseUrl,
      apiKey: env.apiKey || '',
      allowUpload: env.allowUpload ?? false,
      gitRepoUrl: env.gitRepoUrl || '',
      gitBranch: env.gitBranch || 'main',
      gitPat: env.gitPat || '',
    });
  };

  const handleAddClick = () => {
    setIsAddMode(true);
    setEditingEnv(null);
    setFormData({
      name: '',
      type: undefined,
      baseUrl: '',
      apiKey: '',
      allowUpload: true,
      gitRepoUrl: '',
      gitBranch: 'main',
      gitPat: '',
    });
  };

  const handleClose = () => {
    setEditingEnv(null);
    setIsAddMode(false);
    setFormData({
      name: '',
      type: undefined,
      baseUrl: '',
      apiKey: '',
      allowUpload: true,
      gitRepoUrl: '',
      gitBranch: 'main',
      gitPat: '',
    });
  };

  const handleTestInDialog = () => {
    if (formData.baseUrl && formData.apiKey) {
      setTestingInDialog(true);
      testMutation.mutate({ baseUrl: formData.baseUrl, apiKey: formData.apiKey });
    }
  };

  const handleTestGitInDialog = async () => {
    if (!formData.gitRepoUrl) {
      toast.error('Git Repository URL is required');
      return;
    }

    setTestingGitInDialog(true);
    try {
      const result = await api.testGitConnection({
        gitRepoUrl: formData.gitRepoUrl,
        gitBranch: formData.gitBranch || 'main',
        gitPat: formData.gitPat || undefined,
      });

      if (result.data.success) {
        toast.success(result.data.message);
      } else {
        toast.error(result.data.message);
      }
    } catch (error: any) {
      toast.error(error.response?.data?.message || 'Failed to test Git connection');
    } finally {
      setTestingGitInDialog(false);
    }
  };

  const handleBackupClick = (env: Environment) => {
    setSelectedEnvForAction(env);
    setForceBackup(false);
    setBackupDialogOpen(true);
  };

  const handleBackupConfirm = () => {
    if (selectedEnvForAction) {
      backupMutation.mutate({ environment: selectedEnvForAction.id, force: forceBackup });
    }
  };

  const handleDownloadClick = (env: Environment) => {
    setSelectedEnvForAction(env);
    setDownloadDialogOpen(true);
  };

  const handleDownloadConfirm = () => {
    if (selectedEnvForAction) {
      downloadMutation.mutate(selectedEnvForAction);
    }
  };

  const handleDeleteClick = (env: Environment) => {
    setSelectedEnvForAction(env);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (selectedEnvForAction) {
      deleteMutation.mutate(selectedEnvForAction.id);
    }
  };

  const handleSyncClick = (env: Environment) => {
    // Check if there's already an active job
    if (activeJobs[env.id]?.status === 'running') {
      toast.info('Sync already in progress for this environment');
      return;
    }
    setSelectedEnvForAction(env);
    setSyncConfirmDialogOpen(true);
  };

  const handleSyncConfirm = () => {
    if (selectedEnvForAction) {
      setSyncingEnvId(selectedEnvForAction.id);
      syncMutation.mutate(selectedEnvForAction.id);
      setSyncConfirmDialogOpen(false);
      setSelectedEnvForAction(null);
    }
  };

  const handleSave = () => {
    // Validate form
    if (!formData.name.trim()) {
      toast.error('Environment name is required');
      return;
    }
    if (!formData.baseUrl.trim()) {
      toast.error('Base URL is required');
      return;
    }
    if (!formData.apiKey.trim()) {
      toast.error('API Key is required');
      return;
    }

    if (isAddMode) {
      // Create new environment
      createMutation.mutate({
        name: formData.name,
        type: formData.type,
        base_url: formData.baseUrl,
        api_key: formData.apiKey,
        allow_upload: formData.allowUpload,
        git_repo_url: formData.gitRepoUrl || undefined,
        git_branch: formData.gitBranch || undefined,
        git_pat: formData.gitPat || undefined,
      });
    } else if (editingEnv) {
      // Update existing environment
      updateMutation.mutate({
        id: editingEnv.id,
        updates: {
          name: formData.name,
          type: formData.type,
          base_url: formData.baseUrl,
          api_key: formData.apiKey,
          allow_upload: formData.allowUpload,
          git_repo_url: formData.gitRepoUrl || undefined,
          git_branch: formData.gitBranch || undefined,
          git_pat: formData.gitPat || undefined,
        },
      });
    }
  };


  // Helper function to format relative time (returns time without "ago" suffix)
  const formatRelativeTime = (dateString?: string): string => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m`;
    if (diffHours < 24) return `${diffHours}h`;
    if (diffDays < 7) return `${diffDays}d`;
    return date.toLocaleDateString();
  };

  // Helper function to get environment status
  const getEnvironmentStatus = (env: Environment): { status: 'connected' | 'degraded' | 'disconnected'; lastHeartbeat?: string } => {
    // STATUS = connectivity from heartbeat only
    if (!env.lastHeartbeatAt) {
      return { status: 'disconnected' };
    }

    const lastHeartbeat = new Date(env.lastHeartbeatAt);
    const now = new Date();
    const diffMins = Math.floor((now.getTime() - lastHeartbeat.getTime()) / 60000);

    // Compute enum:
    // - connected if now - lastHeartbeatAt <= 5 minutes
    // - degraded if 5 minutes < age <= 60 minutes
    // - disconnected if age > 60 minutes OR lastHeartbeatAt is null
    if (diffMins <= 5) {
      return { status: 'connected', lastHeartbeat: env.lastHeartbeatAt };
    } else if (diffMins <= 60) {
      return { status: 'degraded', lastHeartbeat: env.lastHeartbeatAt };
    } else {
      return { status: 'disconnected', lastHeartbeat: env.lastHeartbeatAt };
    }
  };

  // Helper function to get state badge info (STATE = drift/tracking status only)
  const getStateBadgeInfo = (env: Environment): {
    status: 'in_sync' | 'drift_detected' | 'untracked' | 'unknown' | 'error';
    label: string;
    variant: 'default' | 'secondary' | 'destructive' | 'outline';
    tooltip: string;
  } => {
    // Use case-insensitive comparison for drift_status
    const driftStatus = (env.driftStatus || 'UNKNOWN').toUpperCase();

    switch (driftStatus) {
      case 'IN_SYNC':
        return {
          status: 'in_sync',
          label: 'In Sync',
          variant: 'default',
          tooltip: 'This environment matches the canonical Git version.',
        };
      case 'DRIFT_DETECTED':
        return {
          status: 'drift_detected',
          label: 'Drift Detected',
          variant: 'destructive',
          tooltip: 'This environment differs from the canonical Git version.',
        };
      case 'UNTRACKED':
        return {
          status: 'untracked',
          label: 'Untracked',
          variant: 'outline',
          tooltip: 'No workflows are linked/tracked for this environment.',
        };
      case 'ERROR':
        return {
          status: 'error',
          label: 'Error',
          variant: 'secondary',
          tooltip: 'An error occurred while checking state.',
        };
      default:
        return {
          status: 'unknown',
          label: 'Unknown',
          variant: 'outline',
          tooltip: 'State has not been checked yet.',
        };
    }
  };

  // Use the new features system for limits
  const { features, planName } = useFeatures();
  const environmentCount = environments?.data?.length || 0;
  const maxEnvironments = features?.max_environments;
  const atLimit = maxEnvironments !== 'unlimited' && environmentCount >= (maxEnvironments || 1);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Environments</h1>
          <p className="text-muted-foreground">
            Manage and monitor connected workflow environments
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Environment count indicator */}
          {maxEnvironments !== 'unlimited' && (
            <div className="text-sm text-muted-foreground">
              {environmentCount} / {maxEnvironments} environments
            </div>
          )}
          <Button onClick={handleAddClick} disabled={atLimit}>
            <Plus className="h-4 w-4 mr-2" />
            Add Environment
          </Button>
        </div>
      </div>


      {/* Show SmartEmptyState for service errors */}
      {error && !isLoading && !environments?.data && (
        <SmartEmptyState
          title="Unable to load environments"
          error={error as Error}
          isLoading={isLoading}
          onRetry={refetch}
        />
      )}

      {!error && (
        <Card>
          <CardContent className="p-0">
            {isLoading && !environments?.data ? (
              <div className="text-center py-8">Loading environments...</div>
            ) : (
              <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Environment</TableHead>
                  <TableHead>Status</TableHead>
                  {planName?.toLowerCase() !== 'free' && <TableHead>State</TableHead>}
                  <TableHead>Workflows</TableHead>
                  <TableHead>Last Sync</TableHead>
                  <TableHead className="sticky right-0 bg-background">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {environments?.data?.map((env) => {
                  const envStatus = getEnvironmentStatus(env);
                  const stateBadge = getStateBadgeInfo(env);
                  const isProduction = env.type?.toLowerCase() === 'production';
                  
                  return (
                    <TableRow
                      key={env.id}
                      className={cn(
                        isProduction && 'border-l-4 border-l-red-500'
                      )}
                    >
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <Server className="h-4 w-4" />
                          <Link
                            to={`/environments/${env.id}`}
                            className="text-primary hover:underline"
                          >
                            {env.name}
                          </Link>
                          {env.type && (
                            <Badge
                              variant={isProduction ? 'destructive' : env.type.toLowerCase() === 'staging' ? 'secondary' : 'outline'}
                              className="ml-1"
                            >
                              {getEnvironmentTypeLabel(environmentTypes, env.type)}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-0.5">
                          <Badge 
                            variant={
                              envStatus.status === 'connected' ? 'default' : 
                              envStatus.status === 'degraded' ? 'secondary' : 
                              'destructive'
                            }
                            className="text-xs"
                          >
                            {envStatus.status === 'connected' ? 'Connected' : 
                             envStatus.status === 'degraded' ? 'Degraded' : 
                             'Disconnected'}
                          </Badge>
                          {envStatus.lastHeartbeat && (
                            <p className="text-xs text-muted-foreground">
                              Last heartbeat: {formatRelativeTime(envStatus.lastHeartbeat)} ago
                            </p>
                          )}
                        </div>
                      </TableCell>
                      {planName?.toLowerCase() !== 'free' && (
                        <TableCell>
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Link to={`/environments/${env.id}#drift`}>
                                  <Badge
                                    variant={stateBadge.variant}
                                    className="text-xs cursor-pointer hover:opacity-80"
                                  >
                                    {stateBadge.label}
                                  </Badge>
                                </Link>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>{stateBadge.tooltip}</p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                          {env.lastDriftCheckAt && (
                            <p className="text-xs text-muted-foreground mt-0.5">
                              Checked {formatRelativeTime(env.lastDriftCheckAt)} ago
                            </p>
                          )}
                        </TableCell>
                      )}
                      <TableCell>
                        <Link
                          to={`/environments/${env.id}`}
                          className="text-primary hover:underline font-medium"
                        >
                          {env.workflowCount || 0}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="text-sm text-muted-foreground cursor-help">
                                {env.lastSyncAt ? `${formatRelativeTime(env.lastSyncAt)} ago` : 'Never'}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>{env.lastSyncAt ? new Date(env.lastSyncAt).toLocaleString() : 'Never synced'}</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </TableCell>
                      <TableCell className="sticky right-0 bg-background">
                        <div className="flex gap-2 items-center">
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleSyncClick(env)}
                                  disabled={syncingEnvId === env.id || activeJobs[env.id]?.status === 'running'}
                                >
                                  <RefreshCcw
                                    className={`h-3 w-3 mr-1 ${syncingEnvId === env.id || activeJobs[env.id]?.status === 'running' ? 'animate-spin' : ''}`}
                                  />
                                  Sync
                                </Button>
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>
                                  {env.environmentClass?.toLowerCase() === 'dev'
                                    ? 'Sync captures current dev workflows and commits them to Git.'
                                    : 'Sync checks this environment against the canonical Git version.'}
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button size="sm" variant="ghost" className="h-8 w-8 p-0">
                                <MoreVertical className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => handleEdit(env)}>
                                <Edit className="h-4 w-4 mr-2" />
                                Edit environment
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                          {activeJobs[env.id] && (
                            <Link
                              to={`/activity/${activeJobs[env.id].jobId}`}
                              className="ml-2"
                            >
                              <Badge
                                variant={activeJobs[env.id].status === 'running' ? 'secondary' : activeJobs[env.id].status === 'completed' ? 'default' : 'destructive'}
                                className="flex items-center gap-1 cursor-pointer hover:opacity-80"
                              >
                                {activeJobs[env.id].status === 'running' && (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                )}
                                {activeJobs[env.id].status === 'completed' && (
                                  <CheckCircle2 className="h-3 w-3" />
                                )}
                                {activeJobs[env.id].status === 'failed' && (
                                  <XCircle className="h-3 w-3" />
                                )}
                                Syncing
                                {activeJobs[env.id].current > 0 && activeJobs[env.id].total > 0 && (
                                  <span className="text-xs">
                                    ({activeJobs[env.id].current}/{activeJobs[env.id].total})
                                  </span>
                                )}
                              </Badge>
                            </Link>
                          )}
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
      )}

      {/* Add/Edit Environment Dialog */}
      <Dialog open={!!editingEnv || isAddMode} onOpenChange={(open) => !open && handleClose()}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{isAddMode ? 'Add Environment' : 'Edit Environment'}</DialogTitle>
            <DialogDescription>
              {isAddMode
                ? 'Add a new n8n instance connection'
                : 'Update your n8n instance connection details'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Basic Fields */}
            <div className="space-y-2">
              <Label htmlFor="name">Environment Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Production"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="type">Type (Optional)</Label>
              <Select
                value={(formData.type as string) || '__none__'}
                onValueChange={(v) => setFormData({ ...formData, type: v === '__none__' ? undefined : v })}
              >
                <SelectTrigger id="type">
                  <SelectValue placeholder="Select type (optional)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">None</SelectItem>
                  {environmentTypes.map((t) => (
                    <SelectItem key={t.id} value={t.key}>
                      {t.label}
                    </SelectItem>
                  ))}
                  {formData.type && !environmentTypes.some((t) => t.key === formData.type) && (
                    <SelectItem value={formData.type}>
                      {String(formData.type)} (Custom)
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Optional metadata for categorization and display. Not used for business logic.
              </p>
            </div>

            {/* Feature Flags */}
            <div className="space-y-3 p-4 border rounded-lg bg-muted/50">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="allowUpload"
                  checked={formData.allowUpload}
                  onChange={(e) =>
                    setFormData({ ...formData, allowUpload: e.target.checked })
                  }
                  className="h-4 w-4 rounded border-gray-300"
                />
                <Label htmlFor="allowUpload" className="cursor-pointer">
                  Allow Workflow Upload
                </Label>
              </div>
              <p className="text-xs text-muted-foreground ml-6">
                When enabled, workflows can be uploaded/backed up to GitHub from this environment.
              </p>
            </div>

            {/* n8n API Card */}
            <Card className="border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">n8n API</CardTitle>
                <CardDescription className="text-sm">
                  Connection details for your n8n instance
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="baseUrl">Base URL</Label>
                  <Input
                    id="baseUrl"
                    value={formData.baseUrl}
                    onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })}
                    placeholder="https://n8n.example.com"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="apiKey">API Key</Label>
                  <Input
                    id="apiKey"
                    type="password"
                    value={formData.apiKey}
                    onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                    placeholder="Enter API key"
                  />
                </div>

                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handleTestInDialog}
                  disabled={testingInDialog}
                >
                  <RefreshCw
                    className={`h-4 w-4 mr-2 ${testingInDialog ? 'animate-spin' : ''}`}
                  />
                  {testingInDialog ? 'Testing...' : 'Test Connection'}
                </Button>
              </CardContent>
            </Card>

            {/* Git API Card */}
            <Card className="border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-950/20">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Git API (Optional)</CardTitle>
                <CardDescription className="text-sm">
                  GitHub repository for workflow backup and sync
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="gitRepoUrl">Repository URL</Label>
                  <Input
                    id="gitRepoUrl"
                    value={formData.gitRepoUrl}
                    onChange={(e) => setFormData({ ...formData, gitRepoUrl: e.target.value })}
                    placeholder="https://github.com/owner/repo"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="gitBranch">Branch</Label>
                  <Input
                    id="gitBranch"
                    value={formData.gitBranch}
                    onChange={(e) => setFormData({ ...formData, gitBranch: e.target.value })}
                    placeholder="main"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="gitPat">Personal Access Token</Label>
                  <Input
                    id="gitPat"
                    type="password"
                    value={formData.gitPat}
                    onChange={(e) => setFormData({ ...formData, gitPat: e.target.value })}
                    placeholder="Enter PAT (optional)"
                  />
                </div>

                <Button
                  variant="outline"
                  className="w-full"
                  onClick={handleTestGitInDialog}
                  disabled={testingGitInDialog || !formData.gitRepoUrl}
                >
                  <RefreshCw
                    className={`h-4 w-4 mr-2 ${testingGitInDialog ? 'animate-spin' : ''}`}
                  />
                  {testingGitInDialog ? 'Testing...' : 'Test Git Connection'}
                </Button>
              </CardContent>
            </Card>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={updateMutation.isPending || createMutation.isPending}
            >
              {updateMutation.isPending || createMutation.isPending
                ? 'Saving...'
                : isAddMode
                  ? 'Add Environment'
                  : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Sync Confirmation Dialog */}
      <Dialog open={syncConfirmDialogOpen} onOpenChange={setSyncConfirmDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Sync Environment</DialogTitle>
            <DialogDescription>
              {selectedEnvForAction?.environmentClass?.toLowerCase() === 'dev'
                ? `Capture and commit changes from ${selectedEnvForAction?.name}`
                : `Check ${selectedEnvForAction?.name} against canonical Git version`}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-muted-foreground">
              {selectedEnvForAction?.environmentClass?.toLowerCase() === 'dev'
                ? 'This will pull the latest workflows from the n8n instance and commit any changes to Git. The sync will run in the background.'
                : 'This will pull the latest workflows from the n8n instance and compare against the canonical Git version. The sync will run in the background.'}
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setSyncConfirmDialogOpen(false);
              setSelectedEnvForAction(null);
            }}>
              Cancel
            </Button>
            <Button
              onClick={handleSyncConfirm}
              disabled={syncMutation.isPending}
            >
              {syncMutation.isPending ? 'Starting...' : 'Start Sync'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
