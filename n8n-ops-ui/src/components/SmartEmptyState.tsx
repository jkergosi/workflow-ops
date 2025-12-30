/**
 * Smart Empty State Component
 * Distinguishes between "no data" and "service unavailable" states.
 * Shows appropriate message based on service health.
 */
import React from 'react';
import { useAuth } from '@/lib/auth';
import { useHealthCheck } from '@/lib/use-health-check';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  AlertTriangle,
  RefreshCw,
  Loader2,
  Inbox,
  ServerOff,
} from 'lucide-react';

interface SmartEmptyStateProps {
  /** Title when there's genuinely no data */
  title?: string;
  /** Description when there's genuinely no data */
  description?: string;
  /** Icon component when there's genuinely no data */
  icon?: React.ComponentType<{ className?: string }>;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Error from data fetch (if any) */
  error?: Error | null;
  /** Retry function */
  onRetry?: () => void;
  /** Custom action button */
  action?: React.ReactNode;
  /** Children to render if not in empty/error state */
  children?: React.ReactNode;
  /** Custom className */
  className?: string;
}

export function SmartEmptyState({
  title = 'No data found',
  description = 'There is no data to display.',
  icon: Icon = Inbox,
  isLoading = false,
  error = null,
  onRetry,
  action,
  children,
  className,
}: SmartEmptyStateProps) {
  const { user } = useAuth();
  const { status, healthStatus, checkHealth, isChecking } = useHealthCheck();

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  // Check if error is due to service unavailability
  const isServiceError =
    (error as any)?.isServiceUnavailable ||
    error?.message?.includes('Service temporarily unavailable') ||
    error?.message?.includes('Network Error') ||
    status === 'unhealthy';

  // Loading state
  if (isLoading) {
    return (
      <div className={`flex flex-col items-center justify-center py-12 ${className}`}>
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-4" />
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  // Service unavailable state
  if (isServiceError || status === 'unhealthy') {
    return (
      <Card className={`border-yellow-200 bg-yellow-50 dark:bg-yellow-950/20 ${className}`}>
        <CardHeader className="text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center mb-4">
            <ServerOff className="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
          </div>
          <CardTitle>Service Unavailable</CardTitle>
          <CardDescription>
            {isAdmin ? (
              <>
                {error?.message || 'One or more services are currently unavailable.'}
                {healthStatus && (
                  <span className="block mt-2 text-xs">
                    Status: {Object.entries(healthStatus.services)
                      .filter(([, svc]) => svc?.status !== 'healthy')
                      .map(([name]) => name)
                      .join(', ') || 'Unknown'}
                  </span>
                )}
              </>
            ) : (
              "We're experiencing technical difficulties. Please try again in a few moments."
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          <Button
            onClick={() => {
              checkHealth();
              onRetry?.();
            }}
            disabled={isChecking}
          >
            {isChecking ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Try Again
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Error state (not service-related)
  if (error) {
    return (
      <Card className={`border-red-200 bg-red-50 dark:bg-red-950/20 ${className}`}>
        <CardHeader className="text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
            <AlertTriangle className="h-6 w-6 text-red-600 dark:text-red-400" />
          </div>
          <CardTitle>Something went wrong</CardTitle>
          <CardDescription>
            {isAdmin ? error.message : 'An error occurred while loading data.'}
          </CardDescription>
        </CardHeader>
        {onRetry && (
          <CardContent className="text-center">
            <Button onClick={onRetry}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </CardContent>
        )}
      </Card>
    );
  }

  // If children are provided and we're not in error state, render them
  if (children) {
    return <>{children}</>;
  }

  // Genuine empty state
  return (
    <div className={`flex flex-col items-center justify-center py-12 ${className}`}>
      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4">
        <Icon className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-medium mb-1">{title}</h3>
      <p className="text-muted-foreground text-sm mb-4">{description}</p>
      {action}
    </div>
  );
}

/**
 * HOC to wrap a component with service health awareness
 */
export function withServiceHealth<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  emptyStateProps?: Partial<SmartEmptyStateProps>
) {
  return function WithServiceHealth(props: P & { error?: Error | null; isLoading?: boolean }) {
    const { status } = useHealthCheck();

    if (status === 'unhealthy' || props.error) {
      return (
        <SmartEmptyState
          error={props.error}
          isLoading={props.isLoading}
          {...emptyStateProps}
        />
      );
    }

    return <WrappedComponent {...props} />;
  };
}
