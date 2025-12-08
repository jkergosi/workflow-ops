// Environment types
export type EnvironmentType = 'dev' | 'staging' | 'production';

export interface Environment {
  id: string;
  tenantId: string;
  name: string;
  type: EnvironmentType;
  baseUrl: string;
  apiKey?: string;
  n8nEncryptionKey?: string;
  isActive: boolean;
  lastConnected?: string;
  lastBackup?: string;
  workflowCount: number;
  gitRepoUrl?: string;
  gitBranch?: string;
  gitPat?: string;
  createdAt: string;
  updatedAt: string;
}

// Workflow types
export interface Workflow {
  id: string;
  name: string;
  description?: string;
  active: boolean;
  nodes: any[];
  connections: Record<string, any>;
  settings: Record<string, any>;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  environment: EnvironmentType;
}

// Snapshot types
export interface Snapshot {
  id: string;
  workflowId: string;
  workflowName: string;
  version: number;
  data: Workflow;
  trigger: string;
  createdAt: string;
  createdBy: string;
}

// Deployment types
export interface Deployment {
  id: string;
  workflowId: string;
  workflowName: string;
  sourceEnvironment: EnvironmentType;
  targetEnvironment: EnvironmentType;
  status: 'pending' | 'running' | 'success' | 'failed';
  snapshotId?: string;
  triggeredBy: string;
  startedAt: string;
  completedAt?: string;
  errorMessage?: string;
}

// Execution types
export interface Execution {
  id: string;
  workflowId: string;
  workflowName: string;
  environmentId: string;
  status: 'waiting' | 'running' | 'success' | 'error';
  startedAt: string;
  finishedAt?: string;
  data?: any;
}

// Team types
export interface TeamMember {
  id: string;
  tenantId: string;
  email: string;
  name: string;
  role: 'admin' | 'developer' | 'viewer';
  status: 'active' | 'pending' | 'inactive';
  createdAt: string;
}

// Billing types
export interface SubscriptionPlan {
  id: string;
  name: string;
  tier: 'free' | 'pro' | 'enterprise';
  status: 'active' | 'canceled' | 'past_due';
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
}

// Auth types
export interface AuthStatus {
  authenticated: boolean;
  user?: {
    id: string;
    email: string;
    name?: string;
    role: string;
    tenantId: string;
  };
  tenant?: {
    id: string;
    name: string;
    subscriptionTier: string;
  };
  requiresOnboarding: boolean;
}

export interface OnboardingResponse {
  success: boolean;
  user: {
    id: string;
    email: string;
    name?: string;
    role: string;
    tenantId: string;
  };
  tenant: {
    id: string;
    name: string;
    subscriptionTier: string;
  };
}

export interface UserResponse {
  id: string;
  email: string;
  name?: string;
  role: string;
  tenantId: string;
  tenant: {
    id: string;
    name: string;
    subscriptionTier: string;
  };
}

// Drift analysis types
export interface DriftAnalysisResult {
  hasDrift: boolean;
  differences: Array<{
    path: string;
    type: 'added' | 'removed' | 'changed';
    oldValue?: any;
    newValue?: any;
  }>;
  lastSyncedAt?: string;
}

// Legacy types for mock API compatibility
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
  status: 'healthy' | 'degraded' | 'offline';
  latency: number;
  uptime: number;
  lastChecked: string;
  workflowsActive: number;
  workflowsTotal: number;
}

export interface BillingStatus {
  tenantId: string;
  plan: 'free' | 'pro' | 'enterprise';
  status: 'active' | 'canceled' | 'past_due';
  features: {
    maxEnvironments: number;
    maxUsers: number;
    cicdEnabled: boolean;
    snapshotRetentionDays: number;
    advancedObservability: boolean;
  };
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}
