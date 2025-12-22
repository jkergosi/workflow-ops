// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Building2,
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  MoreHorizontal,
  Search,
  Shield,
  Calendar,
  User,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import type { TenantFeatureOverride, Tenant, AdminFeature } from '@/types';

export function TenantOverridesPage() {
  useEffect(() => {
    document.title = 'Tenant Overrides - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);
  const queryClient = useQueryClient();
  const [selectedTenantId, setSelectedTenantId] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedOverride, setSelectedOverride] = useState<TenantFeatureOverride | null>(null);

  const [overrideForm, setOverrideForm] = useState({
    featureKey: '',
    value: '' as string,
    valueType: 'flag' as 'flag' | 'limit',
    reason: '',
    expiresAt: '',
  });

  // Fetch tenants for dropdown
  const { data: tenantsData } = useQuery({
    queryKey: ['tenants'],
    queryFn: () => apiClient.getTenants(),
  });

  // Fetch features for dropdown
  const { data: featuresData } = useQuery({
    queryKey: ['admin-features'],
    queryFn: () => apiClient.getAdminFeatures(),
  });

  // Fetch overrides for selected tenant
  const { data: overridesData, isLoading, refetch } = useQuery({
    queryKey: ['tenant-overrides', selectedTenantId],
    queryFn: () => apiClient.getTenantOverrides(selectedTenantId),
    enabled: !!selectedTenantId,
  });

  const tenants = tenantsData?.data?.tenants || [];
  const features = featuresData?.data?.features || [];
  const overrides = overridesData?.data?.overrides || [];

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: {
      featureKey: string;
      value: Record<string, any>;
      reason?: string;
      expiresAt?: string;
    }) => apiClient.createTenantOverride(selectedTenantId, data),
    onSuccess: () => {
      toast.success('Override created successfully');
      queryClient.invalidateQueries({ queryKey: ['tenant-overrides', selectedTenantId] });
      setCreateDialogOpen(false);
      resetForm();
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to create override';
      toast.error(message);
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({
      overrideId,
      data,
    }: {
      overrideId: string;
      data: { value?: Record<string, any>; reason?: string; expiresAt?: string; isActive?: boolean };
    }) => apiClient.updateTenantOverride(selectedTenantId, overrideId, data),
    onSuccess: () => {
      toast.success('Override updated successfully');
      queryClient.invalidateQueries({ queryKey: ['tenant-overrides', selectedTenantId] });
      setEditDialogOpen(false);
      setSelectedOverride(null);
      resetForm();
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to update override';
      toast.error(message);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (overrideId: string) =>
      apiClient.deleteTenantOverride(selectedTenantId, overrideId),
    onSuccess: () => {
      toast.success('Override deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['tenant-overrides', selectedTenantId] });
      setDeleteDialogOpen(false);
      setSelectedOverride(null);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to delete override';
      toast.error(message);
    },
  });

  const resetForm = () => {
    setOverrideForm({
      featureKey: '',
      value: '',
      valueType: 'flag',
      reason: '',
      expiresAt: '',
    });
  };

  const handleFeatureSelect = (featureKey: string) => {
    const feature = features.find((f: AdminFeature) => f.key === featureKey);
    setOverrideForm({
      ...overrideForm,
      featureKey,
      valueType: feature?.type || 'flag',
      value: feature?.type === 'flag' ? 'true' : '0',
    });
  };

  const handleCreate = () => {
    const value =
      overrideForm.valueType === 'flag'
        ? { enabled: overrideForm.value === 'true' }
        : { value: parseInt(overrideForm.value, 10) || 0 };

    createMutation.mutate({
      featureKey: overrideForm.featureKey,
      value,
      reason: overrideForm.reason || undefined,
      expiresAt: overrideForm.expiresAt || undefined,
    });
  };

  const handleEdit = (override: TenantFeatureOverride) => {
    setSelectedOverride(override);
    const feature = features.find((f: AdminFeature) => f.key === override.featureKey);
    const valueType = feature?.type || 'flag';
    const value =
      valueType === 'flag'
        ? String(override.value?.enabled || false)
        : String(override.value?.value || 0);

    setOverrideForm({
      featureKey: override.featureKey,
      value,
      valueType,
      reason: override.reason || '',
      expiresAt: override.expiresAt ? override.expiresAt.split('T')[0] : '',
    });
    setEditDialogOpen(true);
  };

  const handleUpdate = () => {
    if (!selectedOverride) return;

    const value =
      overrideForm.valueType === 'flag'
        ? { enabled: overrideForm.value === 'true' }
        : { value: parseInt(overrideForm.value, 10) || 0 };

    updateMutation.mutate({
      overrideId: selectedOverride.id,
      data: {
        value,
        reason: overrideForm.reason || undefined,
        expiresAt: overrideForm.expiresAt || undefined,
      },
    });
  };

  const handleToggleActive = (override: TenantFeatureOverride) => {
    updateMutation.mutate({
      overrideId: override.id,
      data: { isActive: !override.isActive },
    });
  };

  const handleDelete = (override: TenantFeatureOverride) => {
    setSelectedOverride(override);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (!selectedOverride) return;
    deleteMutation.mutate(selectedOverride.id);
  };

  const filteredOverrides = overrides.filter(
    (o: TenantFeatureOverride) =>
      o.featureKey.toLowerCase().includes(searchTerm.toLowerCase()) ||
      o.featureDisplayName.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const selectedTenant = tenants.find((t: Tenant) => t.id === selectedTenantId);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const renderOverrideValue = (override: TenantFeatureOverride) => {
    if (override.value?.enabled !== undefined) {
      return override.value.enabled ? (
        <Badge variant="default">Enabled</Badge>
      ) : (
        <Badge variant="outline">Disabled</Badge>
      );
    }
    if (override.value?.value !== undefined) {
      const val = override.value.value;
      if (val === -1 || val >= 9999) {
        return <Badge variant="secondary">Unlimited</Badge>;
      }
      return <Badge variant="secondary">{val}</Badge>;
    }
    return <Badge variant="outline">Unknown</Badge>;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Tenant Overrides</h1>
          <p className="text-muted-foreground">
            Manage feature overrides for specific tenants
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => refetch()}
            disabled={!selectedTenantId}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button
            onClick={() => setCreateDialogOpen(true)}
            disabled={!selectedTenantId}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Override
          </Button>
        </div>
      </div>

      {/* Tenant Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            Select Tenant
          </CardTitle>
          <CardDescription>
            Choose a tenant to view and manage their feature overrides
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Select value={selectedTenantId} onValueChange={setSelectedTenantId}>
            <SelectTrigger className="w-full max-w-md">
              <SelectValue placeholder="Select a tenant..." />
            </SelectTrigger>
            <SelectContent>
              {tenants.map((tenant: Tenant) => (
                <SelectItem key={tenant.id} value={tenant.id}>
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4" />
                    <span>{tenant.name}</span>
                    <Badge variant="outline" className="ml-2 text-xs capitalize">
                      {tenant.subscriptionPlan}
                    </Badge>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {/* Overrides Table */}
      {selectedTenantId && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  Overrides for {selectedTenant?.name}
                </CardTitle>
                <CardDescription>
                  {overrides.length} override{overrides.length !== 1 ? 's' : ''} configured
                </CardDescription>
              </div>
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search overrides..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-8">Loading overrides...</div>
            ) : filteredOverrides.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {searchTerm
                  ? 'No overrides match your search'
                  : 'No overrides configured for this tenant'}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Feature</TableHead>
                    <TableHead>Value</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Expires</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredOverrides.map((override: TenantFeatureOverride) => (
                    <TableRow key={override.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{override.featureDisplayName}</p>
                          <p className="text-xs text-muted-foreground font-mono">
                            {override.featureKey}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>{renderOverrideValue(override)}</TableCell>
                      <TableCell>
                        <Badge
                          variant={override.isActive ? 'default' : 'outline'}
                          className="cursor-pointer"
                          onClick={() => handleToggleActive(override)}
                        >
                          {override.isActive ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {override.expiresAt ? (
                          <div className="flex items-center gap-1 text-sm">
                            <Calendar className="h-3 w-3" />
                            {formatDate(override.expiresAt)}
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-sm">Never</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-muted-foreground max-w-[200px] truncate block">
                          {override.reason || '-'}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          <p>{formatDate(override.createdAt)}</p>
                          {override.createdByEmail && (
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                              <User className="h-3 w-3" />
                              {override.createdByEmail}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleEdit(override)}>
                              <Edit className="h-4 w-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => handleDelete(override)}
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
      )}

      {/* Create Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Add Feature Override</DialogTitle>
            <DialogDescription>
              Create a new feature override for {selectedTenant?.name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="feature">Feature</Label>
              <Select
                value={overrideForm.featureKey}
                onValueChange={handleFeatureSelect}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a feature..." />
                </SelectTrigger>
                <SelectContent>
                  {features.map((feature: AdminFeature) => (
                    <SelectItem key={feature.id} value={feature.key}>
                      <div className="flex items-center gap-2">
                        <span>{feature.displayName}</span>
                        <Badge variant="outline" className="text-xs">
                          {feature.type}
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {overrideForm.featureKey && (
              <>
                {overrideForm.valueType === 'flag' ? (
                  <div className="flex items-center justify-between">
                    <Label htmlFor="value">Enabled</Label>
                    <Switch
                      id="value"
                      checked={overrideForm.value === 'true'}
                      onCheckedChange={(checked) =>
                        setOverrideForm({ ...overrideForm, value: String(checked) })
                      }
                    />
                  </div>
                ) : (
                  <div className="space-y-2">
                    <Label htmlFor="value">Limit Value</Label>
                    <Input
                      id="value"
                      type="number"
                      min={-1}
                      value={overrideForm.value}
                      onChange={(e) =>
                        setOverrideForm({ ...overrideForm, value: e.target.value })
                      }
                      placeholder="Enter limit (-1 for unlimited)"
                    />
                  </div>
                )}
              </>
            )}

            <div className="space-y-2">
              <Label htmlFor="expires">Expires (optional)</Label>
              <Input
                id="expires"
                type="date"
                value={overrideForm.expiresAt}
                onChange={(e) =>
                  setOverrideForm({ ...overrideForm, expiresAt: e.target.value })
                }
              />
              <p className="text-xs text-muted-foreground">
                Leave empty for permanent override
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="reason">Reason (optional)</Label>
              <Input
                id="reason"
                value={overrideForm.reason}
                onChange={(e) =>
                  setOverrideForm({ ...overrideForm, reason: e.target.value })
                }
                placeholder="Why is this override being created?"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!overrideForm.featureKey || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Override'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Override</DialogTitle>
            <DialogDescription>
              Update override for {selectedOverride?.featureDisplayName}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-3 bg-muted rounded-lg">
              <p className="text-sm font-medium">
                {selectedOverride?.featureDisplayName}
              </p>
              <p className="text-xs text-muted-foreground font-mono">
                {selectedOverride?.featureKey}
              </p>
            </div>

            {overrideForm.valueType === 'flag' ? (
              <div className="flex items-center justify-between">
                <Label htmlFor="edit-value">Enabled</Label>
                <Switch
                  id="edit-value"
                  checked={overrideForm.value === 'true'}
                  onCheckedChange={(checked) =>
                    setOverrideForm({ ...overrideForm, value: String(checked) })
                  }
                />
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="edit-value">Limit Value</Label>
                <Input
                  id="edit-value"
                  type="number"
                  min={-1}
                  value={overrideForm.value}
                  onChange={(e) =>
                    setOverrideForm({ ...overrideForm, value: e.target.value })
                  }
                  placeholder="Enter limit (-1 for unlimited)"
                />
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="edit-expires">Expires (optional)</Label>
              <Input
                id="edit-expires"
                type="date"
                value={overrideForm.expiresAt}
                onChange={(e) =>
                  setOverrideForm({ ...overrideForm, expiresAt: e.target.value })
                }
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-reason">Reason (optional)</Label>
              <Input
                id="edit-reason"
                value={overrideForm.reason}
                onChange={(e) =>
                  setOverrideForm({ ...overrideForm, reason: e.target.value })
                }
                placeholder="Why is this change being made?"
              />
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
            <DialogTitle>Delete Override</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the override for{' '}
              {selectedOverride?.featureDisplayName}? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete Override'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
