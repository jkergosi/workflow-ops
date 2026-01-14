// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
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
import { api } from '@/lib/api';
import { useAppStore } from '@/store/use-app-store';
import { Search, AlertCircle, CheckCircle2, Clock, RefreshCw, Download } from 'lucide-react';
import type { EnvironmentType } from '@/types';
import { toast } from 'sonner';
import { getDefaultEnvironmentId, resolveEnvironment, sortEnvironments } from '@/lib/environment-utils';

export function N8NUsersPage() {
  useEffect(() => {
    document.title = 'N8N Users - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRole, setSelectedRole] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [isSyncing, setIsSyncing] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  // Fetch environments for filter
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.getEnvironments(),
  });

  const availableEnvironments = useMemo(() => {
    if (!environments?.data) return [];
    return sortEnvironments(environments.data.filter((env: any) => env.isActive));
  }, [environments?.data]);

  const currentEnvironment = useMemo(
    () => resolveEnvironment(availableEnvironments, selectedEnvironment),
    [availableEnvironments, selectedEnvironment]
  );
  const currentEnvironmentId = currentEnvironment?.id;
  const currentEnvironmentType = currentEnvironment?.environmentClass || currentEnvironment?.type;

  useEffect(() => {
    if (availableEnvironments.length === 0) return;
    const nextId = currentEnvironmentId || getDefaultEnvironmentId(availableEnvironments);
    if (nextId && selectedEnvironment !== nextId) {
      setSelectedEnvironment(nextId);
    }
  }, [availableEnvironments, currentEnvironmentId, selectedEnvironment, setSelectedEnvironment]);

  // Reset pagination when environment changes
  useEffect(() => {
    setCurrentPage(1);
  }, [currentEnvironmentType]);

  // Fetch all N8N users (API expects environment_type, so we derive it from the selected environment)
  const { data: n8nUsers, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['n8n-users', currentEnvironmentType, currentPage, pageSize],
    queryFn: () => api.getN8NUsers({
      environmentType: currentEnvironmentType,
      page: currentPage,
      pageSize,
    }),
    placeholderData: keepPreviousData,
  });

  const allUsers = n8nUsers?.data?.items || [];
  const totalUsers = n8nUsers?.data?.total || 0;
  const totalPages = n8nUsers?.data?.totalPages || 1;

  // Sync mutation to refresh from N8N (users only)
  const syncMutation = useMutation({
    mutationFn: async () => {
      if (!currentEnvironmentId) return [];
      const result = await api.syncUsersOnly(currentEnvironmentId);
      return [{ env: currentEnvironment?.name || currentEnvironmentId, ...result.data }];
    },
    onSuccess: (results) => {
      setIsSyncing(false);
      const totalUsers = results.reduce((sum, r) => sum + (r.synced || 0), 0);
      toast.success(`Synced ${totalUsers} users from N8N`);
      queryClient.invalidateQueries({ queryKey: ['n8n-users'] });
    },
    onError: (error: any) => {
      setIsSyncing(false);
      const message = error.response?.data?.detail || 'Failed to sync from N8N';
      toast.error(message);
    },
  });

  const handleSyncFromN8N = () => {
    toast.info('Syncing from N8N...');
    setIsSyncing(true);
    syncMutation.mutate();
  };

  // Get unique roles
  const allRoles = useMemo(() => {
    if (!allUsers.length) return [];
    const roles = new Set<string>();
    allUsers.forEach((user: any) => {
      if (user.role) roles.add(user.role);
    });
    return Array.from(roles).sort();
  }, [allUsers]);

  // Filter and search users (client-side filtering on server-paginated data)
  const filteredUsers = useMemo(() => {
    if (!allUsers.length) return [];

    return allUsers.filter((user: any) => {
      // Search filter
      const matchesSearch =
        !searchQuery ||
        user.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        user.first_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        user.last_name?.toLowerCase().includes(searchQuery.toLowerCase());

      // Role filter
      const matchesRole = selectedRole === 'all' || user.role === selectedRole;

      // Status filter
      let matchesStatus = true;
      if (selectedStatus === 'active') matchesStatus = !user.is_pending;
      if (selectedStatus === 'pending') matchesStatus = user.is_pending;

      return matchesSearch && matchesRole && matchesStatus;
    });
  }, [n8nUsers?.data, searchQuery, selectedRole, selectedStatus]);

  const getStatusBadge = (isPending: boolean) => {
    if (isPending) {
      return (
        <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
          <Clock className="h-3 w-3 mr-1" />
          Pending
        </Badge>
      );
    }
    return (
      <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
        <CheckCircle2 className="h-3 w-3 mr-1" />
        Active
      </Badge>
    );
  };

  const getRoleBadge = (role?: string) => {
    if (!role) return <Badge variant="secondary">Unknown</Badge>;

    const roleColors: Record<string, string> = {
      owner: 'bg-purple-50 text-purple-700 border-purple-200',
      admin: 'bg-blue-50 text-blue-700 border-blue-200',
      member: 'bg-gray-50 text-gray-700 border-gray-200',
    };

    return (
      <Badge variant="outline" className={roleColors[role] || 'bg-gray-50 text-gray-700 border-gray-200'}>
        {role}
      </Badge>
    );
  };

  const getEnvironmentBadge = (type: EnvironmentType) => {
    const colors: Record<EnvironmentType, string> = {
      dev: 'bg-blue-50 text-blue-700 border-blue-200',
      staging: 'bg-yellow-50 text-yellow-700 border-yellow-200',
      production: 'bg-green-50 text-green-700 border-green-200',
    };

    return (
      <Badge variant="outline" className={colors[type]}>
        {type}
      </Badge>
    );
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">N8N Users</h1>
          <p className="text-muted-foreground">
            View users synced from N8N instances across environments
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => refetch()} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button
            onClick={handleSyncFromN8N}
            variant="default"
            size="sm"
            disabled={isSyncing}
          >
            <Download className={`h-4 w-4 mr-2 ${isSyncing ? 'animate-spin' : ''}`} />
            Sync from N8N
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>N8N Instance Users</CardTitle>
          <CardDescription>
            Users who have access to your N8N environments. Click "Sync from N8N" to fetch the latest users.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="flex gap-4 mb-6">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by email or name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <select
              value={currentEnvironmentId || ''}
              onChange={(e) => setSelectedEnvironment(e.target.value as EnvironmentType)}
              className="flex h-9 w-[180px] rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {availableEnvironments.map((env: any) => (
                <option key={env.id} value={env.id} className="bg-background text-foreground">
                  {env.name}
                </option>
              ))}
            </select>

            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
              className="flex h-9 w-[140px] rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="all" className="bg-background text-foreground">All Roles</option>
              {allRoles.map((role) => (
                <option key={role} value={role} className="bg-background text-foreground">
                  {role}
                </option>
              ))}
            </select>

            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="flex h-9 w-[140px] rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="all" className="bg-background text-foreground">All Status</option>
              <option value="active" className="bg-background text-foreground">Active</option>
              <option value="pending" className="bg-background text-foreground">Pending</option>
            </select>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">{filteredUsers.length}</div>
                <p className="text-xs text-muted-foreground">Total Users</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">
                  {filteredUsers.filter((u: any) => !u.is_pending).length}
                </div>
                <p className="text-xs text-muted-foreground">Active Users</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">
                  {filteredUsers.filter((u: any) => u.is_pending).length}
                </div>
                <p className="text-xs text-muted-foreground">Pending Users</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">{allRoles.length}</div>
                <p className="text-xs text-muted-foreground">Unique Roles</p>
              </CardContent>
            </Card>
          </div>

          {/* Users Table */}
          {isLoading ? (
            <div className="text-center py-8">Loading N8N users...</div>
          ) : filteredUsers.length === 0 ? (
            <div className="text-center py-8">
              <AlertCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
              <p className="text-muted-foreground">
                {totalUsers === 0
                  ? 'No N8N users found. Run Sync on the Environments page to fetch users from N8N.'
                  : 'No users match your filters.'}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Environment</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Synced</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredUsers.map((user: any) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.email}</TableCell>
                    <TableCell>
                      {user.first_name || user.last_name
                        ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                        : 'N/A'}
                    </TableCell>
                    <TableCell>
                      {user.environment ? (
                        <div className="flex flex-col gap-1">
                          <span className="text-sm">{user.environment.name}</span>
                          {getEnvironmentBadge(user.environment.type)}
                        </div>
                      ) : (
                        'N/A'
                      )}
                    </TableCell>
                    <TableCell>{getRoleBadge(user.role)}</TableCell>
                    <TableCell>{getStatusBadge(user.is_pending)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(user.last_synced_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination Controls */}
          {totalUsers > 0 && (
            <div className="mt-4 flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                Showing {filteredUsers.length} of {totalUsers} users
                {isFetching && !isLoading && (
                  <span className="ml-2">(updating...)</span>
                )}
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Rows per page:</span>
                  <select
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      setCurrentPage(1);
                    }}
                    className="flex h-8 w-[70px] rounded-md border border-input bg-background px-2 py-1 text-sm"
                  >
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-sm text-muted-foreground">
                    Page {currentPage} of {totalPages}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                  >
                    First
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
                    disabled={currentPage >= totalPages}
                  >
                    Next
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage >= totalPages}
                  >
                    Last
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
