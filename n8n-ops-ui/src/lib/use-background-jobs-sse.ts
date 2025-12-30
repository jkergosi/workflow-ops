/**
 * SSE Hook for real-time background job updates (sync, backup, restore).
 *
 * Connects to the backend SSE endpoint and updates TanStack Query cache
 * in response to server-sent events for background jobs.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

// Convert snake_case keys to camelCase
function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function transformKeys(obj: any): any {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) return obj.map(transformKeys);
  if (typeof obj !== 'object') return obj;

  const result: any = {};
  for (const key in obj) {
    const camelKey = snakeToCamel(key);
    result[camelKey] = transformKeys(obj[key]);
  }
  return result;
}

interface SSEEvent {
  event_id: string;
  type: string;
  tenant_id: string;
  env_id?: string;
  job_id?: string;
  ts: string;
  payload: any;
}

interface UseBackgroundJobsSSEOptions {
  enabled?: boolean;
  environmentId?: string; // For filtering by environment
  jobId?: string; // For filtering by specific job
}

interface UseBackgroundJobsSSEReturn {
  isConnected: boolean;
  connectionError: string | null;
}

export function useBackgroundJobsSSE(
  options: UseBackgroundJobsSSEOptions = {}
): UseBackgroundJobsSSEReturn {
  const { enabled = true, environmentId, jobId } = options;
  const queryClient = useQueryClient();

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const lastEventIdRef = useRef<string | null>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Max reconnection attempts and backoff
  const MAX_RECONNECT_ATTEMPTS = 10;
  const BASE_RECONNECT_DELAY = 1000; // 1 second
  const MAX_RECONNECT_DELAY = 30000; // 30 seconds

  const getReconnectDelay = useCallback(() => {
    const delay = Math.min(
      BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttemptRef.current),
      MAX_RECONNECT_DELAY
    );
    return delay;
  }, []);

  const handleSyncProgress = useCallback(
    (data: any) => {
      const progress = transformKeys(data);
      const envId = progress.environmentId || environmentId;
      const jId = progress.jobId || jobId;

      // Update job status in cache
      if (jId) {
        queryClient.setQueryData(['background-job', jId], (old: any) => {
          if (!old) return { data: progress };
          return {
            ...old,
            data: {
              ...old.data,
              ...progress,
            },
          };
        });
      }

      // Update environment jobs list
      if (envId) {
        queryClient.setQueryData(['environment-jobs', envId], (old: any) => {
          if (!old?.data) return old;
          return {
            ...old,
            data: old.data.map((job: any) =>
              job.id === jId ? { ...job, ...progress } : job
            ),
          };
        });
      }
    },
    [queryClient, environmentId, jobId]
  );

  const handleBackupProgress = useCallback(
    (data: any) => {
      const progress = transformKeys(data);
      const envId = progress.environmentId || environmentId;
      const jId = progress.jobId || jobId;

      // Update job status in cache
      if (jId) {
        queryClient.setQueryData(['background-job', jId], (old: any) => {
          if (!old) return { data: progress };
          return {
            ...old,
            data: {
              ...old.data,
              ...progress,
            },
          };
        });
      }

      // Update environment jobs list
      if (envId) {
        queryClient.setQueryData(['environment-jobs', envId], (old: any) => {
          if (!old?.data) return old;
          return {
            ...old,
            data: old.data.map((job: any) =>
              job.id === jId ? { ...job, ...progress } : job
            ),
          };
        });
      }
    },
    [queryClient, environmentId, jobId]
  );

  const handleRestoreProgress = useCallback(
    (data: any) => {
      const progress = transformKeys(data);
      const envId = progress.environmentId || environmentId;
      const jId = progress.jobId || jobId;

      // Update job status in cache
      if (jId) {
        queryClient.setQueryData(['background-job', jId], (old: any) => {
          if (!old) return { data: progress };
          return {
            ...old,
            data: {
              ...old.data,
              ...progress,
            },
          };
        });
      }

      // Update environment jobs list
      if (envId) {
        queryClient.setQueryData(['environment-jobs', envId], (old: any) => {
          if (!old?.data) return old;
          return {
            ...old,
            data: old.data.map((job: any) =>
              job.id === jId ? { ...job, ...progress } : job
            ),
          };
        });
      }
    },
    [queryClient, environmentId, jobId]
  );

  const connect = useCallback(() => {
    if (!enabled) return;

    // Build SSE URL with filters
    // Note: VITE_API_BASE_URL already includes /api/v1
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4000/api/v1';
    let url = `${baseUrl}/sse/stream`;
    const params = new URLSearchParams();

    // Include auth token since EventSource doesn't support custom headers
    const token = localStorage.getItem('auth_token');
    if (token) params.append('token', token);

    if (environmentId) params.append('env_id', environmentId);
    if (jobId) params.append('job_id', jobId);
    if (params.toString()) url += `?${params.toString()}`;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setConnectionError(null);
      reconnectAttemptRef.current = 0;
    };

    eventSource.onerror = (error) => {
      setIsConnected(false);
      setConnectionError('SSE connection error');

      // Attempt reconnection
      if (reconnectAttemptRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = getReconnectDelay();
        reconnectAttemptRef.current += 1;

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      } else {
        setConnectionError('Max reconnection attempts reached');
      }
    };

    // Handle sync progress events
    eventSource.addEventListener('sync.progress', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        handleSyncProgress(data);
      } catch (error) {
        console.error('Failed to parse sync.progress event:', error);
      }
    });

    // Handle backup progress events
    eventSource.addEventListener('backup.progress', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        handleBackupProgress(data);
      } catch (error) {
        console.error('Failed to parse backup.progress event:', error);
      }
    });

    // Handle restore progress events
    eventSource.addEventListener('restore.progress', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        handleRestoreProgress(data);
      } catch (error) {
        console.error('Failed to parse restore.progress event:', error);
      }
    });
  }, [enabled, environmentId, jobId, handleSyncProgress, handleBackupProgress, handleRestoreProgress, getReconnectDelay]);

  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [enabled, connect]);

  return {
    isConnected,
    connectionError,
  };
}

