import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { useFeatures } from '@/lib/features';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Workflow } from 'lucide-react';

/**
 * Get plan-based default landing page.
 * Based on reqs/lifecycle.md Phase 5:
 * - Free: Environments / Workflows
 * - Pro: Snapshots
 * - Agency: Pipelines (Deployments)
 * - Enterprise: Drift Dashboard
 */
function getDefaultLandingPage(planName: string | null): string {
  if (!planName) return '/environments';
  
  const planLower = planName.toLowerCase();
  switch (planLower) {
    case 'free':
      return '/environments'; // Environments / Workflows
    case 'pro':
      return '/snapshots'; // Snapshots
    case 'agency':
      return '/deployments?tab=pipelines'; // Pipelines (Deployments)
    case 'enterprise':
      return '/drift-dashboard'; // Drift Dashboard
    default:
      return '/environments';
  }
}

export function LoginPage() {
  useEffect(() => {
    document.title = 'Login - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const { isAuthenticated, isLoading, needsOnboarding, login } = useAuth();
  const { planName } = useFeatures();
  const navigate = useNavigate();

  // Redirect if already authenticated
  useEffect(() => {
    console.log('[LoginPage] useEffect check:', { isLoading, isAuthenticated, needsOnboarding });
    if (!isLoading && isAuthenticated) {
      if (needsOnboarding) {
        console.log('[LoginPage] Redirecting to onboarding');
        navigate('/onboarding', { replace: true });
      } else {
        const defaultPage = getDefaultLandingPage(planName);
        console.log('[LoginPage] Redirecting to plan-based default:', defaultPage);
        navigate(defaultPage, { replace: true });
      }
    }
  }, [isAuthenticated, isLoading, needsOnboarding, planName, navigate]);

  const handleLogin = () => {
    login();
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="mt-4 text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-4 text-center">
          <div className="mx-auto h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
            <Workflow className="h-6 w-6 text-primary" />
          </div>
          <div className="space-y-1">
            <CardTitle className="text-2xl font-bold">WorkflowOps</CardTitle>
            <CardDescription>
              Manage your N8N workflows across all environments
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <Button onClick={handleLogin} className="w-full" size="lg">
              Sign In / Sign Up
            </Button>
            <p className="text-sm text-muted-foreground text-center">
              New users will be guided through a quick setup process
            </p>
            <p className="text-xs text-muted-foreground text-center">
              If you already have an account, sign in. If not, you can create one during the sign-in process.
            </p>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                Features
              </span>
            </div>
          </div>

          <ul className="text-sm text-muted-foreground space-y-2">
            <li className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              Multi-environment workflow management
            </li>
            <li className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              Version control with GitHub integration
            </li>
            <li className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              Execution monitoring and observability
            </li>
            <li className="flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-primary" />
              Team collaboration and access control
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
