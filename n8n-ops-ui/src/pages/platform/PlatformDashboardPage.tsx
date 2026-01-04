import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Server,
  Database,
  Activity,
  Clock,
  Users,
  AlertTriangle,
  GitCompare,
  Key,
  Shield,
  UserCheck,
  Building2,
  Settings,
  HelpCircle,
  History,
  TrendingUp,
  AlertCircle,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { cn } from '@/lib/utils';

function MockBadge({ title = 'Placeholder metric (not yet wired to live data)' }: { title?: string }) {
  return (
    <Badge
      variant="outline"
      title={title}
      className="ml-2 text-[10px] font-medium text-red-800 dark:text-red-500 border-red-800/30 dark:border-red-500/40 bg-red-500/10 px-1 py-0 h-4 leading-4"
    >
      Mock
    </Badge>
  );
}

// Health status tile component
function HealthTile({
  title,
  value,
  subValue,
  status,
  icon: Icon,
  href,
  isMocked,
}: {
  title: string;
  value: string | number;
  subValue?: string;
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
  icon: React.ComponentType<{ className?: string }>;
  href?: string;
  isMocked?: boolean;
}) {
  const statusColors = {
    healthy: 'bg-green-500/10 text-green-700 dark:text-green-400',
    warning: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400',
    critical: 'bg-red-500/10 text-red-700 dark:text-red-400',
    unknown: 'bg-gray-500/10 text-gray-700 dark:text-gray-400',
  };

  const statusDot = {
    healthy: 'bg-green-500',
    warning: 'bg-yellow-500',
    critical: 'bg-red-500',
    unknown: 'bg-gray-500',
  };

  const content = (
    <Card className={cn(href && 'hover:shadow-md transition-shadow cursor-pointer')}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={cn('p-2 rounded-lg', statusColors[status])}>
              <Icon className="h-4 w-4" />
            </div>
            <CardTitle className="text-base flex items-center gap-2">
              {title}
              {isMocked ? <MockBadge /> : null}
            </CardTitle>
          </div>
          <div className={cn('h-2 w-2 rounded-full', statusDot[status])} />
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div>
          <p className="text-2xl font-bold">{value}</p>
          {subValue && <p className="text-xs text-muted-foreground mt-1">{subValue}</p>}
        </div>
      </CardContent>
    </Card>
  );

  if (href) {
    return <Link to={href}>{content}</Link>;
  }
  return content;
}

// Metric card component
function MetricCard({
  title,
  value,
  subValue,
  icon: Icon,
  href,
  trend,
}: {
  title: string;
  value: string | number;
  subValue?: string;
  icon: React.ComponentType<{ className?: string }>;
  href?: string;
  trend?: 'up' | 'down' | 'neutral';
}) {
  const content = (
    <Card className={cn(href && 'hover:shadow-md transition-shadow cursor-pointer')}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10">
              <Icon className="h-4 w-4 text-primary" />
            </div>
            <CardTitle className="text-base">{title}</CardTitle>
          </div>
          {trend && (
            <TrendingUp
              className={cn(
                'h-4 w-4',
                trend === 'up' && 'text-green-500',
                trend === 'down' && 'text-red-500 rotate-180',
                trend === 'neutral' && 'text-gray-500'
              )}
            />
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div>
          <p className="text-2xl font-bold">{value}</p>
          {subValue && <p className="text-xs text-muted-foreground mt-1">{subValue}</p>}
        </div>
      </CardContent>
    </Card>
  );

  if (href) {
    return <Link to={href}>{content}</Link>;
  }
  return content;
}

// Plan distribution bar
function PlanDistributionBar({
  distribution,
}: {
  distribution: { free: number; pro: number; agency: number; enterprise: number };
}) {
  const total = distribution.free + distribution.pro + distribution.agency + distribution.enterprise;
  if (total === 0) return null;

  const segments = [
    { key: 'free', label: 'Free', count: distribution.free, color: 'bg-gray-400' },
    { key: 'pro', label: 'Pro', count: distribution.pro, color: 'bg-blue-500' },
    { key: 'agency', label: 'Agency', count: distribution.agency, color: 'bg-purple-500' },
    { key: 'enterprise', label: 'Enterprise', count: distribution.enterprise, color: 'bg-green-500' },
  ];

  return (
    <div className="space-y-2">
      <div className="flex h-3 rounded-full overflow-hidden bg-muted">
        {segments.map((seg) => {
          const pct = (seg.count / total) * 100;
          if (pct === 0) return null;
          return (
            <div
              key={seg.key}
              className={cn(seg.color)}
              style={{ width: `${pct}%` }}
              title={`${seg.label}: ${seg.count} (${pct.toFixed(1)}%)`}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap gap-3 text-xs">
        {segments.map((seg) => (
          <div key={seg.key} className="flex items-center gap-1">
            <div className={cn('h-2 w-2 rounded-full', seg.color)} />
            <span className="text-muted-foreground">
              {seg.label}: {seg.count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Format relative time
function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return 'Never';
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export function PlatformDashboardPage() {
  useEffect(() => {
    document.title = 'Platform Dashboard - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const { data: overview, isLoading, error } = useQuery({
    queryKey: ['platform-overview'],
    queryFn: () => apiClient.getPlatformOverview(),
    refetchInterval: 60000, // Refresh every minute
  });

  const data = overview?.data;

  // Determine health statuses
  const getApiStatus = (): 'healthy' | 'warning' | 'critical' | 'unknown' => {
    if (!data?.platform_health?.api) return 'unknown';
    const { error_rate_24h } = data.platform_health.api;
    if (error_rate_24h >= 0.05) return 'critical';
    if (error_rate_24h >= 0.01) return 'warning';
    return 'healthy';
  };

  const getDbStatus = (): 'healthy' | 'warning' | 'critical' | 'unknown' => {
    if (!data?.platform_health?.db) return 'unknown';
    const { connections_used_pct, slow_queries_1h } = data.platform_health.db;
    if (connections_used_pct >= 90 || slow_queries_1h >= 100) return 'critical';
    if (connections_used_pct >= 70 || slow_queries_1h >= 20) return 'warning';
    return 'healthy';
  };

  const getJobsStatus = (): 'healthy' | 'warning' | 'critical' | 'unknown' => {
    if (!data?.platform_health?.jobs?.length) return 'unknown';
    const hasFailures = data.platform_health.jobs.some((j) => j.status === 'fail' || j.failures_24h > 0);
    return hasFailures ? 'warning' : 'healthy';
  };

  const getQueueStatus = (): 'healthy' | 'warning' | 'critical' | 'unknown' => {
    if (!data?.platform_health?.queue) return 'unknown';
    const { depth, dead_letters_24h } = data.platform_health.queue;
    if (dead_letters_24h > 10 || depth > 1000) return 'critical';
    if (dead_letters_24h > 0 || depth > 100) return 'warning';
    return 'healthy';
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Platform Dashboard</h1>
          <p className="text-muted-foreground">Loading platform overview...</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-4 h-32" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Platform Dashboard</h1>
          <p className="text-destructive">Failed to load platform overview. Please try again.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Platform Dashboard</h1>
          <p className="text-muted-foreground">Platform-wide health, tenants, and operations at a glance</p>
        </div>
      </div>

      {/* Platform Health Tiles */}
      <div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <HealthTile
            title="API Health"
            value={getApiStatus() === 'healthy' ? 'Healthy' : getApiStatus() === 'warning' ? 'Degraded' : 'Issues'}
            subValue={`${((data?.platform_health?.api?.error_rate_24h || 0) * 100).toFixed(2)}% error rate (24h)`}
            status={getApiStatus()}
            icon={Activity}
            isMocked
          />
          <HealthTile
            title="Database"
            value={getDbStatus() === 'healthy' ? 'Healthy' : getDbStatus() === 'warning' ? 'Degraded' : 'Issues'}
            subValue={`${data?.platform_health?.db?.slow_queries_1h || 0} slow queries (1h)`}
            status={getDbStatus()}
            icon={Database}
            isMocked
          />
          <HealthTile
            title="Background Jobs"
            value={data?.platform_health?.jobs?.length || 0}
            subValue={getJobsStatus() === 'healthy' ? 'All running' : 'Some failures'}
            status={getJobsStatus()}
            icon={Clock}
          />
          <HealthTile
            title="Queue"
            value={data?.platform_health?.queue?.depth || 0}
            subValue={`${data?.platform_health?.queue?.dead_letters_24h || 0} dead letters (24h)`}
            status={getQueueStatus()}
            icon={Server}
            isMocked
          />
        </div>
      </div>

      {/* Tenant Health Overview */}
      <div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Active Tenants"
            value={data?.tenants?.active_7d || 0}
            subValue={`${data?.tenants?.active_30d || 0} in 30d / ${data?.tenants?.total || 0} total`}
            icon={Users}
            href="/platform/tenants"
          />
          <MetricCard
            title="At-Risk Tenants"
            value={data?.tenants?.at_risk || 0}
            subValue="Requires attention"
            icon={AlertTriangle}
            href="/platform/tenants?filter=at_risk"
          />
          <MetricCard
            title="Tenants with Drift"
            value={data?.tenants?.with_drift_7d || 0}
            subValue="Last 7 days"
            icon={GitCompare}
          />
          <MetricCard
            title="Credential Failures"
            value={data?.tenants?.with_credential_failures_7d || 0}
            subValue="Tenants affected (7d)"
            icon={Key}
          />
        </div>
      </div>

      {/* Usage & Revenue Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Usage & Capacity */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Usage & Capacity</CardTitle>
            <CardDescription>Platform-wide execution metrics</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-2xl font-bold">{(data?.usage?.executions_24h || 0).toLocaleString()}</p>
                <p className="text-sm text-muted-foreground">Executions (24h)</p>
              </div>
              <div>
                <p className="text-2xl font-bold">{(data?.usage?.executions_7d || 0).toLocaleString()}</p>
                <p className="text-sm text-muted-foreground">Executions (7d)</p>
              </div>
            </div>

            {/* Top tenants by executions */}
            {data?.top_lists?.tenants_by_executions_24h?.length ? (
              <div className="mt-4">
                <p className="text-sm font-medium mb-2">Top Tenants by Executions (24h)</p>
                <div className="space-y-2">
                  {data.top_lists.tenants_by_executions_24h.slice(0, 5).map((t) => (
                    <Link
                      key={t.tenant_id}
                      to={`/platform/tenants/${t.tenant_id}`}
                      className="flex items-center justify-between p-2 rounded hover:bg-muted/50"
                    >
                      <span className="text-sm truncate">{t.tenant_name}</span>
                      <Badge variant="secondary">{t.executions.toLocaleString()}</Badge>
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>

        {/* Revenue & Plan Distribution */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Revenue & Plans</CardTitle>
            <CardDescription>Subscription distribution and billing status</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-2xl font-bold">
                  ${((data?.revenue?.mrr_cents || 0) / 100).toLocaleString()}
                </p>
                <p className="text-sm text-muted-foreground flex items-center">
                  <span>MRR</span>
                  <MockBadge title="MRR is currently a placeholder (defaults to 0 until billing integration is wired)" />
                </p>
              </div>
              <div>
                <p className="text-2xl font-bold text-destructive">{data?.revenue?.delinquent_orgs || 0}</p>
                <p className="text-sm text-muted-foreground">Delinquent Orgs</p>
              </div>
            </div>

            <div>
              <p className="text-sm font-medium mb-2">Plan Distribution</p>
              <div className="flex items-center gap-2 mb-2">
                <PlanDistributionBar distribution={data?.revenue?.plan_distribution || { free: 0, pro: 0, agency: 0, enterprise: 0 }} />
                <MockBadge title="Plan distribution uses deprecated subscription_tier field. Should be calculated from provider subscriptions." />
              </div>
            </div>

            {(data?.revenue?.entitlement_exceptions || 0) > 0 && (
              <Link
                to="/platform/tenant-overrides"
                className="flex items-center justify-between p-2 rounded hover:bg-muted/50 mt-2"
              >
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-yellow-500" />
                  <span className="text-sm">Entitlement Exceptions</span>
                </div>
                <Badge variant="secondary">{data.revenue.entitlement_exceptions}</Badge>
              </Link>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Top Outliers Tables */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Top Tenants by Failure Rate */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Top Tenants by Failure Rate (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            {data?.top_lists?.tenants_by_fail_rate_24h?.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tenant</TableHead>
                    <TableHead className="text-right">Failures</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead className="text-right">Rate</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.top_lists.tenants_by_fail_rate_24h.slice(0, 5).map((t) => (
                    <TableRow key={t.tenant_id}>
                      <TableCell>
                        <Link to={`/platform/tenants/${t.tenant_id}`} className="hover:underline">
                          {t.tenant_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right">{t.failures}</TableCell>
                      <TableCell className="text-right">{t.total_executions}</TableCell>
                      <TableCell className="text-right">
                        <Badge variant={t.failure_rate >= 0.1 ? 'destructive' : 'secondary'}>
                          {(t.failure_rate * 100).toFixed(1)}%
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">No failure data available</p>
            )}
          </CardContent>
        </Card>

        {/* Top Tenants with Drift */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Top Tenants with Drift (7d)</CardTitle>
          </CardHeader>
          <CardContent>
            {data?.top_lists?.tenants_with_drift_7d?.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tenant</TableHead>
                    <TableHead className="text-right">Drift Count</TableHead>
                    <TableHead className="text-right">Last Detected</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.top_lists.tenants_with_drift_7d.slice(0, 5).map((t) => (
                    <TableRow key={t.tenant_id}>
                      <TableCell>
                        <Link to={`/platform/tenants/${t.tenant_id}`} className="hover:underline">
                          {t.tenant_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge variant="secondary">{t.drift_count}</Badge>
                      </TableCell>
                      <TableCell className="text-right text-muted-foreground">
                        {formatRelativeTime(t.last_detected)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">No drift data available</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Security & Admin Activity */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Security Metrics */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Security & Admin Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="text-center p-3 rounded-lg bg-muted/50">
                <p className="text-2xl font-bold">{data?.security?.impersonations_active || 0}</p>
                <p className="text-xs text-muted-foreground">Active Impersonations</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-muted/50">
                <p className="text-2xl font-bold">{data?.security?.impersonations_24h || 0}</p>
                <p className="text-xs text-muted-foreground">Impersonations (24h)</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-muted/50">
                <p className="text-2xl font-bold">{data?.security?.admin_actions_24h || 0}</p>
                <p className="text-xs text-muted-foreground">Admin Actions (24h)</p>
              </div>
            </div>

            {/* Recent admin activity */}
            {data?.top_lists?.recent_admin_activity?.length ? (
              <div>
                <p className="text-sm font-medium mb-2">Recent Admin Activity</p>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {data.top_lists.recent_admin_activity.slice(0, 10).map((a, i) => (
                    <div key={i} className="flex items-center justify-between p-2 rounded hover:bg-muted/50 text-sm">
                      <div className="flex items-center gap-2 min-w-0">
                        <UserCheck className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                        <span className="truncate">{a.actor_name}</span>
                        <span className="text-muted-foreground truncate">{a.action}</span>
                      </div>
                      <span className="text-xs text-muted-foreground flex-shrink-0">{formatRelativeTime(a.timestamp)}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">No recent admin activity</p>
            )}
          </CardContent>
        </Card>

        {/* Open Incidents */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Open Incidents</CardTitle>
          </CardHeader>
          <CardContent>
            {data?.top_lists?.open_incidents?.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Severity</TableHead>
                    <TableHead>Tenant</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Age</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.top_lists.open_incidents.slice(0, 5).map((inc) => (
                    <TableRow key={inc.id}>
                      <TableCell>
                        <Badge
                          variant={inc.severity === 'critical' ? 'destructive' : inc.severity === 'high' ? 'destructive' : 'secondary'}
                        >
                          {inc.severity}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Link to={`/platform/tenants/${inc.tenant_id}`} className="hover:underline">
                          {inc.tenant_name}
                        </Link>
                      </TableCell>
                      <TableCell className="capitalize">{inc.status}</TableCell>
                      <TableCell className="text-right text-muted-foreground">{inc.age_hours}h</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="text-center py-8">
                <Shield className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No open incidents</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

    </div>
  );
}
