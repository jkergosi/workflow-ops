// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { useAuth } from '@/lib/auth';
import { apiClient } from '@/lib/api-client';

// Default provider for MVP - all feature checks default to n8n
const DEFAULT_PROVIDER = 'n8n';

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

  // Drift
  drift_incidents?: boolean;
}

// Plan features cache - loaded from API (no fallback - database is the source of truth)
let PLAN_FEATURES_CACHE: Record<string, PlanFeatures> = {};

// Feature display names cache - loaded from API (no fallback)
let FEATURE_DISPLAY_NAMES_CACHE: Record<string, string> = {};

// Feature required plans - loaded from API (no fallback)
let FEATURE_REQUIRED_PLANS_CACHE: Record<string, 'free' | 'pro' | 'agency' | 'enterprise' | null> = {};

// Track loading state
let featuresLoaded = false;
let featuresError: Error | null = null;

// Load plan features from API - throws on error (no fallback)
async function loadPlanFeatures(): Promise<void> {
  try {
    const response = await apiClient.getAllPlanFeatures();

    if (!response.data || Object.keys(response.data).length === 0) {
      throw new Error('Plan features table is empty - database misconfiguration');
    }

    // Check for empty plan data
    const hasValidData = Object.values(response.data).some(plan => Object.keys(plan).length > 0);
    if (!hasValidData) {
      throw new Error('Plan features contain no feature data - database misconfiguration');
    }

    PLAN_FEATURES_CACHE = response.data as Record<string, PlanFeatures>;
  } catch (error) {
    console.error('Failed to load plan features from API:', error);
    featuresError = error instanceof Error ? error : new Error('Failed to load plan features');
    throw featuresError;
  }
}

// Load feature display names from API - throws on error (no fallback)
async function loadFeatureDisplayNames(): Promise<void> {
  try {
    const response = await apiClient.getFeatureDisplayNames();

    if (!response.data || Object.keys(response.data).length === 0) {
      throw new Error('Feature display names table is empty - database misconfiguration');
    }

    FEATURE_DISPLAY_NAMES_CACHE = response.data as Record<string, string>;
  } catch (error) {
    console.error('Failed to load feature display names from API:', error);
    featuresError = error instanceof Error ? error : new Error('Failed to load feature display names');
    throw featuresError;
  }
}

// Load feature requirements from API - throws on error (no fallback)
async function loadFeatureRequirements(): Promise<void> {
  try {
    const response = await apiClient.getPlanConfigurations();
    const requirements = response.data.feature_requirements || [];

    const cache: Record<string, 'free' | 'pro' | 'agency' | 'enterprise' | null> = {};
    for (const req of requirements) {
      cache[req.feature_name] = (req.required_plan as 'free' | 'pro' | 'agency' | 'enterprise' | null) || null;
    }
    FEATURE_REQUIRED_PLANS_CACHE = cache;
  } catch (error) {
    console.error('Failed to load feature requirements from API:', error);
    featuresError = error instanceof Error ? error : new Error('Failed to load feature requirements');
    throw featuresError;
  }
}

// Load all feature data from API
async function loadAllFeatureData(): Promise<void> {
  if (featuresLoaded) return;

  try {
    await Promise.all([
      loadPlanFeatures(),
      loadFeatureDisplayNames(),
      loadFeatureRequirements(),
    ]);
    featuresLoaded = true;
    featuresError = null;
  } catch (error) {
    featuresLoaded = false;
    throw error;
  }
}

// Export getter function for plan features - throws if not loaded
export function getPlanFeatures(plan: string): PlanFeatures {
  if (featuresError) {
    throw featuresError;
  }

  const planFeatures = PLAN_FEATURES_CACHE[plan];
  if (!planFeatures) {
    throw new Error(`Plan '${plan}' not found in database. Available plans: ${Object.keys(PLAN_FEATURES_CACHE).join(', ')}`);
  }

  return planFeatures;
}

// Export getter function for feature required plan - returns null if not found
export function getFeatureRequiredPlan(feature: string): 'free' | 'pro' | 'agency' | 'enterprise' | null {
  return FEATURE_REQUIRED_PLANS_CACHE[feature] ?? null;
}

// Export getter function for feature display name
export function getFeatureDisplayName(feature: string): string {
  return FEATURE_DISPLAY_NAMES_CACHE[feature] ?? feature;
}

// For backward compatibility, export as object that uses getter
export const FEATURE_REQUIRED_PLANS = new Proxy({} as Record<string, 'free' | 'pro' | 'agency' | 'enterprise' | null>, {
  get(target, prop: string) {
    return getFeatureRequiredPlan(prop);
  },
  has(target, prop: string) {
    return prop in FEATURE_REQUIRED_PLANS_CACHE;
  },
  ownKeys(target) {
    return Object.keys(FEATURE_REQUIRED_PLANS_CACHE);
  },
});

// For backward compatibility, export display names proxy
export const FEATURE_DISPLAY_NAMES = new Proxy({} as Record<string, string>, {
  get(target, prop: string) {
    return getFeatureDisplayName(prop);
  },
  has(target, prop: string) {
    return prop in FEATURE_DISPLAY_NAMES_CACHE;
  },
  ownKeys(target) {
    return Object.keys(FEATURE_DISPLAY_NAMES_CACHE);
  },
});

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

// Provider entitlements from backend (source of truth)
interface ProviderEntitlements {
  plan_name: string | null;
  provider_key: string;
  features: Record<string, any>;
  max_environments: number;
  max_workflows: number;
  has_subscription: boolean;
  status: string | null;
}

interface FeaturesContextValue {
  planName: string;
  features: PlanFeatures | null;
  usage: UsageData | null;
  isLoading: boolean;
  error: Error | null;
  // Legacy feature checks (backwards compatible)
  canUseFeature: (feature: keyof PlanFeatures | string) => boolean;
  hasEntitlement: (entitlementName: string) => boolean;
  getEntitlementLimit: (entitlementName: string) => number | null;
  isAtLimit: (resource: 'environments' | 'team_members') => boolean;
  getRequiredPlan: (feature: keyof PlanFeatures | string) => 'free' | 'pro' | 'agency' | 'enterprise' | null;
  refreshUsage: () => Promise<void>;
  // Provider-aware feature checks (new - single source of truth)
  hasFeature: (featureKey: string, providerKey?: string) => boolean;
  getProviderEntitlements: (providerKey?: string) => ProviderEntitlements | null;
  hasProviderSubscription: (providerKey?: string) => boolean;
  providerEntitlements: ProviderEntitlements | null;
}

// Keep a single context instance across Vite HMR updates.
// Without this, edits to this file can produce multiple live module copies (different `?t=`),
// causing providers/consumers to reference different contexts and crash at runtime.
const FEATURES_CONTEXT_KEY = '__n8n_ops_features_context__';
const FeaturesContext: React.Context<FeaturesContextValue | null> =
  (globalThis as any)[FEATURES_CONTEXT_KEY] ?? createContext<FeaturesContextValue | null>(null);
if (import.meta.env.DEV) {
  (globalThis as any)[FEATURES_CONTEXT_KEY] = FeaturesContext;
}

interface FeaturesProviderProps {
  children: ReactNode;
}

export function FeaturesProvider({ children }: FeaturesProviderProps) {
  const { user, entitlements, needsOnboarding } = useAuth();
  const isTest = import.meta.env.MODE === 'test';
  const [planName, setPlanName] = useState<string>('free');
  const [features, setFeatures] = useState<PlanFeatures | null>(null);
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [featureDataReady, setFeatureDataReady] = useState(false);

  // Load all plan data on mount
  useEffect(() => {
    const initializeFeatures = async () => {
      try {
        await loadAllFeatureData();
        // Also load workflow policy matrix
        const { loadWorkflowPolicyMatrix } = await import('./workflow-action-policy');
        await loadWorkflowPolicyMatrix();
        setError(null);
        setFeatureDataReady(true);
      } catch (err) {
        const loadError = err instanceof Error ? err : new Error('Failed to load feature data');
        console.error('Failed to initialize features:', loadError);
        setError(loadError);
        setFeatureDataReady(true); // Still mark as ready so we can show error state
      }
    };

    initializeFeatures();
  }, []);

  // Provider-scoped entitlements - source of truth from backend
  const [providerEntitlements, setProviderEntitlements] = useState<ProviderEntitlements | null>(null);
  const [entitlementsCache, setEntitlementsCache] = useState<Record<string, ProviderEntitlements>>({});

  // Load plan and features based on user's subscription and entitlements
  useEffect(() => {
    // Wait for feature data to be loaded before proceeding
    if (!featureDataReady) {
      return;
    }

    const loadFeatures = async () => {
      setIsLoading(true);
      try {
        // Use entitlements plan name if available, otherwise fall back to 'free'
        const userPlan = entitlements?.plan_name || 'free';
        setPlanName(userPlan);

        // Get base plan features from cache (throws if not loaded)
        let baseFeatures: PlanFeatures;
        try {
          baseFeatures = getPlanFeatures(userPlan);
        } catch (err) {
          // If plan not found, this is a database configuration issue
          const planError = err instanceof Error ? err : new Error('Failed to get plan features');
          console.error('Failed to get plan features:', planError);
          setError(planError);
          setIsLoading(false);
          return;
        }

        // Get environment_limits from entitlements - prioritize entitlements over baseFeatures
        let envLimits = 1; // Default fallback
        if (entitlements?.features?.environment_limits !== undefined && entitlements.features.environment_limits !== null) {
          envLimits = entitlements.features.environment_limits as number;
          if (!isTest) console.log('[Features] Using environment_limits from entitlements:', envLimits);
        } else if (baseFeatures.max_environments && baseFeatures.max_environments !== 'unlimited') {
          envLimits = baseFeatures.max_environments as number;
          if (!isTest) console.log('[Features] Using environment_limits from baseFeatures:', envLimits);
        }
        if (!isTest) console.log('[Features] Entitlements:', entitlements);
        if (!isTest) console.log('[Features] Plan:', userPlan, 'envLimits:', envLimits, 'baseFeatures.max_environments:', baseFeatures.max_environments);

        // Merge with entitlements from database if available
        if (entitlements?.features) {
          setFeatures({
            ...baseFeatures,
            // Map entitlements features to plan features
            snapshots_enabled: entitlements.features.snapshots_enabled as boolean ?? baseFeatures.snapshots_enabled ?? true,
            workflow_ci_cd: entitlements.features.workflow_ci_cd as boolean ?? baseFeatures.workflow_ci_cd ?? false,
            workflow_limits: entitlements.features.workflow_limits as number ?? baseFeatures.workflow_limits ?? 10,
            // Sync environment_limits to legacy max_environments for backward compatibility
            max_environments: envLimits,
            // Map all Phase 2 features from entitlements
            environment_basic: entitlements.features.environment_basic as boolean ?? baseFeatures.environment_basic ?? true,
            environment_health: entitlements.features.environment_health as boolean ?? baseFeatures.environment_health ?? false,
            environment_diff: entitlements.features.environment_diff as boolean ?? baseFeatures.environment_diff ?? false,
            environment_limits: envLimits,
            workflow_read: entitlements.features.workflow_read as boolean ?? baseFeatures.workflow_read ?? true,
            workflow_push: entitlements.features.workflow_push as boolean ?? baseFeatures.workflow_push ?? true,
            workflow_dirty_check: entitlements.features.workflow_dirty_check as boolean ?? baseFeatures.workflow_dirty_check ?? false,
            workflow_ci_cd_approval: entitlements.features.workflow_ci_cd_approval as boolean ?? baseFeatures.workflow_ci_cd_approval ?? false,
            snapshots_auto: entitlements.features.snapshots_auto as boolean ?? baseFeatures.snapshots_auto ?? false,
            snapshots_history: entitlements.features.snapshots_history as number ?? baseFeatures.snapshots_history ?? 5,
            snapshots_export: entitlements.features.snapshots_export as boolean ?? baseFeatures.snapshots_export ?? false,
            observability_basic: entitlements.features.observability_basic as boolean ?? baseFeatures.observability_basic ?? true,
            observability_alerts: entitlements.features.observability_alerts as boolean ?? baseFeatures.observability_alerts ?? false,
            observability_alerts_advanced: entitlements.features.observability_alerts_advanced as boolean ?? baseFeatures.observability_alerts_advanced ?? false,
            observability_logs: entitlements.features.observability_logs as boolean ?? baseFeatures.observability_logs ?? false,
            observability_limits: entitlements.features.observability_limits as number ?? baseFeatures.observability_limits ?? 7,
            rbac_basic: entitlements.features.rbac_basic as boolean ?? baseFeatures.rbac_basic ?? true,
            rbac_advanced: entitlements.features.rbac_advanced as boolean ?? baseFeatures.rbac_advanced ?? false,
            audit_logs: entitlements.features.audit_logs as boolean ?? baseFeatures.audit_logs ?? false,
            audit_logs_enabled: entitlements.features.audit_logs as boolean ?? baseFeatures.audit_logs_enabled ?? false,
            audit_export: entitlements.features.audit_export as boolean ?? baseFeatures.audit_export ?? false,
            agency_enabled: entitlements.features.agency_enabled as boolean ?? baseFeatures.agency_enabled ?? false,
            agency_client_management: entitlements.features.agency_client_management as boolean ?? baseFeatures.agency_client_management ?? false,
            agency_whitelabel: entitlements.features.agency_whitelabel as boolean ?? baseFeatures.agency_whitelabel ?? false,
            agency_client_limits: entitlements.features.agency_client_limits as number ?? baseFeatures.agency_client_limits ?? 0,
            sso_saml: entitlements.features.sso_saml as boolean ?? baseFeatures.sso_saml ?? false,
            support_priority: entitlements.features.support_priority as boolean ?? baseFeatures.support_priority ?? false,
            data_residency: entitlements.features.data_residency as boolean ?? baseFeatures.data_residency ?? false,
            enterprise_limits: entitlements.features.enterprise_limits as number ?? baseFeatures.enterprise_limits ?? 0,
            drift_incidents: entitlements.features.drift_incidents as boolean ?? baseFeatures.drift_incidents ?? false,
            // Also map to legacy feature names for backward compatibility
            workflow_snapshots: entitlements.features.snapshots_enabled as boolean ?? baseFeatures.workflow_snapshots ?? true,
            deployments: entitlements.features.workflow_ci_cd as boolean ?? baseFeatures.deployments ?? false,
          });
        } else {
          setFeatures({
            ...baseFeatures,
            max_environments: envLimits,
            environment_limits: envLimits,
          });
        }

        // Load actual usage data - skip during onboarding or when not authenticated
        if (user && !needsOnboarding) {
          try {
            const { api } = await import('./api');
            const envsResponse = await api.getEnvironments();
            const envCount = envsResponse?.data?.length || 0;

            setUsage({
              environments: { current: envCount, max: envLimits },
              team_members: { current: 1, max: baseFeatures.max_team_members || 3 },
              workflows: {},
            });
          } catch (err) {
            if (!isTest) console.warn('Failed to load environment count, using defaults:', err);
            setUsage({
              environments: { current: 0, max: envLimits },
              team_members: { current: 1, max: baseFeatures.max_team_members || 3 },
              workflows: {},
            });
          }
        } else {
          // During onboarding, use default values from database
          setUsage({
            environments: { current: 0, max: envLimits },
            team_members: { current: 1, max: baseFeatures.max_team_members || 3 },
            workflows: {},
          });
        }

        setError(null);
      } catch (err) {
        const loadError = err instanceof Error ? err : new Error('Failed to load features');
        if (!isTest) console.error('Failed to load features:', loadError);
        setError(loadError);
      } finally {
        setIsLoading(false);
      }
    };

    loadFeatures();
  }, [user, entitlements, needsOnboarding, featureDataReady]);

  const canUseFeature = (feature: keyof PlanFeatures | string): boolean => {
    // If features failed to load, deny all feature access
    if (error || !features) {
      return false;
    }

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
    return getFeatureRequiredPlan(feature);
  };

  const refreshUsage = async (): Promise<void> => {
    // TODO: Implement API call to refresh usage data
    if (!isTest) console.log('Refreshing usage data...');
  };

  // ============================================================================
  // Provider-Scoped Entitlements (New - Single Source of Truth)
  // ============================================================================

  // Fetch provider entitlements from backend
  useEffect(() => {
    const loadProviderEntitlements = async () => {
      if (!user || needsOnboarding) {
        setProviderEntitlements(null);
        return;
      }

      try {
        const response = await apiClient.getProviderEntitlements(DEFAULT_PROVIDER);
        if (response.data) {
          setProviderEntitlements(response.data);
          setEntitlementsCache(prev => ({
            ...prev,
            [DEFAULT_PROVIDER]: response.data,
          }));
          if (!isTest) console.log('[Features] Loaded provider entitlements:', response.data);
        }
      } catch (err) {
        if (!isTest) console.warn('[Features] Failed to load provider entitlements:', err);
        // Keep using legacy entitlements on error
      }
    };

    loadProviderEntitlements();
  }, [user, needsOnboarding]);

  /**
   * Check if a feature is enabled for a provider.
   * This is the NEW preferred method for feature gating.
   *
   * @param featureKey - Feature to check (e.g., "github_backup", "promotions")
   * @param providerKey - Provider name (default: "n8n" for MVP)
   * @returns True if feature is enabled
   */
  const hasFeature = (featureKey: string, providerKey: string = DEFAULT_PROVIDER): boolean => {
    // If features failed to load, deny all feature access
    if (error || !features) {
      return false;
    }

    // Get entitlements for the provider
    const ent = providerKey === DEFAULT_PROVIDER
      ? providerEntitlements
      : entitlementsCache[providerKey];

    if (!ent || !ent.has_subscription) {
      // No subscription - fall back to legacy check for backwards compatibility
      return canUseFeature(featureKey as keyof PlanFeatures);
    }

    // Check provider-specific features
    const featureValue = ent.features[featureKey];
    if (typeof featureValue === 'boolean') {
      return featureValue;
    }
    if (typeof featureValue === 'number') {
      return featureValue > 0;
    }

    // Feature not found in provider plan - fall back to legacy
    return canUseFeature(featureKey as keyof PlanFeatures);
  };

  /**
   * Get provider entitlements.
   *
   * @param providerKey - Provider name (default: "n8n")
   * @returns Provider entitlements or null
   */
  const getProviderEntitlements = (providerKey: string = DEFAULT_PROVIDER): ProviderEntitlements | null => {
    if (providerKey === DEFAULT_PROVIDER) {
      return providerEntitlements;
    }
    return entitlementsCache[providerKey] || null;
  };

  /**
   * Check if tenant has a subscription to a provider.
   *
   * @param providerKey - Provider name (default: "n8n")
   * @returns True if tenant has selected/subscribed to this provider
   */
  const hasProviderSubscription = (providerKey: string = DEFAULT_PROVIDER): boolean => {
    const ent = providerKey === DEFAULT_PROVIDER
      ? providerEntitlements
      : entitlementsCache[providerKey];
    return ent?.has_subscription ?? false;
  };

  const value: FeaturesContextValue = {
    planName,
    features,
    usage,
    isLoading,
    error,
    // Legacy methods (backwards compatible)
    canUseFeature,
    hasEntitlement,
    getEntitlementLimit,
    isAtLimit,
    getRequiredPlan,
    refreshUsage,
    // Provider-aware methods (new - single source of truth)
    hasFeature,
    getProviderEntitlements,
    hasProviderSubscription,
    providerEntitlements,
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
