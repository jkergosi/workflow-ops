/**
 * Service Status Indicator Component
 * Shows a banner when services are unhealthy.
 * Admins see detailed diagnostics, regular users see friendly messages.
 */
import React from 'react';
import { useAuth } from '@/lib/auth';
import { useHealthCheck } from '@/lib/use-health-check';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronDown,
  ChevronUp,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ServiceStatusIndicatorProps {
  /** Show even when healthy (for admin dashboards) */
  showWhenHealthy?: boolean;
  /** Position of the indicator */
  position?: 'fixed' | 'inline';
  /** Custom className */
  className?: string;
  /** Allow dismissing the indicator */
  dismissable?: boolean;
}

export function ServiceStatusIndicator({
  showWhenHealthy = false,
  position = 'fixed',
  className,
  dismissable = true,
}: ServiceStatusIndicatorProps) {
  const { user } = useAuth();
  const { status, healthStatus, isChecking, checkHealth } = useHealthCheck();
  const [expanded, setExpanded] = React.useState(false);
  const [dismissed, setDismissed] = React.useState(false);

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  // Reset dismissed state when status changes to unhealthy
  React.useEffect(() => {
    if (status === 'unhealthy') {
      setDismissed(false);
    }
  }, [status]);

  // If dismissed, don't show (unless status becomes unhealthy)
  if (dismissed && status !== 'unhealthy') {
    return null;
  }

  // Don't show anything if healthy and showWhenHealthy is false
  if (status === 'healthy' && !showWhenHealthy) {
    return null;
  }

  // Don't show for healthy status unless admin wants to see it
  if (status === 'healthy' && showWhenHealthy && !isAdmin) {
    return null;
  }

  const getStatusIcon = () => {
    if (isChecking) {
      return <Loader2 className="h-4 w-4 animate-spin" />;
    }
    switch (status) {
      case 'healthy':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'degraded':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'unhealthy':
        return <XCircle className="h-4 w-4 text-red-500" />;
    }
  };

  const getStatusMessage = () => {
    switch (status) {
      case 'healthy':
        return 'All services are operational';
      case 'degraded':
        return isAdmin
          ? 'Some services are experiencing issues'
          : 'We\'re experiencing minor issues. Some features may be limited.';
      case 'unhealthy':
        return isAdmin
          ? 'Critical services are unavailable'
          : 'We\'re experiencing technical difficulties. Please try again later.';
    }
  };

  const getAlertVariant = () => {
    switch (status) {
      case 'healthy':
        return 'default';
      case 'degraded':
        return 'default';
      case 'unhealthy':
        return 'destructive';
    }
  };

  const positionClasses = position === 'fixed'
    ? 'fixed bottom-4 right-4 z-50 max-w-md'
    : '';

  return (
    <Alert
      variant={getAlertVariant()}
      className={cn(
        positionClasses,
        status === 'degraded' && 'border-yellow-500 bg-yellow-50 dark:bg-yellow-950/20',
        className
      )}
    >
      <div className="flex items-start gap-3">
        {getStatusIcon()}
        <div className="flex-1">
          <AlertTitle className="flex items-center justify-between">
            <span>
              {status === 'healthy' ? 'System Status' : 'Service Status'}
            </span>
            <div className="flex items-center gap-2">
              <Badge
                variant={status === 'healthy' ? 'default' : status === 'degraded' ? 'secondary' : 'destructive'}
              >
                {status}
              </Badge>
              {dismissable && status !== 'unhealthy' && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5"
                  onClick={() => setDismissed(true)}
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>
          </AlertTitle>
          <AlertDescription className="mt-1">
            {getStatusMessage()}
          </AlertDescription>

          {/* Admin Diagnostics */}
          {isAdmin && healthStatus && (
            <div className="mt-3">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <>
                    <ChevronUp className="h-3 w-3 mr-1" />
                    Hide Details
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-3 w-3 mr-1" />
                    Show Details
                  </>
                )}
              </Button>

              {expanded && (
                <div className="mt-2 space-y-2 text-sm">
                  {healthStatus?.services && Object.keys(healthStatus.services).length > 0 ? (
                    <>
                      {Object.entries(healthStatus.services).map(([name, service]) => (
                        <div
                          key={name}
                          className="flex items-center justify-between p-2 rounded bg-muted/50"
                        >
                          <span className="capitalize font-medium">{name}</span>
                          <div className="flex items-center gap-2">
                            <Badge
                              variant={service?.status === 'healthy' ? 'default' : 'destructive'}
                              className="text-xs"
                            >
                              {service?.status || 'unknown'}
                            </Badge>
                            {service?.error && (
                              <span className="text-xs text-muted-foreground max-w-[200px] truncate">
                                {service.error}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                      {healthStatus?.timestamp && (
                        <p className="text-xs text-muted-foreground">
                          Last checked: {new Date(healthStatus.timestamp).toLocaleTimeString()}
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-muted-foreground italic">
                      No service details available. Health check may still be in progress.
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Refresh Button */}
          <div className="mt-3 flex justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => checkHealth()}
              disabled={isChecking}
              className="h-7 px-2 text-xs"
            >
              {isChecking ? (
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              ) : (
                <RefreshCw className="h-3 w-3 mr-1" />
              )}
              Refresh
            </Button>
          </div>
        </div>
      </div>
    </Alert>
  );
}

/**
 * Compact status indicator for headers/toolbars
 */
export function ServiceStatusBadge() {
  const { status, isChecking, checkHealth } = useHealthCheck();

  if (status === 'healthy') {
    return null;
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      className={cn(
        'h-7 px-2 text-xs gap-1',
        status === 'degraded' && 'text-yellow-600 hover:text-yellow-700',
        status === 'unhealthy' && 'text-red-600 hover:text-red-700'
      )}
      onClick={() => checkHealth()}
      disabled={isChecking}
    >
      {isChecking ? (
        <Loader2 className="h-3 w-3 animate-spin" />
      ) : status === 'degraded' ? (
        <AlertTriangle className="h-3 w-3" />
      ) : (
        <XCircle className="h-3 w-3" />
      )}
      {status === 'degraded' ? 'Degraded' : 'Offline'}
    </Button>
  );
}
