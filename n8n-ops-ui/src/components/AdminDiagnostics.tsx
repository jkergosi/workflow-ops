/**
 * Admin Diagnostics Panel
 * Full diagnostic view for administrators showing all service statuses.
 */
import React from 'react';
import { useAuth } from '@/lib/auth';
import { useHealthCheck } from '@/lib/use-health-check';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Loader2,
  Database,
  Cloud,
  Server,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface AdminDiagnosticsProps {
  /** Custom className */
  className?: string;
}

const serviceIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  database: Database,
  supabase: Cloud,
  backend: Server,
};

export function AdminDiagnostics({ className }: AdminDiagnosticsProps) {
  const { user } = useAuth();
  const { status, healthStatus, isChecking, checkHealth } = useHealthCheck();

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  // Don't render for non-admin users
  if (!isAdmin) {
    return null;
  }

  const getStatusIcon = (serviceStatus: string) => {
    switch (serviceStatus) {
      case 'healthy':
        return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case 'degraded':
        return <AlertTriangle className="h-5 w-5 text-yellow-500" />;
      case 'unhealthy':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <AlertTriangle className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStatusBadgeVariant = (serviceStatus: string) => {
    switch (serviceStatus) {
      case 'healthy':
        return 'default';
      case 'degraded':
        return 'secondary';
      case 'unhealthy':
        return 'destructive';
      default:
        return 'outline';
    }
  };

  return (
    <Card
      className={cn(
        status !== 'healthy' && 'border-yellow-200 bg-yellow-50 dark:bg-yellow-950/20',
        className
      )}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              System Diagnostics
              {isChecking && <Loader2 className="h-4 w-4 animate-spin" />}
            </CardTitle>
            <CardDescription>
              Real-time service health monitoring
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={getStatusBadgeVariant(status)} className="capitalize">
              {status}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={() => checkHealth()}
              disabled={isChecking}
            >
              {isChecking ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {healthStatus ? (
          <div className="space-y-3">
            {Object.entries(healthStatus.services).map(([name, service]) => {
              const Icon = serviceIcons[name] || Server;
              return (
                <div
                  key={name}
                  className={cn(
                    'flex items-center justify-between p-3 rounded-lg border',
                    service?.status === 'healthy'
                      ? 'bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800'
                      : service?.status === 'degraded'
                      ? 'bg-yellow-50 dark:bg-yellow-950/20 border-yellow-200 dark:border-yellow-800'
                      : 'bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800'
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Icon className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium capitalize">{name}</p>
                      {service?.error && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {service.error}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {service?.latency_ms && (
                      <span className="text-xs text-muted-foreground">
                        {service.latency_ms}ms
                      </span>
                    )}
                    {getStatusIcon(service?.status || 'unknown')}
                  </div>
                </div>
              );
            })}

            <div className="pt-2 border-t text-xs text-muted-foreground flex items-center justify-between">
              <span>
                Last checked: {new Date(healthStatus.timestamp).toLocaleString()}
              </span>
              <span>
                Auto-refresh: 30s
              </span>
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
            <p>Checking service health...</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Compact inline diagnostics for dashboard widgets
 */
export function DiagnosticsInline() {
  const { user } = useAuth();
  const { status, healthStatus } = useHealthCheck();

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';

  if (!isAdmin || status === 'healthy') {
    return null;
  }

  const unhealthyServices = healthStatus
    ? Object.entries(healthStatus.services)
        .filter(([, service]) => service?.status !== 'healthy')
        .map(([name]) => name)
    : [];

  return (
    <div className="flex items-center gap-2 text-sm">
      {status === 'degraded' ? (
        <AlertTriangle className="h-4 w-4 text-yellow-500" />
      ) : (
        <XCircle className="h-4 w-4 text-red-500" />
      )}
      <span>
        {unhealthyServices.length > 0
          ? `Issues with: ${unhealthyServices.join(', ')}`
          : 'System issues detected'}
      </span>
    </div>
  );
}
