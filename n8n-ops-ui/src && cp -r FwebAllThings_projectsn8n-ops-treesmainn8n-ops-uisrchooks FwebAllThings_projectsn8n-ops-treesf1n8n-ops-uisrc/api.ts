// API wrapper that allows switching between mock and real API
import { mockApi } from './mock-api';
import { apiClient } from './api-client';

// Check environment variable to determine which API to use
const useMockApi = import.meta.env.VITE_USE_MOCK_API === 'true';

// Export the appropriate API
export const api = useMockApi ? mockApi : apiClient;

// Also export both for direct access if needed
export { mockApi, apiClient };
