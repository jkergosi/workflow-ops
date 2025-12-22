import { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { apiClient } from '@/lib/api-client';
import { api } from '@/lib/api';
import { useAppStore } from '@/store/use-app-store';
import type {
  TimeRange,
  EnvironmentStatus,
  EnvironmentType,
  SystemHealthStatus,
  SparklineDataPoint,
} from '@/types';
import {
  Activity,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  Clock,
  RefreshCw,
  CheckCircle,
  XCircle,
  Minus,
  Server,
  Loader2,
  ArrowRight,
  Camera,
  Rocket,
  GitCompare,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Key,
  Zap,
} from 'lucide-react';

const TIME_RANGE_OPTIONS: { value: TimeRange; label: string }[] = [
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
];

// Sparkline component
function Sparkline({ data, color = 'currentColor', height = 24, width = 80 }: {
  data?: SparklineDataPoint[];
  color?: string;
  height?: number;
  width?: number;
}) {
  if (!data || data.length === 0) return null;

  const values = data.map(d => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height} className="inline-block ml-2">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function getStatusBadgeVariant(status: EnvironmentStatus): 'success' | 'warning' | 'destructive' {
  switch (status) {
    case 'healthy':
      return 'success';
    case 'degraded':
      return 'warning';
    case 'unreachable':
      return 'destructive';
    default:
      return 'warning';
  }
}

function getSystemStatusIcon(status: SystemHealthStatus) {
  switch (status) {
    case 'healthy':
      return <ShieldCheck className="h-5 w-5 text-green-500" />;
    case 'degraded':
      return <ShieldAlert className="h-5 w-5 text-yellow-500" />;
    case 'critical':
      return <ShieldX className="h-5 w-5 text-red-500" />;
    default:
      return <ShieldCheck className="h-5 w-5 text-gray-500" />;
  }
}

function getStatusIcon(status: EnvironmentStatus) {
  switch (status) {
    case 'healthy':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'degraded':
      return <AlertCircle className="h-4 w-4 text-yellow-500" />;
    case 'unreachable':
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <Minus className="h-4 w-4 text-gray-500" />;
  }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function formatDelta(value: number | undefined, suffix: string = ''): React.ReactNode {
  if (value === undefined || value === null) return null;
  const isPositive = value > 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  const color = isPositive ? 'text-green-600' : 'text-red-600';
  return (
    <span className={`flex items-center gap-1 text-xs ${color}`}>
      <Icon className="h-3 w-3" />
      {isPositive ? '+' : ''}{value.toFixed(1)}{suffix}
    </span>
  );
}

function formatRelativeTime(dateString: string | undefined): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffHours < 1) return 'just now';
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function ObservabilityPage() {
  useEffect(() => {
    document.title = 'Observability - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  const [timeRange, setTimeRange] = useState<TimeRange>('24h');
  const [sortBy, setSortBy] = useState<'risk' | 'executions' | 'failures'>('risk');

  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);

  // Fetch environments
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: async () => {
      const result = await api.getEnvironments();
      return result;
    },
  });

  // Get current environment ID
  const currentEnvironmentId = useMemo(() => {
    const envData = environments?.data;
    if (!envData) return undefined;
    const env = envData.find((e: { id: string; type?: string }) => e.type === selectedEnvironment);
    return env?.id;
  }, [environments, selectedEnvironment]);

  const { data: overview, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['observability-overview', timeRange, currentEnvironmentId],
    queryFn: () => apiClient.getObservabilityOverview(timeRange, currentEnvironmentId),
  });

  const systemStatus = overview?.data.systemStatus;
  const kpi = overview?.data.kpiMetrics;
  const errorIntelligence = overview?.data.errorIntelligence;
  const workflows = overview?.data.workflowPerformance || [];
  const envHealth = overview?.data.environmentHealth || [];
  const syncStats = overview?.data.promotionSyncStats;

  // Filter environment health by selected environment
  const filteredEnvHealth = useMemo(() => {
    if (!selectedEnvironment) {
      return envHealth || [];
    }
    return (envHealth || []).filter((env) => env.environmentType === selectedEnvironment);
  }, [envHealth, selectedEnvironment]);

  // Sort workflows based on sortBy
  const sortedWorkflows = useMemo(() => {
    const sorted = [...workflows];
    if (sortBy === 'risk') {
      sorted.sort((a, b) => (b.riskScore || 0) - (a.riskScore || 0));
    } else if (sortBy === 'failures') {
      sorted.sort((a, b) => b.failureCount - a.failureCount);
    } else {
      sorted.sort((a, b) => b.executionCount - a.executionCount);
    }
    return sorted;
  }, [workflows, sortBy]);

  const handleRefresh = () => {
    refetch();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <p className="text-muted-foreground">Failed to load observability data</p>
        <Button onClick={handleRefresh}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Section 0: Global Controls (Sticky Header) */}
      <div className="sticky top-0 z-10 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 pb-4 -mt-4 pt-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Observability</h1>
            <p className="text-muted-foreground text-sm mt-1">
              Active filters: {selectedEnvironment || 'all'} · {TIME_RANGE_OPTIONS.find(o => o.value === timeRange)?.label}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="space-y-2">
              <Label htmlFor="environment" className="sr-only">Environment</Label>
              <select
                id="environment"
                value={selectedEnvironment || ''}
                onChange={(e) => setSelectedEnvironment(e.target.value as EnvironmentType)}
                className="flex h-9 w-[180px] rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                disabled={!environments?.data || (environments.data as Array<{id: string; name: string; type?: string}>).length === 0}
              >
                {!environments?.data || (environments.data as Array<{id: string; name: string; type?: string}>).length === 0 ? (
                  <option value="" className="bg-background text-foreground">No environments</option>
                ) : (
                  (environments.data as Array<{id: string; name: string; type?: string}>).map((env) => (
                    <option key={env.id} value={env.type || ''} className="bg-background text-foreground">
                      {env.name}
                    </option>
                  ))
                )}
              </select>
            </div>
            <Select value={timeRange} onValueChange={(value) => setTimeRange(value as TimeRange)}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Select time range" />
              </SelectTrigger>
              <SelectContent>
                {TIME_RANGE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={handleRefresh} disabled={isFetching}>
              <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      {/* Section 1: System Status (Immediate Health Verdict) */}
      {systemStatus && (
        <Card className={`border-l-4 ${
          systemStatus.status === 'healthy' ? 'border-l-green-500 bg-green-50/50 dark:bg-green-950/20' :
          systemStatus.status === 'degraded' ? 'border-l-yellow-500 bg-yellow-50/50 dark:bg-yellow-950/20' :
          'border-l-red-500 bg-red-50/50 dark:bg-red-950/20'
        }`}>
          <CardContent className="pt-4">
            <div className="flex items-start gap-3">
              {getSystemStatusIcon(systemStatus.status)}
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-lg capitalize">
                    STATUS: {systemStatus.status === 'healthy' ? '✓ Healthy' :
                            systemStatus.status === 'degraded' ? '⚠ Degraded' :
                            '✗ Critical'}
                  </span>
                </div>
                <ul className="mt-2 space-y-1 text-sm">
                  {systemStatus.insights.map((insight, idx) => (
                    <li key={idx} className={`flex items-center gap-2 ${
                      insight.severity === 'critical' ? 'text-red-600 dark:text-red-400' :
                      insight.severity === 'warning' ? 'text-yellow-600 dark:text-yellow-400' :
                      'text-muted-foreground'
                    }`}>
                      <span>•</span>
                      <span>{insight.message}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Section 2: KPI Cards with Sparklines */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Executions</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center">
              <span className="text-2xl font-bold">{kpi?.totalExecutions.toLocaleString() || 0}</span>
              <Sparkline data={kpi?.executionsSparkline} color="hsl(var(--primary))" />
            </div>
            {formatDelta(kpi?.deltaExecutions)}
            <p className="text-xs text-muted-foreground mt-1">vs previous period</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center">
              <span className={`text-2xl font-bold ${
                (kpi?.successRate || 0) >= 95 ? 'text-green-600' :
                (kpi?.successRate || 0) >= 80 ? 'text-yellow-600' : 'text-red-600'
              }`}>
                {(kpi?.successRate || 0).toFixed(1)}%
              </span>
              <Sparkline
                data={kpi?.successRateSparkline}
                color={(kpi?.successRate || 0) >= 95 ? 'rgb(22, 163, 74)' :
                       (kpi?.successRate || 0) >= 80 ? 'rgb(202, 138, 4)' : 'rgb(220, 38, 38)'}
              />
            </div>
            {formatDelta(kpi?.deltaSuccessRate, '%')}
            <p className="text-xs text-muted-foreground mt-1">vs previous period</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Duration</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center">
              <span className="text-2xl font-bold">p50 {formatDuration(kpi?.avgDurationMs || 0)}</span>
              <Sparkline data={kpi?.durationSparkline} color="hsl(var(--muted-foreground))" />
            </div>
            {kpi?.p95DurationMs && (
              <p className="text-xs text-muted-foreground mt-1">
                p95: {formatDuration(kpi.p95DurationMs)}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failures</CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center">
              <span className="text-2xl font-bold text-red-600">
                {kpi?.failureCount.toLocaleString() || 0}
              </span>
              <Sparkline data={kpi?.failuresSparkline} color="rgb(220, 38, 38)" />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {((kpi?.failureCount || 0) / Math.max(kpi?.totalExecutions || 1, 1) * 100).toFixed(1)}% of total
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Section 3: Error Intelligence */}
      {errorIntelligence && errorIntelligence.errors.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              Error Intelligence
            </CardTitle>
            <CardDescription>
              Errors grouped by root cause ({errorIntelligence.totalErrorCount} total)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Error Type</TableHead>
                  <TableHead className="text-right">Count</TableHead>
                  <TableHead>First Seen</TableHead>
                  <TableHead>Last Seen</TableHead>
                  <TableHead className="text-right">Workflows</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {errorIntelligence.errors.slice(0, 10).map((error) => (
                  <TableRow key={error.errorType} className="cursor-pointer hover:bg-muted/50">
                    <TableCell>
                      <div className="space-y-1">
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="font-medium">{error.errorType}</span>
                            </TooltipTrigger>
                            {error.sampleMessage && (
                              <TooltipContent className="max-w-md">
                                <p className="text-xs font-mono">{error.sampleMessage}</p>
                              </TooltipContent>
                            )}
                          </Tooltip>
                        </TooltipProvider>
                        {/* Show sample message inline for unclassified errors */}
                        {error.isClassified === false && error.sampleMessage && (
                          <p className="text-xs text-muted-foreground font-mono truncate max-w-[300px]">
                            {error.sampleMessage}
                          </p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-medium text-red-600">
                      {error.count}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {new Date(error.firstSeen).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {formatRelativeTime(error.lastSeen)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge variant="outline">{error.affectedWorkflowCount}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Section 4: Workflow Risk Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Workflow Risk Table</CardTitle>
                <CardDescription>Sorted by risk (failure rate × volume)</CardDescription>
              </div>
              <Select value={sortBy} onValueChange={(value) => setSortBy(value as 'risk' | 'executions' | 'failures')}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="risk">By Risk</SelectItem>
                  <SelectItem value="executions">By Runs</SelectItem>
                  <SelectItem value="failures">By Failures</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            {sortedWorkflows.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No workflow data for this time period
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Workflow</TableHead>
                    <TableHead className="text-right">Runs</TableHead>
                    <TableHead className="text-right">Fail %</TableHead>
                    <TableHead>Last Failure</TableHead>
                    <TableHead>Error Type</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedWorkflows.slice(0, 10).map((wf) => (
                    <TableRow key={wf.workflowId} className="cursor-pointer hover:bg-muted/50">
                      <TableCell>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Link
                                to={`/workflows/${wf.workflowId}`}
                                className="font-medium truncate max-w-[150px] block text-primary hover:underline"
                              >
                                {wf.workflowName}
                              </Link>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p className="text-xs">ID: {wf.workflowId}</p>
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </TableCell>
                      <TableCell className="text-right">{wf.executionCount}</TableCell>
                      <TableCell className="text-right">
                        <Badge variant={wf.errorRate < 5 ? 'success' : wf.errorRate < 20 ? 'warning' : 'destructive'}>
                          {wf.errorRate.toFixed(1)}%
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {wf.lastFailureAt ? formatRelativeTime(wf.lastFailureAt) : '—'}
                      </TableCell>
                      <TableCell>
                        {wf.primaryErrorType ? (
                          <Badge variant="outline" className="text-xs">
                            {wf.primaryErrorType}
                          </Badge>
                        ) : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Section 5: Environment Health */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Environment Health
            </CardTitle>
            <CardDescription>Multi-dimensional health status</CardDescription>
          </CardHeader>
          <CardContent>
            {filteredEnvHealth.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {selectedEnvironment
                  ? 'No data for selected environment'
                  : 'No environments configured'}
              </div>
            ) : (
              <div className="space-y-4">
                {filteredEnvHealth.map((health) => (
                  <div key={health.environmentId} className="p-4 border rounded-lg space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(health.status)}
                        <span className="font-medium">{health.environmentName}</span>
                        {health.environmentType && (
                          <Badge variant="outline" className="text-xs">
                            {health.environmentType}
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {/* Show dual status when runtime is healthy but pipeline has issues */}
                        {health.status === 'healthy' && health.lastDeploymentStatus === 'failed' ? (
                          <>
                            <Badge variant="success" className="text-xs">
                              runtime ok
                            </Badge>
                            <Badge variant="warning" className="text-xs">
                              pipeline degraded
                            </Badge>
                          </>
                        ) : (
                          <Badge variant={getStatusBadgeVariant(health.status)}>
                            {health.status}
                          </Badge>
                        )}
                      </div>
                    </div>

                    {/* Health Details */}
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="flex items-center gap-2">
                        {health.apiReachable ? (
                          <CheckCircle className="h-3 w-3 text-green-500" />
                        ) : (
                          <XCircle className="h-3 w-3 text-red-500" />
                        )}
                        <span>API Reachability</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">Uptime:</span>
                        <span className="font-medium">{health.uptimePercent.toFixed(1)}%</span>
                      </div>

                      {/* Credential Health */}
                      {health.credentialHealth && (
                        <div className="flex items-center gap-2">
                          <Key className="h-3 w-3" />
                          <span>Credentials:</span>
                          {health.credentialHealth.invalidCount > 0 ? (
                            <span className="text-red-600 font-medium">
                              ❌ {health.credentialHealth.invalidCount} invalid
                            </span>
                          ) : (
                            <span className="text-green-600">✓ All valid</span>
                          )}
                        </div>
                      )}

                      {/* Drift Status */}
                      <div className="flex items-center gap-2">
                        <GitCompare className="h-3 w-3" />
                        <span>Drift:</span>
                        {health.driftState === 'drift' ? (
                          <span className="text-yellow-600 font-medium">
                            ⚠ {health.driftWorkflowCount || 0} workflows
                          </span>
                        ) : health.driftState === 'in_sync' ? (
                          <span className="text-green-600">✓ In sync</span>
                        ) : (
                          <span className="text-muted-foreground">Unknown</span>
                        )}
                      </div>
                    </div>

                    {/* Metadata */}
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <div>
                        <Zap className="h-3 w-3 inline mr-1" />
                        {health.activeWorkflows}/{health.totalWorkflows} active
                      </div>
                      {health.lastSnapshotAt && (
                        <div className="flex items-center gap-1">
                          <Camera className="h-3 w-3" />
                          Snapshot: {formatRelativeTime(health.lastSnapshotAt)}
                        </div>
                      )}
                      {health.lastDeploymentAt && (
                        <div className="flex items-center gap-1">
                          <Rocket className="h-3 w-3" />
                          Deploy: {formatRelativeTime(health.lastDeploymentAt)}
                          {health.lastDeploymentStatus === 'failed' && (
                            <Badge variant="destructive" className="text-xs ml-1">failed</Badge>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Section 6: Promotion & Sync Stats */}
      {syncStats && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Rocket className="h-5 w-5" />
              Promotions & Deployments (Last 7 Days)
            </CardTitle>
            <CardDescription>Deployment activity and change-failure correlation</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 md:grid-cols-2">
              {/* Section 6a: Promotions Summary */}
              <div className="space-y-4">
                <h4 className="font-medium">Promotions Summary</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 border rounded-lg">
                    <div className="text-2xl font-bold">{syncStats.promotionsTotal}</div>
                    <div className="text-sm text-muted-foreground">Total</div>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <div className="text-2xl font-bold text-green-600">{syncStats.promotionsSuccess}</div>
                    <div className="text-sm text-muted-foreground">Successful</div>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <div className="text-2xl font-bold text-red-600">
                      {syncStats.promotionsFailed}
                      {syncStats.promotionsFailed > 0 && ' ⚠'}
                    </div>
                    <div className="text-sm text-muted-foreground">Failed</div>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <div className="text-2xl font-bold">{syncStats.snapshotsCreated}</div>
                    <div className="text-sm text-muted-foreground">Snapshots</div>
                  </div>
                </div>
                {syncStats.driftCount > 0 && (
                  <div className="p-4 border border-yellow-200 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="h-5 w-5 text-yellow-600" />
                      <span className="font-medium text-yellow-800 dark:text-yellow-200">
                        {syncStats.driftCount} workflow(s) with drift detected
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Section 6b: Recent Deployments (With Impact) */}
              <div>
                <h4 className="font-medium mb-3">Recent Deployments</h4>
                {syncStats.recentDeployments.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No recent deployments</div>
                ) : (
                  <div className="space-y-3">
                    {syncStats.recentDeployments.map((d) => (
                      <div key={d.id} className="border rounded-lg p-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2 text-sm">
                            {d.status === 'success' ? (
                              <CheckCircle className="h-4 w-4 text-green-500" />
                            ) : d.status === 'failed' ? (
                              <XCircle className="h-4 w-4 text-red-500" />
                            ) : (
                              <Minus className="h-4 w-4 text-gray-500" />
                            )}
                            <span className="truncate max-w-[100px]">{d.sourceEnvironmentName}</span>
                            <ArrowRight className="h-3 w-3" />
                            <span className="truncate max-w-[100px]">{d.targetEnvironmentName}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">
                              {formatRelativeTime(d.startedAt)}
                            </span>
                            <Badge
                              variant={
                                d.status === 'success'
                                  ? 'success'
                                  : d.status === 'failed'
                                  ? 'destructive'
                                  : 'outline'
                              }
                            >
                              {d.status}
                            </Badge>
                          </div>
                        </div>

                        {/* Impacted Workflows for failed deployments */}
                        {d.status === 'failed' && d.impactedWorkflows && d.impactedWorkflows.length > 0 && (
                          <div className="mt-2 pl-6 text-xs text-muted-foreground">
                            <span className="text-red-600">↳ Impacted:</span>{' '}
                            {d.impactedWorkflows.slice(0, 3).map((iw, idx) => (
                              <span key={iw.workflowId}>
                                {idx > 0 && ', '}
                                {iw.workflowName}
                              </span>
                            ))}
                            {d.impactedWorkflows.length > 3 && (
                              <span> +{d.impactedWorkflows.length - 3} more</span>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
