// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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

export function N8NUsersPage() {
  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRole, setSelectedRole] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [isSyncing, setIsSyncing] = useState(false);

  // Fetch all N8N users
  const { data: n8nUsers, isLoading, refetch } = useQuery({
    queryKey: ['n8n-users', selectedEnvironment],
    queryFn: () => api.getN8NUsers(selectedEnvironment === 'dev' ? undefined : selectedEnvironment),
  });

  // Fetch environments for filter
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.getEnvironments(),
  });

  // Sync mutation to refresh from N8N (users only)
  const syncMutation = useMutation({
    mutationFn: async () => {
      // Get all environments or just the selected one
      const envsToSync = environments?.data?.filter((env: any) =>
        selectedEnvironment === 'dev' || env.type === selectedEnvironment
      ) || [];

      const results = [];
      for (const env of envsToSync) {
        const result = await api.syncUsersOnly(env.id);
        results.push({ env: env.name, ...result.data });
      }
      return results;
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
    if (!n8nUsers?.data) return [];
    const roles = new Set<string>();
    n8nUsers.data.forEach((user: any) => {
      if (user.role) roles.add(user.role);
    });
    return Array.from(roles).sort();
  }, [n8nUsers?.data]);

  // Filter and search users
  const filteredUsers = useMemo(() => {
    if (!n8nUsers?.data) return [];

    return n8nUsers.data.filter((user: any) => {
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
              value={selectedEnvironment}
              onChange={(e) => setSelectedEnvironment(e.target.value as EnvironmentType)}
              className="flex h-9 w-[180px] rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <option value="dev" className="bg-background text-foreground">All Environments</option>
              {environments?.data?.map((env: any) => (
                <option key={env.id} value={env.type} className="bg-background text-foreground">
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
                {n8nUsers?.data?.length === 0
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

          {/* Results count */}
          {filteredUsers.length > 0 && (
            <div className="mt-4 text-sm text-muted-foreground">
              Showing {filteredUsers.length} of {n8nUsers?.data?.length || 0} users
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
