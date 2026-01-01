import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { setLastRoute } from '@/lib/lastRoute';

/**
 * RouteTracker component - tracks route changes and updates lastRoute
 * This should be placed inside BrowserRouter to track all navigation
 */
export function RouteTracker() {
  const location = useLocation();

  useEffect(() => {
    // Update lastRoute whenever the route changes
    setLastRoute(location.pathname);
  }, [location.pathname]);

  return null;
}

