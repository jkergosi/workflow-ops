// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  CreditCard,
  Users,
  Check,
  X,
  Edit,
  Settings,
  DollarSign,
  Zap,
  Building2,
  Crown,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast as _toast } from 'sonner';
import { Link } from 'react-router-dom';


export function PlansPage() {
  useEffect(() => {
    document.title = 'Plans - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);

  // Fetch plans from database
  const { data: plansData, isLoading: loadingPlans } = useQuery({
    queryKey: ['admin-plans'],
    queryFn: () => apiClient.getAdminPlans(),
  });

  // Fetch feature matrix for plan features
  const { data: matrixData } = useQuery({
    queryKey: ['feature-matrix'],
    queryFn: () => apiClient.getFeatureMatrix(),
  });

  // Fetch plan distribution for stats
  const { data: distributionData } = useQuery({
    queryKey: ['plan-distribution'],
    queryFn: () => apiClient.getPlanDistribution(),
  });

  // Fetch billing metrics
  const { data: metricsData } = useQuery({
    queryKey: ['billing-metrics'],
    queryFn: () => apiClient.getBillingMetrics(),
  });

  const plans = plansData?.data?.plans || [];
  const sortedPlans = [...plans].sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0));
  const matrix = matrixData?.data;
  const distribution = distributionData?.data || [];
  const metrics = metricsData?.data || { mrr: 0, arr: 0, total_subscriptions: 0, churn_rate: 0 };

  const getPlanIcon = (plan: string) => {
    switch (plan) {
      case 'free':
        return <Zap className="h-5 w-5" />;
      case 'pro':
        return <CreditCard className="h-5 w-5" />;
      case 'agency':
        return <Building2 className="h-5 w-5" />;
      case 'enterprise':
        return <Crown className="h-5 w-5" />;
      default:
        return <CreditCard className="h-5 w-5" />;
    }
  };

  const getPlanColor = (plan: string) => {
    switch (plan) {
      case 'free':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200';
      case 'pro':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'agency':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200';
      case 'enterprise':
        return 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const handleEditPlan = (plan: string) => {
    setSelectedPlan(plan);
    setEditDialogOpen(true);
  };

  const renderFeatureValue = (value: boolean | number | string) => {
    if (typeof value === 'boolean') {
      return value ? (
        <Check className="h-5 w-5 text-green-500" />
      ) : (
        <X className="h-5 w-5 text-muted-foreground" />
      );
    }
    return <span className="font-medium">{value}</span>;
  };

  const getTenantCount = (planName: string) => {
    const item = distribution.find((d: any) => (d.plan || d.planName) === planName);
    return item?.count || 0;
  };

  const getPlanFeatureValue = (planName: string, featureKey: string) => {
    if (!matrix) return null;
    const feature = matrix.features.find((f) => f.featureKey === featureKey);
    if (!feature) return null;
    return feature.planValues[planName] ?? null;
  };

  const getPlanDisplayValue = (value: any): string | number => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value === 'number') {
      if (value === -1 || value === 9999) return 'Unlimited';
      return value;
    }
    if (typeof value === 'object' && value.enabled !== undefined) {
      return value.enabled ? 'Yes' : 'No';
    }
    return String(value);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Plans Management</h1>
          <p className="text-muted-foreground">Configure subscription plans and features</p>
        </div>
        <Button variant="outline" asChild>
          <Link to="/admin/entitlements/matrix">
            <Settings className="h-4 w-4 mr-2" />
            Feature Matrix
          </Link>
        </Button>
      </div>

      {/* Revenue Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <DollarSign className="h-8 w-8 text-green-500" />
              <div>
                <p className="text-2xl font-bold">${metrics.mrr?.toLocaleString() || 0}</p>
                <p className="text-sm text-muted-foreground">Monthly Revenue</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <DollarSign className="h-8 w-8 text-blue-500" />
              <div>
                <p className="text-2xl font-bold">${metrics.arr?.toLocaleString() || 0}</p>
                <p className="text-sm text-muted-foreground">Annual Revenue</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Users className="h-8 w-8 text-purple-500" />
              <div>
                <p className="text-2xl font-bold">{metrics.total_subscriptions || 0}</p>
                <p className="text-sm text-muted-foreground">Total Subscribers</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Building2 className="h-8 w-8 text-amber-500" />
              <div>
                <p className="text-2xl font-bold">{getTenantCount('enterprise')}</p>
                <p className="text-sm text-muted-foreground">Enterprise Tenants</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Plan Overview</TabsTrigger>
          <TabsTrigger value="features">Feature Comparison</TabsTrigger>
          <TabsTrigger value="pricing">Pricing</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          {loadingPlans ? (
            <div className="text-center py-8 text-muted-foreground">Loading plans...</div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {sortedPlans.map((plan) => (
              <Card key={plan} className="relative">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div className={`p-2 rounded-lg ${getPlanColor(plan)}`}>
                      {getPlanIcon(plan)}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEditPlan(plan)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                  </div>
                  <CardTitle>{plan.displayName}</CardTitle>
                  <CardDescription>{plan.description || ''}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="text-3xl font-bold">
                    <span className="text-sm font-normal text-muted-foreground">Plan Details</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm">
                      {getTenantCount(plan.name)} tenants
                    </span>
                  </div>
                  <div className="space-y-2 pt-4 border-t">
                    <p className="text-sm font-medium">Key Features:</p>
                    <ul className="text-sm space-y-1 text-muted-foreground">
                      {matrix && (() => {
                        const envValue = getPlanFeatureValue(plan.name, 'max_environments');
                        const workflowValue = getPlanFeatureValue(plan.name, 'max_workflows');
                        const teamValue = getPlanFeatureValue(plan.name, 'max_team_members');
                        return (
                          <>
                            {envValue !== null && (
                              <li className="flex items-center gap-2">
                                <Check className="h-3 w-3 text-green-500" />
                                {getPlanDisplayValue(envValue)} environment(s)
                              </li>
                            )}
                            {workflowValue !== null && (
                              <li className="flex items-center gap-2">
                                <Check className="h-3 w-3 text-green-500" />
                                {getPlanDisplayValue(workflowValue)} workflows
                              </li>
                            )}
                            {teamValue !== null && (
                              <li className="flex items-center gap-2">
                                <Check className="h-3 w-3 text-green-500" />
                                {getPlanDisplayValue(teamValue)} team members
                              </li>
                            )}
                          </>
                        );
                      })()}
                    </ul>
                  </div>
                </CardContent>
              </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Features Tab */}
        <TabsContent value="features">
          <Card>
            <CardHeader>
              <CardTitle>Feature Comparison</CardTitle>
              <CardDescription>
                Compare features across all subscription plans
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!matrix ? (
                <div className="text-center py-8 text-muted-foreground">Loading feature matrix...</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[300px]">Feature</TableHead>
                      {sortedPlans.map((plan) => (
                        <TableHead key={plan.id} className="text-center">
                          {plan.displayName}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {matrix.features.map((feature) => (
                      <TableRow key={feature.featureId}>
                        <TableCell>
                          <div>
                            <p className="font-medium">{feature.featureDisplayName}</p>
                            <p className="text-sm text-muted-foreground font-mono">{feature.featureKey}</p>
                            {feature.description && (
                              <p className="text-sm text-muted-foreground mt-1">{feature.description}</p>
                            )}
                          </div>
                        </TableCell>
                        {sortedPlans.map((plan) => {
                          const value = feature.planValues[plan.name];
                          return (
                            <TableCell key={plan.id} className="text-center">
                              {renderFeatureValue(value)}
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Pricing Tab */}
        <TabsContent value="pricing">
          <Card>
            <CardHeader>
              <CardTitle>Pricing Configuration</CardTitle>
              <CardDescription>
                View and configure plan pricing (connected to Stripe)
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Plan</TableHead>
                    <TableHead className="text-right">Monthly</TableHead>
                    <TableHead className="text-right">Annual</TableHead>
                    <TableHead className="text-right">Annual Savings</TableHead>
                    <TableHead className="text-right">Tenants</TableHead>
                    <TableHead className="text-right">Revenue</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loadingPlans ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                        Loading plans...
                      </TableCell>
                    </TableRow>
                  ) : (
                    sortedPlans.map((plan) => {
                      const tenantCount = getTenantCount(plan.name);
                      return (
                        <TableRow key={plan.id}>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Badge className={getPlanColor(plan.name)}>
                                {plan.displayName}
                              </Badge>
                            </div>
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            Pricing managed via providers
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            -
                          </TableCell>
                          <TableCell className="text-right">-</TableCell>
                          <TableCell className="text-right">{tenantCount}</TableCell>
                          <TableCell className="text-right font-medium text-green-600">
                            -
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
              <div className="mt-4 p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground">
                  Pricing is managed through Stripe. To modify pricing, update the
                  corresponding products in your Stripe dashboard. Changes will be reflected
                  automatically for new subscribers.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit Plan Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="capitalize">Edit {selectedPlan} Plan</DialogTitle>
            <DialogDescription>
              Configure feature limits and settings for this plan
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Plan Name</Label>
              <Input value={selectedPlan || ''} disabled className="capitalize" />
            </div>
            <div className="space-y-4">
              <Label>Feature Limits</Label>
              {selectedPlan && matrix && matrix.features
                .filter((f) => f.featureType === 'limit')
                .slice(0, 3)
                .map((feature) => {
                  const value = feature.planValues[selectedPlan];
                  return (
                    <div key={feature.featureId} className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">{feature.featureDisplayName}</p>
                        <p className="text-xs text-muted-foreground font-mono">{feature.featureKey}</p>
                      </div>
                      <Input
                        className="w-24"
                        value={getPlanDisplayValue(value)}
                        disabled
                      />
                    </div>
                  );
                })}
            </div>
            <div className="space-y-4 pt-4 border-t">
              <Label>Feature Toggles</Label>
              {selectedPlan && matrix && matrix.features
                .filter((f) => f.featureType === 'flag')
                .slice(0, 5)
                .map((feature) => {
                  const value = feature.planValues[selectedPlan];
                  return (
                    <div key={feature.featureId} className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">{feature.featureDisplayName}</p>
                        <p className="text-xs text-muted-foreground font-mono">{feature.featureKey}</p>
                      </div>
                      <Switch
                        checked={!!value}
                        disabled
                      />
                    </div>
                  );
                })}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button asChild>
              <Link to="/admin/entitlements/matrix">
                Edit in Feature Matrix
              </Link>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
