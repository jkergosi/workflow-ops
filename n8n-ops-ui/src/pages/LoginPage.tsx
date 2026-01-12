import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { useFeatures } from '@/lib/features';
import { getLastRoute } from '@/lib/lastRoute';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Workflow, Mail, Github, AlertCircle } from 'lucide-react';
import { TechnicalDifficultiesPage } from './TechnicalDifficultiesPage';

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

  const { isAuthenticated, isLoading, needsOnboarding, backendUnavailable, loginWithEmail, loginWithOAuth, signup } = useAuth();
  const { planName } = useFeatures();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [signupSuccess, setSignupSuccess] = useState(false);

  // Redirect if already authenticated
  // Navigation order: 1. onboarding 2. explicit redirect 3. lastRoute 4. plan default
  useEffect(() => {
    console.log('[LoginPage] useEffect check:', { isLoading, isAuthenticated, needsOnboarding });
    if (!isLoading && isAuthenticated) {
      // 1. If needs onboarding → /onboarding
      if (needsOnboarding) {
        console.log('[LoginPage] Redirecting to onboarding');
        navigate('/onboarding', { replace: true });
        return;
      }

      // 2. Check for explicit redirect target in URL
      const redirectParam = searchParams.get('redirect');
      if (redirectParam) {
        console.log('[LoginPage] Redirecting to explicit target:', redirectParam);
        navigate(redirectParam, { replace: true });
        return;
      }

      // 3. Check for lastRoute
      const lastRoute = getLastRoute();
      if (lastRoute) {
        console.log('[LoginPage] Redirecting to last route:', lastRoute);
        navigate(lastRoute, { replace: true });
        return;
      }

      // 4. Fallback to plan-based default
      const defaultPage = getDefaultLandingPage(planName);
      console.log('[LoginPage] Redirecting to plan-based default:', defaultPage);
      navigate(defaultPage, { replace: true });
    }
  }, [isAuthenticated, isLoading, needsOnboarding, planName, navigate, searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (mode === 'signup') {
        if (password !== confirmPassword) {
          setError('Passwords do not match');
          setIsSubmitting(false);
          return;
        }
        if (password.length < 6) {
          setError('Password must be at least 6 characters');
          setIsSubmitting(false);
          return;
        }
        await signup(email, password);
        setSignupSuccess(true);
      } else {
        await loginWithEmail(email, password);
      }
    } catch (err: any) {
      console.error('[LoginPage] Auth error:', err);
      setError(err.message || 'Authentication failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOAuthLogin = async (provider: 'google' | 'github') => {
    setError(null);
    try {
      await loginWithOAuth(provider);
    } catch (err: any) {
      console.error('[LoginPage] OAuth error:', err);
      setError(err.message || 'OAuth authentication failed');
    }
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

  // Show technical difficulties page if backend is unavailable
  if (backendUnavailable) {
    console.log('[LoginPage] Backend unavailable, showing technical difficulties page');
    return <TechnicalDifficultiesPage />;
  }

  if (signupSuccess) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-4 text-center">
            <div className="mx-auto h-12 w-12 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
              <Mail className="h-6 w-6 text-green-600 dark:text-green-400" />
            </div>
            <div className="space-y-1">
              <CardTitle className="text-2xl font-bold">Check Your Email</CardTitle>
              <CardDescription>
                We've sent a confirmation link to <strong>{email}</strong>
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground text-center">
              Click the link in the email to confirm your account and complete registration.
            </p>
            <Button
              variant="outline"
              className="w-full"
              onClick={() => {
                setSignupSuccess(false);
                setMode('login');
              }}
            >
              Back to Sign In
            </Button>
          </CardContent>
        </Card>
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
              {mode === 'login'
                ? 'Sign in to manage your N8N workflows'
                : 'Create an account to get started'}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
            </div>
            {mode === 'signup' && (
              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm Password</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  placeholder="Confirm your password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                />
              </div>
            )}
            <Button type="submit" className="w-full" size="lg" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {mode === 'login' ? 'Signing in...' : 'Creating account...'}
                </>
              ) : (
                mode === 'login' ? 'Sign In' : 'Create Account'
              )}
            </Button>
          </form>

          <div className="text-center">
            <button
              type="button"
              className="text-sm text-primary hover:underline"
              onClick={() => {
                setMode(mode === 'login' ? 'signup' : 'login');
                setError(null);
              }}
            >
              {mode === 'login'
                ? "Don't have an account? Sign up"
                : 'Already have an account? Sign in'}
            </button>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <Separator className="w-full" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                Or continue with
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Button
              variant="outline"
              onClick={() => handleOAuthLogin('google')}
              disabled={isSubmitting}
            >
              <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Google
            </Button>
            <Button
              variant="outline"
              onClick={() => handleOAuthLogin('github')}
              disabled={isSubmitting}
            >
              <Github className="mr-2 h-4 w-4" />
              GitHub
            </Button>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <Separator className="w-full" />
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
