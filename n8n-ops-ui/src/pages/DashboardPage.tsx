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
import { Activity, Workflow, Server, Plus, Rocket } from 'lucide-react';

export function DashboardPage() {
  useEffect(() => {
    document.title = 'Dashboard - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);
  const { user, hasEnvironment } = useAuth();

  const { data: environments, isLoading: loadingEnvs } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const { data: executions } = useQuery({
    queryKey: ['executions'],
    queryFn: () => apiClient.getExecutions(),
    enabled: hasEnvironment,
  });

  const envCount = environments?.data?.filter((e) => e.isActive).length || 0;
  const totalWorkflows = environments?.data?.reduce((sum, e) => sum + (e.workflowCount || 0), 0) || 0;
  const totalExecutions = executions?.data?.length || 0;

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
            <h2 className="text-2xl font-semibold mb-2">Get Started with N8N Ops</h2>
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
                Track executions, manage versions, and deploy across environments.
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
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Common tasks</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2">
              <Link to="/workflows">
                <Button variant="outline" className="w-full justify-start">
                  <Workflow className="h-4 w-4 mr-2" />
                  View Workflows
                </Button>
              </Link>
              <Link to="/executions">
                <Button variant="outline" className="w-full justify-start">
                  <Activity className="h-4 w-4 mr-2" />
                  View Executions
                </Button>
              </Link>
              <Link to="/environments">
                <Button variant="outline" className="w-full justify-start">
                  <Server className="h-4 w-4 mr-2" />
                  Manage Environments
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
