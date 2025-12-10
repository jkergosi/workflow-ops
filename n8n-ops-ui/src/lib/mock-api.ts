import type {
  Tenant,
  User,
  Environment,
  Workflow,
  Snapshot,
  Deployment,
  WorkflowMetrics,
  EnvironmentHealth,
  BillingStatus,
  ApiResponse,
} from '@/types';

// Mock data
const mockTenant: Tenant = {
  id: '1',
  name: 'Demo Company',
  email: 'demo@example.com',
  subscriptionTier: 'free',
  createdAt: new Date().toISOString(),
  permissions: ['read', 'write', 'deploy'],
};

const mockEnvironments: Environment[] = [
  {
    id: '1',
    tenantId: '1',
    name: 'Development',
    type: 'dev',
    baseUrl: 'http://localhost:5678',
    isActive: true,
    lastConnected: new Date().toISOString(),
    workflowCount: 12,
  },
  {
    id: '2',
    tenantId: '1',
    name: 'Staging',
    type: 'staging',
    baseUrl: 'https://staging.n8n.example.com',
    isActive: false,
    workflowCount: 8,
  },
  {
    id: '3',
    tenantId: '1',
    name: 'Production',
    type: 'production',
    baseUrl: 'https://n8n.example.com',
    isActive: true,
    lastConnected: new Date(Date.now() - 3600000).toISOString(),
    workflowCount: 8,
  },
];

const mockWorkflows: Workflow[] = [
  {
    id: 'wf1',
    name: 'Customer Onboarding',
    description: 'Automated customer onboarding workflow',
    active: true,
    nodes: [],
    connections: {},
    settings: {},
    tags: ['customer', 'onboarding'],
    createdAt: new Date(Date.now() - 86400000 * 7).toISOString(),
    updatedAt: new Date(Date.now() - 86400000).toISOString(),
    environment: 'dev',
  },
  {
    id: 'wf2',
    name: 'Invoice Processing',
    description: 'Process and send invoices',
    active: true,
    nodes: [],
    connections: {},
    settings: {},
    tags: ['billing', 'automation'],
    createdAt: new Date(Date.now() - 86400000 * 14).toISOString(),
    updatedAt: new Date(Date.now() - 86400000 * 2).toISOString(),
    environment: 'dev',
  },
  {
    id: 'wf3',
    name: 'Email Campaign Manager',
    description: 'Manage and send marketing email campaigns',
    active: false,
    nodes: [],
    connections: {},
    settings: {},
    tags: ['marketing', 'email', 'automation'],
    createdAt: new Date(Date.now() - 86400000 * 21).toISOString(),
    updatedAt: new Date(Date.now() - 86400000 * 5).toISOString(),
    environment: 'dev',
  },
  {
    id: 'wf4',
    name: 'Slack Notifications',
    description: 'Send notifications to Slack channels',
    active: true,
    nodes: [],
    connections: {},
    settings: {},
    tags: ['notifications', 'slack'],
    createdAt: new Date(Date.now() - 86400000 * 10).toISOString(),
    updatedAt: new Date(Date.now() - 86400000 * 3).toISOString(),
    environment: 'dev',
  },
  {
    id: 'wf5',
    name: 'Data Sync Pipeline',
    description: 'Synchronize data between systems',
    active: true,
    nodes: [],
    connections: {},
    settings: {},
    tags: ['data', 'integration', 'automation'],
    createdAt: new Date(Date.now() - 86400000 * 30).toISOString(),
    updatedAt: new Date(Date.now() - 86400000 * 7).toISOString(),
    environment: 'dev',
  },
  {
    id: 'wf6',
    name: 'Lead Scoring',
    description: 'Calculate and update lead scores',
    active: false,
    nodes: [],
    connections: {},
    settings: {},
    tags: ['sales', 'customer'],
    createdAt: new Date(Date.now() - 86400000 * 45).toISOString(),
    updatedAt: new Date(Date.now() - 86400000 * 10).toISOString(),
    environment: 'dev',
  },
  {
    id: 'wf7',
    name: 'Backup Automation',
    description: 'Automated database backups',
    active: true,
    nodes: [],
    connections: {},
    settings: {},
    tags: ['backup', 'automation', 'data'],
    createdAt: new Date(Date.now() - 86400000 * 60).toISOString(),
    updatedAt: new Date(Date.now() - 86400000 * 15).toISOString(),
    environment: 'dev',
  },
  {
    id: 'wf8',
    name: 'Payment Gateway Integration',
    description: 'Process payments through multiple gateways',
    active: true,
    nodes: [],
    connections: {},
    settings: {},
    tags: ['billing', 'integration'],
    createdAt: new Date(Date.now() - 86400000 * 25).toISOString(),
    updatedAt: new Date(Date.now() - 86400000 * 4).toISOString(),
    environment: 'dev',
  },
];

const mockSnapshots: Snapshot[] = [
  {
    id: 'snap1',
    workflowId: 'wf1',
    workflowName: 'Customer Onboarding',
    version: 3,
    data: mockWorkflows[0],
    trigger: 'manual',
    createdAt: new Date(Date.now() - 86400000 * 3).toISOString(),
    createdBy: 'user@example.com',
  },
  {
    id: 'snap2',
    workflowId: 'wf1',
    workflowName: 'Customer Onboarding',
    version: 2,
    data: mockWorkflows[0],
    trigger: 'auto-before-deploy',
    createdAt: new Date(Date.now() - 86400000 * 5).toISOString(),
    createdBy: 'user@example.com',
  },
];

const mockDeployments: Deployment[] = [
  {
    id: 'dep1',
    workflowId: 'wf1',
    workflowName: 'Customer Onboarding',
    sourceEnvironment: 'dev',
    targetEnvironment: 'staging',
    status: 'success',
    snapshotId: 'snap1',
    triggeredBy: 'user@example.com',
    startedAt: new Date(Date.now() - 3600000).toISOString(),
    completedAt: new Date(Date.now() - 3500000).toISOString(),
  },
  {
    id: 'dep2',
    workflowId: 'wf2',
    workflowName: 'Invoice Processing',
    sourceEnvironment: 'dev',
    targetEnvironment: 'staging',
    status: 'running',
    triggeredBy: 'user@example.com',
    startedAt: new Date().toISOString(),
  },
];

const mockMetrics: WorkflowMetrics[] = [
  {
    workflowId: 'wf1',
    workflowName: 'Customer Onboarding',
    totalExecutions: 245,
    successfulExecutions: 237,
    failedExecutions: 8,
    errorRate: 3.27,
    averageDuration: 1250,
    lastExecuted: new Date(Date.now() - 60000).toISOString(),
  },
  {
    workflowId: 'wf2',
    workflowName: 'Invoice Processing',
    totalExecutions: 512,
    successfulExecutions: 508,
    failedExecutions: 4,
    errorRate: 0.78,
    averageDuration: 890,
    lastExecuted: new Date(Date.now() - 300000).toISOString(),
  },
];

const mockEnvHealth: EnvironmentHealth[] = [
  {
    environment: 'dev',
    status: 'healthy',
    latency: 45,
    uptime: 99.8,
    lastChecked: new Date().toISOString(),
    workflowsActive: 10,
    workflowsTotal: 12,
  },
  {
    environment: 'production',
    status: 'healthy',
    latency: 32,
    uptime: 99.95,
    lastChecked: new Date().toISOString(),
    workflowsActive: 8,
    workflowsTotal: 8,
  },
];

const mockUsers: User[] = [
  {
    id: '1',
    tenantId: '1',
    email: 'admin@example.com',
    name: 'Admin User',
    role: 'admin',
    status: 'active',
    createdAt: new Date(Date.now() - 86400000 * 30).toISOString(),
  },
  {
    id: '2',
    tenantId: '1',
    email: 'dev@example.com',
    name: 'Developer User',
    role: 'developer',
    status: 'active',
    createdAt: new Date(Date.now() - 86400000 * 15).toISOString(),
  },
];

const mockBilling: BillingStatus = {
  tenantId: '1',
  plan: 'free',
  status: 'active',
  features: {
    maxEnvironments: 1,
    maxUsers: 2,
    cicdEnabled: false,
    snapshotRetentionDays: 7,
    advancedObservability: false,
  },
};

// Mock API functions
export const mockApi = {
  // Tenant
  getTenant: async (): Promise<ApiResponse<Tenant>> => {
    await delay(300);
    return { success: true, data: mockTenant };
  },

  // Environments
  getEnvironments: async (): Promise<ApiResponse<Environment[]>> => {
    await delay(300);
    return { success: true, data: mockEnvironments };
  },

  testEnvironment: async (_envId: string): Promise<ApiResponse<boolean>> => {
    await delay(1000);
    return { success: true, data: true };
  },

  // Workflows
  getWorkflows: async (_env: string): Promise<ApiResponse<Workflow[]>> => {
    await delay(400);
    return { success: true, data: mockWorkflows };
  },

  getWorkflow: async (workflowId: string): Promise<ApiResponse<Workflow>> => {
    await delay(300);
    const workflow = mockWorkflows.find((w) => w.id === workflowId);
    if (!workflow) {
      return { success: false, error: 'Workflow not found' };
    }
    return { success: true, data: workflow };
  },

  // Snapshots
  getSnapshots: async (workflowId: string): Promise<ApiResponse<Snapshot[]>> => {
    await delay(300);
    return {
      success: true,
      data: mockSnapshots.filter((s) => s.workflowId === workflowId),
    };
  },

  createSnapshot: async (workflowId: string): Promise<ApiResponse<Snapshot>> => {
    await delay(500);
    const newSnapshot: Snapshot = {
      id: `snap${Date.now()}`,
      workflowId,
      workflowName: mockWorkflows.find((w) => w.id === workflowId)?.name || 'Unknown',
      version: mockSnapshots.length + 1,
      data: mockWorkflows[0],
      trigger: 'manual',
      createdAt: new Date().toISOString(),
      createdBy: 'user@example.com',
    };
    return { success: true, data: newSnapshot };
  },

  // Deployments
  getDeployments: async (): Promise<ApiResponse<Deployment[]>> => {
    await delay(300);
    return { success: true, data: mockDeployments };
  },

  deployWorkflow: async (
    workflowId: string,
    targetEnv: string
  ): Promise<ApiResponse<Deployment>> => {
    await delay(2000);
    const newDeployment: Deployment = {
      id: `dep${Date.now()}`,
      workflowId,
      workflowName: mockWorkflows.find((w) => w.id === workflowId)?.name || 'Unknown',
      sourceEnvironment: 'dev',
      targetEnvironment: targetEnv as any,
      status: 'success',
      triggeredBy: 'user@example.com',
      startedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
    };
    return { success: true, data: newDeployment };
  },

  // Observability
  getWorkflowMetrics: async (): Promise<ApiResponse<WorkflowMetrics[]>> => {
    await delay(400);
    return { success: true, data: mockMetrics };
  },

  getEnvironmentHealth: async (): Promise<ApiResponse<EnvironmentHealth[]>> => {
    await delay(300);
    return { success: true, data: mockEnvHealth };
  },

  // Team
  getTeamMembers: async (): Promise<ApiResponse<User[]>> => {
    await delay(300);
    return { success: true, data: mockUsers };
  },

  inviteUser: async (email: string, role: string): Promise<ApiResponse<User>> => {
    await delay(800);
    const newUser: User = {
      id: `${Date.now()}`,
      tenantId: '1',
      email,
      name: email.split('@')[0],
      role: role as any,
      status: 'pending',
      createdAt: new Date().toISOString(),
    };
    return { success: true, data: newUser };
  },

  // Billing
  getBillingStatus: async (): Promise<ApiResponse<BillingStatus>> => {
    await delay(300);
    return { success: true, data: mockBilling };
  },
};

// Utility function to simulate API delay
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
