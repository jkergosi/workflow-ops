/**
 * Lifecycle stage definitions for Workflow Ops frontend.
 *
 * These stages represent the journey of a workflow through the platform.
 * Note: AUTHORING is not included as it happens in n8n, outside Workflow Ops.
 */
export const LifecycleStage = {
  INGEST: 'ingest',
  SNAPSHOT: 'snapshot',
  PROMOTION: 'promotion',
  DRIFT: 'drift',
  RECONCILIATION: 'reconciliation',
  OBSERVABILITY: 'observability',
} as const;

export type LifecycleStage = typeof LifecycleStage[keyof typeof LifecycleStage];

/**
 * Drift mode definitions for frontend.
 */
export const DriftMode = {
  PASSIVE: 'passive',
  MANAGED: 'managed',
  ENFORCED: 'enforced',
} as const;

export type DriftMode = typeof DriftMode[keyof typeof DriftMode];

/**
 * Plan-based drift mode mapping.
 */
export const PLAN_DRIFT_MODE: Record<string, DriftMode> = {
  free: DriftMode.PASSIVE,
  pro: DriftMode.PASSIVE,
  agency: DriftMode.MANAGED,
  enterprise: DriftMode.ENFORCED,
};

/**
 * Get drift mode for a plan.
 */
export function getDriftModeForPlan(planName: string): DriftMode {
  const planLower = planName?.toLowerCase() || 'free';
  return PLAN_DRIFT_MODE[planLower] || DriftMode.PASSIVE;
}

/**
 * Check if drift incidents can be created in the given drift mode.
 */
export function canCreateDriftIncident(driftMode: DriftMode): boolean {
  return driftMode === DriftMode.MANAGED || driftMode === DriftMode.ENFORCED;
}

