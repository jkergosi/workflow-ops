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
import { api } from '@/lib/api';
import { UserPlus, Users, Edit, Trash2, Mail } from 'lucide-react';
import { toast } from 'sonner';
import type { TeamMember } from '@/types';

export function TeamPage() {
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
    role: 'viewer' as 'admin' | 'developer' | 'viewer',
    status: 'active' as 'active' | 'pending' | 'inactive',
  });

  const { data: teamMembers, isLoading } = useQuery({
    queryKey: ['team-members'],
    queryFn: () => api.getTeamMembers(),
  });

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
    onSuccess: () => {
      toast.success('Team member updated successfully');
      queryClient.invalidateQueries({ queryKey: ['team-members'] });
      setEditDialogOpen(false);
      setSelectedMember(null);
    },
    onError: () => {
      toast.error('Failed to update team member');
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
      role: member.role as 'admin' | 'developer' | 'viewer',
      status: member.status as 'active' | 'pending' | 'inactive',
    });
    setEditDialogOpen(true);
  };

  const handleEditSubmit = () => {
    if (!selectedMember) return;
    updateMutation.mutate({
      id: selectedMember.id,
      updates: editForm,
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
          ) : teamMembers?.data && teamMembers.data.length > 0 ? (
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
                {teamMembers.data.map((member) => (
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
                <option value="viewer">Viewer - Read-only access</option>
                <option value="developer">Developer - Can manage workflows</option>
                <option value="admin">Admin - Full access</option>
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
              <Label htmlFor="edit-role">Role</Label>
              <select
                id="edit-role"
                value={editForm.role}
                onChange={(e) => setEditForm({ ...editForm, role: e.target.value as any })}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="viewer">Viewer</option>
                <option value="developer">Developer</option>
                <option value="admin">Admin</option>
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
                <option value="active">Active</option>
                <option value="pending">Pending</option>
                <option value="inactive">Inactive</option>
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
