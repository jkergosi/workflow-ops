import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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
import { useAppStore } from '@/store/use-app-store';
import { Search, ArrowUpDown, ArrowUp, ArrowDown, X, ExternalLink, CheckCircle2, XCircle, Clock, Play, Download, RefreshCw } from 'lucide-react';
import type { EnvironmentType } from '@/types';
import { toast } from 'sonner';

type SortField = 'workflowName' | 'status' | 'startedAt' | 'executionTime';
type SortDirection = 'asc' | 'desc';

export function ExecutionsPage() {
  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [sortField, setSortField] = useState<SortField>('startedAt');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [isSyncing, setIsSyncing] = useState(false);

  // Fetch environments to get environment ID
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.getEnvironments(),
  });

  // Get current environment ID
  const currentEnvironmentId = useMemo(() => {
    if (!environments?.data) return undefined;
    const env = environments.data.find((e) => e.type === selectedEnvironment);
    return env?.id;
  }, [environments, selectedEnvironment]);

  // Get the current environment's base URL
  const currentEnvironment = useMemo(() => {
    if (!environments?.data) return undefined;
    return environments.data.find((env) => env.type === selectedEnvironment);
  }, [environments, selectedEnvironment]);

  // Fetch executions from database
  const { data: executions, isLoading, refetch } = useQuery({
    queryKey: ['executions', currentEnvironmentId],
    queryFn: async () => {
      if (!currentEnvironmentId) return { data: [] };
      return api.getExecutions(currentEnvironmentId);
    },
    enabled: !!currentEnvironmentId,
  });

  // Sync mutation to refresh from N8N (executions only)
  const syncMutation = useMutation({
    mutationFn: async () => {
      const envsToSync = environments?.data?.filter((env: any) =>
        selectedEnvironment === 'dev' || env.type === selectedEnvironment
      ) || [];

      const results = [];
      for (const env of envsToSync) {
        const result = await api.syncExecutionsOnly(env.id);
        results.push({ env: env.name, ...result.data });
      }
      return results;
    },
    onSuccess: (results) => {
      setIsSyncing(false);
      const totalExecutions = results.reduce((sum, r) => sum + (r.synced || 0), 0);
      toast.success(`Synced ${totalExecutions} executions from N8N`);
      queryClient.invalidateQueries({ queryKey: ['executions'] });
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

  // Filter and sort executions
  const filteredAndSortedExecutions = useMemo(() => {
    if (!executions?.data) return [];

    let result = [...executions.data];

    // Apply search filter (workflow name)
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter((execution) => {
        const matchesWorkflowName = execution.workflowName?.toLowerCase().includes(query);
        const matchesWorkflowId = execution.workflowId.toLowerCase().includes(query);
        return matchesWorkflowName || matchesWorkflowId;
      });
    }

    // Apply status filter
    if (selectedStatus) {
      result = result.filter((execution) => execution.status === selectedStatus);
    }

    // Apply sorting
    result.sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (sortField) {
        case 'workflowName':
          aValue = (a.workflowName || a.workflowId).toLowerCase();
          bValue = (b.workflowName || b.workflowId).toLowerCase();
          break;
        case 'status':
          aValue = a.status;
          bValue = b.status;
          break;
        case 'startedAt':
          aValue = new Date(a.startedAt).getTime();
          bValue = new Date(b.startedAt).getTime();
          break;
        case 'executionTime':
          aValue = a.executionTime || 0;
          bValue = b.executionTime || 0;
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  }, [executions, searchQuery, selectedStatus, sortField, sortDirection]);

  // Pagination calculations
  const { paginatedExecutions, totalPages, totalExecutions } = useMemo(() => {
    const total = filteredAndSortedExecutions.length;
    const pages = Math.ceil(total / pageSize);
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const paginated = filteredAndSortedExecutions.slice(startIndex, endIndex);

    return {
      paginatedExecutions: paginated,
      totalPages: pages,
      totalExecutions: total,
    };
  }, [filteredAndSortedExecutions, currentPage, pageSize]);

  // Reset to page 1 when filters change
  const resetPage = () => {
    if (currentPage !== 1) {
      setCurrentPage(1);
    }
  };

  // Reset page when filters, search, or environment changes
  useEffect(() => {
    resetPage();
  }, [searchQuery, selectedStatus, selectedEnvironment]);

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
    setSearchQuery('');
    setSelectedStatus('');
  };

  const hasActiveFilters = searchQuery || selectedStatus;

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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Search Filter */}
            <div className="space-y-2">
              <Label htmlFor="search">Search</Label>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="search"
                  placeholder="Search by workflow name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8"
                />
              </div>
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
                <option value="">All Status</option>
                <option value="success">Success</option>
                <option value="error">Error</option>
                <option value="running">Running</option>
                <option value="waiting">Waiting</option>
              </select>
            </div>

            {/* Environment Filter */}
            <div className="space-y-2">
              <Label htmlFor="environment">Environment</Label>
              <select
                id="environment"
                value={selectedEnvironment}
                onChange={(e) => setSelectedEnvironment(e.target.value as EnvironmentType)}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="dev">Development</option>
                <option value="staging">Staging</option>
                <option value="production">Production</option>
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
          <CardTitle>Executions in {selectedEnvironment}</CardTitle>
          <CardDescription>
            View execution history for workflows in the selected environment
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading executions...</div>
          ) : totalExecutions === 0 ? (
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
                  {paginatedExecutions.map((execution) => (
                    <TableRow key={execution.id}>
                      <TableCell className="font-medium">
                        {execution.workflowName || execution.workflowId}
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
                      <option value={10}>10</option>
                      <option value={25}>25</option>
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                    </select>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, totalExecutions)} of {totalExecutions} executions
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                  >
                    First
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(currentPage - 1)}
                    disabled={currentPage === 1}
                  >
                    Previous
                  </Button>
                  <div className="flex items-center gap-1">
                    <span className="text-sm">
                      Page {currentPage} of {totalPages}
                    </span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(currentPage + 1)}
                    disabled={currentPage === totalPages}
                  >
                    Next
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage === totalPages}
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
