import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Camera, History, RotateCcw, Search, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api-client';

interface Snapshot {
  id: string;
  workflow_id: string;
  workflow_name: string;
  version: number;
  trigger: string;
  created_at: string;
}

export function SnapshotsPage() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>('');
  const [rollbackSnapshot, setRollbackSnapshot] = useState<Snapshot | null>(null);

  // Fetch environments to get workflow list
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  // Fetch workflows from first environment to get workflow IDs
  const { data: workflows } = useQuery({
    queryKey: ['workflows-list'],
    queryFn: async () => {
      if (!environments?.data?.[0]) return { data: [] };
      const env = environments.data[0];
      return apiClient.getWorkflows(env.type, false);
    },
    enabled: !!environments?.data?.[0],
  });

  // Fetch snapshots for selected workflow
  const {
    data: snapshots,
    isLoading: loadingSnapshots,
  } = useQuery({
    queryKey: ['snapshots', selectedWorkflowId],
    queryFn: () => apiClient.getWorkflowSnapshots(selectedWorkflowId),
    enabled: !!selectedWorkflowId,
  });

  // Rollback mutation
  const rollbackMutation = useMutation({
    mutationFn: (snapshotId: string) => apiClient.rollbackWorkflow(snapshotId),
    onSuccess: (response) => {
      toast.success(response.data.message);
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      queryClient.invalidateQueries({ queryKey: ['snapshots'] });
      setRollbackSnapshot(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to rollback workflow');
    },
  });

  const handleRollback = (snapshot: Snapshot) => {
    setRollbackSnapshot(snapshot);
  };

  const confirmRollback = () => {
    if (rollbackSnapshot) {
      rollbackMutation.mutate(rollbackSnapshot.id);
    }
  };

  const getTriggerBadgeVariant = (trigger: string) => {
    switch (trigger) {
      case 'auto-before-restore':
        return 'secondary';
      case 'auto-before-rollback':
        return 'outline';
      case 'manual':
        return 'default';
      default:
        return 'outline';
    }
  };

  const formatTrigger = (trigger: string) => {
    switch (trigger) {
      case 'auto-before-restore':
        return 'Before Restore';
      case 'auto-before-rollback':
        return 'Before Rollback';
      case 'auto-before-deploy':
        return 'Before Deploy';
      case 'manual':
        return 'Manual';
      default:
        return trigger;
    }
  };

  // Filter workflows by search
  const filteredWorkflows = workflows?.data?.filter((wf) =>
    wf.name.toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  // Get unique workflow IDs from available workflows
  const workflowOptions = filteredWorkflows.map((wf) => ({
    id: wf.id,
    name: wf.name,
  }));

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

      {/* Workflow Selector */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Camera className="h-5 w-5" />
            Select Workflow
          </CardTitle>
          <CardDescription>
            Choose a workflow to view its snapshot history
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search workflows..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <Select value={selectedWorkflowId} onValueChange={setSelectedWorkflowId}>
              <SelectTrigger className="w-[300px]">
                <SelectValue placeholder="Select a workflow" />
              </SelectTrigger>
              <SelectContent>
                {workflowOptions.map((wf) => (
                  <SelectItem key={wf.id} value={wf.id}>
                    {wf.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Snapshot History */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <History className="h-5 w-5" />
            Snapshot History
          </CardTitle>
          <CardDescription>
            {selectedWorkflowId
              ? 'View and restore previous versions'
              : 'Select a workflow to view its snapshot history'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!selectedWorkflowId ? (
            <p className="text-muted-foreground text-center py-8">
              Select a workflow above to view its snapshot history
            </p>
          ) : loadingSnapshots ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <span className="ml-2">Loading snapshots...</span>
            </div>
          ) : snapshots?.data && snapshots.data.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Version</TableHead>
                  <TableHead>Workflow</TableHead>
                  <TableHead>Trigger</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {snapshots.data.map((snapshot) => (
                  <TableRow key={snapshot.id}>
                    <TableCell>
                      <Badge variant="outline">v{snapshot.version}</Badge>
                    </TableCell>
                    <TableCell className="font-medium">
                      {snapshot.workflow_name}
                    </TableCell>
                    <TableCell>
                      <Badge variant={getTriggerBadgeVariant(snapshot.trigger)}>
                        {formatTrigger(snapshot.trigger)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(snapshot.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRollback(snapshot)}
                      >
                        <RotateCcw className="h-3 w-3 mr-1" />
                        Rollback
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-muted-foreground text-center py-8">
              No snapshots found for this workflow. Snapshots are created automatically
              when restoring from GitHub.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Rollback Confirmation Dialog */}
      <AlertDialog
        open={!!rollbackSnapshot}
        onOpenChange={(open) => !open && setRollbackSnapshot(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Rollback</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to rollback "{rollbackSnapshot?.workflow_name}" to
              version {rollbackSnapshot?.version}?
              <br />
              <br />
              This will replace the current workflow in N8N with the snapshot version.
              A new snapshot will be created automatically before the rollback.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmRollback}
              disabled={rollbackMutation.isPending}
            >
              {rollbackMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Rolling back...
                </>
              ) : (
                <>
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Rollback
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
