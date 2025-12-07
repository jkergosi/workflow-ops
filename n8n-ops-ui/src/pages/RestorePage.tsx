import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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
  Loader2,
  ArrowLeft,
  RotateCcw,
  GitBranch,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api-client';

export function RestorePage() {
  const navigate = useNavigate();
  const { id: environmentId } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [selectedWorkflows, setSelectedWorkflows] = useState<Set<string>>(new Set());
  const [options, setOptions] = useState({
    includeWorkflows: true,
    includeCredentials: false,
    includeTags: false,
    createSnapshots: true,
  });
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [restoreResults, setRestoreResults] = useState<{
    success: boolean;
    workflows_created: number;
    workflows_updated: number;
    workflows_failed: number;
    snapshots_created: number;
    results: Array<{
      workflow_id: string;
      name: string;
      action: 'created' | 'updated' | 'failed';
      error?: string;
    }>;
    errors: string[];
  } | null>(null);

  // Fetch restore preview
  const {
    data: preview,
    isLoading: loadingPreview,
    error: previewError,
    refetch: refetchPreview,
  } = useQuery({
    queryKey: ['restore-preview', environmentId],
    queryFn: () => apiClient.getRestorePreview(environmentId!),
    enabled: !!environmentId,
  });

  // Select all workflows by default when preview loads
  useEffect(() => {
    if (preview?.data?.workflows) {
      const allIds = new Set(preview.data.workflows.map((w) => w.workflow_id));
      setSelectedWorkflows(allIds);
    }
  }, [preview]);

  // Execute restore mutation
  const restoreMutation = useMutation({
    mutationFn: () =>
      apiClient.executeRestore(environmentId!, {
        include_workflows: options.includeWorkflows,
        include_credentials: options.includeCredentials,
        include_tags: options.includeTags,
        create_snapshots: options.createSnapshots,
        selected_workflow_ids:
          selectedWorkflows.size === preview?.data?.workflows?.length
            ? null
            : Array.from(selectedWorkflows),
      }),
    onSuccess: (response) => {
      setRestoreResults(response.data);
      if (response.data.success) {
        toast.success(
          `Restore completed: ${response.data.workflows_created} created, ${response.data.workflows_updated} updated`
        );
      } else {
        toast.warning(
          `Restore completed with errors: ${response.data.workflows_failed} failed`
        );
      }
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      queryClient.invalidateQueries({ queryKey: ['environments'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to execute restore');
    },
  });

  const handleSelectAll = () => {
    if (preview?.data?.workflows) {
      if (selectedWorkflows.size === preview.data.workflows.length) {
        setSelectedWorkflows(new Set());
      } else {
        setSelectedWorkflows(new Set(preview.data.workflows.map((w) => w.workflow_id)));
      }
    }
  };

  const handleSelectWorkflow = (workflowId: string) => {
    const newSelected = new Set(selectedWorkflows);
    if (newSelected.has(workflowId)) {
      newSelected.delete(workflowId);
    } else {
      newSelected.add(workflowId);
    }
    setSelectedWorkflows(newSelected);
  };

  const handleRestore = () => {
    setShowConfirmDialog(true);
  };

  const confirmRestore = () => {
    setShowConfirmDialog(false);
    restoreMutation.mutate();
  };

  if (loadingPreview) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2">Loading restore preview...</span>
      </div>
    );
  }

  if (previewError) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate('/environments')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Environments
        </Button>

        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Error Loading Preview</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              {(previewError as any)?.response?.data?.detail ||
                'Failed to load restore preview. Make sure GitHub is configured for this environment.'}
            </p>
            <Button className="mt-4" variant="outline" onClick={() => refetchPreview()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const previewData = preview?.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate('/environments')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Restore from GitHub</h1>
            <p className="text-muted-foreground">
              Environment: {previewData?.environment_name}
            </p>
          </div>
        </div>
      </div>

      {/* GitHub Info */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Source Repository
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 text-sm">
            <span className="font-mono text-muted-foreground">{previewData?.github_repo}</span>
            <Badge variant="outline">{previewData?.github_branch}</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              New Workflows
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Plus className="h-5 w-5 text-green-500" />
              <span className="text-2xl font-bold">{previewData?.total_new || 0}</span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Updates
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5 text-blue-500" />
              <span className="text-2xl font-bold">{previewData?.total_update || 0}</span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Selected
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-primary" />
              <span className="text-2xl font-bold">{selectedWorkflows.size}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Restore Options */}
      <Card>
        <CardHeader>
          <CardTitle>Restore Options</CardTitle>
          <CardDescription>Select what to restore from GitHub</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="workflows"
              checked={options.includeWorkflows}
              onCheckedChange={(checked) =>
                setOptions({ ...options, includeWorkflows: !!checked })
              }
            />
            <Label htmlFor="workflows" className="cursor-pointer">
              Workflows
            </Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="credentials"
              checked={options.includeCredentials}
              disabled={!previewData?.has_encryption_key}
              onCheckedChange={(checked) =>
                setOptions({ ...options, includeCredentials: !!checked })
              }
            />
            <Label
              htmlFor="credentials"
              className={`cursor-pointer ${!previewData?.has_encryption_key ? 'text-muted-foreground' : ''}`}
            >
              Credentials
              {!previewData?.has_encryption_key && (
                <span className="ml-2 text-xs text-amber-500">
                  (Requires N8N encryption key)
                </span>
              )}
            </Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="tags"
              checked={options.includeTags}
              onCheckedChange={(checked) =>
                setOptions({ ...options, includeTags: !!checked })
              }
            />
            <Label htmlFor="tags" className="cursor-pointer">
              Tags
            </Label>
          </div>

          <div className="border-t pt-4 mt-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="snapshots"
                checked={options.createSnapshots}
                onCheckedChange={(checked) =>
                  setOptions({ ...options, createSnapshots: !!checked })
                }
              />
              <Label htmlFor="snapshots" className="cursor-pointer">
                Create snapshots before restore (recommended for rollback)
              </Label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Workflows Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Workflows to Restore</CardTitle>
              <CardDescription>
                Select which workflows to restore from GitHub
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={handleSelectAll}>
              {selectedWorkflows.size === previewData?.workflows?.length
                ? 'Deselect All'
                : 'Select All'}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {previewData?.workflows && previewData.workflows.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12"></TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Nodes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewData.workflows.map((workflow) => (
                  <TableRow key={workflow.workflow_id}>
                    <TableCell>
                      <Checkbox
                        checked={selectedWorkflows.has(workflow.workflow_id)}
                        onCheckedChange={() => handleSelectWorkflow(workflow.workflow_id)}
                      />
                    </TableCell>
                    <TableCell className="font-medium">{workflow.name}</TableCell>
                    <TableCell>
                      <Badge
                        variant={workflow.status === 'new' ? 'default' : 'secondary'}
                      >
                        {workflow.status === 'new' ? (
                          <Plus className="h-3 w-3 mr-1" />
                        ) : (
                          <RefreshCw className="h-3 w-3 mr-1" />
                        )}
                        {workflow.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{workflow.nodes_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No workflows found in GitHub repository
            </div>
          )}
        </CardContent>
      </Card>

      {/* Restore Results */}
      {restoreResults && (
        <Card className={restoreResults.success ? 'border-green-500' : 'border-amber-500'}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {restoreResults.success ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : (
                <AlertCircle className="h-5 w-5 text-amber-500" />
              )}
              Restore Results
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-green-500">
                  {restoreResults.workflows_created}
                </div>
                <div className="text-sm text-muted-foreground">Created</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-blue-500">
                  {restoreResults.workflows_updated}
                </div>
                <div className="text-sm text-muted-foreground">Updated</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-red-500">
                  {restoreResults.workflows_failed}
                </div>
                <div className="text-sm text-muted-foreground">Failed</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-purple-500">
                  {restoreResults.snapshots_created}
                </div>
                <div className="text-sm text-muted-foreground">Snapshots</div>
              </div>
            </div>

            {restoreResults.errors.length > 0 && (
              <div className="mt-4 p-3 bg-destructive/10 rounded-md">
                <p className="font-medium text-destructive mb-2">Errors:</p>
                <ul className="list-disc list-inside text-sm text-destructive">
                  {restoreResults.errors.map((error, i) => (
                    <li key={i}>{error}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex gap-2 mt-4">
              <Button variant="outline" onClick={() => navigate('/environments')}>
                Back to Environments
              </Button>
              <Button variant="outline" onClick={() => navigate('/snapshots')}>
                View Snapshots
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Action Button */}
      {!restoreResults && (
        <div className="flex justify-end gap-4">
          <Button variant="outline" onClick={() => navigate('/environments')}>
            Cancel
          </Button>
          <Button
            onClick={handleRestore}
            disabled={
              selectedWorkflows.size === 0 ||
              restoreMutation.isPending ||
              !options.includeWorkflows
            }
          >
            {restoreMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Restoring...
              </>
            ) : (
              <>
                <RotateCcw className="h-4 w-4 mr-2" />
                Restore {selectedWorkflows.size} Workflow
                {selectedWorkflows.size !== 1 ? 's' : ''}
              </>
            )}
          </Button>
        </div>
      )}

      {/* Confirmation Dialog */}
      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Restore</AlertDialogTitle>
            <AlertDialogDescription>
              You are about to restore {selectedWorkflows.size} workflow
              {selectedWorkflows.size !== 1 ? 's' : ''} from GitHub to your N8N instance.
              {options.createSnapshots && (
                <>
                  <br />
                  <br />
                  Snapshots will be created for existing workflows before updating them,
                  allowing you to rollback if needed.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmRestore}>
              <RotateCcw className="h-4 w-4 mr-2" />
              Restore
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
