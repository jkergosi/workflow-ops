// Environment type is now optional and free-form (not an enum)
// Kept for backward compatibility but can be any string or undefined
export type EnvironmentType = string | undefined;

export interface Environment {
  id: string;
  tenantId: string;
  name: string;
  type?: string;  // Optional metadata for display/sorting only (e.g., 'dev', 'staging', 'production', 'qa', etc.)
  baseUrl: string;
  apiKey?: string;
  n8nEncryptionKey?: string;
  isActive: boolean;
  allowUpload: boolean;  // Feature flag: true if workflows can be uploaded from this environment
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
export interface WorkflowNode {
  id: string;
  name: string;
  type: string;
  typeVersion?: number;
  position: [number, number] | { x: number; y: number };
  parameters?: Record<string, any>;
  credentials?: Record<string, any>;
  notes?: string;
  notesInFlow?: boolean;
  disabled?: boolean;
}

export type SyncStatus = 'in_sync' | 'local_changes' | 'update_available' | 'conflict';

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  active: boolean;
  nodes: WorkflowNode[];
  connections: Record<string, any>;
  settings: Record<string, any>;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  environment: EnvironmentType;
  analysis?: import('@/lib/workflow-analysis').WorkflowAnalysis;
  lastSyncedAt?: string;
  isArchived?: boolean;
  syncStatus?: SyncStatus;
}

// Snapshot types (Git-backed environment states)
export type SnapshotType = 'auto_backup' | 'pre_promotion' | 'post_promotion' | 'manual_backup';

export interface Snapshot {
  id: string;
  tenantId: string;
  environmentId: string;
  gitCommitSha: string;
  type: SnapshotType;
  createdAt: string;
  createdByUserId?: string;
  relatedDeploymentId?: string;
  metadataJson?: {
    reason?: string;
    workflowsCount?: number;
    [key: string]: any;
  };
}

// Deployment types (Promotion records)
export type DeploymentStatus = 'pending' | 'running' | 'success' | 'failed' | 'canceled';
export type WorkflowChangeType = 'created' | 'updated' | 'deleted' | 'skipped' | 'unchanged';
export type WorkflowStatus = 'success' | 'failed' | 'skipped';

export interface DeploymentWorkflow {
  id: string;
  deploymentId: string;
  workflowId: string;
  workflowNameAtTime: string;
  changeType: WorkflowChangeType;
  status: WorkflowStatus;
  errorMessage?: string;
  createdAt: string;
}

export interface Deployment {
  id: string;
  tenantId: string;
  pipelineId?: string;
  sourceEnvironmentId: string;
  targetEnvironmentId: string;
  status: DeploymentStatus;
  triggeredByUserId: string;
  approvedByUserId?: string;
  startedAt: string;
  finishedAt?: string;
  preSnapshotId?: string;
  postSnapshotId?: string;
  summaryJson?: {
    total: number;
    created: number;
    updated: number;
    deleted: number;
    failed: number;
    skipped?: number;
  };
  createdAt: string;
  updatedAt: string;
}

export interface DeploymentDetail extends Deployment {
  workflows: DeploymentWorkflow[];
  preSnapshot?: Snapshot;
  postSnapshot?: Snapshot;
  pipelineName?: string;
  sourceEnvironmentName?: string;
  targetEnvironmentName?: string;
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
export interface DriftDifference {
  path: string;
  type: 'added' | 'removed' | 'modified';
  gitValue?: any;
  runtimeValue?: any;
}

export interface DriftSummary {
  nodesAdded: number;
  nodesRemoved: number;
  nodesModified: number;
  connectionsChanged: boolean;
  settingsChanged: boolean;
}

export interface DriftAnalysisResult {
  hasDrift: boolean;
  gitVersion?: any;
  runtimeVersion?: any;
  lastCommitSha?: string;
  lastCommitDate?: string;
  differences: DriftDifference[];
  summary: DriftSummary;
  gitConfigured?: boolean;
  notInGit?: boolean;
  message?: string;
}

export interface WorkflowDriftStatus {
  id: string;
  name: string;
  active: boolean;
  hasDrift: boolean;
  notInGit: boolean;
  lastCommitSha?: string;
  lastCommitDate?: string;
  summary?: DriftSummary;
  differenceCount?: number;
}

export interface EnvironmentDriftAnalysis {
  gitConfigured: boolean;
  message?: string;
  workflows: WorkflowDriftStatus[];
  summary: {
    total: number;
    withDrift: number;
    notInGit: number;
    inSync: number;
  };
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

// Pipeline types
export type RiskLevel = 'Low' | 'Medium' | 'High';
export type ApprovalType = '1 of N' | 'All';

export interface PipelineStageGates {
  requireCleanDrift: boolean;
  runPreFlightValidation: boolean;
  credentialsExistInTarget: boolean;
  nodesSupportedInTarget: boolean;
  webhooksAvailable: boolean;
  targetEnvironmentHealthy: boolean;
  maxAllowedRiskLevel: RiskLevel;
}

export interface PipelineStageApprovals {
  requireApproval: boolean;
  approverRole?: string;
  approverGroup?: string;
  requiredApprovals?: ApprovalType;
}

export interface PipelineStageSchedule {
  restrictPromotionTimes: boolean;
  allowedDays?: string[];
  startTime?: string;
  endTime?: string;
}

export interface PipelineStagePolicyFlags {
  allowPlaceholderCredentials: boolean;
  allowOverwritingHotfixes: boolean;
  allowForcePromotionOnConflicts: boolean;
}

export interface PipelineStage {
  sourceEnvironmentId: string;
  targetEnvironmentId: string;
  gates: PipelineStageGates;
  approvals: PipelineStageApprovals;
  schedule?: PipelineStageSchedule;
  policyFlags: PipelineStagePolicyFlags;
}

export interface Pipeline {
  id: string;
  tenantId: string;
  name: string;
  description?: string;
  isActive: boolean;
  environmentIds: string[];
  stages: PipelineStage[];
  lastModifiedBy?: string;
  lastModifiedAt: string;
  createdAt: string;
  updatedAt: string;
}

// Promotion types
export type PromotionStatus = 'pending' | 'pending_approval' | 'approved' | 'rejected' | 'running' | 'completed' | 'failed' | 'cancelled';
export type WorkflowChangeType = 'new' | 'changed' | 'staging_hotfix' | 'conflict' | 'unchanged';

export interface WorkflowSelection {
  workflowId: string;
  workflowName: string;
  changeType: WorkflowChangeType;
  enabledInSource: boolean;
  enabledInTarget?: boolean;
  selected: boolean;
  requiresOverwrite?: boolean;
}

export interface GateResult {
  requireCleanDrift: boolean;
  driftDetected: boolean;
  driftResolved: boolean;
  runPreFlightValidation: boolean;
  credentialsExist: boolean;
  nodesSupported: boolean;
  webhooksAvailable: boolean;
  targetEnvironmentHealthy: boolean;
  riskLevelAllowed: boolean;
  errors: string[];
  warnings: string[];
}

export interface Promotion {
  id: string;
  tenantId: string;
  pipelineId: string;
  pipelineName: string;
  sourceEnvironmentId: string;
  sourceEnvironmentName: string;
  targetEnvironmentId: string;
  targetEnvironmentName: string;
  status: PromotionStatus;
  sourceSnapshotId?: string;
  targetPreSnapshotId?: string;
  targetPostSnapshotId?: string;
  workflowSelections: WorkflowSelection[];
  gateResults?: GateResult;
  createdBy: string;
  approvedBy?: string;
  approvedAt?: string;
  rejectionReason?: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

// Observability types
export type TimeRange = '1h' | '6h' | '24h' | '7d' | '30d';
export type EnvironmentStatus = 'healthy' | 'degraded' | 'unreachable';
export type DriftState = 'in_sync' | 'drift' | 'unknown';

export interface KPIMetrics {
  totalExecutions: number;
  successCount: number;
  failureCount: number;
  successRate: number;
  avgDurationMs: number;
  p95DurationMs?: number;
  deltaExecutions?: number;
  deltaSuccessRate?: number;
}

export interface WorkflowPerformance {
  workflowId: string;
  workflowName: string;
  executionCount: number;
  successCount: number;
  failureCount: number;
  errorRate: number;
  avgDurationMs: number;
  p95DurationMs?: number;
}

export interface EnvironmentHealthData {
  environmentId: string;
  environmentName: string;
  environmentType?: string;
  status: EnvironmentStatus;
  latencyMs?: number;
  uptimePercent: number;
  activeWorkflows: number;
  totalWorkflows: number;
  lastDeploymentAt?: string;
  lastSnapshotAt?: string;
  driftState: DriftState;
  lastCheckedAt?: string;
}

export interface RecentDeployment {
  id: string;
  pipelineName?: string;
  sourceEnvironmentName: string;
  targetEnvironmentName: string;
  status: string;
  startedAt: string;
  finishedAt?: string;
}

export interface PromotionSyncStats {
  promotionsTotal: number;
  promotionsSuccess: number;
  promotionsFailed: number;
  promotionsBlocked: number;
  snapshotsCreated: number;
  snapshotsRestored: number;
  driftCount: number;
  recentDeployments: RecentDeployment[];
}

export interface ObservabilityOverview {
  kpiMetrics: KPIMetrics;
  workflowPerformance: WorkflowPerformance[];
  environmentHealth: EnvironmentHealthData[];
  promotionSyncStats?: PromotionSyncStats;
}

export interface HealthCheckResponse {
  id: string;
  tenantId: string;
  environmentId: string;
  status: EnvironmentStatus;
  latencyMs?: number;
  checkedAt: string;
  errorMessage?: string;
}

// Notification/Alert types
export type ChannelType = 'slack' | 'email' | 'webhook';
export type NotificationStatusType = 'pending' | 'sent' | 'failed' | 'skipped';

export interface SlackConfig {
  webhook_url: string;
  channel?: string;
  username?: string;
  icon_emoji?: string;
}

export interface EmailConfig {
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password: string;
  from_address: string;
  to_addresses: string[];
  use_tls: boolean;
}

export interface WebhookConfig {
  url: string;
  method: string;
  headers?: Record<string, string>;
  auth_type?: 'none' | 'basic' | 'bearer';
  auth_value?: string;
}

export type ChannelConfig = SlackConfig | EmailConfig | WebhookConfig;

export interface NotificationChannel {
  id: string;
  tenantId: string;
  name: string;
  type: ChannelType;
  configJson: ChannelConfig;
  isEnabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface NotificationRule {
  id: string;
  tenantId: string;
  eventType: string;
  channelIds: string[];
  isEnabled: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface AlertEvent {
  id: string;
  tenantId: string;
  eventType: string;
  environmentId?: string;
  timestamp: string;
  metadataJson?: Record<string, any>;
  notificationStatus?: NotificationStatusType;
  channelsNotified?: string[];
}

export interface EventCatalogItem {
  eventType: string;
  displayName: string;
  description: string;
  category: string;
}

// Entitlements types (Phase 1)
export interface EntitlementsFeature {
  name: string;
  type: 'flag' | 'limit';
  value: boolean | number;
}

export interface Entitlements {
  plan_id: string;
  plan_name: string;
  entitlements_version: number;
  features: Record<string, boolean | number>;
}