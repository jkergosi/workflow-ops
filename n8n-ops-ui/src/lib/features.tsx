// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { useAuth } from '@/lib/auth';

// Plan feature definitions - Phase 2 Full Feature Catalog
export interface PlanFeatures {
  // Legacy features (kept for backward compatibility)
  max_environments: number | 'unlimited';
  max_team_members: number | 'unlimited';
  max_workflows_per_env: number | 'unlimited';
  github_sync: boolean;
  scheduled_backups: boolean;
  workflow_snapshots: boolean;
  deployments: boolean;
  observability: boolean;
  audit_logs: boolean;
  custom_branding: boolean;
  sso: boolean;
  api_access: boolean;
  priority_support: boolean;

  // Phase 2 Entitlements - Environment
  environment_basic?: boolean;
  environment_health?: boolean;
  environment_diff?: boolean;
  environment_limits?: number;

  // Phase 2 Entitlements - Workflows + CI/CD
  workflow_read?: boolean;
  workflow_push?: boolean;
  workflow_dirty_check?: boolean;
  workflow_ci_cd?: boolean;
  workflow_ci_cd_approval?: boolean;
  workflow_limits?: number;

  // Phase 2 Entitlements - Snapshots
  snapshots_enabled?: boolean;
  snapshots_auto?: boolean;
  snapshots_history?: number;
  snapshots_export?: boolean;

  // Phase 2 Entitlements - Observability
  observability_basic?: boolean;
  observability_alerts?: boolean;
  observability_alerts_advanced?: boolean;
  observability_logs?: boolean;
  observability_limits?: number;

  // Phase 2 Entitlements - Security / RBAC
  rbac_basic?: boolean;
  rbac_advanced?: boolean;
  audit_logs_enabled?: boolean;
  audit_export?: boolean;

  // Phase 2 Entitlements - Agency
  agency_enabled?: boolean;
  agency_client_management?: boolean;
  agency_whitelabel?: boolean;
  agency_client_limits?: number;

  // Phase 2 Entitlements - Enterprise
  sso_saml?: boolean;
  support_priority?: boolean;
  data_residency?: boolean;
  enterprise_limits?: number;
}

// Default plan configurations - Phase 2 Full Feature Catalog
const PLAN_FEATURES: Record<string, PlanFeatures> = {
  free: {
    // Legacy
    max_environments: 2,
    max_team_members: 3,
    max_workflows_per_env: 50,
    github_sync: false,
    scheduled_backups: false,
    workflow_snapshots: true,
    deployments: false,
    observability: false,
    audit_logs: false,
    custom_branding: false,
    sso: false,
    api_access: false,
    priority_support: false,
    // Phase 2 Environment
    environment_basic: true,
    environment_health: false,
    environment_diff: false,
    environment_limits: 2,
    // Phase 2 Workflows
    workflow_read: true,
    workflow_push: true,
    workflow_dirty_check: false,
    workflow_ci_cd: false,
    workflow_ci_cd_approval: false,
    workflow_limits: 10,
    // Phase 2 Snapshots
    snapshots_enabled: true,
    snapshots_auto: false,
    snapshots_history: 5,
    snapshots_export: false,
    // Phase 2 Observability
    observability_basic: true,
    observability_alerts: false,
    observability_alerts_advanced: false,
    observability_logs: false,
    observability_limits: 7,
    // Phase 2 RBAC
    rbac_basic: true,
    rbac_advanced: false,
    audit_logs_enabled: false,
    audit_export: false,
    // Phase 2 Agency
    agency_enabled: false,
    agency_client_management: false,
    agency_whitelabel: false,
    agency_client_limits: 0,
    // Phase 2 Enterprise
    sso_saml: false,
    support_priority: false,
    data_residency: false,
    enterprise_limits: 0,
  },
  pro: {
    // Legacy
    max_environments: 10,
    max_team_members: 25,
    max_workflows_per_env: 500,
    github_sync: true,
    scheduled_backups: true,
    workflow_snapshots: true,
    deployments: true,
    observability: true,
    audit_logs: true,
    custom_branding: false,
    sso: false,
    api_access: true,
    priority_support: true,
    // Phase 2 Environment
    environment_basic: true,
    environment_health: true,
    environment_diff: true,
    environment_limits: 10,
    // Phase 2 Workflows
    workflow_read: true,
    workflow_push: true,
    workflow_dirty_check: true,
    workflow_ci_cd: true,
    workflow_ci_cd_approval: false,
    workflow_limits: 200,
    // Phase 2 Snapshots
    snapshots_enabled: true,
    snapshots_auto: true,
    snapshots_history: 30,
    snapshots_export: true,
    // Phase 2 Observability
    observability_basic: true,
    observability_alerts: true,
    observability_alerts_advanced: false,
    observability_logs: true,
    observability_limits: 30,
    // Phase 2 RBAC
    rbac_basic: true,
    rbac_advanced: false,
    audit_logs_enabled: true,
    audit_export: false,
    // Phase 2 Agency
    agency_enabled: false,
    agency_client_management: false,
    agency_whitelabel: false,
    agency_client_limits: 0,
    // Phase 2 Enterprise
    sso_saml: false,
    support_priority: true,
    data_residency: false,
    enterprise_limits: 0,
  },
  agency: {
    // Legacy
    max_environments: 50,
    max_team_members: 100,
    max_workflows_per_env: 1000,
    github_sync: true,
    scheduled_backups: true,
    workflow_snapshots: true,
    deployments: true,
    observability: true,
    audit_logs: true,
    custom_branding: true,
    sso: false,
    api_access: true,
    priority_support: true,
    // Phase 2 Environment
    environment_basic: true,
    environment_health: true,
    environment_diff: true,
    environment_limits: 50,
    // Phase 2 Workflows
    workflow_read: true,
    workflow_push: true,
    workflow_dirty_check: true,
    workflow_ci_cd: true,
    workflow_ci_cd_approval: true,
    workflow_limits: 1000,
    // Phase 2 Snapshots
    snapshots_enabled: true,
    snapshots_auto: true,
    snapshots_history: 90,
    snapshots_export: true,
    // Phase 2 Observability
    observability_basic: true,
    observability_alerts: true,
    observability_alerts_advanced: false,
    observability_logs: true,
    observability_limits: 90,
    // Phase 2 RBAC
    rbac_basic: true,
    rbac_advanced: true,
    audit_logs_enabled: true,
    audit_export: true,
    // Phase 2 Agency
    agency_enabled: true,
    agency_client_management: true,
    agency_whitelabel: true,
    agency_client_limits: 25,
    // Phase 2 Enterprise
    sso_saml: false,
    support_priority: true,
    data_residency: false,
    enterprise_limits: 0,
  },
  enterprise: {
    // Legacy
    max_environments: 'unlimited',
    max_team_members: 'unlimited',
    max_workflows_per_env: 'unlimited',
    github_sync: true,
    scheduled_backups: true,
    workflow_snapshots: true,
    deployments: true,
    observability: true,
    audit_logs: true,
    custom_branding: true,
    sso: true,
    api_access: true,
    priority_support: true,
    // Phase 2 Environment
    environment_basic: true,
    environment_health: true,
    environment_diff: true,
    environment_limits: 9999,
    // Phase 2 Workflows
    workflow_read: true,
    workflow_push: true,
    workflow_dirty_check: true,
    workflow_ci_cd: true,
    workflow_ci_cd_approval: true,
    workflow_limits: 5000,
    // Phase 2 Snapshots
    snapshots_enabled: true,
    snapshots_auto: true,
    snapshots_history: 365,
    snapshots_export: true,
    // Phase 2 Observability
    observability_basic: true,
    observability_alerts: true,
    observability_alerts_advanced: true,
    observability_logs: true,
    observability_limits: 365,
    // Phase 2 RBAC
    rbac_basic: true,
    rbac_advanced: true,
    audit_logs_enabled: true,
    audit_export: true,
    // Phase 2 Agency
    agency_enabled: true,
    agency_client_management: true,
    agency_whitelabel: true,
    agency_client_limits: 100,
    // Phase 2 Enterprise
    sso_saml: true,
    support_priority: true,
    data_residency: true,
    enterprise_limits: 9999,
  },
};

// Feature display names for UI - Phase 2 Full Catalog
export const FEATURE_DISPLAY_NAMES: Record<string, string> = {
  // Legacy
  max_environments: 'Environments',
  max_team_members: 'Team Members',
  max_workflows_per_env: 'Workflows per Environment',
  github_sync: 'GitHub Sync',
  scheduled_backups: 'Scheduled Backups',
  workflow_snapshots: 'Workflow Snapshots',
  deployments: 'Deployments',
  observability: 'Observability',
  audit_logs: 'Audit Logs',
  custom_branding: 'Custom Branding',
  sso: 'Single Sign-On',
  api_access: 'API Access',
  priority_support: 'Priority Support',
  // Phase 2 Environment
  environment_basic: 'Basic Environments',
  environment_health: 'Environment Health Monitoring',
  environment_diff: 'Drift Detection',
  environment_limits: 'Environment Limit',
  // Phase 2 Workflows
  workflow_read: 'View Workflows',
  workflow_push: 'Push/Upload Workflows',
  workflow_dirty_check: 'Dirty State Detection',
  workflow_ci_cd: 'Workflow CI/CD',
  workflow_ci_cd_approval: 'CI/CD Approvals',
  workflow_limits: 'Workflow Limit',
  // Phase 2 Snapshots
  snapshots_enabled: 'Snapshots',
  snapshots_auto: 'Automatic Snapshots',
  snapshots_history: 'Snapshot Retention',
  snapshots_export: 'Export Snapshots',
  // Phase 2 Observability
  observability_basic: 'Basic Metrics',
  observability_alerts: 'Alerting',
  observability_alerts_advanced: 'Advanced Alerting',
  observability_logs: 'Execution Logs',
  observability_limits: 'Log Retention',
  // Phase 2 RBAC
  rbac_basic: 'Basic Role Management',
  rbac_advanced: 'Advanced RBAC',
  audit_logs_enabled: 'Audit Logging',
  audit_export: 'Export Audit Logs',
  // Phase 2 Agency
  agency_enabled: 'Agency Mode',
  agency_client_management: 'Client Management',
  agency_whitelabel: 'White-label Branding',
  agency_client_limits: 'Client Limit',
  // Phase 2 Enterprise
  sso_saml: 'SSO/SAML Authentication',
  support_priority: 'Priority Support',
  data_residency: 'Data Residency Controls',
  enterprise_limits: 'Enterprise Quotas',
};

// Which plan is required for each feature - Phase 2 Full Catalog
export const FEATURE_REQUIRED_PLANS: Record<string, 'free' | 'pro' | 'agency' | 'enterprise' | null> = {
  // Legacy
  max_environments: null,
  max_team_members: null,
  max_workflows_per_env: null,
  github_sync: 'pro',
  scheduled_backups: 'pro',
  workflow_snapshots: 'free',
  deployments: 'pro',
  observability: 'pro',
  audit_logs: 'pro',
  custom_branding: 'agency',
  sso: 'enterprise',
  api_access: 'pro',
  priority_support: 'pro',
  // Phase 2 Environment
  environment_basic: 'free',
  environment_health: 'pro',
  environment_diff: 'pro',
  environment_limits: null,
  // Phase 2 Workflows
  workflow_read: 'free',
  workflow_push: 'free',
  workflow_dirty_check: 'pro',
  workflow_ci_cd: 'pro',
  workflow_ci_cd_approval: 'agency',
  workflow_limits: null,
  // Phase 2 Snapshots
  snapshots_enabled: 'free',
  snapshots_auto: 'pro',
  snapshots_history: null,
  snapshots_export: 'pro',
  // Phase 2 Observability
  observability_basic: 'free',
  observability_alerts: 'pro',
  observability_alerts_advanced: 'enterprise',
  observability_logs: 'pro',
  observability_limits: null,
  // Phase 2 RBAC
  rbac_basic: 'free',
  rbac_advanced: 'agency',
  audit_logs_enabled: 'pro',
  audit_export: 'agency',
  // Phase 2 Agency
  agency_enabled: 'agency',
  agency_client_management: 'agency',
  agency_whitelabel: 'agency',
  agency_client_limits: null,
  // Phase 2 Enterprise
  sso_saml: 'enterprise',
  support_priority: 'pro',
  data_residency: 'enterprise',
  enterprise_limits: null,
};

// Usage tracking interface
interface ResourceUsage {
  current: number;
  max: number | 'unlimited';
}

interface UsageData {
  environments: ResourceUsage;
  team_members: ResourceUsage;
  workflows: Record<string, ResourceUsage>; // by environment ID
}

interface FeaturesContextValue {
  planName: string;
  features: PlanFeatures;
  usage: UsageData | null;
  isLoading: boolean;
  canUseFeature: (feature: keyof PlanFeatures | string) => boolean;
  hasEntitlement: (entitlementName: string) => boolean;
  getEntitlementLimit: (entitlementName: string) => number | null;
  isAtLimit: (resource: 'environments' | 'team_members') => boolean;
  getRequiredPlan: (feature: keyof PlanFeatures | string) => 'free' | 'pro' | 'agency' | 'enterprise' | null;
  refreshUsage: () => Promise<void>;
}

const FeaturesContext = createContext<FeaturesContextValue | null>(null);

interface FeaturesProviderProps {
  children: ReactNode;
}

export function FeaturesProvider({ children }: FeaturesProviderProps) {
  const { user, entitlements } = useAuth();
  const [planName, setPlanName] = useState<string>('free');
  const [features, setFeatures] = useState<PlanFeatures>(PLAN_FEATURES.free);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load plan and features based on user's subscription and entitlements
  useEffect(() => {
    const loadFeatures = async () => {
      setIsLoading(true);
      try {
        // Use entitlements plan name if available, otherwise fall back to 'free'
        const userPlan = entitlements?.plan_name || 'free';
        setPlanName(userPlan);

        // Start with base plan features
        const baseFeatures = PLAN_FEATURES[userPlan] || PLAN_FEATURES.free;

        // Merge with entitlements from database if available
        if (entitlements?.features) {
          // Get environment_limits from entitlements and sync to legacy max_environments
          const envLimits = entitlements.features.environment_limits as number ?? 2;
          setFeatures({
            ...baseFeatures,
            // Map entitlements features to plan features
            snapshots_enabled: entitlements.features.snapshots_enabled as boolean ?? true,
            workflow_ci_cd: entitlements.features.workflow_ci_cd as boolean ?? false,
            workflow_limits: entitlements.features.workflow_limits as number ?? 10,
            // Sync environment_limits to legacy max_environments for backward compatibility
            max_environments: envLimits,
            // Map all Phase 2 features from entitlements
            environment_basic: entitlements.features.environment_basic as boolean ?? true,
            environment_health: entitlements.features.environment_health as boolean ?? false,
            environment_diff: entitlements.features.environment_diff as boolean ?? false,
            environment_limits: envLimits,
            workflow_read: entitlements.features.workflow_read as boolean ?? true,
            workflow_push: entitlements.features.workflow_push as boolean ?? true,
            workflow_dirty_check: entitlements.features.workflow_dirty_check as boolean ?? false,
            workflow_ci_cd_approval: entitlements.features.workflow_ci_cd_approval as boolean ?? false,
            snapshots_auto: entitlements.features.snapshots_auto as boolean ?? false,
            snapshots_history: entitlements.features.snapshots_history as number ?? 5,
            snapshots_export: entitlements.features.snapshots_export as boolean ?? false,
            observability_basic: entitlements.features.observability_basic as boolean ?? true,
            observability_alerts: entitlements.features.observability_alerts as boolean ?? false,
            observability_alerts_advanced: entitlements.features.observability_alerts_advanced as boolean ?? false,
            observability_logs: entitlements.features.observability_logs as boolean ?? false,
            observability_limits: entitlements.features.observability_limits as number ?? 7,
            rbac_basic: entitlements.features.rbac_basic as boolean ?? true,
            rbac_advanced: entitlements.features.rbac_advanced as boolean ?? false,
            audit_logs: entitlements.features.audit_logs as boolean ?? false,
            audit_logs_enabled: entitlements.features.audit_logs as boolean ?? false, // Alias for consistency
            audit_export: entitlements.features.audit_export as boolean ?? false,
            agency_enabled: entitlements.features.agency_enabled as boolean ?? false,
            agency_client_management: entitlements.features.agency_client_management as boolean ?? false,
            agency_whitelabel: entitlements.features.agency_whitelabel as boolean ?? false,
            agency_client_limits: entitlements.features.agency_client_limits as number ?? 0,
            sso_saml: entitlements.features.sso_saml as boolean ?? false,
            support_priority: entitlements.features.support_priority as boolean ?? false,
            data_residency: entitlements.features.data_residency as boolean ?? false,
            enterprise_limits: entitlements.features.enterprise_limits as number ?? 0,
            // Also map to legacy feature names for backward compatibility
            workflow_snapshots: entitlements.features.snapshots_enabled as boolean ?? true,
            deployments: entitlements.features.workflow_ci_cd as boolean ?? false,
          });
        } else {
          setFeatures(baseFeatures);
        }

        // Mock usage data
        setUsage({
          environments: { current: 1, max: baseFeatures.max_environments || 2 },
          team_members: { current: 1, max: baseFeatures.max_team_members || 3 },
          workflows: {},
        });
      } catch (error) {
        console.error('Failed to load features:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadFeatures();
  }, [user, entitlements]);

  const canUseFeature = (feature: keyof PlanFeatures | string): boolean => {
    // Check entitlements first for Phase 1 features
    if (entitlements?.features) {
      const entitlementValue = entitlements.features[feature];
      if (typeof entitlementValue === 'boolean') {
        return entitlementValue;
      }
    }

    // Fall back to plan features
    const value = features[feature as keyof PlanFeatures];
    if (typeof value === 'boolean') {
      return value;
    }
    // For numeric limits, always return true (checked separately via isAtLimit)
    return true;
  };

  const hasEntitlement = (entitlementName: string): boolean => {
    if (entitlements?.features) {
      const value = entitlements.features[entitlementName];
      if (typeof value === 'boolean') {
        return value;
      }
      // For numeric values, return true if > 0
      if (typeof value === 'number') {
        return value > 0;
      }
    }
    return false;
  };

  const getEntitlementLimit = (entitlementName: string): number | null => {
    if (entitlements?.features) {
      const value = entitlements.features[entitlementName];
      if (typeof value === 'number') {
        return value;
      }
    }
    return null;
  };

  const isAtLimit = (resource: 'environments' | 'team_members'): boolean => {
    if (!usage) return false;
    const resourceUsage = usage[resource];
    if (!resourceUsage) return false;
    if (resourceUsage.max === 'unlimited') return false;
    return resourceUsage.current >= resourceUsage.max;
  };

  const getRequiredPlan = (feature: keyof PlanFeatures | string): 'free' | 'pro' | 'agency' | 'enterprise' | null => {
    return FEATURE_REQUIRED_PLANS[feature] ?? null;
  };

  const refreshUsage = async (): Promise<void> => {
    // TODO: Implement API call to refresh usage data
    console.log('Refreshing usage data...');
  };

  const value: FeaturesContextValue = {
    planName,
    features,
    usage,
    isLoading,
    canUseFeature,
    hasEntitlement,
    getEntitlementLimit,
    isAtLimit,
    getRequiredPlan,
    refreshUsage,
  };

  return (
    <FeaturesContext.Provider value={value}>
      {children}
    </FeaturesContext.Provider>
  );
}

export function useFeatures(): FeaturesContextValue {
  const context = useContext(FeaturesContext);
  if (!context) {
    throw new Error('useFeatures must be used within a FeaturesProvider');
  }
  return context;
}
