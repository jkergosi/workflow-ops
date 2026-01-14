/**
 * SSE Hook for real-time deployment updates.
 *
 * Connects to the backend SSE endpoint and updates TanStack Query cache
 * in response to server-sent events.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { Deployment } from '@/types';

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

interface UseDeploymentsSSEOptions {
  enabled?: boolean;
  deploymentId?: string; // For detail page - subscribe to specific deployment
}

interface UseDeploymentsSSEReturn {
  isConnected: boolean;
  connectionError: string | null;
}

export function useDeploymentsSSE(
  options: UseDeploymentsSSEOptions = {}
): UseDeploymentsSSEReturn {
  const isTest = import.meta.env.MODE === 'test';
  const { enabled = true, deploymentId } = options;
  const effectiveEnabled = enabled && !isTest;
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

  const handleSnapshot = useCallback(
    (data: any) => {
      const transformed = transformKeys(data);

      if (deploymentId) {
        // Detail page snapshot - update single deployment
        queryClient.setQueryData(['deployment', deploymentId], { data: transformed.deployment });
      } else {
        // List page snapshot - update deployments list
        queryClient.setQueryData(['deployments'], {
          data: {
            deployments: transformed.deployments || [],
            total: transformed.total || 0,
            page: transformed.page || 1,
            pageSize: transformed.pageSize || 50,
            thisWeekSuccessCount: transformed.thisWeekSuccessCount || 0,
            runningCount: transformed.runningCount || 0,
            pendingApprovalsCount: 0,
          },
        });
      }
    },
    [queryClient, deploymentId]
  );

  const handleDeploymentUpsert = useCallback(
    (data: any) => {
      const deployment = transformKeys(data);

      // Update list view
      queryClient.setQueryData(['deployments'], (old: any) => {
        if (!old?.data?.deployments) return old;

        const existingIndex = old.data.deployments.findIndex(
          (d: Deployment) => d.id === deployment.id
        );
        const newDeployments = [...old.data.deployments];

        if (existingIndex >= 0) {
          // Update existing deployment
          newDeployments[existingIndex] = {
            ...newDeployments[existingIndex],
            ...deployment,
          };
        } else {
          // Add new deployment at the beginning
          newDeployments.unshift(deployment);
        }

        return {
          ...old,
          data: {
            ...old.data,
            deployments: newDeployments,
          },
        };
      });

      // Update detail view if viewing this deployment
      if (deployment.id) {
        queryClient.setQueryData(['deployment', deployment.id], (old: any) => {
          if (!old?.data) return old;
          return {
            ...old,
            data: {
              ...old.data,
              ...deployment,
            },
          };
        });
      }
    },
    [queryClient]
  );

  const handleDeploymentProgress = useCallback(
    (data: any) => {
      const progress = transformKeys(data);
      const depId = progress.deploymentId;

      // Update list view
      queryClient.setQueryData(['deployments'], (old: any) => {
        if (!old?.data?.deployments) return old;

        return {
          ...old,
          data: {
            ...old.data,
            deployments: old.data.deployments.map((d: Deployment) =>
              d.id === depId
                ? {
                    ...d,
                    progressCurrent: progress.progressCurrent,
                    progressTotal: progress.progressTotal,
                    currentWorkflowName: progress.currentWorkflowName,
                  }
                : d
            ),
          },
        };
      });

      // Update detail view if viewing this deployment
      queryClient.setQueryData(['deployment', depId], (old: any) => {
        if (!old?.data) return old;
        return {
          ...old,
          data: {
            ...old.data,
            progressCurrent: progress.progressCurrent,
            progressTotal: progress.progressTotal,
            currentWorkflowName: progress.currentWorkflowName,
          },
        };
      });
    },
    [queryClient]
  );

  const handleCountsUpdate = useCallback(
    (data: any) => {
      const counts = transformKeys(data);

      queryClient.setQueryData(['deployments'], (old: any) => {
        if (!old?.data) return old;

        return {
          ...old,
          data: {
            ...old.data,
            thisWeekSuccessCount: counts.thisWeekSuccessCount,
            runningCount: counts.runningCount,
          },
        };
      });
    },
    [queryClient]
  );

  const connect = useCallback(() => {
    if (!effectiveEnabled) return;

    // Clear any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1';
    const endpoint = deploymentId
      ? `${baseUrl}/sse/deployments/${deploymentId}`
      : `${baseUrl}/sse/deployments`;

    // Include last event ID for reconnection resume
    const url = lastEventIdRef.current
      ? `${endpoint}?lastEventId=${lastEventIdRef.current}`
      : endpoint;

    if (!isTest) console.log('[SSE] Connecting to:', url);
    const eventSource = new EventSource(url, { withCredentials: true });
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      if (!isTest) console.log('[SSE] Connected');
      setIsConnected(true);
      setConnectionError(null);
      reconnectAttemptRef.current = 0;
    };

    eventSource.onerror = (event) => {
      if (!isTest) console.error('[SSE] Connection error:', event);
      setIsConnected(false);
      eventSource.close();

      // Attempt reconnection with exponential backoff
      if (reconnectAttemptRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = getReconnectDelay();
        if (!isTest) {
          console.log(
            `[SSE] Reconnecting in ${delay}ms (attempt ${reconnectAttemptRef.current + 1}/${MAX_RECONNECT_ATTEMPTS})`
          );
        }
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectAttemptRef.current++;
          connect();
        }, delay);
      } else {
        setConnectionError('Failed to connect to real-time updates. Please refresh the page.');
        if (!isTest) console.error('[SSE] Max reconnection attempts reached');
      }
    };

    // Handle snapshot event
    eventSource.addEventListener('snapshot', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        lastEventIdRef.current = event.lastEventId;
        handleSnapshot(data);
      } catch (e) {
        console.error('[SSE] Error parsing snapshot:', e);
      }
    });

    // Handle deployment.upsert event
    eventSource.addEventListener('deployment.upsert', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        lastEventIdRef.current = event.lastEventId;
        handleDeploymentUpsert(data);
      } catch (e) {
        console.error('[SSE] Error parsing deployment.upsert:', e);
      }
    });

    // Handle deployment.progress event
    eventSource.addEventListener('deployment.progress', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        lastEventIdRef.current = event.lastEventId;
        handleDeploymentProgress(data);
      } catch (e) {
        console.error('[SSE] Error parsing deployment.progress:', e);
      }
    });

    // Handle counts.update event
    eventSource.addEventListener('counts.update', (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        lastEventIdRef.current = event.lastEventId;
        handleCountsUpdate(data);
      } catch (e) {
        console.error('[SSE] Error parsing counts.update:', e);
      }
    });
  }, [
    effectiveEnabled,
    deploymentId,
    getReconnectDelay,
    handleSnapshot,
    handleDeploymentUpsert,
    handleDeploymentProgress,
    handleCountsUpdate,
    isTest,
  ]);

  useEffect(() => {
    if (!effectiveEnabled) {
      // Clean up if disabled
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      setIsConnected(false);
      return;
    }

    connect();

    return () => {
      if (eventSourceRef.current) {
        if (!isTest) console.log('[SSE] Disconnecting');
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [effectiveEnabled, connect, isTest]);

  return { isConnected, connectionError };
}
