import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { api } from '@/lib/api';
import { useAppStore } from '@/store/use-app-store';
import { Search, AlertCircle, RefreshCw, Key, Download, ArrowUpDown, ArrowUp, ArrowDown, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { EnvironmentType } from '@/types';
import { toast } from 'sonner';
import { formatNodeType } from '@/lib/workflow-analysis';

type SortField = 'name' | 'type' | 'environment' | 'workflows';
type SortDirection = 'asc' | 'desc';

export function CredentialsPage() {
  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [isSyncing, setIsSyncing] = useState(false);
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Fetch all credentials
  const { data: credentials, isLoading, refetch } = useQuery({
    queryKey: ['credentials', selectedEnvironment],
    queryFn: () => api.getCredentials(selectedEnvironment === 'dev' ? undefined : selectedEnvironment),
  });

  // Fetch environments for filter
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.getEnvironments(),
  });

  // Sync mutation to refresh from N8N (via environment sync)
  const syncMutation = useMutation({
    mutationFn: async () => {
      // Get all environments or just the selected one
      const envsToSync = environments?.data?.filter((env: any) =>
        selectedEnvironment === 'dev' || env.n8n_type === selectedEnvironment
      ) || [];

      const results = [];
      for (const env of envsToSync) {
        const result = await api.syncEnvironment(env.id);
        results.push({ env: env.n8n_name, ...result.data });
      }
      return results;
    },
    onSuccess: () => {
      setIsSyncing(false);
      toast.success('Synced credentials from N8N workflows');
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
    },
    onError: (error: any) => {
      setIsSyncing(false);
      const message = error.response?.data?.detail || 'Failed to sync from N8N';
      toast.error(message);
    },
  });

  const handleSyncFromN8N = () => {
    toast.info('Syncing credentials from N8N workflows...');
    setIsSyncing(true);
    syncMutation.mutate();
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
    credentials.data.forEach((cred: any) => {
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
      result = result.filter((cred: any) =>
        cred.name?.toLowerCase().includes(query) ||
        cred.type?.toLowerCase().includes(query)
      );
    }

    // Apply type filter
    if (selectedType !== 'all') {
      result = result.filter((cred: any) => cred.type === selectedType);
    }

    // Apply sorting
    result.sort((a: any, b: any) => {
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

  const getEnvironmentBadge = (type: EnvironmentType) => {
    const colors: Record<EnvironmentType, string> = {
      dev: 'bg-blue-50 text-blue-700 border-blue-200',
      staging: 'bg-yellow-50 text-yellow-700 border-yellow-200',
      production: 'bg-green-50 text-green-700 border-green-200',
    };

    return (
      <Badge variant="outline" className={colors[type]}>
        {type}
      </Badge>
    );
  };

  // Open credential in N8N
  const openInN8N = (cred: any) => {
    const baseUrl = cred.environment?.n8n_base_url;
    const credId = cred.n8n_credential_id;
    if (baseUrl && credId && !credId.includes(':')) {
      window.open(`${baseUrl}/home/credentials/${credId}`, '_blank');
    }
  };

  // Check if credential can be opened in N8N (has valid ID, not a generated key)
  const canOpenInN8N = (cred: any) => {
    const credId = cred.n8n_credential_id;
    return cred.environment?.n8n_base_url && credId && !credId.includes(':');
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Credentials</h1>
          <p className="text-muted-foreground">
            View credentials synced from N8N instances across environments
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => refetch()} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button
            onClick={handleSyncFromN8N}
            variant="default"
            size="sm"
            disabled={isSyncing}
          >
            <Download className={`h-4 w-4 mr-2 ${isSyncing ? 'animate-spin' : ''}`} />
            Sync from N8N
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            N8N Credentials
          </CardTitle>
          <CardDescription>
            Credentials referenced by workflows in your N8N environments. Extracted from workflow node configurations.
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
              value={selectedEnvironment}
              onChange={(e) => setSelectedEnvironment(e.target.value as EnvironmentType)}
              className="flex h-9 w-[180px] rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="dev">All Environments</option>
              {environments?.data?.map((env: any) => (
                <option key={env.id} value={env.type}>
                  {env.name}
                </option>
              ))}
            </select>

            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="flex h-9 w-[180px] rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="all">All Types</option>
              {allTypes.map((type) => (
                <option key={type} value={type}>
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
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  Click "Sync from N8N" to extract credential references from your workflows.
                </p>
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
                    className="cursor-pointer hover:bg-muted/50 max-w-[50%] w-[50%]"
                    onClick={() => handleSort('workflows')}
                  >
                    <div className="flex items-center">
                      Used by Workflows
                      {getSortIcon('workflows')}
                    </div>
                  </TableHead>
                  <TableHead className="w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAndSortedCredentials.map((cred: any) => (
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
                    <TableCell className="max-w-[50%]">
                      {cred.used_by_workflows && cred.used_by_workflows.length > 0 ? (
                        <div className="flex flex-wrap gap-x-3 gap-y-1">
                          {cred.used_by_workflows.map((wf: any, index: number) => (
                            <span key={wf.id}>
                              <Link
                                to={`/workflows/${wf.n8n_workflow_id || wf.id}?environment=${cred.environment?.type || 'dev'}`}
                                className="text-sm text-primary hover:underline"
                              >
                                {wf.name}
                              </Link>
                              {index < cred.used_by_workflows.length - 1 && <span className="text-muted-foreground">,</span>}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-sm">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {canOpenInN8N(cred) && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openInN8N(cred)}
                          title="Open in N8N"
                        >
                          <ExternalLink className="h-4 w-4 mr-1" />
                          N8N
                        </Button>
                      )}
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
    </div>
  );
}
