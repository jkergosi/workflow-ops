import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { apiClient } from '@/lib/api-client';
import {
  Workflow,
  Loader2,
  MoreHorizontal,
  ArrowUpCircle,
  CreditCard,
  XCircle,
  Plus,
  CheckCircle2,
  Sparkles,
  Crown,
  Zap,
  ExternalLink,
} from 'lucide-react';
import { toast } from 'sonner';
import type { TenantProviderSubscription, ProviderWithPlans, ProviderPlan } from '@/types';

export function TenantProvidersPage() {
  useEffect(() => {
    document.title = 'Providers & Plans - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const queryClient = useQueryClient();

  // Dialog state
  const [upgradePlanDialogOpen, setUpgradePlanDialogOpen] = useState(false);
  const [selectedSubscription, setSelectedSubscription] = useState<TenantProviderSubscription | null>(null);
  const [selectedNewPlan, setSelectedNewPlan] = useState<ProviderPlan | null>(null);
  const [addProviderDialogOpen, setAddProviderDialogOpen] = useState(false);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);

  // Fetch subscriptions
  const { data: subscriptionsData, isLoading: loadingSubscriptions } = useQuery({
    queryKey: ['tenant-provider-subscriptions'],
    queryFn: () => apiClient.getTenantProviderSubscriptions(),
  });

  // Fetch all providers with plans
  const { data: providersData, isLoading: loadingProviders } = useQuery({
    queryKey: ['providers-with-plans'],
    queryFn: () => apiClient.getProvidersWithPlans(),
  });

  const subscriptions = subscriptionsData?.data || [];
  const providers = providersData?.data || [];

  // Find providers not yet subscribed
  const subscribedProviderIds = subscriptions.map((s: TenantProviderSubscription) => s.provider_id);
  const availableProviders = providers.filter(
    (p: ProviderWithPlans) => !subscribedProviderIds.includes(p.id) && p.is_active
  );

  // Subscribe to free plan mutation
  const subscribeFreeMutation = useMutation({
    mutationFn: (providerId: string) => apiClient.subscribeToFreePlan(providerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-provider-subscriptions'] });
      setAddProviderDialogOpen(false);
      toast.success('Successfully subscribed to provider');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to subscribe');
    },
  });

  // Cancel subscription mutation
  const cancelSubscriptionMutation = useMutation({
    mutationFn: (providerId: string) => apiClient.cancelProviderSubscription(providerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenant-provider-subscriptions'] });
      setCancelDialogOpen(false);
      setSelectedSubscription(null);
      toast.success('Subscription will be canceled at end of billing period');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to cancel subscription');
    },
  });

  // Handle upgrade/downgrade - redirects to Stripe checkout
  const handleChangePlan = async (subscription: TenantProviderSubscription, newPlan: ProviderPlan) => {
    try {
      const isFree = newPlan.price_monthly === 0;

      if (isFree) {
        // Downgrade to free - use update endpoint
        await apiClient.updateProviderSubscription(subscription.provider_id, {
          plan_id: newPlan.id,
        });
        queryClient.invalidateQueries({ queryKey: ['tenant-provider-subscriptions'] });
        setUpgradePlanDialogOpen(false);
        toast.success(`Downgraded to ${newPlan.display_name} plan`);
      } else {
        // Upgrade to paid - redirect to Stripe checkout
        const result = await apiClient.createProviderCheckout({
          provider_id: subscription.provider_id,
          plan_id: newPlan.id,
          billing_cycle: subscription.billing_cycle as 'monthly' | 'yearly',
          success_url: `${window.location.origin}/admin/providers?success=true`,
          cancel_url: `${window.location.origin}/admin/providers?canceled=true`,
        });

        if (result.data.checkout_url) {
          window.location.href = result.data.checkout_url;
        }
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to change plan');
    }
  };

  // Handle Stripe portal
  const handleManageBilling = async () => {
    try {
      const result = await apiClient.createPortalSession(
        `${window.location.origin}/admin/providers`
      );
      if (result.data.url) {
        window.location.href = result.data.url;
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Failed to open billing portal');
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusBadge = (status: string, cancelAtPeriodEnd: boolean) => {
    if (cancelAtPeriodEnd) {
      return <Badge variant="destructive">Canceling</Badge>;
    }
    switch (status) {
      case 'active':
        return <Badge variant="default" className="bg-green-600">Active</Badge>;
      case 'trialing':
        return <Badge variant="secondary">Trial</Badge>;
      case 'past_due':
        return <Badge variant="destructive">Past Due</Badge>;
      case 'canceled':
        return <Badge variant="outline">Canceled</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getPlanIcon = (planName: string) => {
    switch (planName) {
      case 'enterprise':
        return <Crown className="h-4 w-4 text-amber-500" />;
      case 'pro':
        return <Sparkles className="h-4 w-4 text-primary" />;
      default:
        return <Zap className="h-4 w-4 text-muted-foreground" />;
    }
  };

  // Check URL params for checkout return
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const success = urlParams.get('success');
    const canceled = urlParams.get('canceled');

    if (success === 'true') {
      toast.success('Plan updated successfully');
      queryClient.invalidateQueries({ queryKey: ['tenant-provider-subscriptions'] });
      window.history.replaceState({}, '', window.location.pathname);
    } else if (canceled === 'true') {
      toast.info('Plan change canceled');
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [queryClient]);

  if (loadingSubscriptions || loadingProviders) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold">Providers & Plans</h1>
          <p className="text-muted-foreground">Manage your automation platform subscriptions</p>
        </div>
        {availableProviders.length > 0 && (
          <Button onClick={() => setAddProviderDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Provider
          </Button>
        )}
      </div>

      {/* Current Subscriptions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Workflow className="h-5 w-5" />
            Active Subscriptions
          </CardTitle>
          <CardDescription>
            Automation platforms currently active for your organization
          </CardDescription>
        </CardHeader>
        <CardContent>
          {subscriptions.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Workflow className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="font-medium">No active subscriptions</p>
              <p className="text-sm">Add a provider to start managing workflows</p>
              <Button className="mt-4" onClick={() => setAddProviderDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add Provider
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Current Plan</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Billing</TableHead>
                  <TableHead>Renews</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {subscriptions.map((sub: TenantProviderSubscription) => (
                  <TableRow key={sub.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Workflow className="h-5 w-5 text-orange-500" />
                        <span className="font-medium">{sub.provider?.display_name || sub.provider?.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getPlanIcon(sub.plan?.name || 'free')}
                        <span>{sub.plan?.display_name || 'Free'}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      {getStatusBadge(sub.status, sub.cancel_at_period_end)}
                    </TableCell>
                    <TableCell>
                      {sub.plan?.price_monthly === 0 ? (
                        <span className="text-muted-foreground">--</span>
                      ) : (
                        <span className="capitalize">{sub.billing_cycle}</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {sub.current_period_end ? formatDate(sub.current_period_end) : 'N/A'}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => {
                              setSelectedSubscription(sub);
                              setUpgradePlanDialogOpen(true);
                            }}
                          >
                            <ArrowUpCircle className="h-4 w-4 mr-2" />
                            Change Plan
                          </DropdownMenuItem>
                          {sub.stripe_subscription_id && (
                            <DropdownMenuItem onClick={handleManageBilling}>
                              <CreditCard className="h-4 w-4 mr-2" />
                              Manage Billing
                              <ExternalLink className="h-3 w-3 ml-auto opacity-50" />
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          {!sub.cancel_at_period_end && sub.status === 'active' && (
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={() => {
                                setSelectedSubscription(sub);
                                setCancelDialogOpen(true);
                              }}
                            >
                              <XCircle className="h-4 w-4 mr-2" />
                              Cancel Subscription
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Plan Features Summary */}
      {subscriptions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Plan Features</CardTitle>
            <CardDescription>Current entitlements across all provider subscriptions</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {subscriptions.map((sub: TenantProviderSubscription) => (
                <div key={sub.id} className="border rounded-lg p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <Workflow className="h-4 w-4 text-orange-500" />
                    <span className="font-medium text-sm">{sub.provider?.display_name}</span>
                  </div>
                  <div className="space-y-1 text-sm">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-3 w-3 text-green-500" />
                      <span className="text-muted-foreground">
                        {sub.plan?.max_environments === -1
                          ? 'Unlimited'
                          : sub.plan?.max_environments} Environments
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-3 w-3 text-green-500" />
                      <span className="text-muted-foreground">
                        {sub.plan?.max_workflows === -1
                          ? 'Unlimited'
                          : sub.plan?.max_workflows} Workflows
                      </span>
                    </div>
                    {sub.plan?.features?.github_backup && (
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-3 w-3 text-green-500" />
                        <span className="text-muted-foreground">GitHub Backup</span>
                      </div>
                    )}
                    {sub.plan?.features?.promotions && (
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="h-3 w-3 text-green-500" />
                        <span className="text-muted-foreground">Workflow Promotions</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Add Provider Dialog */}
      <Dialog open={addProviderDialogOpen} onOpenChange={setAddProviderDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Add Provider</DialogTitle>
            <DialogDescription>
              Select an automation platform to add to your organization
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {availableProviders.length === 0 ? (
              <p className="text-center text-muted-foreground py-4">
                All available providers have been added.
              </p>
            ) : (
              availableProviders.map((provider: ProviderWithPlans) => {
                const isN8N = provider.name === 'n8n';
                return (
                  <Card
                    key={provider.id}
                    className={`cursor-pointer transition-all hover:border-primary ${!isN8N ? 'opacity-50' : ''}`}
                    onClick={() => {
                      if (isN8N) {
                        subscribeFreeMutation.mutate(provider.id);
                      } else {
                        toast.info('Coming soon! Only n8n is available for MVP.');
                      }
                    }}
                  >
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center gap-2 text-lg">
                        <Workflow className="h-5 w-5 text-orange-500" />
                        {provider.display_name}
                        {!isN8N && <Badge variant="secondary" className="ml-auto">Coming Soon</Badge>}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground">{provider.description}</p>
                      <p className="text-xs text-muted-foreground mt-2">
                        Starts with Free plan. Upgrade anytime.
                      </p>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddProviderDialogOpen(false)}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Change Plan Dialog */}
      <Dialog open={upgradePlanDialogOpen} onOpenChange={setUpgradePlanDialogOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Change Plan</DialogTitle>
            <DialogDescription>
              Select a new plan for {selectedSubscription?.provider?.display_name}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4 md:grid-cols-3">
            {selectedSubscription && providers
              .find((p: ProviderWithPlans) => p.id === selectedSubscription.provider_id)
              ?.plans
              ?.sort((a: ProviderPlan, b: ProviderPlan) => (a.sort_order || 0) - (b.sort_order || 0))
              .map((plan: ProviderPlan) => {
                const isCurrentPlan = plan.id === selectedSubscription.plan_id;
                const isFree = plan.price_monthly === 0;

                return (
                  <Card
                    key={plan.id}
                    className={`cursor-pointer transition-all ${
                      selectedNewPlan?.id === plan.id
                        ? 'border-primary border-2'
                        : isCurrentPlan
                          ? 'border-green-500 border-2'
                          : 'hover:border-primary/50'
                    }`}
                    onClick={() => !isCurrentPlan && setSelectedNewPlan(plan)}
                  >
                    {isCurrentPlan && (
                      <div className="absolute -top-2 right-2">
                        <Badge className="bg-green-600">Current</Badge>
                      </div>
                    )}
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        {getPlanIcon(plan.name)}
                        {plan.display_name}
                      </CardTitle>
                      <CardDescription>{plan.description}</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="text-2xl font-bold">
                        {isFree ? 'Free' : formatCurrency(plan.price_monthly)}
                        {!isFree && <span className="text-sm font-normal text-muted-foreground">/mo</span>}
                      </div>
                      <div className="space-y-1 text-sm">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-3 w-3 text-green-500" />
                          <span>
                            {plan.max_environments === -1 ? 'Unlimited' : plan.max_environments} Environments
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-3 w-3 text-green-500" />
                          <span>
                            {plan.max_workflows === -1 ? 'Unlimited' : plan.max_workflows} Workflows
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setUpgradePlanDialogOpen(false);
              setSelectedNewPlan(null);
            }}>
              Cancel
            </Button>
            <Button
              disabled={!selectedNewPlan}
              onClick={() => {
                if (selectedSubscription && selectedNewPlan) {
                  handleChangePlan(selectedSubscription, selectedNewPlan);
                }
              }}
            >
              {selectedNewPlan && selectedNewPlan.price_monthly > (selectedSubscription?.plan?.price_monthly || 0)
                ? 'Upgrade Plan'
                : 'Change Plan'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel Subscription Dialog */}
      <AlertDialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel Subscription</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to cancel your {selectedSubscription?.provider?.display_name} subscription?
              Your access will continue until the end of the current billing period
              {selectedSubscription?.current_period_end && (
                <span> ({formatDate(selectedSubscription.current_period_end)})</span>
              )}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep Subscription</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (selectedSubscription) {
                  cancelSubscriptionMutation.mutate(selectedSubscription.provider_id);
                }
              }}
            >
              {cancelSubscriptionMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : null}
              Cancel Subscription
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
