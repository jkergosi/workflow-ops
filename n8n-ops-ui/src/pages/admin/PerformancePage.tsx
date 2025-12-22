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
  Cpu,
  HardDrive,
  Activity,
  Clock,
  Server,
  AlertTriangle,
  CheckCircle,
  Zap,
} from 'lucide-react';

interface SystemMetric {
  label: string;
  value: string;
  status: 'healthy' | 'warning' | 'critical';
  icon: React.ComponentType<{ className?: string }>;
}

interface EndpointMetric {
  endpoint: string;
  method: string;
  avgLatency: number;
  p95Latency: number;
  requestsPerMin: number;
  errorRate: number;
}

const systemMetrics: SystemMetric[] = [
  { label: 'CPU Usage', value: '42%', status: 'healthy', icon: Cpu },
  { label: 'Memory Usage', value: '68%', status: 'warning', icon: HardDrive },
  { label: 'API Latency (avg)', value: '145ms', status: 'healthy', icon: Clock },
  { label: 'Active Connections', value: '234', status: 'healthy', icon: Activity },
];

const endpointMetrics: EndpointMetric[] = [
  {
    endpoint: '/api/v1/workflows',
    method: 'GET',
    avgLatency: 120,
    p95Latency: 250,
    requestsPerMin: 450,
    errorRate: 0.1,
  },
  {
    endpoint: '/api/v1/environments/sync',
    method: 'POST',
    avgLatency: 2500,
    p95Latency: 5000,
    requestsPerMin: 15,
    errorRate: 2.5,
  },
  {
    endpoint: '/api/v1/executions',
    method: 'GET',
    avgLatency: 85,
    p95Latency: 180,
    requestsPerMin: 320,
    errorRate: 0.2,
  },
  {
    endpoint: '/api/v1/workflows/upload',
    method: 'POST',
    avgLatency: 450,
    p95Latency: 1200,
    requestsPerMin: 25,
    errorRate: 1.8,
  },
  {
    endpoint: '/api/v1/auth/login',
    method: 'POST',
    avgLatency: 180,
    p95Latency: 350,
    requestsPerMin: 85,
    errorRate: 5.2,
  },
];

const recentAlerts = [
  {
    id: '1',
    type: 'warning',
    message: 'High memory usage detected (>65%)',
    time: '5 minutes ago',
  },
  {
    id: '2',
    type: 'info',
    message: 'Scheduled maintenance completed successfully',
    time: '2 hours ago',
  },
  {
    id: '3',
    type: 'error',
    message: 'Database connection timeout - auto-recovered',
    time: '4 hours ago',
  },
  {
    id: '4',
    type: 'info',
    message: 'API rate limit increased for enterprise tenants',
    time: '1 day ago',
  },
];

export function PerformancePage() {
  useEffect(() => {
    document.title = 'Performance - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-green-600';
      case 'warning':
        return 'text-yellow-600';
      case 'critical':
        return 'text-red-600';
      default:
        return 'text-muted-foreground';
    }
  };

  const getStatusBg = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-100 dark:bg-green-900/30';
      case 'warning':
        return 'bg-yellow-100 dark:bg-yellow-900/30';
      case 'critical':
        return 'bg-red-100 dark:bg-red-900/30';
      default:
        return 'bg-muted';
    }
  };

  const getLatencyColor = (latency: number) => {
    if (latency < 200) return 'text-green-600';
    if (latency < 500) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getErrorRateColor = (rate: number) => {
    if (rate < 1) return 'text-green-600';
    if (rate < 5) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'error':
        return <AlertTriangle className="h-4 w-4 text-red-600" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-600" />;
      default:
        return <CheckCircle className="h-4 w-4 text-blue-600" />;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Performance</h1>
        <p className="text-muted-foreground">Monitor system health and API performance</p>
      </div>

      {/* System Health */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {systemMetrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <Card key={metric.label}>
              <CardContent className="pt-6">
                <div className="flex items-center gap-4">
                  <div className={`p-3 rounded-lg ${getStatusBg(metric.status)}`}>
                    <Icon className={`h-6 w-6 ${getStatusColor(metric.status)}`} />
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">{metric.label}</p>
                    <p className="text-2xl font-bold">{metric.value}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* API Endpoints */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              API Endpoint Performance
            </CardTitle>
            <CardDescription>Response times and error rates by endpoint</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Endpoint</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead className="text-right">Avg Latency</TableHead>
                  <TableHead className="text-right">P95 Latency</TableHead>
                  <TableHead className="text-right">Req/min</TableHead>
                  <TableHead className="text-right">Error Rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {endpointMetrics.map((endpoint, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-mono text-sm">{endpoint.endpoint}</TableCell>
                    <TableCell>
                      <Badge variant={endpoint.method === 'GET' ? 'secondary' : 'default'}>
                        {endpoint.method}
                      </Badge>
                    </TableCell>
                    <TableCell className={`text-right ${getLatencyColor(endpoint.avgLatency)}`}>
                      {endpoint.avgLatency}ms
                    </TableCell>
                    <TableCell className={`text-right ${getLatencyColor(endpoint.p95Latency)}`}>
                      {endpoint.p95Latency}ms
                    </TableCell>
                    <TableCell className="text-right">{endpoint.requestsPerMin}</TableCell>
                    <TableCell className={`text-right ${getErrorRateColor(endpoint.errorRate)}`}>
                      {endpoint.errorRate}%
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Recent Alerts */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Recent Alerts
            </CardTitle>
            <CardDescription>System notifications and events</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentAlerts.map((alert) => (
                <div key={alert.id} className="flex gap-3 p-3 rounded-lg bg-muted/50">
                  {getAlertIcon(alert.type)}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">{alert.message}</p>
                    <p className="text-xs text-muted-foreground mt-1">{alert.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Infrastructure Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            Infrastructure Overview
          </CardTitle>
          <CardDescription>Current system resource utilization</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-3">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Database Connections</span>
                <span className="text-sm text-muted-foreground">45 / 100</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-green-500 rounded-full" style={{ width: '45%' }} />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Redis Cache Usage</span>
                <span className="text-sm text-muted-foreground">2.4GB / 4GB</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-yellow-500 rounded-full" style={{ width: '60%' }} />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">File Storage</span>
                <span className="text-sm text-muted-foreground">85GB / 500GB</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-green-500 rounded-full" style={{ width: '17%' }} />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
