// Tenant & Auth Types
export interface Tenant {
  id: string;
  name: string;
  email: string;
  subscriptionTier: 'free' | 'pro' | 'enterprise';
  createdAt: string;
  permissions: string[];
}

export interface User {
  id: string;
  tenantId: string;
  email: string;
  name: string;
  role: 'admin' | 'developer' | 'viewer';
  status: 'active' | 'pending' | 'inactive';
  createdAt: string;
}

// Environment Types
export type EnvironmentType = 'dev' | 'staging' | 'production';

export interface Environment {
  id: string;
  tenantId: string;
  name: string;
  type: EnvironmentType;
  baseUrl: string;
  apiKey?: string;
  isActive: boolean;
  lastConnected?: string;
  lastBackup?: string;
  workflowCount?: number;
  gitRepoUrl?: string;
  gitBranch?: string;
  gitPat?: string;
}

export interface EnvironmentConfig {
  environments: Environment[];
  gitConfig?: GitConfig;
}

export interface GitConfig {
  repoUrl: string;
  branch: string;
  pat?: string;
  lastSync?: string;
}

// Workflow Types
export interface Workflow {
  id: string;
  name: string;
  description?: string;
  active: boolean;
  nodes: WorkflowNode[];
  connections: Record<string, unknown>;
  settings: Record<string, unknown>;
  tags?: string[];
  createdAt: string;
  updatedAt: string;
  environment: EnvironmentType;
}

export interface WorkflowNode {
  id: string;
  name: string;
  type: string;
  position: [number, number];
  parameters: Record<string, unknown>;
  credentials?: Record<string, unknown>;
}

export interface WorkflowUploadPayload {
  tenantId: string;
  environment: EnvironmentType;
  files: File[];
  syncToGit?: boolean;
  createSnapshot?: boolean;
}

// Snapshot Types
export interface Snapshot {
  id: string;
  workflowId: string;
  workflowName: string;
  version: number;
  data: Workflow;
  trigger: 'manual' | 'auto-before-deploy' | 'auto-before-restore' | 'promotion';
  createdAt: string;
  createdBy: string;
}

export interface SnapshotComparison {
  snapshotA: Snapshot;
  snapshotB: Snapshot;
  differences: WorkflowDiff[];
}

export interface WorkflowDiff {
  path: string;
  type: 'added' | 'removed' | 'modified';
  oldValue?: unknown;
  newValue?: unknown;
}

// Deployment Types
export type DeploymentStatus = 'pending' | 'running' | 'success' | 'failed';

export interface Deployment {
  id: string;
  workflowId: string;
  workflowName: string;
  sourceEnvironment: EnvironmentType;
  targetEnvironment: EnvironmentType;
  status: DeploymentStatus;
  snapshotId?: string;
  errorMessage?: string;
  triggeredBy: string;
  startedAt: string;
  completedAt?: string;
}

export interface DeploymentPipeline {
  validate: boolean;
  createSnapshot: boolean;
  targetEnvironment: EnvironmentType;
}

// Observability Types
export interface WorkflowMetrics {
  workflowId: string;
  workflowName: string;
  totalExecutions: number;
  successfulExecutions: number;
  failedExecutions: number;
  errorRate: number;
  averageDuration: number;
  lastExecuted?: string;
}

export interface EnvironmentHealth {
  environment: EnvironmentType;
  status: 'healthy' | 'degraded' | 'down';
  latency: number;
  uptime: number;
  lastChecked: string;
  workflowsActive: number;
  workflowsTotal: number;
}

export interface ExecutionLog {
  id: string;
  workflowId: string;
  status: 'success' | 'error' | 'running';
  startedAt: string;
  finishedAt?: string;
  duration?: number;
  errorMessage?: string;
  nodeErrors?: NodeError[];
}

export interface NodeError {
  nodeId: string;
  nodeName: string;
  message: string;
  stack?: string;
}

// Execution Types (from N8N API)
export interface Execution {
  id: string;
  executionId: string;
  workflowId: string;
  workflowName?: string;
  status: 'success' | 'error' | 'waiting' | 'running' | 'new' | 'unknown';
  mode: 'manual' | 'trigger' | 'webhook' | 'retry' | string;
  startedAt: string;
  finishedAt?: string;
  executionTime?: number; // Duration in milliseconds
  data?: Record<string, unknown>;
  tenantId: string;
  environmentId: string;
  createdAt: string;
  updatedAt: string;
}

// Tag Types (from N8N API)
export interface Tag {
  id: string;
  tagId: string;
  name: string;
  tenantId: string;
  environmentId: string;
  createdAt?: string;
  updatedAt?: string;
  lastSyncedAt: string;
}

// N8N User Types (from N8N API)
export interface N8NUser {
  id: string;
  n8nUserId: string;
  email: string;
  firstName?: string;
  lastName?: string;
  isPending: boolean;
  role?: string;
  settings?: Record<string, unknown>;
  userData: Record<string, unknown>;
  tenantId: string;
  environmentId: string;
  environment?: {
    id: string;
    name: string;
    type: EnvironmentType;
  };
  createdAt?: string;
  updatedAt?: string;
  lastSyncedAt: string;
  isDeleted: boolean;
  cachedAt: string;
}

// Billing Types
export interface BillingStatus {
  tenantId: string;
  plan: 'free' | 'pro' | 'enterprise';
  status: 'active' | 'canceled' | 'past_due';
  renewalDate?: string;
  features: BillingFeatures;
}

export interface BillingFeatures {
  maxEnvironments: number;
  maxUsers: number;
  cicdEnabled: boolean;
  snapshotRetentionDays: number;
  advancedObservability: boolean;
}

export interface CheckoutSession {
  sessionId: string;
  url: string;
}

// Team Member Types
export interface TeamMember {
  id: string;
  tenantId: string;
  email: string;
  name: string;
  role: 'admin' | 'developer' | 'viewer';
  status: 'active' | 'pending' | 'inactive';
  createdAt: string;
  invitedAt?: string;
  lastActive?: string;
}

// Subscription Plan Types
export interface SubscriptionPlan {
  id: string;
  name: string;
  tier: 'free' | 'pro' | 'enterprise';
  status: 'active' | 'canceled' | 'past_due' | 'trialing';
  price?: number;
  billingCycle?: 'monthly' | 'yearly';
  currentPeriodStart?: string;
  currentPeriodEnd?: string;
  cancelAtPeriodEnd?: boolean;
  features: BillingFeatures;
}

// API Response Types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
