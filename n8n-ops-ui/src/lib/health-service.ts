/**
 * Health Service for monitoring backend service status.
 * Provides polling-based health checks and event-driven status updates.
 */

export type ServiceStatus = 'healthy' | 'degraded' | 'unhealthy';

export interface ServiceHealth {
  status: ServiceStatus;
  error?: string;
  latency_ms?: number;
}

export interface HealthStatus {
  status: ServiceStatus;
  timestamp: string;
  services: {
    database?: ServiceHealth;
    supabase?: ServiceHealth;
    [key: string]: ServiceHealth | undefined;
  };
}

type HealthListener = (status: HealthStatus) => void;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4000/api/v1';

class HealthService {
  private status: ServiceStatus = 'healthy';
  private lastCheck: HealthStatus | null = null;
  private listeners: Set<HealthListener> = new Set();
  private pollingInterval: number | null = null;
  private isPolling = false;

  /**
   * Perform a health check against the backend
   */
  async checkHealth(): Promise<HealthStatus> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      const response = await fetch(`${API_BASE_URL}/health`, {
        signal: controller.signal,
        headers: {
          'Accept': 'application/json',
        },
      });

      clearTimeout(timeoutId);

      const data: HealthStatus = await response.json();
      this.status = data.status;
      this.lastCheck = data;
      this.notifyListeners();
      return data;
    } catch (error) {
      // Network error or timeout - service is likely down
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      const unhealthyStatus: HealthStatus = {
        status: 'unhealthy',
        timestamp: new Date().toISOString(),
        services: {
          database: { status: 'unhealthy', error: 'Connection failed' },
          supabase: { status: 'unhealthy', error: 'Connection failed' },
        },
      };

      // Check if it's a network error vs abort
      if (error instanceof DOMException && error.name === 'AbortError') {
        unhealthyStatus.services.database = { status: 'unhealthy', error: 'Request timeout' };
        unhealthyStatus.services.supabase = { status: 'unhealthy', error: 'Request timeout' };
      }

      this.status = 'unhealthy';
      this.lastCheck = unhealthyStatus;
      this.notifyListeners();
      return unhealthyStatus;
    }
  }

  /**
   * Start polling for health status
   * @param interval Polling interval in milliseconds (default: 30000ms)
   */
  startPolling(interval = 30000): void {
    if (this.isPolling) return;

    this.isPolling = true;
    // Do initial check
    this.checkHealth();

    // Set up interval
    this.pollingInterval = window.setInterval(() => {
      this.checkHealth();
    }, interval);
  }

  /**
   * Stop polling for health status
   */
  stopPolling(): void {
    if (this.pollingInterval !== null) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
    this.isPolling = false;
  }

  /**
   * Subscribe to health status changes
   */
  subscribe(listener: HealthListener): () => void {
    this.listeners.add(listener);

    // Immediately notify with current status if available
    if (this.lastCheck) {
      listener(this.lastCheck);
    }

    // Return unsubscribe function
    return () => {
      this.listeners.delete(listener);
    };
  }

  /**
   * Get current status
   */
  getStatus(): ServiceStatus {
    return this.status;
  }

  /**
   * Get last health check result
   */
  getLastCheck(): HealthStatus | null {
    return this.lastCheck;
  }

  /**
   * Check if a specific service is healthy
   */
  isServiceHealthy(serviceName: string): boolean {
    if (!this.lastCheck) return true; // Assume healthy if no check done
    const service = this.lastCheck.services[serviceName];
    return service?.status === 'healthy';
  }

  private notifyListeners(): void {
    if (this.lastCheck) {
      this.listeners.forEach(listener => {
        try {
          listener(this.lastCheck!);
        } catch (error) {
          console.error('Health listener error:', error);
        }
      });
    }
  }
}

// Export singleton instance
export const healthService = new HealthService();

// Auto-start polling when module is imported
// This can be disabled by calling healthService.stopPolling()
if (typeof window !== 'undefined') {
  // Only start in browser environment
  healthService.startPolling();
}
