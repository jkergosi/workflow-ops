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
import {
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Filter,
  GitBranch,
  AlertTriangle,
  Plus,
  Edit3
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api-client';
import type {
  WorkflowDiffState,
  CanonicalWorkflow,
  Environment,
  CanonicalWorkflowDiffStatus,
  PaginatedResponse
} from '@/types';

export function DiffStatesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Data state
  const [diffStates, setDiffStates] = useState<WorkflowDiffState[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [canonicalWorkflows, setCanonicalWorkflows] = useState<Map<string, CanonicalWorkflow>>(new Map());
  const [isLoading, setIsLoading] = useState(true);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  // Filter state
  const [selectedSourceEnv, setSelectedSourceEnv] = useState<string>(searchParams.get('source_env') || '');
  const [selectedTargetEnv, setSelectedTargetEnv] = useState<string>(searchParams.get('target_env') || '');
  const [searchCanonicalId, setSearchCanonicalId] = useState<string>(searchParams.get('canonical_id') || '');

  useEffect(() => {
    document.title = 'Workflow Diff States - WorkflowOps';
    loadEnvironments();
  }, []);

  useEffect(() => {
    loadDiffStates();
  }, [currentPage, pageSize, selectedSourceEnv, selectedTargetEnv, searchCanonicalId]);

  const loadEnvironments = async () => {
    try {
      const response = await apiClient.get('/environments');
      setEnvironments(response.data);
    } catch (error: any) {
      toast.error('Failed to load environments');
      console.error(error);
    }
  };

  const loadDiffStates = async () => {
    setIsLoading(true);
    try {
      const params: any = {
        page: currentPage,
        pageSize: pageSize,
      };

      if (selectedSourceEnv) params.sourceEnvId = selectedSourceEnv;
      if (selectedTargetEnv) params.targetEnvId = selectedTargetEnv;
      if (searchCanonicalId) params.canonicalId = searchCanonicalId;

      const response = await apiClient.getDiffStates(params);
      const paginatedData = response.data as PaginatedResponse<WorkflowDiffState>;

      setDiffStates(paginatedData.items);
      setTotalItems(paginatedData.total);
      setTotalPages(paginatedData.totalPages);

      // Load canonical workflow details for display names
      await loadCanonicalWorkflowDetails(paginatedData.items);
    } catch (error: any) {
      toast.error('Failed to load workflow diff states');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadCanonicalWorkflowDetails = async (diffStatesList: WorkflowDiffState[]) => {
    const uniqueCanonicalIds = [...new Set(diffStatesList.map(d => d.canonicalId))];
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
    if (selectedSourceEnv) params.set('source_env', selectedSourceEnv);
    if (selectedTargetEnv) params.set('target_env', selectedTargetEnv);
    if (searchCanonicalId) params.set('canonical_id', searchCanonicalId);
    setSearchParams(params);

    // Reset to first page when filters change
    setCurrentPage(1);
  };

  const handleClearFilters = () => {
    setSelectedSourceEnv('');
    setSelectedTargetEnv('');
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

  const getDiffStatusBadgeVariant = (status: CanonicalWorkflowDiffStatus) => {
    switch (status) {
      case 'unchanged':
        return 'secondary';
      case 'modified':
        return 'default';
      case 'added':
        return 'default';
      case 'target_only':
        return 'destructive';
      case 'target_hotfix':
        return 'outline';
      default:
        return 'outline';
    }
  };

  const getDiffStatusIcon = (status: CanonicalWorkflowDiffStatus) => {
    switch (status) {
      case 'unchanged':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'modified':
        return <Edit3 className="h-4 w-4 text-blue-500" />;
      case 'added':
        return <Plus className="h-4 w-4 text-green-500" />;
      case 'target_only':
        return <AlertTriangle className="h-4 w-4 text-amber-500" />;
      case 'target_hotfix':
        return <AlertCircle className="h-4 w-4 text-orange-500" />;
      default:
        return <AlertCircle className="h-4 w-4" />;
    }
  };

  const getDiffStatusDescription = (status: CanonicalWorkflowDiffStatus): string => {
    switch (status) {
      case 'unchanged':
        return 'Workflow is identical in both environments';
      case 'modified':
        return 'Workflow has been modified between environments';
      case 'added':
        return 'Workflow exists in source but not in target';
      case 'target_only':
        return 'Workflow only exists in target environment';
      case 'target_hotfix':
        return 'Target has modifications not present in source';
      default:
        return 'Unknown status';
    }
  };

  if (isLoading && diffStates.length === 0) {
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
          <h1 className="text-3xl font-bold">Workflow Diff States</h1>
          <p className="text-muted-foreground mt-2">
            View workflow differences between environments
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadDiffStates} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={() => navigate('/canonical/workflows')}>
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
            <CardDescription>Filter diff states by environments or canonical ID</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="source-env-filter">Source Environment</Label>
                <Select value={selectedSourceEnv} onValueChange={setSelectedSourceEnv}>
                  <SelectTrigger id="source-env-filter">
                    <SelectValue placeholder="All source environments" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All source environments</SelectItem>
                    {environments.map(env => (
                      <SelectItem key={env.id} value={env.id}>
                        {env.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="target-env-filter">Target Environment</Label>
                <Select value={selectedTargetEnv} onValueChange={setSelectedTargetEnv}>
                  <SelectTrigger id="target-env-filter">
                    <SelectValue placeholder="All target environments" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All target environments</SelectItem>
                    {environments.map(env => (
                      <SelectItem key={env.id} value={env.id}>
                        {env.name}
                      </SelectItem>
                    ))}
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

        {/* Diff States Table */}
        <Card>
          <CardHeader>
            <CardTitle>Workflow Diff States ({totalItems})</CardTitle>
            <CardDescription>Differences detected between environment pairs</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Canonical Workflow</TableHead>
                  <TableHead>Source Environment</TableHead>
                  <TableHead>Target Environment</TableHead>
                  <TableHead>Computed At</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {diffStates.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-muted-foreground">
                      {selectedSourceEnv || selectedTargetEnv || searchCanonicalId
                        ? 'No diff states found matching the current filters'
                        : 'No workflow diff states found'}
                    </TableCell>
                  </TableRow>
                ) : (
                  diffStates.map((diffState) => (
                    <TableRow key={diffState.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getDiffStatusIcon(diffState.diffStatus)}
                          <div className="space-y-1">
                            <Badge variant={getDiffStatusBadgeVariant(diffState.diffStatus)}>
                              {diffState.diffStatus}
                            </Badge>
                            <div className="text-xs text-muted-foreground">
                              {getDiffStatusDescription(diffState.diffStatus)}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="font-medium">
                            {getCanonicalWorkflowName(diffState.canonicalId)}
                          </div>
                          <div className="text-xs text-muted-foreground font-mono">
                            {diffState.canonicalId.substring(0, 12)}...
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="flex items-center gap-1 w-fit">
                          <GitBranch className="h-3 w-3" />
                          {getEnvironmentName(diffState.sourceEnvId)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="flex items-center gap-1 w-fit">
                          <GitBranch className="h-3 w-3" />
                          {getEnvironmentName(diffState.targetEnvId)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(diffState.computedAt).toLocaleString()}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/canonical/workflows?canonical_id=${diffState.canonicalId}`)}
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
              itemLabel="diff states"
            />
          </CardContent>
        </Card>

        {/* Info Alert */}
        {totalItems === 0 && !isLoading && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              No workflow diff states found. Diff states are computed automatically when you sync
              workflows between environments. Visit the{' '}
              <Button
                variant="link"
                className="h-auto p-0"
                onClick={() => navigate('/canonical/workflows')}
              >
                Canonical Workflows
              </Button>{' '}
              page to sync your environments and compute diffs.
            </AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  );
}
