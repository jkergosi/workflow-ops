/**
 * Smart Empty State Component
 * Distinguishes between "no data" and "service unavailable" states.
 * Shows appropriate message based on service health.
 * Now with enhanced loading states showing progress and ETA.
 *
 * Supports rich empty states with:
 * - Contextual illustrations
 * - Feature bullets explaining value
 * - Tutorial/help links
 * - Video walkthroughs
 * - Prominent CTAs
 */
import React from 'react';
import { useAuth } from '@/lib/auth';
import { useHealthCheck } from '@/lib/use-health-check';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LoadingState } from '@/components/ui/loading-state';
import { SkeletonTableRows, SkeletonCard, SkeletonList } from '@/components/ui/skeleton';
import { InformativeEmptyState, type HelpLink, type QuickAction } from '@/components/ui/informative-empty-state';
import { type IllustrationType } from '@/components/ui/empty-state-illustration';
import {
  AlertTriangle,
  RefreshCw,
  Loader2,
  Inbox,
  ServerOff,
} from 'lucide-react';

type LoadingVariant = 'spinner' | 'skeleton-table' | 'skeleton-cards' | 'skeleton-list' | 'progress';

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
  /** What resource is being loaded (e.g., "workflows", "environments") */
  loadingResource?: string;
  /** Expected count of items being loaded (for display) */
  loadingCount?: number;
  /** Loading variant - determines how loading state is displayed */
  loadingVariant?: LoadingVariant;
  /** Current progress (0-100) for progress variant */
  loadingProgress?: number;
  /** Estimated time remaining in seconds */
  loadingEta?: number;
  /** Current step being performed */
  loadingStep?: string;
  /** Number of skeleton rows/cards/items to show */
  skeletonCount?: number;

  // Enhanced empty state options (for rich, informative empty states)
  /** Illustration type to display instead of icon */
  illustration?: IllustrationType;
  /** Feature bullets explaining what the area is for */
  featureBullets?: string[];
  /** Help/documentation links */
  helpLinks?: HelpLink[];
  /** Video tutorial info */
  videoTutorial?: {
    title: string;
    url: string;
    duration?: string;
  };
  /** Secondary descriptive text */
  secondaryText?: string;
  /** Size variant for the empty state */
  size?: 'sm' | 'md' | 'lg';
  /** Whether to use enhanced informative empty state */
  useInformativeStyle?: boolean;
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
  loadingResource,
  loadingCount,
  loadingVariant = 'spinner',
  loadingProgress,
  loadingEta,
  loadingStep,
  skeletonCount = 5,
  // Enhanced options
  illustration,
  featureBullets,
  helpLinks,
  videoTutorial,
  secondaryText,
  size = 'md',
  useInformativeStyle,
}: SmartEmptyStateProps) {
  const { user } = useAuth();
  const { status, healthStatus, checkHealth, isChecking } = useHealthCheck();

  const isAdmin = user?.role === 'admin' || user?.isPlatformAdmin;

  // Check if error is due to service unavailability
  const isServiceError =
    (error as any)?.isServiceUnavailable ||
    error?.message?.includes('Service temporarily unavailable') ||
    error?.message?.includes('Network Error') ||
    status === 'unhealthy';

  // Loading state with enhanced variants
  if (isLoading) {
    // Skeleton table variant
    if (loadingVariant === 'skeleton-table') {
      return (
        <div className={`space-y-4 ${className}`}>
          {loadingResource && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading {loadingResource}...</span>
            </div>
          )}
          <SkeletonTableRows rows={skeletonCount} columns={4} />
        </div>
      );
    }

    // Skeleton cards variant
    if (loadingVariant === 'skeleton-cards') {
      return (
        <div className={`space-y-4 ${className}`}>
          {loadingResource && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading {loadingResource}...</span>
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: skeletonCount }).map((_, i) => (
              <SkeletonCard key={i} showHeader={true} contentLines={2} />
            ))}
          </div>
        </div>
      );
    }

    // Skeleton list variant
    if (loadingVariant === 'skeleton-list') {
      return (
        <div className={`space-y-4 ${className}`}>
          {loadingResource && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Loading {loadingResource}...</span>
            </div>
          )}
          <SkeletonList items={skeletonCount} showIcons={true} />
        </div>
      );
    }

    // Progress variant with detailed information
    if (loadingVariant === 'progress') {
      return (
        <div className={className}>
          <LoadingState
            resource={loadingResource}
            count={loadingCount}
            progress={loadingProgress}
            currentStep={loadingStep}
            estimatedTimeRemaining={loadingEta}
            indeterminate={loadingProgress === undefined}
            size="md"
          />
        </div>
      );
    }

    // Default spinner variant with enhanced message
    return (
      <div className={className}>
        <LoadingState
          resource={loadingResource}
          count={loadingCount}
          size="md"
        />
      </div>
    );
  }

  // Service unavailable state (isServiceError already includes status === 'unhealthy' check)
  if (isServiceError) {
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

  // Determine if we should use the enhanced informative style
  const shouldUseInformativeStyle = useInformativeStyle ||
    illustration ||
    featureBullets?.length ||
    helpLinks?.length ||
    videoTutorial;

  // Genuine empty state - Enhanced Informative Style
  if (shouldUseInformativeStyle) {
    // Convert action ReactNode to QuickAction if it's a button
    const primaryAction: QuickAction | undefined = onRetry
      ? { label: 'Retry', onClick: onRetry, icon: RefreshCw }
      : undefined;

    return (
      <InformativeEmptyState
        title={title}
        description={description}
        illustration={illustration}
        icon={Icon as any}
        secondaryText={secondaryText}
        featureBullets={featureBullets}
        helpLinks={helpLinks}
        videoTutorial={videoTutorial}
        size={size}
        primaryAction={primaryAction}
        className={className}
      >
        {action}
      </InformativeEmptyState>
    );
  }

  // Genuine empty state - Simple Style
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
