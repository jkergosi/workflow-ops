// @ts-nocheck
import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { Zap, Sparkles, Building2, Loader2 } from 'lucide-react';

interface ChangePlanModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentPlanKey: string;
}

export function ChangePlanModal({ open, onOpenChange, currentPlanKey }: ChangePlanModalProps) {
  const navigate = useNavigate();
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');

  const { data: plans, isLoading } = useQuery({
    queryKey: ['subscription-plans'],
    queryFn: () => api.getSubscriptionPlans(),
    enabled: open,
  });

  const checkoutMutation = useMutation({
    mutationFn: (data: { price_id: string; billing_cycle: string }) => {
      return api.createCheckoutSession({
        price_id: data.price_id,
        billing_cycle: data.billing_cycle,
        success_url: `${window.location.origin}/billing?success=true`,
        cancel_url: `${window.location.origin}/billing?canceled=true`,
      });
    },
    onSuccess: (result) => {
      window.location.href = result.data.url;
    },
    onError: () => {
      toast.error('Failed to start checkout process');
    },
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const handleSelectPlan = (plan: any) => {
    if (plan.name === 'enterprise' || plan.name === 'agency') {
      // For enterprise/agency, show contact sales
      toast.info('Please contact sales for Enterprise and Agency plans');
      return;
    }

    setSelectedPlan(plan);
  };

  const handleConfirm = () => {
    if (!selectedPlan) return;

    const priceId = billingCycle === 'monthly'
      ? selectedPlan.stripe_price_id_monthly
      : selectedPlan.stripe_price_id_yearly;

    if (!priceId) {
      toast.error('Plan pricing not configured');
      return;
    }

    checkoutMutation.mutate({
      price_id: priceId,
      billing_cycle: billingCycle,
    });
  };

  const availablePlans = plans?.data?.filter((p: any) => 
    ['free', 'pro', 'agency'].includes(p.name)
  ) || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Change Plan</DialogTitle>
          <DialogDescription>
            Select a new plan for your subscription
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              {availablePlans.map((plan: any) => {
                const isCurrent = plan.name === currentPlanKey;
                const isSelected = selectedPlan?.id === plan.id;
                const isEnterprise = plan.name === 'enterprise' || plan.name === 'agency';

                return (
                  <div
                    key={plan.id}
                    className={`relative border-2 rounded-lg p-4 cursor-pointer transition-all ${
                      isSelected
                        ? 'border-primary bg-primary/5'
                        : isCurrent
                        ? 'border-muted bg-muted/50'
                        : 'border-border hover:border-primary/50'
                    }`}
                    onClick={() => !isCurrent && handleSelectPlan(plan)}
                  >
                    {isCurrent && (
                      <Badge className="absolute -top-2 left-1/2 -translate-x-1/2" variant="secondary">
                        Current
                      </Badge>
                    )}
                    <div className="text-center space-y-2">
                      <div className="flex justify-center">
                        {plan.name === 'pro' ? (
                          <Sparkles className="h-6 w-6 text-blue-500" />
                        ) : plan.name === 'agency' ? (
                          <Building2 className="h-6 w-6 text-purple-500" />
                        ) : (
                          <Zap className="h-6 w-6 text-gray-500" />
                        )}
                      </div>
                      <h3 className="font-semibold">{plan.display_name}</h3>
                      <div className="text-2xl font-bold">
                        {formatCurrency(parseFloat(plan.price_monthly))}
                        <span className="text-sm font-normal text-muted-foreground">/mo</span>
                      </div>
                      {isCurrent ? (
                        <Button variant="outline" size="sm" className="w-full" disabled>
                          Current Plan
                        </Button>
                      ) : isEnterprise ? (
                        <Button variant="outline" size="sm" className="w-full">
                          Contact Sales
                        </Button>
                      ) : (
                        <Button
                          variant={isSelected ? 'default' : 'outline'}
                          size="sm"
                          className="w-full"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectPlan(plan);
                          }}
                        >
                          {isSelected ? 'Selected' : 'Select'}
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {selectedPlan && selectedPlan.name !== 'enterprise' && selectedPlan.name !== 'agency' && (
              <div className="space-y-4 border-t pt-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Billing Cycle</label>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      variant={billingCycle === 'monthly' ? 'default' : 'outline'}
                      onClick={() => setBillingCycle('monthly')}
                      className="w-full"
                    >
                      <div className="text-center">
                        <div>Monthly</div>
                        <div className="text-xs">
                          {formatCurrency(parseFloat(selectedPlan.price_monthly))}/mo
                        </div>
                      </div>
                    </Button>
                    {selectedPlan.price_yearly && parseFloat(selectedPlan.price_yearly) > 0 && (
                      <Button
                        variant={billingCycle === 'yearly' ? 'default' : 'outline'}
                        onClick={() => setBillingCycle('yearly')}
                        className="w-full"
                      >
                        <div className="text-center">
                          <div>Yearly</div>
                          <div className="text-xs">
                            {formatCurrency(parseFloat(selectedPlan.price_yearly) / 12)}/mo
                          </div>
                        </div>
                      </Button>
                    )}
                  </div>
                </div>

                <div className="bg-muted p-4 rounded-md">
                  <p className="text-sm">
                    You will be charged{' '}
                    <span className="font-bold">
                      {formatCurrency(
                        billingCycle === 'monthly'
                          ? parseFloat(selectedPlan.price_monthly)
                          : parseFloat(selectedPlan.price_yearly)
                      )}
                    </span>{' '}
                    {billingCycle === 'monthly' ? 'per month' : 'per year'}
                  </p>
                </div>
              </div>
            )}

            <div className="text-center text-sm text-muted-foreground">
              <Button
                variant="link"
                className="p-0 h-auto"
                onClick={() => {
                  onOpenChange(false);
                  navigate('/admin/feature-matrix');
                }}
              >
                View full plan details →
              </Button>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          {selectedPlan && selectedPlan.name !== 'enterprise' && selectedPlan.name !== 'agency' && (
            <Button
              onClick={handleConfirm}
              disabled={checkoutMutation.isPending}
            >
              {checkoutMutation.isPending ? 'Processing...' : 'Proceed to Checkout'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

