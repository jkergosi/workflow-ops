import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Bell,
  Plus,
  CheckCircle,
  AlertTriangle,
  Info,
  Edit,
  Trash2,
  Send,
  Play,
  RefreshCw,
  Loader2,
  XCircle,
  Clock,
  Mail,
  MessageSquare,
  Webhook,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import type {
  NotificationChannel,
  NotificationRule,
  AlertEvent,
  EventCatalogItem,
  ChannelType,
  SlackConfig,
  EmailConfig,
  WebhookConfig,
} from '@/types';

// Default configs for each channel type
const defaultSlackConfig: SlackConfig = {
  webhook_url: '',
  channel: '',
  username: 'N8N Ops',
  icon_emoji: ':bell:',
};

const defaultEmailConfig: EmailConfig = {
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  from_address: '',
  to_addresses: [],
  use_tls: true,
};

const defaultWebhookConfig: WebhookConfig = {
  url: '',
  method: 'POST',
  headers: {},
  auth_type: 'none',
  auth_value: '',
};

export function AlertsPage() {
  const queryClient = useQueryClient();
  const [createChannelOpen, setCreateChannelOpen] = useState(false);
  const [editChannelOpen, setEditChannelOpen] = useState(false);
  const [createRuleOpen, setCreateRuleOpen] = useState(false);
  const [editRuleOpen, setEditRuleOpen] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState<NotificationChannel | null>(null);
  const [selectedRule, setSelectedRule] = useState<NotificationRule | null>(null);

  const [channelForm, setChannelForm] = useState<{
    name: string;
    type: ChannelType;
    isEnabled: boolean;
    slackConfig: SlackConfig;
    emailConfig: EmailConfig;
    webhookConfig: WebhookConfig;
    emailToAddresses: string; // comma-separated for input
  }>({
    name: '',
    type: 'slack',
    isEnabled: true,
    slackConfig: { ...defaultSlackConfig },
    emailConfig: { ...defaultEmailConfig },
    webhookConfig: { ...defaultWebhookConfig },
    emailToAddresses: '',
  });

  const [ruleForm, setRuleForm] = useState({
    eventType: '',
    channelIds: [] as string[],
    isEnabled: true,
  });

  // Queries
  const { data: channelsData, isLoading: channelsLoading, refetch: refetchChannels } = useQuery({
    queryKey: ['notification-channels'],
    queryFn: () => apiClient.getNotificationChannels(),
  });

  const { data: rulesData, isLoading: rulesLoading, refetch: refetchRules } = useQuery({
    queryKey: ['notification-rules'],
    queryFn: () => apiClient.getNotificationRules(),
  });

  const { data: eventsData, isLoading: eventsLoading, refetch: refetchEvents } = useQuery({
    queryKey: ['alert-events'],
    queryFn: () => apiClient.getAlertEvents({ limit: 50 }),
  });

  const { data: catalogData } = useQuery({
    queryKey: ['event-catalog'],
    queryFn: () => apiClient.getEventCatalog(),
  });

  const channels = channelsData?.data ?? [];
  const rules = rulesData?.data ?? [];
  const events = eventsData?.data ?? [];
  const eventCatalog = catalogData?.data ?? [];

  // Mutations
  const createChannelMutation = useMutation({
    mutationFn: (data: { name: string; type: ChannelType; configJson: Record<string, unknown>; isEnabled: boolean }) =>
      apiClient.createNotificationChannel(data),
    onSuccess: () => {
      toast.success('Notification channel created');
      queryClient.invalidateQueries({ queryKey: ['notification-channels'] });
      setCreateChannelOpen(false);
      resetChannelForm();
    },
    onError: (error: Error) => {
      toast.error('Failed to create channel', {
        description: error.message,
        duration: 8000,
      });
    },
  });

  const updateChannelMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<NotificationChannel> }) =>
      apiClient.updateNotificationChannel(id, data),
    onSuccess: () => {
      toast.success('Notification channel updated');
      queryClient.invalidateQueries({ queryKey: ['notification-channels'] });
      setEditChannelOpen(false);
      setSelectedChannel(null);
    },
    onError: (error: Error) => {
      toast.error('Failed to update channel', {
        description: error.message,
        duration: 8000,
      });
    },
  });

  const deleteChannelMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteNotificationChannel(id),
    onSuccess: () => {
      toast.success('Notification channel deleted');
      queryClient.invalidateQueries({ queryKey: ['notification-channels'] });
    },
    onError: (error: Error) => {
      toast.error('Failed to delete channel', {
        description: error.message,
        duration: 8000,
      });
    },
  });

  const testChannelMutation = useMutation({
    mutationFn: (id: string) => apiClient.testNotificationChannel(id),
    onSuccess: (result) => {
      if (result.data.success) {
        toast.success(result.data.message || 'Test notification sent successfully');
      } else {
        toast.error('Test notification failed', {
          description: result.data.message || 'The test notification could not be delivered',
          duration: 8000,
        });
      }
    },
    onError: (error: Error) => {
      toast.error('Test failed', {
        description: error.message,
        duration: 8000,
      });
    },
  });

  const createRuleMutation = useMutation({
    mutationFn: (data: { eventType: string; channelIds: string[]; isEnabled: boolean }) =>
      apiClient.createNotificationRule(data),
    onSuccess: () => {
      toast.success('Notification rule created');
      queryClient.invalidateQueries({ queryKey: ['notification-rules'] });
      setCreateRuleOpen(false);
      resetRuleForm();
    },
    onError: (error: Error) => {
      toast.error('Failed to create rule', {
        description: error.message,
        duration: 8000,
      });
    },
  });

  const updateRuleMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<NotificationRule> }) =>
      apiClient.updateNotificationRule(id, data),
    onSuccess: () => {
      toast.success('Notification rule updated');
      queryClient.invalidateQueries({ queryKey: ['notification-rules'] });
      setEditRuleOpen(false);
      setSelectedRule(null);
    },
    onError: (error: Error) => {
      toast.error('Failed to update rule', {
        description: error.message,
        duration: 8000,
      });
    },
  });

  const deleteRuleMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteNotificationRule(id),
    onSuccess: () => {
      toast.success('Notification rule deleted');
      queryClient.invalidateQueries({ queryKey: ['notification-rules'] });
    },
    onError: (error: Error) => {
      toast.error('Failed to delete rule', {
        description: error.message,
        duration: 8000,
      });
    },
  });

  // Helpers
  const resetChannelForm = () => {
    setChannelForm({
      name: '',
      type: 'slack',
      isEnabled: true,
      slackConfig: { ...defaultSlackConfig },
      emailConfig: { ...defaultEmailConfig },
      webhookConfig: { ...defaultWebhookConfig },
      emailToAddresses: '',
    });
  };

  const resetRuleForm = () => {
    setRuleForm({
      eventType: '',
      channelIds: [],
      isEnabled: true,
    });
  };

  const getConfigForType = (type: ChannelType): Record<string, unknown> => {
    switch (type) {
      case 'slack':
        return channelForm.slackConfig;
      case 'email':
        return {
          ...channelForm.emailConfig,
          to_addresses: channelForm.emailToAddresses.split(',').map((e) => e.trim()).filter(Boolean),
        };
      case 'webhook':
        return channelForm.webhookConfig;
      default:
        return {};
    }
  };

  const handleCreateChannel = () => {
    if (!channelForm.name) {
      toast.warning('Missing channel name', {
        description: 'Please enter a name for this notification channel',
      });
      return;
    }

    const configJson = getConfigForType(channelForm.type);

    // Validate required fields
    if (channelForm.type === 'slack' && !channelForm.slackConfig.webhook_url) {
      toast.warning('Missing Slack webhook URL', {
        description: 'Enter your Slack incoming webhook URL to enable notifications',
      });
      return;
    }
    if (channelForm.type === 'email') {
      if (!channelForm.emailConfig.smtp_host || !channelForm.emailConfig.from_address || !channelForm.emailToAddresses) {
        toast.warning('Missing email configuration', {
          description: 'Please fill in SMTP host, from address, and recipient addresses',
        });
        return;
      }
    }
    if (channelForm.type === 'webhook' && !channelForm.webhookConfig.url) {
      toast.warning('Missing webhook URL', {
        description: 'Enter the URL where notifications should be sent',
      });
      return;
    }

    createChannelMutation.mutate({
      name: channelForm.name,
      type: channelForm.type,
      configJson,
      isEnabled: channelForm.isEnabled,
    });
  };

  const handleUpdateChannel = () => {
    if (!selectedChannel) return;
    const configJson = getConfigForType(channelForm.type);
    updateChannelMutation.mutate({
      id: selectedChannel.id,
      data: {
        name: channelForm.name,
        configJson: configJson as any,
        isEnabled: channelForm.isEnabled,
      },
    });
  };

  const handleEditChannel = (channel: NotificationChannel) => {
    setSelectedChannel(channel);
    const config = channel.configJson as Record<string, unknown>;

    setChannelForm({
      name: channel.name,
      type: channel.type,
      isEnabled: channel.isEnabled,
      slackConfig: channel.type === 'slack' ? (config as SlackConfig) : { ...defaultSlackConfig },
      emailConfig: channel.type === 'email' ? (config as EmailConfig) : { ...defaultEmailConfig },
      webhookConfig: channel.type === 'webhook' ? (config as WebhookConfig) : { ...defaultWebhookConfig },
      emailToAddresses: channel.type === 'email' ? ((config as EmailConfig).to_addresses || []).join(', ') : '',
    });
    setEditChannelOpen(true);
  };

  const handleCreateRule = () => {
    if (!ruleForm.eventType || ruleForm.channelIds.length === 0) {
      toast.warning('Incomplete rule configuration', {
        description: 'Please select an event type and at least one notification channel',
      });
      return;
    }
    createRuleMutation.mutate(ruleForm);
  };

  const handleUpdateRule = () => {
    if (!selectedRule) return;
    updateRuleMutation.mutate({
      id: selectedRule.id,
      data: {
        channelIds: ruleForm.channelIds,
        isEnabled: ruleForm.isEnabled,
      },
    });
  };

  const handleEditRule = (rule: NotificationRule) => {
    setSelectedRule(rule);
    setRuleForm({
      eventType: rule.eventType,
      channelIds: rule.channelIds,
      isEnabled: rule.isEnabled,
    });
    setEditRuleOpen(true);
  };

  const toggleRuleChannel = (channelId: string) => {
    setRuleForm((prev) => ({
      ...prev,
      channelIds: prev.channelIds.includes(channelId)
        ? prev.channelIds.filter((id) => id !== channelId)
        : [...prev.channelIds, channelId],
    }));
  };

  const getEventDisplayName = (eventType: string): string => {
    const catalogItem = eventCatalog.find((item) => item.eventType === eventType);
    return catalogItem?.displayName || eventType;
  };

  const getChannelName = (channelId: string): string => {
    const channel = channels.find((c) => c.id === channelId);
    return channel?.name || channelId;
  };

  const getChannelIcon = (type: ChannelType) => {
    switch (type) {
      case 'slack':
        return <MessageSquare className="h-4 w-4" />;
      case 'email':
        return <Mail className="h-4 w-4" />;
      case 'webhook':
        return <Webhook className="h-4 w-4" />;
      default:
        return <Bell className="h-4 w-4" />;
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'sent':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case 'skipped':
        return <AlertTriangle className="h-4 w-4 text-muted-foreground" />;
      default:
        return <Info className="h-4 w-4 text-blue-500" />;
    }
  };

  const getEventTypeIcon = (eventType: string) => {
    if (eventType.includes('fail') || eventType.includes('error') || eventType.includes('unhealthy')) {
      return <AlertTriangle className="h-5 w-5 text-red-500" />;
    }
    if (eventType.includes('success') || eventType.includes('completed') || eventType.includes('recovered')) {
      return <CheckCircle className="h-5 w-5 text-green-500" />;
    }
    if (eventType.includes('started') || eventType.includes('pending')) {
      return <Info className="h-5 w-5 text-blue-500" />;
    }
    return <Bell className="h-5 w-5 text-muted-foreground" />;
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins !== 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    return date.toLocaleDateString();
  };

  // Group event catalog by category
  const catalogByCategory = eventCatalog.reduce((acc, item) => {
    if (!acc[item.category]) {
      acc[item.category] = [];
    }
    acc[item.category].push(item);
    return acc;
  }, {} as Record<string, EventCatalogItem[]>);

  const handleRefreshAll = () => {
    refetchChannels();
    refetchRules();
    refetchEvents();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Alerts</h1>
          <p className="text-muted-foreground">Configure notification channels and event rules</p>
        </div>
        <Button variant="outline" onClick={handleRefreshAll}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
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
            {channelsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : channels.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Bell className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>No notification channels configured</p>
                <p className="text-sm">Add a channel to start receiving alerts</p>
              </div>
            ) : (
              channels.map((channel) => (
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
                    <Badge variant={channel.isEnabled ? 'success' : 'outline'}>
                      {channel.isEnabled ? 'Active' : 'Disabled'}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => testChannelMutation.mutate(channel.id)}
                      disabled={testChannelMutation.isPending}
                      title="Test channel"
                    >
                      {testChannelMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleEditChannel(channel)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        if (confirm('Delete this notification channel?')) {
                          deleteChannelMutation.mutate(channel.id);
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))
            )}
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
                <CardDescription>Define which events trigger which channels</CardDescription>
              </div>
              <Button
                size="sm"
                onClick={() => setCreateRuleOpen(true)}
                disabled={channels.length === 0}
              >
                <Plus className="h-4 w-4 mr-1" />
                Add Rule
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {rulesLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : rules.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <CheckCircle className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>No notification rules configured</p>
                <p className="text-sm">
                  {channels.length === 0
                    ? 'Add a channel first, then create rules'
                    : 'Create rules to route events to channels'}
                </p>
              </div>
            ) : (
              rules.map((rule) => (
                <div
                  key={rule.id}
                  className="flex items-center justify-between p-4 rounded-lg border"
                >
                  <div>
                    <p className="font-medium">{getEventDisplayName(rule.eventType)}</p>
                    <p className="text-sm text-muted-foreground">
                      <code className="bg-muted px-1 rounded">{rule.eventType}</code>
                      <span className="mx-2">→</span>
                      {rule.channelIds.length} channel(s)
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={rule.isEnabled ? 'success' : 'outline'}>
                      {rule.isEnabled ? 'Active' : 'Disabled'}
                    </Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleEditRule(rule)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        if (confirm('Delete this notification rule?')) {
                          deleteRuleMutation.mutate(rule.id);
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Events */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Send className="h-5 w-5" />
            Recent Activity
          </CardTitle>
          <CardDescription>Log of recent events and notification status</CardDescription>
        </CardHeader>
        <CardContent>
          {eventsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : events.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Send className="h-12 w-12 mx-auto mb-2 opacity-50" />
              <p>No recent events</p>
              <p className="text-sm">Events will appear here as they occur</p>
            </div>
          ) : (
            <div className="space-y-4">
              {events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-start gap-4 p-4 rounded-lg border"
                >
                  {getEventTypeIcon(event.eventType)}
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <p className="font-medium">{getEventDisplayName(event.eventType)}</p>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(event.timestamp)}
                        </span>
                        <div className="flex items-center gap-1">
                          {getStatusIcon(event.notificationStatus)}
                          <Badge
                            variant={
                              event.notificationStatus === 'sent'
                                ? 'success'
                                : event.notificationStatus === 'failed'
                                  ? 'destructive'
                                  : 'outline'
                            }
                            className="text-xs"
                          >
                            {event.notificationStatus || 'no rule'}
                          </Badge>
                        </div>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">
                      <code className="bg-muted px-1 rounded text-xs">{event.eventType}</code>
                      {event.environmentId && (
                        <span className="ml-2">Environment: {event.environmentId}</span>
                      )}
                    </p>
                    {event.metadataJson && Object.keys(event.metadataJson).length > 0 && (
                      <div className="mt-2 text-xs text-muted-foreground">
                        {Object.entries(event.metadataJson).map(([key, value]) => (
                          <span key={key} className="mr-3">
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    )}
                    {event.channelsNotified && event.channelsNotified.length > 0 && (
                      <div className="mt-2 flex gap-1">
                        {event.channelsNotified.map((channelId) => (
                          <Badge key={channelId} variant="outline" className="text-xs">
                            {getChannelName(channelId)}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Channel Dialog */}
      <Dialog open={createChannelOpen} onOpenChange={setCreateChannelOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add Notification Channel</DialogTitle>
            <DialogDescription>
              Configure a channel to receive event notifications
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="channel-name">Channel Name</Label>
              <Input
                id="channel-name"
                placeholder="My Alert Channel"
                value={channelForm.name}
                onChange={(e) => setChannelForm({ ...channelForm, name: e.target.value })}
              />
            </div>

            <Tabs value={channelForm.type} onValueChange={(v) => setChannelForm({ ...channelForm, type: v as ChannelType })}>
              <TabsList className="grid grid-cols-3">
                <TabsTrigger value="slack">
                  <MessageSquare className="h-4 w-4 mr-2" />
                  Slack
                </TabsTrigger>
                <TabsTrigger value="email">
                  <Mail className="h-4 w-4 mr-2" />
                  Email
                </TabsTrigger>
                <TabsTrigger value="webhook">
                  <Webhook className="h-4 w-4 mr-2" />
                  Webhook
                </TabsTrigger>
              </TabsList>

              <TabsContent value="slack" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label>Webhook URL *</Label>
                  <Input
                    placeholder="https://hooks.slack.com/services/..."
                    value={channelForm.slackConfig.webhook_url}
                    onChange={(e) => setChannelForm({
                      ...channelForm,
                      slackConfig: { ...channelForm.slackConfig, webhook_url: e.target.value }
                    })}
                  />
                  <p className="text-xs text-muted-foreground">
                    Create an incoming webhook in your Slack workspace
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Channel Override</Label>
                    <Input
                      placeholder="#alerts"
                      value={channelForm.slackConfig.channel || ''}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        slackConfig: { ...channelForm.slackConfig, channel: e.target.value }
                      })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Username</Label>
                    <Input
                      placeholder="N8N Ops"
                      value={channelForm.slackConfig.username || ''}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        slackConfig: { ...channelForm.slackConfig, username: e.target.value }
                      })}
                    />
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="email" className="space-y-4 mt-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>SMTP Host *</Label>
                    <Input
                      placeholder="smtp.gmail.com"
                      value={channelForm.emailConfig.smtp_host}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        emailConfig: { ...channelForm.emailConfig, smtp_host: e.target.value }
                      })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>SMTP Port</Label>
                    <Input
                      type="number"
                      placeholder="587"
                      value={channelForm.emailConfig.smtp_port}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        emailConfig: { ...channelForm.emailConfig, smtp_port: parseInt(e.target.value) || 587 }
                      })}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>SMTP User *</Label>
                    <Input
                      placeholder="user@example.com"
                      value={channelForm.emailConfig.smtp_user}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        emailConfig: { ...channelForm.emailConfig, smtp_user: e.target.value }
                      })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>SMTP Password *</Label>
                    <Input
                      type="password"
                      placeholder="••••••••"
                      value={channelForm.emailConfig.smtp_password}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        emailConfig: { ...channelForm.emailConfig, smtp_password: e.target.value }
                      })}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>From Address *</Label>
                  <Input
                    placeholder="alerts@yourcompany.com"
                    value={channelForm.emailConfig.from_address}
                    onChange={(e) => setChannelForm({
                      ...channelForm,
                      emailConfig: { ...channelForm.emailConfig, from_address: e.target.value }
                    })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>To Addresses * (comma-separated)</Label>
                  <Input
                    placeholder="admin@example.com, ops@example.com"
                    value={channelForm.emailToAddresses}
                    onChange={(e) => setChannelForm({ ...channelForm, emailToAddresses: e.target.value })}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Label>Use TLS</Label>
                  <Switch
                    checked={channelForm.emailConfig.use_tls}
                    onCheckedChange={(checked) => setChannelForm({
                      ...channelForm,
                      emailConfig: { ...channelForm.emailConfig, use_tls: checked }
                    })}
                  />
                </div>
              </TabsContent>

              <TabsContent value="webhook" className="space-y-4 mt-4">
                <div className="space-y-2">
                  <Label>Webhook URL *</Label>
                  <Input
                    placeholder="https://api.example.com/webhook"
                    value={channelForm.webhookConfig.url}
                    onChange={(e) => setChannelForm({
                      ...channelForm,
                      webhookConfig: { ...channelForm.webhookConfig, url: e.target.value }
                    })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>HTTP Method</Label>
                    <Select
                      value={channelForm.webhookConfig.method}
                      onValueChange={(value) => setChannelForm({
                        ...channelForm,
                        webhookConfig: { ...channelForm.webhookConfig, method: value }
                      })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="POST">POST</SelectItem>
                        <SelectItem value="PUT">PUT</SelectItem>
                        <SelectItem value="PATCH">PATCH</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Authentication</Label>
                    <Select
                      value={channelForm.webhookConfig.auth_type || 'none'}
                      onValueChange={(value) => setChannelForm({
                        ...channelForm,
                        webhookConfig: { ...channelForm.webhookConfig, auth_type: value as 'none' | 'basic' | 'bearer' }
                      })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">None</SelectItem>
                        <SelectItem value="basic">Basic Auth</SelectItem>
                        <SelectItem value="bearer">Bearer Token</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {channelForm.webhookConfig.auth_type && channelForm.webhookConfig.auth_type !== 'none' && (
                  <div className="space-y-2">
                    <Label>
                      {channelForm.webhookConfig.auth_type === 'basic' ? 'Credentials (username:password)' : 'Bearer Token'}
                    </Label>
                    <Input
                      type="password"
                      placeholder={channelForm.webhookConfig.auth_type === 'basic' ? 'username:password' : 'your-token'}
                      value={channelForm.webhookConfig.auth_value || ''}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        webhookConfig: { ...channelForm.webhookConfig, auth_value: e.target.value }
                      })}
                    />
                  </div>
                )}
              </TabsContent>
            </Tabs>

            <div className="flex items-center justify-between">
              <Label>Enable channel</Label>
              <Switch
                checked={channelForm.isEnabled}
                onCheckedChange={(checked) => setChannelForm({ ...channelForm, isEnabled: checked })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateChannelOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateChannel} disabled={createChannelMutation.isPending}>
              {createChannelMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create Channel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Channel Dialog */}
      <Dialog open={editChannelOpen} onOpenChange={setEditChannelOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit Notification Channel</DialogTitle>
            <DialogDescription>
              Update the notification channel settings
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Channel Name</Label>
              <Input
                value={channelForm.name}
                onChange={(e) => setChannelForm({ ...channelForm, name: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label>Channel Type</Label>
              <div className="flex items-center gap-2 p-2 border rounded-md bg-muted">
                {getChannelIcon(channelForm.type)}
                <span className="capitalize">{channelForm.type}</span>
              </div>
            </div>

            {channelForm.type === 'slack' && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Webhook URL</Label>
                  <Input
                    placeholder="https://hooks.slack.com/services/..."
                    value={channelForm.slackConfig.webhook_url}
                    onChange={(e) => setChannelForm({
                      ...channelForm,
                      slackConfig: { ...channelForm.slackConfig, webhook_url: e.target.value }
                    })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Channel Override</Label>
                    <Input
                      placeholder="#alerts"
                      value={channelForm.slackConfig.channel || ''}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        slackConfig: { ...channelForm.slackConfig, channel: e.target.value }
                      })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Username</Label>
                    <Input
                      placeholder="N8N Ops"
                      value={channelForm.slackConfig.username || ''}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        slackConfig: { ...channelForm.slackConfig, username: e.target.value }
                      })}
                    />
                  </div>
                </div>
              </div>
            )}

            {channelForm.type === 'email' && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>SMTP Host</Label>
                    <Input
                      value={channelForm.emailConfig.smtp_host}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        emailConfig: { ...channelForm.emailConfig, smtp_host: e.target.value }
                      })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>SMTP Port</Label>
                    <Input
                      type="number"
                      value={channelForm.emailConfig.smtp_port}
                      onChange={(e) => setChannelForm({
                        ...channelForm,
                        emailConfig: { ...channelForm.emailConfig, smtp_port: parseInt(e.target.value) || 587 }
                      })}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>To Addresses (comma-separated)</Label>
                  <Input
                    value={channelForm.emailToAddresses}
                    onChange={(e) => setChannelForm({ ...channelForm, emailToAddresses: e.target.value })}
                  />
                </div>
              </div>
            )}

            {channelForm.type === 'webhook' && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Webhook URL</Label>
                  <Input
                    value={channelForm.webhookConfig.url}
                    onChange={(e) => setChannelForm({
                      ...channelForm,
                      webhookConfig: { ...channelForm.webhookConfig, url: e.target.value }
                    })}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>HTTP Method</Label>
                    <Select
                      value={channelForm.webhookConfig.method}
                      onValueChange={(value) => setChannelForm({
                        ...channelForm,
                        webhookConfig: { ...channelForm.webhookConfig, method: value }
                      })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="POST">POST</SelectItem>
                        <SelectItem value="PUT">PUT</SelectItem>
                        <SelectItem value="PATCH">PATCH</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Authentication</Label>
                    <Select
                      value={channelForm.webhookConfig.auth_type || 'none'}
                      onValueChange={(value) => setChannelForm({
                        ...channelForm,
                        webhookConfig: { ...channelForm.webhookConfig, auth_type: value as 'none' | 'basic' | 'bearer' }
                      })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">None</SelectItem>
                        <SelectItem value="basic">Basic Auth</SelectItem>
                        <SelectItem value="bearer">Bearer Token</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between">
              <Label>Enable channel</Label>
              <Switch
                checked={channelForm.isEnabled}
                onCheckedChange={(checked) => setChannelForm({ ...channelForm, isEnabled: checked })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditChannelOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateChannel} disabled={updateChannelMutation.isPending}>
              {updateChannelMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Rule Dialog */}
      <Dialog open={createRuleOpen} onOpenChange={setCreateRuleOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Notification Rule</DialogTitle>
            <DialogDescription>Define which events trigger notifications</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Event Type</Label>
              <Select
                value={ruleForm.eventType}
                onValueChange={(value) => setRuleForm({ ...ruleForm, eventType: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select event type" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(catalogByCategory).map(([category, items]) => (
                    <div key={category}>
                      <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground capitalize">
                        {category}
                      </div>
                      {items.map((item) => (
                        <SelectItem key={item.eventType} value={item.eventType}>
                          {item.displayName}
                        </SelectItem>
                      ))}
                    </div>
                  ))}
                </SelectContent>
              </Select>
              {ruleForm.eventType && (
                <p className="text-xs text-muted-foreground">
                  {eventCatalog.find((e) => e.eventType === ruleForm.eventType)?.description}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label>Channels</Label>
              <div className="space-y-2 max-h-48 overflow-y-auto border rounded-md p-2">
                {channels.map((channel) => (
                  <label key={channel.id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      className="rounded border-input"
                      checked={ruleForm.channelIds.includes(channel.id)}
                      onChange={() => toggleRuleChannel(channel.id)}
                    />
                    <span className="flex items-center gap-2 text-sm">
                      {getChannelIcon(channel.type)}
                      {channel.name}
                    </span>
                    {!channel.isEnabled && (
                      <Badge variant="outline" className="text-xs">disabled</Badge>
                    )}
                  </label>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <Label>Enable rule</Label>
              <Switch
                checked={ruleForm.isEnabled}
                onCheckedChange={(checked) => setRuleForm({ ...ruleForm, isEnabled: checked })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateRuleOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateRule} disabled={createRuleMutation.isPending}>
              {createRuleMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create Rule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Rule Dialog */}
      <Dialog open={editRuleOpen} onOpenChange={setEditRuleOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Notification Rule</DialogTitle>
            <DialogDescription>
              Update channels for {selectedRule && getEventDisplayName(selectedRule.eventType)}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Event Type</Label>
              <div className="p-2 border rounded-md bg-muted">
                <p className="font-medium">{selectedRule && getEventDisplayName(selectedRule.eventType)}</p>
                <code className="text-xs text-muted-foreground">{selectedRule?.eventType}</code>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Channels</Label>
              <div className="space-y-2 max-h-48 overflow-y-auto border rounded-md p-2">
                {channels.map((channel) => (
                  <label key={channel.id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      className="rounded border-input"
                      checked={ruleForm.channelIds.includes(channel.id)}
                      onChange={() => toggleRuleChannel(channel.id)}
                    />
                    <span className="flex items-center gap-2 text-sm">
                      {getChannelIcon(channel.type)}
                      {channel.name}
                    </span>
                    {!channel.isEnabled && (
                      <Badge variant="outline" className="text-xs">disabled</Badge>
                    )}
                  </label>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <Label>Enable rule</Label>
              <Switch
                checked={ruleForm.isEnabled}
                onCheckedChange={(checked) => setRuleForm({ ...ruleForm, isEnabled: checked })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditRuleOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateRule} disabled={updateRuleMutation.isPending}>
              {updateRuleMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
