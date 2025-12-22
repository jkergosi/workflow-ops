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

interface PlanFeature {
  key: string;
  name: string;
  description: string;
  free: boolean | number | string;
  pro: boolean | number | string;
  agency: boolean | number | string;
  enterprise: boolean | number | string;
}

// Plan features definition - ties into the feature matrix
const planFeatures: PlanFeature[] = [
  {
    key: 'max_environments',
    name: 'Environments',
    description: 'Number of N8N instances',
    free: 1,
    pro: 3,
    agency: 10,
    enterprise: 'Unlimited',
  },
  {
    key: 'max_workflows',
    name: 'Workflows',
    description: 'Total workflows across environments',
    free: 10,
    pro: 100,
    agency: 500,
    enterprise: 'Unlimited',
  },
  {
    key: 'max_team_members',
    name: 'Team Members',
    description: 'Users in your organization',
    free: 2,
    pro: 10,
    agency: 50,
    enterprise: 'Unlimited',
  },
  {
    key: 'github_backup',
    name: 'GitHub Backup',
    description: 'Automatic workflow backup to Git',
    free: false,
    pro: true,
    agency: true,
    enterprise: true,
  },
  {
    key: 'environment_promotion',
    name: 'Environment Promotion',
    description: 'Promote workflows between environments',
    free: false,
    pro: true,
    agency: true,
    enterprise: true,
  },
  {
    key: 'scheduled_backup',
    name: 'Scheduled Backup',
    description: 'Automatic scheduled backups',
    free: false,
    pro: true,
    agency: true,
    enterprise: true,
  },
  {
    key: 'observability',
    name: 'Observability',
    description: 'Execution analytics and monitoring',
    free: false,
    pro: true,
    agency: true,
    enterprise: true,
  },
  {
    key: 'custom_gates',
    name: 'Custom Gates',
    description: 'Custom promotion gates and approvals',
    free: false,
    pro: false,
    agency: true,
    enterprise: true,
  },
  {
    key: 'audit_logs',
    name: 'Audit Logs',
    description: 'Detailed activity logging',
    free: false,
    pro: false,
    agency: true,
    enterprise: true,
  },
  {
    key: 'sso',
    name: 'SSO/SAML',
    description: 'Single Sign-On integration',
    free: false,
    pro: false,
    agency: false,
    enterprise: true,
  },
  {
    key: 'dedicated_support',
    name: 'Dedicated Support',
    description: 'Priority support with SLA',
    free: false,
    pro: false,
    agency: false,
    enterprise: true,
  },
  {
    key: 'custom_contracts',
    name: 'Custom Contracts',
    description: 'Custom terms and invoicing',
    free: false,
    pro: false,
    agency: false,
    enterprise: true,
  },
];

const planPricing = {
  free: { monthly: 0, annual: 0 },
  pro: { monthly: 49, annual: 490 },
  agency: { monthly: 199, annual: 1990 },
  enterprise: { monthly: 'Custom', annual: 'Custom' },
};

export function PlansPage() {
  useEffect(() => {
    document.title = 'Plans - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);

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

  const getTenantCount = (plan: string) => {
    const item = distribution.find((d: any) => d.plan === plan);
    return item?.count || 0;
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
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {(['free', 'pro', 'agency', 'enterprise'] as const).map((plan) => (
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
                  <CardTitle className="capitalize">{plan}</CardTitle>
                  <CardDescription>
                    {plan === 'free' && 'Get started for free'}
                    {plan === 'pro' && 'For growing teams'}
                    {plan === 'agency' && 'For agencies and large teams'}
                    {plan === 'enterprise' && 'For large organizations'}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="text-3xl font-bold">
                    {typeof planPricing[plan].monthly === 'number'
                      ? `$${planPricing[plan].monthly}`
                      : planPricing[plan].monthly}
                    {typeof planPricing[plan].monthly === 'number' && (
                      <span className="text-sm font-normal text-muted-foreground">/mo</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm">
                      {getTenantCount(plan)} tenants
                    </span>
                  </div>
                  <div className="space-y-2 pt-4 border-t">
                    <p className="text-sm font-medium">Key Features:</p>
                    <ul className="text-sm space-y-1 text-muted-foreground">
                      <li className="flex items-center gap-2">
                        <Check className="h-3 w-3 text-green-500" />
                        {planFeatures.find((f) => f.key === 'max_environments')?.[plan]} environment(s)
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-3 w-3 text-green-500" />
                        {planFeatures.find((f) => f.key === 'max_workflows')?.[plan]} workflows
                      </li>
                      <li className="flex items-center gap-2">
                        <Check className="h-3 w-3 text-green-500" />
                        {planFeatures.find((f) => f.key === 'max_team_members')?.[plan]} team members
                      </li>
                      {plan !== 'free' && (
                        <li className="flex items-center gap-2">
                          <Check className="h-3 w-3 text-green-500" />
                          GitHub backup
                        </li>
                      )}
                    </ul>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
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
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[300px]">Feature</TableHead>
                    <TableHead className="text-center">Free</TableHead>
                    <TableHead className="text-center">Pro</TableHead>
                    <TableHead className="text-center">Agency</TableHead>
                    <TableHead className="text-center">Enterprise</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {planFeatures.map((feature) => (
                    <TableRow key={feature.key}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{feature.name}</p>
                          <p className="text-sm text-muted-foreground">{feature.description}</p>
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        {renderFeatureValue(feature.free)}
                      </TableCell>
                      <TableCell className="text-center">
                        {renderFeatureValue(feature.pro)}
                      </TableCell>
                      <TableCell className="text-center">
                        {renderFeatureValue(feature.agency)}
                      </TableCell>
                      <TableCell className="text-center">
                        {renderFeatureValue(feature.enterprise)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
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
                  {(['free', 'pro', 'agency', 'enterprise'] as const).map((plan) => {
                    const tenantCount = getTenantCount(plan);
                    const monthlyPrice = typeof planPricing[plan].monthly === 'number'
                      ? planPricing[plan].monthly
                      : 0;
                    const annualPrice = typeof planPricing[plan].annual === 'number'
                      ? planPricing[plan].annual
                      : 0;
                    const savings = monthlyPrice > 0
                      ? Math.round(((monthlyPrice * 12 - annualPrice) / (monthlyPrice * 12)) * 100)
                      : 0;
                    const estimatedRevenue = tenantCount * monthlyPrice;

                    return (
                      <TableRow key={plan}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Badge className={getPlanColor(plan)}>
                              {plan.charAt(0).toUpperCase() + plan.slice(1)}
                            </Badge>
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {typeof planPricing[plan].monthly === 'number'
                            ? `$${planPricing[plan].monthly}`
                            : planPricing[plan].monthly}
                        </TableCell>
                        <TableCell className="text-right font-medium">
                          {typeof planPricing[plan].annual === 'number'
                            ? `$${planPricing[plan].annual}`
                            : planPricing[plan].annual}
                        </TableCell>
                        <TableCell className="text-right">
                          {savings > 0 ? (
                            <Badge variant="outline" className="text-green-600">
                              {savings}% off
                            </Badge>
                          ) : (
                            '-'
                          )}
                        </TableCell>
                        <TableCell className="text-right">{tenantCount}</TableCell>
                        <TableCell className="text-right font-medium text-green-600">
                          ${estimatedRevenue.toLocaleString()}/mo
                        </TableCell>
                      </TableRow>
                    );
                  })}
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
              {selectedPlan && planFeatures.slice(0, 3).map((feature) => (
                <div key={feature.key} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{feature.name}</p>
                    <p className="text-xs text-muted-foreground">{feature.description}</p>
                  </div>
                  <Input
                    className="w-24"
                    value={feature[selectedPlan as keyof typeof feature] as string}
                    disabled
                  />
                </div>
              ))}
            </div>
            <div className="space-y-4 pt-4 border-t">
              <Label>Feature Toggles</Label>
              {selectedPlan && planFeatures.slice(3).map((feature) => (
                <div key={feature.key} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{feature.name}</p>
                    <p className="text-xs text-muted-foreground">{feature.description}</p>
                  </div>
                  <Switch
                    checked={!!feature[selectedPlan as keyof typeof feature]}
                    disabled
                  />
                </div>
              ))}
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
