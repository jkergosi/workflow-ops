import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { AuthProvider, useAuth } from '@/lib/auth';
import { FeaturesProvider } from '@/lib/features';
import { ThemeProvider } from '@/components/ThemeProvider';
import { Toaster } from 'sonner';
import { AppLayout } from '@/components/AppLayout';
import { LoginPage } from '@/pages/LoginPage';
import { OnboardingPage } from '@/pages/OnboardingPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { EnvironmentsPage } from '@/pages/EnvironmentsPage';
import { WorkflowsPage } from '@/pages/WorkflowsPage';
import { WorkflowDetailPage } from '@/pages/WorkflowDetailPage';
import { ExecutionsPage } from '@/pages/ExecutionsPage';
import { SnapshotsPage } from '@/pages/SnapshotsPage';
import { DeploymentsPage } from '@/pages/DeploymentsPage';
import { ObservabilityPage } from '@/pages/ObservabilityPage';
import { AlertsPage } from '@/pages/AlertsPage';
import { TeamPage } from '@/pages/TeamPage';
import { BillingPage } from '@/pages/BillingPage';
import { N8NUsersPage } from '@/pages/N8NUsersPage';
import { CredentialsPage } from '@/pages/CredentialsPage';
import { EnvironmentSetupPage } from '@/pages/EnvironmentSetupPage';
import { RestorePage } from '@/pages/RestorePage';
import { ProfilePage } from '@/pages/ProfilePage';
import { PipelinesPage } from '@/pages/PipelinesPage';
import { PipelineEditorPage } from '@/pages/PipelineEditorPage';
import { PromotionPage } from '@/pages/PromotionPage';
import {
  TenantsPage,
  SystemBillingPage,
  PerformancePage,
  AuditLogsPage,
  NotificationsPage,
  SecurityPage,
  SettingsPage,
} from '@/pages/admin';
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { canAccessRoute, mapBackendRoleToFrontendRole } from '@/lib/permissions';

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
  const { isAuthenticated, isLoading, needsOnboarding } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // If user needs onboarding and not already on onboarding page, redirect
    if (!isLoading && needsOnboarding && window.location.pathname !== '/onboarding') {
      navigate('/onboarding');
    }
  }, [isLoading, needsOnboarding, navigate]);

  if (isLoading) {
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
  if (!isAuthenticated && !needsOnboarding) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// Role Protected Route Component - checks role permissions and redirects to dashboard if unauthorized
function RoleProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      const userRole = mapBackendRoleToFrontendRole(user.role);
      const pathname = location.pathname;
      
      // Check if user can access this route
      if (!canAccessRoute(pathname, userRole)) {
        // Redirect to dashboard if unauthorized
        navigate('/', { replace: true });
      }
    }
  }, [user, location.pathname, navigate]);

  // If no user, let ProtectedRoute handle it
  if (!user) {
    return <>{children}</>;
  }

  const userRole = mapBackendRoleToFrontendRole(user.role);
  const canAccess = canAccessRoute(location.pathname, userRole);

  if (!canAccess) {
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

  return <>{children}</>;
}

function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="n8n-ops-theme">
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <FeaturesProvider>
            <BrowserRouter>
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
                <Route path="/" element={<RoleProtectedRoute><DashboardPage /></RoleProtectedRoute>} />
                <Route path="/environments" element={<RoleProtectedRoute><EnvironmentsPage /></RoleProtectedRoute>} />
                <Route path="/environments/new" element={<RoleProtectedRoute><EnvironmentSetupPage /></RoleProtectedRoute>} />
                <Route path="/environments/:id/edit" element={<RoleProtectedRoute><EnvironmentSetupPage /></RoleProtectedRoute>} />
                <Route path="/environments/:id/restore" element={<RoleProtectedRoute><RestorePage /></RoleProtectedRoute>} />
                <Route path="/workflows" element={<RoleProtectedRoute><WorkflowsPage /></RoleProtectedRoute>} />
                <Route path="/workflows/:id" element={<RoleProtectedRoute><WorkflowDetailPage /></RoleProtectedRoute>} />
                <Route path="/executions" element={<RoleProtectedRoute><ExecutionsPage /></RoleProtectedRoute>} />
                <Route path="/snapshots" element={<RoleProtectedRoute><SnapshotsPage /></RoleProtectedRoute>} />
                <Route path="/deployments" element={<RoleProtectedRoute><DeploymentsPage /></RoleProtectedRoute>} />
                <Route path="/pipelines" element={<RoleProtectedRoute><PipelinesPage /></RoleProtectedRoute>} />
                <Route path="/pipelines/new" element={<RoleProtectedRoute><PipelineEditorPage /></RoleProtectedRoute>} />
                <Route path="/pipelines/:id" element={<RoleProtectedRoute><PipelineEditorPage /></RoleProtectedRoute>} />
                <Route path="/promote" element={<RoleProtectedRoute><PromotionPage /></RoleProtectedRoute>} />
                <Route path="/observability" element={<RoleProtectedRoute><ObservabilityPage /></RoleProtectedRoute>} />
                <Route path="/alerts" element={<RoleProtectedRoute><AlertsPage /></RoleProtectedRoute>} />
                <Route path="/n8n-users" element={<RoleProtectedRoute><N8NUsersPage /></RoleProtectedRoute>} />
                <Route path="/credentials" element={<RoleProtectedRoute><CredentialsPage /></RoleProtectedRoute>} />
                <Route path="/team" element={<RoleProtectedRoute><TeamPage /></RoleProtectedRoute>} />
                <Route path="/billing" element={<RoleProtectedRoute><BillingPage /></RoleProtectedRoute>} />
                <Route path="/profile" element={<RoleProtectedRoute><ProfilePage /></RoleProtectedRoute>} />
                {/* Admin Routes */}
                <Route path="/admin/tenants" element={<RoleProtectedRoute><TenantsPage /></RoleProtectedRoute>} />
                <Route path="/admin/billing" element={<RoleProtectedRoute><SystemBillingPage /></RoleProtectedRoute>} />
                <Route path="/admin/performance" element={<RoleProtectedRoute><PerformancePage /></RoleProtectedRoute>} />
                <Route path="/admin/audit-logs" element={<RoleProtectedRoute><AuditLogsPage /></RoleProtectedRoute>} />
                <Route path="/admin/notifications" element={<RoleProtectedRoute><NotificationsPage /></RoleProtectedRoute>} />
                <Route path="/admin/security" element={<RoleProtectedRoute><SecurityPage /></RoleProtectedRoute>} />
                <Route path="/admin/settings" element={<RoleProtectedRoute><SettingsPage /></RoleProtectedRoute>} />
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
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;
