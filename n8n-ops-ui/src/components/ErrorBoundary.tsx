/**
 * Error Boundary Component
 * Catches JavaScript errors in child component tree and displays fallback UI.
 */
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle, RefreshCw, Home, Bug } from 'lucide-react';

interface Props {
  children: ReactNode;
  /** Custom fallback component */
  fallback?: ReactNode;
  /** Called when error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  /** Show technical details (for admins) */
  showDetails?: boolean;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo });

    // Log to console in development
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    // Call custom error handler if provided
    this.props.onError?.(error, errorInfo);
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  private handleGoHome = (): void => {
    window.location.href = '/';
  };

  private handleReload = (): void => {
    window.location.reload();
  };

  public render(): ReactNode {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <ErrorFallback
          error={this.state.error}
          errorInfo={this.state.errorInfo}
          showDetails={this.props.showDetails}
          onRetry={this.handleRetry}
          onGoHome={this.handleGoHome}
          onReload={this.handleReload}
        />
      );
    }

    return this.props.children;
  }
}

interface ErrorFallbackProps {
  error: Error | null;
  errorInfo?: ErrorInfo | null;
  showDetails?: boolean;
  onRetry?: () => void;
  onGoHome?: () => void;
  onReload?: () => void;
}

export function ErrorFallback({
  error,
  errorInfo,
  showDetails = false,
  onRetry,
  onGoHome,
  onReload,
}: ErrorFallbackProps) {
  const [detailsExpanded, setDetailsExpanded] = React.useState(false);

  return (
    <div className="min-h-[400px] flex items-center justify-center p-6">
      <Card className="max-w-lg w-full">
        <CardHeader className="text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-red-100 dark:bg-red-900/20 flex items-center justify-center mb-4">
            <AlertTriangle className="h-6 w-6 text-red-600 dark:text-red-400" />
          </div>
          <CardTitle>Something went wrong</CardTitle>
          <CardDescription>
            We encountered an unexpected error. Please try again or contact support if the problem persists.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Error message */}
          {error && (
            <div className="p-3 rounded-lg bg-muted text-sm">
              <p className="font-medium text-destructive">{error.message}</p>
            </div>
          )}

          {/* Technical details for admins */}
          {showDetails && error && (
            <div>
              <Button
                variant="ghost"
                size="sm"
                className="text-xs"
                onClick={() => setDetailsExpanded(!detailsExpanded)}
              >
                <Bug className="h-3 w-3 mr-1" />
                {detailsExpanded ? 'Hide' : 'Show'} Technical Details
              </Button>
              {detailsExpanded && (
                <pre className="mt-2 p-3 rounded-lg bg-muted text-xs overflow-auto max-h-48">
                  {error.stack}
                  {errorInfo?.componentStack && (
                    <>
                      {'\n\nComponent Stack:'}
                      {errorInfo.componentStack}
                    </>
                  )}
                </pre>
              )}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex flex-col sm:flex-row gap-2">
            {onRetry && (
              <Button onClick={onRetry} className="flex-1">
                <RefreshCw className="h-4 w-4 mr-2" />
                Try Again
              </Button>
            )}
            {onGoHome && (
              <Button variant="outline" onClick={onGoHome} className="flex-1">
                <Home className="h-4 w-4 mr-2" />
                Go to Dashboard
              </Button>
            )}
            {onReload && (
              <Button variant="ghost" onClick={onReload} className="flex-1">
                Reload Page
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/**
 * Service unavailable message component
 * Shows when backend services are down
 */
interface ServiceUnavailableProps {
  isAdmin?: boolean;
  serviceName?: string;
  error?: string;
  onRetry?: () => void;
}

export function ServiceUnavailableMessage({
  isAdmin = false,
  serviceName,
  error,
  onRetry,
}: ServiceUnavailableProps) {
  return (
    <div className="min-h-[300px] flex items-center justify-center p-6">
      <Card className="max-w-md w-full">
        <CardHeader className="text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-yellow-100 dark:bg-yellow-900/20 flex items-center justify-center mb-4">
            <AlertTriangle className="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
          </div>
          <CardTitle>Service Unavailable</CardTitle>
          <CardDescription>
            {isAdmin ? (
              <>
                {serviceName
                  ? `The ${serviceName} service is currently unavailable.`
                  : 'One or more services are currently unavailable.'}
                {error && (
                  <span className="block mt-2 text-xs font-mono text-destructive">
                    Error: {error}
                  </span>
                )}
              </>
            ) : (
              "We're experiencing technical difficulties. Please try again in a few moments."
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          {onRetry && (
            <Button onClick={onRetry}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Try Again
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
