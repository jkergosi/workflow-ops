/**
 * Workflow Action Policy - Pure functions for determining workflow actions based on environment
 *
 * CRITICAL: Use getWorkflowActionPolicy() (pure function) inside event handlers.
 *           Use useWorkflowActionPolicy() (hook) only at component level.
 */

import type { Environment, EnvironmentClass } from '@/types';

export type DeleteMode = 'soft' | 'hard' | 'none';

export interface WorkflowActionPolicy {
  canViewDetails: boolean;
  canOpenInN8N: boolean;
  canCreateDeployment: boolean;
  canEditDirectly: boolean;
  canSoftDelete: boolean;        // Archive/hide workflow
  canHardDelete: boolean;        // Permanently remove (admin-only with confirmation)
  canCreateDriftIncident: boolean;
  driftIncidentRequired: boolean; // Agency+: must create incident to resolve drift
  editRequiresConfirmation: boolean;
  editRequiresAdmin: boolean;
}

/**
 * Legacy type inference - only used for migration from existing data without environmentClass.
 * DEPRECATED: Use environmentClass field directly.
 */
export function inferEnvironmentClass(legacyType?: string): EnvironmentClass {
  console.warn('inferEnvironmentClass: Legacy type field used. Migrate to environmentClass.');
  if (!legacyType) return 'dev'; // Safe default
  const normalized = legacyType.toLowerCase();

  if (normalized.includes('prod') || normalized === 'live') return 'production';
  if (normalized.includes('stag') || normalized === 'uat') return 'staging';
  return 'dev';
}

// Policy matrix cache - loaded from API
let POLICY_MATRIX_CACHE: Record<EnvironmentClass, WorkflowActionPolicy> = {
  dev: {
    canViewDetails: true,
    canOpenInN8N: true,
    canCreateDeployment: true,
    canEditDirectly: true,
    canSoftDelete: true,
    canHardDelete: false,
    canCreateDriftIncident: true,
    driftIncidentRequired: false,
    editRequiresConfirmation: false,
    editRequiresAdmin: false,
  },
  staging: {
    canViewDetails: true,
    canOpenInN8N: true,
    canCreateDeployment: true,
    canEditDirectly: true,
    canSoftDelete: false,
    canHardDelete: false,
    canCreateDriftIncident: true,
    driftIncidentRequired: false,
    editRequiresConfirmation: true,
    editRequiresAdmin: true,
  },
  production: {
    canViewDetails: true,
    canOpenInN8N: true,
    canCreateDeployment: true,
    canEditDirectly: false,
    canSoftDelete: false,
    canHardDelete: false,
    canCreateDriftIncident: true,
    driftIncidentRequired: true,
    editRequiresConfirmation: false,
    editRequiresAdmin: false,
  },
};

// Plan policy overrides cache
let PLAN_POLICY_OVERRIDES_CACHE: Record<string, Partial<WorkflowActionPolicy>> = {};

// Load policy matrix from API
export async function loadWorkflowPolicyMatrix() {
  try {
    const { apiClient } = await import('./api-client');
    const matrixResponse = await apiClient.getWorkflowPolicyMatrix();
    const overridesResponse = await apiClient.getPlanPolicyOverrides();
    
    // Update matrix cache
    for (const row of matrixResponse.data || []) {
      const envClass = row.environment_class as EnvironmentClass;
      if (envClass) {
        // Use existing cache values as fallback to preserve hard-coded defaults
        const existingPolicy = POLICY_MATRIX_CACHE[envClass];
        POLICY_MATRIX_CACHE[envClass] = {
          canViewDetails: row.can_view_details ?? existingPolicy.canViewDetails,
          canOpenInN8N: row.can_open_in_n8n ?? existingPolicy.canOpenInN8N,
          canCreateDeployment: row.can_create_deployment ?? existingPolicy.canCreateDeployment,
          canEditDirectly: row.can_edit_directly ?? existingPolicy.canEditDirectly,
          canSoftDelete: row.can_soft_delete ?? existingPolicy.canSoftDelete,
          canHardDelete: row.can_hard_delete ?? existingPolicy.canHardDelete,
          canCreateDriftIncident: row.can_create_drift_incident ?? existingPolicy.canCreateDriftIncident,
          driftIncidentRequired: row.drift_incident_required ?? existingPolicy.driftIncidentRequired,
          editRequiresConfirmation: row.edit_requires_confirmation ?? existingPolicy.editRequiresConfirmation,
          editRequiresAdmin: row.edit_requires_admin ?? existingPolicy.editRequiresAdmin,
        };
      }
    }
    
    // Update overrides cache
    PLAN_POLICY_OVERRIDES_CACHE = {};
    for (const override of overridesResponse.data || []) {
      const key = `${override.plan_name}:${override.environment_class}`;
      PLAN_POLICY_OVERRIDES_CACHE[key] = {
        canEditDirectly: override.can_edit_directly ?? undefined,
        canSoftDelete: override.can_soft_delete ?? undefined,
        canHardDelete: override.can_hard_delete ?? undefined,
        canCreateDriftIncident: override.can_create_drift_incident ?? undefined,
        driftIncidentRequired: override.drift_incident_required ?? undefined,
        editRequiresConfirmation: override.edit_requires_confirmation ?? undefined,
        editRequiresAdmin: override.edit_requires_admin ?? undefined,
      };
    }
  } catch (error) {
    console.warn('Failed to load workflow policy matrix from API, using defaults:', error);
  }
}

/**
 * Pure function to compute workflow action policy.
 * USE THIS inside event handlers (not hooks).
 *
 * @param environment - The current environment (or null)
 * @param planName - The tenant's subscription plan
 * @param userRole - The user's role
 * @param hasDrift - Whether the workflow has drift
 * @returns The computed policy
 */
export function getWorkflowActionPolicy(
  environment: Environment | null,
  planName: string,
  userRole: string,
  hasDrift: boolean
): WorkflowActionPolicy {
  // Use environmentClass if available, otherwise infer from legacy type field
  const envClass: EnvironmentClass = environment?.environmentClass ||
    inferEnvironmentClass(environment?.type);

  const basePolicy = { ...POLICY_MATRIX_CACHE[envClass] };
  const planTier = planName.toLowerCase();
  const isAgencyPlus = planTier === 'agency' || planTier === 'agency_plus' || planTier === 'enterprise';
  const isAdmin = userRole === 'admin' || userRole === 'platform_admin' || userRole === 'superuser' || userRole === 'super_admin';

  // =============================================
  // PLAN-BASED RESTRICTIONS (from database)
  // =============================================
  
  // Check for plan-based override from database
  const overrideKey = `${planTier}:${envClass}`;
  const planOverride = PLAN_POLICY_OVERRIDES_CACHE[overrideKey];
  if (planOverride) {
    if (typeof planOverride.canEditDirectly === 'boolean') {
      basePolicy.canEditDirectly = planOverride.canEditDirectly;
    }
    if (typeof planOverride.canSoftDelete === 'boolean') {
      basePolicy.canSoftDelete = planOverride.canSoftDelete;
    }
    if (typeof planOverride.canHardDelete === 'boolean') {
      basePolicy.canHardDelete = planOverride.canHardDelete;
    }
    if (typeof planOverride.canCreateDriftIncident === 'boolean') {
      basePolicy.canCreateDriftIncident = planOverride.canCreateDriftIncident;
    }
    if (typeof planOverride.driftIncidentRequired === 'boolean') {
      basePolicy.driftIncidentRequired = planOverride.driftIncidentRequired;
    }
    if (typeof planOverride.editRequiresConfirmation === 'boolean') {
      basePolicy.editRequiresConfirmation = planOverride.editRequiresConfirmation;
    }
    if (typeof planOverride.editRequiresAdmin === 'boolean') {
      basePolicy.editRequiresAdmin = planOverride.editRequiresAdmin;
    }
  } else {
    // Fallback to hard-coded logic if no database override
    // Free tier: No drift incident workflow at all
    if (planTier === 'free') {
      basePolicy.canCreateDriftIncident = false;
      basePolicy.driftIncidentRequired = false;
    }

    // Pro tier: Drift incidents optional (not required)
    if (planTier === 'pro') {
      basePolicy.driftIncidentRequired = false;
    }

    // Agency+: Drift incidents required by default in staging/production
    if (isAgencyPlus) {
      if (envClass === 'staging') {
        basePolicy.canEditDirectly = false; // Even stricter for agency+
        basePolicy.driftIncidentRequired = true;
      }
      // Production already has driftIncidentRequired = true
    }
  }

  // =============================================
  // ROLE-BASED RESTRICTIONS
  // =============================================

  // Admin-gated actions
  if (basePolicy.editRequiresAdmin && !isAdmin) {
    basePolicy.canEditDirectly = false;
  }

  // Hard delete: Admin-only in dev, never elsewhere
  if (envClass === 'dev' && isAdmin) {
    basePolicy.canHardDelete = true; // Unlocks "Permanently delete" option
  }

  // =============================================
  // ENVIRONMENT-SPECIFIC OVERRIDES
  // =============================================

  // Dev environments: Never require confirmation for direct edits
  // (dev environments don't have drift since they are the source of truth)
  if (envClass === 'dev') {
    basePolicy.editRequiresConfirmation = false;
  }

  // =============================================
  // DRIFT STATE RESTRICTIONS
  // =============================================

  // Drift incident only if drift exists
  if (!hasDrift) {
    basePolicy.canCreateDriftIncident = false;
    basePolicy.driftIncidentRequired = false;
  }

  return basePolicy;
}
