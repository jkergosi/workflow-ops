import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  ArrowLeft,
  Search,
  UserCog,
  Ban,
  CheckCircle,
  Trash2,
  MoreVertical,
  Loader2,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';

interface TenantUser {
  user_id: string;
  name: string;
  email: string;
  role_in_tenant: string;
  status_in_tenant: string;
  joined_at: string;
  last_activity_at?: string;
  is_platform_admin: boolean;
}

export function PlatformTenantUsersRolesPage() {
  useEffect(() => {
    document.title = 'Tenant Users & Roles - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  });

  const { tenantId } = useParams<{ tenantId: string }>();
  const navigate = useNavigate();

  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('joined');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const [impersonateDialogOpen, setImpersonateDialogOpen] = useState(false);
  const [suspendDialogOpen, setSuspendDialogOpen] = useState(false);
  const [unsuspendDialogOpen, setUnsuspendDialogOpen] = useState(false);
  const [roleChangeDialogOpen, setRoleChangeDialogOpen] = useState(false);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<TenantUser | null>(null);
  const [newRole, setNewRole] = useState<string>('');

  // Fetch tenant details
  const { data: tenantData, isLoading: tenantLoading } = useQuery({
    queryKey: ['tenant', tenantId],
    queryFn: () => apiClient.getTenantById(tenantId!),
    enabled: !!tenantId,
  });

  // Fetch tenant users
  const { data: usersData, isLoading: usersLoading, refetch: refetchUsers } = useQuery({
    queryKey: ['tenant-users', tenantId, searchQuery, roleFilter, statusFilter, sortBy, sortOrder, page],
    queryFn: () => apiClient.getPlatformTenantUsers(tenantId!, {
      search: searchQuery || undefined,
      role: roleFilter !== 'all' ? roleFilter : undefined,
      status: statusFilter !== 'all' ? statusFilter : undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
      page,
      page_size: pageSize,
    }),
    enabled: !!tenantId,
  });

  const tenant = tenantData?.data;
  const users = usersData?.data?.users || [];
  const totalUsers = usersData?.data?.total || 0;

  // Mutations
  const impersonateMutation = useMutation({
    mutationFn: (userId: string) => apiClient.startPlatformImpersonation(userId),
    onSuccess: async (_data) => {
      toast.success('Impersonation started');
      setImpersonateDialogOpen(false);
      window.location.reload();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to start impersonation');
    },
  });

  const suspendMutation = useMutation({
    mutationFn: (userId: string) => apiClient.suspendPlatformTenantUser(tenantId!, userId),
    onSuccess: () => {
      toast.success('User suspended');
      setSuspendDialogOpen(false);
      refetchUsers();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to suspend user');
    },
  });

  const unsuspendMutation = useMutation({
    mutationFn: (userId: string) => apiClient.unsuspendPlatformTenantUser(tenantId!, userId),
    onSuccess: () => {
      toast.success('User unsuspended');
      setUnsuspendDialogOpen(false);
      refetchUsers();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to unsuspend user');
    },
  });

  const changeRoleMutation = useMutation({
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

  const removeMutation = useMutation({
    mutationFn: (userId: string) => apiClient.removePlatformTenantUser(tenantId!, userId),
    onSuccess: () => {
      toast.success('User removed from tenant');
      setRemoveDialogOpen(false);
      refetchUsers();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to remove user');
    },
  });

  const handleImpersonate = (user: TenantUser) => {
    setSelectedUser(user);
    setImpersonateDialogOpen(true);
  };

  const handleSuspend = (user: TenantUser) => {
    setSelectedUser(user);
    setSuspendDialogOpen(true);
  };

  const handleUnsuspend = (user: TenantUser) => {
    setSelectedUser(user);
    setUnsuspendDialogOpen(true);
  };

  const handleChangeRole = (user: TenantUser) => {
    setSelectedUser(user);
    setNewRole(user.role_in_tenant);
    setRoleChangeDialogOpen(true);
  };

  const handleRemove = (user: TenantUser) => {
    setSelectedUser(user);
    setRemoveDialogOpen(true);
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return 'Invalid Date';
    }
  };

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

  if (tenantLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!tenant) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Tenant not found</p>
        <Button variant="link" onClick={() => navigate('/platform/tenants')}>
          Back to Tenants
        </Button>
      </div>
    );
  }

  const planName = (tenant.subscriptionPlan || (tenant as any).subscription_plan || (tenant as any).subscription_tier || 'free') as string;
  const statusName = (tenant.status || (tenant as any).status || 'active') as string;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(`/platform/tenants/${tenantId}`)}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{tenant.name}</h1>
              <Badge>{planName}</Badge>
              <Badge variant="outline">{statusName}</Badge>
            </div>
            <p className="text-muted-foreground">Tenant ID: {tenantId}</p>
          </div>
        </div>
        <Link to={`/platform/tenants/${tenantId}`}>
          <Button variant="outline">Back to Tenant Overview</Button>
        </Link>
      </div>

      {/* Users Table */}
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
                    setPage(1);
                  }}
                  className="pl-10"
                />
              </div>
            </div>
            <Select value={roleFilter} onValueChange={(value) => { setRoleFilter(value); setPage(1); }}>
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
            <Select value={statusFilter} onValueChange={(value) => { setStatusFilter(value); setPage(1); }}>
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
            <>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 -ml-3"
                          onClick={() => {
                            if (sortBy === 'name') {
                              setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                            } else {
                              setSortBy('name');
                              setSortOrder('asc');
                            }
                            setPage(1);
                          }}
                        >
                          User
                          {sortBy === 'name' ? (
                            sortOrder === 'asc' ? <ArrowUp className="ml-2 h-4 w-4" /> : <ArrowDown className="ml-2 h-4 w-4" />
                          ) : (
                            <ArrowUpDown className="ml-2 h-4 w-4 opacity-50" />
                          )}
                        </Button>
                      </TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 -ml-3"
                          onClick={() => {
                            if (sortBy === 'role') {
                              setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                            } else {
                              setSortBy('role');
                              setSortOrder('asc');
                            }
                            setPage(1);
                          }}
                        >
                          Role
                          {sortBy === 'role' ? (
                            sortOrder === 'asc' ? <ArrowUp className="ml-2 h-4 w-4" /> : <ArrowDown className="ml-2 h-4 w-4" />
                          ) : (
                            <ArrowUpDown className="ml-2 h-4 w-4 opacity-50" />
                          )}
                        </Button>
                      </TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 -ml-3"
                          onClick={() => {
                            if (sortBy === 'status') {
                              setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                            } else {
                              setSortBy('status');
                              setSortOrder('asc');
                            }
                            setPage(1);
                          }}
                        >
                          Status
                          {sortBy === 'status' ? (
                            sortOrder === 'asc' ? <ArrowUp className="ml-2 h-4 w-4" /> : <ArrowDown className="ml-2 h-4 w-4" />
                          ) : (
                            <ArrowUpDown className="ml-2 h-4 w-4 opacity-50" />
                          )}
                        </Button>
                      </TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 -ml-3"
                          onClick={() => {
                            if (sortBy === 'joined') {
                              setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                            } else {
                              setSortBy('joined');
                              setSortOrder('desc');
                            }
                            setPage(1);
                          }}
                        >
                          Joined
                          {sortBy === 'joined' ? (
                            sortOrder === 'asc' ? <ArrowUp className="ml-2 h-4 w-4" /> : <ArrowDown className="ml-2 h-4 w-4" />
                          ) : (
                            <ArrowUpDown className="ml-2 h-4 w-4 opacity-50" />
                          )}
                        </Button>
                      </TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 -ml-3"
                          onClick={() => {
                            if (sortBy === 'last_activity') {
                              setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                            } else {
                              setSortBy('last_activity');
                              setSortOrder('desc');
                            }
                            setPage(1);
                          }}
                        >
                          Last Activity
                          {sortBy === 'last_activity' ? (
                            sortOrder === 'asc' ? <ArrowUp className="ml-2 h-4 w-4" /> : <ArrowDown className="ml-2 h-4 w-4" />
                          ) : (
                            <ArrowUpDown className="ml-2 h-4 w-4 opacity-50" />
                          )}
                        </Button>
                      </TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((user) => (
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
                        <TableCell>{formatDate(user.joined_at)}</TableCell>
                        <TableCell>{formatDate(user.last_activity_at)}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            {!user.is_platform_admin && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleImpersonate(user)}
                                title="Impersonate"
                              >
                                <UserCog className="h-4 w-4" />
                              </Button>
                            )}
                            {user.status_in_tenant === 'active' ? (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleSuspend(user)}
                                title="Suspend"
                              >
                                <Ban className="h-4 w-4" />
                              </Button>
                            ) : (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleUnsuspend(user)}
                                title="Unsuspend"
                              >
                                <CheckCircle className="h-4 w-4" />
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleChangeRole(user)}
                              title="Change Role"
                            >
                              <MoreVertical className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRemove(user)}
                              title="Remove from Tenant"
                              className="text-destructive hover:text-destructive"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {totalUsers > pageSize && (
                <div className="flex items-center justify-between mt-4">
                  <div className="text-sm text-muted-foreground">
                    Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, totalUsers)} of {totalUsers} users
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage(p => p + 1)}
                      disabled={page * pageSize >= totalUsers}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Impersonate Confirmation Dialog */}
      <AlertDialog open={impersonateDialogOpen} onOpenChange={setImpersonateDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Impersonate User</AlertDialogTitle>
            <AlertDialogDescription>
              You are about to impersonate <strong>{selectedUser?.name || selectedUser?.email}</strong>.
              This action will be recorded in the audit log.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => selectedUser && impersonateMutation.mutate(selectedUser.user_id)}
              disabled={impersonateMutation.isPending}
            >
              {impersonateMutation.isPending ? 'Starting...' : 'Impersonate'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Suspend Confirmation Dialog */}
      <AlertDialog open={suspendDialogOpen} onOpenChange={setSuspendDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Suspend User</AlertDialogTitle>
            <AlertDialogDescription>
              Suspending <strong>{selectedUser?.name || selectedUser?.email}</strong> will block them from accessing this tenant.
              This action will be recorded in the audit log.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => selectedUser && suspendMutation.mutate(selectedUser.user_id)}
              disabled={suspendMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {suspendMutation.isPending ? 'Suspending...' : 'Suspend'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Unsuspend Confirmation Dialog */}
      <AlertDialog open={unsuspendDialogOpen} onOpenChange={setUnsuspendDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Unsuspend User</AlertDialogTitle>
            <AlertDialogDescription>
              Unsuspending <strong>{selectedUser?.name || selectedUser?.email}</strong> will restore their access to this tenant.
              This action will be recorded in the audit log.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => selectedUser && unsuspendMutation.mutate(selectedUser.user_id)}
              disabled={unsuspendMutation.isPending}
            >
              {unsuspendMutation.isPending ? 'Unsuspending...' : 'Unsuspend'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Change Role Dialog */}
      <Dialog open={roleChangeDialogOpen} onOpenChange={setRoleChangeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Change Role</DialogTitle>
            <DialogDescription>
              Change role for <strong>{selectedUser?.name || selectedUser?.email}</strong> from{' '}
              <strong>{selectedUser?.role_in_tenant}</strong> to:
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Select value={newRole} onValueChange={setNewRole}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="admin">Admin</SelectItem>
                <SelectItem value="developer">Developer</SelectItem>
                <SelectItem value="viewer">Viewer</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRoleChangeDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (selectedUser && newRole && newRole !== selectedUser.role_in_tenant) {
                  changeRoleMutation.mutate({ userId: selectedUser.user_id, role: newRole });
                }
              }}
              disabled={changeRoleMutation.isPending || !newRole || newRole === selectedUser?.role_in_tenant}
            >
              {changeRoleMutation.isPending ? 'Changing...' : 'Change Role'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Confirmation Dialog */}
      <AlertDialog open={removeDialogOpen} onOpenChange={setRemoveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove User from Tenant</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove <strong>{selectedUser?.name || selectedUser?.email}</strong> from this tenant?
              This action cannot be undone and will be recorded in the audit log.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => selectedUser && removeMutation.mutate(selectedUser.user_id)}
              disabled={removeMutation.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {removeMutation.isPending ? 'Removing...' : 'Remove'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

