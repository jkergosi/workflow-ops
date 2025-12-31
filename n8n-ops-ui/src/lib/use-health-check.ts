/**
 * React hook for monitoring service health status.
 * Provides reactive access to health service state.
 */
import { useState, useEffect, useCallback } from 'react';
import { healthService, type HealthStatus, type ServiceStatus } from './health-service';

export interface UseHealthCheckResult {
  /** Current overall health status */
  status: ServiceStatus;
  /** Full health check result with service details */
  healthStatus: HealthStatus | null;
  /** Whether we're currently checking health */
  isChecking: boolean;
  /** Manually trigger a health check */
  checkHealth: () => Promise<HealthStatus>;
  /** Check if a specific service is healthy */
  isServiceHealthy: (serviceName: string) => boolean;
  /** Get error message for a specific service */
  getServiceError: (serviceName: string) => string | undefined;
}

/**
 * Hook to monitor backend service health
 * @param autoCheck Whether to start automatic polling (default: true)
 * @param pollInterval Polling interval in ms (default: 30000)
 */
export function useHealthCheck(
  autoCheck = true,
  pollInterval = 30000
): UseHealthCheckResult {
  const [status, setStatus] = useState<ServiceStatus>('healthy');
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(
    healthService.getLastCheck()
  );
  const [isChecking, setIsChecking] = useState(false);
  const [previousStatus, setPreviousStatus] = useState<ServiceStatus>('healthy');

  useEffect(() => {
    // Subscribe to health status changes
    const unsubscribe = healthService.subscribe((newStatus) => {
      const newStatusValue = newStatus.status;
      
      // Check for service recovery (unhealthy -> healthy/degraded)
      if (previousStatus === 'unhealthy' && (newStatusValue === 'healthy' || newStatusValue === 'degraded')) {
        // Trigger recovery notification
        if (typeof window !== 'undefined' && window.dispatchEvent) {
          window.dispatchEvent(new CustomEvent('service-recovered', {
            detail: { from: previousStatus, to: newStatusValue }
          }));
        }
      }
      
      setPreviousStatus(newStatusValue);
      setStatus(newStatusValue);
      setHealthStatus(newStatus);
      setIsChecking(false);
    });

    // Start polling if autoCheck is enabled
    if (autoCheck) {
      healthService.startPolling(pollInterval);
    }

    return () => {
      unsubscribe();
    };
  }, [autoCheck, pollInterval, previousStatus]);

  const checkHealth = useCallback(async (): Promise<HealthStatus> => {
    setIsChecking(true);
    try {
      return await healthService.checkHealth();
    } finally {
      setIsChecking(false);
    }
  }, []);

  const isServiceHealthy = useCallback((serviceName: string): boolean => {
    return healthService.isServiceHealthy(serviceName);
  }, []);

  const getServiceError = useCallback((serviceName: string): string | undefined => {
    if (!healthStatus) return undefined;
    const service = healthStatus.services[serviceName];
    return service?.error;
  }, [healthStatus]);

  return {
    status,
    healthStatus,
    isChecking,
    checkHealth,
    isServiceHealthy,
    getServiceError,
  };
}

/**
 * Hook to get connection status (simplified version)
 */
export function useConnectionStatus(): 'online' | 'offline' | 'degraded' {
  const { status } = useHealthCheck();

  switch (status) {
    case 'healthy':
      return 'online';
    case 'degraded':
      return 'degraded';
    case 'unhealthy':
      return 'offline';
    default:
      return 'online';
  }
}
