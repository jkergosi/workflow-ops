import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { AuthProvider, useAuth } from '@/lib/auth';
import { FeaturesProvider, useFeatures } from '@/lib/features';
import { ThemeProvider } from '@/components/ThemeProvider';
import { Toaster, toast } from 'sonner';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { ServiceStatusIndicator } from '@/components/ServiceStatusIndicator';
import { RouteTracker } from '@/components/RouteTracker';
import { useEffect, useState } from 'react';
import { AppLayout } from '@/components/AppLayout';
import { LoginPage } from '@/pages/LoginPage';
import { OnboardingPage } from '@/pages/OnboardingPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { EnvironmentsPage } from '@/pages/EnvironmentsPage';
import { EnvironmentDetailPage } from '@/pages/EnvironmentDetailPage';
import { WorkflowsPage } from '@/pages/WorkflowsPage';
import { WorkflowDetailPage } from '@/pages/WorkflowDetailPage';
import { ExecutionsPage } from '@/pages/ExecutionsPage';
import { SnapshotsPage } from '@/pages/SnapshotsPage';
import { DeploymentsPage } from '@/pages/DeploymentsPage';
import { DeploymentDetailPage } from '@/pages/DeploymentDetailPage';
import { ObservabilityPage } from '@/pages/ObservabilityPage';
import { AlertsPage } from '@/pages/AlertsPage';
import { ActivityCenterPage } from '@/pages/ActivityCenterPage';
import { ActivityDetailPage } from '@/pages/ActivityDetailPage';
import { TeamPage } from '@/pages/TeamPage';
import { BillingPage } from '@/pages/BillingPage';
import { N8NUsersPage } from '@/pages/N8NUsersPage';
import { CredentialsPage } from '@/pages/CredentialsPage';
import { IncidentsPage } from '@/pages/IncidentsPage';
import { IncidentDetailPage } from '@/pages/IncidentDetailPage';
import { DriftDashboardPage } from '@/pages/DriftDashboardPage';
import { EnvironmentSetupPage } from '@/pages/EnvironmentSetupPage';
import { RestorePage } from '@/pages/RestorePage';
import { ProfilePage } from '@/pages/ProfilePage';
import { PipelineEditorPage } from '@/pages/PipelineEditorPage';
import { PromotePage } from '@/pages/PromotePage';
import { CanonicalOnboardingPage } from '@/pages/CanonicalOnboardingPage';
import { CanonicalWorkflowsPage } from '@/pages/CanonicalWorkflowsPage';
import {
  TenantsPage,
  TenantDetailPage,
  PlatformSettingsPage,
  TenantSettingsPage,
  TenantOverridesPage,
  EntitlementsAuditPage,
  CredentialHealthPage,
  AdminDashboardPage,
  TenantProvidersPage,
  FeatureMatrixPage,
} from '@/pages/admin';
import {
  SupportHomePage,
  ReportBugPage,
  RequestFeaturePage,
  GetHelpPage,
} from '@/pages/support';
import { useLocation } from 'react-router-dom';
import { canAccessRoute, mapBackendRoleToFrontendRole, normalizePlan, isAtLeastPlan, type Plan } from '@/lib/permissions';
import { setLastRoute } from '@/lib/lastRoute';
import { AdminUsagePage } from '@/pages/AdminUsagePage';
import { AdminEntitlementsPage } from '@/pages/AdminEntitlementsPage';
import { PlatformAdminsPage } from '@/pages/platform/PlatformAdminsPage';
import { SupportConsolePage } from '@/pages/platform/SupportConsolePage';
import { PlatformDashboardPage } from '@/pages/platform/PlatformDashboardPage';
import { PlatformTenantUsersRolesPage } from '@/pages/platform/PlatformTenantUsersRolesPage';
import { UpgradeRequiredModal } from '@/components/upsell/UpgradeRequiredModal';

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
});

// Protected Route Component with Onboarding Check
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, initComplete, needsOnboarding } = useAuth();
  const navigate = useNavigate();
  const currentPath = window.location.pathname;

  // Debug logging
  console.log('[ProtectedRoute] Render:', { currentPath, isAuthenticated, isLoading, initComplete, needsOnboarding });

  useEffect(() => {
    // If user needs onboarding and not already on onboarding page, redirect
    if (!isLoading && initComplete && needsOnboarding && window.location.pathname !== '/onboarding') {
      console.log('[ProtectedRoute] Redirecting to onboarding');
      navigate('/onboarding', { replace: true });
    }
  }, [isLoading, initComplete, needsOnboarding, navigate]);

  // Wait for both loading to complete AND initialization to be done
  // This prevents redirects during the brief moment between state updates
  if (isLoading || !initComplete) {
    console.log('[ProtectedRoute] Showing loading spinner');
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]"></div>
          <p className="mt-4 text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Check if user is authenticated (login completed)
  // isAuthenticated is true when user is logged in AND has completed onboarding
  // Only redirect if we're not already on login or onboarding page to prevent loops
  if (!isAuthenticated && !needsOnboarding && currentPath !== '/login' && currentPath !== '/onboarding') {
    console.log('[ProtectedRoute] Not authenticated, redirecting to login');
    return <Navigate to="/login" replace />;
  }

  console.log('[ProtectedRoute] Rendering children');
  return <>{children}</>;
}

// Role Protected Route Component - checks role permissions and redirects to dashboard if unauthorized
function RoleProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Get planName from FeaturesProvider - use default if not available (shouldn't happen but safety check)
  let planName = 'free';
  try {
    const features = useFeatures();
    planName = features.planName;
  } catch (error) {
    // FeaturesProvider not available - this shouldn't happen but handle gracefully
    console.warn('[RoleProtectedRoute] FeaturesProvider not available, using default plan');
  }

  const effectiveRole = user
    ? ((user as any)?.isPlatformAdmin ? 'platform_admin' : mapBackendRoleToFrontendRole(user.role))
    : null;
  const plan = normalizePlan(planName);
  const canAccess = user ? canAccessRoute(location.pathname, effectiveRole!, plan) : true;

  console.log('[RoleProtectedRoute] Render:', {
    pathname: location.pathname,
    hasUser: !!user,
    userRole: effectiveRole,
    plan: plan,
    canAccess
  });

  useEffect(() => {
    if (user) {
      const role = (user as any)?.isPlatformAdmin ? 'platform_admin' : mapBackendRoleToFrontendRole(user.role);
      const pathname = location.pathname;

      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/35363e7c-4fd6-4b04-adaf-3a3d3056abb3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:142',message:'RoleProtectedRoute useEffect - checking access',data:{pathname,role,plan,userRole:user.role,isPlatformAdmin:(user as any)?.isPlatformAdmin},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion

      const hasAccess = canAccessRoute(pathname, role, plan);
      
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/35363e7c-4fd6-4b04-adaf-3a3d3056abb3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:148',message:'canAccessRoute result',data:{pathname,role,plan,hasAccess},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
      // #endregion

      // Check if user can access this route
      if (!hasAccess) {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/35363e7c-4fd6-4b04-adaf-3a3d3056abb3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'App.tsx:151',message:'Redirecting to dashboard - unauthorized',data:{pathname,role,plan},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
        // #endregion
        console.log('[RoleProtectedRoute] Redirecting to dashboard - unauthorized');
        // Redirect to dashboard if unauthorized
        navigate('/', { replace: true });
      }
    }
  }, [user, location.pathname, navigate, plan]);

  // If no user, let ProtectedRoute handle it
  if (!user) {
    console.log('[RoleProtectedRoute] No user, rendering children');
    return <>{children}</>;
  }

  if (!canAccess) {
    console.log('[RoleProtectedRoute] Cannot access, showing redirect spinner');
    // Show loading while redirecting
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]"></div>
          <p className="mt-4 text-muted-foreground">Redirecting...</p>
        </div>
      </div>
    );
  }

  console.log('[RoleProtectedRoute] Rendering children');
  return <>{children}</>;
}

function LegacyPlatformTenantRedirect() {
  const { tenantId } = useParams();
  if (!tenantId) return <Navigate to="/platform/tenants" replace />;
  return <Navigate to={`/platform/tenants/${tenantId}`} replace />;
}

// Plan Protected Route Component - shows upgrade modal if plan insufficient
function PlanProtectedRoute({ 
  children, 
  minPlan, 
  featureName, 
  benefits 
}: { 
  children: React.ReactNode;
  minPlan: Plan;
  featureName: string;
  benefits: string[];
}) {
  const { planName } = useFeatures();
  const [showModal, setShowModal] = useState(false);
  const normalizedPlan = normalizePlan(planName);
  const hasAccess = isAtLeastPlan(normalizedPlan, minPlan);

  useEffect(() => {
    if (!hasAccess) {
      setShowModal(true);
    }
  }, [hasAccess]);

  if (!hasAccess) {
    return (
      <>
        <UpgradeRequiredModal
          open={showModal}
          onOpenChange={setShowModal}
          requiredPlan={minPlan === 'agency' || minPlan === 'agency_plus' ? 'agency' : minPlan === 'pro' ? 'pro' : 'enterprise'}
          featureName={featureName}
          benefits={benefits}
        />
        {null}
      </>
    );
  }

  return <>{children}</>;
}

function App() {
  // Listen for service recovery notifications
  useEffect(() => {
    const handleServiceRecovery = (event: CustomEvent) => {
      const { from, to } = event.detail;
      if (from === 'unhealthy' && (to === 'healthy' || to === 'degraded')) {
        toast.success('Service recovered', {
          description: to === 'healthy' 
            ? 'All systems are now operational' 
            : 'Some services have recovered',
          duration: 5000,
        });
      }
    };

    window.addEventListener('service-recovered', handleServiceRecovery as EventListener);
    return () => {
      window.removeEventListener('service-recovered', handleServiceRecovery as EventListener);
    };
  }, []);

  return (
    <ThemeProvider defaultTheme="system" storageKey="n8n-ops-theme">
      <QueryClientProvider client={queryClient}>
        <ErrorBoundary showDetails={true}>
          <AuthProvider>
            <FeaturesProvider>
              <BrowserRouter>
                {/* Route Tracker - tracks lastRoute for navigation persistence */}
                <RouteTracker />
                {/* Service Status Indicator - shows when services are unhealthy */}
                <ServiceStatusIndicator position="fixed" />
                <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/onboarding"
                element={
                  <ProtectedRoute>
                    <OnboardingPage />
                  </ProtectedRoute>
                }
              />
              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                {/* Operations */}
                <Route path="/dashboard" element={<Navigate to="/" replace />} />
                <Route path="/" element={<RoleProtectedRoute><DashboardPage /></RoleProtectedRoute>} />
                <Route path="/environments" element={<RoleProtectedRoute><EnvironmentsPage /></RoleProtectedRoute>} />
                <Route path="/environments/new" element={<RoleProtectedRoute><EnvironmentSetupPage /></RoleProtectedRoute>} />
                <Route path="/environments/:id" element={<RoleProtectedRoute><EnvironmentDetailPage /></RoleProtectedRoute>} />
                <Route path="/environments/:id/edit" element={<RoleProtectedRoute><EnvironmentSetupPage /></RoleProtectedRoute>} />
                <Route path="/environments/:id/restore" element={<RoleProtectedRoute><RestorePage /></RoleProtectedRoute>} />
                <Route path="/workflows" element={<RoleProtectedRoute><WorkflowsPage /></RoleProtectedRoute>} />
                <Route path="/workflows/:id" element={<RoleProtectedRoute><WorkflowDetailPage /></RoleProtectedRoute>} />
                <Route path="/executions" element={<RoleProtectedRoute><ExecutionsPage /></RoleProtectedRoute>} />
                <Route path="/snapshots" element={<RoleProtectedRoute><SnapshotsPage /></RoleProtectedRoute>} />
                <Route path="/deployments" element={<RoleProtectedRoute><DeploymentsPage /></RoleProtectedRoute>} />
                <Route path="/deployments/:id" element={<RoleProtectedRoute><DeploymentDetailPage /></RoleProtectedRoute>} />
                <Route path="/pipelines" element={<Navigate to="/deployments?tab=pipelines" replace />} />
                <Route path="/pipelines/new" element={<RoleProtectedRoute><PipelineEditorPage /></RoleProtectedRoute>} />
                <Route path="/pipelines/:id" element={<RoleProtectedRoute><PipelineEditorPage /></RoleProtectedRoute>} />
                <Route path="/promote" element={<RoleProtectedRoute><PromotePage /></RoleProtectedRoute>} />
                <Route path="/deployments/new" element={<Navigate to="/promote" replace />} />
                <Route path="/canonical/onboarding" element={<RoleProtectedRoute><CanonicalOnboardingPage /></RoleProtectedRoute>} />
                <Route path="/canonical/workflows" element={<RoleProtectedRoute><CanonicalWorkflowsPage /></RoleProtectedRoute>} />
                <Route path="/observability" element={<RoleProtectedRoute><ObservabilityPage /></RoleProtectedRoute>} />
                <Route path="/alerts" element={<RoleProtectedRoute><AlertsPage /></RoleProtectedRoute>} />
                <Route path="/activity" element={<RoleProtectedRoute><ActivityCenterPage /></RoleProtectedRoute>} />
                <Route path="/activity/:id" element={<RoleProtectedRoute><ActivityDetailPage /></RoleProtectedRoute>} />
                <Route path="/n8n-users" element={<RoleProtectedRoute><N8NUsersPage /></RoleProtectedRoute>} />
                <Route path="/credentials" element={<RoleProtectedRoute><CredentialsPage /></RoleProtectedRoute>} />
                <Route path="/incidents" element={<RoleProtectedRoute><IncidentsPage /></RoleProtectedRoute>} />
                <Route path="/incidents/:id" element={<RoleProtectedRoute><IncidentDetailPage /></RoleProtectedRoute>} />
                <Route path="/drift-dashboard" element={<RoleProtectedRoute><DriftDashboardPage /></RoleProtectedRoute>} />

                {/* Org Admin */}
                <Route path="/admin" element={<RoleProtectedRoute><AdminDashboardPage /></RoleProtectedRoute>} />
                <Route path="/admin/members" element={<RoleProtectedRoute><TeamPage /></RoleProtectedRoute>} />
                <Route path="/admin/plans" element={<RoleProtectedRoute><Navigate to="/admin/providers" replace /></RoleProtectedRoute>} />
                <Route path="/admin/billing" element={<RoleProtectedRoute><Navigate to="/admin/providers" replace /></RoleProtectedRoute>} />
                <Route 
                  path="/admin/usage" 
                  element={
                    <RoleProtectedRoute>
                      <PlanProtectedRoute 
                        minPlan="pro" 
                        featureName="Usage Analytics" 
                        benefits={[
                          'Detailed usage metrics and analytics',
                          'Track resource consumption across environments',
                          'Monitor usage trends and patterns'
                        ]}
                      >
                        <AdminUsagePage />
                      </PlanProtectedRoute>
                    </RoleProtectedRoute>
                  } 
                />
                <Route path="/platform/feature-matrix" element={<RoleProtectedRoute><FeatureMatrixPage /></RoleProtectedRoute>} />
                <Route path="/platform/entitlements" element={<RoleProtectedRoute><AdminEntitlementsPage /></RoleProtectedRoute>} />
                <Route 
                  path="/admin/credential-health" 
                  element={
                    <RoleProtectedRoute>
                      <PlanProtectedRoute 
                        minPlan="pro" 
                        featureName="Credential Health" 
                        benefits={[
                          'Monitor credential status and health',
                          'Track credential usage across environments',
                          'Get alerts for credential issues'
                        ]}
                      >
                        <CredentialHealthPage />
                      </PlanProtectedRoute>
                    </RoleProtectedRoute>
                  } 
                />
                <Route path="/admin/settings" element={<RoleProtectedRoute><TenantSettingsPage /></RoleProtectedRoute>} />
                <Route path="/admin/providers" element={<RoleProtectedRoute><TenantProvidersPage /></RoleProtectedRoute>} />

                {/* Platform (Platform Admin Only) */}
                <Route path="/platform" element={<RoleProtectedRoute><PlatformDashboardPage /></RoleProtectedRoute>} />
                <Route path="/platform/tenants" element={<RoleProtectedRoute><TenantsPage /></RoleProtectedRoute>} />
                <Route path="/platform/tenants/:tenantId" element={<RoleProtectedRoute><TenantDetailPage /></RoleProtectedRoute>} />
                <Route path="/platform/tenants/:tenantId/users" element={<RoleProtectedRoute><PlatformTenantUsersRolesPage /></RoleProtectedRoute>} />
                <Route path="/platform/support" element={<RoleProtectedRoute><SupportConsolePage /></RoleProtectedRoute>} />
                <Route path="/platform/tenant-overrides" element={<RoleProtectedRoute><TenantOverridesPage /></RoleProtectedRoute>} />
                <Route path="/platform/entitlements-audit" element={<RoleProtectedRoute><EntitlementsAuditPage /></RoleProtectedRoute>} />
                <Route path="/platform/admins" element={<RoleProtectedRoute><PlatformAdminsPage /></RoleProtectedRoute>} />
                <Route path="/platform/settings" element={<RoleProtectedRoute><PlatformSettingsPage /></RoleProtectedRoute>} />

                {/* Platform legacy redirects */}
                <Route path="/platform/console" element={<Navigate to="/platform/support" replace />} />
                <Route path="/platform/support/requests" element={<Navigate to="/platform/support?tab=requests" replace />} />
                <Route path="/platform/support/config" element={<Navigate to="/platform/support?tab=config" replace />} />

                {/* Legacy redirects */}
                <Route path="/team" element={<Navigate to="/admin/members" replace />} />
                <Route path="/billing" element={<Navigate to="/admin/providers" replace />} />
                <Route path="/admin/tenants" element={<Navigate to="/platform/tenants" replace />} />
                <Route path="/admin/tenants/:tenantId" element={<RoleProtectedRoute><LegacyPlatformTenantRedirect /></RoleProtectedRoute>} />
                <Route path="/admin/entitlements/overrides" element={<Navigate to="/platform/tenant-overrides" replace />} />
                <Route path="/admin/entitlements/audit" element={<Navigate to="/platform/entitlements-audit" replace />} />
                <Route path="/admin/entitlements-audit" element={<Navigate to="/platform/entitlements-audit" replace />} />
                <Route path="/admin/support" element={<Navigate to="/platform/support?tab=requests" replace />} />
                <Route path="/admin/support-config" element={<Navigate to="/platform/support?tab=config" replace />} />
                <Route path="/admin/audit-logs" element={<Navigate to="/platform/entitlements-audit" replace />} />
                <Route path="/admin/entitlements/matrix" element={<Navigate to="/platform/feature-matrix" replace />} />
                <Route path="/admin/feature-matrix" element={<Navigate to="/platform/feature-matrix" replace />} />
                <Route path="/admin/entitlements" element={<Navigate to="/platform/entitlements" replace />} />
                <Route path="/admin/plans-old" element={<Navigate to="/platform/tenants" replace />} />
                <Route path="/admin/usage-old" element={<Navigate to="/platform/tenants" replace />} />
                <Route path="/admin/billing-old" element={<Navigate to="/platform/tenants" replace />} />

                <Route path="/profile" element={<RoleProtectedRoute><ProfilePage /></RoleProtectedRoute>} />
                {/* Support Routes */}
                <Route path="/support" element={<RoleProtectedRoute><SupportHomePage /></RoleProtectedRoute>} />
                <Route path="/support/bug/new" element={<RoleProtectedRoute><ReportBugPage /></RoleProtectedRoute>} />
                <Route path="/support/feature/new" element={<RoleProtectedRoute><RequestFeaturePage /></RoleProtectedRoute>} />
                <Route path="/support/help/new" element={<RoleProtectedRoute><GetHelpPage /></RoleProtectedRoute>} />
              </Route>
              </Routes>
            </BrowserRouter>
            <Toaster
              position="top-right"
              expand={true}
              richColors={false}
              toastOptions={{
                classNames: {
                  toast: '!rounded-lg !shadow-lg !border-l-4 !font-medium !px-4 !py-3 !text-sm',
                  success: '!bg-green-50 dark:!bg-green-950/90 !text-green-900 dark:!text-green-50 !border-green-500',
                  error: '!bg-red-50 dark:!bg-red-950/90 !text-red-900 dark:!text-red-50 !border-red-500',
                },
              }}
            />
          </FeaturesProvider>
        </AuthProvider>
      </ErrorBoundary>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;
