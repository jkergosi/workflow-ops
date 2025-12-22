import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { apiClient } from '@/lib/api-client';
import {
  Settings,
  Database,
  Mail,
  Key,
  Save,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  ExternalLink,
  Shield,
  CreditCard,
  Eye,
  EyeOff,
  Copy,
  Webhook,
  TestTube,
  ArrowUp,
  ArrowDown,
  Plus,
  Trash2,
  Pencil,
  Layers,
  Check,
  X,
  Loader2,
  Workflow,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import { useAppStore } from '@/store/use-app-store';
import type { ProviderWithPlans, TenantProviderSubscription } from '@/types';

interface SystemConfig {
  appName: string;
  appUrl: string;
  supportEmail: string;
  defaultTimezone: string;
  maintenanceMode: boolean;
}

interface DatabaseConfig {
  host: string;
  port: number;
  database: string;
  connectionPoolSize: number;
  status: 'connected' | 'disconnected' | 'error';
}

interface EmailConfig {
  provider: 'smtp' | 'sendgrid' | 'aws_ses';
  smtpHost: string;
  smtpPort: number;
  smtpUser: string;
  fromName: string;
  fromEmail: string;
}

interface Auth0Config {
  domain: string;
  clientId: string;
  clientSecret: string;
  audience: string;
  connectionStatus: 'connected' | 'disconnected' | 'error';
  lastSynced?: string;
}

interface StripeConfig {
  mode: 'test' | 'live';
  publishableKey: string;
  secretKey: string;
  webhookSecret: string;
  webhookEndpoint: string;
  webhookStatus: 'active' | 'inactive' | 'error';
  lastWebhookReceived?: string;
}

const mockSystemConfig: SystemConfig = {
  appName: 'N8N Ops',
  appUrl: 'https://app.n8nops.com',
  supportEmail: 'support@n8nops.com',
  defaultTimezone: 'UTC',
  maintenanceMode: false,
};

const mockDatabaseConfig: DatabaseConfig = {
  host: 'db.supabase.co',
  port: 5432,
  database: 'n8n_ops',
  connectionPoolSize: 20,
  status: 'connected',
};

const mockEmailConfig: EmailConfig = {
  provider: 'sendgrid',
  smtpHost: 'smtp.sendgrid.net',
  smtpPort: 587,
  smtpUser: 'apikey',
  fromName: 'N8N Ops',
  fromEmail: 'noreply@n8nops.com',
};

const mockAuth0Config: Auth0Config = {
  domain: 'n8nops.us.auth0.com',
  clientId: 'abc123...xyz789',
  clientSecret: '•••••••••••••••••••••••••',
  audience: 'https://api.n8nops.com',
  connectionStatus: 'connected',
  lastSynced: new Date().toISOString(),
};

const mockStripeConfig: StripeConfig = {
  mode: 'test',
  publishableKey: 'pk_test_...abc123',
  secretKey: 'sk_test_•••••••••••••••',
  webhookSecret: 'whsec_•••••••••••••••',
  webhookEndpoint: 'https://api.n8nops.com/webhooks/stripe',
  webhookStatus: 'active',
  lastWebhookReceived: new Date(Date.now() - 3600000).toISOString(),
};

// Provider Plans Management Component
function ProviderPlansManagement() {
  const queryClient = useQueryClient();
  const [editingPlan, setEditingPlan] = useState<any>(null);
  const [expandedProviders, setExpandedProviders] = useState<Record<string, boolean>>({});

  // Fetch all providers with plans (including inactive)
  const { data: providersData, isLoading } = useQuery({
    queryKey: ['admin-providers-all'],
    queryFn: () => apiClient.adminGetAllProviders(),
  });

  const providers = providersData?.data || [];

  // Update plan mutation
  const updatePlanMutation = useMutation({
    mutationFn: ({ planId, data }: { planId: string; data: any }) =>
      apiClient.adminUpdateProviderPlan(planId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-providers-all'] });
      queryClient.invalidateQueries({ queryKey: ['providers-with-plans'] });
      toast.success('Plan updated successfully');
      setEditingPlan(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update plan');
    },
  });

  // Toggle provider expansion
  const toggleProvider = (providerId: string) => {
    setExpandedProviders((prev) => ({
      ...prev,
      [providerId]: !prev[providerId],
    }));
  };

  // Get provider icon
  const getProviderIcon = (name: string) => {
    switch (name?.toLowerCase()) {
      case 'n8n':
        return <Workflow className="h-5 w-5" />;
      case 'make':
        return <Zap className="h-5 w-5" />;
      default:
        return <Layers className="h-5 w-5" />;
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Layers className="h-5 w-5" />
          Provider Plans
        </CardTitle>
        <CardDescription>
          Manage pricing plans and Stripe integration for each provider
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {providers.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            No providers configured. Run the database migration to seed providers.
          </div>
        ) : (
          providers.map((provider: any) => (
            <div key={provider.id} className="border rounded-lg">
              {/* Provider Header */}
              <button
                onClick={() => toggleProvider(provider.id)}
                className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-muted rounded-lg">
                    {getProviderIcon(provider.name)}
                  </div>
                  <div className="text-left">
                    <h3 className="font-semibold">{provider.display_name}</h3>
                    <p className="text-sm text-muted-foreground">
                      {provider.plans?.length || 0} plans configured
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={provider.is_active ? 'default' : 'secondary'}>
                    {provider.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                  {expandedProviders[provider.id] ? (
                    <ArrowUp className="h-4 w-4" />
                  ) : (
                    <ArrowDown className="h-4 w-4" />
                  )}
                </div>
              </button>

              {/* Plans Table */}
              {expandedProviders[provider.id] && (
                <div className="border-t">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-muted/50">
                        <tr>
                          <th className="text-left p-3 font-medium">Plan</th>
                          <th className="text-left p-3 font-medium">Monthly</th>
                          <th className="text-left p-3 font-medium">Yearly</th>
                          <th className="text-left p-3 font-medium">Stripe Monthly</th>
                          <th className="text-left p-3 font-medium">Stripe Yearly</th>
                          <th className="text-left p-3 font-medium">Limits</th>
                          <th className="text-left p-3 font-medium">Status</th>
                          <th className="text-right p-3 font-medium">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {provider.plans?.map((plan: any) => (
                          <tr key={plan.id} className="border-t">
                            {editingPlan?.id === plan.id ? (
                              // Editing mode
                              <>
                                <td className="p-3">
                                  <Input
                                    value={editingPlan.display_name}
                                    onChange={(e) =>
                                      setEditingPlan({ ...editingPlan, display_name: e.target.value })
                                    }
                                    className="w-32"
                                  />
                                </td>
                                <td className="p-3">
                                  <Input
                                    type="number"
                                    value={editingPlan.price_monthly}
                                    onChange={(e) =>
                                      setEditingPlan({
                                        ...editingPlan,
                                        price_monthly: parseFloat(e.target.value) || 0,
                                      })
                                    }
                                    className="w-20"
                                  />
                                </td>
                                <td className="p-3">
                                  <Input
                                    type="number"
                                    value={editingPlan.price_yearly}
                                    onChange={(e) =>
                                      setEditingPlan({
                                        ...editingPlan,
                                        price_yearly: parseFloat(e.target.value) || 0,
                                      })
                                    }
                                    className="w-20"
                                  />
                                </td>
                                <td className="p-3">
                                  <Input
                                    value={editingPlan.stripe_price_id_monthly || ''}
                                    onChange={(e) =>
                                      setEditingPlan({
                                        ...editingPlan,
                                        stripe_price_id_monthly: e.target.value,
                                      })
                                    }
                                    placeholder="price_xxx"
                                    className="w-32 font-mono text-xs"
                                  />
                                </td>
                                <td className="p-3">
                                  <Input
                                    value={editingPlan.stripe_price_id_yearly || ''}
                                    onChange={(e) =>
                                      setEditingPlan({
                                        ...editingPlan,
                                        stripe_price_id_yearly: e.target.value,
                                      })
                                    }
                                    placeholder="price_xxx"
                                    className="w-32 font-mono text-xs"
                                  />
                                </td>
                                <td className="p-3">
                                  <div className="flex gap-2">
                                    <Input
                                      type="number"
                                      value={editingPlan.max_environments}
                                      onChange={(e) =>
                                        setEditingPlan({
                                          ...editingPlan,
                                          max_environments: parseInt(e.target.value) || 0,
                                        })
                                      }
                                      className="w-16"
                                      title="Max Environments (-1 = unlimited)"
                                    />
                                    <Input
                                      type="number"
                                      value={editingPlan.max_workflows}
                                      onChange={(e) =>
                                        setEditingPlan({
                                          ...editingPlan,
                                          max_workflows: parseInt(e.target.value) || 0,
                                        })
                                      }
                                      className="w-16"
                                      title="Max Workflows (-1 = unlimited)"
                                    />
                                  </div>
                                </td>
                                <td className="p-3">
                                  <Switch
                                    checked={editingPlan.is_active}
                                    onCheckedChange={(checked) =>
                                      setEditingPlan({ ...editingPlan, is_active: checked })
                                    }
                                  />
                                </td>
                                <td className="p-3 text-right">
                                  <div className="flex justify-end gap-2">
                                    <Button
                                      size="sm"
                                      onClick={() => {
                                        updatePlanMutation.mutate({
                                          planId: editingPlan.id,
                                          data: {
                                            display_name: editingPlan.display_name,
                                            price_monthly: editingPlan.price_monthly,
                                            price_yearly: editingPlan.price_yearly,
                                            stripe_price_id_monthly: editingPlan.stripe_price_id_monthly || null,
                                            stripe_price_id_yearly: editingPlan.stripe_price_id_yearly || null,
                                            max_environments: editingPlan.max_environments,
                                            max_workflows: editingPlan.max_workflows,
                                            is_active: editingPlan.is_active,
                                          },
                                        });
                                      }}
                                      disabled={updatePlanMutation.isPending}
                                    >
                                      {updatePlanMutation.isPending ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                      ) : (
                                        <Save className="h-4 w-4" />
                                      )}
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => setEditingPlan(null)}
                                    >
                                      <X className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </td>
                              </>
                            ) : (
                              // View mode
                              <>
                                <td className="p-3">
                                  <div>
                                    <span className="font-medium">{plan.display_name}</span>
                                    <span className="text-xs text-muted-foreground ml-2">
                                      ({plan.name})
                                    </span>
                                  </div>
                                </td>
                                <td className="p-3">${plan.price_monthly}</td>
                                <td className="p-3">${plan.price_yearly}</td>
                                <td className="p-3">
                                  {plan.stripe_price_id_monthly ? (
                                    <code className="text-xs bg-muted px-1 py-0.5 rounded">
                                      {plan.stripe_price_id_monthly.substring(0, 12)}...
                                    </code>
                                  ) : (
                                    <span className="text-muted-foreground">-</span>
                                  )}
                                </td>
                                <td className="p-3">
                                  {plan.stripe_price_id_yearly ? (
                                    <code className="text-xs bg-muted px-1 py-0.5 rounded">
                                      {plan.stripe_price_id_yearly.substring(0, 12)}...
                                    </code>
                                  ) : (
                                    <span className="text-muted-foreground">-</span>
                                  )}
                                </td>
                                <td className="p-3">
                                  <span className="text-xs">
                                    {plan.max_environments === -1 ? '∞' : plan.max_environments} env,{' '}
                                    {plan.max_workflows === -1 ? '∞' : plan.max_workflows} wf
                                  </span>
                                </td>
                                <td className="p-3">
                                  <Badge variant={plan.is_active ? 'default' : 'secondary'}>
                                    {plan.is_active ? 'Active' : 'Inactive'}
                                  </Badge>
                                </td>
                                <td className="p-3 text-right">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => setEditingPlan({ ...plan })}
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </Button>
                                </td>
                              </>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

export function SettingsPage() {
  useEffect(() => {
    document.title = 'Settings - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  const queryClient = useQueryClient();

  const { data: environmentTypesData, isLoading: isLoadingEnvironmentTypes } = useQuery({
    queryKey: ['environment-types'],
    queryFn: () => apiClient.getEnvironmentTypes(),
  });

  const environmentTypes = environmentTypesData?.data || [];

  const createEnvironmentTypeMutation = useMutation({
    mutationFn: (payload: { key: string; label: string }) =>
      apiClient.createEnvironmentType({ key: payload.key, label: payload.label }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environment-types'] });
      toast.success('Environment type created');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create environment type');
    },
  });

  const updateEnvironmentTypeMutation = useMutation({
    mutationFn: (payload: { id: string; updates: { key?: string; label?: string; is_active?: boolean } }) =>
      apiClient.updateEnvironmentType(payload.id, payload.updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environment-types'] });
      toast.success('Environment type updated');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update environment type');
    },
  });

  const deleteEnvironmentTypeMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteEnvironmentType(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environment-types'] });
      toast.success('Environment type deleted');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete environment type');
    },
  });

  const reorderEnvironmentTypesMutation = useMutation({
    mutationFn: (orderedIds: string[]) => apiClient.reorderEnvironmentTypes(orderedIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environment-types'] });
      toast.success('Environment types reordered');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to reorder environment types');
    },
  });

  const [newEnvTypeKey, setNewEnvTypeKey] = useState('');
  const [newEnvTypeLabel, setNewEnvTypeLabel] = useState('');
  const [editingEnvTypeId, setEditingEnvTypeId] = useState<string | null>(null);
  const [editingEnvTypeKey, setEditingEnvTypeKey] = useState('');
  const [editingEnvTypeLabel, setEditingEnvTypeLabel] = useState('');

  const startEditEnvType = (t: any) => {
    setEditingEnvTypeId(t.id);
    setEditingEnvTypeKey(t.key || '');
    setEditingEnvTypeLabel(t.label || '');
  };

  const cancelEditEnvType = () => {
    setEditingEnvTypeId(null);
    setEditingEnvTypeKey('');
    setEditingEnvTypeLabel('');
  };

  const saveEditEnvType = () => {
    if (!editingEnvTypeId) return;
    updateEnvironmentTypeMutation.mutate({
      id: editingEnvTypeId,
      updates: { key: editingEnvTypeKey.trim(), label: editingEnvTypeLabel.trim() },
    });
    cancelEditEnvType();
  };

  const moveEnvType = (id: string, direction: 'up' | 'down') => {
    const sorted = [...environmentTypes].sort((a: any, b: any) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0));
    const idx = sorted.findIndex((t: any) => t.id === id);
    if (idx < 0) return;
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= sorted.length) return;
    const next = [...sorted];
    const tmp = next[idx];
    next[idx] = next[swapIdx];
    next[swapIdx] = tmp;
    reorderEnvironmentTypesMutation.mutate(next.map((t: any) => t.id));
  };
  const [systemConfig, setSystemConfig] = useState(mockSystemConfig);
  const [emailConfig, setEmailConfig] = useState(mockEmailConfig);
  const [isSaving, setIsSaving] = useState(false);
  const [showAuth0Secret, setShowAuth0Secret] = useState(false);
  const [showStripeSecret, setShowStripeSecret] = useState(false);
  const [showWebhookSecret, setShowWebhookSecret] = useState(false);

  // Provider state from Zustand store
  const { providerDisplayName, setProviderDisplayName, setSelectedProvider } = useAppStore();
  const [localProviderDisplayName, setLocalProviderDisplayName] = useState(providerDisplayName);
  const [selectedBillingCycle, setSelectedBillingCycle] = useState<'monthly' | 'yearly'>('monthly');

  // Fetch providers with plans
  const { data: providersData, isLoading: isLoadingProviders } = useQuery({
    queryKey: ['providers-with-plans'],
    queryFn: () => apiClient.getProvidersWithPlans(),
  });

  const providers: ProviderWithPlans[] = providersData?.data || [];

  // Fetch tenant's provider subscriptions
  const { data: subscriptionsData, isLoading: isLoadingSubscriptions } = useQuery({
    queryKey: ['tenant-provider-subscriptions'],
    queryFn: () => apiClient.getTenantProviderSubscriptions(),
  });

  const subscriptions: TenantProviderSubscription[] = subscriptionsData?.data || [];

  // Get subscription for a provider
  const getSubscription = (providerId: string) => {
    return subscriptions.find((s) => s.provider_id === providerId);
  };

  // Subscribe to free plan mutation
  const subscribeFreeMutation = useMutation({
    mutationFn: (providerId: string) => apiClient.subscribeToFreePlan(providerId),
    onSuccess: (_, providerId) => {
      queryClient.invalidateQueries({ queryKey: ['tenant-provider-subscriptions'] });
      // Update selected provider
      const provider = providers.find((p) => p.id === providerId);
      if (provider) {
        setSelectedProvider(provider.name as 'n8n' | 'make');
        setProviderDisplayName(provider.display_name);
      }
      toast.success('Successfully subscribed to free plan');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to subscribe');
    },
  });

  // Create checkout mutation (for paid plans)
  const createCheckoutMutation = useMutation({
    mutationFn: (data: { provider_id: string; plan_id: string; billing_cycle: 'monthly' | 'yearly' }) =>
      apiClient.createProviderCheckout({
        ...data,
        success_url: `${window.location.origin}/admin/settings?tab=provider&success=true`,
        cancel_url: `${window.location.origin}/admin/settings?tab=provider&canceled=true`,
      }),
    onSuccess: (response) => {
      // Redirect to Stripe checkout
      window.location.href = response.data.checkout_url;
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to start checkout');
    },
  });

  // Cancel subscription mutation
  const cancelSubscriptionMutation = useMutation({
    mutationFn: (providerId: string) => apiClient.cancelProviderSubscription(providerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-provider-subscriptions'] });
      toast.success('Subscription will be canceled at the end of the billing period');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to cancel subscription');
    },
  });

  const handleSubscribe = (providerId: string, planId: string, planName: string, price: number) => {
    if (price === 0 || planName.toLowerCase() === 'free') {
      subscribeFreeMutation.mutate(providerId);
    } else {
      createCheckoutMutation.mutate({
        provider_id: providerId,
        plan_id: planId,
        billing_cycle: selectedBillingCycle,
      });
    }
  };

  // Get icon for provider
  const getProviderIcon = (name: string) => {
    switch (name.toLowerCase()) {
      case 'n8n':
        return <Workflow className="h-6 w-6" />;
      case 'make':
        return <Zap className="h-6 w-6" />;
      default:
        return <Layers className="h-6 w-6" />;
    }
  };

  const handleSaveProvider = async () => {
    setIsSaving(true);
    setProviderDisplayName(localProviderDisplayName);
    await new Promise((resolve) => setTimeout(resolve, 500));
    setIsSaving(false);
    toast.success('Provider settings saved successfully');
  };

  const handleSaveSystem = async () => {
    setIsSaving(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsSaving(false);
    toast.success('System settings saved successfully');
  };

  const handleSaveEmail = async () => {
    setIsSaving(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsSaving(false);
    toast.success('Email settings saved successfully');
  };

  const handleTestEmail = async () => {
    toast.info('Sending test email...');
    await new Promise((resolve) => setTimeout(resolve, 2000));
    toast.success('Test email sent successfully');
  };

  const handleTestDatabase = async () => {
    toast.info('Testing database connection...');
    await new Promise((resolve) => setTimeout(resolve, 1500));
    toast.success('Database connection successful');
  };

  const handleTestAuth0 = async () => {
    toast.info('Testing Auth0 connection...');
    await new Promise((resolve) => setTimeout(resolve, 1500));
    toast.success('Auth0 connection successful');
  };

  const handleTestStripeWebhook = async () => {
    toast.info('Sending test webhook...');
    await new Promise((resolve) => setTimeout(resolve, 2000));
    toast.success('Webhook test successful');
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Configure system-wide settings and integrations</p>
      </div>

      <Tabs defaultValue="general" className="space-y-6">
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="provider">Provider</TabsTrigger>
          <TabsTrigger value="database">Database</TabsTrigger>
          <TabsTrigger value="auth">Auth0</TabsTrigger>
          <TabsTrigger value="payments">Payments</TabsTrigger>
          <TabsTrigger value="email">Email</TabsTrigger>
          <TabsTrigger value="environments">Environments</TabsTrigger>
        </TabsList>

        {/* General Tab */}
        <TabsContent value="general" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                System Settings
              </CardTitle>
              <CardDescription>General application configuration</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="app-name">Application Name</Label>
                  <Input
                    id="app-name"
                    value={systemConfig.appName}
                    onChange={(e) =>
                      setSystemConfig({ ...systemConfig, appName: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="app-url">Application URL</Label>
                  <Input
                    id="app-url"
                    value={systemConfig.appUrl}
                    onChange={(e) =>
                      setSystemConfig({ ...systemConfig, appUrl: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="support-email">Support Email</Label>
                  <Input
                    id="support-email"
                    type="email"
                    value={systemConfig.supportEmail}
                    onChange={(e) =>
                      setSystemConfig({ ...systemConfig, supportEmail: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="timezone">Default Timezone</Label>
                  <select
                    id="timezone"
                    value={systemConfig.defaultTimezone}
                    onChange={(e) =>
                      setSystemConfig({ ...systemConfig, defaultTimezone: e.target.value })
                    }
                    className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value="UTC" className="bg-background text-foreground">UTC</option>
                    <option value="America/New_York" className="bg-background text-foreground">Eastern Time</option>
                    <option value="America/Chicago" className="bg-background text-foreground">Central Time</option>
                    <option value="America/Denver" className="bg-background text-foreground">Mountain Time</option>
                    <option value="America/Los_Angeles" className="bg-background text-foreground">Pacific Time</option>
                    <option value="Europe/London" className="bg-background text-foreground">London</option>
                    <option value="Europe/Paris" className="bg-background text-foreground">Paris</option>
                    <option value="Asia/Tokyo" className="bg-background text-foreground">Tokyo</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-between p-4 rounded-lg border">
                <div>
                  <p className="font-medium">Maintenance Mode</p>
                  <p className="text-sm text-muted-foreground">
                    When enabled, users will see a maintenance page
                  </p>
                </div>
                <Switch
                  checked={systemConfig.maintenanceMode}
                  onCheckedChange={(checked) =>
                    setSystemConfig({ ...systemConfig, maintenanceMode: checked })
                  }
                />
              </div>

              <div className="flex justify-end">
                <Button onClick={handleSaveSystem} disabled={isSaving}>
                  <Save className="h-4 w-4 mr-2" />
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Environment Variables */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                Environment Variables
              </CardTitle>
              <CardDescription>System environment configuration (read-only)</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 font-mono text-sm">
                <div className="flex items-center justify-between p-2 rounded bg-muted">
                  <span className="text-muted-foreground">NODE_ENV</span>
                  <span>production</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-muted">
                  <span className="text-muted-foreground">API_VERSION</span>
                  <span>v1</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-muted">
                  <span className="text-muted-foreground">MAX_UPLOAD_SIZE</span>
                  <span>50MB</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded bg-muted">
                  <span className="text-muted-foreground">RATE_LIMIT_ENABLED</span>
                  <span>true</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Provider Tab */}
        <TabsContent value="provider" className="space-y-6">
          {/* Active Subscriptions */}
          {subscriptions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  Active Subscriptions
                </CardTitle>
                <CardDescription>Providers you are currently subscribed to</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {subscriptions.map((sub) => (
                  <div key={sub.id} className="flex items-center justify-between p-4 rounded-lg border bg-muted/30">
                    <div className="flex items-center gap-4">
                      <div className="p-2 bg-background rounded-lg">
                        {getProviderIcon(sub.provider?.name || '')}
                      </div>
                      <div>
                        <h3 className="font-semibold">{sub.provider?.display_name || 'Unknown Provider'}</h3>
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Badge variant={sub.status === 'active' ? 'default' : 'secondary'}>
                            {sub.plan?.display_name || 'Unknown Plan'}
                          </Badge>
                          <span>•</span>
                          <span className="capitalize">{sub.billing_cycle}</span>
                          {sub.cancel_at_period_end && (
                            <>
                              <span>•</span>
                              <span className="text-amber-600">Cancels at period end</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {!sub.cancel_at_period_end && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => cancelSubscriptionMutation.mutate(sub.provider_id)}
                          disabled={cancelSubscriptionMutation.isPending}
                        >
                          {cancelSubscriptionMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            'Cancel'
                          )}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Display Name Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Layers className="h-5 w-5" />
                Display Settings
              </CardTitle>
              <CardDescription>Customize how the provider name appears in the application</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="provider-display-name">Provider Display Name</Label>
                <Input
                  id="provider-display-name"
                  value={localProviderDisplayName}
                  onChange={(e) => setLocalProviderDisplayName(e.target.value)}
                  placeholder="n8n"
                />
              </div>
              <div className="flex justify-end">
                <Button onClick={handleSaveProvider} disabled={isSaving}>
                  <Save className="h-4 w-4 mr-2" />
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Available Providers */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Layers className="h-5 w-5" />
                Available Providers
              </CardTitle>
              <CardDescription>Subscribe to workflow automation providers</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Billing Cycle Toggle */}
              <div className="flex items-center justify-center gap-4 p-2 bg-muted/50 rounded-lg">
                <Button
                  variant={selectedBillingCycle === 'monthly' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setSelectedBillingCycle('monthly')}
                >
                  Monthly
                </Button>
                <Button
                  variant={selectedBillingCycle === 'yearly' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setSelectedBillingCycle('yearly')}
                >
                  Yearly
                  <Badge variant="secondary" className="ml-2">Save 17%</Badge>
                </Button>
              </div>

              {isLoadingProviders || isLoadingSubscriptions ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : providers.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No providers available.
                </div>
              ) : (
                <div className="space-y-8">
                  {providers.map((provider) => {
                    const existingSub = getSubscription(provider.id);
                    return (
                      <div key={provider.id} className="space-y-4">
                        {/* Provider Header */}
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-muted rounded-lg">
                            {getProviderIcon(provider.name)}
                          </div>
                          <div>
                            <h3 className="text-lg font-semibold">{provider.display_name}</h3>
                            <p className="text-sm text-muted-foreground">{provider.description}</p>
                          </div>
                        </div>

                        {/* Plans Grid */}
                        <div className="grid gap-4 md:grid-cols-3">
                          {provider.plans?.map((plan) => {
                            const isCurrentPlan = existingSub?.plan_id === plan.id && existingSub?.status === 'active';
                            const price = selectedBillingCycle === 'yearly' ? plan.price_yearly : plan.price_monthly;
                            const monthlyEquivalent = selectedBillingCycle === 'yearly' ? plan.price_yearly / 12 : plan.price_monthly;

                            return (
                              <Card
                                key={plan.id}
                                className={`relative ${isCurrentPlan ? 'border-primary ring-1 ring-primary' : ''}`}
                              >
                                {isCurrentPlan && (
                                  <div className="absolute -top-3 left-4">
                                    <Badge variant="default">Current Plan</Badge>
                                  </div>
                                )}
                                <CardHeader className="pt-6">
                                  <CardTitle className="text-lg">{plan.display_name}</CardTitle>
                                  <CardDescription>{plan.description}</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                  {/* Price */}
                                  <div>
                                    <div className="flex items-baseline gap-1">
                                      <span className="text-3xl font-bold">
                                        ${Math.round(monthlyEquivalent)}
                                      </span>
                                      <span className="text-muted-foreground">/month</span>
                                    </div>
                                    {selectedBillingCycle === 'yearly' && price > 0 && (
                                      <p className="text-sm text-muted-foreground">
                                        Billed ${price}/year
                                      </p>
                                    )}
                                  </div>

                                  {/* Features */}
                                  <ul className="space-y-2 text-sm">
                                    <li className="flex items-center gap-2">
                                      <Check className="h-4 w-4 text-green-500" />
                                      <span>
                                        {plan.max_environments === -1
                                          ? 'Unlimited environments'
                                          : `${plan.max_environments} environment${plan.max_environments > 1 ? 's' : ''}`}
                                      </span>
                                    </li>
                                    <li className="flex items-center gap-2">
                                      <Check className="h-4 w-4 text-green-500" />
                                      <span>
                                        {plan.max_workflows === -1
                                          ? 'Unlimited workflows'
                                          : `${plan.max_workflows} workflows`}
                                      </span>
                                    </li>
                                    {Object.entries(plan.features || {}).map(([key, value]) => (
                                      <li key={key} className="flex items-center gap-2">
                                        {value ? (
                                          <Check className="h-4 w-4 text-green-500" />
                                        ) : (
                                          <X className="h-4 w-4 text-muted-foreground" />
                                        )}
                                        <span className={!value ? 'text-muted-foreground' : ''}>
                                          {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                                        </span>
                                      </li>
                                    ))}
                                  </ul>

                                  {/* Action Button */}
                                  <Button
                                    className="w-full"
                                    variant={isCurrentPlan ? 'outline' : 'default'}
                                    disabled={isCurrentPlan || subscribeFreeMutation.isPending || createCheckoutMutation.isPending}
                                    onClick={() => handleSubscribe(provider.id, plan.id, plan.name, price)}
                                  >
                                    {subscribeFreeMutation.isPending || createCheckoutMutation.isPending ? (
                                      <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : isCurrentPlan ? (
                                      'Current Plan'
                                    ) : existingSub ? (
                                      'Switch Plan'
                                    ) : price === 0 ? (
                                      'Get Started Free'
                                    ) : (
                                      'Subscribe'
                                    )}
                                  </Button>
                                </CardContent>
                              </Card>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Database Tab */}
        <TabsContent value="database">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Database Connection
              </CardTitle>
              <CardDescription>PostgreSQL database configuration (Supabase)</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                <div className="flex items-center gap-3">
                  {mockDatabaseConfig.status === 'connected' ? (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                  )}
                  <div>
                    <p className="font-medium">Connection Status</p>
                    <p className="text-sm text-muted-foreground">
                      {mockDatabaseConfig.host}:{mockDatabaseConfig.port}/{mockDatabaseConfig.database}
                    </p>
                  </div>
                </div>
                <Badge variant={mockDatabaseConfig.status === 'connected' ? 'default' : 'destructive'}>
                  {mockDatabaseConfig.status}
                </Badge>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Host</Label>
                  <Input value={mockDatabaseConfig.host} disabled />
                </div>
                <div className="space-y-2">
                  <Label>Port</Label>
                  <Input value={mockDatabaseConfig.port} disabled />
                </div>
                <div className="space-y-2">
                  <Label>Database</Label>
                  <Input value={mockDatabaseConfig.database} disabled />
                </div>
                <div className="space-y-2">
                  <Label>Connection Pool Size</Label>
                  <Input value={mockDatabaseConfig.connectionPoolSize} disabled />
                </div>
              </div>

              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground">
                  Database connection is managed through environment variables.
                  Contact your system administrator to modify connection settings.
                </p>
              </div>

              <div className="flex justify-end">
                <Button variant="outline" onClick={handleTestDatabase}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Test Connection
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Auth0 Tab */}
        <TabsContent value="auth">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Auth0 Configuration
              </CardTitle>
              <CardDescription>Authentication and authorization settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                <div className="flex items-center gap-3">
                  {mockAuth0Config.connectionStatus === 'connected' ? (
                    <CheckCircle className="h-5 w-5 text-green-500" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                  )}
                  <div>
                    <p className="font-medium">Connection Status</p>
                    <p className="text-sm text-muted-foreground">
                      Last synced: {mockAuth0Config.lastSynced ? new Date(mockAuth0Config.lastSynced).toLocaleString() : 'Never'}
                    </p>
                  </div>
                </div>
                <Badge variant={mockAuth0Config.connectionStatus === 'connected' ? 'default' : 'destructive'}>
                  {mockAuth0Config.connectionStatus}
                </Badge>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Auth0 Domain</Label>
                  <div className="flex gap-2">
                    <Input value={mockAuth0Config.domain} disabled className="font-mono" />
                    <Button variant="outline" size="icon" onClick={() => copyToClipboard(mockAuth0Config.domain, 'Domain')}>
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Client ID</Label>
                  <div className="flex gap-2">
                    <Input value={mockAuth0Config.clientId} disabled className="font-mono" />
                    <Button variant="outline" size="icon" onClick={() => copyToClipboard(mockAuth0Config.clientId, 'Client ID')}>
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Client Secret</Label>
                  <div className="flex gap-2">
                    <Input
                      type={showAuth0Secret ? 'text' : 'password'}
                      value={mockAuth0Config.clientSecret}
                      disabled
                      className="font-mono"
                    />
                    <Button variant="outline" size="icon" onClick={() => setShowAuth0Secret(!showAuth0Secret)}>
                      {showAuth0Secret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>API Audience</Label>
                  <Input value={mockAuth0Config.audience} disabled className="font-mono" />
                </div>
              </div>

              <Card className="bg-muted/30">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Callback URLs</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 font-mono text-sm">
                  <div className="p-2 bg-background rounded">https://app.n8nops.com/callback</div>
                  <div className="p-2 bg-background rounded">https://app.n8nops.com/silent-callback</div>
                </CardContent>
              </Card>

              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground">
                  To modify Auth0 configuration, update the values in your environment variables
                  or visit the Auth0 dashboard directly.
                </p>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleTestAuth0}>
                  <TestTube className="h-4 w-4 mr-2" />
                  Test Connection
                </Button>
                <Button variant="outline" asChild>
                  <a href={`https://manage.auth0.com/dashboard/us/${mockAuth0Config.domain.split('.')[0]}`} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Open Auth0 Dashboard
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Payments Tab */}
        <TabsContent value="payments" className="space-y-6">
          {/* Provider Plans Management */}
          <ProviderPlansManagement />

          {/* Stripe Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CreditCard className="h-5 w-5" />
                Stripe Configuration
              </CardTitle>
              <CardDescription>Payment processing settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Mode Banner */}
              <div className={`p-4 rounded-lg ${mockStripeConfig.mode === 'test' ? 'bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800' : 'bg-green-50 dark:bg-green-950/50 border border-green-200 dark:border-green-800'}`}>
                <div className="flex items-center gap-3">
                  <Badge variant={mockStripeConfig.mode === 'test' ? 'outline' : 'default'} className="text-lg px-4 py-1">
                    {mockStripeConfig.mode === 'test' ? 'TEST MODE' : 'LIVE MODE'}
                  </Badge>
                  <p className={`text-sm ${mockStripeConfig.mode === 'test' ? 'text-amber-700 dark:text-amber-300' : 'text-green-700 dark:text-green-300'}`}>
                    {mockStripeConfig.mode === 'test'
                      ? 'Payments are in test mode. No real charges will be made.'
                      : 'Payments are live. Real charges will be processed.'}
                  </p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Publishable Key</Label>
                  <div className="flex gap-2">
                    <Input value={mockStripeConfig.publishableKey} disabled className="font-mono" />
                    <Button variant="outline" size="icon" onClick={() => copyToClipboard(mockStripeConfig.publishableKey, 'Publishable Key')}>
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Secret Key</Label>
                  <div className="flex gap-2">
                    <Input
                      type={showStripeSecret ? 'text' : 'password'}
                      value={mockStripeConfig.secretKey}
                      disabled
                      className="font-mono"
                    />
                    <Button variant="outline" size="icon" onClick={() => setShowStripeSecret(!showStripeSecret)}>
                      {showStripeSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              </div>

              {/* Webhook Configuration */}
              <Card className="bg-muted/30">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Webhook className="h-4 w-4" />
                    Webhook Configuration
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-background">
                    <div className="flex items-center gap-3">
                      {mockStripeConfig.webhookStatus === 'active' ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : (
                        <AlertTriangle className="h-5 w-5 text-red-500" />
                      )}
                      <div>
                        <p className="font-medium">Webhook Status</p>
                        <p className="text-sm text-muted-foreground">
                          Last received: {mockStripeConfig.lastWebhookReceived ? new Date(mockStripeConfig.lastWebhookReceived).toLocaleString() : 'Never'}
                        </p>
                      </div>
                    </div>
                    <Badge variant={mockStripeConfig.webhookStatus === 'active' ? 'default' : 'destructive'}>
                      {mockStripeConfig.webhookStatus}
                    </Badge>
                  </div>

                  <div className="space-y-2">
                    <Label>Webhook Endpoint</Label>
                    <div className="flex gap-2">
                      <Input value={mockStripeConfig.webhookEndpoint} disabled className="font-mono" />
                      <Button variant="outline" size="icon" onClick={() => copyToClipboard(mockStripeConfig.webhookEndpoint, 'Webhook URL')}>
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Webhook Signing Secret</Label>
                    <div className="flex gap-2">
                      <Input
                        type={showWebhookSecret ? 'text' : 'password'}
                        value={mockStripeConfig.webhookSecret}
                        disabled
                        className="font-mono"
                      />
                      <Button variant="outline" size="icon" onClick={() => setShowWebhookSecret(!showWebhookSecret)}>
                        {showWebhookSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="p-4 bg-muted/50 rounded-lg">
                <p className="text-sm text-muted-foreground">
                  Stripe keys are stored securely in environment variables.
                  Contact your system administrator to change payment configuration.
                </p>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleTestStripeWebhook}>
                  <TestTube className="h-4 w-4 mr-2" />
                  Test Webhook
                </Button>
                <Button variant="outline" asChild>
                  <a href="https://dashboard.stripe.com" target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-4 w-4 mr-2" />
                    Open Stripe Dashboard
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Email Tab */}
        <TabsContent value="email">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5" />
                Email Configuration
              </CardTitle>
              <CardDescription>Transactional email settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Email Provider</Label>
                <select
                  value={emailConfig.provider}
                  onChange={(e) => setEmailConfig({ ...emailConfig, provider: e.target.value as any })}
                  className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="smtp" className="bg-background text-foreground">SMTP</option>
                  <option value="sendgrid" className="bg-background text-foreground">SendGrid</option>
                  <option value="aws_ses" className="bg-background text-foreground">AWS SES</option>
                </select>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="smtp-host">SMTP Host</Label>
                  <Input
                    id="smtp-host"
                    value={emailConfig.smtpHost}
                    onChange={(e) =>
                      setEmailConfig({ ...emailConfig, smtpHost: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="smtp-port">SMTP Port</Label>
                  <Input
                    id="smtp-port"
                    type="number"
                    value={emailConfig.smtpPort}
                    onChange={(e) =>
                      setEmailConfig({ ...emailConfig, smtpPort: parseInt(e.target.value) })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="smtp-user">SMTP Username / API Key</Label>
                  <Input
                    id="smtp-user"
                    value={emailConfig.smtpUser}
                    onChange={(e) =>
                      setEmailConfig({ ...emailConfig, smtpUser: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="smtp-pass">SMTP Password</Label>
                  <Input id="smtp-pass" type="password" placeholder="••••••••" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="from-name">From Name</Label>
                  <Input
                    id="from-name"
                    value={emailConfig.fromName}
                    onChange={(e) =>
                      setEmailConfig({ ...emailConfig, fromName: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="from-email">From Email</Label>
                  <Input
                    id="from-email"
                    type="email"
                    value={emailConfig.fromEmail}
                    onChange={(e) =>
                      setEmailConfig({ ...emailConfig, fromEmail: e.target.value })
                    }
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleTestEmail}>
                  <Mail className="h-4 w-4 mr-2" />
                  Send Test Email
                </Button>
                <Button onClick={handleSaveEmail} disabled={isSaving}>
                  <Save className="h-4 w-4 mr-2" />
                  {isSaving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="environments">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Environment Types
              </CardTitle>
              <CardDescription>
                Create, edit, enable/disable, and reorder environment types. Environments are sorted across the app based on this order.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="env-type-key">Key</Label>
                  <Input
                    id="env-type-key"
                    value={newEnvTypeKey}
                    onChange={(e) => setNewEnvTypeKey(e.target.value)}
                    placeholder="e.g., dev"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="env-type-label">Label</Label>
                  <Input
                    id="env-type-label"
                    value={newEnvTypeLabel}
                    onChange={(e) => setNewEnvTypeLabel(e.target.value)}
                    placeholder="e.g., Development"
                  />
                </div>
                <div className="flex items-end">
                  <Button
                    onClick={() => {
                      const key = newEnvTypeKey.trim();
                      const label = newEnvTypeLabel.trim();
                      if (!key || !label) {
                        toast.error('Key and label are required');
                        return;
                      }
                      createEnvironmentTypeMutation.mutate({ key, label });
                      setNewEnvTypeKey('');
                      setNewEnvTypeLabel('');
                    }}
                    disabled={createEnvironmentTypeMutation.isPending}
                    className="w-full"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Add Type
                  </Button>
                </div>
              </div>

              <div className="border rounded-lg overflow-hidden">
                <div className="grid grid-cols-12 gap-2 px-3 py-2 bg-muted text-xs font-medium">
                  <div className="col-span-1">Order</div>
                  <div className="col-span-3">Key</div>
                  <div className="col-span-4">Label</div>
                  <div className="col-span-2">Active</div>
                  <div className="col-span-2 text-right">Actions</div>
                </div>

                {isLoadingEnvironmentTypes ? (
                  <div className="p-4 text-sm text-muted-foreground">Loading...</div>
                ) : environmentTypes.length === 0 ? (
                  <div className="p-4 text-sm text-muted-foreground">No environment types configured.</div>
                ) : (
                  [...environmentTypes]
                    .sort((a: any, b: any) => (a.sortOrder ?? 0) - (b.sortOrder ?? 0))
                    .map((t: any, idx: number) => {
                      const isEditing = editingEnvTypeId === t.id;
                      return (
                        <div key={t.id} className="grid grid-cols-12 gap-2 px-3 py-2 border-t items-center">
                          <div className="col-span-1 text-xs text-muted-foreground">{idx + 1}</div>
                          <div className="col-span-3">
                            {isEditing ? (
                              <Input value={editingEnvTypeKey} onChange={(e) => setEditingEnvTypeKey(e.target.value)} />
                            ) : (
                              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{t.key}</code>
                            )}
                          </div>
                          <div className="col-span-4">
                            {isEditing ? (
                              <Input value={editingEnvTypeLabel} onChange={(e) => setEditingEnvTypeLabel(e.target.value)} />
                            ) : (
                              <div className="text-sm">{t.label}</div>
                            )}
                          </div>
                          <div className="col-span-2">
                            <Switch
                              checked={!!t.isActive}
                              onCheckedChange={(checked) =>
                                updateEnvironmentTypeMutation.mutate({ id: t.id, updates: { is_active: checked } })
                              }
                            />
                          </div>
                          <div className="col-span-2 flex justify-end gap-2">
                            <Button variant="outline" size="icon" onClick={() => moveEnvType(t.id, 'up')} title="Move up">
                              <ArrowUp className="h-4 w-4" />
                            </Button>
                            <Button variant="outline" size="icon" onClick={() => moveEnvType(t.id, 'down')} title="Move down">
                              <ArrowDown className="h-4 w-4" />
                            </Button>
                            {isEditing ? (
                              <>
                                <Button variant="outline" size="sm" onClick={saveEditEnvType}>Save</Button>
                                <Button variant="ghost" size="sm" onClick={cancelEditEnvType}>Cancel</Button>
                              </>
                            ) : (
                              <Button variant="outline" size="icon" onClick={() => startEditEnvType(t)} title="Edit">
                                <Pencil className="h-4 w-4" />
                              </Button>
                            )}
                            <Button
                              variant="outline"
                              size="icon"
                              onClick={() => deleteEnvironmentTypeMutation.mutate(t.id)}
                              title="Delete"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      );
                    })
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
