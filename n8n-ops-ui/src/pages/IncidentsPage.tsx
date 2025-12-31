import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import {
  AlertTriangle,
  Clock,
  CheckCircle2,
  Eye,
  GitMerge,
  RefreshCw,
  User,
  ExternalLink,
  Filter,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { useAppStore } from '@/store/use-app-store';
import { useFeatures } from '@/lib/features';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import type { DriftIncident, DriftIncidentStatus } from '@/types';
import { SmartEmptyState } from '@/components/SmartEmptyState';

const STATUS_CONFIG: Record<DriftIncidentStatus, {
  label: string;
  variant: 'default' | 'secondary' | 'destructive' | 'outline';
  icon: typeof AlertTriangle;
}> = {
  detected: { label: 'Detected', variant: 'destructive', icon: AlertTriangle },
  acknowledged: { label: 'Acknowledged', variant: 'default', icon: Eye },
  stabilized: { label: 'Stabilized', variant: 'secondary', icon: Clock },
  reconciled: { label: 'Reconciled', variant: 'outline', icon: GitMerge },
  closed: { label: 'Closed', variant: 'outline', icon: CheckCircle2 },
};

export function IncidentsPage() {
  const queryClient = useQueryClient();
  const { selectedEnvironment } = useAppStore();
  const { canUseFeature } = useFeatures();

  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedIncident, setSelectedIncident] = useState<DriftIncident | null>(null);
  const [actionDialog, setActionDialog] = useState<{
    type: 'acknowledge' | 'stabilize' | 'reconcile' | 'close' | null;
    incident: DriftIncident | null;
  }>({ type: null, incident: null });
  const [actionReason, setActionReason] = useState('');
  const [actionTicketRef, setActionTicketRef] = useState('');
  const [resolutionType, setResolutionType] = useState<'promote' | 'revert' | 'replace' | 'acknowledge'>('promote');

  useEffect(() => {
    document.title = 'Incidents - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  // Check feature access
  const hasDriftIncidents = canUseFeature('drift_incidents');

  // Fetch incidents
  const { data: incidentsData, isLoading, error, refetch } = useQuery({
    queryKey: ['incidents', selectedEnvironment, statusFilter],
    queryFn: async () => {
      const response = await apiClient.getIncidents({
        environmentId: selectedEnvironment || undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        limit: 100,
      });
      return response.data;
    },
    enabled: hasDriftIncidents,
    retry: (failureCount, error) => {
      // Don't retry on 503 - service is down
      if ((error as any)?.response?.status === 503) return false;
      return failureCount < 2;
    },
    keepPreviousData: true, // Cached data fallback
  });

  // Fetch environments for lookup
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: async () => {
      const response = await apiClient.getEnvironments();
      return response.data;
    },
  });

  // Fetch stats
  const { data: stats } = useQuery({
    queryKey: ['incident-stats', selectedEnvironment],
    queryFn: async () => {
      const response = await apiClient.getIncidentStats(selectedEnvironment || undefined);
      return response.data;
    },
    enabled: hasDriftIncidents,
  });

  // Mutations
  const acknowledgeMutation = useMutation({
    mutationFn: ({ id, reason, ticketRef }: { id: string; reason?: string; ticketRef?: string }) =>
      apiClient.acknowledgeIncident(id, { reason, ticketRef }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['incident-stats'] });
      toast.success('Incident acknowledged');
      closeActionDialog();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to acknowledge incident');
    },
  });

  const stabilizeMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      apiClient.stabilizeIncident(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['incident-stats'] });
      toast.success('Incident marked as stabilized');
      closeActionDialog();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to stabilize incident');
    },
  });

  const reconcileMutation = useMutation({
    mutationFn: ({ id, resolutionType, reason }: { id: string; resolutionType: any; reason?: string }) =>
      apiClient.reconcileIncident(id, { resolutionType, reason }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['incident-stats'] });
      toast.success('Incident reconciled');
      closeActionDialog();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to reconcile incident');
    },
  });

  const closeMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      apiClient.closeIncident(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      queryClient.invalidateQueries({ queryKey: ['incident-stats'] });
      toast.success('Incident closed');
      closeActionDialog();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to close incident');
    },
  });

  const closeActionDialog = () => {
    setActionDialog({ type: null, incident: null });
    setActionReason('');
    setActionTicketRef('');
    setResolutionType('promote');
  };

  const handleAction = () => {
    if (!actionDialog.incident) return;

    const id = actionDialog.incident.id;

    switch (actionDialog.type) {
      case 'acknowledge':
        acknowledgeMutation.mutate({ id, reason: actionReason, ticketRef: actionTicketRef });
        break;
      case 'stabilize':
        stabilizeMutation.mutate({ id, reason: actionReason });
        break;
      case 'reconcile':
        reconcileMutation.mutate({ id, resolutionType, reason: actionReason });
        break;
      case 'close':
        closeMutation.mutate({ id, reason: actionReason });
        break;
    }
  };

  const getEnvironmentName = (envId: string) => {
    const env = environments?.find((e: any) => e.id === envId);
    return env?.name || envId.slice(0, 8);
  };

  const getAvailableActions = (incident: DriftIncident) => {
    const actions: Array<{ label: string; type: 'acknowledge' | 'stabilize' | 'reconcile' | 'close' }> = [];

    switch (incident.status) {
      case 'detected':
        actions.push({ label: 'Acknowledge', type: 'acknowledge' });
        actions.push({ label: 'Close', type: 'close' });
        break;
      case 'acknowledged':
        actions.push({ label: 'Stabilize', type: 'stabilize' });
        actions.push({ label: 'Reconcile', type: 'reconcile' });
        actions.push({ label: 'Close', type: 'close' });
        break;
      case 'stabilized':
        actions.push({ label: 'Reconcile', type: 'reconcile' });
        actions.push({ label: 'Close', type: 'close' });
        break;
      case 'reconciled':
        actions.push({ label: 'Close', type: 'close' });
        break;
    }

    return actions;
  };

  if (!hasDriftIncidents) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <AlertTriangle className="h-6 w-6" />
            Drift Incidents
          </h1>
          <p className="text-muted-foreground">Manage and resolve drift incidents</p>
        </div>
        <Card>
          <CardContent className="py-12 text-center">
            <AlertTriangle className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Upgrade Required</h3>
            <p className="text-muted-foreground mb-4">
              Drift Incident Management requires a Pro plan or higher.
            </p>
            <Button asChild>
              <Link to="/billing">View Plans</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Handle service errors with SmartEmptyState
  if (error && !isLoading && !incidentsData) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <AlertTriangle className="h-6 w-6" />
              Drift Incidents
            </h1>
            <p className="text-muted-foreground">Manage and resolve drift incidents across environments</p>
          </div>
        </div>
        <SmartEmptyState
          title="Unable to load incidents"
          error={error as Error}
          isLoading={isLoading}
          onRetry={refetch}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <AlertTriangle className="h-6 w-6" />
            Drift Incidents
          </h1>
          <p className="text-muted-foreground">Manage and resolve drift incidents across environments</p>
        </div>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Total Incidents</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Open</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-destructive">{stats.open}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Detected</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.by_status?.detected || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Closed</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-muted-foreground">{stats.by_status?.closed || 0}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Filters
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            <div className="w-48">
              <Label className="text-xs text-muted-foreground">Status</Label>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="All statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="detected">Detected</SelectItem>
                  <SelectItem value="acknowledged">Acknowledged</SelectItem>
                  <SelectItem value="stabilized">Stabilized</SelectItem>
                  <SelectItem value="reconciled">Reconciled</SelectItem>
                  <SelectItem value="closed">Closed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Incidents Table */}
      <Card>
        <CardHeader>
          <CardTitle>Incidents</CardTitle>
          <CardDescription>
            {incidentsData?.length || 0} incident(s)
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">Loading incidents...</div>
          ) : !incidentsData?.length ? (
            <div className="text-center py-8">
              <CheckCircle2 className="mx-auto h-12 w-12 text-green-500 mb-4" />
              <h3 className="text-lg font-semibold mb-2">No Drift Incidents</h3>
              <p className="text-muted-foreground">
                All environments are in sync with their Git source of truth.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Environment</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Affected Workflows</TableHead>
                  <TableHead>Detected</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {incidentsData.map((incident: DriftIncident) => {
                  const statusConfig = STATUS_CONFIG[incident.status] || STATUS_CONFIG.detected;
                  const StatusIcon = statusConfig.icon;
                  const actions = getAvailableActions(incident);

                  return (
                    <TableRow key={incident.id}>
                      <TableCell>
                        <Badge variant={statusConfig.variant} className="gap-1">
                          <StatusIcon className="h-3 w-3" />
                          {statusConfig.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Link
                          to={`/environments/${incident.environment_id}`}
                          className="text-primary hover:underline"
                        >
                          {getEnvironmentName(incident.environment_id)}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <div className="font-medium">
                          {incident.title || 'Untitled Incident'}
                        </div>
                        {incident.ticket_ref && (
                          <div className="text-xs text-muted-foreground flex items-center gap-1">
                            <ExternalLink className="h-3 w-3" />
                            {incident.ticket_ref}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">
                          {incident.affected_workflows?.length || 0} workflow(s)
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          {incident.detected_at
                            ? formatDistanceToNow(new Date(incident.detected_at), { addSuffix: true })
                            : 'Unknown'}
                        </div>
                      </TableCell>
                      <TableCell>
                        {incident.owner_user_id ? (
                          <div className="flex items-center gap-1 text-sm">
                            <User className="h-3 w-3" />
                            Assigned
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-sm">Unassigned</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedIncident(incident)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          {actions.length > 0 && (
                            <Select
                              onValueChange={(type) =>
                                setActionDialog({ type: type as any, incident })
                              }
                            >
                              <SelectTrigger className="w-[120px] h-8">
                                <SelectValue placeholder="Actions" />
                              </SelectTrigger>
                              <SelectContent>
                                {actions.map((action) => (
                                  <SelectItem key={action.type} value={action.type}>
                                    {action.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Detail Dialog */}
      <Dialog open={!!selectedIncident} onOpenChange={() => setSelectedIncident(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Incident Details</DialogTitle>
            <DialogDescription>
              {selectedIncident?.title || 'Untitled Incident'}
            </DialogDescription>
          </DialogHeader>
          {selectedIncident && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-xs text-muted-foreground">Status</Label>
                  <div className="mt-1">
                    <Badge variant={(STATUS_CONFIG[selectedIncident.status] || STATUS_CONFIG.detected).variant}>
                      {(STATUS_CONFIG[selectedIncident.status] || STATUS_CONFIG.detected).label}
                    </Badge>
                  </div>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Environment</Label>
                  <div className="mt-1 font-medium">
                    {getEnvironmentName(selectedIncident.environment_id)}
                  </div>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Detected</Label>
                  <div className="mt-1">
                    {selectedIncident.detected_at
                      ? new Date(selectedIncident.detected_at).toLocaleString()
                      : 'Unknown'}
                  </div>
                </div>
                {selectedIncident.acknowledged_at && (
                  <div>
                    <Label className="text-xs text-muted-foreground">Acknowledged</Label>
                    <div className="mt-1">
                      {new Date(selectedIncident.acknowledged_at).toLocaleString()}
                    </div>
                  </div>
                )}
                {selectedIncident.reason && (
                  <div className="col-span-2">
                    <Label className="text-xs text-muted-foreground">Reason</Label>
                    <div className="mt-1">{selectedIncident.reason}</div>
                  </div>
                )}
              </div>

              {selectedIncident.affected_workflows?.length > 0 && (
                <div>
                  <Label className="text-xs text-muted-foreground">Affected Workflows</Label>
                  <div className="mt-2 space-y-2">
                    {selectedIncident.affected_workflows.map((w: any, i: number) => (
                      <div key={i} className="flex items-center justify-between p-2 bg-muted rounded">
                        <span className="font-medium">{w.workflow_name}</span>
                        <Badge variant="outline">{w.drift_type}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelectedIncident(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Action Dialog */}
      <Dialog open={!!actionDialog.type} onOpenChange={closeActionDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {actionDialog.type === 'acknowledge' && 'Acknowledge Incident'}
              {actionDialog.type === 'stabilize' && 'Mark as Stabilized'}
              {actionDialog.type === 'reconcile' && 'Reconcile Incident'}
              {actionDialog.type === 'close' && 'Close Incident'}
            </DialogTitle>
            <DialogDescription>
              {actionDialog.type === 'acknowledge' && 'Acknowledge this drift incident and optionally assign an owner.'}
              {actionDialog.type === 'stabilize' && 'Mark this incident as stabilized (no new drift changes).'}
              {actionDialog.type === 'reconcile' && 'Record how this drift was resolved.'}
              {actionDialog.type === 'close' && 'Close this incident.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {actionDialog.type === 'reconcile' && (
              <div>
                <Label>Resolution Type</Label>
                <Select value={resolutionType} onValueChange={(v) => setResolutionType(v as any)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="promote">Promote - Runtime changes pushed to Git</SelectItem>
                    <SelectItem value="revert">Revert - Runtime reverted to match Git</SelectItem>
                    <SelectItem value="replace">Replace - Git updated via external process</SelectItem>
                    <SelectItem value="acknowledge">Acknowledge - Drift accepted as-is</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            {actionDialog.type === 'acknowledge' && (
              <div>
                <Label>Ticket Reference (Optional)</Label>
                <Input
                  placeholder="e.g., JIRA-123"
                  value={actionTicketRef}
                  onChange={(e) => setActionTicketRef(e.target.value)}
                />
              </div>
            )}
            <div>
              <Label>Reason (Optional)</Label>
              <Textarea
                placeholder="Add notes about this action..."
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeActionDialog}>
              Cancel
            </Button>
            <Button onClick={handleAction}>
              {actionDialog.type === 'acknowledge' && 'Acknowledge'}
              {actionDialog.type === 'stabilize' && 'Mark Stabilized'}
              {actionDialog.type === 'reconcile' && 'Reconcile'}
              {actionDialog.type === 'close' && 'Close Incident'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
