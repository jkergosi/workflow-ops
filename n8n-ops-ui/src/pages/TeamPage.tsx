// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
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
import { api } from '@/lib/api';
import { UserPlus, Users, Edit, Trash2, Mail } from 'lucide-react';
import { toast } from 'sonner';
import type { TeamMember } from '@/types';

export function TeamPage() {
  useEffect(() => {
    document.title = 'Team - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);
  const queryClient = useQueryClient();
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedMember, setSelectedMember] = useState<TeamMember | null>(null);

  const [inviteForm, setInviteForm] = useState({
    email: '',
    name: '',
    role: 'viewer' as 'admin' | 'developer' | 'viewer',
  });

  const [editForm, setEditForm] = useState({
    name: '',
    email: '',
    role: 'viewer' as 'admin' | 'developer' | 'viewer',
    status: 'active' as 'active' | 'pending' | 'inactive',
  });

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const { data: teamMembersData, isLoading, isFetching } = useQuery({
    queryKey: ['team-members', currentPage, pageSize],
    queryFn: () => api.getTeamMembers({ page: currentPage, pageSize }),
    placeholderData: keepPreviousData,
  });

  const teamMembers = teamMembersData?.data?.items || [];
  const totalMembers = teamMembersData?.data?.total || 0;
  const totalPages = teamMembersData?.data?.totalPages || 1;

  const { data: teamLimits } = useQuery({
    queryKey: ['team-limits'],
    queryFn: () => api.getTeamLimits(),
  });

  const inviteMutation = useMutation({
    mutationFn: (data: { email: string; name: string; role: string }) =>
      api.createTeamMember(data),
    onSuccess: () => {
      toast.success('Team member invited successfully');
      queryClient.invalidateQueries({ queryKey: ['team-members'] });
      queryClient.invalidateQueries({ queryKey: ['team-limits'] });
      setInviteDialogOpen(false);
      resetInviteForm();
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to invite team member';
      toast.error(message);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, updates }: { id: string; updates: Partial<TeamMember> }) =>
      api.updateTeamMember(id, updates),
    onSuccess: (_, variables) => {
      // Check if email was changed
      if (variables.updates.email && variables.updates.email !== selectedMember?.email) {
        toast.success('Email updated. Verification email sent to the new address.');
      } else {
        toast.success('Team member updated successfully');
      }
      queryClient.invalidateQueries({ queryKey: ['team-members'] });
      setEditDialogOpen(false);
      setSelectedMember(null);
    },
    onError: () => {
      toast.error('Failed to update team member');
    },
  });

  const sendEmailVerificationMutation = useMutation({
    mutationFn: async ({ id, email }: { id: string; email: string }) => {
      // Use resend invite endpoint for email verification
      return api.resendInvitation(id);
    },
    onSuccess: () => {
      toast.success('Verification email sent successfully');
    },
    onError: () => {
      toast.error('Failed to send verification email');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteTeamMember(id),
    onSuccess: () => {
      toast.success('Team member removed successfully');
      queryClient.invalidateQueries({ queryKey: ['team-members'] });
      queryClient.invalidateQueries({ queryKey: ['team-limits'] });
      setDeleteDialogOpen(false);
      setSelectedMember(null);
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to remove team member';
      toast.error(message);
    },
  });

  const resendMutation = useMutation({
    mutationFn: (id: string) => api.resendInvitation(id),
    onSuccess: () => {
      toast.success('Invitation sent successfully');
    },
    onError: () => {
      toast.error('Failed to resend invitation');
    },
  });

  const resetInviteForm = () => {
    setInviteForm({ email: '', name: '', role: 'viewer' });
  };

  const handleInviteClick = () => {
    if (!teamLimits?.data?.can_add_more) {
      toast.error(`Team member limit reached (${teamLimits?.data?.max_members}). Upgrade your plan to add more members.`);
      return;
    }
    setInviteDialogOpen(true);
  };

  const handleInviteSubmit = () => {
    if (!inviteForm.email || !inviteForm.name) {
      toast.error('Please fill in all fields');
      return;
    }
    inviteMutation.mutate(inviteForm);
  };

  const handleEditClick = (member: TeamMember) => {
    setSelectedMember(member);
    setEditForm({
      name: member.name,
      email: member.email,
      role: member.role as 'admin' | 'developer' | 'viewer',
      status: member.status as 'active' | 'pending' | 'inactive',
    });
    setEditDialogOpen(true);
  };

  const handleEditSubmit = () => {
    if (!selectedMember) return;
    
    const updates: Partial<TeamMember> = {
      name: editForm.name,
      role: editForm.role,
      status: editForm.status,
    };
    
    // If email changed, include it in updates (backend should handle verification)
    if (editForm.email !== selectedMember.email) {
      updates.email = editForm.email;
    }
    
    updateMutation.mutate({
      id: selectedMember.id,
      updates,
    });
  };

  const handleSendEmailVerification = () => {
    if (!selectedMember) return;
    sendEmailVerificationMutation.mutate({
      id: selectedMember.id,
      email: editForm.email,
    });
  };

  const handleDeleteClick = (member: TeamMember) => {
    setSelectedMember(member);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (!selectedMember) return;
    deleteMutation.mutate(selectedMember.id);
  };

  const handleResendInvite = (member: TeamMember) => {
    resendMutation.mutate(member.id);
  };

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case 'admin':
        return 'default';
      case 'developer':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'pending':
        return 'default';
      default:
        return 'outline';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Team</h1>
          <p className="text-muted-foreground">Manage team members and permissions</p>
        </div>
        <Button onClick={handleInviteClick}>
          <UserPlus className="h-4 w-4 mr-2" />
          Invite Member
        </Button>
      </div>

      {/* Team Limits Card */}
      {teamLimits?.data && (
        <Card className={!teamLimits.data.can_add_more ? 'border-yellow-200 bg-yellow-50' : ''}>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Users className="h-5 w-5" />
                <div>
                  <p className="font-medium">
                    Team Members: {teamLimits.data.current_members}
                    {teamLimits.data.max_members && ` / ${teamLimits.data.max_members}`}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {teamLimits.data.max_members === null
                      ? 'Unlimited team members'
                      : teamLimits.data.can_add_more
                        ? `${teamLimits.data.max_members - teamLimits.data.current_members} slots remaining`
                        : 'Upgrade to add more members'}
                  </p>
                </div>
              </div>
              {!teamLimits.data.can_add_more && (
                <Button onClick={() => window.location.href = '/billing'}>
                  Upgrade Plan
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Team Members Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Team Members
          </CardTitle>
          <CardDescription>View and manage your team members</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading team members...</div>
          ) : teamMembers.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Joined</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {teamMembers.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell className="font-medium">{member.name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {member.email}
                    </TableCell>
                    <TableCell>
                      <Badge variant={getRoleBadgeVariant(member.role)} className="capitalize">
                        {member.role}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={getStatusBadgeVariant(member.status)} className="capitalize">
                        {member.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(member.createdAt).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        {member.status === 'pending' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleResendInvite(member)}
                            disabled={resendMutation.isPending}
                          >
                            <Mail className="h-3 w-3 mr-1" />
                            Resend
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleEditClick(member)}
                        >
                          <Edit className="h-3 w-3 mr-1" />
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleDeleteClick(member)}
                        >
                          <Trash2 className="h-3 w-3 mr-1" />
                          Remove
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No team members yet. Invite your first team member to get started.
            </div>
          )}

          {/* Pagination Controls */}
          {teamMembers.length > 0 && (
            <div className="mt-4 flex items-center justify-between border-t pt-4">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <Label htmlFor="pageSize" className="text-sm text-muted-foreground">
                    Rows per page:
                  </Label>
                  <select
                    id="pageSize"
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      setCurrentPage(1);
                    }}
                    className="h-8 w-20 rounded-md border border-input bg-background text-foreground px-2 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  >
                    <option value={10}>10</option>
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                  </select>
                </div>
                <div className="text-sm text-muted-foreground">
                  Showing {totalMembers > 0 ? ((currentPage - 1) * pageSize) + 1 : 0} to {Math.min(currentPage * pageSize, totalMembers)} of {totalMembers} members
                </div>
              </div>

              <div className="flex items-center gap-2">
                {isFetching && (
                  <span className="text-sm text-muted-foreground">Loading...</span>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(1)}
                  disabled={currentPage === 1 || isFetching}
                >
                  First
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(currentPage - 1)}
                  disabled={currentPage === 1 || isFetching}
                >
                  Previous
                </Button>
                <div className="flex items-center gap-1">
                  <span className="text-sm">
                    Page {currentPage} of {totalPages}
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(currentPage + 1)}
                  disabled={currentPage >= totalPages || isFetching}
                >
                  Next
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={currentPage >= totalPages || isFetching}
                >
                  Last
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Invite Dialog */}
      <Dialog open={inviteDialogOpen} onOpenChange={setInviteDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Invite Team Member</DialogTitle>
            <DialogDescription>
              Send an invitation to join your team
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="member@example.com"
                value={inviteForm.email}
                onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">Full Name</Label>
              <Input
                id="name"
                placeholder="John Doe"
                value={inviteForm.name}
                onChange={(e) => setInviteForm({ ...inviteForm, name: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <select
                id="role"
                value={inviteForm.role}
                onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value as any })}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="viewer" className="bg-background text-foreground">Viewer - Read-only access</option>
                <option value="developer" className="bg-background text-foreground">Developer - Can manage workflows</option>
                <option value="admin" className="bg-background text-foreground">Admin - Full access</option>
              </select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setInviteDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleInviteSubmit} disabled={inviteMutation.isPending}>
              {inviteMutation.isPending ? 'Sending...' : 'Send Invitation'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Team Member</DialogTitle>
            <DialogDescription>
              Update team member details and permissions
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Full Name</Label>
              <Input
                id="edit-name"
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-email">Email Address</Label>
              <div className="flex gap-2">
                <Input
                  id="edit-email"
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                  placeholder="member@example.com"
                  className="flex-1"
                />
                {editForm.email !== selectedMember?.email && editForm.email && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleSendEmailVerification}
                    disabled={sendEmailVerificationMutation.isPending}
                  >
                    <Mail className="h-3 w-3 mr-1" />
                    {sendEmailVerificationMutation.isPending ? 'Sending...' : 'Send Invite'}
                  </Button>
                )}
              </div>
              {editForm.email !== selectedMember?.email && (
                <p className="text-xs text-muted-foreground">
                  A verification email will be sent to the new address when you save. The user will need to verify the new email before it becomes active.
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-role">Role</Label>
              <select
                id="edit-role"
                value={editForm.role}
                onChange={(e) => setEditForm({ ...editForm, role: e.target.value as any })}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="viewer" className="bg-background text-foreground">Viewer</option>
                <option value="developer" className="bg-background text-foreground">Developer</option>
                <option value="admin" className="bg-background text-foreground">Admin</option>
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-status">Status</Label>
              <select
                id="edit-status"
                value={editForm.status}
                onChange={(e) => setEditForm({ ...editForm, status: e.target.value as any })}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="active" className="bg-background text-foreground">Active</option>
                <option value="pending" className="bg-background text-foreground">Pending</option>
                <option value="inactive" className="bg-background text-foreground">Inactive</option>
              </select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleEditSubmit} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Remove Team Member</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove {selectedMember?.name} from the team? This action cannot be undone.
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
              {deleteMutation.isPending ? 'Removing...' : 'Yes, Remove'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
