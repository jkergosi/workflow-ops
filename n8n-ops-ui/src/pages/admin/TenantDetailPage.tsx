import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  ArrowLeft,
  Building2,
  Users,
  CreditCard,
  BarChart3,
  FileText,
  Shield,
  RefreshCw,
  Edit,
  Trash2,
  Ban,
  PlayCircle,
  Calendar,
  AlertTriangle,
  ExternalLink,
  Copy,
  Plus,
  CheckCircle,
  XCircle,
  Workflow,
  MoreHorizontal,
  ArrowUpCircle,
  Loader2,
  Sparkles,
  Crown,
  Zap,
  Search,
  UserCog,
  MoreVertical,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import type { Tenant, TenantNote, TenantFeatureOverride, Provider, TenantProviderSubscriptionSummary, ProviderWithPlans, ProviderPlan } from '@/types';

const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  trial: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  suspended: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  cancelled: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
  archived: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
};

const planColors: Record<string, string> = {
  free: 'bg-gray-100 text-gray-800',
  pro: 'bg-blue-100 text-blue-800',
  agency: 'bg-purple-100 text-purple-800',
  enterprise: 'bg-indigo-100 text-indigo-800',
};

export function TenantDetailPage() {
  useEffect(() => {
    document.title = 'Tenant Details - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);
  const { tenantId } = useParams<{ tenantId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(() => searchParams.get('tab') || 'overview');
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [suspendDialogOpen, setSuspendDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [noteContent, setNoteContent] = useState('');
  const [providerFilter, setProviderFilter] = useState<Provider | 'all'>('all');
  
  // Subscriptions tab state
  const [addProviderDialogOpen, setAddProviderDialogOpen] = useState(false);
  const [changePlanDialogOpen, setChangePlanDialogOpen] = useState(false);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [selectedSubscription, setSelectedSubscription] = useState<TenantProviderSubscriptionSummary | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<ProviderWithPlans | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<ProviderPlan | null>(null);

  // Users & Roles tab state
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('joined');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [usersPage, setUsersPage] = useState(1);
  const [impersonateDialogOpen, setImpersonateDialogOpen] = useState(false);
  const [suspendUserDialogOpen, setSuspendUserDialogOpen] = useState(false);
  const [unsuspendUserDialogOpen, setUnsuspendUserDialogOpen] = useState(false);
  const [roleChangeDialogOpen, setRoleChangeDialogOpen] = useState(false);
  const [removeUserDialogOpen, setRemoveUserDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [newRole, setNewRole] = useState<string>('');

  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
    primaryContactName: '',
  });

  // Fetch tenant details
  const { data: tenantData, isLoading } = useQuery({
    queryKey: ['tenant', tenantId],
    queryFn: () => apiClient.getTenantById(tenantId!),
    enabled: !!tenantId,
  });

  // Fetch tenant usage
  const { data: usageData } = useQuery({
    queryKey: ['tenant-usage', tenantId, providerFilter],
    queryFn: () => apiClient.getTenantUsage(tenantId!, providerFilter),
    enabled: !!tenantId && activeTab === 'usage',
  });

  // Fetch tenant notes
  const { data: notesData, refetch: refetchNotes } = useQuery({
    queryKey: ['tenant-notes', tenantId],
    queryFn: () => apiClient.getTenantNotes(tenantId!),
    enabled: !!tenantId && activeTab === 'notes',
  });

  // Fetch tenant overrides
  const { data: overridesData } = useQuery({
    queryKey: ['tenant-overrides', tenantId],
    queryFn: () => apiClient.getTenantOverrides(tenantId!),
    enabled: !!tenantId && activeTab === 'features',
  });

  // Fetch providers with plans for subscriptions tab
  const { data: providersData } = useQuery({
    queryKey: ['providers-with-plans'],
    queryFn: () => apiClient.getProvidersWithPlans(),
    enabled: !!tenantId && activeTab === 'subscriptions',
  });

  // Fetch tenant users for users tab
  const { data: usersData, isLoading: usersLoading, refetch: refetchUsers } = useQuery({
    queryKey: ['tenant-users', tenantId, searchQuery, roleFilter, statusFilter, sortBy, sortOrder, usersPage],
    queryFn: () => apiClient.getPlatformTenantUsers(tenantId!, {
      search: searchQuery || undefined,
      role: roleFilter !== 'all' ? roleFilter : undefined,
      status: statusFilter !== 'all' ? statusFilter : undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
      page: usersPage,
      page_size: 50,
    }),
    enabled: !!tenantId && activeTab === 'users',
  });

  const tenant = tenantData?.data;
  const usage = usageData?.data;
  const notes = notesData?.data?.notes || [];
  const overrides = overridesData?.data?.overrides || [];
  const providers = providersData?.data || [];
  const subscriptions = (tenant as any)?.providerSubscriptions || [];
  const users = usersData?.data?.users || [];
  const totalUsers = usersData?.data?.total || 0;
  
  // Find providers not yet subscribed
  const subscribedProviderIds = subscriptions.map((s: TenantProviderSubscriptionSummary) => s.provider_id);
  const availableProviders = providers.filter(
    (p: ProviderWithPlans) => !subscribedProviderIds.includes(p.id) && p.is_active
  );

  // Mutations
  const updateMutation = useMutation({
    mutationFn: (updates: Partial<Tenant>) => apiClient.updateTenant(tenantId!, updates),
    onSuccess: () => {
      toast.success('Tenant updated successfully');
      queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] });
      setEditDialogOpen(false);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update tenant');
    },
  });

  const suspendMutation = useMutation({
    mutationFn: () => apiClient.suspendTenant(tenantId!),
    onSuccess: () => {
      toast.success('Tenant suspended');
      queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] });
      setSuspendDialogOpen(false);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to suspend tenant');
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: () => apiClient.reactivateTenant(tenantId!),
    onSuccess: () => {
      toast.success('Tenant reactivated');
      queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to reactivate tenant');
    },
  });

  const scheduleDeletionMutation = useMutation({
    mutationFn: (days: number) => apiClient.scheduleTenantDeletion(tenantId!, days),
    onSuccess: (data) => {
      toast.success(`Deletion scheduled for ${new Date(data.data.scheduled_deletion_at).toLocaleDateString()}`);
      queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] });
      setDeleteDialogOpen(false);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to schedule deletion');
    },
  });

  const createNoteMutation = useMutation({
    mutationFn: (content: string) => apiClient.createTenantNote(tenantId!, content),
    onSuccess: () => {
      toast.success('Note added');
      setNoteContent('');
      refetchNotes();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to add note');
    },
  });

  const deleteNoteMutation = useMutation({
    mutationFn: (noteId: string) => apiClient.deleteTenantNote(tenantId!, noteId),
    onSuccess: () => {
      toast.success('Note deleted');
      refetchNotes();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete note');
    },
  });

  // Subscriptions mutations
  const createSubscriptionMutation = useMutation({
    mutationFn: ({ providerId, planId, billingCycle }: { providerId: string; planId: string; billingCycle: 'monthly' | 'yearly' }) =>
      apiClient.createTenantProviderSubscription(tenantId!, providerId, planId, billingCycle),
    onSuccess: () => {
      toast.success('Provider subscription created');
      queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] });
      setAddProviderDialogOpen(false);
      setSelectedProvider(null);
      setSelectedPlan(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create subscription');
    },
  });

  const updateSubscriptionMutation = useMutation({
    mutationFn: ({ providerId, updates }: { providerId: string; updates: { plan_id?: string; cancel_at_period_end?: boolean } }) =>
      apiClient.updateTenantProviderSubscription(tenantId!, providerId, updates),
    onSuccess: () => {
      toast.success('Subscription updated');
      queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] });
      setChangePlanDialogOpen(false);
      setSelectedSubscription(null);
      setSelectedPlan(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update subscription');
    },
  });

  const cancelSubscriptionMutation = useMutation({
    mutationFn: ({ providerId, atPeriodEnd }: { providerId: string; atPeriodEnd: boolean }) =>
      apiClient.cancelTenantProviderSubscription(tenantId!, providerId, atPeriodEnd),
    onSuccess: () => {
      toast.success('Subscription canceled');
      queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] });
      setCancelDialogOpen(false);
      setSelectedSubscription(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to cancel subscription');
    },
  });

  // Users mutations
  const impersonateUserMutation = useMutation({
    mutationFn: (userId: string) => apiClient.impersonatePlatformTenantUser(tenantId!, userId),
    onSuccess: () => {
      toast.success('Impersonation started');
      setImpersonateDialogOpen(false);
      window.location.reload();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to start impersonation');
    },
  });

  const suspendUserMutation = useMutation({
    mutationFn: (userId: string) => apiClient.suspendPlatformTenantUser(tenantId!, userId),
    onSuccess: () => {
      toast.success('User suspended');
      setSuspendUserDialogOpen(false);
      refetchUsers();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to suspend user');
    },
  });

  const unsuspendUserMutation = useMutation({
    mutationFn: (userId: string) => apiClient.unsuspendPlatformTenantUser(tenantId!, userId),
    onSuccess: () => {
      toast.success('User unsuspended');
      setUnsuspendUserDialogOpen(false);
      refetchUsers();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to unsuspend user');
    },
  });

  const changeUserRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      apiClient.changePlatformTenantUserRole(tenantId!, userId, role),
    onSuccess: () => {
      toast.success('User role changed');
      setRoleChangeDialogOpen(false);
      refetchUsers();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to change user role');
    },
  });

  const removeUserMutation = useMutation({
    mutationFn: (userId: string) => apiClient.removePlatformTenantUser(tenantId!, userId),
    onSuccess: () => {
      toast.success('User removed from tenant');
      setRemoveUserDialogOpen(false);
      refetchUsers();
      queryClient.invalidateQueries({ queryKey: ['tenant', tenantId] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to remove user');
    },
  });

  const handleEditOpen = () => {
    if (tenant) {
      setEditForm({
        name: tenant.name,
        email: tenant.email,
        primaryContactName: tenant.primaryContactName || '',
      });
      setEditDialogOpen(true);
    }
  };

  const handleUpdate = () => {
    updateMutation.mutate({
      name: editForm.name,
      email: editForm.email,
      primary_contact_name: editForm.primaryContactName || undefined,
    } as any);
  };

  const formatDateTime = (dateString?: string) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  // Handle tab change with URL param
  const handleTabChange = (value: string) => {
    setActiveTab(value);
    if (value === 'subscriptions') {
      setSearchParams({ tab: 'subscriptions' });
    } else {
      setSearchParams({});
    }
  };

  // Subscriptions helper functions
  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getStatusBadge = (status: string, cancelAtPeriodEnd?: boolean) => {
    if (cancelAtPeriodEnd) {
      return <Badge variant="destructive">Canceling</Badge>;
    }
    switch (status) {
      case 'active':
        return <Badge variant="default" className="bg-green-600">Active</Badge>;
      case 'trialing':
        return <Badge variant="secondary">Trial</Badge>;
      case 'past_due':
        return <Badge variant="destructive">Past Due</Badge>;
      case 'canceled':
        return <Badge variant="outline">Canceled</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getPlanIcon = (planName: string) => {
    switch (planName) {
      case 'enterprise':
        return <Crown className="h-4 w-4 text-amber-500" />;
      case 'pro':
        return <Sparkles className="h-4 w-4 text-primary" />;
      default:
        return <Zap className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const handleAddProvider = () => {
    if (selectedProvider && selectedPlan) {
      createSubscriptionMutation.mutate({
        providerId: selectedProvider.id,
        planId: selectedPlan.id,
        billingCycle: 'monthly',
      });
    }
  };

  const handleChangePlan = () => {
    if (selectedSubscription && selectedPlan) {
      updateSubscriptionMutation.mutate({
        providerId: selectedSubscription.provider_id,
        updates: { plan_id: selectedPlan.id },
      });
    }
  };

  const handleCancelSubscription = () => {
    if (selectedSubscription) {
      cancelSubscriptionMutation.mutate({
        providerId: selectedSubscription.provider_id,
        atPeriodEnd: true,
      });
    }
  };

  // Users helper functions
  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'admin':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200';
      case 'developer':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'viewer':
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'inactive':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getUsageColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 75) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Loading tenant...</p>
      </div>
    );
  }

  if (!tenant) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Tenant not found</p>
        <Button variant="link" onClick={() => navigate('/admin/tenants')}>
          Back to Tenants
        </Button>
      </div>
    );
  }

  // Get plan name from provider subscriptions (new system) or fall back to deprecated fields
  const primarySubscription = subscriptions.find((s: TenantProviderSubscriptionSummary) => s.status === 'active');
  const planName = primarySubscription?.plan?.name || (tenant.subscriptionPlan || (tenant as any).subscription_plan || (tenant as any).subscription_tier || 'free') as string;
  const statusName = (tenant.status || (tenant as any).status || 'active') as string;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" aria-label="Back to Tenants" onClick={() => navigate('/admin/tenants')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{tenant.name}</h1>
              <Badge className={statusColors[statusName] || statusColors.active}>{statusName}</Badge>
              <Badge className={planColors[planName] || planColors.free}>{planName}</Badge>
            </div>
            <p className="text-muted-foreground">{tenant.email}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleEditOpen}>
            <Edit className="h-4 w-4 mr-2" />
            Edit
          </Button>
          {tenant.status === 'suspended' ? (
            <Button onClick={() => reactivateMutation.mutate()} disabled={reactivateMutation.isPending}>
              <PlayCircle className="h-4 w-4 mr-2" />
              Reactivate
            </Button>
          ) : tenant.status === 'active' ? (
            <Button variant="destructive" onClick={() => setSuspendDialogOpen(true)}>
              <Ban className="h-4 w-4 mr-2" />
              Suspend
            </Button>
          ) : null}
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="overview">
            <Building2 className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="users">
            <Users className="h-4 w-4 mr-2" />
            Users & Roles
          </TabsTrigger>
          <TabsTrigger value="features">
            <Shield className="h-4 w-4 mr-2" />
            Plan & Features
          </TabsTrigger>
          <TabsTrigger value="billing">
            <CreditCard className="h-4 w-4 mr-2" />
            Billing
          </TabsTrigger>
          <TabsTrigger value="subscriptions">
            <Workflow className="h-4 w-4 mr-2" />
            Subscriptions
          </TabsTrigger>
          <TabsTrigger value="usage">
            <BarChart3 className="h-4 w-4 mr-2" />
            Usage
          </TabsTrigger>
          <TabsTrigger value="notes">
            <FileText className="h-4 w-4 mr-2" />
            Notes
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            {/* Tenant Information */}
            <Card>
              <CardHeader>
                <CardTitle>Tenant Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-muted-foreground">Tenant ID</Label>
                  <div className="flex items-center gap-2">
                    <code className="text-sm bg-muted px-2 py-1 rounded">{tenant.id}</code>
                    <Button variant="ghost" size="icon" onClick={() => copyToClipboard(tenant.id)}>
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <div>
                  <Label className="text-muted-foreground">Name</Label>
                  <p className="font-medium">{tenant.name}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Email</Label>
                  <p className="font-medium">{tenant.email}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Created</Label>
                  <p className="font-medium">{formatDateTime(tenant.createdAt)}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Last Active</Label>
                  <p className="font-medium">{formatDateTime(tenant.lastActiveAt)}</p>
                </div>
              </CardContent>
            </Card>

            {/* Quick Stats */}
            <Card>
              <CardHeader>
                <CardTitle>Quick Stats</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <p className="text-3xl font-bold">{tenant.workflowCount}</p>
                    <p className="text-sm text-muted-foreground">Workflows</p>
                  </div>
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <p className="text-3xl font-bold">{tenant.environmentCount}</p>
                    <p className="text-sm text-muted-foreground">Environments</p>
                  </div>
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <p className="text-3xl font-bold">{tenant.userCount}</p>
                    <p className="text-sm text-muted-foreground">Users</p>
                  </div>
                  <div className="text-center p-4 bg-muted rounded-lg">
                    <Badge className={planColors[planName] || planColors.free} variant="outline">
                      {String(planName).toUpperCase()}
                    </Badge>
                    <p className="text-sm text-muted-foreground mt-1">Plan</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Actions */}
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>Actions</CardTitle>
                <CardDescription>Manage tenant lifecycle</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-3">
                  {tenant.status === 'active' && (
                    <Button variant="outline" onClick={() => setSuspendDialogOpen(true)}>
                      <Ban className="h-4 w-4 mr-2" />
                      Suspend Tenant
                    </Button>
                  )}
                  {tenant.status === 'suspended' && (
                    <Button variant="outline" onClick={() => reactivateMutation.mutate()}>
                      <PlayCircle className="h-4 w-4 mr-2" />
                      Reactivate Tenant
                    </Button>
                  )}
                  <Button variant="outline" onClick={() => setDeleteDialogOpen(true)}>
                    <Calendar className="h-4 w-4 mr-2" />
                    Schedule Deletion
                  </Button>
                  <Button variant="outline" asChild>
                    <Link to={`/admin/tenant-overrides?tenant=${tenantId}`}>
                      <Shield className="h-4 w-4 mr-2" />
                      Manage Overrides
                    </Link>
                  </Button>
                </div>
                {tenant.scheduledDeletionAt && (
                  <div className="mt-4 p-3 bg-destructive/10 rounded-lg flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-destructive" />
                    <span className="text-destructive">
                      Scheduled for deletion on {formatDateTime(tenant.scheduledDeletionAt)}
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Users & Roles Tab */}
        <TabsContent value="users" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Users & Roles</CardTitle>
              <CardDescription>
                Manage users and their roles for this tenant. All actions are audited.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Search and Filters */}
              <div className="flex gap-4 mb-6">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search by name or email..."
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        setUsersPage(1);
                      }}
                      className="pl-10"
                    />
                  </div>
                </div>
                <Select value={roleFilter} onValueChange={(value) => { setRoleFilter(value); setUsersPage(1); }}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="All Roles" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Roles</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                    <SelectItem value="developer">Developer</SelectItem>
                    <SelectItem value="viewer">Viewer</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={statusFilter} onValueChange={(value) => { setStatusFilter(value); setUsersPage(1); }}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue placeholder="All Statuses" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Table */}
              {usersLoading ? (
                <div className="flex items-center justify-center h-64">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : users.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-muted-foreground">No users found for this tenant.</p>
                </div>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>User</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Joined</TableHead>
                        <TableHead>Last Activity</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map((user: any) => (
                        <TableRow key={user.user_id}>
                          <TableCell>
                            <div>
                              <div className="font-medium">{user.name || user.email.split('@')[0]}</div>
                              <div className="text-sm text-muted-foreground">{user.email}</div>
                              {user.is_platform_admin && (
                                <Badge variant="outline" className="mt-1">Platform Admin</Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge className={getRoleBadgeColor(user.role_in_tenant)}>
                              {user.role_in_tenant}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Badge className={getStatusBadgeColor(user.status_in_tenant)}>
                              {user.status_in_tenant}
                            </Badge>
                          </TableCell>
                          <TableCell>{formatDateTime(user.joined_at)}</TableCell>
                          <TableCell>{formatDateTime(user.last_activity_at)}</TableCell>
                          <TableCell className="text-right">
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm">
                                  <MoreVertical className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem
                                  onClick={() => {
                                    setSelectedUser(user);
                                    setImpersonateDialogOpen(true);
                                  }}
                                >
                                  <UserCog className="h-4 w-4 mr-2" />
                                  Impersonate
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                  onClick={() => {
                                    setSelectedUser(user);
                                    setNewRole(user.role_in_tenant);
                                    setRoleChangeDialogOpen(true);
                                  }}
                                >
                                  <Edit className="h-4 w-4 mr-2" />
                                  Change Role
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                {user.status_in_tenant === 'active' ? (
                                  <DropdownMenuItem
                                    className="text-destructive"
                                    onClick={() => {
                                      setSelectedUser(user);
                                      setSuspendUserDialogOpen(true);
                                    }}
                                  >
                                    <Ban className="h-4 w-4 mr-2" />
                                    Suspend
                                  </DropdownMenuItem>
                                ) : user.status_in_tenant === 'inactive' ? (
                                  <DropdownMenuItem
                                    onClick={() => {
                                      setSelectedUser(user);
                                      setUnsuspendUserDialogOpen(true);
                                    }}
                                  >
                                    <CheckCircle className="h-4 w-4 mr-2" />
                                    Unsuspend
                                  </DropdownMenuItem>
                                ) : null}
                                <DropdownMenuItem
                                  className="text-destructive"
                                  onClick={() => {
                                    setSelectedUser(user);
                                    setRemoveUserDialogOpen(true);
                                  }}
                                >
                                  <Trash2 className="h-4 w-4 mr-2" />
                                  Remove
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Plan & Features Tab */}
        <TabsContent value="features" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Provider Subscriptions</CardTitle>
              <CardDescription>
                Active subscriptions for this tenant
              </CardDescription>
            </CardHeader>
            <CardContent>
              {subscriptions.length === 0 ? (
                <div className="text-center py-4">
                  <p className="text-muted-foreground">No provider subscriptions</p>
                  <Button variant="outline" className="mt-2" onClick={() => setActiveTab('subscriptions')}>
                    Add Provider Subscription
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {subscriptions.map((sub: TenantProviderSubscriptionSummary) => (
                    <div key={sub.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex items-center gap-4">
                        <Workflow className="h-6 w-6 text-orange-500" />
                        <div>
                          <p className="font-medium">{sub.provider?.display_name || sub.provider?.name}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge className={`${planColors[sub.plan?.name || 'free'] || planColors.free}`}>
                              {sub.plan?.display_name || sub.plan?.name || 'Free'}
                            </Badge>
                            <Badge variant={sub.status === 'active' ? 'default' : 'secondary'} className={sub.status === 'active' ? 'bg-green-600' : ''}>
                              {sub.status}
                            </Badge>
                          </div>
                        </div>
                      </div>
                      <Button variant="outline" size="sm" onClick={() => setActiveTab('subscriptions')}>
                        Manage
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Feature Overrides</CardTitle>
              <CardDescription>
                Custom feature settings for this tenant ({overrides.length} overrides)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {overrides.length === 0 ? (
                <p className="text-muted-foreground text-center py-4">
                  No feature overrides configured
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Feature</TableHead>
                      <TableHead>Value</TableHead>
                      <TableHead>Reason</TableHead>
                      <TableHead>Expires</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {overrides.map((override: TenantFeatureOverride) => (
                      <TableRow key={override.id}>
                        <TableCell>
                          <div>
                            <p className="font-medium">{override.featureDisplayName}</p>
                            <p className="text-xs text-muted-foreground">{override.featureKey}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          {override.value?.enabled !== undefined ? (
                            override.value.enabled ? (
                              <CheckCircle className="h-5 w-5 text-green-500" />
                            ) : (
                              <XCircle className="h-5 w-5 text-red-500" />
                            )
                          ) : (
                            <Badge variant="secondary">{override.value?.value}</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-muted-foreground">{override.reason || '-'}</TableCell>
                        <TableCell>{override.expiresAt ? formatDate(override.expiresAt) : 'Never'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
              <div className="mt-4">
                <Button variant="outline" asChild>
                  <Link to={`/admin/tenant-overrides`}>
                    <Plus className="h-4 w-4 mr-2" />
                    Manage Overrides
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Billing Tab */}
        <TabsContent value="billing">
          <Card>
            <CardHeader>
              <CardTitle>Billing Information</CardTitle>
              <CardDescription>Provider subscriptions and payment details</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {subscriptions.length > 0 ? (
                  <>
                    <div>
                      <Label className="text-muted-foreground">Active Subscriptions</Label>
                      <div className="space-y-2 mt-2">
                        {subscriptions.map((sub: TenantProviderSubscriptionSummary) => (
                          <div key={sub.id} className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                            <div className="flex items-center gap-3">
                              <Workflow className="h-5 w-5 text-orange-500" />
                              <div>
                                <p className="font-medium">{sub.provider?.display_name || sub.provider?.name}</p>
                                <p className="text-sm text-muted-foreground capitalize">{sub.plan?.display_name || sub.plan?.name || 'Free'}</p>
                              </div>
                            </div>
                            <Badge variant={sub.status === 'active' ? 'default' : 'secondary'} className={sub.status === 'active' ? 'bg-green-600' : ''}>
                              {sub.status}
                            </Badge>
                          </div>
                        ))}
                      </div>
                    </div>
                    <Button variant="outline" onClick={() => setActiveTab('subscriptions')}>
                      <CreditCard className="h-4 w-4 mr-2" />
                      Manage Subscriptions
                    </Button>
                  </>
                ) : (
                  <div className="text-center py-4">
                    <p className="text-muted-foreground">No provider subscriptions</p>
                    <Button variant="outline" className="mt-2" onClick={() => setActiveTab('subscriptions')}>
                      Add Provider Subscription
                    </Button>
                  </div>
                )}
                {tenant.stripeCustomerId && (
                  <div className="pt-4 border-t">
                    <Label className="text-muted-foreground">Stripe Customer ID</Label>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="text-sm bg-muted px-2 py-1 rounded">{tenant.stripeCustomerId}</code>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => window.open(`https://dashboard.stripe.com/customers/${tenant.stripeCustomerId}`, '_blank')}
                      >
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Subscriptions Tab */}
        <TabsContent value="subscriptions" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Workflow className="h-5 w-5" />
                    Provider Subscriptions
                  </CardTitle>
                  <CardDescription>
                    Manage provider subscriptions for this tenant
                  </CardDescription>
                </div>
                {availableProviders.length > 0 && (
                  <Button onClick={() => setAddProviderDialogOpen(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Provider
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {subscriptions.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Workflow className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="font-medium">No provider subscriptions</p>
                  <p className="text-sm">Add a provider to start managing workflows</p>
                  {availableProviders.length > 0 && (
                    <Button className="mt-4" onClick={() => setAddProviderDialogOpen(true)}>
                      <Plus className="h-4 w-4 mr-2" />
                      Add Provider
                    </Button>
                  )}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Provider</TableHead>
                      <TableHead>Plan</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Stripe Subscription</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {subscriptions.map((sub: TenantProviderSubscriptionSummary) => (
                      <TableRow key={sub.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Workflow className="h-5 w-5 text-orange-500" />
                            <span className="font-medium">{sub.provider?.display_name || sub.provider?.name || 'Unknown'}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getPlanIcon(sub.plan?.name || 'free')}
                            <span>{sub.plan?.display_name || 'Free'}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {getStatusBadge(sub.status)}
                        </TableCell>
                        <TableCell>
                          {sub.stripe_subscription_id ? (
                            <div className="flex items-center gap-2">
                              <code className="text-xs bg-muted px-2 py-1 rounded">{sub.stripe_subscription_id.substring(0, 20)}...</code>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                onClick={() => window.open(`https://dashboard.stripe.com/subscriptions/${sub.stripe_subscription_id}`, '_blank')}
                              >
                                <ExternalLink className="h-3 w-3" />
                              </Button>
                            </div>
                          ) : (
                            <span className="text-muted-foreground text-sm">N/A</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() => {
                                  setSelectedSubscription(sub);
                                  setChangePlanDialogOpen(true);
                                }}
                              >
                                <ArrowUpCircle className="h-4 w-4 mr-2" />
                                Change Plan
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              {sub.status === 'active' && (
                                <DropdownMenuItem
                                  className="text-destructive"
                                  onClick={() => {
                                    setSelectedSubscription(sub);
                                    setCancelDialogOpen(true);
                                  }}
                                >
                                  <XCircle className="h-4 w-4 mr-2" />
                                  Cancel Subscription
                                </DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Usage Tab */}
        <TabsContent value="usage">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Usage Metrics</CardTitle>
                  <CardDescription>Current usage vs plan limits</CardDescription>
                </div>
                <Select value={providerFilter} onValueChange={(value) => setProviderFilter(value as Provider | 'all')}>
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="All Providers" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Providers</SelectItem>
                    <SelectItem value="n8n">n8n</SelectItem>
                    <SelectItem value="make">Make</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent>
              {usage ? (
                <>
                  <div className="grid gap-6 md:grid-cols-2 mb-6">
                    {Object.entries(usage.metrics).map(([key, metric]) => (
                      <div key={key} className="space-y-2">
                        <div className="flex justify-between">
                          <Label className="capitalize">{key}</Label>
                          <span className="text-sm text-muted-foreground">
                            {metric.current} / {metric.limit === -1 ? 'Unlimited' : metric.limit}
                          </span>
                        </div>
                        <Progress
                          value={metric.limit === -1 ? 0 : metric.percentage}
                          className={`h-2 ${getUsageColor(metric.percentage)}`}
                        />
                        {metric.percentage >= 90 && metric.limit !== -1 && (
                          <p className="text-xs text-destructive flex items-center gap-1">
                            <AlertTriangle className="h-3 w-3" />
                            Near limit
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                  {providerFilter === 'all' && usage.byProvider && (
                    <div className="mt-6 space-y-4">
                      <h3 className="text-lg font-semibold">Breakdown by Provider</h3>
                      {Object.entries(usage.byProvider).map(([provider, providerMetrics]) => (
                        <div key={provider} className="border rounded-lg p-4 space-y-4">
                          <h4 className="font-medium capitalize">{provider}</h4>
                          <div className="grid gap-4 md:grid-cols-2">
                            {Object.entries(providerMetrics).map(([key, metric]) => (
                              <div key={key} className="space-y-2">
                                <div className="flex justify-between">
                                  <Label className="capitalize text-sm">{key}</Label>
                                  <span className="text-xs text-muted-foreground">
                                    {metric.current} / {metric.limit === -1 ? 'Unlimited' : metric.limit}
                                  </span>
                                </div>
                                <Progress
                                  value={metric.limit === -1 ? 0 : metric.percentage}
                                  className={`h-2 ${getUsageColor(metric.percentage)}`}
                                />
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-8">
                  <RefreshCw className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
                  <p className="mt-2 text-muted-foreground">Loading usage data...</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notes Tab */}
        <TabsContent value="notes" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Add Note</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Textarea
                  placeholder="Add an internal note about this tenant..."
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  rows={3}
                />
                <Button
                  onClick={() => createNoteMutation.mutate(noteContent)}
                  disabled={!noteContent.trim() || createNoteMutation.isPending}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Add Note
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notes History</CardTitle>
              <CardDescription>{notes.length} notes</CardDescription>
            </CardHeader>
            <CardContent>
              {notes.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">No notes yet</p>
              ) : (
                <div className="space-y-4">
                  {notes.map((note: TenantNote) => (
                    <div key={note.id} className="border rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <div className="text-sm text-muted-foreground">
                          {note.authorEmail || 'System'} • {formatDateTime(note.createdAt)}
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => deleteNoteMutation.mutate(note.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                      <p className="whitespace-pre-wrap">{note.content}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Tenant</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={editForm.email}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="contact">Primary Contact Name</Label>
              <Input
                id="contact"
                value={editForm.primaryContactName}
                onChange={(e) => setEditForm({ ...editForm, primaryContactName: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Suspend Dialog */}
      <AlertDialog open={suspendDialogOpen} onOpenChange={setSuspendDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Suspend Tenant?</AlertDialogTitle>
            <AlertDialogDescription>
              This will soft-lock access to this tenant. Users will not be able to log in,
              but all data will be preserved. You can reactivate the tenant at any time.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => suspendMutation.mutate()}
              className="bg-destructive text-destructive-foreground"
            >
              {suspendMutation.isPending ? 'Suspending...' : 'Suspend Tenant'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Schedule Deletion Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule Tenant Deletion</DialogTitle>
            <DialogDescription>
              Schedule this tenant for deletion. All data will be permanently deleted after the retention period.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Retention Period</Label>
              <Select defaultValue="30">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="30">30 days</SelectItem>
                  <SelectItem value="60">60 days</SelectItem>
                  <SelectItem value="90">90 days</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="p-3 bg-destructive/10 rounded-lg text-sm text-destructive">
              <AlertTriangle className="h-4 w-4 inline mr-2" />
              This action cannot be undone after the retention period. All tenant data will be permanently deleted.
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={() => scheduleDeletionMutation.mutate(30)}
              disabled={scheduleDeletionMutation.isPending}
            >
              {scheduleDeletionMutation.isPending ? 'Scheduling...' : 'Schedule Deletion'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Provider Dialog */}
      <Dialog open={addProviderDialogOpen} onOpenChange={setAddProviderDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Provider Subscription</DialogTitle>
            <DialogDescription>
              Subscribe this tenant to a provider and plan
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="provider">Provider</Label>
              <Select
                value={selectedProvider?.id || ''}
                onValueChange={(value) => {
                  const provider = providers.find((p: ProviderWithPlans) => p.id === value);
                  setSelectedProvider(provider || null);
                  setSelectedPlan(null);
                }}
              >
                <SelectTrigger id="provider">
                  <SelectValue placeholder="Select a provider" />
                </SelectTrigger>
                <SelectContent>
                  {availableProviders.map((provider: ProviderWithPlans) => (
                    <SelectItem key={provider.id} value={provider.id}>
                      {provider.display_name || provider.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedProvider && (
              <div>
                <Label htmlFor="plan">Plan</Label>
                <Select
                  value={selectedPlan?.id || ''}
                  onValueChange={(value) => {
                    const plan = selectedProvider.plans.find((p: ProviderPlan) => p.id === value);
                    setSelectedPlan(plan || null);
                  }}
                >
                  <SelectTrigger id="plan">
                    <SelectValue placeholder="Select a plan" />
                  </SelectTrigger>
                  <SelectContent>
                    {selectedProvider.plans
                      .filter((p: ProviderPlan) => p.is_active)
                      .map((plan: ProviderPlan) => (
                        <SelectItem key={plan.id} value={plan.id}>
                          {plan.display_name} {plan.price_monthly > 0 && `($${plan.price_monthly}/mo)`}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setAddProviderDialogOpen(false);
              setSelectedProvider(null);
              setSelectedPlan(null);
            }}>
              Cancel
            </Button>
            <Button
              onClick={handleAddProvider}
              disabled={!selectedProvider || !selectedPlan || createSubscriptionMutation.isPending}
            >
              {createSubscriptionMutation.isPending ? 'Creating...' : 'Add Subscription'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Change Plan Dialog */}
      <Dialog open={changePlanDialogOpen} onOpenChange={setChangePlanDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Plan</DialogTitle>
            <DialogDescription>
              Change the plan for {selectedSubscription?.provider?.display_name || 'this provider'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {selectedSubscription && (
              <div>
                <Label htmlFor="new-plan">New Plan</Label>
                <Select
                  value={selectedPlan?.id || ''}
                  onValueChange={(value) => {
                    const provider = providers.find((p: ProviderWithPlans) => p.id === selectedSubscription.provider_id);
                    if (provider) {
                      const plan = provider.plans.find((p: ProviderPlan) => p.id === value);
                      setSelectedPlan(plan || null);
                    }
                  }}
                >
                  <SelectTrigger id="new-plan">
                    <SelectValue placeholder="Select a plan" />
                  </SelectTrigger>
                  <SelectContent>
                    {(() => {
                      const provider = providers.find((p: ProviderWithPlans) => p.id === selectedSubscription.provider_id);
                      return provider?.plans
                        .filter((p: ProviderPlan) => p.is_active)
                        .map((plan: ProviderPlan) => (
                          <SelectItem key={plan.id} value={plan.id}>
                            {plan.display_name} {plan.price_monthly > 0 && `($${plan.price_monthly}/mo)`}
                          </SelectItem>
                        ));
                    })()}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setChangePlanDialogOpen(false);
              setSelectedSubscription(null);
              setSelectedPlan(null);
            }}>
              Cancel
            </Button>
            <Button
              onClick={handleChangePlan}
              disabled={!selectedPlan || updateSubscriptionMutation.isPending}
            >
              {updateSubscriptionMutation.isPending ? 'Updating...' : 'Change Plan'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel Subscription Dialog */}
      <AlertDialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Subscription?</AlertDialogTitle>
            <AlertDialogDescription>
              This will cancel the subscription for {selectedSubscription?.provider?.display_name || 'this provider'}.
              The subscription will remain active until the end of the current billing period.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Subscription</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancelSubscription}
              className="bg-destructive text-destructive-foreground"
              disabled={cancelSubscriptionMutation.isPending}
            >
              {cancelSubscriptionMutation.isPending ? 'Canceling...' : 'Cancel Subscription'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Impersonate User Dialog */}
      <AlertDialog open={impersonateDialogOpen} onOpenChange={setImpersonateDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Impersonate User?</AlertDialogTitle>
            <AlertDialogDescription>
              You will be logged in as {selectedUser?.name || selectedUser?.email}. This action is logged for audit purposes.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => selectedUser && impersonateUserMutation.mutate(selectedUser.user_id)}
              disabled={impersonateUserMutation.isPending}
            >
              {impersonateUserMutation.isPending ? 'Starting...' : 'Impersonate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Suspend User Dialog */}
      <AlertDialog open={suspendUserDialogOpen} onOpenChange={setSuspendUserDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Suspend User?</AlertDialogTitle>
            <AlertDialogDescription>
              This will suspend {selectedUser?.name || selectedUser?.email} from accessing this tenant.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => selectedUser && suspendUserMutation.mutate(selectedUser.user_id)}
              className="bg-destructive text-destructive-foreground"
              disabled={suspendUserMutation.isPending}
            >
              {suspendUserMutation.isPending ? 'Suspending...' : 'Suspend'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Unsuspend User Dialog */}
      <AlertDialog open={unsuspendUserDialogOpen} onOpenChange={setUnsuspendUserDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unsuspend User?</AlertDialogTitle>
            <AlertDialogDescription>
              This will restore access for {selectedUser?.name || selectedUser?.email} to this tenant.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => selectedUser && unsuspendUserMutation.mutate(selectedUser.user_id)}
              disabled={unsuspendUserMutation.isPending}
            >
              {unsuspendUserMutation.isPending ? 'Unsuspending...' : 'Unsuspend'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Change Role Dialog */}
      <Dialog open={roleChangeDialogOpen} onOpenChange={setRoleChangeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change User Role</DialogTitle>
            <DialogDescription>
              Change the role for {selectedUser?.name || selectedUser?.email}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="role">Role</Label>
              <Select value={newRole} onValueChange={setNewRole}>
                <SelectTrigger id="role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="developer">Developer</SelectItem>
                  <SelectItem value="viewer">Viewer</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRoleChangeDialogOpen(false)}>Cancel</Button>
            <Button
              onClick={() => selectedUser && changeUserRoleMutation.mutate({ userId: selectedUser.user_id, role: newRole })}
              disabled={!newRole || changeUserRoleMutation.isPending}
            >
              {changeUserRoleMutation.isPending ? 'Changing...' : 'Change Role'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove User Dialog */}
      <AlertDialog open={removeUserDialogOpen} onOpenChange={setRemoveUserDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove User from Tenant?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove {selectedUser?.name || selectedUser?.email} from this tenant. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => selectedUser && removeUserMutation.mutate(selectedUser.user_id)}
              className="bg-destructive text-destructive-foreground"
              disabled={removeUserMutation.isPending}
            >
              {removeUserMutation.isPending ? 'Removing...' : 'Remove User'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
