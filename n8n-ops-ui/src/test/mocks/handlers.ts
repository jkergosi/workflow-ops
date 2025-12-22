import { http, HttpResponse } from 'msw';

const API_BASE = 'http://localhost:3000/api/v1';
const API_BASE_4000 = 'http://localhost:4000/api/v1';

// Default fixtures
export const mockUsers = [
  {
    id: 'user-1',
    email: 'admin@example.com',
    name: 'Admin User',
    tenant_id: 'tenant-1',
    role: 'admin',
  },
  {
    id: 'user-2',
    email: 'dev@example.com',
    name: 'Developer',
    tenant_id: 'tenant-1',
    role: 'developer',
  },
];

export const mockTenant = {
  id: 'tenant-1',
  name: 'Test Organization',
  subscription_tier: 'pro',
  status: 'active',
};

export const mockEntitlements = {
  plan_name: 'pro',
  features: {
    max_environments: { enabled: true, limit: 5 },
    max_team_members: { enabled: true, limit: 10 },
    workflow_ci_cd: { enabled: true },
    git_integration: { enabled: true },
    api_access: { enabled: true },
    environment_promotion: { enabled: true },
  },
};

export const mockEnvironments = [
  {
    id: 'env-1',
    tenant_id: 'tenant-1',
    n8n_name: 'Development',
    n8n_type: 'development',
    n8n_base_url: 'https://dev.n8n.example.com',
    is_active: true,
    workflow_count: 5,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'env-2',
    tenant_id: 'tenant-1',
    n8n_name: 'Production',
    n8n_type: 'production',
    n8n_base_url: 'https://prod.n8n.example.com',
    is_active: true,
    workflow_count: 3,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

export const mockEnvironmentTypes = [
  {
    id: 'envt-1',
    tenant_id: 'tenant-1',
    key: 'dev',
    label: 'Development',
    sort_order: 10,
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'envt-2',
    tenant_id: 'tenant-1',
    key: 'staging',
    label: 'Staging',
    sort_order: 20,
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'envt-3',
    tenant_id: 'tenant-1',
    key: 'production',
    label: 'Production',
    sort_order: 30,
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

export const mockWorkflows = [
  {
    id: 'wf-1',
    name: 'Test Workflow 1',
    active: true,
    environment_id: 'env-1',
    n8n_workflow_id: 'n8n-wf-1',
    tags: ['test', 'automation'],
    nodes: [
      { id: 'node-1', type: 'n8n-nodes-base.start', name: 'Start', position: [0, 0] },
      { id: 'node-2', type: 'n8n-nodes-base.httpRequest', name: 'HTTP Request', position: [200, 0] },
    ],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'wf-2',
    name: 'Test Workflow 2',
    active: false,
    environment_id: 'env-1',
    n8n_workflow_id: 'n8n-wf-2',
    tags: [],
    nodes: [],
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-02T00:00:00Z',
  },
];

export const mockPipelines = [
  {
    id: 'pipeline-1',
    tenant_id: 'tenant-1',
    name: 'Dev to Prod Pipeline',
    description: 'Promote workflows from development to production',
    is_active: true,
    environment_ids: ['env-1', 'env-2'],
    stages: [
      {
        source_environment_id: 'env-1',
        target_environment_id: 'env-2',
        gates: { require_clean_drift: true },
        approvals: { require_approval: true, approver_role: 'admin' },
      },
    ],
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

export const handlers = [
  // Auth endpoints
  http.get(`${API_BASE}/auth/dev/users`, () => {
    return HttpResponse.json({ users: mockUsers });
  }),

  http.post(`${API_BASE}/auth/dev/login-as/:userId`, ({ params }) => {
    const user = mockUsers.find((u) => u.id === params.userId);
    if (!user) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json({
      user,
      tenant: mockTenant,
    });
  }),

  http.get(`${API_BASE}/auth/status`, () => {
    return HttpResponse.json({
      authenticated: true,
      onboarding_required: false,
      has_environment: true,
      user: mockUsers[0],
      tenant: mockTenant,
      entitlements: mockEntitlements,
    });
  }),

  http.get(`${API_BASE}/auth/me`, () => {
    return HttpResponse.json(mockUsers[0]);
  }),

  // Admin: environment types (used by Settings + environment forms)
  http.get(`${API_BASE}/admin/environment-types`, () => {
    return HttpResponse.json(mockEnvironmentTypes);
  }),
  http.post(`${API_BASE}/admin/environment-types`, async ({ request }) => {
    const body: any = await request.json();
    return HttpResponse.json({
      id: `envt-${Date.now()}`,
      tenant_id: 'tenant-1',
      key: body.key,
      label: body.label,
      sort_order: body.sort_order ?? 0,
      is_active: body.is_active ?? true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }),
  http.patch(`${API_BASE}/admin/environment-types/:id`, async ({ params, request }) => {
    const body: any = await request.json();
    return HttpResponse.json({
      id: params.id,
      tenant_id: 'tenant-1',
      key: body.key ?? 'dev',
      label: body.label ?? 'Development',
      sort_order: body.sort_order ?? 0,
      is_active: body.is_active ?? true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: new Date().toISOString(),
    });
  }),
  http.delete(`${API_BASE}/admin/environment-types/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(`${API_BASE}/admin/environment-types/reorder`, () => {
    return HttpResponse.json(mockEnvironmentTypes);
  }),

  // Same handlers for tests that use API base :4000
  http.get(`${API_BASE_4000}/admin/environment-types`, () => {
    return HttpResponse.json(mockEnvironmentTypes);
  }),
  http.post(`${API_BASE_4000}/admin/environment-types`, async ({ request }) => {
    const body: any = await request.json();
    return HttpResponse.json({
      id: `envt-${Date.now()}`,
      tenant_id: 'tenant-1',
      key: body.key,
      label: body.label,
      sort_order: body.sort_order ?? 0,
      is_active: body.is_active ?? true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }),
  http.patch(`${API_BASE_4000}/admin/environment-types/:id`, async ({ params, request }) => {
    const body: any = await request.json();
    return HttpResponse.json({
      id: params.id,
      tenant_id: 'tenant-1',
      key: body.key ?? 'dev',
      label: body.label ?? 'Development',
      sort_order: body.sort_order ?? 0,
      is_active: body.is_active ?? true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: new Date().toISOString(),
    });
  }),
  http.delete(`${API_BASE_4000}/admin/environment-types/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),
  http.post(`${API_BASE_4000}/admin/environment-types/reorder`, () => {
    return HttpResponse.json(mockEnvironmentTypes);
  }),

  // Environment endpoints
  http.get(`${API_BASE}/environments`, () => {
    return HttpResponse.json(mockEnvironments);
  }),

  http.get(`${API_BASE}/environments/:id`, ({ params }) => {
    const env = mockEnvironments.find((e) => e.id === params.id);
    if (!env) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(env);
  }),

  http.post(`${API_BASE}/environments`, async ({ request }) => {
    const body = await request.json();
    const newEnv = {
      id: `env-${Date.now()}`,
      tenant_id: 'tenant-1',
      ...body,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json(newEnv, { status: 201 });
  }),

  http.delete(`${API_BASE}/environments/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.post(`${API_BASE}/environments/test-connection`, () => {
    return HttpResponse.json({ success: true, message: 'Connection successful' });
  }),

  http.post(`${API_BASE}/environments/:id/sync`, ({ params }) => {
    return HttpResponse.json({
      success: true,
      message: 'Sync completed',
      results: {
        workflows: { synced: 5, errors: [] },
        executions: { synced: 10, errors: [] },
        credentials: { synced: 3, errors: [] },
        users: { synced: 2, errors: [] },
        tags: { synced: 4, errors: [] },
      },
    });
  }),

  // Workflow endpoints
  http.get(`${API_BASE}/workflows`, () => {
    return HttpResponse.json(mockWorkflows);
  }),

  http.get(`${API_BASE}/workflows/:id`, ({ params }) => {
    const workflow = mockWorkflows.find((w) => w.id === params.id);
    if (!workflow) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(workflow);
  }),

  http.get(`${API_BASE}/workflows/:id/drift`, () => {
    return HttpResponse.json({ data: { has_drift: false } });
  }),

  http.post(`${API_BASE}/workflows/:id/activate`, ({ params }) => {
    const workflow = mockWorkflows.find((w) => w.id === params.id);
    if (!workflow) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json({ ...workflow, active: true });
  }),

  http.post(`${API_BASE}/workflows/:id/deactivate`, ({ params }) => {
    const workflow = mockWorkflows.find((w) => w.id === params.id);
    if (!workflow) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json({ ...workflow, active: false });
  }),

  http.put(`${API_BASE}/workflows/:id`, async ({ params, request }) => {
    const workflow = mockWorkflows.find((w) => w.id === params.id);
    if (!workflow) {
      return new HttpResponse(null, { status: 404 });
    }
    const body = await request.json();
    return HttpResponse.json({ ...workflow, ...body, updated_at: new Date().toISOString() });
  }),

  http.delete(`${API_BASE}/workflows/:id`, ({ params }) => {
    const workflow = mockWorkflows.find((w) => w.id === params.id);
    if (!workflow) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json({ success: true });
  }),

  http.put(`${API_BASE}/workflows/:id/tags`, async ({ params, request }) => {
    const workflow = mockWorkflows.find((w) => w.id === params.id);
    if (!workflow) {
      return new HttpResponse(null, { status: 404 });
    }
    const body = await request.json();
    return HttpResponse.json({ ...workflow, tags: body.tags || body });
  }),

  http.post(`${API_BASE}/workflows/sync-to-github`, () => {
    return HttpResponse.json({ success: true, synced: 2, skipped: 0, failed: 0 });
  }),

  // Execution endpoints
  http.get(`${API_BASE}/executions`, () => {
    return HttpResponse.json([
      { id: 'exec-1', workflowId: 'wf-1', status: 'success', startedAt: '2024-01-01T00:00:00Z' },
      { id: 'exec-2', workflowId: 'wf-1', status: 'success', startedAt: '2024-01-02T00:00:00Z' },
      { id: 'exec-3', workflowId: 'wf-2', status: 'error', startedAt: '2024-01-03T00:00:00Z' },
    ]);
  }),

  // Promotions endpoints
  http.get(`${API_BASE}/promotions`, () => {
    return HttpResponse.json([]);
  }),

  http.post(`${API_BASE}/promotions/initiate`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: `promo-${Date.now()}`,
      status: 'pending_approval',
      pipeline_id: body.pipeline_id,
      source_environment_id: body.source_environment_id,
      target_environment_id: body.target_environment_id,
      workflows: body.workflow_ids?.map((id: string) => ({ id, name: `Workflow ${id}` })) || [],
      gate_results: { all_passed: true },
      created_at: new Date().toISOString(),
    });
  }),

  http.post(`${API_BASE}/promotions/:id/approve`, ({ params }) => {
    return HttpResponse.json({ id: params.id, status: 'approved', approved_at: new Date().toISOString() });
  }),

  http.post(`${API_BASE}/promotions/:id/execute`, ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      status: 'completed',
      executed_at: new Date().toISOString(),
      results: { workflows_promoted: 2, errors: [] },
    });
  }),

  // Pipeline endpoints
  http.get(`${API_BASE}/pipelines`, () => {
    return HttpResponse.json(mockPipelines);
  }),

  http.get(`${API_BASE}/pipelines/:id`, ({ params }) => {
    const pipeline = mockPipelines.find((p) => p.id === params.id);
    if (!pipeline) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(pipeline);
  }),

  http.post(`${API_BASE}/pipelines`, async ({ request }) => {
    const body = await request.json();
    const newPipeline = {
      id: `pipeline-${Date.now()}`,
      tenant_id: 'tenant-1',
      ...body,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json(newPipeline, { status: 201 });
  }),

  http.delete(`${API_BASE}/pipelines/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Team endpoints
  http.get(`${API_BASE}/team/members`, () => {
    return HttpResponse.json(
      mockUsers.map((u) => ({
        ...u,
        created_at: '2024-01-01T00:00:00Z',
        status: 'active',
      }))
    );
  }),

  http.get(`${API_BASE}/team/limits`, () => {
    return HttpResponse.json({
      max_members: 10,
      current_members: 2,
      can_add_members: true,
    });
  }),

  http.patch(`${API_BASE}/team/members/:id`, async ({ params, request }) => {
    const updates: any = await request.json();
    const base = mockUsers.find((u) => u.id === params.id) || mockUsers[0];
    return HttpResponse.json({
      ...base,
      ...updates,
      id: String(params.id),
      created_at: '2024-01-01T00:00:00Z',
      status: 'active',
    });
  }),

  http.delete(`${API_BASE}/team/members/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Deployments
  http.get(`${API_BASE}/deployments`, () => {
    return HttpResponse.json({
      deployments: [],
      total: 0,
      page: 1,
      page_size: 50,
      this_week_success_count: 0,
      pending_approvals_count: 0,
    });
  }),

  // Snapshots
  http.get(`${API_BASE}/snapshots`, () => {
    return HttpResponse.json([]);
  }),

  // Billing
  http.get(`${API_BASE}/billing/subscription`, () => {
    return HttpResponse.json({
      plan: 'pro',
      status: 'active',
      current_period_end: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    });
  }),

  http.get(`${API_BASE}/billing/plans`, () => {
    return HttpResponse.json([
      { id: 'free', name: 'Free', price: 0 },
      { id: 'pro', name: 'Pro', price: 29 },
      { id: 'enterprise', name: 'Enterprise', price: 99 },
    ]);
  }),

  http.get(`${API_BASE}/billing/payment-history`, () => {
    return HttpResponse.json([]);
  }),

  // N8N Users endpoints - returns array directly (with and without trailing slash)
  http.get(`${API_BASE}/n8n-users/`, () => {
    return HttpResponse.json([
      {
        id: 'n8n-user-1',
        email: 'admin@example.com',
        first_name: 'Admin',
        last_name: 'User',
        role: 'owner',
        is_pending: false,
        environment: { id: 'env-1', name: 'Development', type: 'dev' },
        last_synced_at: '2024-01-15T10:00:00Z',
      },
      {
        id: 'n8n-user-2',
        email: 'member@example.com',
        first_name: 'Member',
        last_name: 'User',
        role: 'member',
        is_pending: false,
        environment: { id: 'env-1', name: 'Development', type: 'dev' },
        last_synced_at: '2024-01-14T10:00:00Z',
      },
    ]);
  }),

  http.get(`${API_BASE}/n8n-users`, () => {
    return HttpResponse.json([
      {
        id: 'n8n-user-1',
        email: 'admin@example.com',
        first_name: 'Admin',
        last_name: 'User',
        role: 'owner',
        is_pending: false,
        environment: { id: 'env-1', name: 'Development', type: 'dev' },
        last_synced_at: '2024-01-15T10:00:00Z',
      },
      {
        id: 'n8n-user-2',
        email: 'member@example.com',
        first_name: 'Member',
        last_name: 'User',
        role: 'member',
        is_pending: false,
        environment: { id: 'env-1', name: 'Development', type: 'dev' },
        last_synced_at: '2024-01-14T10:00:00Z',
      },
    ]);
  }),

  // Restore preview endpoint
  http.get(`${API_BASE}/restore/preview/:environmentId`, () => {
    return HttpResponse.json({
      data: {
        environment_id: 'env-1',
        environment_name: 'Development',
        github_repo: 'org/repo',
        github_branch: 'main',
        total_new: 2,
        total_update: 1,
        has_encryption_key: true,
        workflows: [
          {
            workflow_id: 'wf-1',
            name: 'New Workflow',
            status: 'new',
            nodes_count: 5,
          },
          {
            workflow_id: 'wf-2',
            name: 'Update Workflow',
            status: 'update',
            nodes_count: 3,
          },
        ],
      },
    });
  }),

  // Restore execute endpoint
  http.post(`${API_BASE}/restore/:environmentId`, () => {
    return HttpResponse.json({
      success: true,
      workflows_created: 2,
      workflows_updated: 1,
      workflows_failed: 0,
      snapshots_created: 1,
      results: [],
      errors: [],
    });
  }),

  // Tags endpoints
  http.get(`${API_BASE}/tags`, () => {
    return HttpResponse.json([
      { id: 'tag-1', name: 'production', created_at: '2024-01-01T00:00:00Z' },
      { id: 'tag-2', name: 'staging', created_at: '2024-01-02T00:00:00Z' },
      { id: 'tag-3', name: 'automation', created_at: '2024-01-03T00:00:00Z' },
    ]);
  }),

  // Credentials endpoints
  http.get(`${API_BASE}/credentials`, () => {
    return HttpResponse.json([
      { id: 'cred-1', name: 'Slack API', type: 'slackApi', created_at: '2024-01-01T00:00:00Z' },
      { id: 'cred-2', name: 'GitHub Token', type: 'githubApi', created_at: '2024-01-02T00:00:00Z' },
    ]);
  }),

  // Dashboard stats
  http.get(`${API_BASE}/stats/dashboard`, () => {
    return HttpResponse.json({
      total_workflows: 10,
      active_workflows: 7,
      total_executions: 100,
      successful_executions: 85,
      failed_executions: 15,
    });
  }),

  // User profile update
  http.patch(`${API_BASE}/auth/me`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: 'user-1',
      ...body,
      updated_at: new Date().toISOString(),
    });
  }),

  // Observability endpoint
  http.get(`${API_BASE}/observability/overview`, () => {
    return HttpResponse.json({
      data: {
        kpiMetrics: {
          totalExecutions: 1000,
          successRate: 95.5,
          avgDurationMs: 5000,
          p95DurationMs: 15000,
          failureCount: 45,
          deltaExecutions: 10,
          deltaSuccessRate: 2.5,
        },
        workflowPerformance: [
          {
            workflowId: 'wf-1',
            workflowName: 'Test Workflow 1',
            executionCount: 500,
            successCount: 480,
            failureCount: 20,
            errorRate: 4.0,
          },
        ],
        environmentHealth: [
          {
            environmentId: 'env-1',
            environmentName: 'Development',
            environmentType: 'dev',
            status: 'healthy',
            latencyMs: 150,
            uptimePercent: 99.9,
            activeWorkflows: 10,
            totalWorkflows: 12,
            driftState: 'in_sync',
          },
        ],
        promotionSyncStats: {
          promotionsTotal: 10,
          promotionsSuccess: 8,
          promotionsFailed: 2,
          snapshotsCreated: 15,
          driftCount: 1,
          recentDeployments: [
            {
              id: 'deploy-1',
              sourceEnvironmentName: 'Dev',
              targetEnvironmentName: 'Staging',
              status: 'success',
            },
          ],
        },
      },
    });
  }),

  // Notifications endpoints (for AlertsPage)
  http.get(`${API_BASE}/notifications/channels`, () => {
    return HttpResponse.json({
      data: [
        {
          id: 'channel-1',
          name: 'Slack Alerts',
          type: 'slack',
          isEnabled: true,
          configJson: { webhook_url: 'https://hooks.slack.com/...' },
        },
        {
          id: 'channel-2',
          name: 'Email Notifications',
          type: 'email',
          isEnabled: false,
          configJson: { smtp_host: 'smtp.example.com' },
        },
      ],
    });
  }),

  http.get(`${API_BASE}/notifications/rules`, () => {
    return HttpResponse.json({
      data: [
        {
          id: 'rule-1',
          eventType: 'workflow.execution.failed',
          channelIds: ['channel-1'],
          isEnabled: true,
        },
      ],
    });
  }),

  http.get(`${API_BASE}/notifications/events`, () => {
    return HttpResponse.json({
      data: [
        {
          id: 'event-1',
          eventType: 'workflow.execution.failed',
          timestamp: new Date().toISOString(),
          notificationStatus: 'sent',
          channelsNotified: ['channel-1'],
        },
      ],
    });
  }),

  http.get(`${API_BASE}/notifications/catalog`, () => {
    return HttpResponse.json({
      data: [
        {
          eventType: 'workflow.execution.failed',
          displayName: 'Workflow Execution Failed',
          description: 'Triggered when a workflow execution fails',
          category: 'workflow',
        },
        {
          eventType: 'workflow.execution.success',
          displayName: 'Workflow Execution Success',
          description: 'Triggered when a workflow execution completes successfully',
          category: 'workflow',
        },
      ],
    });
  }),

  http.get(`${API_BASE}/notifications/event-catalog`, () => {
    return HttpResponse.json({
      data: [
        {
          eventType: 'workflow.execution.failed',
          displayName: 'Workflow Execution Failed',
          description: 'Triggered when a workflow execution fails',
          category: 'workflow',
        },
        {
          eventType: 'workflow.execution.success',
          displayName: 'Workflow Execution Success',
          description: 'Triggered when a workflow execution completes successfully',
          category: 'workflow',
        },
      ],
    });
  }),

  http.post(`${API_BASE}/notifications/channels`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: `channel-${Date.now()}`,
      ...body,
      created_at: new Date().toISOString(),
    }, { status: 201 });
  }),

  http.post(`${API_BASE}/notifications/rules`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: `rule-${Date.now()}`,
      ...body,
      created_at: new Date().toISOString(),
    }, { status: 201 });
  }),

  // Pipeline update endpoint
  http.patch(`${API_BASE}/pipelines/:id`, async ({ params, request }) => {
    const pipeline = mockPipelines.find((p) => p.id === params.id);
    if (!pipeline) {
      return new HttpResponse(null, { status: 404 });
    }
    const body = await request.json();
    return HttpResponse.json({ ...pipeline, ...body, updated_at: new Date().toISOString() });
  }),

  // Environment update endpoint
  http.patch(`${API_BASE}/environments/:id`, async ({ params, request }) => {
    const env = mockEnvironments.find((e) => e.id === params.id);
    if (!env) {
      return new HttpResponse(null, { status: 404 });
    }
    const body = await request.json();
    return HttpResponse.json({ ...env, ...body, updated_at: new Date().toISOString() });
  }),

  // GitHub test connection
  http.post(`${API_BASE}/environments/test-git-connection`, () => {
    return HttpResponse.json({ success: true, message: 'Git connection successful' });
  }),

  // Admin endpoints
  // Tenants
  http.get(`${API_BASE}/admin/tenants`, () => {
    return HttpResponse.json({
      tenants: [
        {
          id: 'tenant-1',
          name: 'Acme Corp',
          email: 'admin@acme.com',
          subscriptionPlan: 'pro',
          status: 'active',
          workflowCount: 15,
          environmentCount: 3,
          userCount: 5,
          createdAt: '2024-01-01T00:00:00Z',
        },
        {
          id: 'tenant-2',
          name: 'Test Org',
          email: 'admin@test.com',
          subscriptionPlan: 'free',
          status: 'active',
          workflowCount: 5,
          environmentCount: 1,
          userCount: 2,
          createdAt: '2024-02-01T00:00:00Z',
        },
      ],
      total: 2,
      total_pages: 1,
    });
  }),

  http.get(`${API_BASE}/admin/tenants/stats`, () => {
    return HttpResponse.json({
      totalTenants: 10,
      activeTenants: 8,
      suspendedTenants: 2,
      byPlan: { free: 5, pro: 3, agency: 1, enterprise: 1 },
    });
  }),

  http.get(`${API_BASE}/tenants/stats`, () => {
    return HttpResponse.json({
      totalTenants: 10,
      activeTenants: 8,
      suspendedTenants: 2,
      trialTenants: 1,
      paidTenants: 4,
      byPlan: { free: 5, pro: 3, agency: 1, enterprise: 1 },
      recentSignups: 2,
      churnedThisMonth: 0,
    });
  }),

  http.get(`${API_BASE}/admin/tenants/:id`, ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      name: 'Acme Corp',
      email: 'admin@acme.com',
      subscriptionPlan: 'pro',
      status: 'active',
      workflowCount: 15,
      environmentCount: 3,
      userCount: 5,
      createdAt: '2024-01-01T00:00:00Z',
    });
  }),

  http.post(`${API_BASE}/admin/tenants`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: `tenant-${Date.now()}`,
      ...body,
      status: 'active',
      createdAt: new Date().toISOString(),
    }, { status: 201 });
  }),

  http.patch(`${API_BASE}/admin/tenants/:id`, async ({ params, request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: params.id,
      ...body,
      updatedAt: new Date().toISOString(),
    });
  }),

  http.delete(`${API_BASE}/admin/tenants/:id`, () => {
    return HttpResponse.json({ success: true });
  }),

  http.post(`${API_BASE}/admin/tenants/:id/suspend`, () => {
    return HttpResponse.json({ success: true, status: 'suspended' });
  }),

  http.post(`${API_BASE}/admin/tenants/:id/reactivate`, () => {
    return HttpResponse.json({ success: true, status: 'active' });
  }),

  // Plans & Billing
  http.get(`${API_BASE}/admin/billing/plan-distribution`, () => {
    return HttpResponse.json([
      { plan: 'free', count: 50 },
      { plan: 'pro', count: 30 },
      { plan: 'agency', count: 15 },
      { plan: 'enterprise', count: 5 },
    ]);
  }),

  http.get(`${API_BASE}/admin/billing/metrics`, () => {
    return HttpResponse.json({
      mrr: 15000,
      arr: 180000,
      total_subscriptions: 100,
      churn_rate: 2.5,
    });
  }),

  http.get(`${API_BASE}/admin/billing/transactions`, () => {
    return HttpResponse.json({
      transactions: [],
      total: 0,
    });
  }),

  // Usage
  http.get(`${API_BASE}/admin/usage`, () => {
    return HttpResponse.json({
      stats: {
        total_tenants: 100,
        total_workflows: 500,
        total_environments: 150,
        total_users: 300,
        total_executions_today: 5000,
        total_executions_month: 150000,
        tenants_at_limit: 5,
        tenants_over_limit: 2,
        tenants_near_limit: 10,
      },
      usage_by_plan: { free: 50, pro: 30, agency: 15, enterprise: 5 },
      recent_growth: {
        tenants_7d: 5,
        tenants_30d: 15,
        workflows_7d: 25,
        workflows_30d: 75,
        executions_7d: 35000,
        executions_30d: 150000,
      },
    });
  }),

  http.get(`${API_BASE}/admin/usage/top-tenants`, () => {
    return HttpResponse.json({
      tenants: [
        { rank: 1, tenant_id: 'tenant-1', tenant_name: 'Acme Corp', plan: 'enterprise', value: 100, limit: 500, percentage: 20 },
        { rank: 2, tenant_id: 'tenant-2', tenant_name: 'Test Org', plan: 'pro', value: 50, limit: 100, percentage: 50 },
      ],
    });
  }),

  http.get(`${API_BASE}/admin/usage/at-limit`, () => {
    return HttpResponse.json({
      tenants: [
        {
          tenant_id: 'tenant-3',
          tenant_name: 'Over Limit Corp',
          plan: 'pro',
          status: 'warning',
          total_usage_percentage: 95,
          metrics: [
            { name: 'workflows', current: 95, limit: 100, percentage: 95 },
          ],
        },
      ],
    });
  }),

  http.get(`${API_BASE}/admin/usage/tenants-at-limit`, () => {
    return HttpResponse.json({
      tenants: [],
    });
  }),

  http.get(`${API_BASE}/admin/billing/recent-charges`, () => {
    return HttpResponse.json([
      { id: 'ch_1', tenantName: 'Acme Corp', amount: 99, status: 'succeeded', createdAt: '2024-01-15T10:00:00Z' },
    ]);
  }),

  http.get(`${API_BASE}/admin/billing/failed-payments`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE}/admin/billing/dunning`, () => {
    return HttpResponse.json([]);
  }),

  // Audit Logs
  http.get(`${API_BASE}/admin/audit-logs`, () => {
    return HttpResponse.json({
      logs: [
        {
          id: 'log-1',
          timestamp: new Date().toISOString(),
          actorEmail: 'admin@test.com',
          actorId: 'user-1',
          tenantId: 'tenant-1',
          actionType: 'tenant_created',
          resourceType: 'tenant',
          resourceId: 'tenant-1',
          ipAddress: '192.168.1.1',
          oldValue: null,
          newValue: { name: 'Test Tenant' },
        },
        {
          id: 'log-2',
          timestamp: new Date(Date.now() - 3600000).toISOString(),
          actorEmail: 'admin@test.com',
          actorId: 'user-1',
          tenantId: 'tenant-1',
          actionType: 'feature_override_created',
          resourceType: 'feature',
          resourceId: 'feature-1',
          ipAddress: '192.168.1.1',
          oldValue: null,
          newValue: { feature: 'max_workflows', value: 200 },
        },
      ],
      total: 2,
    });
  }),

  http.post(`${API_BASE}/admin/audit-logs/export`, () => {
    return HttpResponse.json({ data: 'id,timestamp,action\n1,2024-01-01,test' });
  }),

  // Feature Matrix / Entitlements
  http.get(`${API_BASE}/admin/entitlements/matrix`, () => {
    return HttpResponse.json({
      features: [
        { key: 'max_environments', name: 'Environments', free: 1, pro: 3, agency: 10, enterprise: -1 },
        { key: 'max_workflows', name: 'Workflows', free: 10, pro: 100, agency: 500, enterprise: -1 },
      ],
    });
  }),

  http.get(`${API_BASE}/admin/entitlements/features/matrix`, () => {
    return HttpResponse.json({
      features: [
        { key: 'max_environments', name: 'Environments', free: 1, pro: 3, agency: 10, enterprise: -1, description: 'Number of environments allowed' },
        { key: 'max_workflows', name: 'Workflows', free: 10, pro: 100, agency: 500, enterprise: -1, description: 'Number of workflows allowed' },
        { key: 'max_users', name: 'Users', free: 2, pro: 10, agency: 50, enterprise: -1, description: 'Number of users allowed' },
      ],
      plans: [
        { id: 'free', name: 'Free', description: 'Get started for free' },
        { id: 'pro', name: 'Pro', description: 'For growing teams' },
        { id: 'agency', name: 'Agency', description: 'For agencies' },
        { id: 'enterprise', name: 'Enterprise', description: 'For large organizations' },
      ],
    });
  }),

  http.get(`${API_BASE}/admin/entitlements/plans`, () => {
    return HttpResponse.json({
      plans: [
        { id: 'free', name: 'Free', price: 0, description: 'Get started for free' },
        { id: 'pro', name: 'Pro', price: 49, description: 'For growing teams' },
        { id: 'agency', name: 'Agency', price: 199, description: 'For agencies' },
        { id: 'enterprise', name: 'Enterprise', price: 499, description: 'For large organizations' },
      ],
    });
  }),

  http.get(`${API_BASE}/admin/entitlements/overrides`, () => {
    return HttpResponse.json({
      overrides: [
        {
          id: 'override-1',
          tenant_id: 'tenant-1',
          tenant_name: 'Acme Corp',
          feature_key: 'max_workflows',
          override_value: 200,
          reason: 'Enterprise upgrade pending',
          created_at: '2024-01-01T00:00:00Z',
          created_by: 'admin@test.com',
        },
      ],
    });
  }),

  http.get(`${API_BASE}/admin/entitlements/audit`, () => {
    return HttpResponse.json({
      entries: [
        {
          id: 'audit-1',
          timestamp: new Date().toISOString(),
          actor_email: 'admin@test.com',
          action: 'override_created',
          tenant_name: 'Acme Corp',
          feature_key: 'max_workflows',
          old_value: null,
          new_value: 200,
        },
      ],
      total: 1,
    });
  }),

  // Credential Health
  http.get(`${API_BASE}/admin/credentials/health`, () => {
    return HttpResponse.json({
      summary: {
        total: 50,
        healthy: 45,
        warning: 3,
        error: 2,
      },
      credentials: [
        { id: 'cred-1', name: 'Slack API', type: 'slackApi', status: 'healthy', lastChecked: new Date().toISOString() },
        { id: 'cred-2', name: 'GitHub Token', type: 'githubApi', status: 'warning', lastChecked: new Date().toISOString() },
      ],
    });
  }),

  // Admin Notifications
  http.get(`${API_BASE}/admin/notifications`, () => {
    return HttpResponse.json({
      notifications: [
        {
          id: 'notif-1',
          type: 'system',
          title: 'System Maintenance',
          message: 'Scheduled maintenance on Saturday',
          read: false,
          createdAt: new Date().toISOString(),
        },
      ],
      total: 1,
    });
  }),

  // Tenants endpoint (non-admin)
  http.get(`${API_BASE}/tenants`, () => {
    return HttpResponse.json({
      tenants: [
        {
          id: 'tenant-1',
          name: 'Acme Corp',
          email: 'admin@acme.com',
          subscriptionPlan: 'pro',
          status: 'active',
        },
        {
          id: 'tenant-2',
          name: 'Test Org',
          email: 'admin@test.com',
          subscriptionPlan: 'free',
          status: 'active',
        },
      ],
      total: 2,
    });
  }),

  // Admin entitlements features
  http.get(`${API_BASE}/admin/entitlements/features`, () => {
    return HttpResponse.json({
      features: [
        { key: 'max_environments', name: 'Max Environments', description: 'Maximum environments allowed' },
        { key: 'max_workflows', name: 'Max Workflows', description: 'Maximum workflows allowed' },
        { key: 'max_team_members', name: 'Max Team Members', description: 'Maximum team members allowed' },
      ],
    });
  }),

  // Entitlements audit endpoints
  http.get(`${API_BASE}/tenants/entitlements/audits`, () => {
    return HttpResponse.json({
      audits: [
        {
          id: 'audit-1',
          timestamp: new Date().toISOString(),
          actor_email: 'admin@test.com',
          action: 'override_created',
          tenant_name: 'Acme Corp',
          feature_key: 'max_workflows',
          old_value: null,
          new_value: 200,
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    });
  }),

  http.get(`${API_BASE}/tenants/entitlements/access-logs`, () => {
    return HttpResponse.json({
      logs: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
  }),

  // Active providers endpoint
  http.get(`${API_BASE}/providers/active`, () => {
    return HttpResponse.json([
      { provider: 'n8n', displayName: 'n8n', isActive: true },
      { provider: 'local', displayName: 'Local', isActive: true },
    ]);
  }),

  http.get(`${API_BASE}/admin/providers/active`, () => {
    return HttpResponse.json({
      providers: [
        { provider: 'n8n', displayName: 'n8n', isActive: true },
        { provider: 'local', displayName: 'Local', isActive: true },
      ],
      total_providers: 2,
      is_multi_provider: true,
    });
  }),

  // Logical credentials endpoint
  http.get(`${API_BASE}/credentials/logical`, () => {
    return HttpResponse.json([
      { id: 'logical-1', name: 'Slack API', requiredType: 'slackApi', description: 'Slack API credentials', tenantId: 'tenant-1' },
      { id: 'logical-2', name: 'GitHub Token', requiredType: 'githubApi', description: 'GitHub API credentials', tenantId: 'tenant-1' },
    ]);
  }),

  // Credential mappings endpoint
  http.get(`${API_BASE}/credentials/mappings`, () => {
    return HttpResponse.json([
      { id: 'mapping-1', logicalCredentialId: 'logical-1', environmentId: 'env-1', physicalCredentialId: 'physical-1', provider: 'n8n' },
    ]);
  }),

  // Credentials by environment endpoint
  http.get(`${API_BASE}/credentials/by-environment/:environmentId`, () => {
    return HttpResponse.json([
      { id: 'n8n-cred-1', name: 'Dev Slack', type: 'slackApi', createdAt: '2024-01-01T00:00:00Z' },
      { id: 'n8n-cred-2', name: 'Dev GitHub', type: 'githubApi', createdAt: '2024-01-02T00:00:00Z' },
      { id: 'n8n-cred-3', name: 'Dev PostgreSQL', type: 'postgresApi', createdAt: '2024-01-03T00:00:00Z' },
    ]);
  }),

  // Credential matrix endpoint
  http.get(`${API_BASE}/admin/credentials/matrix`, () => {
    return HttpResponse.json({
      logical_credentials: [
        { id: 'logical-1', name: 'slackApi:prod-slack', requiredType: 'slackApi', description: 'Slack credentials' },
        { id: 'logical-2', name: 'githubApi:gh-token', requiredType: 'githubApi', description: 'GitHub credentials' },
      ],
      environments: [
        { id: 'env-1', name: 'Development', type: 'development' },
        { id: 'env-2', name: 'Production', type: 'production' },
      ],
      matrix: {
        'logical-1': {
          'env-1': { mappingId: 'mapping-1', physicalCredentialId: 'n8n-cred-1', physicalName: 'Dev Slack', physicalType: 'slackApi', status: 'valid' },
          'env-2': { mappingId: 'mapping-2', physicalCredentialId: 'n8n-cred-2', physicalName: 'Prod Slack', physicalType: 'slackApi', status: 'valid' },
        },
        'logical-2': {
          'env-1': { mappingId: 'mapping-3', physicalCredentialId: 'n8n-cred-3', physicalName: 'Dev GitHub', physicalType: 'githubApi', status: 'valid' },
          'env-2': null,
        },
      },
    });
  }),

  // Credential discovery endpoint
  http.post(`${API_BASE}/admin/credentials/discover/:environmentId`, () => {
    return HttpResponse.json([
      { type: 'slackApi', name: 'prod-slack', logicalKey: 'slackApi:prod-slack', workflowCount: 3, workflows: [{ id: 'wf-1', name: 'Workflow 1' }], existingLogicalId: 'logical-1', mappingStatus: 'mapped' },
      { type: 'githubApi', name: 'gh-token', logicalKey: 'githubApi:gh-token', workflowCount: 2, workflows: [{ id: 'wf-2', name: 'Workflow 2' }], existingLogicalId: null, mappingStatus: 'unmapped' },
      { type: 'postgresApi', name: 'main-db', logicalKey: 'postgresApi:main-db', workflowCount: 1, workflows: [{ id: 'wf-3', name: 'Workflow 3' }], existingLogicalId: null, mappingStatus: 'unmapped' },
    ]);
  }),

  // Credential mapping validation endpoint
  http.post(`${API_BASE}/admin/credentials/mappings/validate`, () => {
    return HttpResponse.json({
      total: 5,
      valid: 4,
      invalid: 1,
      stale: 0,
      issues: [
        { mappingId: 'mapping-5', logicalName: 'awsApi:s3-bucket', environmentId: 'env-2', environmentName: 'Production', issue: 'credential_not_found', message: 'Physical credential not found in N8N' },
      ],
    });
  }),

  // Admin logical credentials CRUD
  http.get(`${API_BASE}/admin/credentials/logical`, () => {
    return HttpResponse.json([
      { id: 'logical-1', name: 'slackApi:prod-slack', required_type: 'slackApi', description: 'Slack credentials', tenant_id: 'tenant-1' },
      { id: 'logical-2', name: 'githubApi:gh-token', required_type: 'githubApi', description: 'GitHub credentials', tenant_id: 'tenant-1' },
    ]);
  }),

  http.post(`${API_BASE}/admin/credentials/logical`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: `logical-${Date.now()}`,
      ...body,
      created_at: new Date().toISOString(),
    }, { status: 201 });
  }),

  http.patch(`${API_BASE}/admin/credentials/logical/:id`, async ({ params, request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: params.id,
      ...body,
      updated_at: new Date().toISOString(),
    });
  }),

  http.delete(`${API_BASE}/admin/credentials/logical/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Admin credential mappings CRUD
  http.get(`${API_BASE}/admin/credentials/mappings`, () => {
    return HttpResponse.json([
      { id: 'mapping-1', logical_credential_id: 'logical-1', environment_id: 'env-1', physical_credential_id: 'n8n-cred-1', physical_name: 'Dev Slack', physical_type: 'slackApi', status: 'valid', provider: 'n8n' },
    ]);
  }),

  http.post(`${API_BASE}/admin/credentials/mappings`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: `mapping-${Date.now()}`,
      ...body,
      created_at: new Date().toISOString(),
    }, { status: 201 });
  }),

  http.patch(`${API_BASE}/admin/credentials/mappings/:id`, async ({ params, request }) => {
    const body = await request.json();
    return HttpResponse.json({
      id: params.id,
      ...body,
      updated_at: new Date().toISOString(),
    });
  }),

  http.delete(`${API_BASE}/admin/credentials/mappings/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // Credential preflight check endpoint
  http.post(`${API_BASE}/admin/credentials/preflight`, async ({ request }) => {
    return HttpResponse.json({
      valid: true,
      blocking_issues: [],
      warnings: [],
      resolved_mappings: [
        {
          logical_key: 'slackApi:notifications',
          source_physical_name: 'Dev Slack',
          target_physical_name: 'Prod Slack',
          target_physical_id: 'n8n-cred-prod-1',
        },
      ],
    });
  }),

  // Support endpoints
  http.post(`${API_BASE}/support/requests`, async () => {
    return HttpResponse.json({
      jsm_request_key: 'JSM-12345',
    });
  }),

  http.post(`${API_BASE}/support/upload-url`, async () => {
    return HttpResponse.json({
      upload_url: 'https://storage.example.com/upload?token=abc123',
      public_url: 'https://storage.example.com/files/screenshot.png',
    });
  }),

  // Admin support config
  http.get(`${API_BASE}/admin/support/config`, () => {
    return HttpResponse.json({
      n8n_webhook_url: 'https://n8n.example.com/webhook/support',
      jsm_portal_url: 'https://support.example.atlassian.net/servicedesk/customer/portal/1',
      bug_request_type_id: '10001',
      feature_request_type_id: '10002',
      task_request_type_id: '10003',
    });
  }),

  http.put(`${API_BASE}/admin/support/config`, async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json(body);
  }),

  http.post(`${API_BASE}/admin/support/test-n8n`, () => {
    return HttpResponse.json({ success: true, message: 'Connection successful' });
  }),
];

// Error handlers for testing error states
export const errorHandlers = {
  environments: {
    serverError: http.get(`${API_BASE}/environments`, () => {
      return new HttpResponse(JSON.stringify({ detail: 'Internal server error' }), {
        status: 500,
      });
    }),
    unauthorized: http.get(`${API_BASE}/environments`, () => {
      return new HttpResponse(JSON.stringify({ detail: 'Unauthorized' }), {
        status: 401,
      });
    }),
    forbidden: http.get(`${API_BASE}/environments`, () => {
      return new HttpResponse(JSON.stringify({ detail: 'Forbidden' }), {
        status: 403,
      });
    }),
  },
  workflows: {
    serverError: http.get(`${API_BASE}/workflows`, () => {
      return new HttpResponse(JSON.stringify({ detail: 'Internal server error' }), {
        status: 500,
      });
    }),
  },
  pipelines: {
    serverError: http.get(`${API_BASE}/pipelines`, () => {
      return new HttpResponse(JSON.stringify({ detail: 'Internal server error' }), {
        status: 500,
      });
    }),
  },
};
