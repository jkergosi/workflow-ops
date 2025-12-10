import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useAuth } from '@/lib/auth';

// Plan feature definitions
export interface PlanFeatures {
  // Core features
  max_environments: number | 'unlimited';
  max_team_members: number | 'unlimited';
  max_workflows_per_env: number | 'unlimited';

  // Feature flags
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
}

// Default plan configurations
const PLAN_FEATURES: Record<string, PlanFeatures> = {
  free: {
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
  },
  pro: {
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
  },
  enterprise: {
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
  },
};

// Feature display names for UI
export const FEATURE_DISPLAY_NAMES: Record<keyof PlanFeatures, string> = {
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
};

// Which plan is required for each feature
export const FEATURE_REQUIRED_PLANS: Record<keyof PlanFeatures, 'free' | 'pro' | 'enterprise' | null> = {
  max_environments: null,
  max_team_members: null,
  max_workflows_per_env: null,
  github_sync: 'pro',
  scheduled_backups: 'pro',
  workflow_snapshots: 'free',
  deployments: 'pro',
  observability: 'pro',
  audit_logs: 'pro',
  custom_branding: 'enterprise',
  sso: 'enterprise',
  api_access: 'pro',
  priority_support: 'pro',
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
  canUseFeature: (feature: keyof PlanFeatures) => boolean;
  isAtLimit: (resource: 'environments' | 'team_members') => boolean;
  getRequiredPlan: (feature: keyof PlanFeatures) => 'free' | 'pro' | 'enterprise' | null;
  refreshUsage: () => Promise<void>;
}

const FeaturesContext = createContext<FeaturesContextValue | null>(null);

interface FeaturesProviderProps {
  children: ReactNode;
}

export function FeaturesProvider({ children }: FeaturesProviderProps) {
  const { user } = useAuth();
  const [planName, setPlanName] = useState<string>('free');
  const [features, setFeatures] = useState<PlanFeatures>(PLAN_FEATURES.free);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load plan and features based on user's subscription
  useEffect(() => {
    const loadFeatures = async () => {
      setIsLoading(true);
      try {
        // For now, use mock data - in production, fetch from API
        const userPlan = user?.subscription_plan || 'free';
        setPlanName(userPlan);
        setFeatures(PLAN_FEATURES[userPlan] || PLAN_FEATURES.free);

        // Mock usage data
        setUsage({
          environments: { current: 1, max: PLAN_FEATURES[userPlan]?.max_environments || 2 },
          team_members: { current: 1, max: PLAN_FEATURES[userPlan]?.max_team_members || 3 },
          workflows: {},
        });
      } catch (error) {
        console.error('Failed to load features:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadFeatures();
  }, [user]);

  const canUseFeature = (feature: keyof PlanFeatures): boolean => {
    const value = features[feature];
    if (typeof value === 'boolean') {
      return value;
    }
    // For numeric limits, always return true (checked separately via isAtLimit)
    return true;
  };

  const isAtLimit = (resource: 'environments' | 'team_members'): boolean => {
    if (!usage) return false;
    const resourceUsage = usage[resource];
    if (!resourceUsage) return false;
    if (resourceUsage.max === 'unlimited') return false;
    return resourceUsage.current >= resourceUsage.max;
  };

  const getRequiredPlan = (feature: keyof PlanFeatures): 'free' | 'pro' | 'enterprise' | null => {
    return FEATURE_REQUIRED_PLANS[feature];
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
