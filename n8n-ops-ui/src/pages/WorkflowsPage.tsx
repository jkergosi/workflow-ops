import { useState, useMemo, useRef, useEffect } from 'react';
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
import { useAppStore } from '@/store/use-app-store';
import { Upload, PlayCircle, PauseCircle, Search, ArrowUpDown, ArrowUp, ArrowDown, X, FileJson, FolderOpen, Edit, Trash2, Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { Workflow, EnvironmentType } from '@/types';

type SortField = 'name' | 'description' | 'active' | 'updatedAt';
type SortDirection = 'asc' | 'desc';

export function WorkflowsPage() {
  const queryClient = useQueryClient();
  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTag, setSelectedTag] = useState<string[]>([]);
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [workflowToEdit, setWorkflowToEdit] = useState<Workflow | null>(null);
  const [workflowToDelete, setWorkflowToDelete] = useState<Workflow | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [isBackingUp, setIsBackingUp] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [workflowsToBackupCount, setWorkflowsToBackupCount] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const [editForm, setEditForm] = useState({
    name: '',
    active: false,
    tags: [] as string[],
  });

  const { data: workflows, isLoading } = useQuery({
    queryKey: ['workflows', selectedEnvironment],
    queryFn: () => api.getWorkflows(selectedEnvironment),
  });

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

      // Force refresh from N8N to get updated tags
      await api.getWorkflows(selectedEnvironment, true);
      queryClient.invalidateQueries({ queryKey: ['workflows', selectedEnvironment] });

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
      queryClient.invalidateQueries({ queryKey: ['workflows', selectedEnvironment] });
      setDeleteDialogOpen(false);
      setWorkflowToDelete(null);
    },
    onError: () => {
      toast.error('Failed to delete workflow');
      setDeleteDialogOpen(false);
    },
  });

  // Get all unique tags from workflows
  const allTags = useMemo(() => {
    if (!workflows?.data) return [];
    const tags = new Set<string>();
    workflows.data.forEach((workflow) => {
      workflow.tags?.forEach((tag) => tags.add(tag));
    });
    return Array.from(tags).sort();
  }, [workflows]);

  // Filter and sort workflows
  const filteredAndSortedWorkflows = useMemo(() => {
    if (!workflows?.data) return [];

    let result = [...workflows.data];

    // Apply search filter (name and description only)
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter((workflow) => {
        const matchesName = workflow.name.toLowerCase().includes(query);
        const matchesDescription = workflow.description?.toLowerCase().includes(query);
        return matchesName || matchesDescription;
      });
    }

    // Apply tag filter
    if (selectedTag.length > 0) {
      result = result.filter((workflow) =>
        selectedTag.some((tag) => workflow.tags?.includes(tag))
      );
    }

    // Apply status filter
    if (selectedStatus) {
      const isActive = selectedStatus === 'active';
      result = result.filter((workflow) => workflow.active === isActive);
    }

    // Apply sorting
    result.sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (sortField) {
        case 'name':
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
          break;
        case 'description':
          aValue = (a.description || '').toLowerCase();
          bValue = (b.description || '').toLowerCase();
          break;
        case 'active':
          aValue = a.active ? 1 : 0;
          bValue = b.active ? 1 : 0;
          break;
        case 'updatedAt':
          aValue = new Date(a.updatedAt).getTime();
          bValue = new Date(b.updatedAt).getTime();
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  }, [workflows, searchQuery, selectedTag, selectedStatus, sortField, sortDirection]);

  // Pagination calculations
  const { paginatedWorkflows, totalPages, totalWorkflows } = useMemo(() => {
    const total = filteredAndSortedWorkflows.length;
    const pages = Math.ceil(total / pageSize);
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const paginated = filteredAndSortedWorkflows.slice(startIndex, endIndex);

    return {
      paginatedWorkflows: paginated,
      totalPages: pages,
      totalWorkflows: total,
    };
  }, [filteredAndSortedWorkflows, currentPage, pageSize]);

  // Reset to page 1 when filters change
  const resetPage = () => {
    if (currentPage !== 1) {
      setCurrentPage(1);
    }
  };

  // Reset page when filters, search, or tag changes
  useEffect(() => {
    resetPage();
  }, [searchQuery, selectedTag, selectedStatus, selectedEnvironment]);

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

  const clearFilters = () => {
    setSearchQuery('');
    setSelectedTag([]);
    setSelectedStatus('');
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const jsonFiles = Array.from(files).filter(
        (file) => file.name.endsWith('.json') || file.name.endsWith('.zip')
      );
      setUploadedFiles(jsonFiles);
    }
  };

  const handleFolderSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files) {
      const jsonFiles = Array.from(files).filter((file) => file.name.endsWith('.json'));
      setUploadedFiles(jsonFiles);
    }
  };

  const handleUploadClick = async () => {
    setUploadDialogOpen(true);
    setUploadedFiles([]);
    setWorkflowsToBackupCount(null); // Reset count

    // Fetch count of workflows needing backup
    try {
      // Get workflows and environment to calculate count
      const workflowsData = await apiClient.getWorkflows(selectedEnvironment);
      const environmentsData = await apiClient.getEnvironments();
      const currentEnv = environmentsData.data.find(env => env.type === selectedEnvironment);

      if (currentEnv && currentEnv.lastBackup) {
        // Filter workflows updated since last backup
        const lastBackupDate = new Date(currentEnv.lastBackup);
        const workflowsNeedingBackup = workflowsData.data.filter(workflow => {
          if (workflow.updatedAt) {
            const workflowUpdatedDate = new Date(workflow.updatedAt);
            return workflowUpdatedDate > lastBackupDate;
          }
          return true; // Include workflows without updatedAt
        });
        setWorkflowsToBackupCount(workflowsNeedingBackup.length);
      } else {
        // No last backup, all workflows need backup
        setWorkflowsToBackupCount(workflowsData.data.length);
      }
    } catch (error) {
      console.error('Error calculating workflows to backup:', error);
      setWorkflowsToBackupCount(null);
    }
  };

  const handleRemoveFile = (index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    try {
      setIsBackingUp(true);
      toast.info('Backing up workflows to GitHub...');

      const result = await apiClient.syncWorkflowsToGithub(selectedEnvironment);

      if (result.data.success) {
        const { synced, skipped = 0, failed } = result.data;

        // Build success message
        let message = '';
        if (synced > 0 && skipped > 0) {
          message = `Backed up ${synced} workflow${synced !== 1 ? 's' : ''}, ${skipped} already up to date`;
        } else if (synced > 0) {
          message = `Successfully backed up ${synced} workflow${synced !== 1 ? 's' : ''} to GitHub`;
        } else if (skipped > 0) {
          message = `All ${skipped} workflow${skipped !== 1 ? 's are' : ' is'} already up to date`;
        } else {
          message = 'No workflows to backup';
        }

        toast.success(message);

        if (result.data.errors && result.data.errors.length > 0) {
          toast.warning(`${failed} workflow${failed !== 1 ? 's' : ''} failed to sync`);
          console.error('Sync errors:', result.data.errors);
        }
      } else {
        toast.error('Failed to backup workflows to GitHub');
      }

      setUploadDialogOpen(false);
      setUploadedFiles([]);
    } catch (error: any) {
      console.error('Error syncing to GitHub:', error);
      toast.error(error.response?.data?.detail || 'Failed to backup workflows to GitHub');
    } finally {
      setIsBackingUp(false);
    }
  };

  const hasActiveFilters = searchQuery || selectedTag.length > 0 || selectedStatus;

  // Get N8N URL for opening workflows
  const getN8nUrl = () => {
    // In production, this would come from environment config
    const devUrl = localStorage.getItem('dev_n8n_url') || 'http://localhost:5678';
    return devUrl;
  };

  const openWorkflow = (workflowId: string, editMode: boolean = false) => {
    const n8nUrl = getN8nUrl();
    const url = editMode ? `${n8nUrl}/workflow/${workflowId}` : `${n8nUrl}/workflow/${workflowId}`;
    window.open(url, '_blank');
  };

  const handleEditClick = (workflow: Workflow) => {
    setWorkflowToEdit(workflow);
    setEditForm({
      name: workflow.name,
      active: workflow.active,
      tags: workflow.tags || [],
    });
    setEditDialogOpen(true);
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

  const handleDeleteClick = (workflow: Workflow) => {
    setWorkflowToDelete(workflow);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (workflowToDelete) {
      deleteMutation.mutate({ workflowId: workflowToDelete.id });
    }
  };

  const handleRefresh = async () => {
    try {
      setIsRefreshing(true);
      toast.info('Refreshing workflows from N8N...');

      // Fetch with force_refresh=true
      await api.getWorkflows(selectedEnvironment, true);

      // Invalidate query to refetch with the new cached data
      queryClient.invalidateQueries({ queryKey: ['workflows', selectedEnvironment] });

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
          {selectedEnvironment === 'dev' && (
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
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
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
              <CardTitle>Workflows in {selectedEnvironment}</CardTitle>
              <CardDescription>
                View and manage workflows in the selected environment
                {workflows?.data?.[0]?.lastSyncedAt && (
                  <span className="ml-2 text-xs">
                    • Last synced: {new Date(workflows.data[0].lastSyncedAt).toLocaleString()}
                  </span>
                )}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading workflows...</div>
          ) : totalWorkflows === 0 ? (
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
                  <TableHead>Tags</TableHead>
                  <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('updatedAt')}>
                    Last Updated {getSortIcon('updatedAt')}
                  </TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedWorkflows.map((workflow) => (
                  <TableRow key={workflow.id}>
                    <TableCell className="font-medium">
                      <button
                        onClick={() => openWorkflow(workflow.id)}
                        className="text-primary hover:underline text-left"
                      >
                        {workflow.name}
                      </button>
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
                      <div className="flex gap-1 flex-wrap">
                        {workflow.tags?.map((tag) => (
                          <Badge
                            key={tag}
                            variant="secondary"
                            className="text-xs cursor-pointer hover:bg-secondary/80"
                            onClick={() => {
                              if (!selectedTag.includes(tag)) {
                                setSelectedTag([...selectedTag, tag]);
                              }
                            }}
                          >
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(workflow.updatedAt).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleEditClick(workflow)}
                          title="Edit workflow"
                        >
                          <Edit className="h-3 w-3 mr-1" />
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDeleteClick(workflow)}
                          title="Delete workflow"
                        >
                          <Trash2 className="h-3 w-3 mr-1" />
                          Delete
                        </Button>
                      </div>
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
                  Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, totalWorkflows)} of {totalWorkflows} workflows
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

      {/* Upload Dialog */}
      <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Backup Workflows to GitHub</DialogTitle>
            <DialogDescription>
              Back up your workflows to the configured GitHub repository
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Workflows to Backup Count */}
            <div className="p-4 bg-muted rounded-lg">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Workflows to back up:</span>
                <span className="text-lg font-bold">
                  {workflowsToBackupCount === null ? (
                    <span className="text-muted-foreground">Calculating...</span>
                  ) : (
                    <span className={workflowsToBackupCount > 0 ? "text-primary" : "text-muted-foreground"}>
                      {workflowsToBackupCount}
                    </span>
                  )}
                </span>
              </div>
              {workflowsToBackupCount === 0 && (
                <p className="text-xs text-muted-foreground mt-2">
                  All workflows are already backed up
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadDialogOpen(false)} disabled={isBackingUp}>
              Cancel
            </Button>
            <Button onClick={handleUpload} disabled={isBackingUp}>
              {isBackingUp ? (
                <>
                  <Loader2 className="h-5 w-5 mr-2 animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
                  Backing Up...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Yes, Backup
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
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

      {/* Delete Confirmation Dialog */}
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
    </div>
  );
}
