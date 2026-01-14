import type { ReactElement, ReactNode } from 'react';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '@/lib/auth';
import { FeaturesProvider } from '@/lib/features';
import { Toaster } from 'sonner';
import { mockUsers, mockTenant, mockEntitlements, mockEnvironments, mockWorkflows, mockPipelines } from './mocks/handlers';

// Re-export everything from testing-library
export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';

// Create a new QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

interface WrapperOptions {
  initialRoute?: string;
  useMemoryRouter?: boolean;
  queryClient?: QueryClient;
}

interface AllProvidersProps {
  children: ReactNode;
  options?: WrapperOptions;
}

function AllProviders({ children, options = {} }: AllProvidersProps) {
  const { initialRoute = '/', useMemoryRouter = true, queryClient } = options;
  const client = queryClient || createTestQueryClient();

  const Router = useMemoryRouter ? MemoryRouter : BrowserRouter;
  const routerProps = useMemoryRouter ? { initialEntries: [initialRoute] } : {};

  return (
    <QueryClientProvider client={client}>
      <Router {...routerProps}>
        <AuthProvider>
          <FeaturesProvider>{children}</FeaturesProvider>
        </AuthProvider>
      </Router>
      <Toaster />
    </QueryClientProvider>
  );
}

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  initialRoute?: string;
  useMemoryRouter?: boolean;
  queryClient?: QueryClient;
}

/**
 * Custom render function that wraps components with all necessary providers
 */
function customRender(
  ui: ReactElement,
  options: CustomRenderOptions = {}
): RenderResult & { queryClient: QueryClient } {
  const { initialRoute, useMemoryRouter, queryClient: providedClient, ...renderOptions } = options;
  const queryClient = providedClient || createTestQueryClient();

  const result = render(ui, {
    wrapper: ({ children }) => (
      <AllProviders options={{ initialRoute, useMemoryRouter, queryClient }}>
        {children}
      </AllProviders>
    ),
    ...renderOptions,
  });

  return {
    ...result,
    queryClient,
  };
}

/**
 * Render without providers - for testing pure components
 */
function renderWithoutProviders(ui: ReactElement, options?: RenderOptions): RenderResult {
  return render(ui, options);
}

/**
 * Render with only QueryClient - for testing hooks
 */
function renderWithQuery(
  ui: ReactElement,
  options: CustomRenderOptions = {}
): RenderResult & { queryClient: QueryClient } {
  const queryClient = options.queryClient || createTestQueryClient();

  const result = render(ui, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
    ...options,
  });

  return {
    ...result,
    queryClient,
  };
}

// Override default render with custom render
export { customRender as render, renderWithoutProviders, renderWithQuery };

// Default fixtures for tests
export const fixtures = {
  users: mockUsers,
  tenant: mockTenant,
  entitlements: mockEntitlements,
  environments: mockEnvironments,
  workflows: mockWorkflows,
  pipelines: mockPipelines,

  // Common user scenarios
  adminUser: mockUsers[0],
  developerUser: mockUsers[1],

  // Default auth state
  authenticatedState: {
    isAuthenticated: true,
    user: mockUsers[0],
    tenant: mockTenant,
    entitlements: mockEntitlements,
  },

  unauthenticatedState: {
    isAuthenticated: false,
    user: null,
    tenant: null,
    entitlements: null,
  },
};

/**
 * Helper to wait for async operations
 */
export function waitForAsync(ms = 0): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Helper to create mock functions with typed signatures
 */
export function createMockFn<T extends (...args: any[]) => any>(): ReturnType<typeof vi.fn<T>> {
  return vi.fn<T>();
}

// Import vi from vitest for global use
import { vi } from 'vitest';
export { vi };
