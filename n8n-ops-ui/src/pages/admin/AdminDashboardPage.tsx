// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Server,
  Shield,
  AlertTriangle,
  GitCompare,
  Workflow,
  History,
  Camera,
  Users,
  BarChart3,
  CreditCard,
  Settings,
  ArrowRight,
  Sparkles,
  Lock,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { useFeatures } from '@/lib/features';
import { isAtLeastPlan, normalizePlan } from '@/lib/permissions';
import { cn } from '@/lib/utils';

// Org Health tile component
function HealthTile({
  title,
  value,
  subValue,
  status,
  icon: Icon,
  href,
}: {
  title: string;
  value: string | number;
  subValue?: string;
  status: 'healthy' | 'warning' | 'critical';
  icon: React.ComponentType<{ className?: string }>;
  href: string;
}) {
  const statusColors = {
    healthy: 'bg-green-500/10 text-green-700 dark:text-green-400',
    warning: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400',
    critical: 'bg-red-500/10 text-red-700 dark:text-red-400',
  };

  const statusDot = {
    healthy: 'bg-green-500',
    warning: 'bg-yellow-500',
    critical: 'bg-red-500',
  };

  return (
    <Link to={href}>
      <Card className="hover:shadow-md transition-shadow cursor-pointer">
        <CardContent className="p-4">
          <div className="flex items-start justify-between">
            <div className={cn('p-2 rounded-lg', statusColors[status])}>
              <Icon className="h-5 w-5" />
            </div>
            <div className={cn('h-2 w-2 rounded-full', statusDot[status])} />
          </div>
          <div className="mt-3">
            <p className="text-2xl font-bold">{value}</p>
            {subValue && <p className="text-xs text-muted-foreground">{subValue}</p>}
          </div>
          <p className="text-sm text-muted-foreground mt-1">{title}</p>
        </CardContent>
      </Card>
    </Link>
  );
}

// Usage pressure card component
function UsagePressureCard({
  title,
  used,
  limit,
  href,
}: {
  title: string;
  used: number;
  limit: number | null;
  href: string;
}) {
  const isUnlimited = limit === null || limit === -1 || limit >= 9999;
  const percentage = isUnlimited ? 0 : Math.round((used / limit) * 100);

  let status: 'ok' | 'warning' | 'critical' = 'ok';
  if (!isUnlimited) {
    if (percentage >= 95) status = 'critical';
    else if (percentage >= 80) status = 'warning';
  }

  const statusColors = {
    ok: 'bg-primary',
    warning: 'bg-yellow-500',
    critical: 'bg-red-500',
  };

  return (
    <Link to={href}>
      <Card className="hover:shadow-md transition-shadow cursor-pointer">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium">{title}</p>
            {status !== 'ok' && (
              <Badge variant={status === 'critical' ? 'destructive' : 'secondary'} className="text-xs">
                {status === 'critical' ? 'Critical' : 'Warning'}
              </Badge>
            )}
          </div>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold">{used.toLocaleString()}</span>
            <span className="text-sm text-muted-foreground">
              / {isUnlimited ? 'Unlimited' : limit?.toLocaleString()}
            </span>
          </div>
          {!isUnlimited && (
            <div className="mt-2">
              <Progress
                value={percentage}
                className={cn('h-2', statusColors[status])}
              />
              <p className="text-xs text-muted-foreground mt-1">{percentage}% used</p>
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

// Governance signal row
function GovernanceSignal({
  title,
  count,
  href,
  icon: Icon,
}: {
  title: string;
  count: number;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  if (count === 0) return null;

  return (
    <Link
      to={href}
      className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/50 transition-colors"
    >
      <div className="flex items-center gap-3">
        <div className="p-1.5 rounded bg-yellow-500/10">
          <Icon className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
        </div>
        <span className="text-sm">{title}</span>
      </div>
      <div className="flex items-center gap-2">
        <Badge variant="secondary">{count}</Badge>
        <ArrowRight className="h-4 w-4 text-muted-foreground" />
      </div>
    </Link>
  );
}

// Upgrade Required page for Free users
export function AdminUpgradeRequiredPage() {
  useEffect(() => {
    document.title = 'Upgrade Required - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="p-4 rounded-full bg-primary/10 mb-6">
        <Lock className="h-12 w-12 text-primary" />
      </div>
      <h1 className="text-3xl font-bold mb-2">Upgrade Required</h1>
      <p className="text-muted-foreground mb-8 max-w-md">
        The Admin Dashboard is available on Pro and Agency plans. Upgrade to unlock powerful insights and governance tools.
      </p>

      <div className="grid gap-4 mb-8 text-left max-w-sm">
        <div className="flex items-start gap-3">
          <Shield className="h-5 w-5 text-primary mt-0.5" />
          <div>
            <p className="font-medium">Credential Health Monitoring</p>
            <p className="text-sm text-muted-foreground">Track credential status across environments</p>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <BarChart3 className="h-5 w-5 text-primary mt-0.5" />
          <div>
            <p className="font-medium">Detailed Usage Analytics</p>
            <p className="text-sm text-muted-foreground">Monitor executions, workflows, and limits</p>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <GitCompare className="h-5 w-5 text-primary mt-0.5" />
          <div>
            <p className="font-medium">Governance Signals</p>
            <p className="text-sm text-muted-foreground">Drift detection and risk indicators</p>
          </div>
        </div>
      </div>

      <Button onClick={() => navigate('/admin/providers')} size="lg">
        <Sparkles className="h-4 w-4 mr-2" />
        Upgrade to Pro
      </Button>
    </div>
  );
}

// Main Admin Dashboard for Pro/Agency users
export function AdminDashboardPage() {
  useEffect(() => {
    document.title = 'Admin Dashboard - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const { planName } = useFeatures();
  const normalizedPlan = normalizePlan(planName);

  // If free plan, show upgrade page
  if (!isAtLeastPlan(normalizedPlan, 'pro')) {
    return <AdminUpgradeRequiredPage />;
  }

  // Fetch admin overview data
  const { data: overview, isLoading } = useQuery({
    queryKey: ['admin-overview'],
    queryFn: () => apiClient.getAdminOverview(),
  });

  const data = overview?.data;

  // Calculate health statuses
  const getEnvironmentStatus = () => {
    if (!data) return 'healthy';
    const { environment_count, environment_limit } = data;
    if (environment_limit === null || environment_limit === -1) return 'healthy';
    const percentage = (environment_count / environment_limit) * 100;
    if (percentage >= 95) return 'critical';
    if (percentage >= 80) return 'warning';
    return 'healthy';
  };

  const getCredentialStatus = () => {
    if (!data?.credential_health) return 'healthy';
    const { failing, warning } = data.credential_health;
    if (failing > 0) return 'critical';
    if (warning > 0) return 'warning';
    return 'healthy';
  };

  const getFailuresStatus = () => {
    if (!data) return 'healthy';
    if (data.failed_executions_24h > 10) return 'critical';
    if (data.failed_executions_24h > 0) return 'warning';
    return 'healthy';
  };

  const getDriftStatus = () => {
    if (!data) return 'healthy';
    if (data.drift_detected_count > 0) return 'warning';
    return 'healthy';
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Admin Dashboard</h1>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <p className="text-muted-foreground">Organization health, usage, and governance at a glance</p>
      </div>

      {/* Org Health Tiles */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Organization Health</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <HealthTile
            title="Environments"
            value={data?.environment_count ?? 0}
            subValue={data?.environment_limit ? `of ${data.environment_limit} limit` : 'Unlimited'}
            status={getEnvironmentStatus()}
            icon={Server}
            href="/environments"
          />
          <HealthTile
            title="Credential Health"
            value={data?.credential_health?.healthy ?? 0}
            subValue={`${data?.credential_health?.warning ?? 0} warning, ${data?.credential_health?.failing ?? 0} failing`}
            status={getCredentialStatus()}
            icon={Shield}
            href="/credentials"
          />
          <HealthTile
            title="Recent Failures"
            value={data?.failed_executions_24h ?? 0}
            subValue="in last 24 hours"
            status={getFailuresStatus()}
            icon={AlertTriangle}
            href="/executions?status=failed"
          />
          <HealthTile
            title="Drift Detected"
            value={data?.drift_detected_count ?? 0}
            subValue="environments"
            status={getDriftStatus()}
            icon={GitCompare}
            href="/environments?drift=detected"
          />
        </div>
      </div>

      {/* Usage & Limits */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Usage & Limits</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <UsagePressureCard
            title="Executions"
            used={data?.usage?.executions?.used ?? 0}
            limit={data?.usage?.executions?.limit ?? null}
            href="/admin/usage"
          />
          <UsagePressureCard
            title="Workflows"
            used={data?.usage?.workflows?.used ?? 0}
            limit={data?.usage?.workflows?.limit ?? null}
            href="/admin/usage"
          />
          <UsagePressureCard
            title="Snapshots"
            used={data?.usage?.snapshots?.used ?? 0}
            limit={data?.usage?.snapshots?.limit ?? null}
            href="/admin/usage"
          />
          <UsagePressureCard
            title="Pipelines"
            used={data?.usage?.pipelines?.used ?? 0}
            limit={data?.usage?.pipelines?.limit ?? null}
            href="/admin/usage"
          />
        </div>
      </div>

      {/* Governance Signals */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Governance Signals</CardTitle>
          <CardDescription>Items requiring attention</CardDescription>
        </CardHeader>
        <CardContent className="space-y-1">
          <GovernanceSignal
            title="Credentials needing attention"
            count={(data?.credential_health?.warning ?? 0) + (data?.credential_health?.failing ?? 0)}
            href="/credentials"
            icon={Shield}
          />
          <GovernanceSignal
            title="Environments with drift"
            count={data?.drift_detected_count ?? 0}
            href="/environments?drift=detected"
            icon={GitCompare}
          />
          {((data?.credential_health?.warning ?? 0) + (data?.credential_health?.failing ?? 0) === 0) &&
           (data?.drift_detected_count ?? 0) === 0 && (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No governance issues detected
            </p>
          )}
        </CardContent>
      </Card>

      {/* Admin Shortcuts */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Admin Shortcuts</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link to="/admin/members">
                <Users className="h-4 w-4 mr-2" />
                Members
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to="/admin/usage">
                <BarChart3 className="h-4 w-4 mr-2" />
                Usage
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to="/admin/providers">
                <CreditCard className="h-4 w-4 mr-2" />
                Billing & Plans
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link to="/admin/settings">
                <Settings className="h-4 w-4 mr-2" />
                Settings
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
