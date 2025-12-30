// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { apiClient } from '@/lib/api-client';
import { api } from '@/lib/api';
import { useBackgroundJobsSSE } from '@/lib/use-background-jobs-sse';
import { 
  ArrowLeft, 
  Server, 
  RefreshCw, 
  Edit, 
  Trash2, 
  Database, 
  Download, 
  RotateCcw,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Activity,
  Workflow,
  Calendar,
  ExternalLink,
  GitBranch
} from 'lucide-react';
import { useState, useEffect } from 'react';
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
import { Progress } from '@/components/ui/progress';
import type { Environment } from '@/types';

export function EnvironmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [backupDialogOpen, setBackupDialogOpen] = useState(false);
  const [downloadDialogOpen, setDownloadDialogOpen] = useState(false);
  const [forceBackup, setForceBackup] = useState(false);
  const [editingEnv, setEditingEnv] = useState<Environment | null>(null);
  const [syncingEnvId, setSyncingEnvId] = useState<string | null>(null);
  const [testingInDialog, setTestingInDialog] = useState(false);
  const [testingGitInDialog, setTestingGitInDialog] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [activeJobs, setActiveJobs] = useState<Record<string, {
    jobId: string;
    jobType: 'sync' | 'backup' | 'restore';
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

  useEffect(() => {
    document.title = 'Environment Details - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  // Fetch environment details
  const { data: environmentData, isLoading, error } = useQuery({
    queryKey: ['environment', id],
    queryFn: () => apiClient.getEnvironment(id!),
    enabled: !!id,
  });

  const environment = environmentData?.data;

  // Fetch environment types
  const { data: environmentTypesData } = useQuery({
    queryKey: ['environment-types'],
    queryFn: () => apiClient.getEnvironmentTypes(),
  });

  const environmentTypes = (environmentTypesData?.data || []).filter((t) => t.isActive);

  // Subscribe to background job updates
  useBackgroundJobsSSE({
    enabled: !isLoading && !!id,
  });

  // Listen to SSE events and update active jobs
  useEffect(() => {
    const handleSSEEvent = (eventType: string) => (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data);
        const envId = payload.environmentId || payload.environment_id;
        
        if (envId === id) {
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
            }, 10000);
          }
        }
      } catch (error) {
        console.error('[SSE] Failed to parse event:', error, event.data);
      }
    };

    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4000/api/v1';
    const token = localStorage.getItem('auth_token');
    const url = token 
      ? `${baseUrl}/sse/stream?token=${encodeURIComponent(token)}`
      : `${baseUrl}/sse/stream`;
    
    const eventSource = new EventSource(url, { withCredentials: true });

    eventSource.addEventListener('sync.progress', handleSSEEvent('sync.progress'));
    eventSource.addEventListener('backup.progress', handleSSEEvent('backup.progress'));
    eventSource.addEventListener('restore.progress', handleSSEEvent('restore.progress'));

    return () => {
      eventSource.close();
    };
  }, [id]);

  // Fetch recent jobs for this environment
  const { data: jobsData } = useQuery({
    queryKey: ['environment-jobs', id],
    queryFn: async () => {
      if (!id) return [];
      const response = await apiClient.getEnvironmentJobs(id);
      return response.data || [];
    },
    enabled: !!id,
    refetchInterval: 5000,
  });

  const recentJobs = (jobsData || []).slice(0, 10);

  // Mutations
  const syncMutation = useMutation({
    mutationFn: (environmentId: string) => apiClient.syncEnvironment(environmentId),
    onSuccess: (result, environmentId) => {
      setSyncingEnvId(null);
      const { job_id, status, message } = result.data;
      
      if (job_id && status === 'running') {
        toast.success('Sync started in background');
        setActiveJobs((prev) => ({
          ...prev,
          [environmentId]: {
            jobId: job_id,
            jobType: 'sync',
            status: 'running',
            current: 0,
            total: 5,
            message: 'Starting sync...',
          },
        }));
      } else {
        toast.error(message || 'Failed to start sync');
      }

      queryClient.invalidateQueries({ queryKey: ['environment', id] });
      queryClient.invalidateQueries({ queryKey: ['environment-jobs', id] });
    },
    onError: (error: any) => {
      setSyncingEnvId(null);
      const message = error.response?.data?.detail || 'Failed to sync environment';
      toast.error(message);
    },
  });

  const backupMutation = useMutation({
    mutationFn: ({ environment, force }: { environment: Environment; force: boolean }) => 
      apiClient.syncWorkflowsToGithub(environment, force),
    onSuccess: (result) => {
      const { job_id, status, message } = result.data;
      
      if (job_id && status === 'running') {
        toast.success('Backup started in background');
        setActiveJobs((prev) => ({
          ...prev,
          [id!]: {
            jobId: job_id,
            jobType: 'backup',
            status: 'running',
            current: 0,
            total: 1,
            message: 'Starting backup...',
          },
        }));
        setBackupDialogOpen(false);
      } else {
        toast.error(message || 'Failed to start backup');
      }

      queryClient.invalidateQueries({ queryKey: ['environment-jobs', id] });
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to backup workflows';
      toast.error(message);
    },
  });

  const downloadMutation = useMutation({
    mutationFn: (env: Environment) => apiClient.downloadWorkflows(env),
    onSuccess: () => {
      toast.success('Download started');
      setDownloadDialogOpen(false);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to download workflows';
      toast.error(message);
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: {
      id: string;
      name: string;
      type?: string;
      base_url: string;
      api_key: string;
      allow_upload: boolean;
      git_repo_url?: string;
      git_branch?: string;
      git_pat?: string;
    }) => apiClient.updateEnvironment(data.id, {
      name: data.name,
      type: data.type,
      base_url: data.base_url,
      api_key: data.api_key,
      allow_upload: data.allow_upload,
      git_repo_url: data.git_repo_url,
      git_branch: data.git_branch,
      git_pat: data.git_pat,
    }),
    onSuccess: () => {
      toast.success('Environment updated successfully');
      queryClient.invalidateQueries({ queryKey: ['environment', id] });
      queryClient.invalidateQueries({ queryKey: ['environments'] });
      setEditingEnv(null);
      handleClose();
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to update environment';
      toast.error(message);
    },
  });

  const testMutation = useMutation({
    mutationFn: ({ baseUrl, apiKey }: { baseUrl: string; apiKey: string }) =>
      apiClient.testConnection({ baseUrl, apiKey }),
    onSuccess: (result) => {
      if (result.data.success) {
        toast.success(result.data.message);
        // Update last_connected timestamp if test succeeds
        queryClient.invalidateQueries({ queryKey: ['environment', id] });
      } else {
        toast.error(result.data.message);
      }
      setTestingInDialog(false);
      setTestingConnection(false);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.message || 'Connection test failed');
      setTestingInDialog(false);
      setTestingConnection(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (environmentId: string) => apiClient.deleteEnvironment(environmentId),
    onSuccess: () => {
      toast.success('Environment deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['environments'] });
      navigate('/environments');
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to delete environment';
      toast.error(message);
    },
  });

  const handleEdit = () => {
    if (!environment) return;
    setEditingEnv(environment);
    setFormData({
      name: environment.name,
      type: environment.type,
      baseUrl: environment.baseUrl,
      apiKey: environment.apiKey || '',
      allowUpload: environment.allowUpload ?? false,
      gitRepoUrl: environment.gitRepoUrl || '',
      gitBranch: environment.gitBranch || 'main',
      gitPat: environment.gitPat || '',
    });
  };

  const handleClose = () => {
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

  const handleSave = () => {
    if (!editingEnv) return;
    
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

    updateMutation.mutate({
      id: editingEnv.id,
      name: formData.name,
      type: formData.type,
      base_url: formData.baseUrl,
      api_key: formData.apiKey,
      allow_upload: formData.allowUpload,
      git_repo_url: formData.gitRepoUrl || undefined,
      git_branch: formData.gitBranch || undefined,
      git_pat: formData.gitPat || undefined,
    });
  };

  const handleTestInDialog = () => {
    if (formData.baseUrl && formData.apiKey) {
      setTestingInDialog(true);
      testMutation.mutate({ baseUrl: formData.baseUrl, apiKey: formData.apiKey });
    }
  };

  const handleTestConnection = () => {
    if (!environment?.baseUrl || !environment?.apiKey) {
      toast.error('Environment configuration is missing. Please edit the environment to add base URL and API key.');
      return;
    }
    setTestingConnection(true);
    testMutation.mutate({ baseUrl: environment.baseUrl, apiKey: environment.apiKey });
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

  const handleSync = () => {
    if (!id) return;
    if (activeJobs[id]?.status === 'running') {
      toast.info('Sync already in progress for this environment');
      return;
    }
    setSyncingEnvId(id);
    syncMutation.mutate(id);
  };

  const handleBackup = () => {
    if (!environment) return;
    setForceBackup(false);
    setBackupDialogOpen(true);
  };

  const handleBackupConfirm = () => {
    if (environment) {
      backupMutation.mutate({ environment, force: forceBackup });
    }
  };

  const handleDownload = () => {
    if (!environment) return;
    setDownloadDialogOpen(true);
  };

  const handleDownloadConfirm = () => {
    if (environment) {
      downloadMutation.mutate(environment);
    }
  };

  const handleDelete = () => {
    if (!id) return;
    deleteMutation.mutate(id);
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
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
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

  const formatRelativeTime = (dateString?: string) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
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
  };

  const getJobTypeLabel = (jobType: string) => {
    switch (jobType) {
      case 'environment_sync':
        return 'Environment Sync';
      case 'github_sync_to':
        return 'GitHub Backup';
      case 'github_sync_from':
        return 'GitHub Restore';
      default:
        return jobType;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !environment) {
    return (
      <div className="container mx-auto p-6">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-8">
              <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
              <h2 className="text-xl font-semibold mb-2">Environment not found</h2>
              <p className="text-muted-foreground mb-4">
                The environment you're looking for doesn't exist or you don't have access to it.
              </p>
              <Button onClick={() => navigate('/environments')} variant="outline">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Environments
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const activeJob = activeJobs[id || ''];

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/environments')}
            className="mt-1"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-4xl font-bold flex items-center gap-3 mb-2">
              <Server className="h-10 w-10" />
              {environment.name}
            </h1>
            <div className="flex items-center gap-2 mt-2">
              {environment.type && (
                <Badge variant="outline" className="text-sm">{environment.type}</Badge>
              )}
              {environment.provider && (
                <Badge variant="secondary" className="text-sm">{environment.provider}</Badge>
              )}
            </div>
            <div className="flex items-center gap-3 mt-2">
              <p className="text-sm text-muted-foreground">
                Last connected: {formatRelativeTime(environment.lastConnected)}
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleTestConnection}
                disabled={testingConnection}
                className="h-7"
              >
                <RefreshCw className={`h-3 w-3 mr-1 ${testingConnection ? 'animate-spin' : ''}`} />
                {testingConnection ? 'Testing...' : 'Test Connection'}
              </Button>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handleSync}
            disabled={syncingEnvId === id || activeJob?.status === 'running'}
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${syncingEnvId === id || activeJob?.status === 'running' ? 'animate-spin' : ''}`}
            />
            Sync
          </Button>
          <Button
            variant="outline"
            onClick={handleBackup}
            disabled={activeJob?.jobType === 'backup' && activeJob?.status === 'running'}
          >
            <Database className={`h-4 w-4 mr-2 ${activeJob?.jobType === 'backup' && activeJob?.status === 'running' ? 'animate-spin' : ''}`} />
            Backup
          </Button>
          <Button
            variant="outline"
            onClick={() => navigate(`/environments/${id}/restore`)}
          >
            <RotateCcw className="h-4 w-4 mr-2" />
            Restore
          </Button>
          <Button
            variant="outline"
            onClick={handleDownload}
          >
            <Download className="h-4 w-4 mr-2" />
            Download
          </Button>
          <Button
            variant="outline"
            onClick={handleEdit}
          >
            <Edit className="h-4 w-4 mr-2" />
            Edit
          </Button>
          <Button
            variant="outline"
            onClick={() => setDeleteDialogOpen(true)}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>

      {/* Active Job Status */}
      {activeJob && (
        <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-950/30">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                {getStatusIcon(activeJob.status)}
                {activeJob.jobType === 'sync' ? 'Environment Sync' : 
                 activeJob.jobType === 'backup' ? 'GitHub Backup' : 
                 'GitHub Restore'}
              </CardTitle>
              <Badge variant={getStatusVariant(activeJob.status)}>{activeJob.status}</Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {activeJob.status === 'running' && (
              <>
                {activeJob.currentStep && (
                  <p className="text-sm text-muted-foreground">
                    Current step: <span className="font-medium">{activeJob.currentStep}</span>
                  </p>
                )}
                {activeJob.message && <p className="text-sm text-muted-foreground">{activeJob.message}</p>}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span>Progress</span>
                    <span>
                      {activeJob.current} / {activeJob.total} ({Math.round((activeJob.current / activeJob.total) * 100)}%)
                    </span>
                  </div>
                  <Progress value={(activeJob.current / activeJob.total) * 100} className="h-2" />
                </div>
                <Link
                  to={`/activity?job_id=${activeJob.jobId}`}
                  className="text-sm text-primary hover:underline"
                >
                  View full details in Activity Center →
                </Link>
              </>
            )}
            {activeJob.status === 'completed' && (
              <p className="text-sm text-green-600 dark:text-green-400">
                {activeJob.message || 'Job completed successfully'}
              </p>
            )}
            {activeJob.status === 'failed' && (
              <div className="space-y-2">
                <p className="text-sm text-red-600 dark:text-red-400">
                  {activeJob.message || 'Job failed'}
                </p>
                {activeJob.errors && (
                  <p className="text-xs text-muted-foreground">
                    {JSON.stringify(activeJob.errors, null, 2)}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Workflows</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Workflow className="h-5 w-5 text-muted-foreground" />
              <span className="text-2xl font-bold">{environment.workflowCount || 0}</span>
            </div>
            <Link
              to={`/workflows?environment=${id}`}
              className="text-xs text-primary hover:underline mt-1 block"
            >
              View workflows →
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Last Sync</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm font-medium">
                {formatRelativeTime(environment.lastConnected)}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Last Backup</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm font-medium">
                {formatRelativeTime(environment.lastBackup)}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Configuration */}
        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
            <CardDescription>Environment settings and Git repository</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {environment.gitRepoUrl ? (
              <>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Git Repository</label>
                  <div className="flex items-center gap-2 mt-1">
                    <GitBranch className="h-4 w-4 text-muted-foreground" />
                    <a
                      href={environment.gitRepoUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-primary hover:underline flex items-center gap-1"
                    >
                      {environment.gitRepoUrl}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Branch: {environment.gitBranch || 'main'}
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">No Git repository configured</p>
            )}
            <div>
              <label className="text-sm font-medium text-muted-foreground">Status</label>
              <div className="flex flex-wrap gap-2 mt-2">
                <Badge variant={environment.isActive ? 'default' : 'outline'}>
                  {environment.isActive ? 'Active' : 'Inactive'}
                </Badge>
                <Badge variant={environment.allowUpload ? 'default' : 'outline'}>
                  {environment.allowUpload ? 'Upload Enabled' : 'Upload Disabled'}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Background jobs and operations</CardDescription>
          </CardHeader>
          <CardContent>
            {recentJobs.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No recent activity
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Progress</TableHead>
                    <TableHead>Time</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentJobs.map((job: any) => (
                    <TableRow key={job.id}>
                      <TableCell className="font-medium">
                        {getJobTypeLabel(job.job_type)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={getStatusVariant(job.status)} className="flex items-center gap-1 w-fit">
                          {getStatusIcon(job.status)}
                          {job.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {job.progress ? (
                          <div className="text-sm">
                            {job.progress.current} / {job.progress.total} ({job.progress.percentage}%)
                          </div>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatRelativeTime(job.created_at)}
                      </TableCell>
                      <TableCell>
                        <Link
                          to={`/activity?job_id=${job.id}`}
                          className="text-sm text-primary hover:underline"
                        >
                          View
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <div className="mt-4">
              <Link to="/activity">
                <Button variant="outline" size="sm" className="w-full">
                  <Activity className="h-4 w-4 mr-2" />
                  View All Activity
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Edit Environment Dialog */}
      <Dialog open={!!editingEnv} onOpenChange={(open) => !open && handleClose()}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Environment</DialogTitle>
            <DialogDescription>
              Update your n8n instance connection details
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
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Backup Confirmation Dialog */}
      <Dialog open={backupDialogOpen} onOpenChange={setBackupDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Backup Workflows to GitHub</DialogTitle>
            <DialogDescription>
              This will push workflows from {environment.name} environment to your configured GitHub repository.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <p className="text-sm text-muted-foreground">
              By default, only workflows changed since the last backup will be pushed.
            </p>
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="forceBackup"
                checked={forceBackup}
                onChange={(e) => setForceBackup(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
              <Label htmlFor="forceBackup" className="cursor-pointer text-sm">
                Force full backup (re-upload all workflows)
              </Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBackupDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleBackupConfirm}
              disabled={backupMutation.isPending}
            >
              {backupMutation.isPending ? 'Backing up...' : 'Backup'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Download Confirmation Dialog */}
      <Dialog open={downloadDialogOpen} onOpenChange={setDownloadDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Download All Workflows</DialogTitle>
            <DialogDescription>
              This will download all workflows from {environment.name} environment as a ZIP file.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-muted-foreground">
              Are you sure you want to download all workflows?
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDownloadDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleDownloadConfirm}
              disabled={downloadMutation.isPending}
            >
              {downloadMutation.isPending ? 'Downloading...' : 'Yes, Download'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Environment</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{environment.name}</strong>? This action cannot be undone.
              All workflows, executions, and credentials associated with this environment will be removed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
