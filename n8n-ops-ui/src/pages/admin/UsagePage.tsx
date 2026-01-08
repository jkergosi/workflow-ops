// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useMemo, useEffect, memo } from 'react';
import { useQuery } from '@tanstack/react-query';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import {
  Activity,
  Workflow,
  Users,
  Server as _Server,
  Building2,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  ExternalLink,
  RefreshCw,
  BarChart3,
  ArrowUpRight,
  Zap,
  Download,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { Link } from 'react-router-dom';
import { exportToCSV } from '@/lib/export-utils';
import { toast } from 'sonner';
import type { GlobalUsageStats, TopTenant, TenantAtLimit, GlobalUsageMetric, Provider } from '@/types';

// Optimized bar chart component for usage history
// Uses React.memo to prevent unnecessary re-renders
const UsageHistoryChart = memo(function UsageHistoryChart({ data, label }: { data: number[]; label: string }) {
  // Pre-compute max value outside of render loop
  const max = useMemo(() => Math.max(...data, 1), [data]);
  
  // Pre-compute bar heights to avoid recalculation on each render
  const bars = useMemo(() => 
    data.map((value) => ({
      value,
      height: Math.max((value / max) * 100, 2)
    })),
    [data, max]
  );

  return (
    <div className="h-32 flex items-end gap-1">
      {bars.map(({ value, height }, i) => (
        <div
          key={i}
          className="flex-1 bg-primary/20 hover:bg-primary/30 rounded-t transition-all relative group"
          style={{ height: `${height}%` }}
        >
          <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-popover border rounded px-2 py-1 text-xs opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10">
            {value.toLocaleString()} {label}
          </div>
        </div>
      ))}
    </div>
  );
});

export function UsagePage() {
  useEffect(() => {
    document.title = 'Usage - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);
  const [topMetric, setTopMetric] = useState('workflows');
  const [topPeriod, setTopPeriod] = useState('all');
  const [providerFilter, setProviderFilter] = useState<Provider | 'all'>('all');

  // Fetch global usage stats
  const { data: usageData, isLoading: usageLoading, refetch: refetchUsage } = useQuery({
    queryKey: ['global-usage', providerFilter],
    queryFn: () => apiClient.getGlobalUsage(),
  });

  // Fetch top tenants
  const { data: topTenantsData, isLoading: topLoading } = useQuery({
    queryKey: ['top-tenants', topMetric, topPeriod, providerFilter],
    queryFn: () => apiClient.getTopTenants({ metric: topMetric, period: topPeriod, limit: 10, provider: providerFilter }),
  });

  // Fetch tenants at limit
  const { data: atLimitData, isLoading: atLimitLoading } = useQuery({
    queryKey: ['tenants-at-limit', providerFilter],
    queryFn: () => apiClient.getTenantsAtLimit(75, providerFilter),
  });

  // Fetch plans from database
  const { data: plansData } = useQuery({
    queryKey: ['admin-plans'],
    queryFn: () => apiClient.getAdminPlans(),
  });

  const plans = plansData?.data?.plans || [];
  const sortedPlans = [...plans].sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0));

  const stats: GlobalUsageStats = usageData?.data?.stats || {
    total_tenants: 0,
    total_workflows: 0,
    total_environments: 0,
    total_users: 0,
    total_executions_today: 0,
    total_executions_month: 0,
    tenants_at_limit: 0,
    tenants_over_limit: 0,
    tenants_near_limit: 0,
  };

  const usageByPlan = usageData?.data?.usage_by_plan || {};
  const recentGrowth = usageData?.data?.recent_growth || {};
  const topTenants: TopTenant[] = topTenantsData?.data?.tenants || [];
  const tenantsAtLimit: TenantAtLimit[] = atLimitData?.data?.tenants || [];

  const isLoading = usageLoading || topLoading || atLimitLoading;

  const { data: historyData } = useQuery({
    queryKey: ['admin-usage-history', providerFilter],
    queryFn: () => apiClient.getAdminUsageHistory({ metric: 'executions', days: 30, provider: providerFilter }),
  });

  const historicalData = useMemo(() => {
    const points = historyData?.data?.points || [];
    return points.map((p: any) => p.value);
  }, [historyData?.data]);

  // Export functions
  const handleExportTopTenants = () => {
    if (topTenants.length === 0) {
      toast.error('No data to export');
      return;
    }

    const columns = [
      { key: 'rank' as const, header: 'Rank' },
      { key: 'tenant_id' as const, header: 'Tenant ID' },
      { key: 'tenant_name' as const, header: 'Tenant Name' },
      { key: 'plan' as const, header: 'Plan' },
      ...(providerFilter === 'all' ? [{ key: 'provider' as const, header: 'Provider' }] : []),
      { key: 'value' as const, header: 'Value' },
      { key: 'limit' as const, header: 'Limit' },
      { key: 'percentage' as const, header: 'Usage %' },
    ];

    exportToCSV(topTenants, columns, `top-tenants-by-${topMetric}`);
    toast.success(`Exported ${topTenants.length} top tenants to CSV`);
  };

  const handleExportTenantsAtLimit = () => {
    if (tenantsAtLimit.length === 0) {
      toast.error('No data to export');
      return;
    }

    // Flatten the metrics for export
    const flattenedData = tenantsAtLimit.flatMap(tenant =>
      tenant.metrics.map((metric: GlobalUsageMetric) => ({
        tenant_id: tenant.tenant_id,
        tenant_name: tenant.tenant_name,
        plan: tenant.plan,
        status: tenant.status,
        metric_name: metric.name,
        current: metric.current,
        limit: metric.limit,
        percentage: metric.percentage,
        total_usage_percentage: tenant.total_usage_percentage,
      }))
    );

    const columns = [
      { key: 'tenant_id' as const, header: 'Tenant ID' },
      { key: 'tenant_name' as const, header: 'Tenant Name' },
      { key: 'plan' as const, header: 'Plan' },
      { key: 'status' as const, header: 'Status' },
      { key: 'metric_name' as const, header: 'Metric' },
      { key: 'current' as const, header: 'Current' },
      { key: 'limit' as const, header: 'Limit' },
      { key: 'percentage' as const, header: 'Metric %' },
      { key: 'total_usage_percentage' as const, header: 'Max Usage %' },
    ];

    exportToCSV(flattenedData, columns, 'tenants-at-limit');
    toast.success(`Exported ${tenantsAtLimit.length} tenants at limit to CSV`);
  };

  const handleExportUsageSummary = () => {
    const summaryData = [
      { metric: 'Total Tenants', value: stats.total_tenants },
      { metric: 'Total Workflows', value: stats.total_workflows },
      { metric: 'Total Environments', value: stats.total_environments },
      { metric: 'Total Users', value: stats.total_users },
      { metric: 'Executions Today', value: stats.total_executions_today },
      { metric: 'Executions This Month', value: stats.total_executions_month },
      { metric: 'Tenants Over Limit', value: stats.tenants_over_limit },
      { metric: 'Tenants At Limit', value: stats.tenants_at_limit },
      { metric: 'Tenants Near Limit', value: stats.tenants_near_limit },
      ...sortedPlans.map((plan) => ({
        metric: `${plan.displayName} Plan Tenants`,
        value: usageByPlan[plan.name] || 0,
      })),
    ];

    const columns = [
      { key: 'metric' as const, header: 'Metric' },
      { key: 'value' as const, header: 'Value' },
    ];

    exportToCSV(summaryData, columns, 'usage-summary');
    toast.success('Exported usage summary to CSV');
  };

  const getPlanBadgeVariant = (plan: string) => {
    switch (plan) {
      case 'enterprise': return 'default';
      case 'agency': return 'default';
      case 'pro': return 'secondary';
      default: return 'outline';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'over_limit': return 'text-red-600 bg-red-100 dark:bg-red-950';
      case 'critical': return 'text-red-500 bg-red-50 dark:bg-red-950/50';
      case 'warning': return 'text-amber-600 bg-amber-50 dark:bg-amber-950/50';
      default: return 'text-green-600 bg-green-50 dark:bg-green-950/50';
    }
  };

  const getProgressColor = (percentage: number) => {
    if (percentage >= 100) return 'bg-red-500';
    if (percentage >= 90) return 'bg-red-400';
    if (percentage >= 75) return 'bg-amber-400';
    return 'bg-green-500';
  };

  const getTrendIcon = (trend?: string) => {
    if (trend === 'up') return <TrendingUp className="h-4 w-4 text-green-500" />;
    if (trend === 'down') return <TrendingDown className="h-4 w-4 text-red-500" />;
    return null;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Usage & Limits</h1>
          <p className="text-muted-foreground">Monitor platform usage and identify upsell opportunities</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetchUsage()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" onClick={handleExportUsageSummary}>
            <Download className="h-4 w-4 mr-2" />
            Export Summary
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-8">Loading usage data...</div>
      ) : (
        <>
          {/* Global Stats */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Tenants</p>
                    <p className="text-2xl font-bold">{stats.total_tenants}</p>
                  </div>
                  <Building2 className="h-8 w-8 text-blue-500" />
                </div>
                <div className="flex items-center gap-1 mt-2 text-sm text-green-600">
                  <ArrowUpRight className="h-3 w-3" />
                  +{recentGrowth.tenants_30d || 0} this month
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Workflows</p>
                    <p className="text-2xl font-bold">{stats.total_workflows}</p>
                  </div>
                  <Workflow className="h-8 w-8 text-purple-500" />
                </div>
                <div className="flex items-center gap-1 mt-2 text-sm text-green-600">
                  <ArrowUpRight className="h-3 w-3" />
                  +{recentGrowth.workflows_30d || 0} this month
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Executions Today</p>
                    <p className="text-2xl font-bold">{stats.total_executions_today.toLocaleString()}</p>
                  </div>
                  <Zap className="h-8 w-8 text-amber-500" />
                </div>
                <div className="text-sm text-muted-foreground mt-2">
                  {stats.total_executions_month.toLocaleString()} this month
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Users</p>
                    <p className="text-2xl font-bold">{stats.total_users}</p>
                  </div>
                  <Users className="h-8 w-8 text-green-500" />
                </div>
                <div className="text-sm text-muted-foreground mt-2">
                  Across {stats.total_environments} environments
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Limit Alerts */}
          {(stats.tenants_over_limit > 0 || stats.tenants_at_limit > 0 || stats.tenants_near_limit > 0) && (
            <Card className="border-amber-500">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-amber-600">
                  <AlertTriangle className="h-5 w-5" />
                  Usage Alerts
                </CardTitle>
                <CardDescription>Tenants approaching or exceeding their plan limits</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="p-4 bg-red-50 dark:bg-red-950/50 rounded-lg">
                    <p className="text-3xl font-bold text-red-600">{stats.tenants_over_limit}</p>
                    <p className="text-sm text-muted-foreground">Over Limit</p>
                    <p className="text-xs text-red-600 mt-1">Immediate attention needed</p>
                  </div>
                  <div className="p-4 bg-amber-50 dark:bg-amber-950/50 rounded-lg">
                    <p className="text-3xl font-bold text-amber-600">{stats.tenants_at_limit}</p>
                    <p className="text-sm text-muted-foreground">At Limit (95%+)</p>
                    <p className="text-xs text-amber-600 mt-1">Upgrade candidates</p>
                  </div>
                  <div className="p-4 bg-yellow-50 dark:bg-yellow-950/50 rounded-lg">
                    <p className="text-3xl font-bold text-yellow-600">{stats.tenants_near_limit}</p>
                    <p className="text-sm text-muted-foreground">Near Limit (75%+)</p>
                    <p className="text-xs text-yellow-600 mt-1">Monitor closely</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Usage by Plan */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Usage by Plan
              </CardTitle>
              <CardDescription>Distribution of tenants across subscription plans</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-4">
                {sortedPlans.map((plan) => {
                  const count = usageByPlan[plan.name] || 0;
                  const total = stats.total_tenants || 1;
                  const percentage = Math.round((count / total) * 100);
                  const colorClass = {
                    free: 'bg-gray-400',
                    pro: 'bg-blue-500',
                    agency: 'bg-purple-500',
                    enterprise: 'bg-amber-500',
                  }[plan.name] || 'bg-gray-400';

                  return (
                    <div key={plan.id} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <Badge variant={getPlanBadgeVariant(plan.name)} className="capitalize">
                          {plan.displayName}
                        </Badge>
                        <span className="text-2xl font-bold">{count}</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full ${colorClass} rounded-full`}
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">{percentage}% of tenants</p>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Top Tenants */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Activity className="h-5 w-5" />
                      Top Tenants
                    </CardTitle>
                    <CardDescription>Ranked by usage metrics</CardDescription>
                  </div>
                  <div className="flex gap-2">
                    <Select value={topMetric} onValueChange={setTopMetric}>
                      <SelectTrigger className="w-[130px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="workflows">Workflows</SelectItem>
                        <SelectItem value="users">Users</SelectItem>
                        <SelectItem value="environments">Environments</SelectItem>
                        <SelectItem value="executions">Executions</SelectItem>
                      </SelectContent>
                    </Select>
                    <Select value={topPeriod} onValueChange={setTopPeriod}>
                      <SelectTrigger className="w-[100px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="today">Today</SelectItem>
                        <SelectItem value="week">Week</SelectItem>
                        <SelectItem value="month">Month</SelectItem>
                        <SelectItem value="all">All Time</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button variant="outline" size="icon" onClick={handleExportTopTenants} disabled={topTenants.length === 0}>
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {topTenants.length === 0 ? (
                  <p className="text-center py-4 text-muted-foreground">No data available</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">#</TableHead>
                        <TableHead>Tenant</TableHead>
                        <TableHead>Plan</TableHead>
                        {providerFilter === 'all' && <TableHead>Provider</TableHead>}
                        <TableHead className="text-right">Value</TableHead>
                        <TableHead className="text-right">% Used</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {topTenants.map((tenant) => (
                        <TableRow key={`${tenant.tenant_id}-${tenant.provider || ''}`}>
                          <TableCell className="font-medium">{tenant.rank}</TableCell>
                          <TableCell>
                            <Link
                              to={`/admin/tenants/${tenant.tenant_id}`}
                              className="hover:underline flex items-center gap-1"
                            >
                              {tenant.tenant_name}
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                          </TableCell>
                          <TableCell>
                            <Badge variant={getPlanBadgeVariant(tenant.plan)} className="capitalize">
                              {tenant.plan}
                            </Badge>
                          </TableCell>
                          {providerFilter === 'all' && (
                            <TableCell>
                              <Badge variant="outline" className="capitalize">
                                {tenant.provider || 'n8n'}
                              </Badge>
                            </TableCell>
                          )}
                          <TableCell className="text-right font-medium">
                            {tenant.value.toLocaleString()}
                            {tenant.limit && (
                              <span className="text-muted-foreground">/{tenant.limit}</span>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            {tenant.percentage !== undefined && tenant.percentage !== null ? (
                              <span className={tenant.percentage >= 90 ? 'text-red-600 font-medium' : tenant.percentage >= 75 ? 'text-amber-600' : ''}>
                                {tenant.percentage}%
                              </span>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            {/* Tenants at Limit */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5 text-amber-500" />
                      Tenants Near Limits
                    </CardTitle>
                    <CardDescription>Tenants using 75%+ of any resource limit</CardDescription>
                  </div>
                  <Button variant="outline" size="icon" onClick={handleExportTenantsAtLimit} disabled={tenantsAtLimit.length === 0}>
                    <Download className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {tenantsAtLimit.length === 0 ? (
                  <p className="text-center py-4 text-muted-foreground">No tenants near limits</p>
                ) : (
                  <div className="space-y-4">
                    {tenantsAtLimit.slice(0, 5).map((tenant) => (
                      <div key={tenant.tenant_id} className="p-4 border rounded-lg space-y-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <Link
                              to={`/admin/tenants/${tenant.tenant_id}`}
                              className="font-medium hover:underline flex items-center gap-1"
                            >
                              {tenant.tenant_name}
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant={getPlanBadgeVariant(tenant.plan)} className="capitalize">
                                {tenant.plan}
                              </Badge>
                              <Badge variant="outline" className="capitalize">
                                {tenant.status}
                              </Badge>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className={`text-lg font-bold ${tenant.total_usage_percentage >= 100 ? 'text-red-600' : tenant.total_usage_percentage >= 90 ? 'text-amber-600' : 'text-amber-500'}`}>
                              {tenant.total_usage_percentage.toFixed(0)}%
                            </p>
                            <p className="text-xs text-muted-foreground">max usage</p>
                          </div>
                        </div>
                        <div className="space-y-2">
                          {tenant.metrics.map((metric: GlobalUsageMetric) => (
                            <div key={metric.name} className="space-y-1">
                              <div className="flex items-center justify-between text-sm">
                                <span className="capitalize">{metric.name}</span>
                                <span className={metric.percentage >= 90 ? 'text-red-600 font-medium' : ''}>
                                  {metric.current}/{metric.limit > 0 ? metric.limit : '∞'} ({metric.percentage.toFixed(0)}%)
                                </span>
                              </div>
                              <Progress
                                value={Math.min(metric.percentage, 100)}
                                className="h-1.5"
                              />
                            </div>
                          ))}
                        </div>
                        <Button variant="outline" size="sm" className="w-full" asChild>
                          <Link to={`/admin/tenants/${tenant.tenant_id}`}>
                            View Details / Recommend Upgrade
                          </Link>
                        </Button>
                      </div>
                    ))}
                    {tenantsAtLimit.length > 5 && (
                      <p className="text-center text-sm text-muted-foreground">
                        +{tenantsAtLimit.length - 5} more tenants near limits
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Growth Metrics */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                Recent Growth
              </CardTitle>
              <CardDescription>Platform growth over the last 7 and 30 days</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3">
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">New Tenants</p>
                      <div className="flex items-baseline gap-2">
                        <p className="text-2xl font-bold">+{recentGrowth.tenants_7d || 0}</p>
                        <span className="text-sm text-muted-foreground">7d</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-medium">+{recentGrowth.tenants_30d || 0}</p>
                      <span className="text-xs text-muted-foreground">30d</span>
                    </div>
                  </div>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">New Workflows</p>
                      <div className="flex items-baseline gap-2">
                        <p className="text-2xl font-bold">+{recentGrowth.workflows_7d || 0}</p>
                        <span className="text-sm text-muted-foreground">7d</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-medium">+{recentGrowth.workflows_30d || 0}</p>
                      <span className="text-xs text-muted-foreground">30d</span>
                    </div>
                  </div>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Executions</p>
                      <div className="flex items-baseline gap-2">
                        <p className="text-2xl font-bold">{(recentGrowth.executions_7d || 0).toLocaleString()}</p>
                        <span className="text-sm text-muted-foreground">7d</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-medium">{(recentGrowth.executions_30d || 0).toLocaleString()}</p>
                      <span className="text-xs text-muted-foreground">30d</span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Historical Usage Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Execution History (Last 30 Days)
              </CardTitle>
              <CardDescription>Daily execution counts across all tenants</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <UsageHistoryChart data={historicalData} label="executions" />
                <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
                  <span>30 days ago</span>
                  <div className="flex items-center gap-4">
                    <span>Avg: {Math.round(historicalData.reduce((a, b) => a + b, 0) / historicalData.length).toLocaleString()}/day</span>
                    <span>Peak: {Math.max(...historicalData).toLocaleString()}</span>
                    <span>Total: {historicalData.reduce((a, b) => a + b, 0).toLocaleString()}</span>
                  </div>
                  <span>Today</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
