import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  FileText,
  Search,
  Download,
  User,
  Clock,
  Activity,
  Shield,
  Settings,
  Workflow,
} from 'lucide-react';

interface AuditLog {
  id: string;
  timestamp: string;
  user: string;
  userEmail: string;
  tenant: string;
  action: string;
  resource: string;
  resourceId: string;
  details: string;
  ipAddress: string;
  category: 'auth' | 'workflow' | 'settings' | 'billing' | 'admin';
}

const mockAuditLogs: AuditLog[] = [
  {
    id: '1',
    timestamp: '2024-03-15T14:32:00Z',
    user: 'John Doe',
    userEmail: 'john@acme.com',
    tenant: 'Acme Corp',
    action: 'workflow.create',
    resource: 'Workflow',
    resourceId: 'wf_abc123',
    details: 'Created workflow "Order Processing"',
    ipAddress: '192.168.1.100',
    category: 'workflow',
  },
  {
    id: '2',
    timestamp: '2024-03-15T14:28:00Z',
    user: 'Jane Smith',
    userEmail: 'jane@techstart.io',
    tenant: 'TechStart Inc',
    action: 'auth.login',
    resource: 'Session',
    resourceId: 'sess_xyz789',
    details: 'User logged in successfully',
    ipAddress: '10.0.0.45',
    category: 'auth',
  },
  {
    id: '3',
    timestamp: '2024-03-15T14:15:00Z',
    user: 'Admin',
    userEmail: 'admin@system.local',
    tenant: 'System',
    action: 'tenant.update',
    resource: 'Tenant',
    resourceId: 'tenant_acme',
    details: 'Updated subscription plan to Enterprise',
    ipAddress: '192.168.1.1',
    category: 'admin',
  },
  {
    id: '4',
    timestamp: '2024-03-15T13:55:00Z',
    user: 'Mike Johnson',
    userEmail: 'mike@devshop.dev',
    tenant: 'DevShop',
    action: 'settings.update',
    resource: 'Environment',
    resourceId: 'env_prod',
    details: 'Modified production environment settings',
    ipAddress: '172.16.0.22',
    category: 'settings',
  },
  {
    id: '5',
    timestamp: '2024-03-15T13:42:00Z',
    user: 'Sarah Brown',
    userEmail: 'sarah@cloudnine.io',
    tenant: 'CloudNine',
    action: 'billing.upgrade',
    resource: 'Subscription',
    resourceId: 'sub_def456',
    details: 'Upgraded from Pro to Enterprise plan',
    ipAddress: '192.168.2.88',
    category: 'billing',
  },
  {
    id: '6',
    timestamp: '2024-03-15T13:30:00Z',
    user: 'John Doe',
    userEmail: 'john@acme.com',
    tenant: 'Acme Corp',
    action: 'workflow.delete',
    resource: 'Workflow',
    resourceId: 'wf_old123',
    details: 'Deleted workflow "Legacy Import"',
    ipAddress: '192.168.1.100',
    category: 'workflow',
  },
  {
    id: '7',
    timestamp: '2024-03-15T12:15:00Z',
    user: 'Admin',
    userEmail: 'admin@system.local',
    tenant: 'System',
    action: 'user.create',
    resource: 'User',
    resourceId: 'user_new789',
    details: 'Created new admin user',
    ipAddress: '192.168.1.1',
    category: 'admin',
  },
  {
    id: '8',
    timestamp: '2024-03-15T11:45:00Z',
    user: 'Jane Smith',
    userEmail: 'jane@techstart.io',
    tenant: 'TechStart Inc',
    action: 'auth.logout',
    resource: 'Session',
    resourceId: 'sess_abc456',
    details: 'User logged out',
    ipAddress: '10.0.0.45',
    category: 'auth',
  },
];

export function AuditLogsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  const filteredLogs = mockAuditLogs.filter((log) => {
    const matchesSearch =
      log.user.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.details.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.tenant.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesCategory = categoryFilter === 'all' || log.category === categoryFilter;

    return matchesSearch && matchesCategory;
  });

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'auth':
        return <Shield className="h-4 w-4" />;
      case 'workflow':
        return <Workflow className="h-4 w-4" />;
      case 'settings':
        return <Settings className="h-4 w-4" />;
      case 'billing':
        return <Activity className="h-4 w-4" />;
      case 'admin':
        return <User className="h-4 w-4" />;
      default:
        return <FileText className="h-4 w-4" />;
    }
  };

  const getCategoryBadgeVariant = (category: string) => {
    switch (category) {
      case 'auth':
        return 'default';
      case 'workflow':
        return 'secondary';
      case 'billing':
        return 'outline';
      case 'admin':
        return 'destructive';
      default:
        return 'outline';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return {
      date: date.toLocaleDateString(),
      time: date.toLocaleTimeString(),
    };
  };

  const categories = [
    { value: 'all', label: 'All Categories' },
    { value: 'auth', label: 'Authentication' },
    { value: 'workflow', label: 'Workflows' },
    { value: 'settings', label: 'Settings' },
    { value: 'billing', label: 'Billing' },
    { value: 'admin', label: 'Admin' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Audit Logs</h1>
          <p className="text-muted-foreground">Track all system activity and user actions</p>
        </div>
        <Button variant="outline">
          <Download className="h-4 w-4 mr-2" />
          Export Logs
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <FileText className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">{mockAuditLogs.length}</p>
                <p className="text-sm text-muted-foreground">Total Events</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Shield className="h-8 w-8 text-blue-500" />
              <div>
                <p className="text-2xl font-bold">
                  {mockAuditLogs.filter((l) => l.category === 'auth').length}
                </p>
                <p className="text-sm text-muted-foreground">Auth Events</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Workflow className="h-8 w-8 text-green-500" />
              <div>
                <p className="text-2xl font-bold">
                  {mockAuditLogs.filter((l) => l.category === 'workflow').length}
                </p>
                <p className="text-sm text-muted-foreground">Workflow Events</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <User className="h-8 w-8 text-red-500" />
              <div>
                <p className="text-2xl font-bold">
                  {mockAuditLogs.filter((l) => l.category === 'admin').length}
                </p>
                <p className="text-sm text-muted-foreground">Admin Events</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Logs Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Activity Log
              </CardTitle>
              <CardDescription>Detailed log of all system events</CardDescription>
            </div>
            <div className="flex items-center gap-3">
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search logs..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="flex h-9 rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {categories.map((cat) => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Tenant</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Details</TableHead>
                <TableHead>IP Address</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredLogs.map((log) => {
                const { date, time } = formatTimestamp(log.timestamp);
                return (
                  <TableRow key={log.id}>
                    <TableCell>
                      <div className="flex items-center gap-1 text-sm">
                        <Clock className="h-3 w-3 text-muted-foreground" />
                        <div>
                          <p>{date}</p>
                          <p className="text-xs text-muted-foreground">{time}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div>
                        <p className="font-medium">{log.user}</p>
                        <p className="text-xs text-muted-foreground">{log.userEmail}</p>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">{log.tenant}</TableCell>
                    <TableCell>
                      <Badge
                        variant={getCategoryBadgeVariant(log.category)}
                        className="capitalize flex items-center gap-1 w-fit"
                      >
                        {getCategoryIcon(log.category)}
                        {log.category}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <code className="text-xs bg-muted px-2 py-1 rounded">{log.action}</code>
                    </TableCell>
                    <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                      {log.details}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{log.ipAddress}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
