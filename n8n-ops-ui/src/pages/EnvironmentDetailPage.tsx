// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
import { useFeatures } from '@/lib/features';
import { useAuth } from '@/lib/auth';
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
  GitBranch,
  AlertTriangle,
  Shield,
  Settings,
  FileText,
  Key,
  History,
  Archive,
  Link as LinkIcon,
  Zap,
  Wifi,
  WifiOff,
  Info,
  Eye,
} from 'lucide-react';
import { useState, useEffect } from 'react';
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
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import type { Environment, Workflow as WorkflowType, Snapshot, Credential, EnvironmentTypeConfig } from '@/types';
import { useEnvironmentTypes, getEnvironmentTypeLabel } from '@/hooks/useEnvironmentTypes';

// Helper to determine connection status based on last connected time
function getConnectionStatus(lastConnected?: string): 'connected' | 'degraded' | 'offline' {
  if (!lastConnected) return 'offline';
  const lastConnectedDate = new Date(lastConnected);
  const now = new Date();
  const diffMs = now.getTime() - lastConnectedDate.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);

  if (diffHours < 1) return 'connected';
  if (diffHours < 24) return 'degraded';
  return 'offline';
}

// Helper to check if environment is production type
function isProductionEnvironment(type?: string): boolean {
  if (!type) return false;
  const prodTypes = ['production', 'prod', 'prd', 'live'];
  return prodTypes.includes(type.toLowerCase());
}

// Helper to check if environment is staging/prod for safety prompts
function requiresSafetyConfirmation(type?: string): boolean {
  if (!type) return false;
  const safetyTypes = ['production', 'prod', 'prd', 'live', 'staging', 'stg', 'stage', 'uat'];
  return safetyTypes.includes(type.toLowerCase());
}

export function EnvironmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { canUseFeature } = useFeatures();
  const { user } = useAuth();
  const { environmentTypes } = useEnvironmentTypes();

  // Dialog states
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [backupDialogOpen, setBackupDialogOpen] = useState(false);
  const [downloadDialogOpen, setDownloadDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  // Form states
  const [forceBackup, setForceBackup] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');

  // Loading states
  const [testingConnection, setTestingConnection] = useState(false);
  const [testingInDialog, setTestingInDialog] = useState(false);
  const [testingGitInDialog, setTestingGitInDialog] = useState(false);
  const [driftSummary, setDriftSummary] = useState<{
    totalWorkflows: number;
    inSync: number;
    withDrift: number;
    notInGit: number;
    affectedWorkflows: Array<{
      id: string;
      name: string;
      hasDrift: boolean;
      notInGit: boolean;
      driftType: string;
    }>;
  } | null>(null);

  // Active tab
  const [activeTab, setActiveTab] = useState('overview');

  const [driftHandlingMode, setDriftHandlingMode] = useState<'warn_only' | 'manual_override' | 'require_attestation'>('warn_only');

  // Active jobs tracking
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

  // Edit form data
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
    document.title = 'Environment Details - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  // Fetch environment details
  const { data: environmentData, isLoading, error } = useQuery({
    queryKey: ['environment', id],
    queryFn: () => apiClient.getEnvironment(id!),
    enabled: !!id,
  });

  const environment = environmentData?.data;

  // Sync drift handling mode from environment data
  useEffect(() => {
    if (!environment) return;
    const mode = (environment.driftHandlingMode || 'warn_only') as any;
    if (mode === 'warn_only' || mode === 'manual_override' || mode === 'require_attestation') {
      setDriftHandlingMode(mode);
    } else {
      setDriftHandlingMode('warn_only');
    }
  }, [environment?.id, environment?.driftHandlingMode]);

  // Fetch workflows for this environment
  const { data: workflowsData, isLoading: workflowsLoading } = useQuery({
    queryKey: ['workflows', id],
    queryFn: () => apiClient.getWorkflows(id!),
    enabled: !!id,
  });

  const workflows = workflowsData?.data || [];

  // Fetch snapshots for this environment
  const { data: snapshotsData, isLoading: snapshotsLoading } = useQuery({
    queryKey: ['snapshots', id],
    queryFn: () => apiClient.getSnapshots({ environmentId: id }),
    enabled: !!id,
  });

  const snapshots = snapshotsData?.data || [];

  // Fetch credentials for this environment
  const { data: credentialsData, isLoading: credentialsLoading } = useQuery({
    queryKey: ['credentials', id],
    queryFn: () => apiClient.getCredentials({ environmentId: id }),
    enabled: !!id,
  });

  const credentials = credentialsData?.data || [];

  // Fetch recent jobs for this environment
  const { data: jobsData } = useQuery({
    queryKey: ['environment-jobs', id],
    queryFn: async () => {
      if (!id) return [];
      const response = await apiClient.getEnvironmentJobs(id);
      // Handle different response formats
      const data = response?.data;
      if (Array.isArray(data)) return data;
      if (data?.jobs && Array.isArray(data.jobs)) return data.jobs;
      return [];
    },
    enabled: !!id,
    refetchInterval: 5000,
  });

  const recentJobs = Array.isArray(jobsData) ? jobsData.slice(0, 20) : [];

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
              // Refresh data
              queryClient.invalidateQueries({ queryKey: ['environment', id] });
              queryClient.invalidateQueries({ queryKey: ['environment-jobs', id] });
              queryClient.invalidateQueries({ queryKey: ['workflows', id] });
              queryClient.invalidateQueries({ queryKey: ['snapshots', id] });
            }, 10000);
          }
        }
      } catch (error) {
        console.error('[SSE] Failed to parse event:', error, event.data);
      }
    };

    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
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
  }, [id, queryClient]);

  // Mutations
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

  const syncMutation = useMutation({
    mutationFn: (environmentId: string) => apiClient.syncEnvironment(environmentId),
    onSuccess: (result, environmentId) => {
      const { job_id, status, message } = result.data;

      if (job_id && (status === 'running' || status === 'pending')) {
        toast.success('Sync started in background');
        setActiveJobs((prev) => ({
          ...prev,
          [environmentId]: {
            jobId: job_id,
            jobType: 'sync',
            status: 'running',
            current: 0,
            total: 1,
            message: 'Starting sync...',
          },
        }));
        queryClient.invalidateQueries({ queryKey: ['environment', id] });
        queryClient.invalidateQueries({ queryKey: ['environment-jobs', id] });
      } else {
        toast.error(message || 'Failed to start sync');
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to sync environment');
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
      setEditDialogOpen(false);
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

  const driftHandlingModeMutation = useMutation({
    mutationFn: (mode: 'warn_only' | 'manual_override' | 'require_attestation') => {
      if (!environment?.id) throw new Error('Environment not loaded');
      return apiClient.updateEnvironment(environment.id, { drift_handling_mode: mode });
    },
    onSuccess: () => {
      toast.success('Drift handling updated');
      queryClient.invalidateQueries({ queryKey: ['environment', id] });
      queryClient.invalidateQueries({ queryKey: ['environments'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update drift handling');
    },
  });

  // Handlers
  const handleEdit = () => {
    if (!environment) return;
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
    setEditDialogOpen(true);
  };

  const handleSave = () => {
    if (!environment) return;

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
      id: environment.id,
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

    // For production, verify typed confirmation
    if (isProductionEnvironment(environment?.type) && deleteConfirmText !== environment?.name) {
      toast.error('Please type the environment name to confirm deletion');
      return;
    }

    deleteMutation.mutate(id);
  };

  const handleOpenDeleteDialog = () => {
    setDeleteConfirmText('');
    setDeleteDialogOpen(true);
  };

  // Utility functions
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

  const getConnectionStatusBadge = (status: 'connected' | 'degraded' | 'offline') => {
    switch (status) {
      case 'connected':
        return (
          <Badge variant="default" className="bg-green-500 hover:bg-green-600">
            <Wifi className="h-3 w-3 mr-1" />
            Connected
          </Badge>
        );
      case 'degraded':
        return (
          <Badge variant="secondary" className="bg-yellow-500 text-white hover:bg-yellow-600">
            <AlertTriangle className="h-3 w-3 mr-1" />
            Degraded
          </Badge>
        );
      case 'offline':
        return (
          <Badge variant="destructive">
            <WifiOff className="h-3 w-3 mr-1" />
            Offline
          </Badge>
        );
    }
  };

  const getEnvironmentTypeBadge = (type?: string) => {
    if (!type) return null;

    const label = getEnvironmentTypeLabel(environmentTypes, type);
    const lowerType = type.toLowerCase();
    if (['production', 'prod', 'prd', 'live'].includes(lowerType)) {
      return <Badge variant="destructive">{label}</Badge>;
    }
    if (['staging', 'stg', 'stage', 'uat'].includes(lowerType)) {
      return <Badge variant="secondary" className="bg-orange-500 text-white">{label}</Badge>;
    }
    if (['dev', 'development', 'local'].includes(lowerType)) {
      return <Badge variant="outline">{label}</Badge>;
    }
    return <Badge variant="outline">{label}</Badge>;
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

  const formatDateTime = (dateString?: string) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
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

  const getSnapshotTypeLabel = (type: string) => {
    switch (type) {
      case 'auto_backup':
        return 'Auto Backup';
      case 'pre_promotion':
        return 'Pre-Promotion';
      case 'post_promotion':
        return 'Post-Promotion';
      case 'manual_backup':
        return 'Manual Backup';
      default:
        return type;
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Error state
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
  const connectionStatus = getConnectionStatus(environment.lastConnected);
  const isProduction = isProductionEnvironment(environment.type);
  const needsSafetyConfirmation = requiresSafetyConfirmation(environment.type);
  const canUseDriftIncidents = canUseFeature('drift_incidents');

  const userRole = String((user as any)?.role || '').toLowerCase();
  const canAdminEnvironment = userRole === 'admin' || userRole === 'superuser' || userRole === 'super_admin';
  const canDeleteEnvironment = canAdminEnvironment && (!isProduction || userRole === 'superuser' || userRole === 'super_admin');

  const envState =
    environment.activeDriftIncidentId ? 'DRIFT_INCIDENT_ACTIVE' : (environment.driftStatus || 'IN_SYNC');
  const envStateLabel =
    envState === 'DRIFT_INCIDENT_ACTIVE' ? (canUseDriftIncidents ? 'Drift Incident Active' : 'Changes Detected') :
    envState === 'DRIFT_DETECTED' ? (canUseDriftIncidents ? 'Drift Detected' : 'Changes Detected') :
    'In Sync';

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Production Warning Banner */}
      {isProduction && (
        <Alert variant="destructive" className="border-red-500 bg-red-50 dark:bg-red-950/30">
          <AlertTriangle className="h-5 w-5" />
          <AlertTitle className="text-red-700 dark:text-red-400 font-semibold">
            Production Environment
          </AlertTitle>
          <AlertDescription className="text-red-600 dark:text-red-300">
            You are operating on <strong>{environment.name}</strong>. All actions will affect production workflows and data.
            Please proceed with caution.
          </AlertDescription>
        </Alert>
      )}

      {/* Environment Header */}
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
            <h1 className="text-3xl font-bold flex items-center gap-3 mb-2">
              <Server className="h-8 w-8" />
              {environment.name}
            </h1>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {getEnvironmentTypeBadge(environment.type)}
              <Badge
                variant={
                  envState === 'IN_SYNC' ? 'default' :
                  envState === 'DRIFT_DETECTED' ? 'secondary' :
                  'destructive'
                }
                className="text-sm"
              >
                {envStateLabel}
              </Badge>
              {environment.provider && (
                <Badge variant="outline" className="text-sm">{environment.provider}</Badge>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {envState === 'DRIFT_INCIDENT_ACTIVE' && environment.activeDriftIncidentId && canUseDriftIncidents && (
            <Button asChild variant="default">
              <Link to={`/incidents/${environment.activeDriftIncidentId}`}>
                View Drift Incident
              </Link>
            </Button>
          )}
          {envState === 'DRIFT_DETECTED' && (
            canUseDriftIncidents ? (
              <Button
                variant="default"
                onClick={async () => {
                  try {
                    const res = await apiClient.createIncident({ environmentId: environment.id, title: `Drift detected: ${environment.name}` });
                    const incidentId = res?.data?.id;
                    if (incidentId) {
                      navigate(`/incidents/${incidentId}`);
                      return;
                    }
                    navigate('/incidents');
                  } catch (e: any) {
                    toast.error(e?.response?.data?.detail || 'Failed to create incident');
                  }
                }}
              >
                Create Drift Incident
              </Button>
            ) : (
              <Button
                variant="outline"
                onClick={() => toast.info('Upgrade to Agency+ to use Drift Incidents')}
              >
                View Drift Summary
              </Button>
            )
          )}
        </div>
      </div>

      {/* Environment Summary Panel */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Environment Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Instance URL</p>
              <a
                href={environment.baseUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline flex items-center gap-1"
              >
                {new URL(environment.baseUrl).hostname}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Provider</p>
              <p className="text-sm">{environment.provider || 'n8n'}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Source of Truth</p>
              <p className="text-sm">{environment.gitRepoUrl ? 'Git' : 'Manual'}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Workflows</p>
              <p className="text-sm font-semibold">{environment.workflowCount || 0}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Last Sync</p>
              <div className="flex items-center gap-2">
                <p className="text-sm">{formatRelativeTime(environment.lastConnected)}</p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    if (id) {
                      syncMutation.mutate(id);
                    }
                  }}
                  disabled={syncMutation.isPending || activeJob?.status === 'running'}
                  className="h-7 text-xs"
                >
                  {syncMutation.isPending || activeJob?.status === 'running' ? (
                    <>
                      <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                      Syncing...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-3 w-3 mr-1" />
                      Sync
                    </>
                  )}
                </Button>
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Last Drift Detected</p>
              <p className="text-sm">{formatRelativeTime(environment.lastDriftDetectedAt)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Last Backup</p>
              <p className="text-sm">{formatRelativeTime(environment.lastBackup)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              This page is read-first. Run changes via <span className="font-medium text-foreground">Deployments</span>; handle drift/recovery via <span className="font-medium text-foreground">Incidents</span>.
            </p>
            <div className="flex items-center gap-2">
              <Button asChild variant="outline">
                <Link to="/deployments">
                  Go to Deployments →
                </Link>
              </Button>
              {canUseDriftIncidents && (
                <Button asChild variant="outline">
                  <Link to="/incidents">
                    Incidents →
                  </Link>
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

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
                <div className="flex items-center justify-between gap-3">
                  <Link
                    to={`/activity/${activeJob.jobId}`}
                    className="text-sm text-primary hover:underline"
                  >
                    View details →
                  </Link>
                  <Link to="/activity" className="text-xs text-muted-foreground hover:underline">
                    Activity Center
                  </Link>
                </div>
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

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid grid-cols-6 w-full max-w-3xl">
          <TabsTrigger value="overview" className="flex items-center gap-1">
            <Info className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="workflows" className="flex items-center gap-1">
            <Workflow className="h-4 w-4" />
            Workflows
          </TabsTrigger>
          <TabsTrigger value="snapshots" className="flex items-center gap-1">
            <Archive className="h-4 w-4" />
            Snapshots
          </TabsTrigger>
          <TabsTrigger value="activity" className="flex items-center gap-1">
            <History className="h-4 w-4" />
            Activity
          </TabsTrigger>
          <TabsTrigger value="credentials" className="flex items-center gap-1">
            <Key className="h-4 w-4" />
            Credentials
          </TabsTrigger>
          <TabsTrigger value="settings" className="flex items-center gap-1">
            <Settings className="h-4 w-4" />
            Settings
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4" id="drift">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Drift Summary</CardTitle>
                <CardDescription>Compare runtime state against Git source of truth</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Status Row */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        envState === 'IN_SYNC' ? 'default' :
                        envState === 'DRIFT_DETECTED' ? 'secondary' :
                        'destructive'
                      }
                    >
                      {envStateLabel}
                    </Badge>
                    {environment.lastDriftDetectedAt && (
                      <span className="text-xs text-muted-foreground">
                        Last checked: {formatRelativeTime(environment.lastDriftDetectedAt)}
                      </span>
                    )}
                  </div>
                  {!environment.gitRepoUrl && (
                    <p className="text-xs text-yellow-600 dark:text-yellow-400">
                      Git repository not configured. Configure Git to enable drift detection.
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {envState === 'DRIFT_INCIDENT_ACTIVE' && environment.activeDriftIncidentId && canUseDriftIncidents && (
                    <Button asChild>
                      <Link to={`/incidents/${environment.activeDriftIncidentId}`}>
                        View Drift Incident
                      </Link>
                    </Button>
                  )}
                  {envState === 'DRIFT_DETECTED' && (
                    canUseDriftIncidents ? (
                      <Button
                        onClick={async () => {
                          try {
                            const res = await apiClient.createIncident({ environmentId: environment.id, title: `Drift detected: ${environment.name}` });
                            const incidentId = res?.data?.id;
                            navigate(incidentId ? `/incidents/${incidentId}` : '/incidents');
                          } catch (e: any) {
                            toast.error(e?.response?.data?.detail || 'Failed to create incident');
                          }
                        }}
                      >
                        Create Drift Incident
                      </Button>
                    ) : (
                      <Button variant="outline" onClick={() => toast.info('Advanced governance features available on Agency+ plans')}>
                        View Changes
                      </Button>
                    )
                  )}
                </div>
              </div>

              {/* Drift Summary Stats */}
              {driftSummary && (
                <div className="border-t pt-4 space-y-3">
                  <div className="grid grid-cols-4 gap-4 text-center">
                    <div>
                      <p className="text-2xl font-bold">{driftSummary.totalWorkflows}</p>
                      <p className="text-xs text-muted-foreground">Total Workflows</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-green-600">{driftSummary.inSync}</p>
                      <p className="text-xs text-muted-foreground">In Sync</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-yellow-600">{driftSummary.withDrift}</p>
                      <p className="text-xs text-muted-foreground">With Drift</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-blue-600">{driftSummary.notInGit}</p>
                      <p className="text-xs text-muted-foreground">Not in Git</p>
                    </div>
                  </div>

                  {/* Affected Workflows List */}
                  {driftSummary.affectedWorkflows.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Affected Workflows:</p>
                      <div className="max-h-48 overflow-y-auto space-y-1">
                        {driftSummary.affectedWorkflows.slice(0, 10).map((wf) => (
                          <div key={wf.id} className="flex items-center justify-between text-sm p-2 bg-muted/50 rounded">
                            <span className="font-medium">{wf.name}</span>
                            <Badge variant={wf.hasDrift ? 'secondary' : 'outline'} className="text-xs">
                              {wf.hasDrift ? 'Modified' : wf.notInGit ? 'Not in Git' : 'Unknown'}
                            </Badge>
                          </div>
                        ))}
                        {driftSummary.affectedWorkflows.length > 10 && (
                          <p className="text-xs text-muted-foreground text-center">
                            +{driftSummary.affectedWorkflows.length - 10} more workflows
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

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
                <CardTitle className="text-sm font-medium text-muted-foreground">Active Workflows</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <Zap className="h-5 w-5 text-green-500" />
                  <span className="text-2xl font-bold">
                    {workflows.filter((w: WorkflowType) => w.active).length}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {workflows.filter((w: WorkflowType) => !w.active).length} inactive
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Credentials</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <Key className="h-5 w-5 text-muted-foreground" />
                  <span className="text-2xl font-bold">{credentials.length}</span>
                </div>
                <Link
                  to={`/credentials?environment=${id}`}
                  className="text-xs text-primary hover:underline mt-1 block"
                >
                  View credentials →
                </Link>
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

            {/* Recent Events */}
            <Card>
              <CardHeader>
                <CardTitle>Recent Events</CardTitle>
                <CardDescription>Syncs, backups, restores, and operational events</CardDescription>
              </CardHeader>
              <CardContent>
                {recentJobs.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No recent activity
                  </p>
                ) : (
                  <div className="space-y-2">
                    {recentJobs.slice(0, 5).map((job: any) => (
                      <div key={job.id} className="flex items-center justify-between py-2 border-b last:border-0">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(job.status)}
                          <span className="text-sm">{getJobTypeLabel(job.job_type)}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-muted-foreground">
                            {formatRelativeTime(job.created_at)}
                          </span>
                          <Link
                            to={`/activity/${job.id}`}
                            className="text-sm text-primary hover:underline inline-flex items-center gap-1"
                          >
                            <Eye className="h-4 w-4" />
                            View
                          </Link>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-4">
                  <Button variant="outline" size="sm" className="w-full" onClick={() => setActiveTab('activity')}>
                    <Activity className="h-4 w-4 mr-2" />
                    View All Activity
                  </Button>
                </div>
                <div className="mt-2">
                  <Link to="/activity" className="text-xs text-muted-foreground hover:underline">
                    Open Activity Center
                  </Link>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Workflows Tab */}
        <TabsContent value="workflows" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Workflows</CardTitle>
              <CardDescription>
                All workflows in this environment ({workflows.length} total)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {workflowsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : workflows.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No workflows found. Sync the environment to fetch workflows.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last Updated</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {workflows.map((workflow: WorkflowType) => (
                      <TableRow key={workflow.id}>
                        <TableCell className="font-medium">
                          <Link
                            to={`/workflows/${workflow.id}`}
                            className="text-primary hover:underline"
                          >
                            {workflow.name}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Badge variant={workflow.active ? 'default' : 'secondary'}>
                            {workflow.active ? 'Active' : 'Inactive'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatRelativeTime(workflow.updatedAt)}
                        </TableCell>
                        <TableCell>
                          <Link
                            to={`/workflows/${workflow.id}`}
                            className="text-sm text-primary hover:underline"
                          >
                            <Eye className="h-4 w-4 inline mr-1" />
                            View
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Snapshots Tab */}
        <TabsContent value="snapshots" className="space-y-4">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Snapshots</CardTitle>
                <CardDescription>
                  Git-backed environment state backups ({snapshots.length} total)
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {snapshotsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : snapshots.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No snapshots found. Create a snapshot to generate a Git-backed backup.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Created</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Commit SHA</TableHead>
                      <TableHead>Notes</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {snapshots.map((snapshot: Snapshot) => (
                      <TableRow key={snapshot.id}>
                        <TableCell className="text-sm">
                          {formatDateTime(snapshot.createdAt)}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">
                            {getSnapshotTypeLabel(snapshot.type)}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {snapshot.gitCommitSha?.substring(0, 8) || 'N/A'}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                          {snapshot.metadataJson?.reason || snapshot.metadataJson?.notes || '-'}
                        </TableCell>
                        <TableCell>
                          {canUseDriftIncidents ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => navigate(`/incidents?environment_id=${id}&snapshot_id=${snapshot.id}`)}
                            >
                              Use in Incident
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Activity Tab */}
        <TabsContent value="activity" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle>Activity</CardTitle>
                  <CardDescription>
                    Audit log of operations for this environment
                  </CardDescription>
                </div>
                <Link to="/activity" className="text-sm text-primary hover:underline whitespace-nowrap">
                  Activity Center →
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {recentJobs.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No activity found.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Progress</TableHead>
                      <TableHead>Started</TableHead>
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
                            '-'
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatRelativeTime(job.created_at)}
                        </TableCell>
                        <TableCell>
                          <Link
                            to={`/activity/${job.id}`}
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
            </CardContent>
          </Card>
        </TabsContent>

        {/* Credentials Tab */}
        <TabsContent value="credentials" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Credentials</CardTitle>
              <CardDescription>
                Credential health summary ({credentials.length} total)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {credentialsLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : credentials.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No credentials cached. Run a deployment via Deployments to sync metadata, or check your plan/permissions.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Created</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {credentials.map((credential: Credential) => (
                      <TableRow key={credential.id}>
                        <TableCell className="font-medium">{credential.name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{credential.type}</Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatRelativeTime(credential.created_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
              <div className="mt-4">
                <Link to={`/credentials?environment=${id}`}>
                  <Button variant="outline" size="sm" className="w-full">
                    <Key className="h-4 w-4 mr-2" />
                    Manage Credentials
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Environment Settings</CardTitle>
              <CardDescription>
                Configuration and safety controls
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold">Connection</h3>
                  <p className="text-sm text-muted-foreground">
                    Connection credentials are managed via environment configuration. Use “Test Connection” to validate access.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      onClick={handleTestConnection}
                      disabled={testingConnection}
                    >
                      <RefreshCw className={`h-4 w-4 mr-2 ${testingConnection ? 'animate-spin' : ''}`} />
                      {testingConnection ? 'Testing…' : 'Test Connection'}
                    </Button>
                    <Button variant="outline" onClick={handleEdit}>
                      <Edit className="h-4 w-4 mr-2" />
                      Edit Configuration
                    </Button>
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="text-sm font-semibold">Git Configuration</h3>
                  {environment.gitRepoUrl ? (
                    <div className="space-y-2">
                      <div>
                        <Label className="text-muted-foreground">Repository</Label>
                        <p className="text-sm">{environment.gitRepoUrl}</p>
                      </div>
                      <div>
                        <Label className="text-muted-foreground">Branch</Label>
                        <p className="text-sm">{environment.gitBranch || 'main'}</p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">Not configured</p>
                  )}
                </div>

                <div className="space-y-4">
                  <h3 className="text-sm font-semibold">Snapshots</h3>
                  <p className="text-sm text-muted-foreground">
                    Create a Git-backed snapshot of the current environment state. Snapshots can be used in Drift Incidents for recovery operations.
                  </p>
                  <Button
                    variant="outline"
                    onClick={handleBackup}
                    disabled={activeJob?.jobType === 'backup' && activeJob?.status === 'running'}
                  >
                    <Database className={`h-4 w-4 mr-2 ${activeJob?.jobType === 'backup' && activeJob?.status === 'running' ? 'animate-spin' : ''}`} />
                    {activeJob?.jobType === 'backup' && activeJob?.status === 'running' ? 'Creating...' : 'Create Snapshot'}
                  </Button>
                </div>
              </div>

              {!canUseDriftIncidents && (
                <div className="border-t pt-4 space-y-3">
                  <div>
                    <h3 className="text-sm font-semibold">Drift Handling (Free/Pro)</h3>
                    <p className="text-sm text-muted-foreground">
                      Configure how drift should be handled for this environment. Agency+ centralizes drift handling in Incidents.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="space-y-2 min-w-[260px]">
                      <Label>Behavior</Label>
                      <Select value={driftHandlingMode} onValueChange={(v) => setDriftHandlingMode(v as any)}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select behavior" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="warn_only">Warn only</SelectItem>
                          <SelectItem value="manual_override">Allow manual override (recorded)</SelectItem>
                          <SelectItem value="require_attestation">Require manual attestation</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <Button
                      onClick={() => driftHandlingModeMutation.mutate(driftHandlingMode)}
                      disabled={driftHandlingModeMutation.isPending}
                    >
                      {driftHandlingModeMutation.isPending ? 'Saving…' : 'Save'}
                    </Button>
                  </div>
                </div>
              )}

              <div className="border-t pt-4">
                <h3 className="text-sm font-semibold mb-4">Feature Flags</h3>
                <div className="flex flex-wrap gap-3">
                  <div className="flex items-center gap-2">
                    <Badge variant={environment.isActive ? 'default' : 'outline'}>
                      {environment.isActive ? 'Active' : 'Inactive'}
                    </Badge>
                    <span className="text-sm text-muted-foreground">Environment Status</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={environment.allowUpload ? 'default' : 'outline'}>
                      {environment.allowUpload ? 'Enabled' : 'Disabled'}
                    </Badge>
                    <span className="text-sm text-muted-foreground">Workflow Upload</span>
                  </div>
                </div>
              </div>

              <div className="border-t pt-4">
                <h3 className="text-sm font-semibold mb-4">Timestamps</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <Label className="text-muted-foreground">Created</Label>
                    <p>{formatDateTime(environment.createdAt)}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">Last Updated</Label>
                    <p>{formatDateTime(environment.updatedAt)}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">Last Connected</Label>
                    <p>{formatDateTime(environment.lastConnected)}</p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground">Last Backup</Label>
                    <p>{formatDateTime(environment.lastBackup)}</p>
                  </div>
                </div>
              </div>

              <div className="border-t pt-4">
                <h3 className="text-sm font-semibold mb-3 text-destructive">Danger Zone</h3>
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    variant="outline"
                    className="border-destructive text-destructive hover:bg-destructive/10"
                    onClick={handleOpenDeleteDialog}
                    disabled={!canDeleteEnvironment}
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete Environment
                  </Button>
                  {!canAdminEnvironment && (
                    <p className="text-xs text-muted-foreground">
                      Admin permissions required.
                    </p>
                  )}
                  {canAdminEnvironment && isProduction && !canDeleteEnvironment && (
                    <p className="text-xs text-muted-foreground">
                      Deleting production environments is restricted.
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit Environment Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
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
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
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
              The download will include workflow definitions only. Credentials and sensitive data are not included.
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
            <AlertDialogTitle className="flex items-center gap-2">
              <Trash2 className="h-5 w-5 text-red-500" />
              Delete Environment
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{environment.name}</strong>? This action cannot be undone.
              All workflows, executions, and credentials associated with this environment will be removed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {needsSafetyConfirmation && (
            <div className="py-4 space-y-4">
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Destructive Action</AlertTitle>
                <AlertDescription>
                  Type the environment name to confirm: <strong>{environment.name}</strong>
                </AlertDescription>
              </Alert>
              <Input
                placeholder={`Type "${environment.name}" to confirm`}
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
              />
            </div>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setDeleteConfirmText('')}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700"
              disabled={needsSafetyConfirmation && deleteConfirmText !== environment.name}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
