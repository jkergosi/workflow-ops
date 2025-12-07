import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { api } from '@/lib/api';
import { toast } from 'sonner';

interface Tenant {
  id: string;
  name: string;
  email: string;
  subscriptionPlan: 'free' | 'pro' | 'enterprise';
  status: 'active' | 'suspended' | 'pending';
  workflowCount: number;
  environmentCount: number;
  userCount: number;
  createdAt: string;
}

export function TenantsPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);

  const [tenantForm, setTenantForm] = useState({
    name: '',
    email: '',
    subscriptionPlan: 'free' as 'free' | 'pro' | 'enterprise',
  });

  // Fetch tenants
  const { data: tenantsData, isLoading, refetch } = useQuery({
    queryKey: ['tenants'],
    queryFn: () => api.getTenants(),
  });

  // Fetch stats
  const { data: statsData } = useQuery({
    queryKey: ['tenant-stats'],
    queryFn: () => api.getTenantStats(),
  });

  const tenants = tenantsData?.data || [];
  const stats = statsData?.data || { total: 0, active: 0, suspended: 0, pending: 0, by_plan: { free: 0, pro: 0, enterprise: 0 } };

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: { name: string; email: string; subscription_plan: string }) =>
      api.createTenant(data),
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
      api.updateTenant(id, updates),
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
    mutationFn: (id: string) => api.deleteTenant(id),
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

  const resetForm = () => {
    setTenantForm({ name: '', email: '', subscriptionPlan: 'free' });
  };

  const filteredTenants = tenants.filter(
    (tenant: Tenant) =>
      tenant.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      tenant.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getPlanBadgeVariant = (plan: string) => {
    switch (plan) {
      case 'enterprise':
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
      email: tenant.email,
      subscriptionPlan: tenant.subscriptionPlan,
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Tenants</h1>
          <p className="text-muted-foreground">Manage all tenants in the system</p>
        </div>
        <div className="flex gap-2">
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
                <p className="text-2xl font-bold">{stats.total}</p>
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
                <p className="text-2xl font-bold">{stats.active}</p>
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
                <p className="text-2xl font-bold">{stats.by_plan?.enterprise || 0}</p>
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
                <p className="text-2xl font-bold">{stats.by_plan?.pro || 0}</p>
                <p className="text-sm text-muted-foreground">Pro</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tenants Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5" />
                All Tenants
              </CardTitle>
              <CardDescription>View and manage tenant accounts</CardDescription>
            </div>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search tenants..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading tenants...</div>
          ) : filteredTenants.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {searchTerm ? 'No tenants match your search' : 'No tenants found. Create your first tenant to get started.'}
            </div>
          ) : (
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
                {filteredTenants.map((tenant: Tenant) => (
                  <TableRow key={tenant.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{tenant.name}</p>
                        <p className="text-sm text-muted-foreground">{tenant.email}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={getPlanBadgeVariant(tenant.subscriptionPlan)} className="capitalize">
                        {tenant.subscriptionPlan}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={getStatusBadgeVariant(tenant.status)} className="capitalize">
                        {tenant.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">{tenant.workflowCount}</TableCell>
                    <TableCell className="text-center">{tenant.environmentCount}</TableCell>
                    <TableCell className="text-center">{tenant.userCount}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(tenant.createdAt).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleEdit(tenant)}>
                            <Edit className="h-4 w-4 mr-2" />
                            Edit
                          </DropdownMenuItem>
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
              <select
                id="plan"
                value={tenantForm.subscriptionPlan}
                onChange={(e) =>
                  setTenantForm({ ...tenantForm, subscriptionPlan: e.target.value as any })
                }
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="free">Free</option>
                <option value="pro">Pro</option>
                <option value="enterprise">Enterprise</option>
              </select>
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
              <select
                id="edit-plan"
                value={tenantForm.subscriptionPlan}
                onChange={(e) =>
                  setTenantForm({ ...tenantForm, subscriptionPlan: e.target.value as any })
                }
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="free">Free</option>
                <option value="pro">Pro</option>
                <option value="enterprise">Enterprise</option>
              </select>
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
