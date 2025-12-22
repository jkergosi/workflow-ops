// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { mapBackendRoleToFrontendRole } from '@/lib/permissions';
import { UserCircle, Save, Mail, User, Shield } from 'lucide-react';
import { toast } from 'sonner';

export function ProfilePage() {
  useEffect(() => {
    document.title = 'Profile - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    role: user?.role || 'viewer' as 'admin' | 'developer' | 'viewer',
  });
  
  // Check if current user is admin (using frontend role mapping)
  const currentUserRole = user ? mapBackendRoleToFrontendRole(user.role) : 'user';
  const isAdmin = currentUserRole === 'admin' || currentUserRole === 'superuser';

  // Update form data when user changes
  useEffect(() => {
    if (user) {
      setFormData({
        name: user.name || '',
        email: user.email || '',
        role: user.role || 'viewer' as 'admin' | 'developer' | 'viewer',
      });
    }
  }, [user]);

  const updateMutation = useMutation({
    mutationFn: async (updates: { name?: string; email?: string; role?: string }) => {
      return api.updateCurrentUser(updates);
    },
    onSuccess: () => {
      toast.success('Profile updated successfully');
      setIsEditing(false);
      queryClient.invalidateQueries({ queryKey: ['user'] });
      // Refresh the page to update auth context
      window.location.reload();
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to update profile';
      toast.error(message);
    },
  });

  const handleSave = () => {
    if (!formData.name.trim()) {
      toast.error('Name is required');
      return;
    }
    if (!formData.email.trim()) {
      toast.error('Email is required');
      return;
    }
    const updates: { name?: string; email?: string; role?: string } = {
      name: formData.name,
      email: formData.email,
    };
    // Only include role if user is admin and it changed
    if (isAdmin && formData.role !== user?.role) {
      updates.role = formData.role;
    }
    updateMutation.mutate(updates);
  };

  const handleCancel = () => {
    setFormData({
      name: user?.name || '',
      email: user?.email || '',
      role: user?.role || 'viewer' as 'admin' | 'developer' | 'viewer',
    });
    setIsEditing(false);
  };

  if (!user) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">Loading user information...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Profile</h1>
        <p className="text-muted-foreground">Manage your account information</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserCircle className="h-5 w-5" />
            Account Information
          </CardTitle>
          <CardDescription>Your personal account details</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">
                <User className="h-4 w-4 inline mr-1" />
                Name
              </Label>
              {isEditing ? (
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Enter your name"
                />
              ) : (
                <Input
                  id="name"
                  value={user.name}
                  disabled
                  className="bg-muted"
                />
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">
                <Mail className="h-4 w-4 inline mr-1" />
                Email
              </Label>
              {isEditing ? (
                <Input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="Enter your email"
                />
              ) : (
                <Input
                  id="email"
                  type="email"
                  value={user.email}
                  disabled
                  className="bg-muted"
                />
              )}
            </div>

            {isAdmin && (
              <div className="space-y-2">
                <Label htmlFor="role">
                  <Shield className="h-4 w-4 inline mr-1" />
                  Role
                </Label>
                {isEditing ? (
                  <select
                    id="role"
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value as 'admin' | 'developer' | 'viewer' })}
                    className="flex h-10 w-full rounded-md border border-input bg-background text-foreground px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <option value="admin" className="bg-background text-foreground">Admin</option>
                    <option value="developer" className="bg-background text-foreground">Developer</option>
                    <option value="viewer" className="bg-background text-foreground">Viewer</option>
                  </select>
                ) : (
                  <div className="flex items-center gap-2">
                    <Input
                      id="role"
                      value={user.role}
                      disabled
                      className="bg-muted"
                    />
                    <Badge variant="secondary" className="capitalize">
                      {user.role}
                    </Badge>
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  Only administrators can view and change roles
                </p>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 pt-4 border-t">
            {isEditing ? (
              <>
                <Button
                  onClick={handleSave}
                  disabled={updateMutation.isPending}
                >
                  <Save className="h-4 w-4 mr-2" />
                  {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleCancel}
                  disabled={updateMutation.isPending}
                >
                  Cancel
                </Button>
              </>
            ) : (
              <Button onClick={() => setIsEditing(true)}>
                <UserCircle className="h-4 w-4 mr-2" />
                Edit Profile
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

