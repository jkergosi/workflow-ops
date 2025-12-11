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
  DeploymentWorkflow,
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
  UserResponse,
  Subscription,
  SubscriptionPlan,
  PaymentHistory,
  CheckoutSession,
  PortalSession,
  ApiResponse,
  TimeRange,
  ObservabilityOverview,
  KPIMetrics,
  WorkflowPerformance,
  EnvironmentHealthData,
  PromotionSyncStats,
  HealthCheckResponse,
  NotificationChannel,
  NotificationRule,
  AlertEvent,
  EventCatalogItem,
  Entitlements,
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
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
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
          // Handle unauthorized - redirect to login
          localStorage.removeItem('auth_token');
          window.location.href = '/login';
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

  // Environment endpoints
  async getEnvironments(): Promise<{ data: Environment[] }> {
    const response = await this.client.get<any[]>('/environments');
    // Transform snake_case to camelCase
    const data = response.data.map((env: any) => ({
      ...env,
      id: env.id,
      tenantId: env.tenant_id,
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
    const response = await this.client.get<Workflow[]>('/workflows', { params });
    return { data: response.data };
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
  async getPipelines(): Promise<{ data: Pipeline[] }> {
    const response = await this.client.get<Pipeline[]>('/pipelines');
    return { data: response.data };
  }

  async getPipeline(id: string): Promise<{ data: Pipeline }> {
    const response = await this.client.get<Pipeline>(`/pipelines/${id}`);
    return { data: response.data };
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
  async initiatePromotion(request: PromotionInitiateRequest): Promise<{ data: PromotionInitiateResponse }> {
    const response = await this.client.post<PromotionInitiateResponse>('/promotions/initiate', request);
    return { data: response.data };
  }

  async executePromotion(promotionId: string): Promise<{ data: PromotionExecutionResult }> {
    const response = await this.client.post<PromotionExecutionResult>(`/promotions/execute/${promotionId}`);
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
    const response = await this.client.get<Credential[]>('/credentials/', { params });
    return { data: response.data };
  }

  // N8N User endpoints
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
  async getTenants(): Promise<{ data: Tenant[] }> {
    const response = await this.client.get<Tenant[]>('/admin/tenants');
    return { data: response.data };
  }

  async getTenantStats(): Promise<{ data: TenantStats }> {
    const response = await this.client.get<TenantStats>('/admin/tenants/stats');
    return { data: response.data };
  }

  async createTenant(tenant: {
    name: string;
    email: string;
    subscriptionTier: string;
  }): Promise<{ data: Tenant }> {
    const response = await this.client.post<Tenant>('/admin/tenants', tenant);
    return { data: response.data };
  }

  async updateTenant(id: string, updates: {
    name?: string;
    email?: string;
    subscriptionTier?: string;
  }): Promise<{ data: Tenant }> {
    const response = await this.client.patch<Tenant>(`/admin/tenants/${id}`, updates);
    return { data: response.data };
  }

  async deleteTenant(id: string): Promise<void> {
    await this.client.delete(`/admin/tenants/${id}`);
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
}

export const apiClient = new ApiClient();
