// Environment type is now optional and free-form (not an enum)
// Kept for backward compatibility but can be any string or undefined
export type EnvironmentType = string | undefined;

export interface EnvironmentTypeConfig {
  id: string;
  tenantId: string;
  key: string;
  label: string;
  sortOrder: number;
  isActive: boolean;
  createdAt?: string;
  updatedAt?: string;
}

// Provider type for multi-provider support (n8n, Make.com, etc.)
export type Provider = "n8n" | "make";

// Provider configuration for UI settings
export interface ProviderConfig {
  id: Provider;
  displayName: string;
}

// Provider as purchasable product
export interface ProviderInfo {
  id: string;
  name: string;
  display_name: string;
  icon?: string;
  description?: string;
  is_active: boolean;
  created_at?: string;
}

export interface ProviderPlan {
  id: string;
  provider_id: string;
  name: string;
  display_name: string;
  description?: string;
  price_monthly: number;
  price_yearly: number;
  stripe_price_id_monthly?: string;
  stripe_price_id_yearly?: string;
  features: Record<string, boolean | string | number>;
  max_environments: number;
  max_workflows: number;
  is_active: boolean;
  sort_order: number;
  created_at?: string;
}

export interface ProviderWithPlans extends ProviderInfo {
  plans: ProviderPlan[];
}

export interface TenantProviderSubscription {
  id: string;
  tenant_id: string;
  provider_id: string;
  provider: ProviderInfo;
  plan_id: string;
  plan: ProviderPlan;
  stripe_subscription_id?: string;
  status: 'active' | 'canceled' | 'past_due' | 'trialing';
  billing_cycle: 'monthly' | 'yearly';
  current_period_start?: string;
  current_period_end?: string;
  cancel_at_period_end: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ProviderCheckoutRequest {
  provider_id: string;
  plan_id: string;
  billing_cycle: 'monthly' | 'yearly';
  success_url: string;
  cancel_url: string;
}

export interface ProviderCheckoutResponse {
  checkout_url: string;
  session_id: string;
}

export interface Environment {
  id: string;
  tenantId: string;
  provider: Provider;  // Provider type (n8n, make)
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
  provider: Provider;  // Provider type (n8n, make)
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
  provider: Provider;  // Provider type (n8n, make)
  environmentId: string;
  gitCommitSha: string;
  type: SnapshotType;
  createdAt: string;
  createdByUserId?: string;
  relatedDeploymentId?: string;
  metadataJson?: {
    reason?: string;
    workflowsCount?: number;
    notes?: string;
    [key: string]: any;
  };
}

// Snapshot comparison types
export type WorkflowDiffStatus = 'added' | 'removed' | 'modified' | 'unchanged';

export interface WorkflowDiff {
  workflowId: string;
  workflowName: string;
  status: WorkflowDiffStatus;
  snapshot1Version?: any;
  snapshot2Version?: any;
  changes?: string[];
}

export interface SnapshotComparison {
  snapshot1: Snapshot;
  snapshot2: Snapshot;
  workflows: WorkflowDiff[];
  summary: {
    added: number;
    removed: number;
    modified: number;
    unchanged: number;
  };
}

// Workflow diff types for deployment preview
export type WorkflowDiffType = 'added' | 'removed' | 'modified';

export interface WorkflowDifference {
  path: string;
  sourceValue: any;
  targetValue: any;
  type: WorkflowDiffType;
}

export interface WorkflowDiffSummary {
  nodesAdded: number;
  nodesRemoved: number;
  nodesModified: number;
  connectionsChanged: boolean;
  settingsChanged: boolean;
}

export interface WorkflowDiffResult {
  workflowId: string;
  workflowName: string;
  sourceVersion: any; // Full workflow JSON from source
  targetVersion: any | null; // Full workflow JSON from target (null if new workflow)
  differences: WorkflowDifference[];
  summary: WorkflowDiffSummary;
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
  provider: Provider;  // Provider type (n8n, make)
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
    processed?: number;
    current_workflow?: string;
  };
  progressCurrent?: number;
  progressTotal?: number;
  currentWorkflowName?: string;
  createdAt: string;
  updatedAt: string;
  deletedAt?: string;
  deletedByUserId?: string;
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
  provider: Provider;  // Provider type (n8n, make)
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
  subscriptionPlan: 'free' | 'pro' | 'agency' | 'enterprise';
  status: 'active' | 'trial' | 'suspended' | 'cancelled' | 'archived' | 'pending';
  workflowCount: number;
  environmentCount: number;
  userCount: number;
  primaryContactName?: string;
  lastActiveAt?: string;
  scheduledDeletionAt?: string;
  stripeCustomerId?: string;
  createdAt: string;
  updatedAt: string;
  // Legacy field for backward compatibility
  subscriptionTier?: 'free' | 'pro' | 'enterprise';
  permissions?: string[];
}

export interface TenantNote {
  id: string;
  tenantId: string;
  authorId?: string;
  authorEmail?: string;
  authorName?: string;
  content: string;
  createdAt: string;
  updatedAt: string;
}

export interface TenantUsageMetric {
  current: number;
  limit: number;
  percentage: number;
  period?: string;
}

export interface TenantUsage {
  tenantId: string;
  plan: string;
  metrics: {
    workflows: TenantUsageMetric;
    environments: TenantUsageMetric;
    users: TenantUsageMetric;
    executions: TenantUsageMetric;
  };
}

export interface AuditLog {
  id: string;
  timestamp: string;
  actorId?: string;
  actorEmail?: string;
  actorName?: string;
  tenantId?: string;
  tenantName?: string;
  action: string;
  actionType: string;
  resourceType?: string;
  resourceId?: string;
  resourceName?: string;
  oldValue?: Record<string, any>;
  newValue?: Record<string, any>;
  reason?: string;
  ipAddress?: string;
  metadata?: Record<string, any>;
}

export interface BillingMetrics {
  mrr: number;
  arr: number;
  activeSubscriptions: number;
  activeTrials: number;
  newSubscriptions30d: number;
  churnedSubscriptions30d: number;
  payingTenants: number;
  freeTenants: number;
  totalSubscriptions?: number;
  trialSubscriptions?: number;
  churnRate?: number;
  avgRevenuePerUser?: number;
  mrrGrowth?: number;
}

export interface PlanDistributionItem {
  planName: string;
  plan?: string;
  count: number;
  percentage: number;
  revenue: number;
}

export interface RecentCharge {
  id: string;
  tenantId?: string;
  tenantName?: string;
  type?: string;
  amount: number;
  currency: string;
  status: string;
  planName?: string;
  createdAt: string;
}

export interface FailedPayment {
  id: string;
  tenantId?: string;
  tenantName?: string;
  amount: number;
  currency: string;
  failureReason?: string;
  retryDate?: string;
  createdAt: string;
}

export interface DunningTenant {
  tenantId: string;
  tenantName: string;
  planName: string;
  status: string;
  lastPaymentAttempt?: string;
  dueDate?: string;
  retryCount?: number;
  amountDue: number;
  failedAttempts: number;
}

export interface TenantSubscription {
  tenantId: string;
  tenantName: string;
  planName: string;
  status: string;
  billingCycle: string;
  currentPeriodStart?: string;
  currentPeriodEnd?: string;
  trialEnd?: string;
  cancelAtPeriodEnd: boolean;
  stripeCustomerId?: string;
  stripeSubscriptionId?: string;
}

export interface TenantInvoice {
  id: string;
  amount: number;
  currency: string;
  status: string;
  createdAt: string;
  invoicePdf?: string;
  hostedInvoiceUrl?: string;
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
  provider: Provider;  // Provider type (n8n, make)
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
// Note: WorkflowChangeType is defined above with Deployment types

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
  provider: Provider;  // Provider type (n8n, make)
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
export type SystemHealthStatus = 'healthy' | 'degraded' | 'critical';

// Section 1: System Status
export interface SystemStatusInsight {
  message: string;
  severity: 'info' | 'warning' | 'critical';
  linkType?: 'workflow' | 'deployment' | 'error' | 'environment';
  linkId?: string;
}

export interface SystemStatus {
  status: SystemHealthStatus;
  insights: SystemStatusInsight[];
  failureDeltaPercent?: number;
  failingWorkflowsCount: number;
  lastFailedDeployment?: string;
}

// Section 2: KPI with Sparklines
export interface SparklineDataPoint {
  timestamp: string;
  value: number;
}

export interface KPIMetrics {
  totalExecutions: number;
  successCount: number;
  failureCount: number;
  successRate: number;
  avgDurationMs: number;
  p95DurationMs?: number;
  deltaExecutions?: number;
  deltaSuccessRate?: number;
  // Sparkline data
  executionsSparkline?: SparklineDataPoint[];
  successRateSparkline?: SparklineDataPoint[];
  durationSparkline?: SparklineDataPoint[];
  failuresSparkline?: SparklineDataPoint[];
}

// Section 3: Error Intelligence
export interface ErrorGroup {
  errorType: string;
  count: number;
  firstSeen: string;
  lastSeen: string;
  affectedWorkflowCount: number;
  affectedWorkflowIds: string[];
  sampleMessage?: string;
  isClassified?: boolean; // False if error type is a fallback, UI should show sample_message inline
}

export interface ErrorIntelligence {
  errors: ErrorGroup[];
  totalErrorCount: number;
}

// Section 4: Workflow Performance with Risk
export interface WorkflowPerformance {
  workflowId: string;
  workflowName: string;
  executionCount: number;
  successCount: number;
  failureCount: number;
  errorRate: number;
  avgDurationMs: number;
  p95DurationMs?: number;
  // Risk fields
  riskScore?: number;
  lastFailureAt?: string;
  primaryErrorType?: string;
}

// Section 5: Environment Health with Credential Health
export interface CredentialHealth {
  totalCount: number;
  validCount: number;
  invalidCount: number;
  unknownCount: number;
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
  lastDeploymentStatus?: string;
  lastSnapshotAt?: string;
  driftState: DriftState;
  driftWorkflowCount?: number;
  lastCheckedAt?: string;
  credentialHealth?: CredentialHealth;
  apiReachable?: boolean;
}

// Section 6: Deployments with Impact
export interface ImpactedWorkflow {
  workflowId: string;
  workflowName: string;
  changeType: string;
}

export interface RecentDeployment {
  id: string;
  pipelineName?: string;
  sourceEnvironmentName: string;
  targetEnvironmentName: string;
  status: string;
  startedAt: string;
  finishedAt?: string;
  impactedWorkflows?: ImpactedWorkflow[];
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

// Complete Overview
export interface ObservabilityOverview {
  systemStatus?: SystemStatus;
  kpiMetrics: KPIMetrics;
  errorIntelligence?: ErrorIntelligence;
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

// Admin Entitlements types (Phase 4)
export type FeatureType = 'flag' | 'limit';
export type FeatureStatus = 'active' | 'deprecated' | 'hidden';

export interface AdminFeature {
  id: string;
  key: string;
  displayName: string;
  description?: string;
  type: FeatureType;
  defaultValue: Record<string, any>;
  status: FeatureStatus;
  createdAt: string;
  updatedAt: string;
}

export interface AdminPlan {
  id: string;
  name: string;
  displayName: string;
  description?: string;
  sortOrder: number;
  isActive: boolean;
  tenantCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface FeatureMatrixEntry {
  featureId: string;
  featureKey: string;
  featureDisplayName: string;
  featureType: FeatureType;
  description?: string;
  status: FeatureStatus;
  planValues: Record<string, boolean | number>;
}

export interface FeatureMatrix {
  features: FeatureMatrixEntry[];
  plans: AdminPlan[];
  totalFeatures: number;
}

export interface TenantFeatureOverride {
  id: string;
  tenantId: string;
  featureId: string;
  featureKey: string;
  featureDisplayName: string;
  value: Record<string, any>;
  reason?: string;
  createdBy?: string;
  createdByEmail?: string;
  expiresAt?: string;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface FeatureConfigAudit {
  id: string;
  tenantId?: string;
  entityType: 'plan_feature' | 'tenant_plan' | 'tenant_override';
  entityId: string;
  featureKey?: string;
  action: 'create' | 'update' | 'delete';
  oldValue?: Record<string, any>;
  newValue?: Record<string, any>;
  changedBy?: string;
  changedByEmail?: string;
  changedAt: string;
  reason?: string;
}

export interface FeatureAccessLog {
  id: string;
  tenantId: string;
  userId?: string;
  userEmail?: string;
  featureKey: string;
  accessType: 'flag_check' | 'limit_check';
  result: 'allowed' | 'denied' | 'limit_exceeded';
  currentValue?: number;
  limitValue?: number;
  endpoint?: string;
  resourceType?: string;
  resourceId?: string;
  accessedAt: string;
}

// Credential types
export interface WorkflowReference {
  id: string;
  name: string;
  n8n_workflow_id?: string;
}

export interface CredentialEnvironment {
  id: string;
  name: string;
  type?: string;
  n8n_base_url?: string;
}

export interface Credential {
  id: string;
  provider: Provider;  // Provider type (n8n, make)
  name: string;
  type: string;
  n8n_credential_id?: string;
  tenant_id?: string;
  environment_id?: string;
  created_at?: string;
  updated_at?: string;
  used_by_workflows?: WorkflowReference[];
  environment?: CredentialEnvironment;
  credential_data?: Record<string, any>;
}

export interface CredentialCreate {
  name: string;
  type: string;
  data: Record<string, any>;
  environment_id: string;
}

export interface CredentialUpdate {
  name?: string;
  data?: Record<string, any>;
}

export interface CredentialTypeField {
  displayName: string;
  name: string;
  type: string;
  default?: any;
  required?: boolean;
  description?: string;
  options?: Array<{ name: string; value: any }>;
}

export interface CredentialTypeSchema {
  name: string;
  displayName: string;
  properties: CredentialTypeField[];
  documentationUrl?: string;
}

// Provider User types (previously N8NUser)
export interface ProviderUser {
  id: string;
  provider: Provider;  // Provider type (n8n, make)
  email: string;
  firstName?: string;
  lastName?: string;
  role?: string;
  environment_id?: string;
  environment?: CredentialEnvironment;
}

// Backward compatibility alias
export type N8NUser = ProviderUser;

// Tag types
export interface Tag {
  id: string;
  provider: Provider;  // Provider type (n8n, make)
  name: string;
  n8n_tag_id?: string;  // Legacy field, now provider_tag_id
  provider_tag_id?: string;
  environment_id?: string;
}

// Team limits
export interface TeamLimits {
  maxMembers: number;
  currentMembers: number;
  canAddMembers: boolean;
}

// Payment history
export interface PaymentHistory {
  id: string;
  amount: number;
  currency: string;
  status: string;
  description?: string;
  createdAt: string;
}

// Checkout and Portal sessions
export interface CheckoutSession {
  url: string;
  sessionId: string;
}

export interface PortalSession {
  url: string;
}

// Subscription
export interface Subscription {
  id: string;
  planId: string;
  planName: string;
  status: string;
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
}

// Global Usage types (Phase 2)
export interface GlobalUsageMetric {
  name: string;
  current: number;
  limit: number;
  percentage: number;
  status: 'ok' | 'warning' | 'critical' | 'over_limit';
}

export interface GlobalUsageStats {
  total_tenants: number;
  total_workflows: number;
  total_environments: number;
  total_users: number;
  total_executions_today: number;
  total_executions_month: number;
  tenants_at_limit: number;
  tenants_over_limit: number;
  tenants_near_limit: number;
}

export interface GlobalUsageResponse {
  stats: GlobalUsageStats;
  usage_by_plan: Record<string, number>;
  recent_growth: Record<string, number>;
}

export interface TopTenant {
  rank: number;
  tenant_id: string;
  tenant_name: string;
  plan: string;
  value: number;
  limit?: number;
  percentage?: number;
  trend?: string;
}

export interface TopTenantsResponse {
  metric: string;
  period: string;
  tenants: TopTenant[];
}

export interface TenantAtLimit {
  tenant_id: string;
  tenant_name: string;
  plan: string;
  status: string;
  metrics: GlobalUsageMetric[];
  total_usage_percentage: number;
}

export interface TenantsAtLimitResponse {
  total: number;
  tenants: TenantAtLimit[];
}

// Promotion Request/Response types (for API client)
export interface PromotionInitiateRequest {
  pipelineId: string;
  sourceEnvironmentId: string;
  targetEnvironmentId: string;
  workflowSelections: WorkflowSelection[];
  notes?: string;
}

export interface PromotionInitiateResponse {
  promotionId: string;
  status: PromotionStatus;
  workflowSelections: WorkflowSelection[];
  gateResults?: GateResult;
  requiresApproval: boolean;
}

export interface PromotionExecutionResult {
  promotionId: string;
  status: PromotionStatus;
  workflowResults: Array<{
    workflowId: string;
    workflowName: string;
    status: string;
    error?: string;
  }>;
  errors?: string[];
}

export interface PromotionApprovalRequest {
  approved: boolean;
  notes?: string;
}

export interface PromotionApprovalResponse {
  promotionId: string;
  status: PromotionStatus;
  approvedBy?: string;
  approvedAt?: string;
  rejectionReason?: string;
}

export interface PromotionSnapshotRequest {
  environmentId: string;
  type: SnapshotType;
  reason?: string;
}

export interface PromotionSnapshotResponse {
  snapshotId: string;
  gitCommitSha: string;
  type: SnapshotType;
  createdAt: string;
}

export interface PromotionCheckDriftRequest {
  sourceEnvironmentId: string;
  targetEnvironmentId: string;
  workflowIds?: string[];
}

export interface PromotionCheckDriftResponse {
  hasDrift: boolean;
  driftDetails: Array<{
    workflowId: string;
    workflowName: string;
    sourceVersion?: string;
    targetVersion?: string;
    status: 'in_sync' | 'modified' | 'missing_source' | 'missing_target';
  }>;
}

// Alias for Promotion (used by api-client)
export type PromotionResponse = Promotion;

// Tenant Stats (for admin)
export interface TenantStats {
  totalTenants: number;
  activeTenants: number;
  suspendedTenants: number;
  trialTenants: number;
  paidTenants: number;
  byPlan: Record<string, number>;
  recentSignups: number;
  churnedThisMonth: number;
}

// Execution Metrics Summary
export interface ExecutionMetricsSummary {
  totalExecutions: number;
  successCount: number;
  failureCount: number;
  successRate: number;
  avgDurationMs: number;
  period: string;
}