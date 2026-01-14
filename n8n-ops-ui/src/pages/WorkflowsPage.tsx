// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useMemo, useEffect } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { MultiSelect } from '@/components/ui/multi-select';
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
import { api } from '@/lib/api';
import { apiClient } from '@/lib/api-client';
import { useAppStore } from '@/store/use-app-store';
import { useDebounce } from '@/hooks/useDebounce';
import { Upload, PlayCircle, PauseCircle, Search, ArrowUpDown, ArrowUp, ArrowDown, X, Edit, Trash2, Loader2, RefreshCw, ExternalLink, CheckCircle2, AlertCircle, RefreshCcw, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { Workflow, EnvironmentType } from '@/types';

// Workflow governance components
import { WorkflowActionsMenu } from '@/components/workflow/WorkflowActionsMenu';
import { DirectEditWarningDialog } from '@/components/workflow/DirectEditWarningDialog';
import { HardDeleteConfirmDialog } from '@/components/workflow/HardDeleteConfirmDialog';
import { getWorkflowActionPolicy } from '@/lib/workflow-action-policy';
import { useFeatures } from '@/lib/features';
import { useAuth } from '@/lib/auth';
import { getDefaultEnvironmentId, resolveEnvironment, sortEnvironments } from '@/lib/environment-utils';

type SortField = 'name' | 'description' | 'active' | 'executions' | 'updatedAt';
type SortDirection = 'asc' | 'desc';

export function WorkflowsPage() {
  useEffect(() => {
    document.title = 'Workflows - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);
  const [searchParams, setSearchParams] = useSearchParams();

  // Governance hooks
  const { planName } = useFeatures();
  const { user } = useAuth();

  // Initialize searchQuery from URL params
  const [searchInput, setSearchInput] = useState(() => searchParams.get('search') || '');
  // Debounce search to prevent excessive API calls while typing
  const debouncedSearch = useDebounce(searchInput, 300);

  // Initialize selectedTag from URL params
  const [selectedTag, setSelectedTag] = useState<string[]>(() => {
    const tagParam = searchParams.get('tag');
    return tagParam ? [tagParam] : [];
  });

  // Update URL when search or tag changes
  useEffect(() => {
    if (debouncedSearch) {
      searchParams.set('search', debouncedSearch);
    } else {
      searchParams.delete('search');
    }
    if (selectedTag.length > 0) {
      searchParams.set('tag', selectedTag[0]);
    } else {
      searchParams.delete('tag');
    }
    setSearchParams(searchParams, { replace: true });
  }, [debouncedSearch, selectedTag, searchParams, setSearchParams]);
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [workflowToEdit, setWorkflowToEdit] = useState<Workflow | null>(null);
  const [workflowToDelete, setWorkflowToDelete] = useState<Workflow | null>(null);

  // Governance dialog state
  const [driftWarningOpen, setDriftWarningOpen] = useState(false);
  const [hardDeleteOpen, setHardDeleteOpen] = useState(false);
  const [pendingEditWorkflow, setPendingEditWorkflow] = useState<Workflow | null>(null);
  const [pendingDeleteWorkflow, setPendingDeleteWorkflow] = useState<Workflow | null>(null);

  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [editForm, setEditForm] = useState({
    name: '',
    active: false,
    tags: [] as string[],
  });

  // Fetch environments to get the n8n base URL for opening workflows
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.getEnvironments(),
  });

  // Get available environments for the tenant (filtered and sorted)
  const availableEnvironments = useMemo(() => {
    if (!environments?.data) return [];
    return sortEnvironments(environments.data.filter((env) => env.isActive));
  }, [environments]);

  // Get the current environment's base URL and ID
  // selectedEnvironment can now be either a type string or an environment ID
  const currentEnvironment = resolveEnvironment(environments?.data, selectedEnvironment);

  // Server-side paginated workflow query (optimized)
  const { data: workflowsResponse, isLoading, isFetching } = useQuery({
    queryKey: [
      'workflows-paginated',
      currentEnvironment?.id,
      currentPage,
      pageSize,
      debouncedSearch,
      selectedTag,
      selectedStatus,
      sortField,
      sortDirection,
    ],
    queryFn: () =>
      currentEnvironment?.id
        ? apiClient.getWorkflowsPaginated(currentEnvironment.id, currentPage, pageSize, {
            search: debouncedSearch || undefined,
            tags: selectedTag.length > 0 ? selectedTag : undefined,
            statusFilter: selectedStatus || undefined,
            sortField: sortField === 'executions' ? 'updatedAt' : sortField, // executions sorted client-side
            sortDirection,
          })
        : Promise.resolve({ data: { workflows: [], total: 0, page: 1, page_size: pageSize, total_pages: 0 } }),
    enabled: !!currentEnvironment?.id,
    keepPreviousData: true, // Keep old data while loading new page for smooth UX
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  // Extract data from paginated response
  // Support both standardized format (items, pageSize, totalPages) and legacy format (workflows, page_size, total_pages)
  const workflows = workflowsResponse?.data?.items || workflowsResponse?.data?.workflows || [];
  const totalWorkflows = workflowsResponse?.data?.total || 0;
  const totalPages = workflowsResponse?.data?.totalPages || workflowsResponse?.data?.total_pages || 1;

  // Set default environment if none selected and environments are available
  useEffect(() => {
    if (availableEnvironments.length === 0) return;
    const resolved = resolveEnvironment(availableEnvironments, selectedEnvironment);
    const nextId = resolved?.id || getDefaultEnvironmentId(availableEnvironments);
    if (nextId && selectedEnvironment !== nextId) {
      setSelectedEnvironment(nextId);
    }
  }, [availableEnvironments, selectedEnvironment, setSelectedEnvironment]);

  // Fetch execution counts for workflows (optimized endpoint)
  const { data: executionCounts } = useQuery({
    queryKey: ['workflow-execution-counts', currentEnvironment?.id],
    queryFn: () => currentEnvironment?.id ? api.getWorkflowExecutionCounts(currentEnvironment.id) : Promise.resolve({ data: {} }),
    enabled: !!currentEnvironment?.id,
  });

  // Use execution counts directly from API (no client-side aggregation needed)
  const executionCountsByWorkflow = executionCounts?.data || {};

  const openInN8N = (workflowId: string) => {
    if (currentEnvironment?.baseUrl) {
      window.open(`${currentEnvironment.baseUrl}/workflow/${workflowId}`, '_blank');
    } else {
      toast.error('N8N URL not configured for this environment');
    }
  };

  const updateMutation = useMutation({
    mutationFn: async ({ workflowId }: { workflowId: string }) => {
      if (!workflowToEdit) throw new Error('No workflow to edit');
      
      const nameChanged = editForm.name !== workflowToEdit.name;
      const tagsChanged = JSON.stringify(editForm.tags.sort()) !== JSON.stringify((workflowToEdit.tags || []).sort());
      const statusChanged = editForm.active !== workflowToEdit.active;
      
      if (!nameChanged && !tagsChanged && !statusChanged) {
        return { noChanges: true };
      }
      
      const promises: Promise<any>[] = [];
      
      if (nameChanged) {
        const fullWorkflow = await api.getWorkflow(workflowId, selectedEnvironment);
        const workflowData = {
          ...fullWorkflow.data,
          name: editForm.name,
        };
        promises.push(api.updateWorkflow(workflowId, selectedEnvironment, workflowData));
      }
      
      if (tagsChanged) {
        promises.push(api.updateWorkflowTags(workflowId, selectedEnvironment, editForm.tags));
      }
      
      if (statusChanged) {
        if (editForm.active) {
          promises.push(api.activateWorkflow(workflowId, selectedEnvironment));
        } else {
          promises.push(api.deactivateWorkflow(workflowId, selectedEnvironment));
        }
      }
      
      await Promise.all(promises);
      return { noChanges: false };
    },
    onSuccess: async (result) => {
      if (result?.noChanges) {
        toast.info('No changes to save');
        setEditDialogOpen(false);
        setWorkflowToEdit(null);
        return;
      }
      toast.success('Workflow updated successfully');

      // Invalidate paginated workflows query to refetch
      queryClient.invalidateQueries({ queryKey: ['workflows-paginated'] });

      setEditDialogOpen(false);
      setWorkflowToEdit(null);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to update workflow';
      toast.error(message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ workflowId }: { workflowId: string }) => {
      return api.deleteWorkflow(workflowId, selectedEnvironment);
    },
    onSuccess: () => {
      toast.success('Workflow deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['workflows-paginated'] });
      setDeleteDialogOpen(false);
      setWorkflowToDelete(null);
    },
    onError: () => {
      toast.error('Failed to delete workflow');
      setDeleteDialogOpen(false);
    },
  });

  // Archive mutation (soft delete)
  const archiveMutation = useMutation({
    mutationFn: (workflowId: string) =>
      api.archiveWorkflow(workflowId, selectedEnvironment!),
    onSuccess: () => {
      toast.success('Workflow archived successfully');
      queryClient.invalidateQueries({ queryKey: ['workflows-paginated'] });
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to archive workflow';
      toast.error(message);
    },
  });

  // Hard delete mutation (permanent delete)
  const hardDeleteMutation = useMutation({
    mutationFn: (workflowId: string) =>
      api.permanentlyDeleteWorkflow(workflowId, selectedEnvironment!),
    onSuccess: () => {
      toast.success('Workflow permanently deleted');
      queryClient.invalidateQueries({ queryKey: ['workflows-paginated'] });
      setHardDeleteOpen(false);
      setPendingDeleteWorkflow(null);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to delete workflow';
      toast.error(message);
      setHardDeleteOpen(false);
    },
  });

  // Get all unique tags from current page of workflows
  // Note: With server-side pagination, we only have tags from the current page
  // For a complete tag list, you could use a separate endpoint
  const allTags = useMemo(() => {
    if (!workflows?.length) return [];
    const tags = new Set<string>();
    workflows.forEach((workflow) => {
      workflow.tags?.forEach((tag) => {
        const tagName = typeof tag === 'string' ? tag : tag.name;
        tags.add(tagName);
      });
    });
    return Array.from(tags).sort();
  }, [workflows]);

  // Sort workflows by execution count if that's the sort field (client-side only for this field)
  const displayWorkflows = useMemo(() => {
    if (sortField !== 'executions') {
      return workflows; // Already sorted by server
    }
    // Sort by execution count client-side
    return [...workflows].sort((a, b) => {
      const aCount = executionCountsByWorkflow[a.id] || 0;
      const bCount = executionCountsByWorkflow[b.id] || 0;
      return sortDirection === 'asc' ? aCount - bCount : bCount - aCount;
    });
  }, [workflows, sortField, sortDirection, executionCountsByWorkflow]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [debouncedSearch, selectedTag, selectedStatus, currentEnvironment?.id]);

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
      return <ArrowUpDown className="h-3 w-3 ml-1 inline opacity-30" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="h-3 w-3 ml-1 inline" />
    ) : (
      <ArrowDown className="h-3 w-3 ml-1 inline" />
    );
  };

  const getSyncStatusDisplay = (syncStatus?: string) => {
    if (!syncStatus) {
      return (
        <Badge variant="outline" className="text-xs">
          Unknown
        </Badge>
      );
    }

    switch (syncStatus) {
      case 'in_sync':
        return (
          <Badge variant="outline" className="text-xs bg-green-50 text-green-700 border-green-200">
            <CheckCircle2 className="h-3 w-3 mr-1" />
            In Sync
          </Badge>
        );
      case 'local_changes':
        return (
          <Badge variant="outline" className="text-xs bg-yellow-50 text-yellow-700 border-yellow-200">
            <AlertCircle className="h-3 w-3 mr-1" />
            Local Changes
          </Badge>
        );
      case 'update_available':
        return (
          <Badge variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">
            <RefreshCcw className="h-3 w-3 mr-1" />
            Update Available
          </Badge>
        );
      case 'conflict':
        return (
          <Badge variant="outline" className="text-xs bg-red-50 text-red-700 border-red-200">
            <AlertTriangle className="h-3 w-3 mr-1" />
            Conflict
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="text-xs">
            {syncStatus}
          </Badge>
        );
    }
  };

  const clearFilters = () => {
    setSearchInput('');
    setSelectedTag([]);
    setSelectedStatus('');
  };


  const hasActiveFilters = searchInput || selectedTag.length > 0 || selectedStatus;

  // Opens the edit dialog directly (called after policy check or confirmation)
  const openEditDialog = (workflow: Workflow) => {
    setWorkflowToEdit(workflow);
    setEditForm({
      name: workflow.name,
      active: workflow.active,
      tags: (workflow.tags || []).map((tag) => typeof tag === 'string' ? tag : tag.name),
    });
    setEditDialogOpen(true);
  };

  // Edit click handler - checks policy and shows warning if needed
  const handleEditClick = (workflow: Workflow) => {
    // Use pure function (NOT hook) inside event handler
    const hasDrift = workflow.syncStatus === 'local_changes' || workflow.syncStatus === 'conflict';
    const policy = getWorkflowActionPolicy(
      currentEnvironment || null,
      planName,
      user?.role || 'user',
      hasDrift
    );

    if (policy.editRequiresConfirmation) {
      setPendingEditWorkflow(workflow);
      setDriftWarningOpen(true);
    } else {
      openEditDialog(workflow);
    }
  };

  // Called when user confirms drift warning
  const handleDriftWarningConfirm = () => {
    if (pendingEditWorkflow) {
      openEditDialog(pendingEditWorkflow);
      setPendingEditWorkflow(null);
    }
    setDriftWarningOpen(false);
  };

  const handleEditSubmit = () => {
    if (!workflowToEdit) return;
    if (!editForm.name.trim()) {
      toast.error('Workflow name is required');
      return;
    }
    updateMutation.mutate({
      workflowId: workflowToEdit.id,
    });
  };

  // Soft delete (archive) - hides workflow but doesn't remove from N8N
  const handleSoftDelete = (workflow: Workflow) => {
    archiveMutation.mutate(workflow.id);
  };

  // Hard delete click - shows confirmation dialog
  const handleHardDeleteClick = (workflow: Workflow) => {
    setPendingDeleteWorkflow(workflow);
    setHardDeleteOpen(true);
  };

  // Called when user confirms hard delete
  const handleHardDeleteConfirm = () => {
    if (pendingDeleteWorkflow) {
      hardDeleteMutation.mutate(pendingDeleteWorkflow.id);
    }
  };

  // Legacy delete handler (for backward compatibility with existing dialogs)
  const handleDeleteClick = (workflow: Workflow) => {
    setWorkflowToDelete(workflow);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (workflowToDelete) {
      deleteMutation.mutate({ workflowId: workflowToDelete.id });
    }
  };

  // Governance handlers for WorkflowActionsMenu
  const handleCreateDeployment = (workflow: Workflow) => {
    // Navigate to new deployment page with workflow context
    navigate(`/promote?workflow=${workflow.id}&source=${currentEnvironment?.id}`);
  };

  const handleViewDriftIncident = (workflow: Workflow) => {
    if (currentEnvironment?.activeDriftIncidentId) {
      navigate(`/incidents/${currentEnvironment.activeDriftIncidentId}`);
    }
  };

  const handleCreateDriftIncident = (workflow: Workflow) => {
    navigate(`/incidents/new?environment=${currentEnvironment?.id}&workflow=${workflow.id}`);
  };

  const handleRefresh = async () => {
    try {
      setIsRefreshing(true);
      toast.info('Refreshing environment state...');

      // Force refresh from N8N by fetching with force_refresh=true
      await api.getWorkflows(selectedEnvironment, true);

      // Invalidate paginated query to refetch with the new cached data
      queryClient.invalidateQueries({ queryKey: ['workflows-paginated'] });
      queryClient.invalidateQueries({ queryKey: ['workflow-execution-counts'] });

      toast.success('Workflows refreshed successfully');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to refresh workflows';
      toast.error(message);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Workflows</h1>
          <p className="text-muted-foreground">
            Manage and deploy your n8n workflows
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handleRefresh}
            disabled={isRefreshing}
            title="Refresh workflows from N8N"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
            {isRefreshing ? 'Refreshing...' : 'Refresh from N8N'}
          </Button>
          {currentEnvironment?.allowUpload && (
            <Button onClick={handleUploadClick}>
              <Upload className="h-4 w-4 mr-2" />
              Upload Workflow
            </Button>
          )}
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
                  placeholder="Search by name..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
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
                <option value="" className="bg-background text-foreground">All Status</option>
                <option value="active" className="bg-background text-foreground">Active</option>
                <option value="inactive" className="bg-background text-foreground">Inactive</option>
              </select>
            </div>

            {/* Environment Filter */}
            <div className="space-y-2">
              <Label htmlFor="environment">Environment</Label>
              <select
                id="environment"
                value={currentEnvironment?.id || ''}
                onChange={(e) => setSelectedEnvironment(e.target.value as EnvironmentType)}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                disabled={availableEnvironments.length === 0}
              >
                {availableEnvironments.length === 0 ? (
                  <option value="" className="bg-background text-foreground">No environments available</option>
                ) : (
                  availableEnvironments.map((env) => (
                    <option key={env.id} value={env.id} className="bg-background text-foreground">
                      {env.name}
                    </option>
                  ))
                )}
              </select>
            </div>

            {/* Tag Filter */}
            <div className="space-y-2">
              <Label htmlFor="tag">Tags</Label>
              <MultiSelect
                options={allTags}
                selected={selectedTag}
                onChange={setSelectedTag}
                placeholder="Select tags..."
              />
            </div>
          </div>

          {hasActiveFilters && (
            <div className="mt-4 flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {totalWorkflows} workflow{totalWorkflows !== 1 ? 's' : ''} found
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
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Workflows in {currentEnvironment?.name || '—'}</CardTitle>
              <CardDescription>
                View and manage workflows in the selected environment
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && !isFetching ? (
            <div className="text-center py-8">Loading workflows...</div>
          ) : totalWorkflows === 0 && !isFetching ? (
            <div className="text-center py-8 text-muted-foreground">
              {hasActiveFilters ? 'No workflows match your filters' : 'No workflows found'}
            </div>
          ) : (
            <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('name')}>
                    Name {getSortIcon('name')}
                  </TableHead>
                  <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('active')}>
                    Status {getSortIcon('active')}
                  </TableHead>
                  <TableHead>Sync Status</TableHead>
                  <TableHead>Tags</TableHead>
                  <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('executions')}>
                    Executions {getSortIcon('executions')}
                  </TableHead>
                  <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('updatedAt')}>
                    Last Updated {getSortIcon('updatedAt')}
                  </TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayWorkflows.map((workflow) => (
                  <TableRow key={workflow.id}>
                    <TableCell className="font-medium">
                      <Link
                        to={`/workflows/${workflow.id}?environment=${selectedEnvironment}`}
                        className="text-primary hover:underline"
                      >
                        {workflow.name}
                      </Link>
                    </TableCell>
                    <TableCell>
                      {workflow.active ? (
                        <Badge variant="success" className="flex items-center gap-1 w-fit">
                          <PlayCircle className="h-3 w-3" />
                          Active
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="flex items-center gap-1 w-fit">
                          <PauseCircle className="h-3 w-3" />
                          Inactive
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {getSyncStatusDisplay(workflow.syncStatus)}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1 flex-wrap">
                        {workflow.tags?.map((tag) => {
                          const tagName = typeof tag === 'string' ? tag : tag.name;
                          return (
                            <Badge
                              key={typeof tag === 'string' ? tag : tag.id}
                              variant="secondary"
                              className="text-xs cursor-pointer hover:bg-secondary/80"
                              onClick={() => {
                                if (!selectedTag.includes(tagName)) {
                                  setSelectedTag([...selectedTag, tagName]);
                                }
                              }}
                            >
                              {tagName}
                            </Badge>
                          );
                        })}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Link
                        to={`/executions?workflow=${workflow.id}`}
                        className="text-primary hover:underline"
                      >
                        {executionCountsByWorkflow[workflow.id] || 0}
                      </Link>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(workflow.updatedAt).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <WorkflowActionsMenu
                        workflow={workflow}
                        environment={currentEnvironment || null}
                        onViewDetails={() => navigate(`/workflows/${workflow.id}`)}
                        onEdit={() => handleEditClick(workflow)}
                        onSoftDelete={() => handleSoftDelete(workflow)}
                        onHardDelete={() => handleHardDeleteClick(workflow)}
                        onOpenInN8N={() => openInN8N(workflow.id)}
                        onCreateDeployment={() => handleCreateDeployment(workflow)}
                        onViewDriftIncident={() => handleViewDriftIncident(workflow)}
                        onCreateDriftIncident={() => handleCreateDriftIncident(workflow)}
                      />
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
                  Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, totalWorkflows)} of {totalWorkflows} workflows
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


      {/* Edit Workflow Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Workflow</DialogTitle>
            <DialogDescription>
              Update workflow name, status, and tags
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Workflow Name</Label>
              <Input
                id="edit-name"
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                placeholder="My Workflow"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-status">Status</Label>
              <select
                id="edit-status"
                value={editForm.active ? 'active' : 'inactive'}
                onChange={(e) => setEditForm({ ...editForm, active: e.target.value === 'active' })}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="active" className="bg-background text-foreground">Active</option>
                <option value="inactive" className="bg-background text-foreground">Inactive</option>
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-tags">Tags</Label>
              <MultiSelect
                options={allTags}
                selected={editForm.tags}
                onChange={(tags) => setEditForm({ ...editForm, tags })}
                placeholder="Select tags..."
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEditSubmit} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog (legacy - kept for backward compatibility) */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Workflow</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{workflowToDelete?.name}"? This action cannot be undone and will remove the workflow from the N8N instance.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Yes, Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Governance Dialogs */}
      <DirectEditWarningDialog
        open={driftWarningOpen}
        onOpenChange={setDriftWarningOpen}
        workflowName={pendingEditWorkflow?.name || ''}
        environmentType={currentEnvironment?.environmentClass || currentEnvironment?.type || 'dev'}
        onConfirm={handleDriftWarningConfirm}
      />
      <HardDeleteConfirmDialog
        open={hardDeleteOpen}
        onOpenChange={setHardDeleteOpen}
        workflowName={pendingDeleteWorkflow?.name || ''}
        onConfirm={handleHardDeleteConfirm}
      />
    </div>
  );
}
