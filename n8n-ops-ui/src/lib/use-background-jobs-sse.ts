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

interface UseBackgroundJobsSSEOptions {
  enabled?: boolean;
  environmentId?: string; // For filtering by environment
  jobId?: string; // For filtering by specific job
  onLogMessage?: (message: LogMessage) => void; // Callback for log messages
  onProgressEvent?: (eventType: string, payload: any) => void; // Callback for parsed SSE events
}

export type LogMessage = {
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  phase?: string;
  details?: any;
};

interface UseBackgroundJobsSSEReturn {
  isConnected: boolean;
  connectionError: string | null;
}

export function useBackgroundJobsSSE(
  options: UseBackgroundJobsSSEOptions = {}
): UseBackgroundJobsSSEReturn {
  const { enabled = true, environmentId, jobId, onLogMessage, onProgressEvent } = options;
  const queryClient = useQueryClient();
  
  // Helper to emit log messages
  const emitLog = useCallback((level: LogMessage['level'], message: string, phase?: string, details?: any) => {
    if (onLogMessage) {
      onLogMessage({
        timestamp: new Date().toISOString(),
        level,
        message,
        phase,
        details,
      });
    }
  }, [onLogMessage]);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);

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
      const sseData = transformKeys(data);
      const envId = sseData.environmentId || environmentId;
      const jId = sseData.jobId || jobId;
      onProgressEvent?.('sync.progress', sseData);
      
      // Emit log message for this progress event
      const logLevel: LogMessage['level'] = sseData.status === 'failed' ? 'error' : 
                                             sseData.status === 'completed' ? 'info' : 'info';
      const logMessage = sseData.message || `${sseData.currentStep}: ${sseData.current}/${sseData.total}`;
      emitLog(logLevel, logMessage, sseData.currentStep, {
        current: sseData.current,
        total: sseData.total,
        percentage: sseData.percentage,
        status: sseData.status,
      });

      // Update job status in cache
      if (jId) {
        queryClient.setQueryData(['background-job', jId], (old: any) => {
          if (!old) return { data: sseData };
          
          // Properly merge progress object
          const updatedJob = {
            ...old.data,
            status: sseData.status || old.data?.status,
            progress: {
              ...(old.data?.progress || {}),
              current: sseData.current,
              total: sseData.total,
              percentage: sseData.percentage,
              message: sseData.message,
              current_step: sseData.currentStep, // Note: transformed from current_step
              currentStep: sseData.currentStep,
            },
          };
          
          return {
            ...old,
            data: updatedJob,
          };
        });
        
        // Invalidate to trigger refetch and get complete data
        queryClient.invalidateQueries({ queryKey: ['background-job', jId] });
      }

      // Update environment jobs list
      if (envId) {
        queryClient.setQueryData(['environment-jobs', envId], (old: any) => {
          if (!old?.data) return old;
          return {
            ...old,
            data: old.data.map((job: any) =>
              job.id === jId ? { 
                ...job, 
                status: sseData.status || job.status,
                progress: {
                  ...(job.progress || {}),
                  current: sseData.current,
                  total: sseData.total,
                  percentage: sseData.percentage,
                  message: sseData.message,
                  current_step: sseData.currentStep,
                  currentStep: sseData.currentStep,
                },
              } : job
            ),
          };
        });
      }
    },
    [queryClient, environmentId, jobId, emitLog, onProgressEvent]
  );

  const handleBackupProgress = useCallback(
    (data: any) => {
      const progress = transformKeys(data);
      const envId = progress.environmentId || environmentId;
      const jId = progress.jobId || jobId;
      onProgressEvent?.('backup.progress', progress);

      // Emit log message for this progress event
      const logLevel: LogMessage['level'] = progress.status === 'failed' ? 'error' :
                                             progress.status === 'completed' ? 'info' : 'info';
      const logMessage = progress.message ||
        (progress.currentWorkflowName
          ? `Backing up: ${progress.currentWorkflowName} (${progress.current}/${progress.total})`
          : `Backup progress: ${progress.current}/${progress.total}`);
      emitLog(logLevel, logMessage, 'backup', {
        current: progress.current,
        total: progress.total,
        currentWorkflowName: progress.currentWorkflowName,
        status: progress.status,
      });

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
    [queryClient, environmentId, jobId, emitLog, onProgressEvent]
  );

  const handleRestoreProgress = useCallback(
    (data: any) => {
      const progress = transformKeys(data);
      const envId = progress.environmentId || environmentId;
      const jId = progress.jobId || jobId;
      onProgressEvent?.('restore.progress', progress);

      // Emit log message for this progress event
      const logLevel: LogMessage['level'] = progress.status === 'failed' ? 'error' :
                                             progress.status === 'completed' ? 'info' : 'info';
      const logMessage = progress.message ||
        (progress.currentWorkflowName
          ? `Restoring: ${progress.currentWorkflowName} (${progress.current}/${progress.total})`
          : `Restore progress: ${progress.current}/${progress.total}`);
      emitLog(logLevel, logMessage, 'restore', {
        current: progress.current,
        total: progress.total,
        currentWorkflowName: progress.currentWorkflowName,
        status: progress.status,
      });

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
    [queryClient, environmentId, jobId, emitLog, onProgressEvent]
  );

  const connect = useCallback(() => {
    if (!enabled) return;

    // Build SSE URL with filters
    // Note: VITE_API_BASE_URL already includes /api/v1
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
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

    const eventSource = new EventSource(url, { withCredentials: true });
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setConnectionError(null);
      reconnectAttemptRef.current = 0;
      // Emit log message on successful connection
      emitLog('info', 'Connected to live updates stream', undefined, { connected: true });
    };

    eventSource.onerror = (_error) => {
      setIsConnected(false);
      setConnectionError('SSE connection error');

      // Attempt reconnection
      if (reconnectAttemptRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = getReconnectDelay();
        emitLog('warn', 'SSE connection lost, attempting to reconnect', 'reconnect', {
          attempt: reconnectAttemptRef.current + 1,
          delayMs: delay,
        });
        reconnectAttemptRef.current += 1;

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      } else {
        setConnectionError('Max reconnection attempts reached');
        emitLog('error', 'Max SSE reconnection attempts reached', 'reconnect', {
          attempts: reconnectAttemptRef.current,
        });
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

    // Handle job status changed events
    eventSource.addEventListener('job.status_changed', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        const sseData = transformKeys(data);
        const jId = sseData.jobId || jobId;

        onProgressEvent?.('job.status_changed', sseData);

        // Emit log message
        const logLevel: LogMessage['level'] = sseData.status === 'failed' ? 'error' :
                                               sseData.status === 'cancelled' ? 'warn' :
                                               sseData.status === 'completed' ? 'info' : 'info';
        const logMessage = sseData.errorMessage || `Job status changed to: ${sseData.status}`;
        emitLog(logLevel, logMessage, 'status_change', {
          jobId: jId,
          status: sseData.status,
          jobType: sseData.jobType,
        });

        // Update job status in cache
        if (jId) {
          queryClient.setQueryData(['background-job', jId], (old: any) => {
            if (!old) return { data: sseData };
            return {
              ...old,
              data: {
                ...old.data,
                status: sseData.status,
                error_message: sseData.errorMessage,
              },
            };
          });

          // Invalidate to trigger refetch
          queryClient.invalidateQueries({ queryKey: ['background-job', jId] });
          queryClient.invalidateQueries({ queryKey: ['all-background-jobs'] });
        }

        // Update environment jobs list
        if (sseData.resourceId) {
          queryClient.setQueryData(['environment-jobs', sseData.resourceId], (old: any) => {
            if (!old?.data) return old;
            return {
              ...old,
              data: old.data.map((job: any) =>
                job.id === jId ? {
                  ...job,
                  status: sseData.status,
                  error_message: sseData.errorMessage,
                } : job
              ),
            };
          });
        }
      } catch (error) {
        console.error('Failed to parse job.status_changed event:', error);
      }
    });
  }, [enabled, environmentId, jobId, handleSyncProgress, handleBackupProgress, handleRestoreProgress, getReconnectDelay, emitLog, onProgressEvent, queryClient]);

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

