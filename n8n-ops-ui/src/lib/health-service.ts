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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

class HealthService {
  private status: ServiceStatus = 'healthy';
  private lastCheck: HealthStatus | null = null;
  private listeners: Set<HealthListener> = new Set();
  private pollingInterval: number | null = null;
  private isPolling = false;
  private subscriberCount = 0;
  private isPageVisible = true;
  private consecutiveErrors = 0;
  private currentCheckPromise: Promise<HealthStatus> | null = null;
  private baseInterval = 60000; // 60 seconds base interval
  private maxInterval = 300000; // 5 minutes max interval

  /**
   * Perform a health check against the backend
   * Uses request deduplication to prevent concurrent duplicate requests
   */
  async checkHealth(): Promise<HealthStatus> {
    // If a check is already in progress, return the same promise
    if (this.currentCheckPromise) {
      return this.currentCheckPromise;
    }

    this.currentCheckPromise = this._performCheck();
    
    try {
      const result = await this.currentCheckPromise;
      return result;
    } finally {
      this.currentCheckPromise = null;
    }
  }

  private async _performCheck(): Promise<HealthStatus> {
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
      this.consecutiveErrors = 0; // Reset error count on success
      this.notifyListeners();
      return data;
    } catch (error) {
      this.consecutiveErrors++;
      
      // Network error or timeout - service is likely down
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
   * @param interval Polling interval in milliseconds (default: 60000ms)
   */
  startPolling(interval = 60000): void {
    if (this.isPolling) return;

    this.baseInterval = interval;
    this.isPolling = true;
    
    // Set up page visibility listener
    this._setupVisibilityListener();
    
    // Do initial check, then schedule next check
    this.checkHealth().finally(() => {
      this._scheduleNextCheck();
    });
  }

  private _scheduleNextCheck(): void {
    if (!this.isPolling) return;

    // Calculate interval with exponential backoff on errors
    // Formula: baseInterval * (2 ^ min(consecutiveErrors, 3))
    // This gives us: 60s, 120s, 240s, 480s (capped at maxInterval)
    const backoffMultiplier = Math.min(Math.pow(2, this.consecutiveErrors), 4);
    const dynamicInterval = Math.min(
      this.baseInterval * backoffMultiplier,
      this.maxInterval
    );

    // Clear existing timeout
    if (this.pollingInterval !== null) {
      clearTimeout(this.pollingInterval);
    }

    // Set up new interval with dynamic timing
    this.pollingInterval = window.setTimeout(() => {
      // Only check if page is visible
      if (this.isPageVisible) {
        this.checkHealth().finally(() => {
          // Schedule next check after current one completes
          this._scheduleNextCheck();
        });
      } else {
        // If page not visible, reschedule without checking
        this._scheduleNextCheck();
      }
    }, dynamicInterval);
  }

  private _setupVisibilityListener(): void {
    if (typeof document === 'undefined') return;

    const handleVisibilityChange = () => {
      this.isPageVisible = !document.hidden;
      
      // If page becomes visible and we haven't checked recently, do a check
      if (this.isPageVisible && this.isPolling) {
        const lastCheckTime = this.lastCheck 
          ? new Date(this.lastCheck.timestamp).getTime() 
          : 0;
        const timeSinceLastCheck = Date.now() - lastCheckTime;
        
        // If last check was more than 30 seconds ago, check now
        if (timeSinceLastCheck > 30000) {
          this.checkHealth();
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    // Store cleanup function
    this._visibilityCleanup = () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }

  private _visibilityCleanup: (() => void) | null = null;

  /**
   * Stop polling for health status
   */
  stopPolling(): void {
    if (this.pollingInterval !== null) {
      clearTimeout(this.pollingInterval);
      this.pollingInterval = null;
    }
    
    if (this._visibilityCleanup) {
      this._visibilityCleanup();
      this._visibilityCleanup = null;
    }
    
    this.isPolling = false;
    this.consecutiveErrors = 0; // Reset error count when stopping
  }

  /**
   * Subscribe to health status changes
   * Automatically manages polling based on subscriber count
   */
  subscribe(listener: HealthListener): () => void {
    const wasEmpty = this.listeners.size === 0;
    this.listeners.add(listener);
    this.subscriberCount++;

    // Start polling when first subscriber joins
    if (wasEmpty && this.subscriberCount === 1) {
      this.startPolling();
    }

    // Immediately notify with current status if available
    if (this.lastCheck) {
      listener(this.lastCheck);
    }

    // Return unsubscribe function
    return () => {
      this.listeners.delete(listener);
      this.subscriberCount = Math.max(0, this.subscriberCount - 1);
      
      // Stop polling when last subscriber leaves
      if (this.subscriberCount === 0) {
        this.stopPolling();
      }
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

// No auto-start - polling will start when first subscriber joins
