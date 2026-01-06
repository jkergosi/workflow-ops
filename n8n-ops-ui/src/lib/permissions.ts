export type OrgRole = 'viewer' | 'developer' | 'admin';
export type Role = OrgRole | 'platform_admin';
export type Plan = 'free' | 'pro' | 'agency' | 'agency_plus';

const ORG_ROLE_ORDER: Record<OrgRole, number> = {
  viewer: 0,
  developer: 1,
  admin: 2,
};

const PLAN_ORDER: Record<Plan, number> = {
  free: 0,
  pro: 1,
  agency: 2,
  agency_plus: 3,
};

export function normalizePlan(plan: string | undefined | null): Plan {
  const p = (plan || 'free').toLowerCase();
  if (p === 'agency_plus') return 'agency_plus';
  if (p === 'agency') return 'agency';
  if (p === 'pro') return 'pro';
  if (p === 'free') return 'free';
  // Back-compat: existing code often uses "enterprise" where spec says "agency_plus"
  if (p === 'enterprise') return 'agency_plus';
  return 'free';
}

export function isAtLeastPlan(current: Plan, required: Plan): boolean {
  return PLAN_ORDER[current] >= PLAN_ORDER[required];
}

export function isAtLeastOrgRole(current: OrgRole, required: OrgRole): boolean {
  return ORG_ROLE_ORDER[current] >= ORG_ROLE_ORDER[required];
}

type RouteRule = {
  roles: Role[];
  minPlan: Plan; // Free+ default
};

const ROUTE_RULES: Array<{ match: (path: string) => boolean; rule: RouteRule }> = [
  // Platform (hidden) — platform_admin only
  {
    match: (p) => p === '/platform' || p.startsWith('/platform/'),
    rule: { roles: ['platform_admin'], minPlan: 'free' },
  },

  // Org Admin — admin only, with plan-specific routes
  {
    match: (p) => p === '/admin/credential-health' || p.startsWith('/admin/credential-health/'),
    rule: { roles: ['admin'], minPlan: 'pro' },
  },
  {
    match: (p) => p === '/admin/usage' || p.startsWith('/admin/usage/'),
    rule: { roles: ['admin'], minPlan: 'pro' },
  },
  {
    match: (p) => p === '/platform/feature-matrix' || p.startsWith('/platform/feature-matrix/'),
    rule: { roles: ['platform_admin'], minPlan: 'free' }, // Platform admin only - full feature matrix management
  },
  {
    match: (p) => p === '/platform/entitlements' || p.startsWith('/platform/entitlements/'),
    rule: { roles: ['platform_admin'], minPlan: 'free' }, // Platform admin only
  },
  {
    match: (p) => p === '/admin' || p.startsWith('/admin/'),
    rule: { roles: ['admin', 'platform_admin'], minPlan: 'free' },
  },

  // Identity & Secrets
  { match: (p) => p === '/credentials' || p.startsWith('/credentials/'), rule: { roles: ['admin'], minPlan: 'free' } },
  { match: (p) => p === '/n8n-users', rule: { roles: ['admin'], minPlan: 'pro' } },

  // Observability
  { match: (p) => p === '/observability', rule: { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'pro' } },

  // Deployments (requires workflow_ci_cd feature = pro plan)
  { match: (p) => p === '/deployments' || p.startsWith('/deployments/'), rule: { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'pro' } },
  { match: (p) => p === '/promote' || p.startsWith('/promote/'), rule: { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'pro' } },
  { match: (p) => p === '/pipelines' || p.startsWith('/pipelines/'), rule: { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'pro' } },

  // Core Operations (viewer+)
  { match: (p) => p === '/' || p === '/dashboard', rule: { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'free' } },
  { match: (p) => p === '/environments' || p.startsWith('/environments/'), rule: { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'free' } },
  { match: (p) => p === '/workflows' || p.startsWith('/workflows/'), rule: { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'free' } },
  { match: (p) => p === '/executions' || p.startsWith('/executions/'), rule: { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'free' } },
  { match: (p) => p === '/activity' || p.startsWith('/activity/'), rule: { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'free' } },

  // Defaults for other existing routes (keep app usable, but do NOT open admin/platform paths)
  { match: (_p) => true, rule: { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'free' } },
];

function getRuleForPath(pathname: string): RouteRule {
  for (const entry of ROUTE_RULES) {
    if (entry.match(pathname)) {
      return entry.rule;
    }
  }
  return { roles: ['viewer', 'developer', 'admin', 'platform_admin'], minPlan: 'free' };
}

export function canAccessRoute(pathname: string, userRole: Role, plan: Plan): boolean {
  const rule = getRuleForPath(pathname);
  const hasRole = rule.roles.includes(userRole);
  const hasPlan = isAtLeastPlan(plan, rule.minPlan);
  const result = hasRole && hasPlan;
  
  return result;
}

export function canSeePlatformNav(userRole: Role): boolean {
  return userRole === 'platform_admin';
}

export function mapBackendRoleToFrontendRole(backendRole: string | undefined): Role {
  const r = (backendRole || 'viewer').toLowerCase();
  if (r === 'platform_admin') return 'platform_admin';
  // Back-compat: old naming used in parts of the backend
  if (r === 'superuser' || r === 'super_admin') return 'platform_admin';
  if (r === 'admin') return 'admin';
  if (r === 'developer') return 'developer';
  if (r === 'viewer') return 'viewer';
  return 'viewer';
}

