// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
import { Plus, Edit, Copy, PlayCircle, PauseCircle, Trash2, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import type { Pipeline } from '@/types';

export function PipelinesPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [pipelineToDelete, setPipelineToDelete] = useState<Pipeline | null>(null);

  const { data: pipelines, isLoading } = useQuery({
    queryKey: ['pipelines'],
    queryFn: () => apiClient.getPipelines(),
  });

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
          <CardTitle>Deployment Pipelines</CardTitle>
          <CardDescription>
            Manage pipelines that define how workflows are deployed between environments
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading pipelines...</div>
          ) : !pipelines?.data || pipelines.data.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <p className="mb-4">No pipelines found</p>
              <Button onClick={() => navigate('/pipelines/new')}>
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Pipeline
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
                {pipelines.data.map((pipeline) => (
                  <TableRow key={pipeline.id}>
                    <TableCell className="font-medium">
                      <Link
                        to={`/pipelines/${pipeline.id}`}
                        className="text-primary hover:underline"
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

