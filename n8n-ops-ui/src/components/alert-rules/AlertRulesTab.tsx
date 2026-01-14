import React, { useState } from 'react';
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  AlertTriangle,
  Plus,
  MoreVertical,
  Edit,
  Trash2,
  Play,
  VolumeX,
  Volume2,
  History,
  Loader2,
  XCircle,
  Zap,
  Clock,
  Hash,
  RefreshCw,
  Bell,
  TrendingUp,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import { AlertRuleBuilder } from './AlertRuleBuilder';
import type {
  AlertRule,
  AlertRuleCreate,
  AlertRuleType,
  NotificationChannel,
  Environment,
} from '@/types';

interface AlertRulesTabProps {
  channels: NotificationChannel[];
  environments: Environment[];
}

const RULE_TYPE_ICONS: Record<AlertRuleType, React.ReactNode> = {
  error_rate: <AlertTriangle className="h-4 w-4" />,
  error_type: <XCircle className="h-4 w-4" />,
  workflow_failure: <Zap className="h-4 w-4" />,
  consecutive_failures: <Hash className="h-4 w-4" />,
  execution_duration: <Clock className="h-4 w-4" />,
};

const RULE_TYPE_LABELS: Record<AlertRuleType, string> = {
  error_rate: 'Error Rate',
  error_type: 'Error Type',
  workflow_failure: 'Workflow Failure',
  consecutive_failures: 'Consecutive Failures',
  execution_duration: 'Duration',
};

export function AlertRulesTab({ channels, environments }: AlertRulesTabProps) {
  const queryClient = useQueryClient();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AlertRule | undefined>();
  const [muteDialogOpen, setMuteDialogOpen] = useState(false);
  const [selectedRuleForMute, setSelectedRuleForMute] = useState<AlertRule | null>(null);
  const [muteDuration, setMuteDuration] = useState(60);
  const [muteReason, setMuteReason] = useState('');
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [selectedRuleForHistory, setSelectedRuleForHistory] = useState<AlertRule | null>(null);

  // Queries
  const { data: rulesData, isLoading: rulesLoading } = useQuery({
    queryKey: ['alert-rules'],
    queryFn: () => apiClient.getAlertRules({ includeDisabled: true }),
  });

  const { data: summaryData } = useQuery({
    queryKey: ['alert-rules-summary'],
    queryFn: () => apiClient.getAlertRulesSummary(),
  });

  const { data: catalogData } = useQuery({
    queryKey: ['alert-rules-catalog'],
    queryFn: () => apiClient.getAlertRuleTypeCatalog(),
  });

  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ['alert-rule-history', selectedRuleForHistory?.id],
    queryFn: () =>
      selectedRuleForHistory
        ? apiClient.getAlertRuleHistory(selectedRuleForHistory.id, { limit: 50 })
        : Promise.resolve({ data: { items: [], total: 0, hasMore: false } }),
    enabled: !!selectedRuleForHistory,
  });

  const rules = rulesData?.data ?? [];
  const summary = summaryData?.data;
  const catalog = catalogData?.data ?? [];

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: AlertRuleCreate) => apiClient.createAlertRule(data),
    onSuccess: () => {
      toast.success('Alert rule created');
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] });
      queryClient.invalidateQueries({ queryKey: ['alert-rules-summary'] });
      setCreateDialogOpen(false);
    },
    onError: (error: Error) => {
      toast.error('Failed to create alert rule', { description: error.message });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: AlertRuleCreate }) =>
      apiClient.updateAlertRule(id, data),
    onSuccess: () => {
      toast.success('Alert rule updated');
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] });
      queryClient.invalidateQueries({ queryKey: ['alert-rules-summary'] });
      setEditingRule(undefined);
    },
    onError: (error: Error) => {
      toast.error('Failed to update alert rule', { description: error.message });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteAlertRule(id),
    onSuccess: () => {
      toast.success('Alert rule deleted');
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] });
      queryClient.invalidateQueries({ queryKey: ['alert-rules-summary'] });
    },
    onError: (error: Error) => {
      toast.error('Failed to delete alert rule', { description: error.message });
    },
  });

  const muteMutation = useMutation({
    mutationFn: ({ id, duration, reason }: { id: string; duration: number; reason?: string }) =>
      apiClient.muteAlertRule(id, { mute_duration_minutes: duration, reason }),
    onSuccess: () => {
      toast.success('Alert rule muted');
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] });
      queryClient.invalidateQueries({ queryKey: ['alert-rules-summary'] });
      setMuteDialogOpen(false);
      setSelectedRuleForMute(null);
    },
    onError: (error: Error) => {
      toast.error('Failed to mute alert rule', { description: error.message });
    },
  });

  const unmuteMutation = useMutation({
    mutationFn: (id: string) => apiClient.unmuteAlertRule(id),
    onSuccess: () => {
      toast.success('Alert rule unmuted');
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] });
      queryClient.invalidateQueries({ queryKey: ['alert-rules-summary'] });
    },
    onError: (error: Error) => {
      toast.error('Failed to unmute alert rule', { description: error.message });
    },
  });

  const evaluateMutation = useMutation({
    mutationFn: (id: string) => apiClient.evaluateAlertRule(id),
    onSuccess: (result) => {
      const { isTriggered, message } = result.data;
      if (isTriggered) {
        toast.warning('Rule triggered', { description: message });
      } else {
        toast.success('Rule not triggered', { description: message });
      }
      queryClient.invalidateQueries({ queryKey: ['alert-rules'] });
    },
    onError: (error: Error) => {
      toast.error('Failed to evaluate rule', { description: error.message });
    },
  });

  const handleSave = async (data: AlertRuleCreate) => {
    if (editingRule) {
      await updateMutation.mutateAsync({ id: editingRule.id, data });
    } else {
      await createMutation.mutateAsync(data);
    }
  };

  const handleMute = (rule: AlertRule) => {
    setSelectedRuleForMute(rule);
    setMuteDuration(60);
    setMuteReason('');
    setMuteDialogOpen(true);
  };

  const handleShowHistory = (rule: AlertRule) => {
    setSelectedRuleForHistory(rule);
    setHistoryDialogOpen(true);
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  const isMuted = (rule: AlertRule) => {
    if (!rule.mutedUntil) return false;
    return new Date(rule.mutedUntil) > new Date();
  };

  const getThresholdDisplay = (rule: AlertRule) => {
    const config = rule.thresholdConfig;
    switch (rule.ruleType) {
      case 'error_rate':
        return `> ${config.threshold_percent || 0}%`;
      case 'error_type':
        const types = (config.error_types as string[]) || [];
        return types.length > 0 ? types.slice(0, 2).join(', ') + (types.length > 2 ? '...' : '') : '-';
      case 'workflow_failure':
        return config.any_workflow ? 'Any workflow' : `${((config.workflow_ids as string[]) || []).length} workflows`;
      case 'consecutive_failures':
        return `${config.failure_count || 0} failures`;
      case 'execution_duration':
        return `> ${((config.max_duration_ms as number) || 0) / 1000}s`;
      default:
        return '-';
    }
  };

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      {summary && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Rules</CardTitle>
              <Bell className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary.totalRules}</div>
              <p className="text-xs text-muted-foreground">
                {summary.enabledRules} enabled
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Firing</CardTitle>
              <AlertTriangle className="h-4 w-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-500">{summary.firingRules}</div>
              <p className="text-xs text-muted-foreground">
                Active alerts
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Muted</CardTitle>
              <VolumeX className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary.mutedRules}</div>
              <p className="text-xs text-muted-foreground">
                Temporarily silenced
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">By Type</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-1">
                {Object.entries(summary.rulesByType).map(([type, count]) => (
                  <Badge key={type} variant="outline" className="text-xs">
                    {RULE_TYPE_LABELS[type as AlertRuleType] || type}: {count}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Rules Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Alert Rules</CardTitle>
              <CardDescription>
                Threshold-based rules with escalation policies
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => queryClient.invalidateQueries({ queryKey: ['alert-rules'] })}
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                Refresh
              </Button>
              <Button size="sm" onClick={() => setCreateDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-1" />
                Create Rule
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {rulesLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : rules.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <AlertTriangle className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>No alert rules configured</p>
              <p className="text-sm">Create a rule to start monitoring</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Threshold</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Evaluated</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule) => (
                  <TableRow key={rule.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{rule.name}</p>
                        {rule.description && (
                          <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                            {rule.description}
                          </p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {RULE_TYPE_ICONS[rule.ruleType]}
                        <span className="text-sm">
                          {RULE_TYPE_LABELS[rule.ruleType]}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <code className="text-xs bg-muted px-1 py-0.5 rounded">
                        {getThresholdDisplay(rule)}
                      </code>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        {!rule.isEnabled ? (
                          <Badge variant="outline">Disabled</Badge>
                        ) : isMuted(rule) ? (
                          <Badge variant="secondary">
                            <VolumeX className="h-3 w-3 mr-1" />
                            Muted
                          </Badge>
                        ) : rule.isFiring ? (
                          <Badge variant="destructive">
                            <AlertTriangle className="h-3 w-3 mr-1" />
                            Firing
                          </Badge>
                        ) : (
                          <Badge variant="success">OK</Badge>
                        )}
                        {rule.consecutiveViolations > 0 && (
                          <span className="text-xs text-muted-foreground">
                            ({rule.consecutiveViolations}x)
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {rule.lastEvaluatedAt ? (
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(rule.lastEvaluatedAt)}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">Never</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => setEditingRule(rule)}>
                            <Edit className="h-4 w-4 mr-2" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => evaluateMutation.mutate(rule.id)}
                            disabled={evaluateMutation.isPending}
                          >
                            <Play className="h-4 w-4 mr-2" />
                            Evaluate Now
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleShowHistory(rule)}>
                            <History className="h-4 w-4 mr-2" />
                            View History
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          {isMuted(rule) ? (
                            <DropdownMenuItem
                              onClick={() => unmuteMutation.mutate(rule.id)}
                            >
                              <Volume2 className="h-4 w-4 mr-2" />
                              Unmute
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem onClick={() => handleMute(rule)}>
                              <VolumeX className="h-4 w-4 mr-2" />
                              Mute
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => {
                              if (confirm('Delete this alert rule?')) {
                                deleteMutation.mutate(rule.id);
                              }
                            }}
                            className="text-destructive"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <AlertRuleBuilder
        open={createDialogOpen || !!editingRule}
        onOpenChange={(open) => {
          if (!open) {
            setCreateDialogOpen(false);
            setEditingRule(undefined);
          }
        }}
        onSave={handleSave}
        editingRule={editingRule}
        ruleTypeCatalog={catalog}
        channels={channels}
        environments={environments}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Mute Dialog */}
      <Dialog open={muteDialogOpen} onOpenChange={setMuteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mute Alert Rule</DialogTitle>
            <DialogDescription>
              Temporarily silence notifications for "{selectedRuleForMute?.name}"
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="muteDuration">Duration (minutes)</Label>
              <Input
                id="muteDuration"
                type="number"
                min={1}
                max={43200}
                value={muteDuration}
                onChange={(e) => setMuteDuration(Number(e.target.value))}
                className="mt-1"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Max: 43200 minutes (30 days)
              </p>
            </div>
            <div>
              <Label htmlFor="muteReason">Reason (optional)</Label>
              <Input
                id="muteReason"
                value={muteReason}
                onChange={(e) => setMuteReason(e.target.value)}
                placeholder="e.g., Scheduled maintenance"
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMuteDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                selectedRuleForMute &&
                muteMutation.mutate({
                  id: selectedRuleForMute.id,
                  duration: muteDuration,
                  reason: muteReason || undefined,
                })
              }
              disabled={muteMutation.isPending}
            >
              {muteMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Mute Rule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* History Dialog */}
      <Dialog open={historyDialogOpen} onOpenChange={setHistoryDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Alert Rule History</DialogTitle>
            <DialogDescription>
              Recent activity for "{selectedRuleForHistory?.name}"
            </DialogDescription>
          </DialogHeader>
          <div className="overflow-y-auto max-h-[50vh]">
            {historyLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : historyData?.data.items.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <History className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>No history available</p>
              </div>
            ) : (
              <div className="space-y-2">
                {historyData?.data.items.map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-start gap-3 p-3 rounded-lg border text-sm"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs capitalize">
                          {entry.eventType}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(entry.createdAt)}
                        </span>
                      </div>
                      {entry.evaluationResult && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {(entry.evaluationResult as Record<string, unknown>).message as string || JSON.stringify(entry.evaluationResult)}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setHistoryDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
