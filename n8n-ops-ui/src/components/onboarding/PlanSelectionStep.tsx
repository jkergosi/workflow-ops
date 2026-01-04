import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Zap, Sparkles, Crown, CheckCircle2, ArrowLeft, ArrowRight, Workflow } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import type { OnboardingFormData } from '@/pages/OnboardingPage';
import type { ProviderWithPlans, ProviderPlan } from '@/types';

interface PlanSelectionStepProps {
  data: OnboardingFormData;
  onNext: (data: Partial<OnboardingFormData>) => void;
  onBack: () => void;
  isLoading: boolean;
}

export function PlanSelectionStep({ data, onNext, onBack, isLoading }: PlanSelectionStepProps) {
  // For MVP: N8N is the only provider, so we default to it
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>(data.billingCycle || 'monthly');

  // Fetch providers with their plans
  const { data: providersData, isLoading: loadingProviders } = useQuery({
    queryKey: ['providers-with-plans'],
    queryFn: () => apiClient.getProvidersWithPlans(),
  });

  const providers = providersData?.data || [];

  // For MVP, auto-select N8N provider
  const n8nProvider = providers.find((p: ProviderWithPlans) => p.name === 'n8n');

  // If N8N is available and no provider selected, auto-select it
  if (n8nProvider && !selectedProvider) {
    setSelectedProvider(n8nProvider.id);
  }

  const selectedProviderData = providers.find((p: ProviderWithPlans) => p.id === selectedProvider);
  const plans = selectedProviderData?.plans || [];

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const handleNext = async () => {
    if (!selectedProvider) {
      toast.error('Please select a provider');
      return;
    }
    if (!selectedPlanId) {
      toast.error('Please select a plan');
      return;
    }

    const selectedPlan = plans.find((p: ProviderPlan) => p.id === selectedPlanId);
    if (!selectedPlan) {
      toast.error('Invalid plan selected');
      return;
    }

    // Pass provider subscription info for onboarding
    onNext({
      selectedPlan: selectedPlan.name,
      billingCycle,
      // Store provider info for later use
      selectedProviderId: selectedProvider,
      selectedPlanId: selectedPlanId,
    } as any);
  };

  if (loadingProviders) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Sort plans by sort_order
  const sortedPlans = [...plans].sort((a: ProviderPlan, b: ProviderPlan) =>
    (a.sort_order || 0) - (b.sort_order || 0)
  );

  // Check if there are any paid plans
  const hasPaidPlans = sortedPlans.some((p: ProviderPlan) => p.price_monthly > 0);

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h3 className="text-xl font-semibold">Choose Your Provider & Plan</h3>
        <p className="text-sm text-muted-foreground">
          Select the automation platform you want to manage. You can add more later.
        </p>
      </div>

      {/* Provider Selection - MVP: Only N8N */}
      <div className="space-y-4">
        <h4 className="font-medium text-sm text-muted-foreground">Select Provider</h4>
        <div className="grid gap-4 md:grid-cols-2">
          {providers.filter((p: ProviderWithPlans) => p.is_active).map((provider: ProviderWithPlans) => {
            const isSelected = selectedProvider === provider.id;
            const isN8N = provider.name === 'n8n';

            return (
              <Card
                key={provider.id}
                className={`relative cursor-pointer transition-all ${
                  isSelected ? 'border-primary border-2 shadow-lg' : 'hover:border-primary/50'
                } ${!isN8N ? 'opacity-50' : ''}`}
                onClick={() => {
                  if (isN8N) {
                    setSelectedProvider(provider.id);
                    setSelectedPlanId(null); // Reset plan selection
                  } else {
                    toast.info('Coming soon! Only n8n is available for MVP.');
                  }
                }}
              >
                {!isN8N && (
                  <div className="absolute -top-2 right-2">
                    <Badge variant="secondary" className="text-xs">Coming Soon</Badge>
                  </div>
                )}
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Workflow className="h-5 w-5 text-orange-500" />
                    {provider.display_name}
                    {isSelected && (
                      <div className="ml-auto h-5 w-5 rounded-full bg-primary flex items-center justify-center">
                        <CheckCircle2 className="h-3 w-3 text-primary-foreground" />
                      </div>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{provider.description}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Plan Selection - Shows only if provider is selected */}
      {selectedProvider && sortedPlans.length > 0 && (
        <div className="space-y-4">
          <h4 className="font-medium text-sm text-muted-foreground">Select Plan for {selectedProviderData?.display_name}</h4>

          {/* Billing Cycle Toggle - Only show if there are paid plans */}
          {hasPaidPlans && (
            <div className="flex items-center justify-center gap-4">
              <span className={`text-sm ${billingCycle === 'monthly' ? 'font-medium' : 'text-muted-foreground'}`}>
                Monthly
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setBillingCycle(billingCycle === 'monthly' ? 'yearly' : 'monthly')}
                className="w-12"
              >
                <div className={`w-5 h-5 rounded-full bg-primary transition-transform ${billingCycle === 'yearly' ? 'translate-x-2' : '-translate-x-2'}`} />
              </Button>
              <span className={`text-sm ${billingCycle === 'yearly' ? 'font-medium' : 'text-muted-foreground'}`}>
                Yearly <span className="text-xs text-green-600">(Save up to 20%)</span>
              </span>
            </div>
          )}

          {/* Plans Grid */}
          <div className="grid gap-4 md:grid-cols-3">
            {sortedPlans.map((plan: ProviderPlan) => {
              const price = billingCycle === 'monthly'
                ? plan.price_monthly
                : (plan.price_yearly || plan.price_monthly * 12) / 12;
              const isSelected = selectedPlanId === plan.id;
              const isPopular = plan.name === 'pro';
              const isFree = plan.price_monthly === 0;

              return (
                <Card
                  key={plan.id}
                  className={`relative cursor-pointer transition-all ${
                    isSelected ? 'border-primary border-2 shadow-lg' : 'hover:border-primary/50'
                  } ${isPopular ? 'shadow-md' : ''}`}
                  onClick={() => setSelectedPlanId(plan.id)}
                >
                  {isPopular && (
                    <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                      <Badge className="bg-primary text-primary-foreground gap-1">
                        <Sparkles className="h-3 w-3" />
                        Recommended
                      </Badge>
                    </div>
                  )}
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {plan.name === 'enterprise' ? (
                          <Crown className="h-5 w-5 text-amber-500" />
                        ) : plan.name === 'pro' ? (
                          <Sparkles className="h-5 w-5 text-primary" />
                        ) : (
                          <Zap className="h-5 w-5 text-muted-foreground" />
                        )}
                        {plan.display_name}
                      </div>
                      {isSelected && (
                        <div className="h-5 w-5 rounded-full bg-primary flex items-center justify-center">
                          <CheckCircle2 className="h-3 w-3 text-primary-foreground" />
                        </div>
                      )}
                    </CardTitle>
                    <CardDescription>{plan.description}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <div className="flex items-baseline gap-1">
                        <span className="text-3xl font-bold">
                          {isFree ? 'Free' : formatCurrency(price)}
                        </span>
                        {!isFree && (
                          <span className="text-muted-foreground">/month</span>
                        )}
                      </div>
                      {billingCycle === 'yearly' && !isFree && plan.price_yearly && (
                        <p className="text-sm text-muted-foreground mt-1">
                          Billed annually ({formatCurrency(plan.price_yearly)}/year)
                        </p>
                      )}
                    </div>

                    <div className="space-y-2">
                      {/* Environment limit */}
                      <div className="flex items-center gap-2 text-sm">
                        <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                        <span>
                          {plan.max_environments === -1
                            ? 'Unlimited Environments'
                            : `${plan.max_environments} Environment${plan.max_environments !== 1 ? 's' : ''}`}
                        </span>
                      </div>
                      {/* Workflow limit */}
                      <div className="flex items-center gap-2 text-sm">
                        <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                        <span>
                          {plan.max_workflows === -1
                            ? 'Unlimited Workflows'
                            : `${plan.max_workflows} Workflows`}
                        </span>
                      </div>
                      {/* Features from plan */}
                      {plan.features && typeof plan.features === 'object' && (
                        <>
                          {plan.features.github_backup && (
                            <div className="flex items-center gap-2 text-sm">
                              <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                              <span>GitHub Backup</span>
                            </div>
                          )}
                          {plan.features.promotions && (
                            <div className="flex items-center gap-2 text-sm">
                              <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                              <span>Workflow Promotions</span>
                            </div>
                          )}
                          {plan.features.audit_logs && (
                            <div className="flex items-center gap-2 text-sm">
                              <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                              <span>Audit Logs</span>
                            </div>
                          )}
                          {plan.features.priority_support && (
                            <div className="flex items-center gap-2 text-sm">
                              <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                              <span>Priority Support</span>
                            </div>
                          )}
                          {plan.features.sso && (
                            <div className="flex items-center gap-2 text-sm">
                              <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                              <span>SSO Integration</span>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack} disabled={isLoading}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <Button onClick={handleNext} disabled={isLoading || !selectedProvider || !selectedPlanId}>
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              Continue
              <ArrowRight className="ml-2 h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
