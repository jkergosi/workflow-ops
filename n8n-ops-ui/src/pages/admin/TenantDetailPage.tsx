import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
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
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import type { Tenant, TenantNote, TenantFeatureOverride, Provider } from '@/types';

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
  const [activeTab, setActiveTab] = useState('overview');
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [suspendDialogOpen, setSuspendDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [noteContent, setNoteContent] = useState('');
  const [providerFilter, setProviderFilter] = useState<Provider | 'all'>('all');

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

  const tenant = tenantData?.data;
  const usage = usageData?.data;
  const notes = notesData?.data?.notes || [];
  const overrides = overridesData?.data?.overrides || [];

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

  const formatDate = (dateString?: string) => {
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

  const getUsageColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500';
    if (percentage >= 75) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/admin/tenants')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{tenant.name}</h1>
              <Badge className={statusColors[tenant.status]}>{tenant.status}</Badge>
              <Badge className={planColors[tenant.subscriptionPlan]}>{tenant.subscriptionPlan}</Badge>
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
      <Tabs value={activeTab} onValueChange={setActiveTab}>
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
                  <p className="font-medium">{formatDate(tenant.createdAt)}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Last Active</Label>
                  <p className="font-medium">{formatDate(tenant.lastActiveAt)}</p>
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
                    <Badge className={planColors[tenant.subscriptionPlan]} variant="outline">
                      {tenant.subscriptionPlan.toUpperCase()}
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
                      Scheduled for deletion on {formatDate(tenant.scheduledDeletionAt)}
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Users & Roles Tab */}
        <TabsContent value="users">
          <Card>
            <CardHeader>
              <CardTitle>Users & Roles</CardTitle>
              <CardDescription>Manage users within this tenant</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground text-center py-8">
                User management will be available in the full implementation.
                <br />
                Currently showing {tenant.userCount} users in this tenant.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Plan & Features Tab */}
        <TabsContent value="features" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Current Plan</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <Badge className={`${planColors[tenant.subscriptionPlan]} text-lg px-4 py-2`}>
                  {tenant.subscriptionPlan.toUpperCase()}
                </Badge>
                <Button variant="outline" asChild>
                  <Link to="/admin/plans">Change Plan</Link>
                </Button>
              </div>
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
              <CardDescription>Subscription and payment details</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <Label className="text-muted-foreground">Current Plan</Label>
                  <p className="font-medium capitalize">{tenant.subscriptionPlan}</p>
                </div>
                {tenant.stripeCustomerId && (
                  <div>
                    <Label className="text-muted-foreground">Stripe Customer ID</Label>
                    <div className="flex items-center gap-2">
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
                <p className="text-muted-foreground text-center py-4">
                  Full billing management will be available in the complete implementation.
                </p>
              </div>
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
                          {note.authorEmail || 'System'} • {formatDate(note.createdAt)}
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
    </div>
  );
}
