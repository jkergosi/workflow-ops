/**
 * Last Route Persistence Utility
 * 
 * Stores the last meaningful route in localStorage to preserve user intent
 * over plan-based defaults after first navigation.
 */

const LAST_ROUTE_KEY = 'last_route';

/**
 * Routes to exclude from lastRoute tracking
 */
const EXCLUDED_ROUTES = [
  '/login',
  '/onboarding',
  '/auth',
  '/dev',
];

/**
 * Check if a route should be excluded from tracking
 */
function shouldExcludeRoute(pathname: string): boolean {
  return EXCLUDED_ROUTES.some(excluded => pathname.startsWith(excluded));
}

/**
 * Get the last stored route
 */
export function getLastRoute(): string | null {
  try {
    const stored = localStorage.getItem(LAST_ROUTE_KEY);
    if (!stored) return null;
    
    // Validate it's not an excluded route
    if (shouldExcludeRoute(stored)) {
      localStorage.removeItem(LAST_ROUTE_KEY);
      return null;
    }
    
    return stored;
  } catch (error) {
    console.warn('Failed to get last route:', error);
    return null;
  }
}

/**
 * Store the last route (if it's not excluded)
 */
export function setLastRoute(pathname: string): void {
  try {
    if (shouldExcludeRoute(pathname)) {
      return;
    }
    
    localStorage.setItem(LAST_ROUTE_KEY, pathname);
  } catch (error) {
    console.warn('Failed to set last route:', error);
  }
}

/**
 * Clear the last route
 */
export function clearLastRoute(): void {
  try {
    localStorage.removeItem(LAST_ROUTE_KEY);
  } catch (error) {
    console.warn('Failed to clear last route:', error);
  }
}

