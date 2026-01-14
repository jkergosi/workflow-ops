/**
 * Reusable component for displaying background job progress.
 * Shows progress bar, current step, and status for sync/backup/restore jobs.
 */

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Loader2, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface BackgroundJobProgressProps {
  jobId: string;
  jobType: 'sync' | 'backup' | 'restore';
  status: 'running' | 'completed' | 'failed';
  currentStep?: string;
  current: number;
  total: number;
  message?: string;
  currentWorkflowName?: string;
  errors?: string[] | Record<string, any>;
  onDismiss?: () => void;
}

export function BackgroundJobProgress({
  jobId: _jobId,
  jobType,
  status,
  currentStep,
  current,
  total,
  message,
  currentWorkflowName,
  errors,
  onDismiss: _onDismiss,
}: BackgroundJobProgressProps) {
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0;

  const getJobTypeLabel = () => {
    switch (jobType) {
      case 'sync':
        return 'Environment Sync';
      case 'backup':
        return 'GitHub Backup';
      case 'restore':
        return 'GitHub Restore';
      default:
        return 'Background Job';
    }
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'running':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getStatusVariant = () => {
    switch (status) {
      case 'running':
        return 'secondary';
      case 'completed':
        return 'default';
      case 'failed':
        return 'destructive';
      default:
        return 'outline';
    }
  };

  const formatStepName = (step: string) => {
    return step
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-800 dark:bg-blue-950/30">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            {getStatusIcon()}
            {getJobTypeLabel()}
          </CardTitle>
          <Badge variant={getStatusVariant()}>{status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {status === 'running' && (
          <>
            {currentStep && (
              <p className="text-sm text-muted-foreground">
                Current step: <span className="font-medium">{formatStepName(currentStep)}</span>
              </p>
            )}
            {currentWorkflowName && (
              <p className="text-sm text-muted-foreground">
                Working on: <span className="font-medium">{currentWorkflowName}</span>
              </p>
            )}
            {message && <p className="text-sm text-muted-foreground">{message}</p>}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>Progress</span>
                <span>
                  {current} / {total} ({percentage}%)
                </span>
              </div>
              <Progress value={percentage} className="h-2" />
            </div>
          </>
        )}

        {status === 'completed' && (
          <div className="space-y-2">
            <p className="text-sm text-green-600 dark:text-green-400">
              {message || 'Job completed successfully'}
            </p>
            {total > 0 && (
              <p className="text-xs text-muted-foreground">
                Completed {current} of {total} items
              </p>
            )}
          </div>
        )}

        {status === 'failed' && (
          <div className="space-y-2">
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {message || 'Job failed'}
              </AlertDescription>
            </Alert>
            {errors && (
              <div className="text-xs text-muted-foreground space-y-1">
                {Array.isArray(errors) ? (
                  errors.map((error, idx) => (
                    <div key={idx} className="text-red-600 dark:text-red-400">
                      {error}
                    </div>
                  ))
                ) : (
                  <div className="text-red-600 dark:text-red-400">
                    {JSON.stringify(errors, null, 2)}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

