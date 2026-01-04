import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, ArrowLeft, CreditCard, CheckCircle2, AlertCircle, Rocket, Check } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import type { OnboardingFormData } from '@/pages/OnboardingPage';

interface PaymentStepProps {
  data: OnboardingFormData;
  onNext: (data: Partial<OnboardingFormData>) => void;
  onBack: () => void;
  isLoading: boolean;
}

export function PaymentStep({ data, onNext, onBack, isLoading }: PaymentStepProps) {
  const [processing, setProcessing] = useState(false);
  const [paymentStatus, setPaymentStatus] = useState<'idle' | 'processing' | 'success' | 'error'>('idle');
  const isFree = data.selectedPlan === 'free';

  // Check if returning from Stripe
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const success = urlParams.get('success');
    const canceled = urlParams.get('canceled');

    if (success === 'true') {
      setPaymentStatus('success');
      // Clear URL params
      window.history.replaceState({}, '', window.location.pathname);
      // Proceed to next step after a moment
      setTimeout(() => {
        onNext({});
      }, 2000);
    } else if (canceled === 'true') {
      // User canceled payment
      toast.info('Payment canceled. You can try again or select a different plan.');
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [onNext]);

  const handleContinue = async () => {
    if (isFree) {
      // Free plan - just advance
      onNext({});
      return;
    }

    // Paid plan - initiate payment via provider checkout (per spec)
    setProcessing(true);
    setPaymentStatus('processing');

    try {
      // Use provider-based checkout if provider info is available (per spec)
      if (data.selectedProviderId && data.selectedPlanId) {
        const result = await apiClient.createProviderCheckout({
          provider_id: data.selectedProviderId,
          plan_id: data.selectedPlanId,
          billing_cycle: data.billingCycle,
          success_url: `${window.location.origin}/onboarding?step=3&success=true&session_id={CHECKOUT_SESSION_ID}`,
          cancel_url: `${window.location.origin}/onboarding?step=3&canceled=true`,
        });

        if (result.data.checkout_url) {
          // Redirect to Stripe Checkout
          window.location.href = result.data.checkout_url;
        } else {
          // No checkout URL (shouldn't happen, but handle gracefully)
          setPaymentStatus('success');
          setTimeout(() => {
            onNext({});
          }, 1000);
        }
      } else {
        // Fallback to legacy payment flow
        const result = await apiClient.onboardingPayment({
          plan_name: data.selectedPlan,
          billing_cycle: data.billingCycle,
          success_url: `${window.location.origin}/onboarding?step=3&success=true&session_id={CHECKOUT_SESSION_ID}`,
          cancel_url: `${window.location.origin}/onboarding?step=3&canceled=true`,
        });

        if (result.data.requires_payment && result.data.checkout_url) {
          // Redirect to Stripe Checkout
          window.location.href = result.data.checkout_url;
        } else {
          // No payment required (shouldn't happen for paid plans, but handle gracefully)
          setPaymentStatus('success');
          setTimeout(() => {
            onNext({});
          }, 1000);
        }
      }
    } catch (error: any) {
      console.error('Payment setup failed:', error);
      setPaymentStatus('error');
      toast.error(error.response?.data?.detail || 'Failed to set up payment. Please try again.');
      setProcessing(false);
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const getPlanPrice = () => {
    // This would typically come from the plan data, but for now we'll use estimates
    const prices: Record<string, { monthly: number; yearly: number }> = {
      pro: { monthly: 49, yearly: 470 },
      enterprise: { monthly: 199, yearly: 1910 },
    };
    return prices[data.selectedPlan]?.[data.billingCycle] || 0;
  };

  if (paymentStatus === 'success') {
    return (
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <div className="h-16 w-16 rounded-full bg-green-100 dark:bg-green-900/20 flex items-center justify-center">
          <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
        </div>
        <div className="text-center space-y-2">
          <h3 className="text-xl font-semibold">{isFree ? 'Workspace Ready!' : 'Payment Successful!'}</h3>
          <p className="text-sm text-muted-foreground">Redirecting to next step...</p>
        </div>
      </div>
    );
  }

  if (paymentStatus === 'error') {
    return (
      <div className="space-y-6">
        <div className="flex flex-col items-center justify-center space-y-4 p-8 border border-destructive rounded-lg bg-destructive/10">
          <div className="h-16 w-16 rounded-full bg-destructive/20 flex items-center justify-center">
            <AlertCircle className="h-8 w-8 text-destructive" />
          </div>
          <div className="text-center space-y-2">
            <h3 className="text-xl font-semibold">Payment Setup Failed</h3>
            <p className="text-sm text-muted-foreground">
              There was an error setting up your payment. Please try again.
            </p>
          </div>
          <div className="flex gap-4">
            <Button variant="outline" onClick={onBack}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            <Button onClick={handleContinue} disabled={processing}>
              {processing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <CreditCard className="mr-2 h-4 w-4" />
                  Try Again
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Free plan - lightweight confirmation
  if (isFree) {
    return (
      <div className="space-y-6">
        <div className="text-center space-y-2">
          <h3 className="text-xl font-semibold">Ready to Get Started</h3>
          <p className="text-sm text-muted-foreground">
            Your workspace is ready to use with the Free plan.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Rocket className="h-5 w-5" />
              Free Plan Includes
            </CardTitle>
            <CardDescription>Everything you need to get started</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-green-600" />
              <span className="text-sm">1 environment</span>
            </div>
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-green-600" />
              <span className="text-sm">Up to 10 workflows</span>
            </div>
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-green-600" />
              <span className="text-sm">Basic workflow management</span>
            </div>
            <div className="flex items-center gap-2">
              <Check className="h-4 w-4 text-green-600" />
              <span className="text-sm">Community support</span>
            </div>
          </CardContent>
        </Card>

        <div className="rounded-lg bg-muted/50 p-4 space-y-2">
          <p className="text-xs text-muted-foreground text-center">
            You can upgrade to a paid plan anytime from the Billing page.
          </p>
        </div>

        <div className="flex justify-between">
          <Button variant="outline" onClick={onBack} disabled={isLoading}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
          <Button onClick={handleContinue} disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Setting up...
              </>
            ) : (
              'Continue'
            )}
          </Button>
        </div>
      </div>
    );
  }

  // Paid plan - payment UI
  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <h3 className="text-xl font-semibold">Set Up Payment</h3>
        <p className="text-sm text-muted-foreground">
          Complete your subscription by adding a payment method.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            Subscription Summary
          </CardTitle>
          <CardDescription>Review your plan selection</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">Plan</span>
            <span className="font-medium capitalize">{data.selectedPlan}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">Billing Cycle</span>
            <span className="font-medium capitalize">{data.billingCycle}</span>
          </div>
          <div className="flex justify-between items-center pt-4 border-t">
            <span className="text-lg font-semibold">Total</span>
            <span className="text-2xl font-bold">
              {formatCurrency(getPlanPrice())}
              <span className="text-sm font-normal text-muted-foreground">/month</span>
            </span>
          </div>
          {data.billingCycle === 'yearly' && (
            <p className="text-xs text-muted-foreground text-center">
              Billed annually. Save up to 20% compared to monthly billing.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="rounded-lg bg-muted/50 p-4 space-y-2">
        <p className="text-sm font-medium">Secure Payment</p>
        <p className="text-xs text-muted-foreground">
          Your payment will be processed securely through Stripe. We accept all major credit cards.
          You can cancel or change your plan at any time.
        </p>
      </div>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack} disabled={processing || isLoading}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        <Button onClick={handleContinue} disabled={processing || isLoading}>
          {processing || isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <CreditCard className="mr-2 h-4 w-4" />
              Continue to Payment
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

