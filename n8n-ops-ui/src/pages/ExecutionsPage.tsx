// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { api } from '@/lib/api';
import { apiClient } from '@/lib/api-client';
import { useAppStore } from '@/store/use-app-store';
import { useDebounce } from '@/hooks/useDebounce';
import { Search, ArrowUpDown, ArrowUp, ArrowDown, X, ExternalLink, CheckCircle2, XCircle, Clock, Play, Download, RefreshCw, Loader2 } from 'lucide-react';
import type { EnvironmentType } from '@/types';
import { toast } from 'sonner';
import { getDefaultEnvironmentId, resolveEnvironment, sortEnvironments } from '@/lib/environment-utils';

type SortField = 'workflowName' | 'status' | 'startedAt' | 'executionTime';
type SortDirection = 'asc' | 'desc';

export function ExecutionsPage() {
  useEffect(() => {
    document.title = 'Executions - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const [searchInput, setSearchInput] = useState('');
  const debouncedSearch = useDebounce(searchInput, 300);
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>(() => searchParams.get('workflow') || '');
  const [sortField, setSortField] = useState<SortField>('startedAt');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [isSyncing, setIsSyncing] = useState(false);

  // Update URL when workflow filter changes
  useEffect(() => {
    if (selectedWorkflow) {
      searchParams.set('workflow', selectedWorkflow);
    } else {
      searchParams.delete('workflow');
    }
    setSearchParams(searchParams, { replace: true });
  }, [selectedWorkflow, searchParams, setSearchParams]);

  // Fetch environments to get environment ID
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.getEnvironments(),
  });

  const availableEnvironments = useMemo(() => {
    if (!environments?.data) return [];
    return sortEnvironments(environments.data.filter((env: any) => env.isActive));
  }, [environments?.data]);

  const currentEnvironment = useMemo(
    () => resolveEnvironment(availableEnvironments, selectedEnvironment),
    [availableEnvironments, selectedEnvironment]
  );
  const currentEnvironmentId = currentEnvironment?.id;

  useEffect(() => {
    if (availableEnvironments.length === 0) return;
    const nextId = currentEnvironment?.id || getDefaultEnvironmentId(availableEnvironments);
    if (nextId && selectedEnvironment !== nextId) {
      setSelectedEnvironment(nextId);
    }
  }, [availableEnvironments, currentEnvironment?.id, selectedEnvironment, setSelectedEnvironment]);

  // Get the current environment's base URL
  // (currentEnvironment is now resolved from availableEnvironments above)

  // Map frontend sort field names to backend names
  const sortFieldMap: Record<SortField, string> = {
    workflowName: 'workflow_name',
    status: 'status',
    startedAt: 'started_at',
    executionTime: 'execution_time',
  };

  // Server-side paginated executions query (optimized)
  const { data: executionsResponse, isLoading, isFetching, refetch } = useQuery({
    queryKey: [
      'executions-paginated',
      currentEnvironmentId,
      currentPage,
      pageSize,
      debouncedSearch,
      selectedStatus,
      selectedWorkflow,
      sortField,
      sortDirection,
    ],
    queryFn: () =>
      currentEnvironmentId
        ? apiClient.getExecutionsPaginated(currentEnvironmentId, currentPage, pageSize, {
            workflowId: selectedWorkflow || undefined,
            statusFilter: selectedStatus || undefined,
            search: debouncedSearch || undefined,
            sortField: sortFieldMap[sortField],
            sortDirection,
          })
        : Promise.resolve({ data: { executions: [], total: 0, page: 1, page_size: pageSize, total_pages: 0 } }),
    enabled: !!currentEnvironmentId,
    keepPreviousData: true,
    staleTime: 60 * 1000, // 1 minute
  });

  // Extract data from paginated response
  const executions = executionsResponse?.data?.executions || [];
  const totalExecutions = executionsResponse?.data?.total || 0;
  const totalPages = executionsResponse?.data?.total_pages || 1;

  // Sync mutation to refresh from N8N (executions only)
  const syncMutation = useMutation({
    mutationFn: async () => {
      if (!currentEnvironmentId) return [];
      const result = await api.syncExecutionsOnly(currentEnvironmentId);
      return [{ env: currentEnvironment?.name || currentEnvironmentId, ...result.data }];
    },
    onSuccess: (results) => {
      setIsSyncing(false);
      const totalSynced = results.reduce((sum, r) => sum + (r.synced || 0), 0);
      toast.success(`Synced ${totalSynced} executions from N8N`);
      queryClient.invalidateQueries({ queryKey: ['executions-paginated'] });
    },
    onError: (error: any) => {
      setIsSyncing(false);
      const message = error.response?.data?.detail || 'Failed to sync from N8N';
      toast.error(message);
    },
  });

  const handleSyncFromN8N = () => {
    toast.info('Syncing from N8N...');
    setIsSyncing(true);
    syncMutation.mutate();
  };

  // Get unique workflows from current page for the filter dropdown
  // Note: With server-side pagination, we only have workflows from the current page
  const uniqueWorkflows = useMemo(() => {
    if (!executions?.length) return [];
    const workflowMap = new Map<string, string>();
    executions.forEach((execution) => {
      if (!workflowMap.has(execution.workflowId)) {
        workflowMap.set(execution.workflowId, execution.workflowName || execution.workflowId);
      }
    });
    return Array.from(workflowMap.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [executions]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearch, selectedStatus, selectedWorkflow, currentEnvironmentId]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection(field === 'startedAt' ? 'desc' : 'asc');
    }
  };

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="h-3 w-3 ml-1 inline opacity-30" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="h-3 w-3 ml-1 inline" />
    ) : (
      <ArrowDown className="h-3 w-3 ml-1 inline" />
    );
  };

  const clearFilters = () => {
    setSearchInput('');
    setSelectedStatus('');
    setSelectedWorkflow('');
  };

  const hasActiveFilters = searchInput || selectedStatus || selectedWorkflow;

  const openExecution = (executionId: string, workflowId: string) => {
    if (currentEnvironment?.baseUrl) {
      const url = `${currentEnvironment.baseUrl}/workflow/${workflowId}/executions/${executionId}`;
      window.open(url, '_blank');
    } else {
      toast.error('N8N URL not configured for this environment');
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return (
          <Badge variant="success" className="flex items-center gap-1 w-fit">
            <CheckCircle2 className="h-3 w-3" />
            Success
          </Badge>
        );
      case 'error':
        return (
          <Badge variant="destructive" className="flex items-center gap-1 w-fit">
            <XCircle className="h-3 w-3" />
            Error
          </Badge>
        );
      case 'running':
        return (
          <Badge variant="default" className="flex items-center gap-1 w-fit">
            <Play className="h-3 w-3" />
            Running
          </Badge>
        );
      case 'waiting':
        return (
          <Badge variant="outline" className="flex items-center gap-1 w-fit">
            <Clock className="h-3 w-3" />
            Waiting
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="flex items-center gap-1 w-fit">
            {status}
          </Badge>
        );
    }
  };

  const formatDuration = (milliseconds?: number) => {
    if (!milliseconds) return '-';

    // Always display in seconds with 3 decimal places for consistency
    // This makes it easy to see longer running executions at a glance
    const seconds = milliseconds / 1000;

    if (seconds >= 60) {
      // For executions over 1 minute, show minutes and seconds
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = (seconds % 60).toFixed(1);
      return `${minutes}m ${remainingSeconds}s`;
    }

    // For executions under 1 minute, show seconds with 3 decimal places
    return `${seconds.toFixed(3)}s`;
  };

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(date);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Executions</h1>
          <p className="text-muted-foreground">
            View workflow execution history from n8n
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

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Search Filter */}
            <div className="space-y-2">
              <Label htmlFor="search">Search</Label>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="search"
                  placeholder="Search by workflow name..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>

            {/* Workflow Filter */}
            <div className="space-y-2">
              <Label htmlFor="workflow">Workflow</Label>
              <select
                id="workflow"
                value={selectedWorkflow}
                onChange={(e) => setSelectedWorkflow(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="" className="bg-background text-foreground">All Workflows</option>
                {uniqueWorkflows.map((workflow) => (
                  <option key={workflow.id} value={workflow.id} className="bg-background text-foreground">
                    {workflow.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Status Filter */}
            <div className="space-y-2">
              <Label htmlFor="status">Status</Label>
              <select
                id="status"
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="" className="bg-background text-foreground">All Status</option>
                <option value="success" className="bg-background text-foreground">Success</option>
                <option value="error" className="bg-background text-foreground">Error</option>
                <option value="running" className="bg-background text-foreground">Running</option>
                <option value="waiting" className="bg-background text-foreground">Waiting</option>
              </select>
            </div>

            {/* Environment Filter */}
            <div className="space-y-2">
              <Label htmlFor="environment">Environment</Label>
              <select
                id="environment"
                value={currentEnvironmentId || ''}
                onChange={(e) => setSelectedEnvironment(e.target.value as EnvironmentType)}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {availableEnvironments.map((env: any) => (
                  <option key={env.id} value={env.id} className="bg-background text-foreground">
                    {env.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {hasActiveFilters && (
            <div className="mt-4 flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {totalExecutions} execution{totalExecutions !== 1 ? 's' : ''} found
              </span>
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="h-3 w-3 mr-1" />
                Clear filters
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Executions in {currentEnvironment?.name || currentEnvironment?.type || selectedEnvironment}</CardTitle>
          <CardDescription>
            View execution history for workflows in the selected environment
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && !isFetching ? (
            <div className="text-center py-8">Loading executions...</div>
          ) : totalExecutions === 0 && !isFetching ? (
            <div className="text-center py-8 text-muted-foreground">
              {hasActiveFilters ? 'No executions match your filters' : 'No executions found'}
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('workflowName')}>
                      Workflow {getSortIcon('workflowName')}
                    </TableHead>
                    <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('status')}>
                      Status {getSortIcon('status')}
                    </TableHead>
                    <TableHead>Mode</TableHead>
                    <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('startedAt')}>
                      Started At {getSortIcon('startedAt')}
                    </TableHead>
                    <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('executionTime')}>
                      Duration {getSortIcon('executionTime')}
                    </TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {executions.map((execution) => (
                    <TableRow key={execution.id}>
                      <TableCell className="font-medium">
                        <Link
                          to={`/workflows/${execution.workflowId}?environment=${selectedEnvironment}`}
                          className="text-primary hover:underline"
                        >
                          {execution.workflowName || execution.workflowId}
                        </Link>
                      </TableCell>
                      <TableCell>
                        {getStatusBadge(execution.status)}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {execution.mode}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDateTime(execution.startedAt)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDuration(execution.executionTime)}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => openExecution(execution.executionId, execution.workflowId)}
                          title="View execution in N8N"
                        >
                          <ExternalLink className="h-3 w-3 mr-1" />
                          N8N
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
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
                    Showing {totalExecutions > 0 ? ((currentPage - 1) * pageSize) + 1 : 0} to {Math.min(currentPage * pageSize, totalExecutions)} of {totalExecutions} executions
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
                      Page {currentPage} of {totalPages || 1}
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
    </div>
  );
}
