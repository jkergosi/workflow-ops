export type Role = 'user' | 'admin' | 'agency' | 'superuser';

export type MenuItemVisibility = {
  id: string;
  roles: Role[];        // which roles see it
};

export const MENU_VISIBILITY: MenuItemVisibility[] = [
  { id: 'dashboard', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'environments', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'workflows', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'executions', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'pipelines', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'deployments', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'snapshots', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'drift', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'observability', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'alerts', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'credentials', roles: ['user', 'admin', 'agency', 'superuser'] },
  { id: 'users', roles: ['admin', 'agency', 'superuser'] },
  { id: 'tenants', roles: ['admin', 'agency', 'superuser'] },
  { id: 'billing', roles: ['admin', 'agency', 'superuser'] },
  { id: 'auditLogs', roles: ['admin', 'agency', 'superuser'] },
  { id: 'security', roles: ['admin', 'agency', 'superuser'] },
  { id: 'systemSettings', roles: ['admin', 'agency', 'superuser'] },
];

// Route to menu item ID mapping
export const ROUTE_TO_MENU_ID: Record<string, string> = {
  '/': 'dashboard',
  '/environments': 'environments',
  '/workflows': 'workflows',
  '/executions': 'executions',
  '/pipelines': 'pipelines',
  '/deployments': 'deployments',
  '/snapshots': 'snapshots',
  '/drift': 'drift',
  '/observability': 'observability',
  '/admin/notifications': 'alerts',
  '/credentials': 'credentials',
  '/n8n-users': 'users',
  '/admin/tenants': 'tenants',
  '/admin/billing': 'billing',
  '/admin/audit-logs': 'auditLogs',
  '/admin/security': 'security',
  '/admin/settings': 'systemSettings',
};

// Helper function to check if a route is accessible by a role
export function canAccessRoute(pathname: string, userRole: Role): boolean {
  // Superuser can access everything
  if (userRole === 'superuser') {
    return true;
  }

  // Handle dynamic routes by checking the base path
  let routeToCheck = pathname;
  
  // Map dynamic routes to their base paths
  if (pathname.startsWith('/workflows/')) {
    routeToCheck = '/workflows';
  } else if (pathname.startsWith('/environments/')) {
    routeToCheck = '/environments';
  } else if (pathname.startsWith('/pipelines/')) {
    routeToCheck = '/pipelines';
  } else if (pathname.startsWith('/admin/')) {
    // Keep admin routes as-is for specific checks
    routeToCheck = pathname;
  }

  // Get the menu item ID for this route
  const menuId = ROUTE_TO_MENU_ID[routeToCheck];
  if (!menuId) {
    // If route not in mapping, check if it's a profile/team route (usually accessible to all authenticated users)
    if (pathname.startsWith('/profile') || pathname.startsWith('/team') || pathname.startsWith('/billing')) {
      return true;
    }
    // For other unmapped routes, default to accessible
    // You may want to add more specific checks
    return true;
  }

  // Check if the role has access to this menu item
  const visibility = MENU_VISIBILITY.find(v => v.id === menuId);
  if (!visibility) {
    return true; // Default to accessible if not configured
  }

  return visibility.roles.includes(userRole);
}

// Helper function to check if a menu item is visible to a role
export function isMenuItemVisible(itemId: string, userRole: Role): boolean {
  // Superuser can see everything
  if (userRole === 'superuser') {
    return true;
  }

  const visibility = MENU_VISIBILITY.find(v => v.id === itemId);
  if (!visibility) {
    return true; // Default to visible if not configured
  }

  return visibility.roles.includes(userRole);
}

// Map backend roles to frontend roles
export function mapBackendRoleToFrontendRole(backendRole: string | undefined): Role {
  if (!backendRole) return 'user';
  
  // Map existing backend roles to new frontend roles
  switch (backendRole.toLowerCase()) {
    case 'admin':
      return 'admin';
    case 'superuser':
    case 'super_admin':
      return 'superuser';
    case 'agency':
      return 'agency';
    case 'developer':
    case 'viewer':
    default:
      return 'user';
  }
}

