import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Bell,
  Plus,
  Mail,
  MessageSquare,
  Webhook,
  CheckCircle,
  AlertTriangle,
  Info,
  Edit,
  Trash2,
  Send,
} from 'lucide-react';

interface NotificationChannel {
  id: string;
  name: string;
  type: 'email' | 'slack' | 'webhook';
  config: Record<string, string>;
  enabled: boolean;
}

interface NotificationRule {
  id: string;
  name: string;
  event: string;
  channels: string[];
  enabled: boolean;
}

const mockChannels: NotificationChannel[] = [
  {
    id: '1',
    name: 'Admin Email',
    type: 'email',
    config: { address: 'admin@n8nops.com' },
    enabled: true,
  },
  {
    id: '2',
    name: 'Ops Slack Channel',
    type: 'slack',
    config: { webhook: 'https://hooks.slack.com/...' },
    enabled: true,
  },
  {
    id: '3',
    name: 'PagerDuty Webhook',
    type: 'webhook',
    config: { url: 'https://events.pagerduty.com/...' },
    enabled: false,
  },
];

const mockRules: NotificationRule[] = [
  {
    id: '1',
    name: 'Critical System Alerts',
    event: 'system.critical',
    channels: ['1', '2', '3'],
    enabled: true,
  },
  {
    id: '2',
    name: 'New Tenant Registration',
    event: 'tenant.created',
    channels: ['1'],
    enabled: true,
  },
  {
    id: '3',
    name: 'High Error Rate Alert',
    event: 'api.error_rate_high',
    channels: ['2'],
    enabled: true,
  },
  {
    id: '4',
    name: 'Subscription Changes',
    event: 'billing.subscription_changed',
    channels: ['1'],
    enabled: false,
  },
];

const recentNotifications = [
  {
    id: '1',
    type: 'error',
    title: 'High API Error Rate',
    message: 'Error rate exceeded 5% threshold for /api/v1/workflows endpoint',
    time: '10 minutes ago',
    sent: true,
  },
  {
    id: '2',
    type: 'info',
    title: 'New Enterprise Tenant',
    message: 'DataFlow Inc upgraded to Enterprise plan',
    time: '2 hours ago',
    sent: true,
  },
  {
    id: '3',
    type: 'warning',
    title: 'Database Connection Warning',
    message: 'Connection pool usage at 85%',
    time: '4 hours ago',
    sent: true,
  },
  {
    id: '4',
    type: 'info',
    title: 'Scheduled Maintenance',
    message: 'System maintenance scheduled for tonight at 2:00 AM',
    time: '1 day ago',
    sent: false,
  },
];

export function NotificationsPage() {
  const [createChannelOpen, setCreateChannelOpen] = useState(false);
  const [createRuleOpen, setCreateRuleOpen] = useState(false);

  const [channelForm, setChannelForm] = useState({
    name: '',
    type: 'email' as 'email' | 'slack' | 'webhook',
    config: '',
  });

  const getChannelIcon = (type: string) => {
    switch (type) {
      case 'email':
        return <Mail className="h-4 w-4" />;
      case 'slack':
        return <MessageSquare className="h-4 w-4" />;
      case 'webhook':
        return <Webhook className="h-4 w-4" />;
      default:
        return <Bell className="h-4 w-4" />;
    }
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'error':
        return <AlertTriangle className="h-5 w-5 text-red-500" />;
      case 'warning':
        return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
      default:
        return <Info className="h-5 w-5 text-blue-500" />;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Notifications</h1>
        <p className="text-muted-foreground">Configure system alerts and notification channels</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Notification Channels */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Bell className="h-5 w-5" />
                  Notification Channels
                </CardTitle>
                <CardDescription>Configure where notifications are sent</CardDescription>
              </div>
              <Button size="sm" onClick={() => setCreateChannelOpen(true)}>
                <Plus className="h-4 w-4 mr-1" />
                Add Channel
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {mockChannels.map((channel) => (
              <div
                key={channel.id}
                className="flex items-center justify-between p-4 rounded-lg border"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-muted">
                    {getChannelIcon(channel.type)}
                  </div>
                  <div>
                    <p className="font-medium">{channel.name}</p>
                    <p className="text-sm text-muted-foreground capitalize">{channel.type}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={channel.enabled ? 'success' : 'outline'}>
                    {channel.enabled ? 'Active' : 'Disabled'}
                  </Badge>
                  <Button variant="ghost" size="icon">
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Notification Rules */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5" />
                  Notification Rules
                </CardTitle>
                <CardDescription>Define when and how to send alerts</CardDescription>
              </div>
              <Button size="sm" onClick={() => setCreateRuleOpen(true)}>
                <Plus className="h-4 w-4 mr-1" />
                Add Rule
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {mockRules.map((rule) => (
              <div
                key={rule.id}
                className="flex items-center justify-between p-4 rounded-lg border"
              >
                <div>
                  <p className="font-medium">{rule.name}</p>
                  <p className="text-sm text-muted-foreground">
                    <code className="bg-muted px-1 rounded">{rule.event}</code>
                    <span className="mx-2">→</span>
                    {rule.channels.length} channel(s)
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={rule.enabled ? 'success' : 'outline'}>
                    {rule.enabled ? 'Active' : 'Disabled'}
                  </Badge>
                  <Button variant="ghost" size="icon">
                    <Edit className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Recent Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Send className="h-5 w-5" />
            Recent Notifications
          </CardTitle>
          <CardDescription>Log of recently sent and pending notifications</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {recentNotifications.map((notification) => (
              <div
                key={notification.id}
                className="flex items-start gap-4 p-4 rounded-lg border"
              >
                {getNotificationIcon(notification.type)}
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <p className="font-medium">{notification.title}</p>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{notification.time}</span>
                      <Badge variant={notification.sent ? 'success' : 'outline'} className="text-xs">
                        {notification.sent ? 'Sent' : 'Pending'}
                      </Badge>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">{notification.message}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Create Channel Dialog */}
      <Dialog open={createChannelOpen} onOpenChange={setCreateChannelOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Notification Channel</DialogTitle>
            <DialogDescription>Configure a new notification destination</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="channel-name">Channel Name</Label>
              <Input
                id="channel-name"
                placeholder="My Slack Channel"
                value={channelForm.name}
                onChange={(e) => setChannelForm({ ...channelForm, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="channel-type">Channel Type</Label>
              <select
                id="channel-type"
                value={channelForm.type}
                onChange={(e) =>
                  setChannelForm({ ...channelForm, type: e.target.value as any })
                }
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="email" className="bg-background text-foreground">Email</option>
                <option value="slack" className="bg-background text-foreground">Slack</option>
                <option value="webhook" className="bg-background text-foreground">Webhook</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="channel-config">
                {channelForm.type === 'email'
                  ? 'Email Address'
                  : channelForm.type === 'slack'
                    ? 'Slack Webhook URL'
                    : 'Webhook URL'}
              </Label>
              <Input
                id="channel-config"
                placeholder={
                  channelForm.type === 'email'
                    ? 'alerts@company.com'
                    : 'https://hooks.example.com/...'
                }
                value={channelForm.config}
                onChange={(e) => setChannelForm({ ...channelForm, config: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateChannelOpen(false)}>
              Cancel
            </Button>
            <Button>Create Channel</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Rule Dialog */}
      <Dialog open={createRuleOpen} onOpenChange={setCreateRuleOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Notification Rule</DialogTitle>
            <DialogDescription>Define when to send notifications</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="rule-name">Rule Name</Label>
              <Input id="rule-name" placeholder="Critical Alerts" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rule-event">Event Type</Label>
              <select
                id="rule-event"
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="system.critical" className="bg-background text-foreground">System Critical</option>
                <option value="system.warning" className="bg-background text-foreground">System Warning</option>
                <option value="tenant.created" className="bg-background text-foreground">Tenant Created</option>
                <option value="tenant.deleted" className="bg-background text-foreground">Tenant Deleted</option>
                <option value="billing.subscription_changed" className="bg-background text-foreground">Subscription Changed</option>
                <option value="api.error_rate_high" className="bg-background text-foreground">High API Error Rate</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>Channels</Label>
              <div className="space-y-2">
                {mockChannels.map((channel) => (
                  <label key={channel.id} className="flex items-center gap-2">
                    <input type="checkbox" className="rounded border-input" />
                    <span className="text-sm">{channel.name}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateRuleOpen(false)}>
              Cancel
            </Button>
            <Button>Create Rule</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
