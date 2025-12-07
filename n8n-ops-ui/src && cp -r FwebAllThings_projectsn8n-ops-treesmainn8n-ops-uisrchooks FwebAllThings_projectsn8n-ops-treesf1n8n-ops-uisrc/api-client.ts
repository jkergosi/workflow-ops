import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type {
  Environment,
  EnvironmentType,
  Workflow,
  Snapshot,
  Deployment,
  TeamMember,
  SubscriptionPlan,
} from '@/types';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_V1_PREFIX = '/api/v1';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: `${API_BASE_URL}${API_V1_PREFIX}`,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for adding auth token
    this.client.interceptors.request.use(
      (config) => {
        // Add auth token if available
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Handle unauthorized - redirect to login
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // Environments
  async getEnvironments(): Promise<{ data: Environment[] }> {
    const response = await this.client.get<any[]>('/environments');
    // Transform snake_case to camelCase
    const data = response.data.map((env: any) => ({
      ...env,
      baseUrl: env.base_url,
      apiKey: env.api_key,
      isActive: env.is_active,
      lastConnected: env.last_connected,
      workflowCount: env.workflow_count || 0,
      tenantId: env.tenant_id,
      createdAt: env.created_at,
      updatedAt: env.updated_at,
      gitRepoUrl: env.git_repo_url,
      gitBranch: env.git_branch,
      gitPat: env.git_pat,
    }));
    return { data };
  }

  async getEnvironment(id: string): Promise<{ data: Environment }> {
    const response = await this.client.get<Environment>(`/environments/${id}`);
    return { data: response.data };
  }

  async createEnvironment(environment: {
    name: string;
    type: EnvironmentType;
    base_url: string;
    api_key: string;
  }): Promise<{ data: Environment }> {
    const response = await this.client.post<Environment>('/environments', environment);
    return { data: response.data };
  }

  async updateEnvironment(
    id: string,
    environment: {
      name?: string;
      base_url?: string;
      api_key?: string;
      is_active?: boolean;
    }
  ): Promise<{ data: Environment }> {
    const response = await this.client.patch<Environment>(`/environments/${id}`, environment);
    return { data: response.data };
  }

  async deleteEnvironment(id: string): Promise<void> {
    await this.client.delete(`/environments/${id}`);
  }

  async testEnvironmentConnection(baseUrl: string, apiKey: string): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.post<{ success: boolean; message: string }>(
      '/environments/test-connection',
      { base_url: baseUrl, api_key: apiKey }
    );
    return { data: response.data };
  }

  async testGitConnection(config: { gitRepoUrl: string; gitBranch?: string; gitPat?: string }): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.post<{ success: boolean; message: string }>(
      '/environments/test-git-connection',
      {
        git_repo_url: config.gitRepoUrl,
        git_branch: config.gitBranch || 'main',
        git_pat: config.gitPat,
      }
    );
    return { data: response.data };
  }

  async syncEnvironment(environmentId: string): Promise<{
    data: {
      success: boolean;
      message: string;
      results: {
        workflows: { synced: number; errors: string[] };
        executions: { synced: number; errors: string[] };
        credentials: { synced: number; errors: string[] };
        users: { synced: number; errors: string[] };
        tags: { synced: number; errors: string[] };
      };
    };
  }> {
    const response = await this.client.post(`/environments/${environmentId}/sync`);
    return { data: response.data };
  }

  async syncUsersOnly(environmentId: string): Promise<{
    data: {
      success: boolean;
      message: string;
      synced: number;
    };
  }> {
    const response = await this.client.post(`/environments/${environmentId}/sync-users`);
    return { data: response.data };
  }

  async syncExecutionsOnly(environmentId: string): Promise<{
    data: {
      success: boolean;
      message: string;
      synced: number;
    };
  }> {
    const response = await this.client.post(`/environments/${environmentId}/sync-executions`);
    return { data: response.data };
  }

  async syncTagsOnly(environmentId: string): Promise<{
    data: {
      success: boolean;
      message: string;
      synced: number;
    };
  }> {
    const response = await this.client.post(`/environments/${environmentId}/sync-tags`);
    return { data: response.data };
  }

  // Workflows
  async getWorkflows(environment: EnvironmentType, forceRefresh: boolean = false): Promise<{ data: Workflow[] }> {
    const response = await this.client.get<Workflow[]>('/workflows', {
      params: { environment, force_refresh: forceRefresh },
    });
    return { data: response.data };
  }

  async getWorkflow(id: string, environment: EnvironmentType): Promise<{ data: Workflow }> {
    const response = await this.client.get<Workflow>(`/workflows/${id}`, {
      params: { environment },
    });
    return { data: response.data };
  }

  async uploadWorkflows(
    files: File[],
    environment: EnvironmentType,
    syncToGithub: boolean = true
  ): Promise<{
    data: {
      success: boolean;
      uploaded: number;
      failed: number;
      workflows: Workflow[];
      errors: string[];
    };
  }> {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await this.client.post(
      '/workflows/upload',
      formData,
      {
        params: { environment, sync_to_github: syncToGithub },
        headers: { 'Content-Type': 'multipart/form-data' },
      }
    );
    return { data: response.data };
  }

  async activateWorkflow(id: string, environment: EnvironmentType): Promise<{ data: Workflow }> {
    const response = await this.client.post<Workflow>(`/workflows/${id}/activate`, null, {
      params: { environment },
    });
    return { data: response.data };
  }

  async deactivateWorkflow(id: string, environment: EnvironmentType): Promise<{ data: Workflow }> {
    const response = await this.client.post<Workflow>(`/workflows/${id}/deactivate`, null, {
      params: { environment },
    });
    return { data: response.data };
  }

  async updateWorkflow(
    id: string,
    environment: EnvironmentType,
    workflowData: any
  ): Promise<{ data: Workflow }> {
    const response = await this.client.put<Workflow>(`/workflows/${id}`, workflowData, {
      params: { environment },
    });
    return { data: response.data };
  }

  async updateWorkflowTags(
    id: string,
    environment: EnvironmentType,
    tagNames: string[]
  ): Promise<{ data: any }> {
    const response = await this.client.put(`/workflows/${id}/tags`, tagNames, {
      params: { environment },
    });
    return { data: response.data };
  }

  async deleteWorkflow(id: string, environment: EnvironmentType): Promise<void> {
    await this.client.delete(`/workflows/${id}`, {
      params: { environment },
    });
  }

  async syncWorkflowsFromGithub(environment: EnvironmentType): Promise<{
    data: {
      success: boolean;
      synced: number;
      failed: number;
      workflows: Workflow[];
      errors: string[];
    };
  }> {
    const response = await this.client.post('/workflows/sync-from-github', null, {
      params: { environment },
    });
    return { data: response.data };
  }

  async syncWorkflowsToGithub(environment: EnvironmentType): Promise<{
    data: {
      success: boolean;
      synced: number;
      failed: number;
      workflows: Array<{ id: string; name: string }>;
      errors: string[];
    };
  }> {
    const response = await this.client.post('/workflows/sync-to-github', null, {
      params: { environment },
    });
    return { data: response.data };
  }

  // Executions
  async getExecutions(environmentId?: string, workflowId?: string): Promise<{ data: any[] }> {
    const params: any = {};
    if (environmentId) params.environment_id = environmentId;
    if (workflowId) params.workflow_id = workflowId;

    const response = await this.client.get('/executions', { params });
    return { data: response.data };
  }

  async getExecution(id: string): Promise<{ data: any }> {
    const response = await this.client.get(`/executions/${id}`);
    return { data: response.data };
  }

  // Tags
  async getTags(environmentId?: string): Promise<{ data: any[] }> {
    const params: any = {};
    if (environmentId) params.environment_id = environmentId;

    const response = await this.client.get('/tags', { params });
    return { data: response.data };
  }

  async getTag(id: string): Promise<{ data: any }> {
    const response = await this.client.get(`/tags/${id}`);
    return { data: response.data };
  }

  // Snapshots (placeholder - to be implemented)
  async getSnapshots(): Promise<{ data: Snapshot[] }> {
    // TODO: Implement when backend endpoint is ready
    return { data: [] };
  }

  // Deployments (placeholder - to be implemented)
  async getDeployments(): Promise<{ data: Deployment[] }> {
    // TODO: Implement when backend endpoint is ready
    return { data: [] };
  }

  // Teams
  async getTeamMembers(): Promise<{ data: TeamMember[] }> {
    const response = await this.client.get<TeamMember[]>('/teams');
    return { data: response.data };
  }

  async getTeamMember(id: string): Promise<{ data: TeamMember }> {
    const response = await this.client.get<TeamMember>(`/teams/${id}`);
    return { data: response.data };
  }

  async createTeamMember(member: { email: string; name: string; role: string }): Promise<{ data: TeamMember }> {
    const response = await this.client.post<TeamMember>('/teams', member);
    return { data: response.data };
  }

  async updateTeamMember(id: string, updates: Partial<TeamMember>): Promise<{ data: TeamMember }> {
    const response = await this.client.patch<TeamMember>(`/teams/${id}`, updates);
    return { data: response.data };
  }

  async deleteTeamMember(id: string): Promise<void> {
    await this.client.delete(`/teams/${id}`);
  }

  async getTeamLimits(): Promise<{ data: { current_members: number; max_members: number | null; can_add_more: boolean } }> {
    const response = await this.client.get<{ current_members: number; max_members: number | null; can_add_more: boolean }>('/teams/limits');
    return { data: response.data };
  }

  async resendInvitation(id: string): Promise<{ data: { message: string } }> {
    const response = await this.client.post<{ message: string }>(`/teams/${id}/resend-invite`);
    return { data: response.data };
  }

  // Billing
  async getSubscriptionPlans(): Promise<{ data: any[] }> {
    const response = await this.client.get<any[]>('/billing/plans');
    return { data: response.data };
  }

  async getSubscription(): Promise<{ data: SubscriptionPlan }> {
    const response = await this.client.get<SubscriptionPlan>('/billing/subscription');
    return { data: response.data };
  }

  async createCheckoutSession(data: { price_id: string; billing_cycle: string; success_url: string; cancel_url: string }): Promise<{ data: { session_id: string; url: string } }> {
    const response = await this.client.post<{ session_id: string; url: string }>('/billing/checkout', data);
    return { data: response.data };
  }

  async createPortalSession(return_url: string): Promise<{ data: { url: string } }> {
    const response = await this.client.post<{ url: string }>('/billing/portal', null, {
      params: { return_url }
    });
    return { data: response.data };
  }

  async cancelSubscription(at_period_end: boolean = true): Promise<{ data: { message: string } }> {
    const response = await this.client.post<{ message: string }>('/billing/cancel', null, {
      params: { at_period_end }
    });
    return { data: response.data };
  }

  async reactivateSubscription(): Promise<{ data: { message: string } }> {
    const response = await this.client.post<{ message: string }>('/billing/reactivate');
    return { data: response.data };
  }

  async getInvoices(limit: number = 10): Promise<{ data: any[] }> {
    const response = await this.client.get<any[]>('/billing/invoices', {
      params: { limit }
    });
    return { data: response.data };
  }

  async getPaymentHistory(limit: number = 10): Promise<{ data: any[] }> {
    const response = await this.client.get<any[]>('/billing/payment-history', {
      params: { limit }
    });
    return { data: response.data };
  }

  // Dashboard stats (placeholder - to be implemented)
  async getDashboardStats(): Promise<{
    data: {
      totalWorkflows: number;
      activeWorkflows: number;
      environments: number;
      deployments: number;
    };
  }> {
    // TODO: Implement when backend endpoint is ready
    return {
      data: {
        totalWorkflows: 0,
        activeWorkflows: 0,
        environments: 0,
        deployments: 0,
      },
    };
  }

  // N8N Users
  async getN8NUsers(environmentId?: string): Promise<{ data: any[] }> {
    const params = environmentId ? { environment_id: environmentId } : {};
    const response = await this.client.get<any[]>('/n8n-users/', { params });
    return { data: response.data };
  }

  async getN8NUser(id: string): Promise<{ data: any }> {
    const response = await this.client.get<any>(`/n8n-users/${id}`);
    return { data: response.data };
  }
}

export const apiClient = new ApiClient();
