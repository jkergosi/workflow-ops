// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  FileText,
  Search,
  Download,
  User,
  Clock,
  Activity,
  Shield,
  Settings,
  Workflow,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Filter,
  X,
  ExternalLink,
  Building2,
  CreditCard,
  AlertTriangle,
  Eye,
  Server,
} from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';
import { exportToCSV } from '@/lib/export-utils';
import type { AuditLog } from '@/types';

// Action type presets for quick filtering
const ACTION_PRESETS = [
  { id: 'all', label: 'All', filter: 'all' },
  { id: 'tenant', label: 'Tenant', filter: 'tenant', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' },
  { id: 'user', label: 'Users', filter: 'user', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300' },
  { id: 'feature', label: 'Features', filter: 'feature', color: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' },
  { id: 'billing', label: 'Billing', filter: 'plan', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300' },
  { id: 'system', label: 'System', filter: 'system', color: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' },
];

export function AuditLogsPage() {
  useEffect(() => {
    document.title = 'Audit Logs - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);
  // Filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [actionTypeFilter, setActionTypeFilter] = useState<string>('all');
  const [presetFilter, setPresetFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [detailSheetOpen, setDetailSheetOpen] = useState(false);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  // Fetch audit logs with filters
  const { data: logsData, isLoading, refetch } = useQuery({
    queryKey: ['audit-logs', page, pageSize, actionTypeFilter, searchTerm],
    queryFn: () => apiClient.getAuditLogs({
      page,
      page_size: pageSize,
      action_type: actionTypeFilter !== 'all' ? actionTypeFilter : undefined,
      search: searchTerm || undefined,
    }),
  });

  const responseData = logsData?.data;
  const logs: AuditLog[] = (responseData && 'logs' in responseData ? responseData.logs : responseData) || [];
  const totalCount = (responseData && 'total' in responseData ? responseData.total : logs.length) || 0;
  const totalPages = Math.ceil(totalCount / pageSize);

  // Local export function (client-side CSV generation)
  const handleLocalExport = () => {
    if (logs.length === 0) {
      toast.error('No data to export');
      return;
    }

    const columns = [
      { key: 'id' as const, header: 'Log ID' },
      { key: 'timestamp' as const, header: 'Timestamp' },
      { key: 'actorEmail' as const, header: 'Actor Email' },
      { key: 'tenantId' as const, header: 'Tenant ID' },
      { key: 'actionType' as const, header: 'Action Type' },
      { key: 'resourceType' as const, header: 'Resource Type' },
      { key: 'resourceId' as const, header: 'Resource ID' },
      { key: 'ipAddress' as const, header: 'IP Address' },
      {
        key: ((log: AuditLog) => log.oldValue ? JSON.stringify(log.oldValue) : '') as unknown as keyof AuditLog,
        header: 'Old Value'
      },
      {
        key: ((log: AuditLog) => log.newValue ? JSON.stringify(log.newValue) : '') as unknown as keyof AuditLog,
        header: 'New Value'
      },
    ];

    let filename = 'audit-logs';
    if (presetFilter !== 'all') filename += `_${presetFilter}`;
    if (actionTypeFilter !== 'all') filename += `_${actionTypeFilter}`;
    if (searchTerm) filename += '_filtered';

    exportToCSV(logs as any, columns as any, filename);
    toast.success(`Exported ${logs.length} audit log entries to CSV`);
  };

  // Export mutation (server-side - fallback)
  const exportMutation = useMutation({
    mutationFn: () => apiClient.exportAuditLogs({
      action_type: actionTypeFilter !== 'all' ? actionTypeFilter : undefined,
      format: 'csv',
    }),
    onSuccess: (response) => {
      // Create download link
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit-logs-${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('Audit logs exported');
    },
    onError: () => {
      // Fall back to local export
      handleLocalExport();
    },
  });

  // Handle preset filter selection
  const handlePresetClick = (preset: typeof ACTION_PRESETS[0]) => {
    setPresetFilter(preset.id);
    if (preset.filter === 'all') {
      setActionTypeFilter('all');
    } else {
      // Set the action type filter to filter by prefix (e.g., "tenant" matches "tenant_suspended")
      setActionTypeFilter(preset.filter);
    }
    setPage(1);
  };

  const clearFilters = () => {
    setSearchTerm('');
    setActionTypeFilter('all');
    setPresetFilter('all');
    setPage(1);
  };

  const hasActiveFilters = searchTerm || actionTypeFilter !== 'all' || presetFilter !== 'all';

  const getActionIcon = (actionType: string | undefined) => {
    if (!actionType) return <FileText className="h-4 w-4" />;
    if (actionType.startsWith('tenant')) return <Building2 className="h-4 w-4" />;
    if (actionType.startsWith('user')) return <User className="h-4 w-4" />;
    if (actionType.startsWith('plan')) return <CreditCard className="h-4 w-4" />;
    if (actionType.startsWith('workflow')) return <Workflow className="h-4 w-4" />;
    if (actionType.startsWith('auth')) return <Shield className="h-4 w-4" />;
    if (actionType.startsWith('setting')) return <Settings className="h-4 w-4" />;
    if (actionType.startsWith('feature')) return <Activity className="h-4 w-4" />;
    if (actionType.startsWith('system')) return <AlertTriangle className="h-4 w-4" />;
    return <FileText className="h-4 w-4" />;
  };

  const getActionBadgeVariant = (actionType: string | undefined) => {
    if (!actionType) {
      return 'outline';
    }
    if (actionType.includes('suspended') || actionType.includes('deleted') || actionType.includes('error')) {
      return 'destructive';
    }
    if (actionType.includes('created') || actionType.includes('reactivated')) {
      return 'success';
    }
    if (actionType.includes('changed') || actionType.includes('updated')) {
      return 'secondary';
    }
    return 'outline';
  };

  const formatActionType = (actionType: string | undefined) => {
    if (!actionType) return 'Unknown';
    return actionType
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const formatTimestamp = (timestamp: string | undefined) => {
    if (!timestamp) {
      return {
        date: 'Unknown',
        time: '',
      };
    }
    try {
      const date = new Date(timestamp);
      if (isNaN(date.getTime())) {
        return {
          date: 'Invalid',
          time: '',
        };
      }
      return {
        date: date.toLocaleDateString(),
        time: date.toLocaleTimeString(),
      };
    } catch (error) {
      return {
        date: 'Invalid',
        time: '',
      };
    }
  };

  // Calculate stats from logs
  const actionTypes = logs
    .filter((log) => log && log.actionType)
    .reduce((acc, log) => {
      const type = log.actionType?.split('_')[0] || 'other';
      acc[type] = (acc[type] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);

  const actionTypeOptions = [
    { value: 'all', label: 'All Actions' },
    { value: 'tenant_suspended', label: 'Tenant Suspended' },
    { value: 'tenant_reactivated', label: 'Tenant Reactivated' },
    { value: 'tenant_plan_changed', label: 'Plan Changed' },
    { value: 'tenant_created', label: 'Tenant Created' },
    { value: 'tenant_deleted', label: 'Tenant Deleted' },
    { value: 'feature_override_created', label: 'Feature Override Created' },
    { value: 'feature_override_updated', label: 'Feature Override Updated' },
    { value: 'feature_override_deleted', label: 'Feature Override Deleted' },
    { value: 'user_role_changed', label: 'User Role Changed' },
    { value: 'system_error', label: 'System Error' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Audit Logs</h1>
          <p className="text-muted-foreground">Track all system activity and admin actions</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button
            variant="outline"
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending}
          >
            <Download className="h-4 w-4 mr-2" />
            {exportMutation.isPending ? 'Exporting...' : 'Export Logs'}
          </Button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <FileText className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">{totalCount}</p>
                <p className="text-sm text-muted-foreground">Total Events</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Building2 className="h-8 w-8 text-blue-500" />
              <div>
                <p className="text-2xl font-bold">{actionTypes['tenant'] || 0}</p>
                <p className="text-sm text-muted-foreground">Tenant Events</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Activity className="h-8 w-8 text-green-500" />
              <div>
                <p className="text-2xl font-bold">{actionTypes['feature'] || 0}</p>
                <p className="text-sm text-muted-foreground">Feature Events</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-8 w-8 text-red-500" />
              <div>
                <p className="text-2xl font-bold">{actionTypes['system'] || 0}</p>
                <p className="text-sm text-muted-foreground">System Events</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Filters
            </CardTitle>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="h-4 w-4 mr-1" />
                Clear
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Quick Filter Presets */}
          <div className="flex flex-wrap gap-2">
            <span className="text-sm text-muted-foreground mr-2 self-center">Quick filters:</span>
            {ACTION_PRESETS.map((preset) => (
              <Button
                key={preset.id}
                variant={presetFilter === preset.id ? 'default' : 'outline'}
                size="sm"
                onClick={() => handlePresetClick(preset)}
                className={presetFilter === preset.id ? '' : preset.color}
              >
                {preset.label}
              </Button>
            ))}
          </div>

          {/* Search and Advanced Filters */}
          <div className="flex flex-wrap gap-4">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by actor, tenant, or details..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setPage(1);
                }}
                className="pl-9"
              />
            </div>
            <Select value={actionTypeFilter} onValueChange={(v) => { setActionTypeFilter(v); setPresetFilter('all'); setPage(1); }}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Action Type" />
              </SelectTrigger>
              <SelectContent>
                {actionTypeOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Logs Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Activity Log
              </CardTitle>
              <CardDescription>
                Showing {logs.length} of {totalCount} events
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading audit logs...</div>
          ) : logs.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {hasActiveFilters ? 'No logs match your filters' : 'No audit logs found'}
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Tenant</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Details</TableHead>
                    <TableHead>IP Address</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logs
                    .filter((log) => log && log.id)
                    .map((log, index) => {
                      const { date, time } = formatTimestamp(log.timestamp);
                      return (
                        <TableRow 
                          key={log.id || `log-${index}`}
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => {
                            setSelectedLog(log);
                            setDetailSheetOpen(true);
                          }}
                        >
                        <TableCell>
                          <div className="flex items-center gap-1 text-sm">
                            <Clock className="h-3 w-3 text-muted-foreground" />
                            <div>
                              <p>{date}</p>
                              {time && <p className="text-xs text-muted-foreground">{time}</p>}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div>
                            <p className="font-medium">{log.actorEmail || 'System'}</p>
                            {log.actorId && (
                              <p className="text-xs text-muted-foreground font-mono">
                                {log.actorId.substring(0, 8)}...
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {log.tenantId ? (
                            <Link
                              to={`/admin/tenants/${log.tenantId}`}
                              className="text-sm hover:underline flex items-center gap-1"
                            >
                              {log.tenantId.substring(0, 8)}...
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          ) : (
                            <span className="text-sm text-muted-foreground">System</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={getActionBadgeVariant(log.actionType)}
                            className="flex items-center gap-1 w-fit"
                          >
                            {getActionIcon(log.actionType)}
                            {formatActionType(log.actionType)}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-xs">
                          <div className="flex items-center gap-2">
                            <div className="text-sm text-muted-foreground truncate">
                              {log.resourceType && log.resourceId ? (
                                <div className="flex items-center gap-1">
                                  {log.resourceType === 'environment' ? (
                                    <Link
                                      to={`/environments/${log.resourceId}`}
                                      className="text-primary hover:underline text-xs flex items-center gap-1"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <Server className="h-3 w-3" />
                                      {log.resourceName || log.resourceId.substring(0, 8)}...
                                    </Link>
                                  ) : log.resourceType === 'promotion' ? (
                                    <Link
                                      to={`/deployments/${log.resourceId}`}
                                      className="text-primary hover:underline text-xs flex items-center gap-1"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <Activity className="h-3 w-3" />
                                      Deployment {log.resourceId.substring(0, 8)}...
                                    </Link>
                                  ) : log.resourceType === 'workflow' ? (
                                    <Link
                                      to={`/workflows/${log.resourceId}`}
                                      className="text-primary hover:underline text-xs flex items-center gap-1"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <Workflow className="h-3 w-3" />
                                      {log.resourceName || log.resourceId.substring(0, 8)}...
                                    </Link>
                                  ) : log.resourceType === 'tenant' ? (
                                    <Link
                                      to={`/admin/tenants/${log.resourceId}`}
                                      className="text-primary hover:underline text-xs flex items-center gap-1"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <Building2 className="h-3 w-3" />
                                      {log.resourceName || log.resourceId.substring(0, 8)}...
                                    </Link>
                                  ) : (
                                    <span className="text-xs">
                                      {log.resourceType}: {log.resourceId.substring(0, 8)}...
                                    </span>
                                  )}
                                </div>
                              ) : log.newValue && typeof log.newValue === 'object' ? (
                                <code className="text-xs bg-muted px-2 py-1 rounded">
                                  {JSON.stringify(log.newValue).substring(0, 50)}...
                                </code>
                              ) : log.oldValue && log.newValue ? (
                                <span>
                                  {String(log.oldValue)} → {String(log.newValue)}
                                </span>
                              ) : (
                                <span>{log.newValue || log.oldValue || '-'}</span>
                              )}
                            </div>
                            <Eye className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {log.ipAddress || '-'}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {totalPages}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Audit Log Detail Sheet */}
      <Sheet open={detailSheetOpen} onOpenChange={setDetailSheetOpen}>
        <SheetContent side="right" className="sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Audit Log Details</SheetTitle>
            <SheetDescription>
              Complete information about this audit log entry
            </SheetDescription>
          </SheetHeader>
          {selectedLog && (
            <div className="mt-6 space-y-6">
              {/* Basic Information */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">Basic Information</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Timestamp:</span>
                    <p className="font-medium">
                      {formatTimestamp(selectedLog.timestamp).date} {formatTimestamp(selectedLog.timestamp).time}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Action Type:</span>
                    <p className="font-medium">{formatActionType(selectedLog.actionType)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Action:</span>
                    <p className="font-medium">{selectedLog.action}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Log ID:</span>
                    <p className="font-mono text-xs">{selectedLog.id}</p>
                  </div>
                </div>
              </div>

              {/* Actor Information */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold">Actor</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Name:</span>
                    <p className="font-medium">{selectedLog.actorName || 'N/A'}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Email:</span>
                    <p className="font-medium">{selectedLog.actorEmail || 'N/A'}</p>
                  </div>
                  {selectedLog.actorId && (
                    <div>
                      <span className="text-muted-foreground">Actor ID:</span>
                      <p className="font-mono text-xs">{selectedLog.actorId}</p>
                  </div>
                  )}
                </div>
              </div>

              {/* Resource Information */}
              {(selectedLog.resourceType || selectedLog.resourceId || selectedLog.resourceName) && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Resource</h3>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    {selectedLog.resourceType && (
                      <div>
                        <span className="text-muted-foreground">Type:</span>
                        <p className="font-medium">{selectedLog.resourceType}</p>
                      </div>
                    )}
                    {selectedLog.resourceName && (
                      <div>
                        <span className="text-muted-foreground">Name:</span>
                        <p className="font-medium">{selectedLog.resourceName}</p>
                      </div>
                    )}
                    {selectedLog.resourceId && (
                      <div className="col-span-2">
                        <span className="text-muted-foreground">Resource ID:</span>
                        <div className="mt-1">
                          {selectedLog.resourceType === 'environment' ? (
                            <Link
                              to={`/environments/${selectedLog.resourceId}`}
                              className="font-mono text-xs text-primary hover:underline flex items-center gap-1"
                            >
                              {selectedLog.resourceId}
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          ) : selectedLog.resourceType === 'promotion' ? (
                            <Link
                              to={`/deployments/${selectedLog.resourceId}`}
                              className="font-mono text-xs text-primary hover:underline flex items-center gap-1"
                            >
                              {selectedLog.resourceId}
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          ) : selectedLog.resourceType === 'workflow' ? (
                            <Link
                              to={`/workflows/${selectedLog.resourceId}`}
                              className="font-mono text-xs text-primary hover:underline flex items-center gap-1"
                            >
                              {selectedLog.resourceId}
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          ) : selectedLog.resourceType === 'tenant' ? (
                            <Link
                              to={`/admin/tenants/${selectedLog.resourceId}`}
                              className="font-mono text-xs text-primary hover:underline flex items-center gap-1"
                            >
                              {selectedLog.resourceId}
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          ) : (
                            <p className="font-mono text-xs">{selectedLog.resourceId}</p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tenant Information */}
              {selectedLog.tenantId && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Tenant</h3>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-muted-foreground">Tenant Name:</span>
                      <p className="font-medium">{selectedLog.tenantName || 'N/A'}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Tenant ID:</span>
                      <p className="font-mono text-xs">{selectedLog.tenantId}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Request Context */}
              {(selectedLog.ipAddress || selectedLog.metadata) && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Request Context</h3>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    {selectedLog.ipAddress && (
                      <div>
                        <span className="text-muted-foreground">IP Address:</span>
                        <p className="font-mono text-xs">{selectedLog.ipAddress}</p>
                      </div>
                    )}
                    {selectedLog.metadata && (
                      <div className="col-span-2">
                        <span className="text-muted-foreground">Metadata:</span>
                        <div className="mt-1 rounded-lg bg-muted p-3">
                          <pre className="whitespace-pre-wrap break-words text-xs font-mono">
                            {JSON.stringify(selectedLog.metadata, null, 2)}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Old Value */}
              {selectedLog.oldValue && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Before</h3>
                  <div className="rounded-lg bg-muted p-4">
                    <pre className="whitespace-pre-wrap break-words text-sm font-mono max-h-64 overflow-y-auto">
                      {typeof selectedLog.oldValue === 'object' 
                        ? JSON.stringify(selectedLog.oldValue, null, 2)
                        : String(selectedLog.oldValue)}
                    </pre>
                  </div>
                </div>
              )}

              {/* New Value */}
              {selectedLog.newValue && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">After</h3>
                  <div className="rounded-lg bg-muted p-4">
                    <pre className="whitespace-pre-wrap break-words text-sm font-mono max-h-64 overflow-y-auto">
                      {typeof selectedLog.newValue === 'object' 
                        ? JSON.stringify(selectedLog.newValue, null, 2)
                        : String(selectedLog.newValue)}
                    </pre>
                  </div>
                </div>
              )}

              {/* Reason */}
              {selectedLog.reason && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold">Reason</h3>
                  <p className="text-sm">{selectedLog.reason}</p>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
