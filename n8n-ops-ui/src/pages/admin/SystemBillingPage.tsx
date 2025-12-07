import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  CreditCard,
  DollarSign,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  Calendar,
  Building2,
} from 'lucide-react';

interface RevenueMetric {
  label: string;
  value: string;
  change: number;
  trend: 'up' | 'down';
}

interface Transaction {
  id: string;
  tenant: string;
  type: 'subscription' | 'upgrade' | 'refund';
  amount: number;
  status: 'completed' | 'pending' | 'failed';
  date: string;
}

const revenueMetrics: RevenueMetric[] = [
  { label: 'Monthly Recurring Revenue', value: '$12,450', change: 12.5, trend: 'up' },
  { label: 'Annual Recurring Revenue', value: '$149,400', change: 8.2, trend: 'up' },
  { label: 'Average Revenue Per User', value: '$89', change: 3.1, trend: 'up' },
  { label: 'Churn Rate', value: '2.4%', change: 0.3, trend: 'down' },
];

const recentTransactions: Transaction[] = [
  {
    id: '1',
    tenant: 'Acme Corp',
    type: 'subscription',
    amount: 299,
    status: 'completed',
    date: '2024-03-15',
  },
  {
    id: '2',
    tenant: 'TechStart Inc',
    type: 'upgrade',
    amount: 150,
    status: 'completed',
    date: '2024-03-14',
  },
  {
    id: '3',
    tenant: 'DevShop',
    type: 'subscription',
    amount: 49,
    status: 'pending',
    date: '2024-03-14',
  },
  {
    id: '4',
    tenant: 'CloudNine',
    type: 'refund',
    amount: -99,
    status: 'completed',
    date: '2024-03-13',
  },
  {
    id: '5',
    tenant: 'DataFlow Inc',
    type: 'subscription',
    amount: 299,
    status: 'completed',
    date: '2024-03-12',
  },
];

const planDistribution = {
  free: { count: 45, percentage: 45 },
  pro: { count: 38, percentage: 38 },
  enterprise: { count: 17, percentage: 17 },
};

export function SystemBillingPage() {
  const getTypeBadgeVariant = (type: string) => {
    switch (type) {
      case 'upgrade':
        return 'default';
      case 'refund':
        return 'destructive';
      default:
        return 'secondary';
    }
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'destructive';
      default:
        return 'outline';
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">System Billing</h1>
        <p className="text-muted-foreground">Monitor revenue and billing across all tenants</p>
      </div>

      {/* Revenue Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {revenueMetrics.map((metric) => (
          <Card key={metric.label}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">{metric.label}</p>
                  <p className="text-2xl font-bold mt-1">{metric.value}</p>
                </div>
                <div
                  className={`flex items-center gap-1 text-sm ${
                    metric.trend === 'up' ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {metric.trend === 'up' ? (
                    <TrendingUp className="h-4 w-4" />
                  ) : (
                    <TrendingDown className="h-4 w-4" />
                  )}
                  {metric.change}%
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

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
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="outline">Free</Badge>
                  <span className="text-sm text-muted-foreground">
                    {planDistribution.free.count} tenants
                  </span>
                </div>
                <span className="font-medium">{planDistribution.free.percentage}%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-gray-400 rounded-full"
                  style={{ width: `${planDistribution.free.percentage}%` }}
                />
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">Pro</Badge>
                  <span className="text-sm text-muted-foreground">
                    {planDistribution.pro.count} tenants
                  </span>
                </div>
                <span className="font-medium">{planDistribution.pro.percentage}%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full"
                  style={{ width: `${planDistribution.pro.percentage}%` }}
                />
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="default">Enterprise</Badge>
                  <span className="text-sm text-muted-foreground">
                    {planDistribution.enterprise.count} tenants
                  </span>
                </div>
                <span className="font-medium">{planDistribution.enterprise.percentage}%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full"
                  style={{ width: `${planDistribution.enterprise.percentage}%` }}
                />
              </div>
            </div>
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
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-muted/50">
                  <p className="text-sm text-muted-foreground">Free Tier</p>
                  <p className="text-xl font-bold">$0</p>
                  <p className="text-xs text-muted-foreground mt-1">45 tenants</p>
                </div>
                <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-950">
                  <p className="text-sm text-muted-foreground">Pro Tier</p>
                  <p className="text-xl font-bold">$3,762</p>
                  <p className="text-xs text-muted-foreground mt-1">38 tenants × $99/mo</p>
                </div>
                <div className="p-4 rounded-lg bg-primary/10">
                  <p className="text-sm text-muted-foreground">Enterprise</p>
                  <p className="text-xl font-bold">$8,483</p>
                  <p className="text-xs text-muted-foreground mt-1">17 tenants × $499/mo avg</p>
                </div>
              </div>

              <div className="pt-4 border-t">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Monthly Revenue</p>
                    <p className="text-3xl font-bold">$12,245</p>
                  </div>
                  <div className="flex items-center gap-1 text-green-600">
                    <ArrowUpRight className="h-5 w-5" />
                    <span className="font-medium">+12.5% vs last month</span>
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
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            Recent Transactions
          </CardTitle>
          <CardDescription>Latest billing activity across all tenants</CardDescription>
        </CardHeader>
        <CardContent>
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
              {recentTransactions.map((tx) => (
                <TableRow key={tx.id}>
                  <TableCell className="font-medium">{tx.tenant}</TableCell>
                  <TableCell>
                    <Badge variant={getTypeBadgeVariant(tx.type)} className="capitalize">
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
                      {new Date(tx.date).toLocaleDateString()}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
