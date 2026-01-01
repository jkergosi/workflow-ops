// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useSearchParams, Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Camera, History, RotateCcw, Loader2, Eye, Plus, GitCompare, ArrowRight, ArrowDown, Check, X, Minus } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api-client';
import { useAppStore } from '@/store/use-app-store';
import { getDefaultEnvironmentId, resolveEnvironment, sortEnvironments } from '@/lib/environment-utils';
import { useFeatures } from '@/lib/features';
import type { Snapshot, SnapshotComparison } from '@/types';

export function SnapshotsPage() {
  useEffect(() => {
    document.title = 'Snapshots - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const { planName, isLoading: loadingFeatures } = useFeatures();
  const planLower = planName?.toLowerCase() || 'free';
  const [selectedSnapshot, setSelectedSnapshot] = useState<Snapshot | null>(null);
  const [restoreSnapshot, setRestoreSnapshot] = useState<Snapshot | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [showRestoreUpsell, setShowRestoreUpsell] = useState(false);
  
  // Create snapshot state
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [createReason, setCreateReason] = useState('');
  const [createNotes, setCreateNotes] = useState('');
  
  // Comparison state
  const [compareMode, setCompareMode] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([]);
  const [comparisonResult, setComparisonResult] = useState<SnapshotComparison | null>(null);
  const [compareDialogOpen, setCompareDialogOpen] = useState(false);

  // Get snapshot ID from URL if present
  const snapshotIdFromUrl = searchParams.get('snapshot');

  // Fetch environments
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const availableEnvironments = useMemo(() => {
    if (!environments?.data) return [];
    return sortEnvironments(environments.data.filter((env) => env.isActive));
  }, [environments?.data]);

  const currentEnvironment = useMemo(
    () => resolveEnvironment(availableEnvironments, selectedEnvironment),
    [availableEnvironments, selectedEnvironment]
  );

  // Get current environment ID (default to dev, normalize legacy type selections to id)
  const currentEnvironmentId = currentEnvironment?.id || getDefaultEnvironmentId(availableEnvironments);

  useEffect(() => {
    if (!currentEnvironmentId) return;
    if (selectedEnvironment !== currentEnvironmentId) {
      useAppStore.getState().setSelectedEnvironment(currentEnvironmentId);
    }
  }, [currentEnvironmentId, selectedEnvironment]);

  // Fetch snapshots for current environment
  const { data: snapshots, isLoading } = useQuery({
    queryKey: ['snapshots', currentEnvironmentId],
    queryFn: () =>
      apiClient.getSnapshots({
        environmentId: currentEnvironmentId,
      }),
    enabled: !!currentEnvironmentId,
  });

  // Fetch specific snapshot if ID in URL
  const { data: snapshotDetail } = useQuery({
    queryKey: ['snapshot', snapshotIdFromUrl],
    queryFn: () => apiClient.getSnapshot(snapshotIdFromUrl!),
    enabled: !!snapshotIdFromUrl,
  });

  // Open detail dialog if snapshot ID in URL
  useEffect(() => {
    if (snapshotDetail?.data) {
      setSelectedSnapshot(snapshotDetail.data);
      setDetailDialogOpen(true);
    }
  }, [snapshotDetail]);

  // Restore mutation
  const restoreMutation = useMutation({
    mutationFn: (snapshotId: string) => apiClient.restoreSnapshot(snapshotId),
    onSuccess: (response) => {
      toast.success(response.data.message || 'Snapshot restored successfully');
      queryClient.invalidateQueries({ queryKey: ['snapshots'] });
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      setRestoreSnapshot(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to restore snapshot');
    },
  });

  // Create snapshot mutation
  const createMutation = useMutation({
    mutationFn: (data: { environment_id: string; reason?: string; notes?: string }) =>
      apiClient.createEnvironmentSnapshot(data),
    onSuccess: (response) => {
      toast.success('Snapshot created successfully');
      queryClient.invalidateQueries({ queryKey: ['snapshots'] });
      setCreateDialogOpen(false);
      setCreateReason('');
      setCreateNotes('');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create snapshot');
    },
  });

  // Compare snapshots mutation
  const compareMutation = useMutation({
    mutationFn: ({ id1, id2 }: { id1: string; id2: string }) =>
      apiClient.compareSnapshots(id1, id2),
    onSuccess: (response) => {
      setComparisonResult(response.data);
      setCompareDialogOpen(true);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to compare snapshots');
    },
  });

  const handleCreateSnapshot = () => {
    if (!currentEnvironmentId) {
      toast.error('Please select an environment first');
      return;
    }
    createMutation.mutate({
      environment_id: currentEnvironmentId,
      reason: createReason || undefined,
      notes: createNotes || undefined,
    });
  };

  const handleToggleCompareSelection = (snapshotId: string) => {
    setSelectedForCompare((prev) => {
      if (prev.includes(snapshotId)) {
        return prev.filter((id) => id !== snapshotId);
      }
      if (prev.length >= 2) {
        return [prev[1], snapshotId];
      }
      return [...prev, snapshotId];
    });
  };

  const handleCompare = () => {
    if (selectedForCompare.length !== 2) {
      toast.error('Please select exactly 2 snapshots to compare');
      return;
    }
    compareMutation.mutate({ id1: selectedForCompare[0], id2: selectedForCompare[1] });
  };

  const handleViewDetails = (snapshot: Snapshot) => {
    setSelectedSnapshot(snapshot);
    setDetailDialogOpen(true);
  };

  const handleRestore = (snapshot: Snapshot) => {
    if (!loadingFeatures && planLower === 'free') {
      setShowRestoreUpsell(true);
      return;
    }
    setRestoreSnapshot(snapshot);
  };

  const confirmRestore = () => {
    if (restoreSnapshot) {
      restoreMutation.mutate(restoreSnapshot.id);
    }
  };

  const formatSnapshotType = (type: string) => {
    switch (type) {
      case 'auto_backup':
        return 'Auto backup';
      case 'pre_promotion':
        return 'Pre-promotion';
      case 'post_promotion':
        return 'Post-promotion';
      case 'manual_backup':
        return 'Manual backup';
      default:
        return type;
    }
  };

  const getTypeBadgeVariant = (type: string) => {
    switch (type) {
      case 'pre_promotion':
      case 'post_promotion':
        return 'default';
      case 'auto_backup':
        return 'secondary';
      case 'manual_backup':
        return 'outline';
      default:
        return 'outline';
    }
  };

  const getEnvironmentName = (envId: string) => {
    return environments?.data?.find((e) => e.id === envId)?.name || envId;
  };

  const snapshotsList = snapshots?.data || [];

  if (!loadingFeatures && planLower === 'free' && !isLoading && snapshotsList.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Snapshots</h1>
            <p className="text-muted-foreground">
              Version control and rollback for your workflows
            </p>
          </div>
        </div>

        <Card>
          <CardContent className="py-12">
            <div className="max-w-2xl">
              <div className="text-xl font-semibold">Snapshots protect your workflows</div>
              <div className="text-muted-foreground mt-2">
                Upgrade to enable automatic snapshots and one-click restore when something breaks.
              </div>
              <div className="flex flex-col sm:flex-row gap-2 mt-6">
                <Link to="/billing">
                  <Button>Upgrade to Pro</Button>
                </Link>
                <Link to="/environments">
                  <Button variant="outline">Manual Git backup</Button>
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
          <h1 className="text-3xl font-bold">Snapshots</h1>
          <p className="text-muted-foreground">
            Version control and rollback for your workflows
          </p>
        </div>
        <div className="flex items-center gap-2">
          {compareMode ? (
            <>
              <Badge variant="secondary" className="mr-2">
                {selectedForCompare.length}/2 selected
              </Badge>
              <Button
                variant="outline"
                onClick={() => {
                  setCompareMode(false);
                  setSelectedForCompare([]);
                }}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCompare}
                disabled={selectedForCompare.length !== 2 || compareMutation.isPending}
              >
                {compareMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <GitCompare className="h-4 w-4 mr-2" />
                )}
                Compare
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={() => setCompareMode(true)}
                disabled={snapshotsList.length < 2}
              >
                <GitCompare className="h-4 w-4 mr-2" />
                Compare
              </Button>
              <Button
                onClick={() => setCreateDialogOpen(true)}
                disabled={!currentEnvironmentId}
              >
                <Plus className="h-4 w-4 mr-2" />
                Create Snapshot
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Environment Selector */}
      {availableEnvironments.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Environment</CardTitle>
          </CardHeader>
          <CardContent>
            <Select
              value={currentEnvironmentId || ''}
              onValueChange={(value) => {
                useAppStore.getState().setSelectedEnvironment(value);
              }}
            >
              <SelectTrigger className="w-[300px]">
                <SelectValue placeholder="Select environment" />
              </SelectTrigger>
              <SelectContent>
                {availableEnvironments.map((env) => (
                  <SelectItem key={env.id} value={env.id}>
                    {env.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>
      )}

      {/* Snapshot History Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Snapshot History
          </CardTitle>
          <CardDescription>
            {currentEnvironmentId
              ? `Snapshots for ${getEnvironmentName(currentEnvironmentId)}`
              : 'Select an environment to view snapshots'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {showRestoreUpsell && !loadingFeatures && planLower === 'free' && (
            <div className="mb-4 rounded-md border p-4">
              <div className="font-semibold">Restore requires snapshots</div>
              <div className="text-sm text-muted-foreground mt-1">
                Pro enables snapshots and one-click restore so you can undo mistakes instantly.
              </div>
              <div className="mt-3">
                <Link to="/billing">
                  <Button>Upgrade to Pro</Button>
                </Link>
              </div>
            </div>
          )}
          {!currentEnvironmentId ? (
            <p className="text-muted-foreground text-center py-8">
              Select an environment above to view its snapshot history
            </p>
          ) : isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <span className="ml-2">Loading snapshots...</span>
            </div>
          ) : snapshotsList.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No snapshots found for this environment. Snapshots are created automatically
              during promotions and manual backups.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  {compareMode && <TableHead className="w-[50px]">Select</TableHead>}
                  <TableHead>Created At</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Triggered By</TableHead>
                  <TableHead>Deployment</TableHead>
                  <TableHead>Notes</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {snapshotsList.map((snapshot) => (
                  <TableRow 
                    key={snapshot.id}
                    className={selectedForCompare.includes(snapshot.id) ? 'bg-primary/5' : ''}
                  >
                    {compareMode && (
                      <TableCell>
                        <Checkbox
                          checked={selectedForCompare.includes(snapshot.id)}
                          onCheckedChange={() => handleToggleCompareSelection(snapshot.id)}
                        />
                      </TableCell>
                    )}
                    <TableCell className="text-muted-foreground">
                      {new Date(snapshot.createdAt).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant={getTypeBadgeVariant(snapshot.type)}>
                        {formatSnapshotType(snapshot.type)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {snapshot.createdByUserId || 'System'}
                    </TableCell>
                    <TableCell>
                      {snapshot.relatedDeploymentId ? (
                        <Link
                          to={`/deployments?deployment=${snapshot.relatedDeploymentId}`}
                          className="text-primary hover:underline"
                        >
                          #{snapshot.relatedDeploymentId.substring(0, 8)}...
                        </Link>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {snapshot.metadataJson?.reason || '—'}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleViewDetails(snapshot)}
                        >
                          <Eye className="h-3 w-3 mr-1" />
                          View
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleRestore(snapshot)}
                        >
                          <RotateCcw className="h-3 w-3 mr-1" />
                          Restore
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

      {/* Snapshot Detail Dialog */}
      <Dialog open={detailDialogOpen} onOpenChange={setDetailDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Snapshot Details</DialogTitle>
            <DialogDescription>View detailed information about this snapshot</DialogDescription>
          </DialogHeader>

          {selectedSnapshot && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Environment</p>
                  <p className="text-base">{getEnvironmentName(selectedSnapshot.environmentId)}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Type</p>
                  <Badge variant={getTypeBadgeVariant(selectedSnapshot.type)}>
                    {formatSnapshotType(selectedSnapshot.type)}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Created At</p>
                  <p className="text-base">
                    {new Date(selectedSnapshot.createdAt).toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Triggered By</p>
                  <p className="text-base">{selectedSnapshot.createdByUserId || 'System'}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-muted-foreground">Git Commit SHA</p>
                  <p className="text-base font-mono text-sm">
                    {selectedSnapshot.gitCommitSha || '—'}
                  </p>
                </div>
                {selectedSnapshot.relatedDeploymentId && (
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Deployment</p>
                    <Link
                      to={`/deployments?deployment=${selectedSnapshot.relatedDeploymentId}`}
                      className="text-primary hover:underline"
                    >
                      #{selectedSnapshot.relatedDeploymentId.substring(0, 8)}...
                    </Link>
                  </div>
                )}
              </div>

              {selectedSnapshot.metadataJson && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-2">Metadata</p>
                  <div className="bg-muted p-3 rounded-md">
                    <pre className="text-xs overflow-auto">
                      {JSON.stringify(selectedSnapshot.metadataJson, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Restore Confirmation Dialog */}
      <AlertDialog
        open={!!restoreSnapshot}
        onOpenChange={(open) => !open && setRestoreSnapshot(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Restore</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to restore the environment to this snapshot?
              <br />
              <br />
              This will replace all workflows in the environment with the versions from this
              snapshot. A new backup snapshot will be created automatically before the restore.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmRestore}
              disabled={restoreMutation.isPending}
            >
              {restoreMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Restoring...
                </>
              ) : (
                <>
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Restore
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Create Snapshot Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Snapshot</DialogTitle>
            <DialogDescription>
              Create a manual backup of all workflows in {currentEnvironmentId ? getEnvironmentName(currentEnvironmentId) : 'the selected environment'}.
              This will export all workflows to GitHub.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="reason">Reason (optional)</Label>
              <Input
                id="reason"
                placeholder="e.g., Before major refactoring"
                value={createReason}
                onChange={(e) => setCreateReason(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Textarea
                id="notes"
                placeholder="Additional notes about this snapshot..."
                value={createNotes}
                onChange={(e) => setCreateNotes(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateSnapshot} disabled={createMutation.isPending}>
              {createMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Camera className="h-4 w-4 mr-2" />
                  Create Snapshot
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Snapshot Comparison Dialog */}
      <Dialog open={compareDialogOpen} onOpenChange={setCompareDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle>Snapshot Comparison</DialogTitle>
            <DialogDescription>
              Comparing changes between two snapshots
            </DialogDescription>
          </DialogHeader>
          {comparisonResult && (
            <div className="space-y-6">
              {/* Snapshot Info */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-muted rounded-md">
                  <p className="text-xs text-muted-foreground mb-1">Older Snapshot</p>
                  <p className="font-medium">{new Date(comparisonResult.snapshot1.createdAt).toLocaleString()}</p>
                  <Badge variant="outline" className="mt-1">
                    {formatSnapshotType(comparisonResult.snapshot1.type)}
                  </Badge>
                </div>
                <div className="p-3 bg-muted rounded-md">
                  <p className="text-xs text-muted-foreground mb-1">Newer Snapshot</p>
                  <p className="font-medium">{new Date(comparisonResult.snapshot2.createdAt).toLocaleString()}</p>
                  <Badge variant="outline" className="mt-1">
                    {formatSnapshotType(comparisonResult.snapshot2.type)}
                  </Badge>
                </div>
              </div>

              {/* Summary Stats */}
              <div className="flex items-center gap-4 p-3 bg-muted/50 rounded-md">
                <div className="flex items-center gap-1">
                  <Plus className="h-4 w-4 text-green-500" />
                  <span className="text-sm">{comparisonResult.summary.added} added</span>
                </div>
                <div className="flex items-center gap-1">
                  <Minus className="h-4 w-4 text-red-500" />
                  <span className="text-sm">{comparisonResult.summary.removed} removed</span>
                </div>
                <div className="flex items-center gap-1">
                  <ArrowRight className="h-4 w-4 text-yellow-500" />
                  <span className="text-sm">{comparisonResult.summary.modified} modified</span>
                </div>
                <div className="flex items-center gap-1">
                  <Check className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">{comparisonResult.summary.unchanged} unchanged</span>
                </div>
              </div>

              {/* Workflow Changes */}
              <div className="space-y-2">
                <h4 className="font-medium">Workflow Changes</h4>
                {comparisonResult.workflows.length === 0 ? (
                  <p className="text-muted-foreground text-sm">No differences found between snapshots.</p>
                ) : (
                  <div className="space-y-2">
                    {comparisonResult.workflows.map((wf) => (
                      <div
                        key={wf.workflowId}
                        className={`p-3 rounded-md border ${
                          wf.status === 'added'
                            ? 'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950'
                            : wf.status === 'removed'
                            ? 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950'
                            : wf.status === 'modified'
                            ? 'border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950'
                            : 'border-border'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{wf.workflowName}</span>
                          <Badge
                            variant={
                              wf.status === 'added'
                                ? 'default'
                                : wf.status === 'removed'
                                ? 'destructive'
                                : wf.status === 'modified'
                                ? 'secondary'
                                : 'outline'
                            }
                          >
                            {wf.status}
                          </Badge>
                        </div>
                        {wf.changes && wf.changes.length > 0 && (
                          <ul className="mt-2 text-sm text-muted-foreground list-disc list-inside">
                            {wf.changes.map((change, i) => (
                              <li key={i}>{change}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
