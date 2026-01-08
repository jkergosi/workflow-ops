import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useDeploymentsSSE } from '../use-deployments-sse';
import { useBackgroundJobsSSE } from '../use-background-jobs-sse';

class ControlledEventSource {
  static instances: ControlledEventSource[] = [];
  url: string;
  withCredentials: boolean;
  readyState = 0;
  onopen: ((ev: Event) => any) | null = null;
  onmessage: ((ev: MessageEvent) => any) | null = null;
  onerror: ((ev: Event) => any) | null = null;
  listeners: Record<string, Array<(ev: MessageEvent) => void>> = {};

  constructor(url: string, options?: EventSourceInit) {
    this.url = url;
    this.withCredentials = options?.withCredentials ?? false;
    ControlledEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (ev: MessageEvent) => void) {
    if (!this.listeners[type]) {
      this.listeners[type] = [];
    }
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: (ev: MessageEvent) => void) {
    this.listeners[type] = (this.listeners[type] || []).filter((cb) => cb !== listener);
  }

  emit(type: string, payload: any, lastEventId?: string) {
    const event = {
      data: typeof payload === 'string' ? payload : JSON.stringify(payload),
      lastEventId,
    } as MessageEvent;

    (this.listeners[type] || []).forEach((listener) => listener(event));

    if (type === 'message' && this.onmessage) {
      this.onmessage(event);
    }
  }

  triggerOpen() {
    this.onopen?.(new Event('open'));
  }

  triggerError() {
    this.onerror?.(new Event('error'));
  }

  close() {
    this.readyState = 2;
  }
}

const createWrapper = (client?: QueryClient) => {
  const queryClient =
    client ||
    new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0, staleTime: 0 },
        mutations: { retry: false },
      },
    });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const OriginalEventSource = globalThis.EventSource;

beforeEach(() => {
  vi.useFakeTimers();
  ControlledEventSource.instances = [];
  // Ensure auth token is present for SSE URLs
  if ((window.localStorage.getItem as any).mockReturnValue) {
    (window.localStorage.getItem as any).mockReturnValue('test-token');
  }
  (globalThis as any).EventSource = ControlledEventSource as unknown as typeof EventSource;
  (window as any).EventSource = ControlledEventSource as unknown as typeof EventSource;
});

afterEach(() => {
  ControlledEventSource.instances = [];
  (globalThis as any).EventSource = OriginalEventSource as unknown as typeof EventSource;
  (window as any).EventSource = OriginalEventSource as unknown as typeof EventSource;
  vi.useRealTimers();
});

describe('SSE reconnection', () => {
  it('reconnects deployments stream and forwards lastEventId on reconnect', async () => {
    const wrapper = createWrapper();
    renderHook(() => useDeploymentsSSE({ enabled: true }), { wrapper });

    expect(ControlledEventSource.instances.length).toBe(1);
    const first = ControlledEventSource.instances[0];

    act(() => {
      first.triggerOpen();
      first.emit('snapshot', { deployments: [] }, 'evt-1');
      first.triggerError();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(ControlledEventSource.instances.length).toBe(2);
    expect(ControlledEventSource.instances[1].url).toContain('lastEventId=evt-1');
  });

  it('reconnects background jobs stream and delivers parsed progress events', async () => {
    const onProgress = vi.fn();
    const wrapper = createWrapper();
    renderHook(() => useBackgroundJobsSSE({ enabled: true, onProgressEvent: onProgress }), { wrapper });

    expect(ControlledEventSource.instances.length).toBe(1);
    const first = ControlledEventSource.instances[0];

    act(() => {
      first.triggerOpen();
      first.triggerError();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(ControlledEventSource.instances.length).toBe(2);
    const second = ControlledEventSource.instances[1];

    act(() => {
      second.emit('sync.progress', {
        environment_id: 'env-1',
        job_id: 'job-123',
        status: 'running',
        current_step: 'download',
        current: 1,
        total: 2,
      });
    });

    expect(onProgress).toHaveBeenCalledWith(
      'sync.progress',
      expect.objectContaining({
        environmentId: 'env-1',
        jobId: 'job-123',
        status: 'running',
      })
    );
  });
});

