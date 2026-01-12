import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PaginationControls } from '@/components/ui/pagination-controls';
import { CheckCircle2, AlertCircle, RefreshCw, Link2, AlertTriangle, ExternalLink, Filter } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth';
import { apiClient } from '@/lib/api-client';
import type {
  WorkflowEnvMap,
  CanonicalWorkflow,
  Environment,
  WorkflowMappingStatus,
  PaginatedResponse
} from '@/types';

export function WorkflowMappingsPage() {
  const navigate = useNavigate();
  const { tenant } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // Data state
  const [mappings, setMappings] = useState<WorkflowEnvMap[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [canonicalWorkflows, setCanonicalWorkflows] = useState<Map<string, CanonicalWorkflow>>(new Map());
  const [isLoading, setIsLoading] = useState(true);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  // Filter state
  const [selectedEnv, setSelectedEnv] = useState<string>(searchParams.get('environment') || '');
  const [selectedStatus, setSelectedStatus] = useState<string>(searchParams.get('status') || '');
  const [searchCanonicalId, setSearchCanonicalId] = useState<string>(searchParams.get('canonical_id') || '');

  useEffect(() => {
    document.title = 'Workflow Mappings - WorkflowOps';
    loadEnvironments();
  }, []);

  useEffect(() => {
    loadMappings();
  }, [currentPage, pageSize, selectedEnv, selectedStatus, searchCanonicalId]);

  const loadEnvironments = async () => {
    try {
      const response = await apiClient.get('/environments');
      setEnvironments(response.data);
    } catch (error: any) {
      toast.error('Failed to load environments');
      console.error(error);
    }
  };

  const loadMappings = async () => {
    setIsLoading(true);
    try {
      const params: any = {
        page: currentPage,
        pageSize: pageSize,
      };

      if (selectedEnv) params.environmentId = selectedEnv;
      if (selectedStatus) params.status = selectedStatus;
      if (searchCanonicalId) params.canonicalId = searchCanonicalId;

      const response = await apiClient.getWorkflowMappings(params);
      const paginatedData = response.data as PaginatedResponse<WorkflowEnvMap>;

      setMappings(paginatedData.items);
      setTotalItems(paginatedData.total);
      setTotalPages(paginatedData.totalPages);

      // Load canonical workflow details for display names
      await loadCanonicalWorkflowDetails(paginatedData.items);
    } catch (error: any) {
      toast.error('Failed to load workflow mappings');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadCanonicalWorkflowDetails = async (mappingsList: WorkflowEnvMap[]) => {
    const uniqueCanonicalIds = [...new Set(mappingsList.map(m => m.canonicalId))];
    const canonicalMap = new Map<string, CanonicalWorkflow>();

    await Promise.all(
      uniqueCanonicalIds.map(async (canonicalId) => {
        try {
          const response = await apiClient.getCanonicalWorkflow(canonicalId);
          canonicalMap.set(canonicalId, response.data);
        } catch (error) {
          console.error(`Failed to load canonical workflow ${canonicalId}:`, error);
        }
      })
    );

    setCanonicalWorkflows(canonicalMap);
  };

  const handleApplyFilters = () => {
    // Update URL params
    const params = new URLSearchParams();
    if (selectedEnv) params.set('environment', selectedEnv);
    if (selectedStatus) params.set('status', selectedStatus);
    if (searchCanonicalId) params.set('canonical_id', searchCanonicalId);
    setSearchParams(params);

    // Reset to first page when filters change
    setCurrentPage(1);
  };

  const handleClearFilters = () => {
    setSelectedEnv('');
    setSelectedStatus('');
    setSearchCanonicalId('');
    setSearchParams(new URLSearchParams());
    setCurrentPage(1);
  };

  const getEnvironmentName = (envId: string): string => {
    return environments.find(e => e.id === envId)?.name || envId;
  };

  const getCanonicalWorkflowName = (canonicalId: string): string => {
    const workflow = canonicalWorkflows.get(canonicalId);
    return workflow?.displayName || canonicalId.substring(0, 12);
  };

  const getStatusBadgeVariant = (status?: WorkflowMappingStatus) => {
    switch (status) {
      case 'linked':
        return 'default';
      case 'ignored':
        return 'secondary';
      case 'deleted':
        return 'destructive';
      case 'untracked':
        return 'outline';
      case 'missing':
        return 'destructive';
      default:
        return 'outline';
    }
  };

  const getStatusIcon = (status?: WorkflowMappingStatus) => {
    switch (status) {
      case 'linked':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'missing':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'untracked':
        return <AlertTriangle className="h-4 w-4 text-amber-500" />;
      default:
        return <Link2 className="h-4 w-4" />;
    }
  };

  if (isLoading && mappings.length === 0) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Workflow Mappings</h1>
          <p className="text-muted-foreground mt-2">
            View and manage workflow mappings across environments
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadMappings} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={() => navigate('/canonical')}>
            Canonical Workflows
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        {/* Filters Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Filter className="h-5 w-5" />
              Filters
            </CardTitle>
            <CardDescription>Filter mappings by environment, status, or canonical ID</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="environment-filter">Environment</Label>
                <Select value={selectedEnv} onValueChange={setSelectedEnv}>
                  <SelectTrigger id="environment-filter">
                    <SelectValue placeholder="All environments" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All environments</SelectItem>
                    {environments.map(env => (
                      <SelectItem key={env.id} value={env.id}>
                        {env.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="status-filter">Status</Label>
                <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                  <SelectTrigger id="status-filter">
                    <SelectValue placeholder="All statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All statuses</SelectItem>
                    <SelectItem value="linked">Linked</SelectItem>
                    <SelectItem value="untracked">Untracked</SelectItem>
                    <SelectItem value="ignored">Ignored</SelectItem>
                    <SelectItem value="deleted">Deleted</SelectItem>
                    <SelectItem value="missing">Missing</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="canonical-id-filter">Canonical ID</Label>
                <Input
                  id="canonical-id-filter"
                  placeholder="Search by canonical ID..."
                  value={searchCanonicalId}
                  onChange={(e) => setSearchCanonicalId(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleApplyFilters();
                    }
                  }}
                />
              </div>
            </div>

            <div className="flex gap-2 mt-4">
              <Button onClick={handleApplyFilters} size="sm">
                Apply Filters
              </Button>
              <Button onClick={handleClearFilters} size="sm" variant="outline">
                Clear Filters
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Mappings Table */}
        <Card>
          <CardHeader>
            <CardTitle>Workflow Mappings ({totalItems})</CardTitle>
            <CardDescription>Environment-specific workflow mapping details</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Canonical Workflow</TableHead>
                  <TableHead>Environment</TableHead>
                  <TableHead>n8n Workflow ID</TableHead>
                  <TableHead>Content Hash</TableHead>
                  <TableHead>Last Sync</TableHead>
                  <TableHead>Linked At</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mappings.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center text-muted-foreground">
                      {selectedEnv || selectedStatus || searchCanonicalId
                        ? 'No mappings found matching the current filters'
                        : 'No workflow mappings found'}
                    </TableCell>
                  </TableRow>
                ) : (
                  mappings.map((mapping) => (
                    <TableRow key={`${mapping.canonicalId}-${mapping.environmentId}`}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(mapping.status)}
                          <Badge variant={getStatusBadgeVariant(mapping.status)}>
                            {mapping.status || 'unknown'}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="font-medium">
                            {getCanonicalWorkflowName(mapping.canonicalId)}
                          </div>
                          <div className="text-xs text-muted-foreground font-mono">
                            {mapping.canonicalId.substring(0, 12)}...
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{getEnvironmentName(mapping.environmentId)}</Badge>
                      </TableCell>
                      <TableCell>
                        {mapping.n8nWorkflowId ? (
                          <div className="flex items-center gap-1">
                            <span className="font-mono text-sm">{mapping.n8nWorkflowId}</span>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0"
                              onClick={() => navigate(`/workflows/${mapping.n8nWorkflowId}`)}
                            >
                              <ExternalLink className="h-3 w-3" />
                            </Button>
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-sm">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="font-mono text-xs text-muted-foreground">
                          {mapping.envContentHash.substring(0, 8)}...
                        </span>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(mapping.lastEnvSyncAt).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {mapping.linkedAt
                          ? new Date(mapping.linkedAt).toLocaleString()
                          : '-'}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/canonical?canonical_id=${mapping.canonicalId}`)}
                        >
                          View Details
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>

            <PaginationControls
              currentPage={currentPage}
              totalPages={totalPages}
              total={totalItems}
              pageSize={pageSize}
              onPageChange={setCurrentPage}
              onPageSizeChange={(newSize) => {
                setPageSize(newSize);
                setCurrentPage(1); // Reset to first page when page size changes
              }}
              isLoading={isLoading}
              itemLabel="mappings"
            />
          </CardContent>
        </Card>

        {/* Info Alert */}
        {totalItems === 0 && !isLoading && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              No workflow mappings found. Workflow mappings are created automatically when you sync
              workflows from Git or n8n environments. Visit the{' '}
              <Button
                variant="link"
                className="h-auto p-0"
                onClick={() => navigate('/canonical')}
              >
                Canonical Workflows
              </Button>{' '}
              page to sync your environments.
            </AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  );
}
