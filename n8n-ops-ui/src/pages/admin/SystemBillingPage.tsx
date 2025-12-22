// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
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
  CreditCard,
  DollarSign,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  Calendar,
  Building2,
  RefreshCw,
  AlertTriangle,
  ExternalLink,
  Download,
  Filter,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { Link } from 'react-router-dom';
import { exportToCSV } from '@/lib/export-utils';
import { toast } from 'sonner';
import type { BillingMetrics, PlanDistributionItem, RecentCharge, FailedPayment, DunningTenant } from '@/types';

export function SystemBillingPage() {
  useEffect(() => {
    document.title = 'System Billing - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  // Filter state
  const [showOnlyDunning, setShowOnlyDunning] = useState(false);
  const [transactionTypeFilter, setTransactionTypeFilter] = useState<string>('all');

  // Fetch billing metrics
  const { data: metricsData, isLoading: metricsLoading, refetch: refetchMetrics } = useQuery({
    queryKey: ['billing-metrics'],
    queryFn: () => apiClient.getBillingMetrics(),
  });

  // Fetch plan distribution
  const { data: distributionData, isLoading: distributionLoading } = useQuery({
    queryKey: ['plan-distribution'],
    queryFn: () => apiClient.getPlanDistribution(),
  });

  // Fetch recent charges
  const { data: chargesData, isLoading: chargesLoading } = useQuery({
    queryKey: ['recent-charges'],
    queryFn: () => apiClient.getRecentCharges(10),
  });

  // Fetch failed payments
  const { data: failedData } = useQuery({
    queryKey: ['failed-payments'],
    queryFn: () => apiClient.getFailedPayments(),
  });

  // Fetch dunning tenants
  const { data: dunningData } = useQuery({
    queryKey: ['dunning-tenants'],
    queryFn: () => apiClient.getDunningTenants(),
  });

  const metrics: BillingMetrics = metricsData?.data || {
    mrr: 0,
    arr: 0,
    totalSubscriptions: 0,
    activeSubscriptions: 0,
    trialSubscriptions: 0,
    churnRate: 0,
    avgRevenuePerUser: 0,
    mrrGrowth: 0,
  };

  const distribution: PlanDistributionItem[] = distributionData?.data || [];
  const recentCharges: RecentCharge[] = chargesData?.data || [];
  const failedPayments: FailedPayment[] = failedData?.data || [];
  const dunningTenants: DunningTenant[] = dunningData?.data || [];

  const isLoading = metricsLoading || distributionLoading || chargesLoading;

  // Filter transactions by type
  const filteredCharges = recentCharges.filter(charge => {
    if (transactionTypeFilter === 'all') return true;
    return charge.type === transactionTypeFilter;
  });

  // Export functions
  const handleExportTransactions = () => {
    if (filteredCharges.length === 0) {
      toast.error('No transactions to export');
      return;
    }

    const columns = [
      { key: 'id' as const, header: 'Transaction ID' },
      { key: 'tenantId' as const, header: 'Tenant ID' },
      { key: 'tenantName' as const, header: 'Tenant Name' },
      { key: 'type' as const, header: 'Type' },
      { key: 'amount' as const, header: 'Amount' },
      { key: 'status' as const, header: 'Status' },
      { key: 'createdAt' as const, header: 'Date' },
    ];

    let filename = 'billing-transactions';
    if (transactionTypeFilter !== 'all') filename += `_${transactionTypeFilter}`;

    exportToCSV(filteredCharges, columns, filename);
    toast.success(`Exported ${filteredCharges.length} transactions to CSV`);
  };

  const handleExportDunning = () => {
    if (dunningTenants.length === 0) {
      toast.error('No dunning tenants to export');
      return;
    }

    const columns = [
      { key: 'tenantId' as const, header: 'Tenant ID' },
      { key: 'tenantName' as const, header: 'Tenant Name' },
      { key: 'amountDue' as const, header: 'Amount Due' },
      { key: 'dueDate' as const, header: 'Due Date' },
      { key: 'retryCount' as const, header: 'Retry Count' },
      { key: 'status' as const, header: 'Status' },
    ];

    exportToCSV(dunningTenants, columns, 'dunning-tenants');
    toast.success(`Exported ${dunningTenants.length} dunning tenants to CSV`);
  };

  const handleExportFailedPayments = () => {
    if (failedPayments.length === 0) {
      toast.error('No failed payments to export');
      return;
    }

    const columns = [
      { key: 'id' as const, header: 'Payment ID' },
      { key: 'tenantId' as const, header: 'Tenant ID' },
      { key: 'tenantName' as const, header: 'Tenant Name' },
      { key: 'amount' as const, header: 'Amount' },
      { key: 'failureReason' as const, header: 'Error Message' },
      { key: 'createdAt' as const, header: 'Failed At' },
    ];

    exportToCSV(failedPayments, columns, 'failed-payments');
    toast.success(`Exported ${failedPayments.length} failed payments to CSV`);
  };

  const getTypeBadgeVariant = (type: string) => {
    switch (type) {
      case 'upgrade':
        return 'default';
      case 'refund':
        return 'destructive';
      case 'subscription':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'succeeded':
      case 'completed':
        return 'success';
      case 'failed':
        return 'destructive';
      case 'pending':
        return 'outline';
      default:
        return 'outline';
    }
  };

  // Calculate plan distribution percentages
  const totalTenants = distribution.reduce((sum, d) => sum + (d.count || 0), 0);
  const getPlanPercentage = (count: number) => totalTenants > 0 ? Math.round((count / totalTenants) * 100) : 0;

  // Calculate estimated revenue by plan
  const planPrices: Record<string, number> = { free: 0, pro: 49, agency: 199, enterprise: 499 };
  const getEstimatedRevenue = (plan: string, count: number) => (planPrices[plan] || 0) * count;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">System Billing</h1>
          <p className="text-muted-foreground">Monitor revenue and billing across all tenants</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetchMetrics()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" onClick={handleExportTransactions} disabled={filteredCharges.length === 0}>
            <Download className="h-4 w-4 mr-2" />
            Export Transactions
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-8">Loading billing data...</div>
      ) : (
        <>
          {/* Revenue Metrics */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Monthly Recurring Revenue</p>
                    <p className="text-2xl font-bold mt-1">${metrics.mrr?.toLocaleString() || 0}</p>
                  </div>
                  <div className={`flex items-center gap-1 text-sm ${(metrics.mrrGrowth || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {(metrics.mrrGrowth || 0) >= 0 ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <TrendingDown className="h-4 w-4" />
                    )}
                    {Math.abs(metrics.mrrGrowth || 0).toFixed(1)}%
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Annual Recurring Revenue</p>
                    <p className="text-2xl font-bold mt-1">${metrics.arr?.toLocaleString() || 0}</p>
                  </div>
                  <DollarSign className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Average Revenue Per User</p>
                    <p className="text-2xl font-bold mt-1">${metrics.avgRevenuePerUser?.toFixed(0) || 0}</p>
                  </div>
                  <TrendingUp className="h-8 w-8 text-green-500" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Churn Rate</p>
                    <p className="text-2xl font-bold mt-1">{metrics.churnRate?.toFixed(1) || 0}%</p>
                  </div>
                  <div className={`flex items-center gap-1 text-sm ${(metrics.churnRate || 0) <= 5 ? 'text-green-600' : 'text-red-600'}`}>
                    {(metrics.churnRate || 0) <= 5 ? (
                      <TrendingDown className="h-4 w-4" />
                    ) : (
                      <TrendingUp className="h-4 w-4" />
                    )}
                    {(metrics.churnRate || 0) <= 5 ? 'Good' : 'High'}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Alerts Section */}
          {(failedPayments.length > 0 || dunningTenants.length > 0) && (
            <Card className="border-amber-500">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-amber-600">
                      <AlertTriangle className="h-5 w-5" />
                      Payment Alerts
                    </CardTitle>
                    <CardDescription>Action required on these billing issues</CardDescription>
                  </div>
                  <div className="flex gap-2">
                    {failedPayments.length > 0 && (
                      <Button variant="outline" size="sm" onClick={handleExportFailedPayments}>
                        <Download className="h-4 w-4 mr-1" />
                        Export Failed
                      </Button>
                    )}
                    {dunningTenants.length > 0 && (
                      <Button variant="outline" size="sm" onClick={handleExportDunning}>
                        <Download className="h-4 w-4 mr-1" />
                        Export Dunning
                      </Button>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {failedPayments.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">Failed Payments ({failedPayments.length})</p>
                    <div className="space-y-2">
                      {failedPayments.slice(0, 3).map((payment) => (
                        <div key={payment.id} className="flex items-center justify-between p-2 bg-red-50 dark:bg-red-950/50 rounded">
                          <div>
                            <p className="font-medium">{payment.tenantName}</p>
                            <p className="text-sm text-muted-foreground">{payment.failureReason}</p>
                          </div>
                          <div className="text-right">
                            <p className="font-medium text-red-600">${payment.amount}</p>
                            <p className="text-xs text-muted-foreground">
                              {new Date(payment.createdAt).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {dunningTenants.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">Dunning ({dunningTenants.length})</p>
                    <div className="space-y-2">
                      {dunningTenants.slice(0, 3).map((tenant) => (
                        <div key={tenant.tenantId} className="flex items-center justify-between p-2 bg-amber-50 dark:bg-amber-950/50 rounded">
                          <div>
                            <Link
                              to={`/admin/tenants/${tenant.tenantId}`}
                              className="font-medium hover:underline flex items-center gap-1"
                            >
                              {tenant.tenantName}
                              <ExternalLink className="h-3 w-3" />
                            </Link>
                            <p className="text-sm text-muted-foreground">
                              {tenant.retryCount} retry attempts
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="font-medium text-amber-600">${tenant.amountDue}</p>
                            <p className="text-xs text-muted-foreground">
                              Due {(tenant.dueDate ? new Date(tenant.dueDate).toLocaleDateString() : '-')}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <div className="grid gap-6 lg:grid-cols-3">
            {/* Plan Distribution */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5" />
                  Plan Distribution
                </CardTitle>
                <CardDescription>Breakdown of tenants by subscription plan</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {['free', 'pro', 'agency', 'enterprise'].map((plan) => {
                  const planData = distribution.find((d) => (d.plan || d.planName) === plan);
                  const count = planData?.count || 0;
                  const percentage = getPlanPercentage(count);
                  const colorClass = {
                    free: 'bg-gray-400',
                    pro: 'bg-blue-500',
                    agency: 'bg-purple-500',
                    enterprise: 'bg-amber-500',
                  }[plan];

                  return (
                    <div key={plan} className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge variant={plan === 'free' ? 'outline' : plan === 'pro' ? 'secondary' : 'default'} className="capitalize">
                            {plan}
                          </Badge>
                          <span className="text-sm text-muted-foreground">
                            {count} tenants
                          </span>
                        </div>
                        <span className="font-medium">{percentage}%</span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full ${colorClass} rounded-full transition-all duration-500`}
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>

            {/* Revenue Summary */}
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5" />
                  Revenue Summary
                </CardTitle>
                <CardDescription>Monthly revenue breakdown by plan</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    {['free', 'pro', 'agency', 'enterprise'].map((plan) => {
                      const planData = distribution.find((d) => (d.plan || d.planName) === plan);
                      const count = planData?.count || 0;
                      const revenue = getEstimatedRevenue(plan, count);
                      const bgClass = {
                        free: 'bg-muted/50',
                        pro: 'bg-blue-50 dark:bg-blue-950',
                        agency: 'bg-purple-50 dark:bg-purple-950',
                        enterprise: 'bg-amber-50 dark:bg-amber-950',
                      }[plan];

                      return (
                        <div key={plan} className={`p-4 rounded-lg ${bgClass}`}>
                          <p className="text-sm text-muted-foreground capitalize">{plan} Tier</p>
                          <p className="text-xl font-bold">${revenue.toLocaleString()}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {count} tenants × ${planPrices[plan]}/mo
                          </p>
                        </div>
                      );
                    })}
                  </div>

                  <div className="pt-4 border-t">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">Total Monthly Revenue</p>
                        <p className="text-3xl font-bold">${metrics.mrr?.toLocaleString() || 0}</p>
                      </div>
                      <div className="flex items-center gap-1 text-green-600">
                        <ArrowUpRight className="h-5 w-5" />
                        <span className="font-medium">+{metrics.mrrGrowth?.toFixed(1) || 0}% vs last month</span>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent Transactions */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <CreditCard className="h-5 w-5" />
                    Recent Transactions
                  </CardTitle>
                  <CardDescription>Latest billing activity across all tenants</CardDescription>
                </div>
                <div className="flex items-center gap-4">
                  {/* Dunning Filter Toggle */}
                  <div className="flex items-center gap-2">
                    <Switch
                      id="dunning-filter"
                      checked={showOnlyDunning}
                      onCheckedChange={setShowOnlyDunning}
                    />
                    <Label htmlFor="dunning-filter" className="text-sm cursor-pointer">
                      Show Dunning Only
                    </Label>
                  </div>
                  {/* Transaction Type Filter */}
                  <Select value={transactionTypeFilter} onValueChange={setTransactionTypeFilter}>
                    <SelectTrigger className="w-[150px]">
                      <Filter className="h-4 w-4 mr-2" />
                      <SelectValue placeholder="Type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="subscription">Subscription</SelectItem>
                      <SelectItem value="upgrade">Upgrade</SelectItem>
                      <SelectItem value="refund">Refund</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button variant="outline" size="sm" asChild>
                    <Link to="/admin/plans">
                      View Plans
                    </Link>
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {filteredCharges.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  {transactionTypeFilter !== 'all' ? 'No transactions match the selected filter' : 'No recent transactions'}
                </div>
              ) : showOnlyDunning ? (
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    Showing {dunningTenants.length} tenants in dunning status
                  </p>
                  {dunningTenants.length === 0 ? (
                    <div className="text-center py-4 text-muted-foreground">No tenants in dunning</div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Tenant</TableHead>
                          <TableHead>Amount Due</TableHead>
                          <TableHead>Due Date</TableHead>
                          <TableHead>Retry Count</TableHead>
                          <TableHead>Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {dunningTenants.map((tenant) => (
                          <TableRow key={tenant.tenantId}>
                            <TableCell>
                              <Link
                                to={`/admin/tenants/${tenant.tenantId}`}
                                className="font-medium hover:underline flex items-center gap-1"
                              >
                                {tenant.tenantName}
                                <ExternalLink className="h-3 w-3" />
                              </Link>
                            </TableCell>
                            <TableCell className="text-amber-600 font-medium">
                              ${tenant.amountDue?.toFixed(2) || '0.00'}
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {tenant.dueDate ? (tenant.dueDate ? new Date(tenant.dueDate).toLocaleDateString() : '-') : '-'}
                            </TableCell>
                            <TableCell>
                              <Badge variant={(tenant.retryCount || 0) >= 3 ? 'destructive' : 'secondary'}>
                                {tenant.retryCount} retries
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline" className="text-amber-600 border-amber-500">
                                {tenant.status || 'Dunning'}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Tenant</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Date</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {recentCharges.map((tx) => (
                      <TableRow key={tx.id}>
                        <TableCell>
                          <Link
                            to={`/admin/tenants/${tx.tenantId}`}
                            className="font-medium hover:underline"
                          >
                            {tx.tenantName}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <Badge variant={getTypeBadgeVariant(tx.type || 'other')} className="capitalize">
                            {tx.type}
                          </Badge>
                        </TableCell>
                        <TableCell
                          className={tx.amount < 0 ? 'text-red-600' : 'text-green-600'}
                        >
                          {tx.amount < 0 ? '-' : '+'}${Math.abs(tx.amount).toFixed(2)}
                        </TableCell>
                        <TableCell>
                          <Badge variant={getStatusBadgeVariant(tx.status)} className="capitalize">
                            {tx.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          <div className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {new Date(tx.createdAt).toLocaleDateString()}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          {/* Subscription Stats */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center">
                    <CreditCard className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{metrics.activeSubscriptions || 0}</p>
                    <p className="text-sm text-muted-foreground">Active Subscriptions</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                    <Calendar className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{metrics.trialSubscriptions || 0}</p>
                    <p className="text-sm text-muted-foreground">Trial Subscriptions</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-purple-100 flex items-center justify-center">
                    <Building2 className="h-5 w-5 text-purple-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{metrics.totalSubscriptions || 0}</p>
                    <p className="text-sm text-muted-foreground">Total Subscriptions</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
