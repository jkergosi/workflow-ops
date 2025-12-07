import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Shield,
  Key,
  Lock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Plus,
  Trash2,
  Globe,
  Clock,
} from 'lucide-react';

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  lastUsed: string;
  created: string;
  scopes: string[];
}

interface SecurityEvent {
  id: string;
  type: 'success' | 'warning' | 'error';
  event: string;
  details: string;
  ip: string;
  timestamp: string;
}

const mockApiKeys: ApiKey[] = [
  {
    id: '1',
    name: 'Production API Key',
    prefix: 'n8n_prod_****',
    lastUsed: '2024-03-15T14:30:00Z',
    created: '2024-01-15',
    scopes: ['read', 'write', 'admin'],
  },
  {
    id: '2',
    name: 'CI/CD Integration',
    prefix: 'n8n_ci_****',
    lastUsed: '2024-03-15T10:00:00Z',
    created: '2024-02-01',
    scopes: ['read', 'write'],
  },
  {
    id: '3',
    name: 'Monitoring Service',
    prefix: 'n8n_mon_****',
    lastUsed: '2024-03-14T22:00:00Z',
    created: '2024-02-15',
    scopes: ['read'],
  },
];

const mockSecurityEvents: SecurityEvent[] = [
  {
    id: '1',
    type: 'warning',
    event: 'Failed login attempt',
    details: 'Multiple failed attempts for user admin@acme.com',
    ip: '192.168.1.100',
    timestamp: '2024-03-15T14:32:00Z',
  },
  {
    id: '2',
    type: 'success',
    event: 'API key rotated',
    details: 'Production API key was successfully rotated',
    ip: '10.0.0.1',
    timestamp: '2024-03-15T10:15:00Z',
  },
  {
    id: '3',
    type: 'error',
    event: 'Rate limit exceeded',
    details: 'IP 203.0.113.45 exceeded rate limit for /api/v1/workflows',
    ip: '203.0.113.45',
    timestamp: '2024-03-15T08:45:00Z',
  },
  {
    id: '4',
    type: 'success',
    event: 'New admin user created',
    details: 'User security@company.com granted admin access',
    ip: '10.0.0.1',
    timestamp: '2024-03-14T16:00:00Z',
  },
];

const securitySettings = {
  mfaRequired: true,
  sessionTimeout: 30,
  ipWhitelist: ['10.0.0.0/8', '192.168.0.0/16'],
  rateLimiting: {
    enabled: true,
    requestsPerMinute: 100,
  },
  passwordPolicy: {
    minLength: 12,
    requireUppercase: true,
    requireNumbers: true,
    requireSpecial: true,
  },
};

export function SecurityPage() {
  const [createKeyOpen, setCreateKeyOpen] = useState(false);
  const [keyForm, setKeyForm] = useState({
    name: '',
    scopes: [] as string[],
  });

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Shield className="h-4 w-4" />;
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Security</h1>
        <p className="text-muted-foreground">Manage API keys, access controls, and security settings</p>
      </div>

      {/* Security Overview */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900/30">
                <Shield className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Security Score</p>
                <p className="text-2xl font-bold">92/100</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
                <Key className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Active API Keys</p>
                <p className="text-2xl font-bold">{mockApiKeys.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-yellow-100 dark:bg-yellow-900/30">
                <AlertTriangle className="h-6 w-6 text-yellow-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Security Events</p>
                <p className="text-2xl font-bold">24</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900/30">
                <Lock className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">MFA Status</p>
                <p className="text-2xl font-bold">Enforced</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* API Keys */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Key className="h-5 w-5" />
                  API Keys
                </CardTitle>
                <CardDescription>Manage system API keys</CardDescription>
              </div>
              <Button size="sm" onClick={() => setCreateKeyOpen(true)}>
                <Plus className="h-4 w-4 mr-1" />
                Create Key
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {mockApiKeys.map((key) => (
              <div key={key.id} className="flex items-center justify-between p-4 rounded-lg border">
                <div>
                  <p className="font-medium">{key.name}</p>
                  <p className="text-sm text-muted-foreground font-mono">{key.prefix}</p>
                  <div className="flex items-center gap-2 mt-2">
                    {key.scopes.map((scope) => (
                      <Badge key={scope} variant="outline" className="text-xs">
                        {scope}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="icon" title="Rotate key">
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" title="Delete key">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Security Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="h-5 w-5" />
              Security Settings
            </CardTitle>
            <CardDescription>Configure security policies</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Multi-Factor Authentication</p>
                <p className="text-sm text-muted-foreground">Require MFA for all users</p>
              </div>
              <Badge variant={securitySettings.mfaRequired ? 'success' : 'outline'}>
                {securitySettings.mfaRequired ? 'Required' : 'Optional'}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Session Timeout</p>
                <p className="text-sm text-muted-foreground">Auto-logout after inactivity</p>
              </div>
              <span className="text-sm">{securitySettings.sessionTimeout} minutes</span>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Rate Limiting</p>
                <p className="text-sm text-muted-foreground">API request throttling</p>
              </div>
              <span className="text-sm">
                {securitySettings.rateLimiting.requestsPerMinute} req/min
              </span>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2">
                <Globe className="h-4 w-4 text-muted-foreground" />
                <p className="font-medium">IP Whitelist</p>
              </div>
              <div className="space-y-1">
                {securitySettings.ipWhitelist.map((ip) => (
                  <code key={ip} className="block text-sm bg-muted px-2 py-1 rounded">
                    {ip}
                  </code>
                ))}
              </div>
            </div>

            <div>
              <p className="font-medium mb-2">Password Policy</p>
              <div className="space-y-1 text-sm text-muted-foreground">
                <p>• Minimum {securitySettings.passwordPolicy.minLength} characters</p>
                {securitySettings.passwordPolicy.requireUppercase && (
                  <p>• At least one uppercase letter</p>
                )}
                {securitySettings.passwordPolicy.requireNumbers && (
                  <p>• At least one number</p>
                )}
                {securitySettings.passwordPolicy.requireSpecial && (
                  <p>• At least one special character</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Security Events */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Recent Security Events
          </CardTitle>
          <CardDescription>Monitor security-related activity</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Event</TableHead>
                <TableHead>Details</TableHead>
                <TableHead>IP Address</TableHead>
                <TableHead>Timestamp</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockSecurityEvents.map((event) => (
                <TableRow key={event.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {getEventIcon(event.type)}
                      <span className="font-medium">{event.event}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground max-w-md truncate">
                    {event.details}
                  </TableCell>
                  <TableCell className="font-mono text-sm">{event.ip}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {formatTimestamp(event.timestamp)}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Create API Key Dialog */}
      <Dialog open={createKeyOpen} onOpenChange={setCreateKeyOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Create API Key</DialogTitle>
            <DialogDescription>Generate a new API key for system access</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="key-name">Key Name</Label>
              <Input
                id="key-name"
                placeholder="Production API Key"
                value={keyForm.name}
                onChange={(e) => setKeyForm({ ...keyForm, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Scopes</Label>
              <div className="space-y-2">
                {['read', 'write', 'admin'].map((scope) => (
                  <label key={scope} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="rounded border-input"
                      checked={keyForm.scopes.includes(scope)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setKeyForm({ ...keyForm, scopes: [...keyForm.scopes, scope] });
                        } else {
                          setKeyForm({
                            ...keyForm,
                            scopes: keyForm.scopes.filter((s) => s !== scope),
                          });
                        }
                      }}
                    />
                    <span className="text-sm capitalize">{scope}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateKeyOpen(false)}>
              Cancel
            </Button>
            <Button>Create Key</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
