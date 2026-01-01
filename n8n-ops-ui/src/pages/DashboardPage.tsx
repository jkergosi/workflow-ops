// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api-client';
import { useAuth } from '@/lib/auth';
import { useFeatures } from '@/lib/features';
import { Activity, Workflow, Server, Plus, Rocket, Camera, History, GitBranch, ArrowRight, Settings, Shield, RotateCcw, AlertTriangle } from 'lucide-react';

export function DashboardPage() {
  useEffect(() => {
    document.title = 'Dashboard - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);
  const { user, hasEnvironment } = useAuth();
  const { planName, isLoading: loadingFeatures } = useFeatures();

  const { data: environments, isLoading: loadingEnvs } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const { data: executions } = useQuery({
    queryKey: ['executions'],
    queryFn: () => apiClient.getExecutions(),
    enabled: hasEnvironment,
  });

  // Context-aware queries for recommended actions
  const firstEnvironmentId = environments?.data?.[0]?.id;
  const planLower = planName?.toLowerCase() || 'free';

  const { data: snapshots } = useQuery({
    queryKey: ['snapshots', firstEnvironmentId],
    queryFn: () => apiClient.getSnapshots({ 
      environmentId: firstEnvironmentId 
    }),
    enabled: !!firstEnvironmentId && (planLower === 'pro' || planLower === 'agency' || planLower === 'enterprise'),
  });

  const { data: pipelines } = useQuery({
    queryKey: ['pipelines', 'all'],
    queryFn: () => apiClient.getPipelines({ includeInactive: true }),
    enabled: planLower === 'agency' || planLower === 'enterprise',
  });

  const { data: incidents } = useQuery({
    queryKey: ['incidents', 'recent'],
    queryFn: () => apiClient.getIncidents({ limit: 10 }),
    enabled: planLower === 'agency',
  });

  const envCount = environments?.data?.filter((e) => e.isActive).length || 0;
  const totalWorkflows = environments?.data?.reduce((sum, e) => sum + (e.workflowCount || 0), 0) || 0;
  const totalExecutions = executions?.data?.length || 0;
  
  // Context checks
  const hasSnapshots = (snapshots?.data?.length || 0) > 0;
  const hasPipelines = (pipelines?.data?.length || 0) > 0;
  const hasRepeatedDriftIncidents = (incidents?.data?.length || 0) >= 2;

  const stats = [
    {
      title: 'Total Workflows',
      value: totalWorkflows,
      icon: Workflow,
      description: 'Across all environments',
    },
    {
      title: 'Recent Executions',
      value: totalExecutions,
      icon: Activity,
      description: 'In the last sync',
    },
    {
      title: 'Environments',
      value: envCount,
      icon: Server,
      description: 'Connected and active',
    },
  ];

  // Show empty state if no environments
  if (!loadingEnvs && (!environments?.data || environments.data.length === 0)) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Welcome back, {user?.name || 'User'}
          </p>
        </div>

        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mb-6">
              <Rocket className="h-8 w-8 text-primary" />
            </div>
            <h2 className="text-2xl font-semibold mb-2">Get Started with WorkflowOps</h2>
            <p className="text-muted-foreground text-center max-w-md mb-6">
              Connect your first N8N environment to start managing and monitoring your workflows.
            </p>
            <Link to="/environments/new?first=true">
              <Button size="lg">
                <Plus className="h-5 w-5 mr-2" />
                Create Your First Environment
              </Button>
            </Link>
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">1. Connect N8N</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Add your N8N instance URL and API key to connect your workflows.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">2. Sync Workflows</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Your workflows will be automatically synced and available for management.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">3. Monitor & Manage</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Track executions, manage versions, and monitor your workflows.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Welcome back, {user?.name || 'User'}
          </p>
        </div>
        <Link to="/environments/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Add Environment
          </Button>
        </Link>
      </div>

      <div className="flex items-center gap-2">
        <Badge variant="outline">Plan: {user?.subscriptionPlan || 'Free'}</Badge>
        <Badge variant="outline">{user?.tenantName}</Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.title}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stat.value}</div>
                <p className="text-xs text-muted-foreground">{stat.description}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Environment Status</CardTitle>
            <CardDescription>Connected N8N instances</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {environments?.data?.map((env) => (
                <div
                  key={env.id}
                  className="flex items-center justify-between p-2 rounded-md border"
                >
                  <div>
                    <p className="font-medium">{env.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {env.type} - {env.workflowCount || 0} workflows
                    </p>
                  </div>
                  <Badge variant={env.isActive ? 'success' : 'outline'}>
                    {env.isActive ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              ))}
              {(!environments?.data || environments.data.length === 0) && (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  No environments connected yet
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recommended Next Step</CardTitle>
            <CardDescription>What you should do next based on your plan</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {(() => {
                // Free plan
                if (planLower === 'free') {
                  const shouldUpsellToPro = !loadingFeatures && envCount > 0; // Free has no snapshots, so "no snapshots exist" is effectively true once connected
                  if (shouldUpsellToPro) {
                    return (
                      <>
                        <div className="space-y-1">
                          <div className="font-semibold">Protect your workflows automatically</div>
                          <div className="text-sm text-muted-foreground">
                            Automatic snapshots and instant restore let you recover from mistakes without fear.
                          </div>
                        </div>
                        <Link to="/billing">
                          <Button className="w-full" size="lg">
                            Upgrade to Pro
                          </Button>
                        </Link>
                        <div className="grid gap-2">
                          <Link to="/workflows">
                            <Button variant="outline" className="w-full justify-start">
                              <Workflow className="h-4 w-4 mr-2" />
                              View Workflows
                            </Button>
                          </Link>
                        </div>
                      </>
                    );
                  }

                  const primary = {
                    label: envCount === 0 ? 'Add Environment' : 'View Workflows',
                    href: envCount === 0 ? '/environments/new' : '/workflows',
                    icon: envCount === 0 ? Plus : Workflow,
                  };
                  const secondary = [
                    { label: 'Sync Workflows', href: '/workflows', icon: Workflow },
                    { label: 'View Executions', href: '/executions', icon: Activity },
                  ];
                  
                  return (
                    <>
                      <Link to={primary.href}>
                        <Button className="w-full" size="lg">
                          <primary.icon className="h-5 w-5 mr-2" />
                          {primary.label}
                        </Button>
                      </Link>
                      <div className="grid gap-2">
                        {secondary.map((action, idx) => (
                          <Link key={idx} to={action.href}>
                            <Button variant="outline" className="w-full justify-start">
                              <action.icon className="h-4 w-4 mr-2" />
                              {action.label}
                            </Button>
                          </Link>
                        ))}
                      </div>
                    </>
                  );
                }
                
                // Pro plan
                if (planLower === 'pro') {
                  const shouldUpsellToAgency = !loadingFeatures && envCount >= 2;
                  if (shouldUpsellToAgency) {
                    return (
                      <>
                        <div className="space-y-1">
                          <div className="font-semibold">Deliver changes safely as a team</div>
                          <div className="text-sm text-muted-foreground">
                            Pipelines, approvals, and drift management help teams promote changes without surprises.
                          </div>
                        </div>
                        <Link to="/billing">
                          <Button className="w-full" size="lg">
                            Upgrade to Agency
                          </Button>
                        </Link>
                        <div className="grid gap-2">
                          <Link to="/snapshots">
                            <Button variant="outline" className="w-full justify-start">
                              <History className="h-4 w-4 mr-2" />
                              View Snapshots
                            </Button>
                          </Link>
                        </div>
                      </>
                    );
                  }

                  const primary = {
                    label: !hasSnapshots ? 'Set Up Snapshots' : 'View Snapshots',
                    href: '/snapshots',
                    icon: !hasSnapshots ? Camera : History,
                  };
                  const secondary = [
                    { 
                      label: hasSnapshots ? 'Promote Workflows' : 'View Snapshots', 
                      href: hasSnapshots ? '/deployments/new' : '/snapshots', 
                      icon: hasSnapshots ? GitBranch : Camera 
                    },
                    { label: 'Restore from Snapshot', href: '/snapshots', icon: RotateCcw },
                  ];
                  
                  return (
                    <>
                      <Link to={primary.href}>
                        <Button className="w-full" size="lg">
                          <primary.icon className="h-5 w-5 mr-2" />
                          {primary.label}
                        </Button>
                      </Link>
                      <div className="grid gap-2">
                        {secondary.map((action, idx) => (
                          <Link key={idx} to={action.href}>
                            <Button variant="outline" className="w-full justify-start">
                              <action.icon className="h-4 w-4 mr-2" />
                              {action.label}
                            </Button>
                          </Link>
                        ))}
                      </div>
                    </>
                  );
                }
                
                // Agency plan
                if (planLower === 'agency') {
                  const shouldUpsellToEnterprise = !loadingFeatures && hasRepeatedDriftIncidents;
                  if (shouldUpsellToEnterprise) {
                    return (
                      <>
                        <div className="space-y-1">
                          <div className="font-semibold">Enforce automation governance at scale</div>
                          <div className="text-sm text-muted-foreground">
                            Policies, SLAs, and audit logs provide compliance and operational guarantees.
                          </div>
                        </div>
                        <Link to="/billing">
                          <Button className="w-full" size="lg">
                            Contact Sales
                          </Button>
                        </Link>
                        <div className="grid gap-2">
                          <Link to="/incidents">
                            <Button variant="outline" className="w-full justify-start">
                              <AlertTriangle className="h-4 w-4 mr-2" />
                              Review Incidents
                            </Button>
                          </Link>
                        </div>
                      </>
                    );
                  }

                  const primary = {
                    label: !hasPipelines ? 'Configure Pipeline' : 'Run Promotion',
                    href: !hasPipelines ? '/deployments?tab=pipelines' : '/deployments/new',
                    icon: !hasPipelines ? Settings : ArrowRight,
                  };
                  const secondary = [
                    { 
                      label: hasPipelines ? 'View Pipelines' : 'Create Pipeline', 
                      href: '/deployments?tab=pipelines', 
                      icon: GitBranch 
                    },
                    { label: 'Resolve Drift', href: '/incidents', icon: AlertTriangle },
                  ];
                  
                  return (
                    <>
                      <Link to={primary.href}>
                        <Button className="w-full" size="lg">
                          <primary.icon className="h-5 w-5 mr-2" />
                          {primary.label}
                        </Button>
                      </Link>
                      <div className="grid gap-2">
                        {secondary.map((action, idx) => (
                          <Link key={idx} to={action.href}>
                            <Button variant="outline" className="w-full justify-start">
                              <action.icon className="h-4 w-4 mr-2" />
                              {action.label}
                            </Button>
                          </Link>
                        ))}
                      </div>
                    </>
                  );
                }
                
                // Enterprise plan
                if (planLower === 'enterprise') {
                  const primary = {
                    label: 'Review Drift Posture',
                    href: '/drift-dashboard',
                    icon: Shield,
                  };
                  const secondary = [
                    { label: 'Manage Policies', href: '/admin/drift-policies', icon: Shield },
                    { label: 'Review Incidents', href: '/incidents', icon: AlertTriangle },
                  ];
                  
                  return (
                    <>
                      <Link to={primary.href}>
                        <Button className="w-full" size="lg">
                          <primary.icon className="h-5 w-5 mr-2" />
                          {primary.label}
                        </Button>
                      </Link>
                      <div className="grid gap-2">
                        {secondary.map((action, idx) => (
                          <Link key={idx} to={action.href}>
                            <Button variant="outline" className="w-full justify-start">
                              <action.icon className="h-4 w-4 mr-2" />
                              {action.label}
                            </Button>
                          </Link>
                        ))}
                      </div>
                    </>
                  );
                }
                
                // Fallback for unknown plans
                const primary = { label: 'Manage Environments', href: '/environments', icon: Server };
                const secondary = [{ label: 'View Workflows', href: '/workflows', icon: Workflow }];
                
                return (
                  <>
                    <Link to={primary.href}>
                      <Button className="w-full" size="lg">
                        <primary.icon className="h-5 w-5 mr-2" />
                        {primary.label}
                      </Button>
                    </Link>
                    <div className="grid gap-2">
                      {secondary.map((action, idx) => (
                        <Link key={idx} to={action.href}>
                          <Button variant="outline" className="w-full justify-start">
                            <action.icon className="h-4 w-4 mr-2" />
                            {action.label}
                          </Button>
                        </Link>
                      ))}
                    </div>
                  </>
                );
              })()}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
