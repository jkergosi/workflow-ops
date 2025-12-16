// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type {
  Environment,
  EnvironmentType,
  Workflow,
  Execution,
  Snapshot,
  Deployment,
  DeploymentDetail,
  Pipeline,
  PipelineStage,
  PromotionInitiateRequest,
  PromotionInitiateResponse,
  PromotionExecutionResult,
  PromotionApprovalRequest,
  PromotionApprovalResponse,
  PromotionSnapshotRequest,
  PromotionSnapshotResponse,
  PromotionCheckDriftRequest,
  PromotionCheckDriftResponse,
  PromotionResponse,
  TeamMember,
  TeamLimits,
  Credential,
  N8NUser,
  Tag,
  Tenant,
  TenantStats,
  TenantNote,
  TenantUsage,
  AuditLog,
  BillingMetrics,
  PlanDistributionItem,
  RecentCharge,
  FailedPayment,
  DunningTenant,
  TenantSubscription,
  TenantInvoice,
  UserResponse,
  Subscription,
  SubscriptionPlan,
  PaymentHistory,
  CheckoutSession,
  PortalSession,
  TimeRange,
  ObservabilityOverview,
  WorkflowPerformance,
  EnvironmentHealthData,
  HealthCheckResponse,
  NotificationChannel,
  NotificationRule,
  AlertEvent,
  EventCatalogItem,
  Entitlements,
  AdminFeature,
  AdminPlan,
  FeatureMatrix,
  TenantFeatureOverride,
  FeatureConfigAudit,
  FeatureAccessLog,
} from '@/types';

// Helper function to determine if a string is a UUID
function isUUID(str: string | undefined): boolean {
  if (!str) return false;
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str);
}

// Helper function to build environment params (prefers environment_id if UUID, otherwise uses environment type)
function buildEnvironmentParams(environment: EnvironmentType): { environment_id?: string; environment?: string } {
  if (!environment) return {};
  if (isUUID(environment)) {
    return { environment_id: environment };
  }
  return { environment };
}

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4000/api/v1';
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor for auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Add response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // TEMPORARY: In dev mode, don't redirect on 401 for dev endpoints
          const url = error.config?.url || '';
          if (url.includes('/auth/dev/')) {
            // Don't redirect for dev endpoints - they don't require auth
            return Promise.reject(error);
          }
          // Handle unauthorized - redirect to login (only for non-dev endpoints)
          localStorage.removeItem('auth_token');
          // Only redirect if not already on login page to prevent loops
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
        }
        return Promise.reject(error);
      }
    );
  }

  // Auth endpoints
  async getCurrentUser(): Promise<{ data: UserResponse }> {
    const response = await this.client.get<UserResponse>('/auth/me');
    return { data: response.data };
  }

  async updateCurrentUser(updates: { name?: string; email?: string }): Promise<{ data: UserResponse }> {
    const response = await this.client.patch<UserResponse>('/auth/me', updates);
    return { data: response.data };
  }

  // Dev auth endpoints (bypass Auth0)
  async getDevUsers(): Promise<{ data: { users: Array<{ id: string; email: string; name: string; tenant_id: string }> } }> {
    const response = await this.client.get('/auth/dev/users');
    return { data: response.data };
  }

  async devLoginAs(userId: string): Promise<{ data: { user: any; tenant: any } }> {
    const response = await this.client.post(`/auth/dev/login-as/${userId}`);
    return { data: response.data };
  }

  async devCreateUser(organizationName?: string): Promise<{ data: { user: any; tenant: any } }> {
    const response = await this.client.post('/auth/dev/create-user', null, {
      params: organizationName ? { organization_name: organizationName } : {},
    });
    return { data: response.data };
  }

  setAuthToken(token: string | null): void {
    if (token) {
      localStorage.setItem('auth_token', token);
    } else {
      localStorage.removeItem('auth_token');
    }
  }

  // Get auth status with entitlements
  async getAuthStatus(): Promise<{
    data: {
      authenticated: boolean;
      onboarding_required: boolean;
      has_environment: boolean;
      user: { id: string; email: string; name: string; role: string } | null;
      tenant: { id: string; name: string; subscription_plan: string } | null;
      entitlements: Entitlements | null;
    };
  }> {
    const response = await this.client.get('/auth/status');
    return { data: response.data };
  }

  // Onboarding endpoints
  async checkEmail(email: string): Promise<{
    data: {
      exists: boolean;
      has_auth0_account: boolean;
      has_n8n_ops_account: boolean;
      message: string | null;
    };
  }> {
    const response = await this.client.post('/auth/check-email', { email });
    return { data: response.data };
  }

  async onboardingOrganization(data: {
    organization_name: string;
    industry?: string;
    company_size?: string;
  }): Promise<{ data: { success: boolean; tenant_id: string; tenant_name: string } }> {
    const response = await this.client.post('/auth/onboarding/organization', data);
    return { data: response.data };
  }

  async onboardingSelectPlan(data: {
    plan_name: string;
    billing_cycle?: string;
  }): Promise<{ data: { success: boolean; plan: string; billing_cycle: string } }> {
    const response = await this.client.post('/auth/onboarding/select-plan', data);
    return { data: response.data };
  }

  async onboardingPayment(data: {
    plan_name: string;
    billing_cycle: string;
    success_url: string;
    cancel_url: string;
  }): Promise<{
    data: {
      success: boolean;
      requires_payment: boolean;
      checkout_url?: string;
      session_id?: string;
      message?: string;
    };
  }> {
    const response = await this.client.post('/auth/onboarding/payment', data);
    return { data: response.data };
  }

  async onboardingInviteTeam(data: {
    invites: Array<{ email: string; role: string }>;
  }): Promise<{
    data: {
      success: boolean;
      invited_count: number;
      errors?: string[];
    };
  }> {
    const response = await this.client.post('/auth/onboarding/invite-team', data);
    return { data: response.data };
  }

  async onboardingComplete(): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.post('/auth/onboarding/complete', {});
    return { data: response.data };
  }

  // Legacy onboarding endpoint (for backward compatibility)
  async completeOnboarding(organizationName?: string): Promise<{ data: UserResponse }> {
    const response = await this.client.post('/auth/onboarding', {
      organization_name: organizationName,
    });
    return { data: response.data.user };
  }

  // Environment endpoints
  async getEnvironments(): Promise<{ data: Environment[] }> {
    const response = await this.client.get<any[]>('/environments');
    // Transform snake_case to camelCase
    const data = response.data.map((env: any) => ({
      ...env,
      id: env.id,
      tenantId: env.tenant_id,
      provider: env.provider || 'n8n',  // Default to n8n for backward compatibility
      name: env.n8n_name,
      type: env.n8n_type,
      baseUrl: env.n8n_base_url,
      apiKey: env.n8n_api_key,
      n8nEncryptionKey: env.n8n_encryption_key,
      isActive: env.is_active,
      allowUpload: env.allow_upload ?? false,
      lastConnected: env.last_connected,
      lastBackup: env.last_backup,
      workflowCount: env.workflow_count || 0,
      gitRepoUrl: env.git_repo_url,
      gitBranch: env.git_branch,
      gitPat: env.git_pat,
      createdAt: env.created_at,
      updatedAt: env.updated_at,
    }));
    return { data };
  }

  async getEnvironment(id: string): Promise<{ data: Environment }> {
    const response = await this.client.get<Environment>(`/environments/${id}`);
    return { data: response.data };
  }

  async createEnvironment(environment: {
    name: string;
    type?: string;
    base_url: string;
    api_key: string;
    n8n_encryption_key?: string;
    allow_upload?: boolean;
    git_repo_url?: string;
    git_branch?: string;
    git_pat?: string;
  }): Promise<{ data: Environment }> {
    // Transform to backend field names
    const payload = {
      n8n_name: environment.name,
      n8n_type: environment.type,
      n8n_base_url: environment.base_url,
      n8n_api_key: environment.api_key,
      n8n_encryption_key: environment.n8n_encryption_key,
      allow_upload: environment.allow_upload ?? false,
      git_repo_url: environment.git_repo_url,
      git_branch: environment.git_branch,
      git_pat: environment.git_pat,
    };
    const response = await this.client.post<Environment>('/environments', payload);
    return { data: response.data };
  }

  async updateEnvironment(
    id: string,
    environment: {
      name?: string;
      base_url?: string;
      api_key?: string;
      n8n_encryption_key?: string;
      is_active?: boolean;
      allow_upload?: boolean;
      git_repo_url?: string;
      git_branch?: string;
      git_pat?: string;
    }
  ): Promise<{ data: Environment }> {
    // Transform to backend field names
    const payload: Record<string, any> = {};
    if (environment.name !== undefined) payload.n8n_name = environment.name;
    if (environment.base_url !== undefined) payload.n8n_base_url = environment.base_url;
    if (environment.api_key !== undefined) payload.n8n_api_key = environment.api_key;
    if (environment.n8n_encryption_key !== undefined) payload.n8n_encryption_key = environment.n8n_encryption_key;
    if (environment.is_active !== undefined) payload.is_active = environment.is_active;
    if (environment.allow_upload !== undefined) payload.allow_upload = environment.allow_upload;
    if (environment.git_repo_url !== undefined) payload.git_repo_url = environment.git_repo_url;
    if (environment.git_branch !== undefined) payload.git_branch = environment.git_branch;
    if (environment.git_pat !== undefined) payload.git_pat = environment.git_pat;

    const response = await this.client.patch<Environment>(`/environments/${id}`, payload);
    return { data: response.data };
  }

  async deleteEnvironment(id: string): Promise<void> {
    await this.client.delete(`/environments/${id}`);
  }

  async testEnvironmentConnection(baseUrl: string, apiKey: string): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.post<{ success: boolean; message: string }>(
      '/environments/test-connection',
      { n8n_base_url: baseUrl, n8n_api_key: apiKey }
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

  // Workflow endpoints
  async getWorkflows(environment: EnvironmentType, forceRefresh: boolean = false): Promise<{ data: Workflow[] }> {
    const params = { ...buildEnvironmentParams(environment), force_refresh: forceRefresh };
    const response = await this.client.get<any[]>('/workflows', { params });
    // Add provider field with default for backward compatibility
    const data = response.data.map((wf: any) => ({
      ...wf,
      provider: wf.provider || 'n8n',
    }));
    return { data };
  }

  async getWorkflow(id: string, environment: EnvironmentType): Promise<{ data: Workflow }> {
    const params = buildEnvironmentParams(environment);
    const response = await this.client.get<Workflow>(`/workflows/${id}`, { params });
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

    const params = { ...buildEnvironmentParams(environment), sync_to_github: syncToGithub };
    const response = await this.client.post(
      '/workflows/upload',
      formData,
      {
        params,
        headers: { 'Content-Type': 'multipart/form-data' },
      }
    );
    return { data: response.data };
  }

  async activateWorkflow(id: string, environment: EnvironmentType): Promise<{ data: Workflow }> {
    const params = buildEnvironmentParams(environment);
    const response = await this.client.post<Workflow>(`/workflows/${id}/activate`, null, { params });
    return { data: response.data };
  }

  async deactivateWorkflow(id: string, environment: EnvironmentType): Promise<{ data: Workflow }> {
    const params = buildEnvironmentParams(environment);
    const response = await this.client.post<Workflow>(`/workflows/${id}/deactivate`, null, { params });
    return { data: response.data };
  }

  async updateWorkflow(
    id: string,
    environment: EnvironmentType,
    workflowData: any
  ): Promise<{ data: Workflow }> {
    const params = buildEnvironmentParams(environment);
    const response = await this.client.put<Workflow>(`/workflows/${id}`, workflowData, { params });
    return { data: response.data };
  }

  async updateWorkflowTags(
    id: string,
    environment: EnvironmentType,
    tagNames: string[]
  ): Promise<{ data: any }> {
    const params = buildEnvironmentParams(environment);
    const response = await this.client.put(`/workflows/${id}/tags`, tagNames, { params });
    return { data: response.data };
  }

  async deleteWorkflow(id: string, environment: EnvironmentType): Promise<void> {
    const params = buildEnvironmentParams(environment);
    await this.client.delete(`/workflows/${id}`, { params });
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
    const params = buildEnvironmentParams(environment);
    const response = await this.client.post('/workflows/sync-from-github', null, { params });
    return { data: response.data };
  }

  async syncWorkflowsToGithub(environment: EnvironmentType): Promise<{
    data: {
      success: boolean;
      synced: number;
      skipped: number;
      failed: number;
      workflows: Workflow[];
      errors: string[];
    };
  }> {
    const params = buildEnvironmentParams(environment);
    const response = await this.client.post('/workflows/sync-to-github', null, { params });
    return { data: response.data };
  }

  async getWorkflowDrift(workflowId: string, environment: EnvironmentType): Promise<{
    data: {
      hasDrift: boolean;
      gitConfigured: boolean;
      message?: string;
      notInGit?: boolean;
      lastCommitSha?: string;
      lastCommitDate?: string;
      differences?: Array<{
        type: 'added' | 'removed' | 'modified';
        path: string;
        value?: any;
        gitValue?: any;
        runtimeValue?: any;
      }>;
      summary?: {
        nodesAdded: number;
        nodesRemoved: number;
        nodesModified: number;
        connectionsChanged: boolean;
      };
    };
  }> {
    const params = buildEnvironmentParams(environment);
    const response = await this.client.get(`/workflows/${workflowId}/drift`, { params });
    return { data: response.data };
  }

  // Execution endpoints
  async getExecutions(environmentId?: string, workflowId?: string): Promise<{ data: Execution[] }> {
    const params: any = {};
    if (environmentId) params.environment_id = environmentId;
    if (workflowId) params.workflow_id = workflowId;
    const response = await this.client.get<Execution[]>('/executions', { params });
    return { data: response.data };
  }

  // Pipeline endpoints
  private transformPipelineResponse(p: any): Pipeline {
    return {
      id: p.id,
      tenantId: p.tenant_id,
      name: p.name,
      description: p.description,
      isActive: p.is_active,
      environmentIds: p.environment_ids || [],
      stages: (p.stages || []).map((s: any) => ({
        sourceEnvironmentId: s.source_environment_id,
        targetEnvironmentId: s.target_environment_id,
        gates: s.gates ? {
          requireCleanDrift: s.gates.require_clean_drift,
          runPreFlightValidation: s.gates.run_pre_flight_validation,
          credentialsExistInTarget: s.gates.credentials_exist_in_target,
          nodesSupportedInTarget: s.gates.nodes_supported_in_target,
          webhooksAvailable: s.gates.webhooks_available,
          targetEnvironmentHealthy: s.gates.target_environment_healthy,
          maxAllowedRiskLevel: s.gates.max_allowed_risk_level,
        } : undefined,
        approvals: s.approvals ? {
          requireApproval: s.approvals.require_approval,
          approverRole: s.approvals.approver_role,
          approverGroup: s.approvals.approver_group,
          requiredApprovals: s.approvals.required_approvals,
        } : undefined,
        schedule: s.schedule ? {
          restrictPromotionTimes: s.schedule.restrict_promotion_times,
          allowedDays: s.schedule.allowed_days,
          startTime: s.schedule.start_time,
          endTime: s.schedule.end_time,
        } : undefined,
        policyFlags: s.policy_flags ? {
          allowPlaceholderCredentials: s.policy_flags.allow_placeholder_credentials,
          allowOverwritingHotfixes: s.policy_flags.allow_overwriting_hotfixes,
          allowForcePromotionOnConflicts: s.policy_flags.allow_force_promotion_on_conflicts,
        } : undefined,
      })),
      lastModifiedBy: p.last_modified_by,
      lastModifiedAt: p.last_modified_at,
      createdAt: p.created_at,
      updatedAt: p.updated_at,
    };
  }

  async getPipelines(): Promise<{ data: Pipeline[] }> {
    const response = await this.client.get<any[]>('/pipelines');
    return { data: response.data.map((p) => this.transformPipelineResponse(p)) };
  }

  async getPipeline(id: string): Promise<{ data: Pipeline }> {
    const response = await this.client.get<any>(`/pipelines/${id}`);
    return { data: this.transformPipelineResponse(response.data) };
  }

  async createPipeline(pipeline: {
    name: string;
    description?: string;
    isActive: boolean;
    environmentIds: string[];
    stages: PipelineStage[];
  }): Promise<{ data: Pipeline }> {
    // Filter out stages with invalid environment IDs
    const validStages = pipeline.stages.filter(
      (stage) => stage.sourceEnvironmentId && stage.targetEnvironmentId
    );
    const payload = {
      name: pipeline.name,
      description: pipeline.description,
      is_active: pipeline.isActive,
      environment_ids: pipeline.environmentIds.filter((id) => id && id !== 'undefined'),
      stages: validStages.map((stage) => ({
        source_environment_id: stage.sourceEnvironmentId,
        target_environment_id: stage.targetEnvironmentId,
        gates: {
          require_clean_drift: stage.gates?.requireCleanDrift ?? false,
          run_pre_flight_validation: stage.gates?.runPreFlightValidation ?? false,
          credentials_exist_in_target: stage.gates?.credentialsExistInTarget ?? false,
          nodes_supported_in_target: stage.gates?.nodesSupportedInTarget ?? false,
          webhooks_available: stage.gates?.webhooksAvailable ?? false,
          target_environment_healthy: stage.gates?.targetEnvironmentHealthy ?? false,
          max_allowed_risk_level: stage.gates?.maxAllowedRiskLevel ?? 'High',
        },
        approvals: {
          require_approval: stage.approvals?.requireApproval ?? false,
          approver_role: stage.approvals?.approverRole ?? null,
          approver_group: stage.approvals?.approverGroup ?? null,
          required_approvals: stage.approvals?.requiredApprovals ?? null,
        },
        schedule: stage.schedule ? {
          restrict_promotion_times: stage.schedule.restrictPromotionTimes ?? false,
          allowed_days: stage.schedule.allowedDays ?? null,
          start_time: stage.schedule.startTime ?? null,
          end_time: stage.schedule.endTime ?? null,
        } : null,
        policy_flags: {
          allow_placeholder_credentials: stage.policyFlags?.allowPlaceholderCredentials ?? false,
          allow_overwriting_hotfixes: stage.policyFlags?.allowOverwritingHotfixes ?? false,
          allow_force_promotion_on_conflicts: stage.policyFlags?.allowForcePromotionOnConflicts ?? false,
        },
      })),
    };
    const response = await this.client.post<Pipeline>('/pipelines', payload);
    return { data: response.data };
  }

  async updatePipeline(
    id: string,
    updates: {
      name?: string;
      description?: string;
      isActive?: boolean;
      environmentIds?: string[];
      stages?: PipelineStage[];
    }
  ): Promise<{ data: Pipeline }> {
    const payload: any = {};
    if (updates.name !== undefined) payload.name = updates.name;
    if (updates.description !== undefined) payload.description = updates.description;
    if (updates.isActive !== undefined) payload.is_active = updates.isActive;
    if (updates.environmentIds !== undefined) {
      payload.environment_ids = updates.environmentIds.filter((id) => id && id !== 'undefined');
    }
    if (updates.stages !== undefined) {
      const validStages = updates.stages.filter(
        (stage) => stage.sourceEnvironmentId && stage.targetEnvironmentId
      );
      payload.stages = validStages.map((stage) => ({
        source_environment_id: stage.sourceEnvironmentId,
        target_environment_id: stage.targetEnvironmentId,
        gates: {
          require_clean_drift: stage.gates?.requireCleanDrift ?? false,
          run_pre_flight_validation: stage.gates?.runPreFlightValidation ?? false,
          credentials_exist_in_target: stage.gates?.credentialsExistInTarget ?? false,
          nodes_supported_in_target: stage.gates?.nodesSupportedInTarget ?? false,
          webhooks_available: stage.gates?.webhooksAvailable ?? false,
          target_environment_healthy: stage.gates?.targetEnvironmentHealthy ?? false,
          max_allowed_risk_level: stage.gates?.maxAllowedRiskLevel ?? 'High',
        },
        approvals: {
          require_approval: stage.approvals?.requireApproval ?? false,
          approver_role: stage.approvals?.approverRole ?? null,
          approver_group: stage.approvals?.approverGroup ?? null,
          required_approvals: stage.approvals?.requiredApprovals ?? null,
        },
        schedule: stage.schedule ? {
          restrict_promotion_times: stage.schedule.restrictPromotionTimes ?? false,
          allowed_days: stage.schedule.allowedDays ?? null,
          start_time: stage.schedule.startTime ?? null,
          end_time: stage.schedule.endTime ?? null,
        } : null,
        policy_flags: {
          allow_placeholder_credentials: stage.policyFlags?.allowPlaceholderCredentials ?? false,
          allow_overwriting_hotfixes: stage.policyFlags?.allowOverwritingHotfixes ?? false,
          allow_force_promotion_on_conflicts: stage.policyFlags?.allowForcePromotionOnConflicts ?? false,
        },
      }));
    }
    const response = await this.client.patch<Pipeline>(`/pipelines/${id}`, payload);
    return { data: response.data };
  }

  async deletePipeline(id: string): Promise<void> {
    await this.client.delete(`/pipelines/${id}`);
  }

  // Promotion endpoints
  async initiatePromotion(request: PromotionInitiateRequest): Promise<{ data: any }> {
    // Transform camelCase to snake_case for backend
    const payload = {
      pipeline_id: request.pipelineId,
      source_environment_id: request.sourceEnvironmentId,
      target_environment_id: request.targetEnvironmentId,
      workflow_selections: request.workflowSelections?.map(ws => ({
        workflow_id: ws.workflowId,
        workflow_name: ws.workflowName,
        change_type: ws.changeType,
        enabled_in_source: ws.enabledInSource,
        enabled_in_target: ws.enabledInTarget,
        selected: ws.selected,
        requires_overwrite: ws.requiresOverwrite,
      })) || [],
    };
    const response = await this.client.post('/promotions/initiate', payload);
    return { data: response.data };
  }

  async executePromotion(promotionId: string): Promise<{ data: any }> {
    const response = await this.client.post(`/promotions/execute/${promotionId}`);
    return { data: response.data };
  }

  async getPromotionJob(promotionId: string): Promise<{ data: any }> {
    const response = await this.client.get(`/promotions/${promotionId}/job`);
    return { data: response.data };
  }

  async approvePromotion(promotionId: string, approval: PromotionApprovalRequest): Promise<{ data: PromotionApprovalResponse }> {
    const response = await this.client.post<PromotionApprovalResponse>(`/promotions/approvals/${promotionId}/approve`, approval);
    return { data: response.data };
  }

  async getPromotion(promotionId: string): Promise<{ data: PromotionResponse }> {
    const response = await this.client.get<PromotionResponse>(`/promotions/${promotionId}`);
    return { data: response.data };
  }

  async getPromotions(): Promise<{ data: PromotionResponse[] }> {
    const response = await this.client.get<PromotionResponse[]>('/promotions');
    return { data: response.data };
  }

  async createSnapshot(request: PromotionSnapshotRequest): Promise<{ data: PromotionSnapshotResponse }> {
    const response = await this.client.post<PromotionSnapshotResponse>('/promotions/snapshots', request);
    return { data: response.data };
  }

  async checkDrift(request: PromotionCheckDriftRequest): Promise<{ data: PromotionCheckDriftResponse }> {
    const response = await this.client.post<PromotionCheckDriftResponse>('/promotions/check-drift', request);
    return { data: response.data };
  }

  // Deployment endpoints
  async getDeployments(params?: {
    status?: 'pending' | 'running' | 'success' | 'failed' | 'canceled';
    pipelineId?: string;
    environmentId?: string;
    from?: string;
    to?: string;
    page?: number;
    pageSize?: number;
  }): Promise<{
    data: {
      deployments: Deployment[];
      total: number;
      page: number;
      pageSize: number;
      thisWeekSuccessCount: number;
      pendingApprovalsCount: number;
    };
  }> {
    const queryParams: any = {};
    if (params?.status) queryParams.status = params.status;
    if (params?.pipelineId) queryParams.pipeline_id = params.pipelineId;
    if (params?.environmentId) queryParams.environment_id = params.environmentId;
    if (params?.from) queryParams.from = params.from;
    if (params?.to) queryParams.to = params.to;
    if (params?.page) queryParams.page = params.page;
    if (params?.pageSize) queryParams.page_size = params.pageSize;
    
    const response = await this.client.get('/deployments', { params: queryParams });
    // Transform snake_case to camelCase
    const deployments = (response.data.deployments || []).map((d: any) => ({
      id: d.id,
      tenantId: d.tenant_id,
      provider: d.provider || 'n8n',  // Default to n8n for backward compatibility
      pipelineId: d.pipeline_id,
      sourceEnvironmentId: d.source_environment_id,
      targetEnvironmentId: d.target_environment_id,
      status: d.status,
      triggeredByUserId: d.triggered_by_user_id,
      approvedByUserId: d.approved_by_user_id,
      startedAt: d.started_at,
      finishedAt: d.finished_at,
      preSnapshotId: d.pre_snapshot_id,
      postSnapshotId: d.post_snapshot_id,
      summaryJson: d.summary_json,
      createdAt: d.created_at,
      updatedAt: d.updated_at,
      deletedAt: d.deleted_at,
      deletedByUserId: d.deleted_by_user_id,
    }));
    return {
      data: {
        deployments,
        total: response.data.total || 0,
        page: response.data.page || 1,
        pageSize: response.data.page_size || 50,
        thisWeekSuccessCount: response.data.this_week_success_count || 0,
        pendingApprovalsCount: response.data.pending_approvals_count || 0,
      },
    };
  }

  async deleteDeployment(deploymentId: string): Promise<void> {
    await this.client.delete(`/deployments/${deploymentId}`);
  }

  async getDeployment(deploymentId: string): Promise<{ data: DeploymentDetail }> {
    const response = await this.client.get(`/deployments/${deploymentId}`);
    // Transform snake_case to camelCase
    const d = response.data;
    const workflows = (d.workflows || []).map((w: any) => ({
      id: w.id,
      deploymentId: w.deployment_id,
      workflowId: w.workflow_id,
      workflowNameAtTime: w.workflow_name_at_time,
      changeType: w.change_type,
      status: w.status,
      errorMessage: w.error_message,
      createdAt: w.created_at,
    }));
    const deployment: DeploymentDetail = {
      id: d.id,
      tenantId: d.tenant_id,
      pipelineId: d.pipeline_id,
      sourceEnvironmentId: d.source_environment_id,
      targetEnvironmentId: d.target_environment_id,
      status: d.status,
      triggeredByUserId: d.triggered_by_user_id,
      approvedByUserId: d.approved_by_user_id,
      startedAt: d.started_at,
      finishedAt: d.finished_at,
      preSnapshotId: d.pre_snapshot_id,
      postSnapshotId: d.post_snapshot_id,
      summaryJson: d.summary_json,
      createdAt: d.created_at,
      updatedAt: d.updated_at,
      workflows,
      preSnapshot: d.pre_snapshot ? this._transformSnapshot(d.pre_snapshot) : undefined,
      postSnapshot: d.post_snapshot ? this._transformSnapshot(d.post_snapshot) : undefined,
    };
    return { data: deployment };
  }

  // Snapshot endpoints (new Git-backed snapshots)
  async getSnapshots(params?: {
    environmentId?: string;
    type?: 'auto_backup' | 'pre_promotion' | 'post_promotion' | 'manual_backup';
    from?: string;
    to?: string;
    page?: number;
    pageSize?: number;
  }): Promise<{ data: Snapshot[] }> {
    const queryParams: any = {};
    if (params?.environmentId) queryParams.environment_id = params.environmentId;
    if (params?.type) queryParams.type = params.type;
    if (params?.from) queryParams.from = params.from;
    if (params?.to) queryParams.to = params.to;
    if (params?.page) queryParams.page = params.page;
    if (params?.pageSize) queryParams.page_size = params.pageSize;
    
    const response = await this.client.get<Snapshot[]>('/snapshots', { params: queryParams });
    // Transform snake_case to camelCase
    const snapshots = (response.data || []).map((s: any) => this._transformSnapshot(s));
    return { data: snapshots };
  }

  async getSnapshot(snapshotId: string): Promise<{ data: Snapshot }> {
    const response = await this.client.get(`/snapshots/${snapshotId}`);
    return { data: this._transformSnapshot(response.data) };
  }

  async restoreSnapshot(snapshotId: string): Promise<{ data: { success: boolean; message: string; restored: number; failed: number; errors: string[] } }> {
    const response = await this.client.post(`/snapshots/${snapshotId}/restore`);
    return { data: response.data };
  }

  // Helper method to transform snapshot data
  private _transformSnapshot(s: any): Snapshot {
    return {
      id: s.id,
      tenantId: s.tenant_id,
      provider: s.provider || 'n8n',  // Default to n8n for backward compatibility
      environmentId: s.environment_id,
      gitCommitSha: s.git_commit_sha,
      type: s.type,
      createdAt: s.created_at,
      createdByUserId: s.created_by_user_id,
      relatedDeploymentId: s.related_deployment_id,
      metadataJson: s.metadata_json,
    };
  }

  // Legacy snapshot methods (deprecated - kept for backward compatibility)
  async getWorkflowSnapshots(workflowId: string): Promise<{ data: Snapshot[] }> {
    // This is deprecated - use getSnapshots with environmentId instead
    return { data: [] };
  }

  async rollbackWorkflow(snapshotId: string): Promise<{ data: { success: boolean; message: string } }> {
    // This is deprecated - use restoreSnapshot instead
    const result = await this.restoreSnapshot(snapshotId);
    return {
      data: {
        success: result.data.success,
        message: result.data.message,
      },
    };
  }

  // Restore endpoints
  async getRestorePreview(environmentId: string): Promise<{
    data: {
      workflows: Array<{
        id: string;
        name: string;
        currentVersion: any;
        snapshotVersion: any;
        hasChanges: boolean;
      }>;
    };
  }> {
    const response = await this.client.get(`/restore/preview/${environmentId}`);
    return { data: response.data };
  }

  async executeRestore(
    environmentId: string,
    options: {
      workflowIds?: string[];
      snapshotId?: string;
      dryRun?: boolean;
    }
  ): Promise<{ data: { success: boolean; message: string; restored: number } }> {
    const response = await this.client.post(`/restore/execute/${environmentId}`, options);
    return { data: response.data };
  }

  // Team endpoints
  async getTeamMembers(): Promise<{ data: TeamMember[] }> {
    const response = await this.client.get<TeamMember[]>('/team/members');
    return { data: response.data };
  }

  async getTeamLimits(): Promise<{ data: TeamLimits }> {
    const response = await this.client.get<TeamLimits>('/team/limits');
    return { data: response.data };
  }

  async createTeamMember(member: {
    email: string;
    name: string;
    role: string;
  }): Promise<{ data: TeamMember }> {
    const response = await this.client.post<TeamMember>('/team/members', member);
    return { data: response.data };
  }

  async updateTeamMember(id: string, updates: {
    name?: string;
    email?: string;
    role?: string;
  }): Promise<{ data: TeamMember }> {
    const response = await this.client.patch<TeamMember>(`/team/members/${id}`, updates);
    return { data: response.data };
  }

  async deleteTeamMember(id: string): Promise<void> {
    await this.client.delete(`/team/members/${id}`);
  }

  async resendInvitation(id: string): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.post(`/team/members/${id}/resend-invitation`);
    return { data: response.data };
  }

  // Credential endpoints
  async getCredentials(environmentType?: string): Promise<{ data: Credential[] }> {
    const params = environmentType ? { environment_type: environmentType } : {};
    const response = await this.client.get<any[]>('/credentials/', { params });
    // Add provider field with default for backward compatibility
    const data = response.data.map((cred: any) => ({
      ...cred,
      provider: cred.provider || 'n8n',
    }));
    return { data };
  }

  async getCredential(credentialId: string): Promise<{ data: Credential }> {
    const response = await this.client.get<Credential>(`/credentials/${credentialId}`);
    return { data: response.data };
  }

  async createCredential(data: {
    name: string;
    type: string;
    data: Record<string, any>;
    environment_id: string;
  }): Promise<{ data: Credential }> {
    const response = await this.client.post<Credential>('/credentials/', data);
    return { data: response.data };
  }

  async updateCredential(
    credentialId: string,
    data: { name?: string; data?: Record<string, any> }
  ): Promise<{ data: Credential }> {
    const response = await this.client.put<Credential>(`/credentials/${credentialId}`, data);
    return { data: response.data };
  }

  async deleteCredential(credentialId: string, deleteFromN8n: boolean = true): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.delete(`/credentials/${credentialId}`, {
      params: { delete_from_n8n: deleteFromN8n },
    });
    return { data: response.data };
  }

  async getCredentialTypes(environmentId: string): Promise<{ data: any[] }> {
    const response = await this.client.get('/credentials/types/schema', {
      params: { environment_id: environmentId },
    });
    return { data: response.data };
  }

  async syncCredentials(environmentId: string): Promise<{ data: { success: boolean; synced: number; message: string } }> {
    const response = await this.client.post(`/credentials/sync/${environmentId}`);
    return { data: response.data };
  }

  // Provider User endpoints (previously N8N Users)
  async getN8NUsers(environmentType?: string): Promise<{ data: N8NUser[] }> {
    const params = environmentType ? { environment_type: environmentType } : {};
    const response = await this.client.get<N8NUser[]>('/n8n-users/', { params });
    return { data: response.data };
  }

  // Tag endpoints
  async getTags(environmentId: string): Promise<{ data: Tag[] }> {
    const response = await this.client.get<Tag[]>(`/tags/${environmentId}`);
    return { data: response.data };
  }

  // Tenant endpoints (admin)
  async getTenants(params?: {
    search?: string;
    plan?: string;
    status?: string;
    created_from?: string;
    created_to?: string;
    page?: number;
    page_size?: number;
  }): Promise<{ data: { tenants: Tenant[]; total: number; page: number; page_size: number } }> {
    const response = await this.client.get('/tenants', { params });
    return { data: response.data };
  }

  async getTenantById(id: string): Promise<{ data: Tenant }> {
    const response = await this.client.get<Tenant>(`/tenants/${id}`);
    return { data: response.data };
  }

  async getTenantStats(): Promise<{ data: TenantStats }> {
    const response = await this.client.get<TenantStats>('/tenants/stats');
    return { data: response.data };
  }

  async createTenant(tenant: {
    name: string;
    email: string;
    subscription_plan: string;
  }): Promise<{ data: Tenant }> {
    const response = await this.client.post<Tenant>('/tenants', tenant);
    return { data: response.data };
  }

  async updateTenant(id: string, updates: {
    name?: string;
    email?: string;
    subscription_plan?: string;
    status?: string;
    primary_contact_name?: string;
  }): Promise<{ data: Tenant }> {
    const response = await this.client.patch<Tenant>(`/tenants/${id}`, updates);
    return { data: response.data };
  }

  async deleteTenant(id: string): Promise<void> {
    await this.client.delete(`/tenants/${id}`);
  }

  // Tenant Actions
  async suspendTenant(id: string, reason?: string): Promise<{ data: Tenant }> {
    const response = await this.client.post<Tenant>(`/tenants/${id}/suspend`, null, {
      params: reason ? { reason } : {},
    });
    return { data: response.data };
  }

  async reactivateTenant(id: string, reason?: string): Promise<{ data: Tenant }> {
    const response = await this.client.post<Tenant>(`/tenants/${id}/reactivate`, null, {
      params: reason ? { reason } : {},
    });
    return { data: response.data };
  }

  async scheduleTenantDeletion(id: string, retentionDays: number, reason?: string): Promise<{ data: { success: boolean; scheduled_deletion_at: string; retention_days: number } }> {
    const response = await this.client.post(`/tenants/${id}/schedule-deletion`, { retention_days: retentionDays }, {
      params: reason ? { reason } : {},
    });
    return { data: response.data };
  }

  async cancelTenantDeletion(id: string): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.delete(`/tenants/${id}/cancel-deletion`);
    return { data: response.data };
  }

  async exportTenantData(id: string): Promise<{ data: { jobId: string; message: string } }> {
    const response = await this.client.post(`/tenants/${id}/export`);
    return { data: response.data };
  }

  // Tenant Notes
  async getTenantNotes(tenantId: string): Promise<{ data: { notes: TenantNote[]; total: number } }> {
    const response = await this.client.get(`/tenants/${tenantId}/notes`);
    return { data: response.data };
  }

  async createTenantNote(tenantId: string, content: string): Promise<{ data: TenantNote }> {
    const response = await this.client.post(`/tenants/${tenantId}/notes`, { content });
    return { data: response.data };
  }

  async deleteTenantNote(tenantId: string, noteId: string): Promise<void> {
    await this.client.delete(`/tenants/${tenantId}/notes/${noteId}`);
  }

  // Tenant Usage
  async getTenantUsage(tenantId: string): Promise<{ data: TenantUsage }> {
    const response = await this.client.get(`/tenants/${tenantId}/usage`);
    return { data: response.data };
  }

  // Admin Audit Logs
  async getAuditLogs(params?: {
    start_date?: string;
    end_date?: string;
    actor_id?: string;
    action_type?: string;
    tenant_id?: string;
    resource_type?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }): Promise<{ data: { logs: AuditLog[]; total: number; page: number; page_size: number } }> {
    const response = await this.client.get('/admin/audit-logs', { params });
    return { data: response.data };
  }

  async getAuditLogActionTypes(): Promise<{ data: { action_types: string[] } }> {
    const response = await this.client.get('/admin/audit-logs/action-types');
    return { data: response.data };
  }

  async getAuditLogStats(): Promise<{ data: { total: number; last_30_days: number; by_action_type: Record<string, number> } }> {
    const response = await this.client.get('/admin/audit-logs/stats');
    return { data: response.data };
  }

  async exportAuditLogs(params?: {
    action_type?: string;
    format?: 'csv' | 'json';
  }): Promise<{ data: string }> {
    const response = await this.client.get('/admin/audit-logs/export', {
      params,
      responseType: 'text',
    });
    return { data: response.data };
  }

  // Admin Billing
  async getBillingMetrics(): Promise<{ data: BillingMetrics }> {
    const response = await this.client.get('/admin/billing/metrics');
    return { data: response.data };
  }

  async getPlanDistribution(): Promise<{ data: PlanDistributionItem[] }> {
    const response = await this.client.get('/admin/billing/plan-distribution');
    return { data: response.data };
  }

  async getRecentCharges(limit?: number): Promise<{ data: RecentCharge[] }> {
    const response = await this.client.get('/admin/billing/recent-charges', { params: { limit } });
    return { data: response.data };
  }

  async getFailedPayments(limit?: number): Promise<{ data: FailedPayment[] }> {
    const response = await this.client.get('/admin/billing/failed-payments', { params: { limit } });
    return { data: response.data };
  }

  async getDunningTenants(): Promise<{ data: DunningTenant[] }> {
    const response = await this.client.get('/admin/billing/dunning');
    return { data: response.data };
  }

  // Admin Tenant Billing
  async getAdminTenantSubscription(tenantId: string): Promise<{ data: TenantSubscription }> {
    const response = await this.client.get(`/admin/billing/tenants/${tenantId}/subscription`);
    return { data: response.data };
  }

  async getAdminTenantInvoices(tenantId: string, limit?: number): Promise<{ data: TenantInvoice[] }> {
    const response = await this.client.get(`/admin/billing/tenants/${tenantId}/invoices`, { params: { limit } });
    return { data: response.data };
  }

  async changeAdminTenantPlan(tenantId: string, newPlan: string, reason?: string): Promise<{ data: { success: boolean; old_plan: string; new_plan: string } }> {
    const response = await this.client.post(`/admin/billing/tenants/${tenantId}/change-plan`, null, {
      params: { new_plan: newPlan, reason },
    });
    return { data: response.data };
  }

  async extendAdminTenantTrial(tenantId: string, days: number, reason?: string): Promise<{ data: { success: boolean; new_trial_end: string } }> {
    const response = await this.client.post(`/admin/billing/tenants/${tenantId}/extend-trial`, null, {
      params: { days, reason },
    });
    return { data: response.data };
  }

  async cancelAdminTenantSubscription(tenantId: string, atPeriodEnd: boolean, reason?: string): Promise<{ data: { success: boolean; at_period_end: boolean } }> {
    const response = await this.client.post(`/admin/billing/tenants/${tenantId}/cancel-subscription`, null, {
      params: { at_period_end: atPeriodEnd, reason },
    });
    return { data: response.data };
  }

  // Billing endpoints
  async getSubscription(): Promise<{ data: Subscription }> {
    const response = await this.client.get<Subscription>('/billing/subscription');
    return { data: response.data };
  }

  async getSubscriptionPlans(): Promise<{ data: SubscriptionPlan[] }> {
    const response = await this.client.get<SubscriptionPlan[]>('/billing/plans');
    return { data: response.data };
  }

  async getPaymentHistory(limit?: number): Promise<{ data: PaymentHistory[] }> {
    const params = limit ? { limit } : {};
    const response = await this.client.get<PaymentHistory[]>('/billing/payment-history', { params });
    return { data: response.data };
  }

  async createCheckoutSession(planId: string): Promise<{ data: CheckoutSession }> {
    const response = await this.client.post<CheckoutSession>('/billing/checkout', { plan_id: planId });
    return { data: response.data };
  }

  async createPortalSession(returnUrl: string): Promise<{ data: PortalSession }> {
    const response = await this.client.post<PortalSession>('/billing/portal', { return_url: returnUrl });
    return { data: response.data };
  }

  async cancelSubscription(immediate: boolean): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.post('/billing/cancel', { immediate });
    return { data: response.data };
  }

  async reactivateSubscription(): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.post('/billing/reactivate');
    return { data: response.data };
  }

  // Observability endpoints
  async getObservabilityOverview(timeRange: TimeRange = '24h'): Promise<{ data: ObservabilityOverview }> {
    const response = await this.client.get('/observability/overview', {
      params: { time_range: timeRange },
    });
    // Transform snake_case to camelCase
    const data = response.data;
    return {
      data: {
        kpiMetrics: {
          totalExecutions: data.kpi_metrics.total_executions,
          successCount: data.kpi_metrics.success_count,
          failureCount: data.kpi_metrics.failure_count,
          successRate: data.kpi_metrics.success_rate,
          avgDurationMs: data.kpi_metrics.avg_duration_ms,
          p95DurationMs: data.kpi_metrics.p95_duration_ms,
          deltaExecutions: data.kpi_metrics.delta_executions,
          deltaSuccessRate: data.kpi_metrics.delta_success_rate,
        },
        workflowPerformance: (data.workflow_performance || []).map((w: any) => ({
          workflowId: w.workflow_id,
          workflowName: w.workflow_name,
          executionCount: w.execution_count,
          successCount: w.success_count,
          failureCount: w.failure_count,
          errorRate: w.error_rate,
          avgDurationMs: w.avg_duration_ms,
          p95DurationMs: w.p95_duration_ms,
        })),
        environmentHealth: (data.environment_health || []).map((e: any) => ({
          environmentId: e.environment_id,
          environmentName: e.environment_name,
          environmentType: e.environment_type,
          status: e.status,
          latencyMs: e.latency_ms,
          uptimePercent: e.uptime_percent,
          activeWorkflows: e.active_workflows,
          totalWorkflows: e.total_workflows,
          lastDeploymentAt: e.last_deployment_at,
          lastSnapshotAt: e.last_snapshot_at,
          driftState: e.drift_state,
          lastCheckedAt: e.last_checked_at,
        })),
        promotionSyncStats: data.promotion_sync_stats ? {
          promotionsTotal: data.promotion_sync_stats.promotions_total,
          promotionsSuccess: data.promotion_sync_stats.promotions_success,
          promotionsFailed: data.promotion_sync_stats.promotions_failed,
          promotionsBlocked: data.promotion_sync_stats.promotions_blocked,
          snapshotsCreated: data.promotion_sync_stats.snapshots_created,
          snapshotsRestored: data.promotion_sync_stats.snapshots_restored,
          driftCount: data.promotion_sync_stats.drift_count,
          recentDeployments: (data.promotion_sync_stats.recent_deployments || []).map((d: any) => ({
            id: d.id,
            pipelineName: d.pipeline_name,
            sourceEnvironmentName: d.source_environment_name,
            targetEnvironmentName: d.target_environment_name,
            status: d.status,
            startedAt: d.started_at,
            finishedAt: d.finished_at,
          })),
        } : undefined,
      },
    };
  }

  async getWorkflowPerformance(
    timeRange: TimeRange = '24h',
    limit: number = 10,
    sortBy: string = 'executions'
  ): Promise<{ data: WorkflowPerformance[] }> {
    const response = await this.client.get('/observability/workflow-performance', {
      params: { time_range: timeRange, limit, sort_by: sortBy },
    });
    return {
      data: (response.data || []).map((w: any) => ({
        workflowId: w.workflow_id,
        workflowName: w.workflow_name,
        executionCount: w.execution_count,
        successCount: w.success_count,
        failureCount: w.failure_count,
        errorRate: w.error_rate,
        avgDurationMs: w.avg_duration_ms,
        p95DurationMs: w.p95_duration_ms,
      })),
    };
  }

  async getEnvironmentHealthData(): Promise<{ data: EnvironmentHealthData[] }> {
    const response = await this.client.get('/observability/environment-health');
    return {
      data: (response.data || []).map((e: any) => ({
        environmentId: e.environment_id,
        environmentName: e.environment_name,
        environmentType: e.environment_type,
        status: e.status,
        latencyMs: e.latency_ms,
        uptimePercent: e.uptime_percent,
        activeWorkflows: e.active_workflows,
        totalWorkflows: e.total_workflows,
        lastDeploymentAt: e.last_deployment_at,
        lastSnapshotAt: e.last_snapshot_at,
        driftState: e.drift_state,
        lastCheckedAt: e.last_checked_at,
      })),
    };
  }

  async triggerHealthCheck(environmentId: string): Promise<{ data: HealthCheckResponse }> {
    const response = await this.client.post(`/observability/health-check/${environmentId}`);
    return {
      data: {
        id: response.data.id,
        tenantId: response.data.tenant_id,
        environmentId: response.data.environment_id,
        status: response.data.status,
        latencyMs: response.data.latency_ms,
        checkedAt: response.data.checked_at,
        errorMessage: response.data.error_message,
      },
    };
  }

  // Notification endpoints
  async getNotificationChannels(): Promise<{ data: NotificationChannel[] }> {
    const response = await this.client.get('/notifications/channels');
    return {
      data: (response.data || []).map((c: any) => ({
        id: c.id,
        tenantId: c.tenant_id,
        name: c.name,
        type: c.type,
        configJson: c.config_json,
        isEnabled: c.is_enabled,
        createdAt: c.created_at,
        updatedAt: c.updated_at,
      })),
    };
  }

  async createNotificationChannel(data: {
    name: string;
    type: 'n8n_workflow';
    configJson: { environmentId: string; workflowId: string; webhookPath: string };
  }): Promise<{ data: NotificationChannel }> {
    const response = await this.client.post('/notifications/channels', {
      name: data.name,
      type: data.type,
      config_json: {
        environment_id: data.configJson.environmentId,
        workflow_id: data.configJson.workflowId,
        webhook_path: data.configJson.webhookPath,
      },
    });
    return {
      data: {
        id: response.data.id,
        tenantId: response.data.tenant_id,
        name: response.data.name,
        type: response.data.type,
        configJson: response.data.config_json,
        isEnabled: response.data.is_enabled,
        createdAt: response.data.created_at,
        updatedAt: response.data.updated_at,
      },
    };
  }

  async updateNotificationChannel(
    id: string,
    data: { name?: string; configJson?: any; isEnabled?: boolean }
  ): Promise<{ data: NotificationChannel }> {
    const payload: any = {};
    if (data.name !== undefined) payload.name = data.name;
    if (data.configJson !== undefined) payload.config_json = data.configJson;
    if (data.isEnabled !== undefined) payload.is_enabled = data.isEnabled;

    const response = await this.client.put(`/notifications/channels/${id}`, payload);
    return {
      data: {
        id: response.data.id,
        tenantId: response.data.tenant_id,
        name: response.data.name,
        type: response.data.type,
        configJson: response.data.config_json,
        isEnabled: response.data.is_enabled,
        createdAt: response.data.created_at,
        updatedAt: response.data.updated_at,
      },
    };
  }

  async deleteNotificationChannel(id: string): Promise<void> {
    await this.client.delete(`/notifications/channels/${id}`);
  }

  async testNotificationChannel(id: string): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.post(`/notifications/channels/${id}/test`);
    return { data: response.data };
  }

  async getNotificationRules(): Promise<{ data: NotificationRule[] }> {
    const response = await this.client.get('/notifications/rules');
    return {
      data: (response.data || []).map((r: any) => ({
        id: r.id,
        tenantId: r.tenant_id,
        eventType: r.event_type,
        channelIds: r.channel_ids,
        isEnabled: r.is_enabled,
        createdAt: r.created_at,
        updatedAt: r.updated_at,
      })),
    };
  }

  async createNotificationRule(data: {
    eventType: string;
    channelIds: string[];
  }): Promise<{ data: NotificationRule }> {
    const response = await this.client.post('/notifications/rules', {
      event_type: data.eventType,
      channel_ids: data.channelIds,
    });
    return {
      data: {
        id: response.data.id,
        tenantId: response.data.tenant_id,
        eventType: response.data.event_type,
        channelIds: response.data.channel_ids,
        isEnabled: response.data.is_enabled,
        createdAt: response.data.created_at,
        updatedAt: response.data.updated_at,
      },
    };
  }

  async updateNotificationRule(
    ruleId: string,
    data: { channelIds?: string[]; isEnabled?: boolean }
  ): Promise<{ data: NotificationRule }> {
    const payload: any = {};
    if (data.channelIds !== undefined) payload.channel_ids = data.channelIds;
    if (data.isEnabled !== undefined) payload.is_enabled = data.isEnabled;

    const response = await this.client.put(`/notifications/rules/${ruleId}`, payload);
    return {
      data: {
        id: response.data.id,
        tenantId: response.data.tenant_id,
        eventType: response.data.event_type,
        channelIds: response.data.channel_ids,
        isEnabled: response.data.is_enabled,
        createdAt: response.data.created_at,
        updatedAt: response.data.updated_at,
      },
    };
  }

  async deleteNotificationRule(ruleId: string): Promise<void> {
    await this.client.delete(`/notifications/rules/${ruleId}`);
  }

  async getAlertEvents(params?: {
    limit?: number;
    eventType?: string;
  }): Promise<{ data: AlertEvent[] }> {
    const response = await this.client.get('/notifications/events', { params });
    return {
      data: (response.data || []).map((e: any) => ({
        id: e.id,
        tenantId: e.tenant_id,
        eventType: e.event_type,
        environmentId: e.environment_id,
        timestamp: e.timestamp,
        metadataJson: e.metadata_json,
        notificationStatus: e.notification_status,
        channelsNotified: e.channels_notified,
      })),
    };
  }

  async getEventCatalog(): Promise<{ data: EventCatalogItem[] }> {
    const response = await this.client.get('/notifications/event-catalog');
    return {
      data: (response.data || []).map((e: any) => ({
        eventType: e.event_type,
        displayName: e.display_name,
        description: e.description,
        category: e.category,
      })),
    };
  }

  // Admin Entitlements endpoints
  async getFeatureMatrix(): Promise<{ data: FeatureMatrix }> {
    const response = await this.client.get('/admin/entitlements/features/matrix');
    const data = response.data;
    return {
      data: {
        features: (data.features || []).map((f: any) => ({
          featureId: f.feature_id,
          featureKey: f.feature_key,
          featureDisplayName: f.feature_display_name,
          featureType: f.feature_type,
          description: f.description,
          status: f.status,
          planValues: f.plan_values,
        })),
        plans: (data.plans || []).map((p: any) => ({
          id: p.id,
          name: p.name,
          displayName: p.display_name,
          description: p.description,
          sortOrder: p.sort_order,
          isActive: p.is_active,
          tenantCount: 0,
          createdAt: '',
          updatedAt: '',
        })),
        totalFeatures: data.total_features,
      },
    };
  }

  async getAdminFeatures(params?: {
    status?: string;
    type?: string;
  }): Promise<{ data: { features: AdminFeature[]; total: number } }> {
    const queryParams: any = {};
    if (params?.status) queryParams.status_filter = params.status;
    if (params?.type) queryParams.type_filter = params.type;

    const response = await this.client.get('/admin/entitlements/features', { params: queryParams });
    return {
      data: {
        features: (response.data.features || []).map((f: any) => ({
          id: f.id,
          key: f.key,
          displayName: f.display_name,
          description: f.description,
          type: f.type,
          defaultValue: f.default_value,
          status: f.status,
          createdAt: f.created_at,
          updatedAt: f.updated_at,
        })),
        total: response.data.total,
      },
    };
  }

  async getAdminFeature(featureId: string): Promise<{ data: AdminFeature }> {
    const response = await this.client.get(`/admin/entitlements/features/${featureId}`);
    const f = response.data;
    return {
      data: {
        id: f.id,
        key: f.key,
        displayName: f.display_name,
        description: f.description,
        type: f.type,
        defaultValue: f.default_value,
        status: f.status,
        createdAt: f.created_at,
        updatedAt: f.updated_at,
      },
    };
  }

  async getAdminPlans(): Promise<{ data: { plans: AdminPlan[]; total: number } }> {
    const response = await this.client.get('/admin/entitlements/plans');
    return {
      data: {
        plans: (response.data.plans || []).map((p: any) => ({
          id: p.id,
          name: p.name,
          displayName: p.display_name,
          description: p.description,
          sortOrder: p.sort_order,
          isActive: p.is_active,
          tenantCount: p.tenant_count,
          createdAt: p.created_at,
          updatedAt: p.updated_at,
        })),
        total: response.data.total,
      },
    };
  }

  async getAdminPlan(planId: string): Promise<{ data: AdminPlan }> {
    const response = await this.client.get(`/admin/entitlements/plans/${planId}`);
    const p = response.data;
    return {
      data: {
        id: p.id,
        name: p.name,
        displayName: p.display_name,
        description: p.description,
        sortOrder: p.sort_order,
        isActive: p.is_active,
        tenantCount: p.tenant_count,
        createdAt: p.created_at,
        updatedAt: p.updated_at,
      },
    };
  }

  async updatePlanFeatureValue(
    planId: string,
    featureKey: string,
    value: Record<string, any>,
    reason?: string
  ): Promise<{ data: { planId: string; featureKey: string; value: Record<string, any>; updatedAt: string } }> {
    const response = await this.client.patch(`/admin/entitlements/plans/${planId}/features/${featureKey}`, {
      value,
      reason,
    });
    return {
      data: {
        planId: response.data.plan_id,
        featureKey: response.data.feature_key,
        value: response.data.value,
        updatedAt: response.data.updated_at,
      },
    };
  }

  async getPlanFeatures(planId: string): Promise<{
    data: Array<{
      planId: string;
      planName: string;
      featureId: string;
      featureKey: string;
      value: Record<string, any>;
      updatedAt: string;
    }>;
  }> {
    const response = await this.client.get(`/admin/entitlements/plans/${planId}/features`);
    return {
      data: (response.data || []).map((f: any) => ({
        planId: f.plan_id,
        planName: f.plan_name,
        featureId: f.feature_id,
        featureKey: f.feature_key,
        value: f.value,
        updatedAt: f.updated_at,
      })),
    };
  }

  async clearEntitlementsCache(): Promise<{ data: { message: string } }> {
    const response = await this.client.post('/admin/entitlements/cache/clear');
    return { data: response.data };
  }

  // Tenant Feature Overrides endpoints
  async getTenantOverrides(tenantId: string): Promise<{ data: { overrides: TenantFeatureOverride[]; total: number } }> {
    const response = await this.client.get(`/tenants/${tenantId}/entitlements/overrides`);
    return {
      data: {
        overrides: (response.data.overrides || []).map((o: any) => ({
          id: o.id,
          tenantId: o.tenant_id,
          featureId: o.feature_id,
          featureKey: o.feature_key,
          featureDisplayName: o.feature_display_name,
          value: o.value,
          reason: o.reason,
          createdBy: o.created_by,
          createdByEmail: o.created_by_email,
          expiresAt: o.expires_at,
          isActive: o.is_active,
          createdAt: o.created_at,
          updatedAt: o.updated_at,
        })),
        total: response.data.total,
      },
    };
  }

  async createTenantOverride(
    tenantId: string,
    data: { featureKey: string; value: Record<string, any>; reason?: string; expiresAt?: string }
  ): Promise<{ data: TenantFeatureOverride }> {
    const response = await this.client.post(`/tenants/${tenantId}/entitlements/overrides`, {
      feature_key: data.featureKey,
      value: data.value,
      reason: data.reason,
      expires_at: data.expiresAt,
    });
    const o = response.data;
    return {
      data: {
        id: o.id,
        tenantId: o.tenant_id,
        featureId: o.feature_id,
        featureKey: o.feature_key,
        featureDisplayName: o.feature_display_name,
        value: o.value,
        reason: o.reason,
        createdBy: o.created_by,
        createdByEmail: o.created_by_email,
        expiresAt: o.expires_at,
        isActive: o.is_active,
        createdAt: o.created_at,
        updatedAt: o.updated_at,
      },
    };
  }

  async updateTenantOverride(
    tenantId: string,
    overrideId: string,
    data: { value?: Record<string, any>; reason?: string; expiresAt?: string; isActive?: boolean }
  ): Promise<{ data: TenantFeatureOverride }> {
    const payload: any = {};
    if (data.value !== undefined) payload.value = data.value;
    if (data.reason !== undefined) payload.reason = data.reason;
    if (data.expiresAt !== undefined) payload.expires_at = data.expiresAt;
    if (data.isActive !== undefined) payload.is_active = data.isActive;

    const response = await this.client.patch(`/tenants/${tenantId}/entitlements/overrides/${overrideId}`, payload);
    const o = response.data;
    return {
      data: {
        id: o.id,
        tenantId: o.tenant_id,
        featureId: o.feature_id,
        featureKey: o.feature_key,
        featureDisplayName: o.feature_display_name,
        value: o.value,
        reason: o.reason,
        createdBy: o.created_by,
        createdByEmail: o.created_by_email,
        expiresAt: o.expires_at,
        isActive: o.is_active,
        createdAt: o.created_at,
        updatedAt: o.updated_at,
      },
    };
  }

  async deleteTenantOverride(tenantId: string, overrideId: string): Promise<void> {
    await this.client.delete(`/tenants/${tenantId}/entitlements/overrides/${overrideId}`);
  }

  // Audit Logs endpoints
  async getFeatureConfigAudits(params?: {
    tenantId?: string;
    featureKey?: string;
    page?: number;
    pageSize?: number;
  }): Promise<{ data: { audits: FeatureConfigAudit[]; total: number; page: number; pageSize: number } }> {
    const queryParams: any = {};
    if (params?.tenantId) queryParams.tenant_id = params.tenantId;
    if (params?.featureKey) queryParams.feature_key = params.featureKey;
    if (params?.page) queryParams.page = params.page;
    if (params?.pageSize) queryParams.page_size = params.pageSize;

    const response = await this.client.get('/tenants/entitlements/audits', { params: queryParams });
    return {
      data: {
        audits: (response.data.audits || []).map((a: any) => ({
          id: a.id,
          tenantId: a.tenant_id,
          entityType: a.entity_type,
          entityId: a.entity_id,
          featureKey: a.feature_key,
          action: a.action,
          oldValue: a.old_value,
          newValue: a.new_value,
          changedBy: a.changed_by,
          changedByEmail: a.changed_by_email,
          changedAt: a.changed_at,
          reason: a.reason,
        })),
        total: response.data.total,
        page: response.data.page,
        pageSize: response.data.page_size,
      },
    };
  }

  async getFeatureAccessLogs(params?: {
    tenantId?: string;
    featureKey?: string;
    result?: string;
    page?: number;
    pageSize?: number;
  }): Promise<{ data: { logs: FeatureAccessLog[]; total: number; page: number; pageSize: number } }> {
    const queryParams: any = {};
    if (params?.tenantId) queryParams.tenant_id = params.tenantId;
    if (params?.featureKey) queryParams.feature_key = params.featureKey;
    if (params?.result) queryParams.result = params.result;
    if (params?.page) queryParams.page = params.page;
    if (params?.pageSize) queryParams.page_size = params.pageSize;

    const response = await this.client.get('/tenants/entitlements/access-logs', { params: queryParams });
    return {
      data: {
        logs: (response.data.logs || []).map((l: any) => ({
          id: l.id,
          tenantId: l.tenant_id,
          userId: l.user_id,
          userEmail: l.user_email,
          featureKey: l.feature_key,
          accessType: l.access_type,
          result: l.result,
          currentValue: l.current_value,
          limitValue: l.limit_value,
          endpoint: l.endpoint,
          resourceType: l.resource_type,
          resourceId: l.resource_id,
          accessedAt: l.accessed_at,
        })),
        total: response.data.total,
        page: response.data.page,
        pageSize: response.data.page_size,
      },
    };
  }

  // Admin Usage endpoints (Phase 2)
  async getGlobalUsage(): Promise<{ data: any }> {
    const response = await this.client.get('/admin/usage');
    return { data: response.data };
  }

  async getTopTenants(params?: {
    metric?: string;
    period?: string;
    limit?: number;
  }): Promise<{ data: any }> {
    const response = await this.client.get('/admin/usage/top-tenants', { params });
    return { data: response.data };
  }

  async getTenantsAtLimit(threshold?: number): Promise<{ data: any }> {
    const response = await this.client.get('/admin/usage/tenants-at-limit', {
      params: threshold ? { threshold } : {},
    });
    return { data: response.data };
  }

  // Support endpoints
  async createSupportRequest(data: {
    intent_kind: 'bug' | 'feature' | 'task';
    bug_report?: {
      title: string;
      what_happened: string;
      expected_behavior: string;
      steps_to_reproduce?: string;
      severity?: string;
      frequency?: string;
      include_diagnostics: boolean;
      attachments?: Array<{ name: string; url: string; content_type: string }>;
    };
    feature_request?: {
      title: string;
      problem_goal: string;
      desired_outcome: string;
      priority?: string;
      acceptance_criteria?: string[];
      who_is_this_for?: string;
    };
    help_request?: {
      title: string;
      details: string;
      include_diagnostics: boolean;
      attachments?: Array<{ name: string; url: string; content_type: string }>;
    };
    diagnostics?: Record<string, any>;
  }): Promise<{ data: { jsm_request_key: string } }> {
    const response = await this.client.post('/support/requests', data);
    return { data: response.data };
  }

  async getSupportUploadUrl(filename: string, contentType: string): Promise<{
    data: { upload_url: string; public_url: string };
  }> {
    const response = await this.client.post('/support/upload-url', {
      filename,
      content_type: contentType,
    });
    return { data: response.data };
  }

  // Admin Support Config endpoints
  async getSupportConfig(): Promise<{
    data: {
      tenant_id: string;
      n8n_webhook_url?: string;
      n8n_api_key?: string;
      jsm_portal_url?: string;
      jsm_cloud_instance?: string;
      jsm_api_token?: string;
      jsm_project_key?: string;
      jsm_bug_request_type_id?: string;
      jsm_feature_request_type_id?: string;
      jsm_help_request_type_id?: string;
      jsm_widget_embed_code?: string;
      updated_at?: string;
    };
  }> {
    const response = await this.client.get('/admin/support/config');
    return { data: response.data };
  }

  async updateSupportConfig(data: {
    n8n_webhook_url?: string;
    n8n_api_key?: string;
    jsm_portal_url?: string;
    jsm_cloud_instance?: string;
    jsm_api_token?: string;
    jsm_project_key?: string;
    jsm_bug_request_type_id?: string;
    jsm_feature_request_type_id?: string;
    jsm_help_request_type_id?: string;
    jsm_widget_embed_code?: string;
  }): Promise<{
    data: {
      tenant_id: string;
      n8n_webhook_url?: string;
      n8n_api_key?: string;
      jsm_portal_url?: string;
      jsm_cloud_instance?: string;
      jsm_api_token?: string;
      jsm_project_key?: string;
      jsm_bug_request_type_id?: string;
      jsm_feature_request_type_id?: string;
      jsm_help_request_type_id?: string;
      jsm_widget_embed_code?: string;
      updated_at?: string;
    };
  }> {
    const response = await this.client.put('/admin/support/config', data);
    return { data: response.data };
  }

  async testN8nConnection(): Promise<{ data: { success: boolean; message: string } }> {
    const response = await this.client.post('/admin/support/test-n8n');
    return { data: response.data };
  }
}

export const apiClient = new ApiClient();
