import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { apiClient } from '@/lib/api-client';
import { useFeatures } from '@/lib/features';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from 'sonner';
import {
  ArrowLeft,
  AlertTriangle,
  Clock,
  CheckCircle2,
  Eye,
  GitMerge,
  Shield,
  User,
  Calendar,
  Timer,
  FileText,
  Loader2,
  Archive,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import type { DriftIncidentStatus, DriftApproval } from '@/types';

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

const SEVERITY_COLORS: Record<string, string> = {
  low: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  high: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  critical: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
};

export function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { canUseFeature } = useFeatures();

  const [actionDialog, setActionDialog] = useState<{
    type: 'acknowledge' | 'stabilize' | 'reconcile' | 'close' | null;
    open: boolean;
  }>({ type: null, open: false });
  const [actionReason, setActionReason] = useState('');
  const [approvalDialog, setApprovalDialog] = useState<{
    approval: DriftApproval | null;
    decision: 'approved' | 'rejected' | null;
  }>({ approval: null, decision: null });
  const [approvalReason, setApprovalReason] = useState('');

  useEffect(() => {
    document.title = 'Incident - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  // Feature check
  const hasDriftPolicies = canUseFeature('drift_policies');

  // Fetch incident
  const { data, isLoading, error } = useQuery({
    queryKey: ['incident', id],
    queryFn: () => apiClient.getIncident(id!),
    enabled: !!id,
  });

  // Fetch approvals for this incident
  const { data: approvalsData, isLoading: approvalsLoading } = useQuery({
    queryKey: ['incident-approvals', id],
    queryFn: () => apiClient.getDriftApprovals({ incidentId: id }),
    enabled: !!id && hasDriftPolicies,
  });

  const incident = data?.data;
  const approvals = approvalsData?.data || [];
  const pendingApprovals = approvals.filter((a: DriftApproval) => a.status === 'pending');

  // Transition mutation - uses specific API methods for each action
  const transitionMutation = useMutation({
    mutationFn: async (params: { action: 'acknowledge' | 'stabilize' | 'reconcile' | 'close'; reason?: string }) => {
      switch (params.action) {
        case 'acknowledge':
          return apiClient.acknowledgeIncident(id!, { reason: params.reason });
        case 'stabilize':
          return apiClient.stabilizeIncident(id!, params.reason);
        case 'reconcile':
          return apiClient.reconcileIncident(id!, { resolutionType: 'acknowledge', reason: params.reason });
        case 'close':
          return apiClient.closeIncident(id!, params.reason);
        default:
          throw new Error(`Unknown action: ${params.action}`);
      }
    },
    onSuccess: () => {
      toast.success('Incident updated successfully');
      queryClient.invalidateQueries({ queryKey: ['incident', id] });
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      setActionDialog({ type: null, open: false });
      setActionReason('');
    },
    onError: (error: any) => {
      toast.error(`Failed to update incident: ${error.message}`);
    },
  });

  // Approval decision mutation
  const approvalMutation = useMutation({
    mutationFn: (params: { approvalId: string; decision: 'approved' | 'rejected'; decisionNotes?: string }) =>
      apiClient.decideDriftApproval(params.approvalId, {
        decision: params.decision,
        decisionNotes: params.decisionNotes,
      }),
    onSuccess: () => {
      toast.success('Approval decision recorded');
      queryClient.invalidateQueries({ queryKey: ['incident-approvals', id] });
      queryClient.invalidateQueries({ queryKey: ['incident', id] });
      setApprovalDialog({ approval: null, decision: null });
      setApprovalReason('');
    },
    onError: (error: any) => {
      toast.error(`Failed to record decision: ${error.message}`);
    },
  });

  const handleAction = (type: 'acknowledge' | 'stabilize' | 'reconcile' | 'close') => {
    setActionDialog({ type, open: true });
    setActionReason('');
  };

  const executeAction = () => {
    if (!actionDialog.type) return;
    transitionMutation.mutate({
      action: actionDialog.type as 'acknowledge' | 'stabilize' | 'reconcile' | 'close',
      reason: actionReason || undefined,
    });
  };

  const handleApprovalDecision = (approval: DriftApproval, decision: 'approved' | 'rejected') => {
    setApprovalDialog({ approval, decision });
    setApprovalReason('');
  };

  const executeApprovalDecision = () => {
    if (!approvalDialog.approval || !approvalDialog.decision) return;
    approvalMutation.mutate({
      approvalId: approvalDialog.approval.id,
      decision: approvalDialog.decision,
      decisionNotes: approvalReason || undefined,
    });
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2" />
          Loading incident...
        </CardContent>
      </Card>
    );
  }

  if (error || !incident) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Incident not found</CardTitle>
          <CardDescription>The incident may not exist or you don't have access.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" onClick={() => navigate('/incidents')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Incidents
          </Button>
        </CardContent>
      </Card>
    );
  }

  const statusConfig = STATUS_CONFIG[incident.status as DriftIncidentStatus] || STATUS_CONFIG.detected;
  const StatusIcon = statusConfig.icon;
  const isOpen = incident.status !== 'closed';

  // Calculate TTL status
  const hasExpired = incident.ttl_expires_at && new Date(incident.ttl_expires_at) < new Date();
  const ttlDistance = incident.ttl_expires_at
    ? formatDistanceToNow(new Date(incident.ttl_expires_at), { addSuffix: true })
    : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/incidents')} className="mt-1">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <StatusIcon className="h-7 w-7" />
              {incident.title || `Drift Incident #${incident.id.slice(0, 8)}`}
            </h1>
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <Badge variant={statusConfig.variant}>
                {statusConfig.label}
              </Badge>
              {incident.severity && (
                <Badge className={SEVERITY_COLORS[incident.severity] || ''}>
                  {incident.severity.toUpperCase()}
                </Badge>
              )}
              {hasExpired && (
                <Badge variant="destructive" className="gap-1">
                  <Timer className="h-3 w-3" />
                  TTL Expired
                </Badge>
              )}
              {incident.environment_id && (
                <Link to={`/environments/${incident.environment_id}`} className="text-sm text-primary hover:underline">
                  View environment
                </Link>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        {isOpen && (
          <div className="flex gap-2">
            {incident.status === 'detected' && (
              <Button variant="outline" onClick={() => handleAction('acknowledge')}>
                <Eye className="h-4 w-4 mr-2" />
                Acknowledge
              </Button>
            )}
            {incident.status === 'acknowledged' && (
              <Button variant="outline" onClick={() => handleAction('stabilize')}>
                <Clock className="h-4 w-4 mr-2" />
                Mark Stabilized
              </Button>
            )}
            {(incident.status === 'stabilized' || incident.status === 'acknowledged') && (
              <Button variant="outline" onClick={() => handleAction('reconcile')}>
                <GitMerge className="h-4 w-4 mr-2" />
                Reconcile
              </Button>
            )}
            {incident.status !== 'closed' && (
              <Button variant="default" onClick={() => handleAction('close')}>
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Close
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Pending Approvals Alert */}
      {pendingApprovals.length > 0 && (
        <Card className="border-yellow-500">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2 text-yellow-600 dark:text-yellow-400">
              <Shield className="h-5 w-5" />
              Pending Approvals ({pendingApprovals.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {pendingApprovals.map((approval: DriftApproval) => (
                <div key={approval.id} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                  <div>
                    <p className="font-medium">{approval.approval_type.replace('_', ' ').toUpperCase()}</p>
                    <p className="text-sm text-muted-foreground">
                      Requested by {approval.requested_by} {' '}
                      {approval.created_at && formatDistanceToNow(new Date(approval.created_at), { addSuffix: true })}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="default"
                      onClick={() => handleApprovalDecision(approval, 'approved')}
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleApprovalDecision(approval, 'rejected')}
                    >
                      Reject
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="details">
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          {hasDriftPolicies && (
            <TabsTrigger value="approvals">
              Approvals {approvals.length > 0 && `(${approvals.length})`}
            </TabsTrigger>
          )}
          <TabsTrigger value="drift">Drift Summary</TabsTrigger>
        </TabsList>

        <TabsContent value="details" className="space-y-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Incident Information</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <div>
                <Label className="text-muted-foreground">Incident ID</Label>
                <p className="font-mono text-sm">{incident.id}</p>
              </div>
              <div>
                <Label className="text-muted-foreground">Environment</Label>
                <p>{incident.environment_name || incident.environment_id || '—'}</p>
              </div>
              <div>
                <Label className="text-muted-foreground">Detected At</Label>
                <p className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  {incident.detected_at
                    ? new Date(incident.detected_at).toLocaleString()
                    : incident.created_at
                    ? new Date(incident.created_at).toLocaleString()
                    : '—'}
                </p>
              </div>
              <div>
                <Label className="text-muted-foreground">Severity</Label>
                <p>
                  {incident.severity ? (
                    <Badge className={SEVERITY_COLORS[incident.severity] || ''}>
                      {incident.severity.toUpperCase()}
                    </Badge>
                  ) : (
                    '—'
                  )}
                </p>
              </div>
              {incident.ttl_expires_at && (
                <div>
                  <Label className="text-muted-foreground">TTL/SLA Deadline</Label>
                  <p className={`flex items-center gap-2 ${hasExpired ? 'text-red-600 dark:text-red-400' : ''}`}>
                    <Timer className="h-4 w-4" />
                    {new Date(incident.ttl_expires_at).toLocaleString()}
                    <span className="text-sm text-muted-foreground">({ttlDistance})</span>
                  </p>
                </div>
              )}
              {incident.assigned_to && (
                <div>
                  <Label className="text-muted-foreground">Assigned To</Label>
                  <p className="flex items-center gap-2">
                    <User className="h-4 w-4 text-muted-foreground" />
                    {incident.assigned_to}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {incident.description && (
            <Card>
              <CardHeader>
                <CardTitle>Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm">{incident.description}</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="timeline" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Incident Timeline</CardTitle>
              <CardDescription>History of status changes and actions</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <div className="mt-1 h-2 w-2 rounded-full bg-red-500" />
                  <div>
                    <p className="font-medium">Detected</p>
                    <p className="text-sm text-muted-foreground">
                      {incident.detected_at
                        ? new Date(incident.detected_at).toLocaleString()
                        : incident.created_at
                        ? new Date(incident.created_at).toLocaleString()
                        : '—'}
                    </p>
                  </div>
                </div>
                {incident.acknowledged_at && (
                  <div className="flex items-start gap-3">
                    <div className="mt-1 h-2 w-2 rounded-full bg-blue-500" />
                    <div>
                      <p className="font-medium">Acknowledged</p>
                      <p className="text-sm text-muted-foreground">
                        {new Date(incident.acknowledged_at).toLocaleString()}
                        {incident.acknowledged_by && ` by ${incident.acknowledged_by}`}
                      </p>
                    </div>
                  </div>
                )}
                {incident.stabilized_at && (
                  <div className="flex items-start gap-3">
                    <div className="mt-1 h-2 w-2 rounded-full bg-yellow-500" />
                    <div>
                      <p className="font-medium">Stabilized</p>
                      <p className="text-sm text-muted-foreground">
                        {new Date(incident.stabilized_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                )}
                {incident.reconciled_at && (
                  <div className="flex items-start gap-3">
                    <div className="mt-1 h-2 w-2 rounded-full bg-purple-500" />
                    <div>
                      <p className="font-medium">Reconciled</p>
                      <p className="text-sm text-muted-foreground">
                        {new Date(incident.reconciled_at).toLocaleString()}
                        {incident.resolution_type && ` (${incident.resolution_type})`}
                      </p>
                    </div>
                  </div>
                )}
                {incident.closed_at && (
                  <div className="flex items-start gap-3">
                    <div className="mt-1 h-2 w-2 rounded-full bg-green-500" />
                    <div>
                      <p className="font-medium">Closed</p>
                      <p className="text-sm text-muted-foreground">
                        {new Date(incident.closed_at).toLocaleString()}
                        {incident.closed_by && ` by ${incident.closed_by}`}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {hasDriftPolicies && (
          <TabsContent value="approvals" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle>Approval History</CardTitle>
                <CardDescription>Enterprise approval workflow for this incident</CardDescription>
              </CardHeader>
              <CardContent>
                {approvalsLoading ? (
                  <div className="text-center py-6">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                  </div>
                ) : approvals.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-6">
                    No approval requests for this incident.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {approvals.map((approval: DriftApproval) => (
                      <div key={approval.id} className="border rounded-lg p-4">
                        <div className="flex items-start justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <FileText className="h-4 w-4 text-muted-foreground" />
                              <span className="font-medium">
                                {approval.approval_type.replace('_', ' ').toUpperCase()}
                              </span>
                              <Badge
                                variant={
                                  approval.status === 'approved'
                                    ? 'default'
                                    : approval.status === 'rejected'
                                    ? 'destructive'
                                    : 'secondary'
                                }
                              >
                                {approval.status}
                              </Badge>
                            </div>
                            <p className="text-sm text-muted-foreground mt-1">
                              Requested by {approval.requested_by}
                              {approval.created_at &&
                                ` ${formatDistanceToNow(new Date(approval.created_at), { addSuffix: true })}`}
                            </p>
                            {approval.request_reason && (
                              <p className="text-sm mt-2">{approval.request_reason}</p>
                            )}
                          </div>
                          {approval.status === 'pending' && (
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                variant="default"
                                onClick={() => handleApprovalDecision(approval, 'approved')}
                              >
                                Approve
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleApprovalDecision(approval, 'rejected')}
                              >
                                Reject
                              </Button>
                            </div>
                          )}
                        </div>
                        {approval.decided_at && (
                          <p className="text-xs text-muted-foreground mt-2">
                            Decided by {approval.decided_by}{' '}
                            {formatDistanceToNow(new Date(approval.decided_at), { addSuffix: true })}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}

        <TabsContent value="drift" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Drift Summary</CardTitle>
              <CardDescription>Detected differences between runtime and Git source</CardDescription>
            </CardHeader>
            <CardContent>
              {/* Show banner if payload was purged per retention policy */}
              {incident.payload_available === false && (
                <Alert className="mb-4">
                  <Archive className="h-4 w-4" />
                  <AlertTitle>Drift details purged</AlertTitle>
                  <AlertDescription>
                    The detailed drift data for this incident was purged per your organization's retention policy.
                    Incident metadata (timeline, status, ownership) is still available.
                    {incident.payload_purged_at && (
                      <span className="block text-xs text-muted-foreground mt-1">
                        Purged on {new Date(incident.payload_purged_at).toLocaleDateString()}
                      </span>
                    )}
                  </AlertDescription>
                </Alert>
              )}

              {incident.payload_available !== false && incident.summary ? (
                <pre className="text-xs bg-muted/40 rounded p-3 overflow-auto max-h-96">
                  {typeof incident.summary === 'string'
                    ? incident.summary
                    : JSON.stringify(incident.summary, null, 2)}
                </pre>
              ) : incident.payload_available !== false ? (
                <p className="text-sm text-muted-foreground text-center py-6">
                  No drift summary available.
                </p>
              ) : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Action Dialog */}
      <Dialog open={actionDialog.open} onOpenChange={(open) => setActionDialog({ ...actionDialog, open })}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {actionDialog.type === 'acknowledge' && 'Acknowledge Incident'}
              {actionDialog.type === 'stabilize' && 'Mark as Stabilized'}
              {actionDialog.type === 'reconcile' && 'Reconcile Incident'}
              {actionDialog.type === 'close' && 'Close Incident'}
            </DialogTitle>
            <DialogDescription>
              {actionDialog.type === 'acknowledge' && 'Acknowledging indicates you are aware of and investigating this incident.'}
              {actionDialog.type === 'stabilize' && 'Marking as stabilized indicates the immediate issue is contained.'}
              {actionDialog.type === 'reconcile' && 'Reconciling indicates the drift has been resolved (promoted, reverted, or accepted).'}
              {actionDialog.type === 'close' && 'Closing the incident marks it as fully resolved.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="reason">Reason (optional)</Label>
              <Textarea
                id="reason"
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                placeholder="Add a note about this action..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setActionDialog({ type: null, open: false })}>
              Cancel
            </Button>
            <Button onClick={executeAction} disabled={transitionMutation.isPending}>
              {transitionMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Approval Decision Dialog */}
      <Dialog
        open={approvalDialog.approval !== null}
        onOpenChange={(open) => !open && setApprovalDialog({ approval: null, decision: null })}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {approvalDialog.decision === 'approved' ? 'Approve Request' : 'Reject Request'}
            </DialogTitle>
            <DialogDescription>
              {approvalDialog.decision === 'approved'
                ? 'You are approving this request. The action will proceed.'
                : 'You are rejecting this request. The action will be blocked.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="approval-reason">Reason (optional)</Label>
              <Textarea
                id="approval-reason"
                value={approvalReason}
                onChange={(e) => setApprovalReason(e.target.value)}
                placeholder="Add a note about your decision..."
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setApprovalDialog({ approval: null, decision: null })}>
              Cancel
            </Button>
            <Button
              variant={approvalDialog.decision === 'rejected' ? 'destructive' : 'default'}
              onClick={executeApprovalDecision}
              disabled={approvalMutation.isPending}
            >
              {approvalMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {approvalDialog.decision === 'approved' ? 'Approve' : 'Reject'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
