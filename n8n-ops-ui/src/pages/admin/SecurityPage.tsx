import { useMemo, useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Plus,
  Trash2,
  Clock,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  lastUsed?: string | null;
  created: string;
  scopes: string[];
  isActive: boolean;
}

interface SecurityEvent {
  id: string;
  type: 'success' | 'warning' | 'error';
  event: string;
  details: string;
  ip: string;
  timestamp: string;
}

export function SecurityPage() {
  useEffect(() => {
    document.title = 'Security - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);
  const queryClient = useQueryClient();
  const [createKeyOpen, setCreateKeyOpen] = useState(false);
  const [createdKeyOpen, setCreatedKeyOpen] = useState(false);
  const [createdKeyValue, setCreatedKeyValue] = useState('');
  const [keyForm, setKeyForm] = useState({
    name: '',
    scopes: [] as string[],
  });

  const { data: apiKeysResp, isLoading: apiKeysLoading } = useQuery({
    queryKey: ['security', 'api-keys'],
    queryFn: () => apiClient.getTenantApiKeys(),
  });

  const { data: auditResp, isLoading: auditLoading } = useQuery({
    queryKey: ['security', 'audit-logs'],
    queryFn: () => apiClient.getAuditLogs({ page: 1, page_size: 50 }),
  });

  const apiKeys: ApiKey[] = useMemo(() => {
    const rows = apiKeysResp?.data || [];
    return rows.map((k) => ({
      id: k.id,
      name: k.name,
      prefix: k.key_prefix,
      lastUsed: k.last_used_at ?? null,
      created: k.created_at,
      scopes: k.scopes || [],
      isActive: k.is_active,
    }));
  }, [apiKeysResp?.data]);

  const activeApiKeysCount = useMemo(
    () => apiKeys.filter((k) => k.isActive).length,
    [apiKeys]
  );

  const securityEvents: SecurityEvent[] = useMemo(() => {
    const logs = auditResp?.data?.logs || [];
    return logs.map((l) => {
      const actionTypeValue = (l.actionType || '').toUpperCase();
      const type: SecurityEvent['type'] =
        actionTypeValue.includes('FAILED') ? 'error' :
        actionTypeValue.includes('SUSPENDED') ? 'warning' :
        'success';
      return {
        id: l.id,
        type,
        event: l.actionType,
        details: l.action || '',
        ip: l.ipAddress || '-',
        timestamp: l.timestamp,
      };
    });
  }, [auditResp?.data?.logs]);

  const createKeyMutation = useMutation({
    mutationFn: () => apiClient.createTenantApiKey({ name: keyForm.name, scopes: keyForm.scopes }),
    onSuccess: (res) => {
      setCreatedKeyValue(res.data.api_key);
      setCreatedKeyOpen(true);
      setCreateKeyOpen(false);
      setKeyForm({ name: '', scopes: [] });
      queryClient.invalidateQueries({ queryKey: ['security', 'api-keys'] });
      toast.success('API key created');
    },
    onError: () => toast.error('Failed to create API key'),
  });

  const revokeKeyMutation = useMutation({
    mutationFn: (keyId: string) => apiClient.revokeTenantApiKey(keyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['security', 'api-keys'] });
      toast.success('API key revoked');
    },
    onError: () => toast.error('Failed to revoke API key'),
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
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
                <Key className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Active API Keys</p>
                <p className="text-2xl font-bold">{apiKeysLoading ? '—' : activeApiKeysCount}</p>
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
                <p className="text-sm text-muted-foreground">Recent Events</p>
                <p className="text-2xl font-bold">{auditLoading ? '—' : securityEvents.length}</p>
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
            {apiKeys.map((key) => (
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
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Revoke key"
                    onClick={() => revokeKeyMutation.mutate(key.id)}
                    disabled={revokeKeyMutation.isPending}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
            {!apiKeysLoading && apiKeys.length === 0 && (
              <div className="text-sm text-muted-foreground">No API keys yet</div>
            )}
          </CardContent>
        </Card>

      </div>

      {/* Security Events */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Recent Security Events
              </CardTitle>
              <CardDescription>Monitor security-related activity</CardDescription>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => queryClient.invalidateQueries({ queryKey: ['security', 'audit-logs'] })}
              disabled={auditLoading}
            >
              <RefreshCw className="h-4 w-4 mr-1" />
              Refresh
            </Button>
          </div>
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
              {securityEvents.map((event) => (
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
              {!auditLoading && securityEvents.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No recent events
                  </TableCell>
                </TableRow>
              )}
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
            <Button onClick={() => createKeyMutation.mutate()} disabled={!keyForm.name || createKeyMutation.isPending}>
              Create Key
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Created Key Dialog */}
      <Dialog open={createdKeyOpen} onOpenChange={setCreatedKeyOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>API key created</DialogTitle>
            <DialogDescription>Copy this key now. You won’t be able to see it again.</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label>API Key</Label>
            <Input value={createdKeyValue} readOnly />
          </div>
          <DialogFooter>
            <Button onClick={() => setCreatedKeyOpen(false)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
