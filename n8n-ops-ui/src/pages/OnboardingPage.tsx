// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Sparkles, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth';
import { apiClient } from '@/lib/api-client';
import { OrganizationStep } from '@/components/onboarding/OrganizationStep';
import { PlanSelectionStep } from '@/components/onboarding/PlanSelectionStep';
import { PaymentStep } from '@/components/onboarding/PaymentStep';
import { TeamInvitationStep } from '@/components/onboarding/TeamInvitationStep';
import { CompletionStep } from '@/components/onboarding/CompletionStep';

export type OnboardingStep = 1 | 2 | 3 | 4 | 5;

export interface OnboardingFormData {
  organizationName: string;
  industry?: string;
  companySize?: string;
  selectedPlan: string;
  billingCycle: 'monthly' | 'yearly';
  teamInvites: Array<{ email: string; role: string }>;
}

const STEPS = [
  { id: 1, title: 'Organization', description: 'Tell us about your organization' },
  { id: 2, title: 'Plan Selection', description: 'Choose your subscription plan' },
  { id: 3, title: 'Payment', description: 'Set up payment (if required)' },
  { id: 4, title: 'Team Setup', description: 'Invite team members (optional)' },
  { id: 5, title: 'Complete', description: 'You\'re all set!' },
];

export function OnboardingPage() {
  useEffect(() => {
    document.title = 'Onboarding - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  const navigate = useNavigate();
  const { needsOnboarding, user, tenant } = useAuth();
  const [currentStep, setCurrentStep] = useState<OnboardingStep>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState<OnboardingFormData>({
    organizationName: '',
    selectedPlan: 'free',
    billingCycle: 'monthly',
    teamInvites: [],
  });

  // Check URL params for payment return
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const step = urlParams.get('step');
    const success = urlParams.get('success');
    
    if (step && parseInt(step) >= 1 && parseInt(step) <= 5) {
      setCurrentStep(parseInt(step) as OnboardingStep);
    }
    
    if (success === 'true') {
      // Payment was successful, we're on step 3
      setCurrentStep(3);
    }
  }, []);

  // If user doesn't need onboarding, redirect to dashboard
  useEffect(() => {
    if (!needsOnboarding && user && tenant) {
      navigate('/');
    }
  }, [needsOnboarding, user, tenant, navigate]);

  // Load saved progress from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('onboarding_progress');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setFormData(parsed.formData);
        setCurrentStep(parsed.currentStep);
      } catch (e) {
        // Ignore parse errors
      }
    }
  }, []);

  // Save progress to localStorage
  const saveProgress = (step: OnboardingStep, data: Partial<OnboardingFormData>) => {
    const updated = { ...formData, ...data };
    setFormData(updated);
    localStorage.setItem('onboarding_progress', JSON.stringify({
      currentStep: step,
      formData: updated,
    }));
  };

  const handleNext = async (stepData?: Partial<OnboardingFormData>) => {
    if (stepData) {
      saveProgress(currentStep, stepData);
    }

    setIsLoading(true);
    try {
      // Handle step-specific logic
      if (currentStep === 1) {
        // Organization step
        await apiClient.onboardingOrganization({
          organization_name: formData.organizationName || (stepData?.organizationName || ''),
          industry: stepData?.industry,
          company_size: stepData?.companySize,
        });
        setCurrentStep(2);
      } else if (currentStep === 2) {
        // Plan selection step
        await apiClient.onboardingSelectPlan({
          plan_name: stepData?.selectedPlan || formData.selectedPlan,
          billing_cycle: stepData?.billingCycle || formData.billingCycle,
        });
        const selectedPlan = stepData?.selectedPlan || formData.selectedPlan;
        
        // If free plan, skip payment step
        if (selectedPlan === 'free') {
          setCurrentStep(4); // Skip to team setup
        } else {
          setCurrentStep(3); // Go to payment
        }
      } else if (currentStep === 3) {
        // Payment step - handled by PaymentStep component
        // This will redirect to Stripe, so we don't advance here
        return;
      } else if (currentStep === 4) {
        // Team invitation step
        const invites = stepData?.teamInvites || formData.teamInvites;
        if (invites && invites.length > 0) {
          const result = await apiClient.onboardingInviteTeam({ invites });
          if (result.data.errors && result.data.errors.length > 0) {
            // Some invitations failed, but continue anyway
            const errorCount = result.data.errors.length;
            const successCount = result.data.invited_count;
            if (successCount > 0) {
              toast.warning(
                `${successCount} invitation${successCount > 1 ? 's' : ''} sent successfully. ${errorCount} failed.`,
                { duration: 5000 }
              );
            } else {
              toast.error('Failed to send invitations. Please check the email addresses and try again.');
              return; // Don't proceed if all failed
            }
          } else if (result.data.invited_count > 0) {
            toast.success(`${result.data.invited_count} invitation${result.data.invited_count > 1 ? 's' : ''} sent successfully!`);
          }
        }
        setCurrentStep(5);
      } else if (currentStep === 5) {
        // Completion step
        await apiClient.onboardingComplete();
        localStorage.removeItem('onboarding_progress');
        toast.success('Welcome to N8N Ops!');
        setTimeout(() => {
          navigate('/');
        }, 2000);
      }
    } catch (error: any) {
      console.error('Onboarding step failed:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to proceed. Please try again.';
      
      // Provide more specific error messages
      if (error.response?.status === 400) {
        toast.error(errorMessage);
      } else if (error.response?.status === 403) {
        toast.error('You do not have permission to perform this action.');
      } else if (error.response?.status === 404) {
        toast.error('Resource not found. Please refresh and try again.');
      } else if (error.response?.status >= 500) {
        toast.error('Server error. Please try again in a moment.');
      } else {
        toast.error(errorMessage);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((currentStep - 1) as OnboardingStep);
    }
  };

  const handleSkip = () => {
    if (currentStep === 4) {
      // Skip team invitation
      handleNext();
    }
  };

  if (!needsOnboarding) {
    return null;
  }

  const progress = ((currentStep - 1) / (STEPS.length - 1)) * 100;

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <Card className="w-full max-w-4xl">
        <CardHeader className="text-center border-b pb-6">
          <div className="mx-auto mb-4 h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
            <Sparkles className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl">Welcome to N8N Ops</CardTitle>
          <CardDescription>
            Let's get your workspace set up. This will only take a moment.
          </CardDescription>
          
          {/* Progress Bar */}
          <div className="mt-6 space-y-2">
            <div className="flex justify-between text-sm text-muted-foreground mb-2">
              <span>Step {currentStep} of {STEPS.length}</span>
              <span>{Math.round(progress)}% Complete</span>
            </div>
            <Progress value={progress} className="h-2" />
            <div className="flex justify-between mt-2">
              {STEPS.map((step) => (
                <div
                  key={step.id}
                  className={`flex flex-col items-center flex-1 ${
                    step.id < currentStep
                      ? 'text-primary'
                      : step.id === currentStep
                      ? 'text-foreground font-medium'
                      : 'text-muted-foreground'
                  }`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center mb-1 ${
                      step.id < currentStep
                        ? 'bg-primary text-primary-foreground'
                        : step.id === currentStep
                        ? 'bg-primary/20 text-primary border-2 border-primary'
                        : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {step.id < currentStep ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <span className="text-xs font-medium">{step.id}</span>
                    )}
                  </div>
                  <span className="text-xs text-center">{step.title}</span>
                </div>
              ))}
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-6">
          {/* Step Content */}
          <div className="min-h-[400px]">
            {currentStep === 1 && (
              <OrganizationStep
                data={formData}
                onNext={handleNext}
                isLoading={isLoading}
              />
            )}
            {currentStep === 2 && (
              <PlanSelectionStep
                data={formData}
                onNext={handleNext}
                onBack={handleBack}
                isLoading={isLoading}
              />
            )}
            {currentStep === 3 && (
              <PaymentStep
                data={formData}
                onNext={handleNext}
                onBack={handleBack}
                isLoading={isLoading}
              />
            )}
            {currentStep === 4 && (
              <TeamInvitationStep
                data={formData}
                onNext={handleNext}
                onBack={handleBack}
                onSkip={handleSkip}
                isLoading={isLoading}
              />
            )}
            {currentStep === 5 && (
              <CompletionStep
                data={formData}
                onComplete={() => handleNext()}
                isLoading={isLoading}
              />
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
