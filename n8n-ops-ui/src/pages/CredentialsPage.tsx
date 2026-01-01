// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
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
import { Alert, AlertDescription } from '@/components/ui/alert';
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { apiClient } from '@/lib/api-client';
import { useAppStore } from '@/store/use-app-store';
import {
  Search, AlertCircle, RefreshCw, Key, Download, ArrowUpDown, ArrowUp, ArrowDown,
  ExternalLink, Plus, MoreHorizontal, Pencil, Trash2, Eye, EyeOff, Info, Grid3X3, ShieldCheck
} from 'lucide-react';
import { Link } from 'react-router-dom';
import type { EnvironmentType, Credential, Environment } from '@/types';
import { toast } from 'sonner';
import { getDefaultEnvironmentId, resolveEnvironment, sortEnvironments } from '@/lib/environment-utils';
import { formatNodeType } from '@/lib/workflow-analysis';
import { CredentialMatrix, CredentialDiscovery, MappingHealthCheck } from '@/components/credentials';

type SortField = 'name' | 'type' | 'environment' | 'workflows';
type SortDirection = 'asc' | 'desc';

// Common credential type fields mapping
const CREDENTIAL_TYPE_FIELDS: Record<string, { name: string; fields: { key: string; label: string; type: string; required?: boolean; placeholder?: string }[] }> = {
  slackApi: {
    name: 'Slack API',
    fields: [
      { key: 'accessToken', label: 'Access Token', type: 'password', required: true, placeholder: 'xoxb-...' },
    ],
  },
  githubApi: {
    name: 'GitHub API',
    fields: [
      { key: 'accessToken', label: 'Personal Access Token', type: 'password', required: true, placeholder: 'ghp_...' },
    ],
  },
  httpBasicAuth: {
    name: 'HTTP Basic Auth',
    fields: [
      { key: 'user', label: 'Username', type: 'text', required: true },
      { key: 'password', label: 'Password', type: 'password', required: true },
    ],
  },
  httpHeaderAuth: {
    name: 'HTTP Header Auth',
    fields: [
      { key: 'name', label: 'Header Name', type: 'text', required: true, placeholder: 'Authorization' },
      { key: 'value', label: 'Header Value', type: 'password', required: true, placeholder: 'Bearer ...' },
    ],
  },
  oAuth2Api: {
    name: 'OAuth2 API',
    fields: [
      { key: 'clientId', label: 'Client ID', type: 'text', required: true },
      { key: 'clientSecret', label: 'Client Secret', type: 'password', required: true },
      { key: 'accessToken', label: 'Access Token', type: 'password' },
      { key: 'refreshToken', label: 'Refresh Token', type: 'password' },
    ],
  },
  postgresApi: {
    name: 'PostgreSQL',
    fields: [
      { key: 'host', label: 'Host', type: 'text', required: true, placeholder: 'localhost' },
      { key: 'port', label: 'Port', type: 'text', required: true, placeholder: '5432' },
      { key: 'database', label: 'Database', type: 'text', required: true },
      { key: 'user', label: 'User', type: 'text', required: true },
      { key: 'password', label: 'Password', type: 'password', required: true },
    ],
  },
  mysqlApi: {
    name: 'MySQL',
    fields: [
      { key: 'host', label: 'Host', type: 'text', required: true, placeholder: 'localhost' },
      { key: 'port', label: 'Port', type: 'text', required: true, placeholder: '3306' },
      { key: 'database', label: 'Database', type: 'text', required: true },
      { key: 'user', label: 'User', type: 'text', required: true },
      { key: 'password', label: 'Password', type: 'password', required: true },
    ],
  },
  awsApi: {
    name: 'AWS',
    fields: [
      { key: 'accessKeyId', label: 'Access Key ID', type: 'text', required: true },
      { key: 'secretAccessKey', label: 'Secret Access Key', type: 'password', required: true },
      { key: 'region', label: 'Region', type: 'text', placeholder: 'us-east-1' },
    ],
  },
};

export function CredentialsPage() {
  useEffect(() => {
    document.title = 'Credentials - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);
  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [isSyncing, setIsSyncing] = useState(false);
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedCredential, setSelectedCredential] = useState<Credential | null>(null);
  const [mappingDialogOpen, setMappingDialogOpen] = useState(false);
  const [mappingLogicalId, setMappingLogicalId] = useState<string>('');
  const [mappingEnvId, setMappingEnvId] = useState<string>('');
  const [selectedPhysicalCredId, setSelectedPhysicalCredId] = useState<string>('');

  // Form states
  const [formName, setFormName] = useState('');
  const [formType, setFormType] = useState('');
  const [formEnvironmentId, setFormEnvironmentId] = useState('');
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});

  // Fetch environments for filter and create dialog
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  // Get the selected environment ID (handle type vs id selection)
  const selectedEnvId = useMemo(() => {
    if (!selectedEnvironment || selectedEnvironment === 'all') return 'all';
    return resolveEnvironment(environments?.data, selectedEnvironment)?.id || 'all';
  }, [selectedEnvironment, environments?.data]);

  // Default to dev (and normalize legacy type selections to environment_id)
  useEffect(() => {
    const envs = environments?.data || [];
    if (envs.length === 0) return;
    if (selectedEnvironment === 'all') return;

    const resolved = resolveEnvironment(envs, selectedEnvironment);
    const nextId = resolved?.id || getDefaultEnvironmentId(envs);
    if (nextId && selectedEnvironment !== nextId) {
      setSelectedEnvironment(nextId);
    }
  }, [environments?.data, selectedEnvironment, setSelectedEnvironment]);

  // Fetch credentials from the database cache (synced from N8N)
  const { data: credentials, isLoading, refetch } = useQuery({
    queryKey: ['physical-credentials', selectedEnvId],
    queryFn: async () => {
      // Get environment type for filtering if a specific environment is selected
      const envs = environments?.data || [];
      let envType: string | undefined;
      
      if (selectedEnvId && selectedEnvId !== 'all') {
        const env = envs.find((e: Environment) => e.id === selectedEnvId);
        envType = env?.type;
      }
      
      // Fetch cached credentials from database
      const result = await apiClient.getCredentials({ environmentType: envType });
      return result;
    },
  });

  // Create credential mutation
  const createMutation = useMutation({
    mutationFn: (data: { name: string; type: string; data: Record<string, any>; environment_id: string }) =>
      apiClient.createCredential(data),
    onSuccess: () => {
      toast.success('Credential created successfully');
      queryClient.invalidateQueries({ queryKey: ['physical-credentials'] });
      setCreateDialogOpen(false);
      resetForm();
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to create credential';
      toast.error(message);
    },
  });

  // Update credential mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; data?: Record<string, any> } }) =>
      apiClient.updateCredential(id, data),
    onSuccess: () => {
      toast.success('Physical credential updated successfully');
      queryClient.invalidateQueries({ queryKey: ['physical-credentials'] });
      setEditDialogOpen(false);
      resetForm();
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to update credential';
      toast.error(message);
    },
  });

  // Delete credential mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteCredential(id),
    onSuccess: () => {
      toast.success('Credential deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['physical-credentials'] });
      setDeleteDialogOpen(false);
      setSelectedCredential(null);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to delete credential';
      toast.error(message);
    },
  });

  // Sync mutation to refresh from N8N (syncs to cache and refetches live data)
  const syncMutation = useMutation({
    mutationFn: async () => {
      const envsToSync = environments?.data?.filter((env: Environment) =>
        selectedEnvId === 'all' ||
        env.id === selectedEnvId
      ) || [];

      const results = [];
      for (const env of envsToSync) {
        const result = await apiClient.syncCredentials(env.id);
        results.push({ env: env.name, ...result.data });
      }
      return results;
    },
    onSuccess: (results) => {
      setIsSyncing(false);
      const total = results.reduce((sum, r) => sum + (r.synced || 0), 0);
      toast.success(`Synced ${total} credentials from N8N`);
      // Invalidate the live credentials query to refetch
      queryClient.invalidateQueries({ queryKey: ['physical-credentials'] });
    },
    onError: (error: any) => {
      setIsSyncing(false);
      const message = error.response?.data?.detail || 'Failed to sync from N8N';
      toast.error(message);
    },
  });

  const handleSyncFromN8N = () => {
    toast.info('Syncing credentials from N8N...');
    setIsSyncing(true);
    syncMutation.mutate();
  };

  // Fetch physical credentials for mapping dialog
  const { data: physicalCredentials, isLoading: isLoadingPhysical } = useQuery({
    queryKey: ['physical-credentials-for-mapping', mappingEnvId],
    queryFn: () => apiClient.getCredentialsByEnvironment(mappingEnvId),
    enabled: !!mappingEnvId && mappingDialogOpen,
  });

  // Fetch logical credentials for mapping dialog
  const { data: logicalCredentials } = useQuery({
    queryKey: ['logical-credentials'],
    queryFn: () => apiClient.getLogicalCredentials(),
  });

  // Create mapping mutation
  const createMappingMutation = useMutation({
    mutationFn: (data: {
      logical_credential_id: string;
      environment_id: string;
      physical_credential_id: string;
      physical_name: string;
      physical_type: string;
    }) => apiClient.createCredentialMapping(data),
    onSuccess: () => {
      toast.success('Mapping created successfully');
      queryClient.invalidateQueries({ queryKey: ['credential-matrix'] });
      setMappingDialogOpen(false);
      setSelectedPhysicalCredId('');
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to create mapping';
      toast.error(message);
    },
  });

  // Delete mapping mutation (unmap)
  const deleteMappingMutation = useMutation({
    mutationFn: (mappingId: string) => apiClient.deleteCredentialMapping(mappingId),
    onSuccess: () => {
      toast.success('Mapping removed successfully');
      queryClient.invalidateQueries({ queryKey: ['credential-matrix'] });
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to remove mapping';
      toast.error(message);
    },
  });

  // Handler for opening mapping dialog
  const handleCreateMapping = (logicalId: string, envId: string) => {
    setMappingLogicalId(logicalId);
    setMappingEnvId(envId);
    setSelectedPhysicalCredId('');
    setMappingDialogOpen(true);
  };

  // Handler for creating mapping
  const handleSubmitMapping = () => {
    const selectedCred = physicalCredentials?.data?.find(
      (c: any) => c.id === selectedPhysicalCredId
    );
    if (!selectedCred) {
      toast.error('Please select a credential');
      return;
    }
    createMappingMutation.mutate({
      logical_credential_id: mappingLogicalId,
      environment_id: mappingEnvId,
      physical_credential_id: selectedCred.id,
      physical_name: selectedCred.name,
      physical_type: selectedCred.type,
    });
  };

  // Handler for unmapping
  const handleUnmapMapping = (mappingId: string) => {
    deleteMappingMutation.mutate(mappingId);
  };

  // Get logical credential name for display
  const getMappingLogicalName = () => {
    const logical = logicalCredentials?.data?.find((lc: any) => lc.id === mappingLogicalId);
    return logical?.name || mappingLogicalId;
  };

  // Get environment name for display
  const getMappingEnvName = () => {
    const env = environments?.data?.find((e: Environment) => e.id === mappingEnvId);
    return env?.name || mappingEnvId;
  };

  // Form helpers
  const resetForm = () => {
    setFormName('');
    setFormType('');
    setFormEnvironmentId('');
    setFormData({});
    setShowPasswords({});
    setSelectedCredential(null);
  };

  const openCreateDialog = () => {
    resetForm();
    // Set default environment if one is selected
    if (environments?.data?.length) {
      const defaultEnv =
        environments.data.find((e: Environment) => e.type === selectedEnvironment || e.id === selectedEnvironment) ||
        environments.data[0];
      setFormEnvironmentId(defaultEnv.id);
    }
    setCreateDialogOpen(true);
  };

  const openEditDialog = (cred: Credential) => {
    setSelectedCredential(cred);
    setFormName(cred.name);
    setFormType(cred.type);
    setFormData({});
    setEditDialogOpen(true);
  };

  const openDeleteDialog = (cred: Credential) => {
    setSelectedCredential(cred);
    setDeleteDialogOpen(true);
  };

  const handleCreate = () => {
    if (!formName || !formType || !formEnvironmentId) {
      toast.error('Please fill in all required fields');
      return;
    }
    createMutation.mutate({
      name: formName,
      type: formType,
      data: formData,
      environment_id: formEnvironmentId,
    });
  };

  const handleUpdate = () => {
    if (!selectedCredential || !formName) {
      toast.error('Please fill in all required fields');
      return;
    }
    const updateData: { name?: string; data?: Record<string, any> } = { name: formName };
    if (Object.keys(formData).length > 0) {
      updateData.data = formData;
    }
    updateMutation.mutate({ id: selectedCredential.id, data: updateData });
  };

  const handleDelete = () => {
    if (!selectedCredential) return;
    deleteMutation.mutate(selectedCredential.id);
  };

  // Get fields for selected credential type
  const getTypeFields = (type: string) => {
    return CREDENTIAL_TYPE_FIELDS[type]?.fields || [
      { key: 'apiKey', label: 'API Key', type: 'password', required: true },
    ];
  };

  // Handle sorting
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="h-4 w-4 ml-1 opacity-50" />;
    }
    return sortDirection === 'asc'
      ? <ArrowUp className="h-4 w-4 ml-1" />
      : <ArrowDown className="h-4 w-4 ml-1" />;
  };

  // Get unique credential types
  const allTypes = useMemo(() => {
    if (!credentials?.data) return [];
    const types = new Set<string>();
    credentials.data.forEach((cred: Credential) => {
      if (cred.type) types.add(cred.type);
    });
    return Array.from(types).sort();
  }, [credentials?.data]);

  // Filter, search, and sort credentials
  const filteredAndSortedCredentials = useMemo(() => {
    if (!credentials?.data) return [];

    let result = [...credentials.data];

    // Apply search filter (name and type)
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter((cred: Credential) =>
        cred.name?.toLowerCase().includes(query) ||
        cred.type?.toLowerCase().includes(query)
      );
    }

    // Apply type filter
    if (selectedType !== 'all') {
      result = result.filter((cred: Credential) => cred.type === selectedType);
    }

    // Apply sorting
    result.sort((a: Credential, b: Credential) => {
      let aValue: any;
      let bValue: any;

      switch (sortField) {
        case 'name':
          aValue = a.name?.toLowerCase() || '';
          bValue = b.name?.toLowerCase() || '';
          break;
        case 'type':
          aValue = a.type?.toLowerCase() || '';
          bValue = b.type?.toLowerCase() || '';
          break;
        case 'environment':
          aValue = a.environment?.name?.toLowerCase() || '';
          bValue = b.environment?.name?.toLowerCase() || '';
          break;
        case 'workflows':
          aValue = a.used_by_workflows?.length || 0;
          bValue = b.used_by_workflows?.length || 0;
          break;
        default:
          aValue = '';
          bValue = '';
      }

      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  }, [credentials?.data, searchQuery, selectedType, sortField, sortDirection]);

  const getEnvironmentBadge = (type: string | undefined) => {
    if (!type) return null;
    const colors: Record<string, string> = {
      dev: 'bg-blue-50 text-blue-700 border-blue-200',
      staging: 'bg-yellow-50 text-yellow-700 border-yellow-200',
      production: 'bg-green-50 text-green-700 border-green-200',
    };

    return (
      <Badge variant="outline" className={colors[type] || 'bg-gray-50 text-gray-700 border-gray-200'}>
        {type}
      </Badge>
    );
  };

  // Open credential in N8N
  const openInN8N = (cred: Credential) => {
    const baseUrl = cred.environment?.n8n_base_url;
    const credId = cred.n8n_credential_id;
    if (baseUrl && credId && !credId.includes(':')) {
      window.open(`${baseUrl}/home/credentials/${credId}`, '_blank');
    }
  };

  // Check if credential can be opened in N8N (has valid ID, not a generated key)
  const canOpenInN8N = (cred: Credential) => {
    const credId = cred.n8n_credential_id;
    return cred.environment?.n8n_base_url && credId && !credId.includes(':');
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Credentials</h1>
          <p className="text-muted-foreground">
            Manage credentials for your N8N workflows across environments
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => refetch()} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button
            onClick={handleSyncFromN8N}
            variant="outline"
            size="sm"
            disabled={isSyncing}
          >
            <Download className={`h-4 w-4 mr-2 ${isSyncing ? 'animate-spin' : ''}`} />
            Sync from N8N
          </Button>
          <Button onClick={openCreateDialog} size="sm">
            <Plus className="h-4 w-4 mr-2" />
            Create Credential
          </Button>
        </div>
      </div>

      {/* Info Banner */}
      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>
          Physical credential secrets are encrypted and stored securely in N8N. Only metadata (name, type) is cached locally.
          Actual secrets are never visible or stored in this application.
        </AlertDescription>
      </Alert>

      <Tabs defaultValue="credentials" className="space-y-4">
        <TabsList>
          <TabsTrigger value="credentials" className="gap-2">
            <Key className="h-4 w-4" />
            Credentials
          </TabsTrigger>
          <TabsTrigger value="matrix" className="gap-2">
            <Grid3X3 className="h-4 w-4" />
            Mapping
          </TabsTrigger>
          <TabsTrigger value="discover" className="gap-2">
            <Search className="h-4 w-4" />
            Discover
          </TabsTrigger>
          <TabsTrigger value="health" className="gap-2">
            <ShieldCheck className="h-4 w-4" />
            Health Check
          </TabsTrigger>
        </TabsList>

        <TabsContent value="credentials">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                Credentials
              </CardTitle>
              <CardDescription>
                Physical credentials exist in N8N and hold secrets. These are used by workflows in your N8N environments.
              </CardDescription>
            </CardHeader>
            <CardContent>
          {/* Filters */}
          <div className="flex gap-4 mb-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by name or type..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <select
              value={selectedEnvId || 'all'}
              onChange={(e) => setSelectedEnvironment(e.target.value as EnvironmentType)}
              className="flex h-9 w-[180px] rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="all" className="bg-background text-foreground">All Environments</option>
              {sortEnvironments((environments?.data || []).filter((env: Environment) => env.isActive)).map((env: Environment) => (
                <option key={env.id} value={env.id} className="bg-background text-foreground">
                  {env.name}
                </option>
              ))}
            </select>

            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="flex h-9 w-[180px] rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="all" className="bg-background text-foreground">All Types</option>
              {allTypes.map((type) => (
                <option key={type} value={type} className="bg-background text-foreground">
                  {formatNodeType(type)}
                </option>
              ))}
            </select>
          </div>

          {/* Credentials Table */}
          {isLoading ? (
            <div className="text-center py-8">Loading credentials...</div>
          ) : filteredAndSortedCredentials.length === 0 ? (
            <div className="text-center py-8">
              <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-muted-foreground mb-2">
                {credentials?.data?.length === 0
                  ? 'No credentials found.'
                  : 'No credentials match your filters.'}
              </p>
              {credentials?.data?.length === 0 && (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground max-w-md mx-auto">
                    Click "Create Physical Credential" to add a new physical credential, or "Sync from N8N" to import existing credentials.
                  </p>
                  <Button onClick={openCreateDialog} size="sm" variant="outline">
                    <Plus className="h-4 w-4 mr-2" />
                    Create your first credential
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleSort('name')}
                  >
                    <div className="flex items-center">
                      Name
                      {getSortIcon('name')}
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleSort('type')}
                  >
                    <div className="flex items-center">
                      Type
                      {getSortIcon('type')}
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => handleSort('environment')}
                  >
                    <div className="flex items-center">
                      Environment
                      {getSortIcon('environment')}
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer hover:bg-muted/50 max-w-[40%] w-[40%]"
                    onClick={() => handleSort('workflows')}
                  >
                    <div className="flex items-center">
                      Used by Workflows
                      {getSortIcon('workflows')}
                    </div>
                  </TableHead>
                  <TableHead className="w-[120px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAndSortedCredentials.map((cred: Credential) => (
                  <TableRow key={cred.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Key className="h-4 w-4 text-muted-foreground" />
                        {cred.name}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-muted-foreground">{formatNodeType(cred.type || '')}</span>
                    </TableCell>
                    <TableCell>
                      {cred.environment ? (
                        <div className="flex flex-col gap-1">
                          <span className="text-sm">{cred.environment.name}</span>
                          {getEnvironmentBadge(cred.environment.type)}
                        </div>
                      ) : (
                        'N/A'
                      )}
                    </TableCell>
                    <TableCell className="max-w-[40%]">
                      {cred.used_by_workflows && cred.used_by_workflows.length > 0 ? (
                        <div className="flex flex-wrap gap-x-3 gap-y-1">
                          {cred.used_by_workflows.map((wf, index: number) => (
                            <span key={wf.id}>
                              <Link
                                to={`/workflows/${wf.n8n_workflow_id || wf.id}?environment=${cred.environment?.type || 'dev'}`}
                                className="text-sm text-primary hover:underline"
                              >
                                {wf.name}
                              </Link>
                              {index < cred.used_by_workflows!.length - 1 && <span className="text-muted-foreground">,</span>}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-sm">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => openEditDialog(cred)}>
                            <Pencil className="h-4 w-4 mr-2" />
                            Edit
                          </DropdownMenuItem>
                          {canOpenInN8N(cred) && (
                            <DropdownMenuItem onClick={() => openInN8N(cred)}>
                              <ExternalLink className="h-4 w-4 mr-2" />
                              Open in N8N
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuItem
                            onClick={() => openDeleteDialog(cred)}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Results count */}
          {filteredAndSortedCredentials.length > 0 && (
            <div className="mt-4 text-sm text-muted-foreground">
              Showing {filteredAndSortedCredentials.length} of {credentials?.data?.length || 0} credentials
            </div>
          )}
        </CardContent>
      </Card>
        </TabsContent>

        <TabsContent value="matrix">
          <CredentialMatrix onCreateMapping={handleCreateMapping} onUnmapMapping={handleUnmapMapping} />
        </TabsContent>

        <TabsContent value="discover">
          <CredentialDiscovery />
        </TabsContent>

        <TabsContent value="health">
          <MappingHealthCheck />
        </TabsContent>
      </Tabs>

      {/* Create Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create Credential</DialogTitle>
            <DialogDescription>
              Add a new credential to your N8N instance. Secrets are encrypted and stored securely in N8N.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="create-name">Name *</Label>
              <Input
                id="create-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="My API Credential"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-environment">Environment *</Label>
              <Select value={formEnvironmentId} onValueChange={setFormEnvironmentId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select environment" />
                </SelectTrigger>
                <SelectContent>
                  {environments?.data?.map((env: Environment) => (
                    <SelectItem key={env.id} value={env.id}>
                      {env.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="create-type">Type *</Label>
              <Select value={formType} onValueChange={(v) => { setFormType(v); setFormData({}); }}>
                <SelectTrigger>
                  <SelectValue placeholder="Select credential type" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(CREDENTIAL_TYPE_FIELDS).map(([key, config]) => (
                    <SelectItem key={key} value={key}>
                      {config.name}
                    </SelectItem>
                  ))}
                  <SelectItem value="custom">Other (Custom)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {formType && (
              <div className="space-y-3 border-t pt-4">
                <Label className="text-sm font-medium">Credential Data</Label>
                {getTypeFields(formType).map((field) => (
                  <div key={field.key} className="space-y-1">
                    <Label htmlFor={`create-${field.key}`} className="text-sm">
                      {field.label} {field.required && '*'}
                    </Label>
                    <div className="relative">
                      <Input
                        id={`create-${field.key}`}
                        type={field.type === 'password' && !showPasswords[field.key] ? 'password' : 'text'}
                        value={formData[field.key] || ''}
                        onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
                        placeholder={field.placeholder}
                      />
                      {field.type === 'password' && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                          onClick={() => setShowPasswords({ ...showPasswords, [field.key]: !showPasswords[field.key] })}
                        >
                          {showPasswords[field.key] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit Physical Credential</DialogTitle>
            <DialogDescription>
              Update the physical credential name or data. Leave data fields empty to keep existing values.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Name *</Label>
              <Input
                id="edit-name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <Input value={formatNodeType(formType || '')} disabled />
            </div>

            {formType && (
              <div className="space-y-3 border-t pt-4">
                <Label className="text-sm font-medium">Update Credential Data (optional)</Label>
                <p className="text-xs text-muted-foreground">
                  Only fill in fields you want to update. Leave blank to keep existing values.
                </p>
                {getTypeFields(formType).map((field) => (
                  <div key={field.key} className="space-y-1">
                    <Label htmlFor={`edit-${field.key}`} className="text-sm">
                      {field.label}
                    </Label>
                    <div className="relative">
                      <Input
                        id={`edit-${field.key}`}
                        type={field.type === 'password' && !showPasswords[field.key] ? 'password' : 'text'}
                        value={formData[field.key] || ''}
                        onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
                        placeholder={`Leave empty to keep current ${field.label.toLowerCase()}`}
                      />
                      {field.type === 'password' && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                          onClick={() => setShowPasswords({ ...showPasswords, [field.key]: !showPasswords[field.key] })}
                        >
                          {showPasswords[field.key] ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Credential</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedCredential?.name}"? This will remove the credential from N8N.
              {selectedCredential?.used_by_workflows && selectedCredential.used_by_workflows.length > 0 && (
                <span className="block mt-2 text-destructive">
                  Warning: This credential is used by {selectedCredential.used_by_workflows.length} workflow(s).
                  Deleting it may break those workflows.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Mapping Dialog */}
      <Dialog open={mappingDialogOpen} onOpenChange={setMappingDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create Credential Mapping</DialogTitle>
            <DialogDescription>
              Map credential alias "{getMappingLogicalName()}" to a physical credential in {getMappingEnvName()}. This creates a mapping: alias → physical credential per environment.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Select Physical Credential</Label>
              {isLoadingPhysical ? (
                <div className="text-sm text-muted-foreground">Loading credentials...</div>
              ) : physicalCredentials?.data?.length === 0 ? (
                <div className="text-sm text-muted-foreground">No credentials found in this environment</div>
              ) : (
                <Select value={selectedPhysicalCredId} onValueChange={setSelectedPhysicalCredId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a credential..." />
                  </SelectTrigger>
                  <SelectContent>
                    {physicalCredentials?.data?.map((cred: any) => (
                      <SelectItem key={cred.id} value={cred.id}>
                        {cred.name} ({cred.type})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMappingDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmitMapping}
              disabled={!selectedPhysicalCredId || createMappingMutation.isPending}
            >
              {createMappingMutation.isPending ? 'Creating...' : 'Create Mapping'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
