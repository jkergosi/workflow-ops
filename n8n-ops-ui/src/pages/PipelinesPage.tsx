// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
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
import { useFeatures } from '@/lib/features';
import { Plus, Edit, Copy, PlayCircle, PauseCircle, Trash2, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import type { Pipeline } from '@/types';

export function PipelinesPage() {
  useEffect(() => {
    document.title = 'Pipelines - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [pipelineToDelete, setPipelineToDelete] = useState<Pipeline | null>(null);
  const [showInactive, setShowInactive] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const { planName, isLoading: loadingFeatures } = useFeatures();
  const planLower = planName?.toLowerCase() || 'free';

  // Reset to page 1 when filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [showInactive]);

  const { data: pipelinesData, isLoading, isFetching } = useQuery({
    queryKey: ['pipelines', showInactive, currentPage, pageSize],
    queryFn: () => apiClient.getPipelines({
      includeInactive: showInactive,
      page: currentPage,
      pageSize,
    }),
    placeholderData: keepPreviousData,
  });

  const pipelines = pipelinesData?.data?.items || [];
  const totalPipelines = pipelinesData?.data?.total || 0;
  const totalPages = pipelinesData?.data?.totalPages || 1;

  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.deletePipeline(id),
    onSuccess: () => {
      toast.success('Pipeline deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
      setDeleteDialogOpen(false);
      setPipelineToDelete(null);
    },
    onError: () => {
      toast.error('Failed to delete pipeline');
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      apiClient.updatePipeline(id, { isActive }),
    onSuccess: (_, variables) => {
      toast.success(`Pipeline ${variables.isActive ? 'activated' : 'deactivated'} successfully`);
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
    },
    onError: () => {
      toast.error('Failed to update pipeline status');
    },
  });

  const duplicateMutation = useMutation({
    mutationFn: (pipeline: Pipeline) =>
      apiClient.createPipeline({
        name: `${pipeline.name} (Copy)`,
        description: pipeline.description,
        isActive: false,
        environmentIds: pipeline.environmentIds,
        stages: pipeline.stages,
      }),
    onSuccess: () => {
      toast.success('Pipeline duplicated successfully');
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
    },
    onError: () => {
      toast.error('Failed to duplicate pipeline');
    },
  });

  const getEnvironmentPath = (pipeline: Pipeline): string => {
    if (!environments?.data || !pipeline.environmentIds || pipeline.environmentIds.length === 0) return 'N/A';
    const envNames = pipeline.environmentIds
      .map((id) => {
        const env = environments.data.find((e) => e.id === id);
        return env?.name || id;
      })
      .join(' → ');
    return envNames;
  };

  const handleDeleteClick = (pipeline: Pipeline) => {
    setPipelineToDelete(pipeline);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (pipelineToDelete) {
      deleteMutation.mutate(pipelineToDelete.id);
    }
  };

  const handleToggleActive = (pipeline: Pipeline) => {
    toggleActiveMutation.mutate({ id: pipeline.id, isActive: !pipeline.isActive });
  };

  const handleDuplicate = (pipeline: Pipeline) => {
    duplicateMutation.mutate(pipeline);
  };

  if (!loadingFeatures && planLower === 'pro') {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Pipelines</h1>
          <p className="text-muted-foreground">
            Define promotion rules and workflows between environments
          </p>
        </div>

        <Card>
          <CardContent className="py-12">
            <div className="max-w-2xl">
              <div className="text-xl font-semibold">Pipelines are built for teams</div>
              <div className="text-muted-foreground mt-2">
                Agency adds pipelines, approvals, and drift management for safe multi-environment delivery.
              </div>
              <div className="flex flex-col sm:flex-row gap-2 mt-6">
                <Link to="/billing">
                  <Button>Upgrade to Agency</Button>
                </Link>
                <Link to="/promote">
                  <Button variant="outline">Promote manually</Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Pipelines</h1>
          <p className="text-muted-foreground">
            Define promotion rules and workflows between environments
          </p>
        </div>
        <Button onClick={() => navigate('/pipelines/new')}>
          <Plus className="h-4 w-4 mr-2" />
          Create Pipeline
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Deployment Pipelines</CardTitle>
              <CardDescription>
                Manage pipelines that define how workflows are deployed between environments
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="show-inactive"
                checked={showInactive}
                onCheckedChange={(checked) => setShowInactive(checked === true)}
              />
              <Label
                htmlFor="show-inactive"
                className="text-sm font-normal cursor-pointer text-muted-foreground"
              >
                Show inactive pipelines
              </Label>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading pipelines...</div>
          ) : pipelines.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p className="mb-4">Create your first pipeline</p>
              <p className="text-sm text-muted-foreground mb-4">
                Define how workflows move from dev → staging → prod with gates and approvals.
              </p>
              <Button onClick={() => navigate('/pipelines/new')}>
                <Plus className="h-4 w-4 mr-2" />
                Create pipeline
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Pipeline Name</TableHead>
                  <TableHead>Environment Path</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Modified</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pipelines.map((pipeline) => (
                  <TableRow 
                    key={pipeline.id}
                    className={!pipeline.isActive ? 'opacity-60' : ''}
                  >
                    <TableCell className="font-medium">
                      <Link
                        to={`/pipelines/${pipeline.id}`}
                        className={`${!pipeline.isActive ? 'text-muted-foreground' : 'text-primary'} hover:underline`}
                      >
                        {pipeline.name}
                      </Link>
                      {pipeline.description && (
                        <p className="text-sm text-muted-foreground mt-1">
                          {pipeline.description}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 text-sm">
                        {getEnvironmentPath(pipeline)}
                      </div>
                    </TableCell>
                    <TableCell>
                      {pipeline.isActive ? (
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
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(pipeline.lastModifiedAt || pipeline.updatedAt).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => navigate(`/pipelines/${pipeline.id}`)}
                          title="Edit pipeline"
                        >
                          <Edit className="h-3 w-3 mr-1" />
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDuplicate(pipeline)}
                          title="Duplicate pipeline"
                          disabled={duplicateMutation.isPending}
                        >
                          <Copy className="h-3 w-3 mr-1" />
                          Duplicate
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleToggleActive(pipeline)}
                          title={pipeline.isActive ? 'Deactivate' : 'Activate'}
                          disabled={toggleActiveMutation.isPending}
                        >
                          {pipeline.isActive ? (
                            <>
                              <PauseCircle className="h-3 w-3 mr-1" />
                              Deactivate
                            </>
                          ) : (
                            <>
                              <PlayCircle className="h-3 w-3 mr-1" />
                              Activate
                            </>
                          )}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDeleteClick(pipeline)}
                          title="Delete pipeline"
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
          )}

          {/* Pagination Controls */}
          {pipelines.length > 0 && (
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
                  Showing {totalPipelines > 0 ? ((currentPage - 1) * pageSize) + 1 : 0} to {Math.min(currentPage * pageSize, totalPipelines)} of {totalPipelines} pipelines
                </div>
              </div>

              <div className="flex items-center gap-2">
                {isFetching && (
                  <span className="text-sm text-muted-foreground">Loading...</span>
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
                    Page {currentPage} of {totalPages}
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
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Pipeline</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{pipelineToDelete?.name}"? This action cannot be undone.
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

