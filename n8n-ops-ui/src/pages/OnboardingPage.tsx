import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, Building2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth';

export function OnboardingPage() {
  const navigate = useNavigate();
  const { completeOnboarding, needsOnboarding } = useAuth();
  const [organizationName, setOrganizationName] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // If user doesn't need onboarding, redirect to dashboard
  if (!needsOnboarding) {
    navigate('/');
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    setIsLoading(true);
    try {
      await completeOnboarding(organizationName || undefined);
      toast.success('Welcome to N8N Ops! Your account has been set up.');
      navigate('/');
    } catch (error) {
      console.error('Onboarding failed:', error);
      toast.error('Failed to complete setup. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
            <Sparkles className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl">Welcome to N8N Ops</CardTitle>
          <CardDescription>
            Let's get your workspace set up. This will only take a moment.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Building2 className="h-5 w-5" />
                <span className="text-sm font-medium">Organization Details</span>
              </div>

              <div className="space-y-2">
                <Label htmlFor="organizationName">Organization Name</Label>
                <Input
                  id="organizationName"
                  type="text"
                  placeholder="My Organization"
                  value={organizationName}
                  onChange={(e) => setOrganizationName(e.target.value)}
                  disabled={isLoading}
                />
                <p className="text-xs text-muted-foreground">
                  This will be the name of your workspace. Leave blank to use your name.
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-lg bg-muted/50 p-4">
                <h4 className="text-sm font-medium mb-2">What happens next?</h4>
                <ul className="text-sm text-muted-foreground space-y-1">
                  <li>• Your account will be created with a free plan</li>
                  <li>• You'll be taken to your dashboard</li>
                  <li>• You can add your first N8N environment</li>
                </ul>
              </div>
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Setting up...
                </>
              ) : (
                'Get Started'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
