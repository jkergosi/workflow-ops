import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
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
  Database,
  Trash2,
  Eye,
  Clock,
  AlertTriangle,
  CheckCircle,
  Info,
  Loader2,
  Calendar,
  BarChart3,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import type { RetentionPolicy, CleanupPreview } from '@/types';

export function RetentionSettingsPage() {
  useEffect(() => {
    document.title = 'Retention Settings - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const queryClient = useQueryClient();
  const [showCleanupDialog, setShowCleanupDialog] = useState(false);
  const [showPreviewDialog, setShowPreviewDialog] = useState(false);

  // Editable form state
  const [retentionDays, setRetentionDays] = useState<number>(90);
  const [isEnabled, setIsEnabled] = useState<boolean>(true);
  const [minExecutionsToKeep, setMinExecutionsToKeep] = useState<number>(100);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Fetch retention policy
  const { data: policyResp, isLoading: policyLoading } = useQuery({
    queryKey: ['retention', 'policy'],
    queryFn: () => apiClient.getRetentionPolicy(),
  });

  const policy: RetentionPolicy | undefined = policyResp?.data;

  // Initialize form state when policy loads
  useEffect(() => {
    if (policy) {
      setRetentionDays(policy.retentionDays);
      setIsEnabled(policy.isEnabled);
      setMinExecutionsToKeep(policy.minExecutionsToKeep);
      setHasUnsavedChanges(false);
    }
  }, [policy]);

  // Track changes
  useEffect(() => {
    if (policy) {
      const changed =
        retentionDays !== policy.retentionDays ||
        isEnabled !== policy.isEnabled ||
        minExecutionsToKeep !== policy.minExecutionsToKeep;
      setHasUnsavedChanges(changed);
    }
  }, [retentionDays, isEnabled, minExecutionsToKeep, policy]);

  // Fetch cleanup preview
  const { data: previewResp, refetch: refetchPreview } = useQuery({
    queryKey: ['retention', 'preview'],
    queryFn: () => apiClient.getCleanupPreview(),
    enabled: false, // Only fetch when explicitly triggered
  });

  const preview: CleanupPreview | undefined = previewResp?.data;

  // Update policy mutation
  const updatePolicyMutation = useMutation({
    mutationFn: () =>
      apiClient.updateRetentionPolicy({
        retentionDays: retentionDays,
        isEnabled: isEnabled,
        minExecutionsToKeep: minExecutionsToKeep,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['retention', 'policy'] });
      toast.success('Retention policy updated successfully');
      setHasUnsavedChanges(false);
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to update retention policy');
    },
  });

  // Trigger cleanup mutation
  const cleanupMutation = useMutation({
    mutationFn: (force: boolean) => apiClient.triggerRetentionCleanup(force),
    onSuccess: (res) => {
      const result = res.data;
      queryClient.invalidateQueries({ queryKey: ['retention', 'policy'] });
      queryClient.invalidateQueries({ queryKey: ['retention', 'preview'] });

      if (result.skipped) {
        toast.info(result.reason || 'Cleanup was skipped');
      } else {
        toast.success(
          `Cleanup completed: ${result.deletedCount.toLocaleString()} executions deleted`
        );
      }
      setShowCleanupDialog(false);
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to trigger cleanup');
      setShowCleanupDialog(false);
    },
  });

  const handleSave = () => {
    if (retentionDays < 1 || retentionDays > 365) {
      toast.error('Retention days must be between 1 and 365');
      return;
    }
    if (minExecutionsToKeep < 0) {
      toast.error('Minimum executions to keep must be 0 or greater');
      return;
    }
    updatePolicyMutation.mutate();
  };

  const handleReset = () => {
    if (policy) {
      setRetentionDays(policy.retentionDays);
      setIsEnabled(policy.isEnabled);
      setMinExecutionsToKeep(policy.minExecutionsToKeep);
      setHasUnsavedChanges(false);
    }
  };

  const handlePreview = () => {
    refetchPreview();
    setShowPreviewDialog(true);
  };

  const handleCleanup = (force: boolean = false) => {
    cleanupMutation.mutate(force);
  };

  const formatTimestamp = (timestamp?: string | null) => {
    if (!timestamp) return 'Never';
    return new Date(timestamp).toLocaleString();
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString();
  };

  if (policyLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="mt-4 text-muted-foreground">Loading retention settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Retention Settings</h1>
        <p className="text-muted-foreground">
          Manage execution data retention policies to optimize storage and performance
        </p>
      </div>

      {/* Status Overview */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div
                className={`p-2 rounded-lg ${
                  isEnabled
                    ? 'bg-green-100 dark:bg-green-900/30'
                    : 'bg-gray-100 dark:bg-gray-900/30'
                }`}
              >
                {isEnabled ? (
                  <CheckCircle className="h-6 w-6 text-green-600" />
                ) : (
                  <AlertTriangle className="h-6 w-6 text-gray-600" />
                )}
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Status</p>
                <p className="text-2xl font-bold">
                  {isEnabled ? 'Enabled' : 'Disabled'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
                <Calendar className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Retention Period</p>
                <p className="text-2xl font-bold">{retentionDays} days</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/30">
                <Clock className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Last Cleanup</p>
                <p className="text-lg font-bold">
                  {policy?.lastCleanupAt
                    ? formatTimestamp(policy.lastCleanupAt)
                    : 'Never'}
                </p>
                {policy && policy.lastCleanupDeletedCount > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {policy.lastCleanupDeletedCount.toLocaleString()} deleted
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Configuration Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Retention Configuration
              </CardTitle>
              <CardDescription>
                Configure how long execution data is retained before automatic cleanup
              </CardDescription>
            </div>
            {hasUnsavedChanges && (
              <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
                Unsaved Changes
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Enable/Disable Switch */}
          <div className="flex items-center justify-between p-4 rounded-lg border">
            <div className="space-y-1">
              <Label htmlFor="retention-enabled" className="text-base font-medium">
                Enable Automatic Retention
              </Label>
              <p className="text-sm text-muted-foreground">
                Automatically delete executions older than the retention period
              </p>
            </div>
            <Switch
              id="retention-enabled"
              checked={isEnabled}
              onCheckedChange={setIsEnabled}
            />
          </div>

          {/* Retention Days Input */}
          <div className="space-y-2">
            <Label htmlFor="retention-days">Retention Period (Days)</Label>
            <Input
              id="retention-days"
              type="number"
              min={1}
              max={365}
              value={retentionDays}
              onChange={(e) => setRetentionDays(parseInt(e.target.value, 10) || 90)}
              className="max-w-xs"
            />
            <p className="text-sm text-muted-foreground">
              Executions older than this period will be deleted (1-365 days)
            </p>
          </div>

          {/* Min Executions to Keep */}
          <div className="space-y-2">
            <Label htmlFor="min-executions">Minimum Executions to Keep</Label>
            <Input
              id="min-executions"
              type="number"
              min={0}
              value={minExecutionsToKeep}
              onChange={(e) => setMinExecutionsToKeep(parseInt(e.target.value, 10) || 0)}
              className="max-w-xs"
            />
            <p className="text-sm text-muted-foreground">
              Safety threshold: Always keep at least this many executions, regardless of age
            </p>
          </div>

          {/* Info Banner */}
          <div className="flex gap-3 p-4 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-900">
            <Info className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-900 dark:text-blue-100">
              <p className="font-medium mb-1">About Retention Cleanup</p>
              <ul className="space-y-1 text-blue-800 dark:text-blue-200">
                <li>• Cleanup runs automatically daily at 2:00 AM</li>
                <li>
                  • Only executions older than {retentionDays} days will be considered for
                  deletion
                </li>
                <li>
                  • At least {minExecutionsToKeep} executions will always be preserved
                </li>
                <li>• Deleted execution data cannot be recovered</li>
              </ul>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3">
            <Button
              onClick={handleSave}
              disabled={!hasUnsavedChanges || updatePolicyMutation.isPending}
            >
              {updatePolicyMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Save Changes
            </Button>
            <Button
              variant="outline"
              onClick={handleReset}
              disabled={!hasUnsavedChanges || updatePolicyMutation.isPending}
            >
              Reset
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Manual Actions Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Manual Actions
          </CardTitle>
          <CardDescription>
            Preview and manually trigger retention cleanup operations
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Button variant="outline" onClick={handlePreview}>
              <Eye className="h-4 w-4 mr-2" />
              Preview Cleanup
            </Button>
            <Button
              variant="destructive"
              onClick={() => setShowCleanupDialog(true)}
              disabled={cleanupMutation.isPending}
            >
              {cleanupMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4 mr-2" />
              )}
              Run Cleanup Now
            </Button>
          </div>
          <p className="text-sm text-muted-foreground mt-3">
            Preview shows what would be deleted without making changes. Manual cleanup triggers
            immediate execution deletion.
          </p>
        </CardContent>
      </Card>

      {/* Cleanup Confirmation Dialog */}
      <AlertDialog open={showCleanupDialog} onOpenChange={setShowCleanupDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-600" />
              Confirm Cleanup Operation
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete executions older than {retentionDays} days.
              <br />
              <br />
              <strong>This action cannot be undone.</strong>
              <br />
              <br />
              {!isEnabled && (
                <span className="text-yellow-600">
                  Note: Retention is currently disabled. The cleanup will still respect your
                  configured settings.
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={cleanupMutation.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handleCleanup(false)}
              disabled={cleanupMutation.isPending}
              className="bg-red-600 hover:bg-red-700"
            >
              {cleanupMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Running...
                </>
              ) : (
                'Run Cleanup'
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Preview Dialog */}
      <AlertDialog open={showPreviewDialog} onOpenChange={setShowPreviewDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Eye className="h-5 w-5" />
              Cleanup Preview
            </AlertDialogTitle>
            <AlertDialogDescription>
              {preview ? (
                <div className="space-y-3 mt-4">
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Total Executions</p>
                      <p className="text-lg font-bold text-foreground">
                        {preview.totalExecutions.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Old Executions</p>
                      <p className="text-lg font-bold text-foreground">
                        {preview.oldExecutionsCount.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">To Be Deleted</p>
                      <p className="text-lg font-bold text-red-600">
                        {preview.executionsToDelete.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Cutoff Date</p>
                      <p className="text-lg font-bold text-foreground">
                        {formatDate(preview.cutoffDate)}
                      </p>
                    </div>
                  </div>
                  {preview.wouldDelete ? (
                    <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900">
                      <p className="text-sm text-red-900 dark:text-red-100">
                        ⚠️ Running cleanup would delete{' '}
                        <strong>{preview.executionsToDelete.toLocaleString()}</strong>{' '}
                        executions
                      </p>
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-900">
                      <p className="text-sm text-green-900 dark:text-green-100">
                        ✓ No executions would be deleted with current settings
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="h-6 w-6 animate-spin text-primary" />
                  <p className="ml-3">Loading preview...</p>
                </div>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Close</AlertDialogCancel>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
