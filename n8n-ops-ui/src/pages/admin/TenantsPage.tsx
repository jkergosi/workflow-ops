// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Building2,
  Plus,
  Search,
  Edit,
  Trash2,
  Users,
  Workflow,
  Server,
  MoreHorizontal,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Filter,
  X,
  Pause,
  Play,
  Calendar as _Calendar,
  Download,
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
import { exportToCSV } from '@/lib/export-utils';
import type { Tenant } from '@/types';

export function TenantsPage() {
  useEffect(() => {
    document.title = 'Tenants - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Filters state
  const [searchTerm, setSearchTerm] = useState('');
  const [planFilter, setPlanFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [suspendDialogOpen, setSuspendDialogOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);

  const [tenantForm, setTenantForm] = useState({
    name: '',
    email: '',
    subscriptionPlan: 'free' as 'free' | 'pro' | 'agency' | 'enterprise',
  });

  // Fetch tenants with filters
  const { data: tenantsData, isLoading, refetch } = useQuery({
    queryKey: ['tenants', page, pageSize, searchTerm, planFilter, statusFilter],
    queryFn: () => apiClient.getTenants({
      page,
      page_size: pageSize,
      search: searchTerm || undefined,
      plan: planFilter !== 'all' ? planFilter : undefined,
      status: statusFilter !== 'all' ? statusFilter : undefined,
    }),
  });

  // Fetch stats
  const { data: statsData } = useQuery({
    queryKey: ['tenant-stats'],
    queryFn: () => apiClient.getTenantStats(),
  });

  const tenantsArray = tenantsData?.data && "tenants" in tenantsData.data ? tenantsData.data.tenants : tenantsData?.data;
  const tenants: Tenant[] = Array.isArray(tenantsArray) ? tenantsArray : [];
  const totalCount = tenantsData?.data?.total || tenants.length;
  const totalPages = (tenantsData?.data && "total_pages" in tenantsData.data ? tenantsData.data.total_pages : undefined) || Math.ceil(totalCount / pageSize);
  const stats = statsData?.data || { total: 0, active: 0, suspended: 0, pending: 0, by_plan: { free: 0, pro: 0, enterprise: 0 } };

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: { name: string; email: string; subscription_plan: string }) =>
      apiClient.createTenant(data),
    onSuccess: () => {
      toast.success('Tenant created successfully');
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      queryClient.invalidateQueries({ queryKey: ['tenant-stats'] });
      setCreateDialogOpen(false);
      resetForm();
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to create tenant';
      toast.error(message);
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: any }) =>
      apiClient.updateTenant(id, updates),
    onSuccess: () => {
      toast.success('Tenant updated successfully');
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      queryClient.invalidateQueries({ queryKey: ['tenant-stats'] });
      setEditDialogOpen(false);
      setSelectedTenant(null);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to update tenant';
      toast.error(message);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteTenant(id),
    onSuccess: () => {
      toast.success('Tenant deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      queryClient.invalidateQueries({ queryKey: ['tenant-stats'] });
      setDeleteDialogOpen(false);
      setSelectedTenant(null);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to delete tenant';
      toast.error(message);
    },
  });

  // Suspend mutation
  const suspendMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      apiClient.suspendTenant(id, reason),
    onSuccess: () => {
      toast.success('Tenant suspended');
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      queryClient.invalidateQueries({ queryKey: ['tenant-stats'] });
      setSuspendDialogOpen(false);
      setSelectedTenant(null);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to suspend tenant';
      toast.error(message);
    },
  });

  // Reactivate mutation
  const reactivateMutation = useMutation({
    mutationFn: (id: string) => apiClient.reactivateTenant(id),
    onSuccess: () => {
      toast.success('Tenant reactivated');
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
      queryClient.invalidateQueries({ queryKey: ['tenant-stats'] });
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to reactivate tenant';
      toast.error(message);
    },
  });

  const resetForm = () => {
    setTenantForm({ name: '', email: '', subscriptionPlan: 'free' });
  };

  const clearFilters = () => {
    setSearchTerm('');
    setPlanFilter('all');
    setStatusFilter('all');
    setPage(1);
  };

  const hasActiveFilters = searchTerm || planFilter !== 'all' || statusFilter !== 'all';

  const getPlanBadgeVariant = (plan: string) => {
    switch (plan) {
      case 'enterprise':
        return 'default';
      case 'agency':
        return 'default';
      case 'pro':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'suspended':
        return 'destructive';
      case 'trial':
        return 'secondary';
      case 'cancelled':
        return 'outline';
      default:
        return 'outline';
    }
  };

  const handleCreate = () => {
    createMutation.mutate({
      name: tenantForm.name,
      email: tenantForm.email,
      subscription_plan: tenantForm.subscriptionPlan,
    });
  };

  const handleEdit = (tenant: Tenant) => {
    setSelectedTenant(tenant);
    setTenantForm({
      name: tenant.name,
      email: tenant.email || '',
      subscriptionPlan: (tenant.subscriptionPlan || 'free') as any,
    });
    setEditDialogOpen(true);
  };

  const handleUpdate = () => {
    if (!selectedTenant) return;
    updateMutation.mutate({
      id: selectedTenant.id,
      updates: {
        name: tenantForm.name,
        email: tenantForm.email,
        subscription_plan: tenantForm.subscriptionPlan,
      },
    });
  };

  const handleDelete = (tenant: Tenant) => {
    setSelectedTenant(tenant);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (!selectedTenant) return;
    deleteMutation.mutate(selectedTenant.id);
  };

  const handleSuspend = (tenant: Tenant) => {
    setSelectedTenant(tenant);
    setSuspendDialogOpen(true);
  };

  const handleSuspendConfirm = () => {
    if (!selectedTenant) return;
    suspendMutation.mutate({ id: selectedTenant.id, reason: 'Admin action' });
  };

  const handleReactivate = (tenant: Tenant) => {
    reactivateMutation.mutate(tenant.id);
  };

  const handleRowClick = (tenant: Tenant) => {
    navigate(`/admin/tenants/${tenant.id}`);
  };

  const handleExport = () => {
    if (tenants.length === 0) {
      toast.error('No data to export');
      return;
    }

    const columns = [
      { key: 'id' as const, header: 'Tenant ID' },
      { key: 'name' as const, header: 'Tenant Name' },
      { key: 'email' as const, header: 'Owner Email' },
      { key: 'subscriptionPlan' as const, header: 'Plan' },
      { key: 'status' as const, header: 'Status' },
      { key: 'workflowCount' as const, header: 'Workflows' },
      { key: 'environmentCount' as const, header: 'Environments' },
      { key: 'userCount' as const, header: 'Users' },
      { key: 'createdAt' as const, header: 'Created At' },
    ];

    // Build filename with filter info
    let filename = 'tenants';
    if (planFilter !== 'all') filename += `_${planFilter}`;
    if (statusFilter !== 'all') filename += `_${statusFilter}`;
    if (searchTerm) filename += '_filtered';

    exportToCSV(tenants, columns, filename);
    toast.success(`Exported ${(Array.isArray(tenants) ? tenants.length : 0)} tenants to CSV`);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Tenants</h1>
          <p className="text-muted-foreground">Manage all tenants in the system</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport} disabled={tenants.length === 0}>
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={() => setCreateDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Tenant
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Building2 className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">{(stats.totalTenants || (stats as any).total || 0)}</p>
                <p className="text-sm text-muted-foreground">Total Tenants</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-green-100 flex items-center justify-center">
                <div className="h-3 w-3 rounded-full bg-green-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">{(stats.activeTenants || (stats as any).active || 0)}</p>
                <p className="text-sm text-muted-foreground">Active</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Badge variant="default" className="h-8 px-3">ENT</Badge>
              <div>
                <p className="text-2xl font-bold">{((stats as any).by_plan || stats.byPlan || { free: 0, pro: 0, enterprise: 0 })?.enterprise || 0}</p>
                <p className="text-sm text-muted-foreground">Enterprise</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Badge variant="secondary" className="h-8 px-3">PRO</Badge>
              <div>
                <p className="text-2xl font-bold">{((stats as any).by_plan || stats.byPlan || { free: 0, pro: 0, enterprise: 0 })?.pro || 0}</p>
                <p className="text-sm text-muted-foreground">Pro</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Filter className="h-4 w-4" />
              Filters
            </CardTitle>
            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="h-4 w-4 mr-1" />
                Clear
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name or email..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setPage(1);
                }}
                className="pl-9"
              />
            </div>
            <Select value={planFilter} onValueChange={(v) => { setPlanFilter(v); setPage(1); }}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Plan" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Plans</SelectItem>
                <SelectItem value="free">Free</SelectItem>
                <SelectItem value="pro">Pro</SelectItem>
                <SelectItem value="agency">Agency</SelectItem>
                <SelectItem value="enterprise">Enterprise</SelectItem>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="trial">Trial</SelectItem>
                <SelectItem value="suspended">Suspended</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Tenants Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5" />
                All Tenants
              </CardTitle>
              <CardDescription>
                Showing {(Array.isArray(tenants) ? tenants.length : 0)} of {totalCount} tenants
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading tenants...</div>
          ) : tenants.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {hasActiveFilters ? 'No tenants match your filters' : 'No tenants found. Create your first tenant to get started.'}
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Tenant</TableHead>
                    <TableHead>Plan</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-center">
                      <Workflow className="h-4 w-4 inline mr-1" />
                      Workflows
                    </TableHead>
                    <TableHead className="text-center">
                      <Server className="h-4 w-4 inline mr-1" />
                      Environments
                    </TableHead>
                    <TableHead className="text-center">
                      <Users className="h-4 w-4 inline mr-1" />
                      Users
                    </TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tenants.map((tenant: Tenant) => (
                    <TableRow
                      key={tenant.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => handleRowClick(tenant)}
                    >
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div>
                            <p className="font-medium">{tenant.name}</p>
                            <p className="text-sm text-muted-foreground">{tenant.email}</p>
                          </div>
                          <ExternalLink className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100" />
                        </div>
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Badge variant={getPlanBadgeVariant(tenant.subscriptionPlan || 'free')} className="capitalize">
                          {tenant.subscriptionPlan || 'free'}
                        </Badge>
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Badge variant={getStatusBadgeVariant(tenant.status || 'active')} className="capitalize">
                          {tenant.status || 'active'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">{tenant.workflowCount || 0}</TableCell>
                      <TableCell className="text-center">{tenant.environmentCount || 0}</TableCell>
                      <TableCell className="text-center">{tenant.userCount || 0}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {tenant.createdAt ? new Date(tenant.createdAt).toLocaleDateString() : '-'}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => navigate(`/admin/tenants/${tenant.id}`)}>
                              <ExternalLink className="h-4 w-4 mr-2" />
                              View Details
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => handleEdit(tenant)}>
                              <Edit className="h-4 w-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            {tenant.status === 'suspended' ? (
                              <DropdownMenuItem onClick={() => handleReactivate(tenant)}>
                                <Play className="h-4 w-4 mr-2" />
                                Reactivate
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onClick={() => handleSuspend(tenant)}>
                                <Pause className="h-4 w-4 mr-2" />
                                Suspend
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onClick={() => handleDelete(tenant)}
                              className="text-destructive"
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {totalPages}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add New Tenant</DialogTitle>
            <DialogDescription>Create a new tenant account</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Organization Name</Label>
              <Input
                id="name"
                placeholder="Acme Corp"
                value={tenantForm.name}
                onChange={(e) => setTenantForm({ ...tenantForm, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Admin Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="admin@example.com"
                value={tenantForm.email}
                onChange={(e) => setTenantForm({ ...tenantForm, email: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plan">Subscription Plan</Label>
              <Select
                value={tenantForm.subscriptionPlan}
                onValueChange={(v) => setTenantForm({ ...tenantForm, subscriptionPlan: v as any })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="free">Free</SelectItem>
                  <SelectItem value="pro">Pro</SelectItem>
                  <SelectItem value="agency">Agency</SelectItem>
                  <SelectItem value="enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating...' : 'Create Tenant'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Tenant</DialogTitle>
            <DialogDescription>Update tenant details</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Organization Name</Label>
              <Input
                id="edit-name"
                value={tenantForm.name}
                onChange={(e) => setTenantForm({ ...tenantForm, name: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-email">Admin Email</Label>
              <Input
                id="edit-email"
                type="email"
                value={tenantForm.email}
                onChange={(e) => setTenantForm({ ...tenantForm, email: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-plan">Subscription Plan</Label>
              <Select
                value={tenantForm.subscriptionPlan}
                onValueChange={(v) => setTenantForm({ ...tenantForm, subscriptionPlan: v as any })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="free">Free</SelectItem>
                  <SelectItem value="pro">Pro</SelectItem>
                  <SelectItem value="agency">Agency</SelectItem>
                  <SelectItem value="enterprise">Enterprise</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Suspend Dialog */}
      <Dialog open={suspendDialogOpen} onOpenChange={setSuspendDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Suspend Tenant</DialogTitle>
            <DialogDescription>
              Are you sure you want to suspend {selectedTenant?.name}? This will disable their access to the platform.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSuspendDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleSuspendConfirm} disabled={suspendMutation.isPending}>
              {suspendMutation.isPending ? 'Suspending...' : 'Suspend Tenant'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete Tenant</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete {selectedTenant?.name}? This action cannot be undone
              and will remove all associated data including workflows, environments, and users.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfirm} disabled={deleteMutation.isPending}>
              {deleteMutation.isPending ? 'Deleting...' : 'Delete Tenant'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
