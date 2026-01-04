// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { api } from '@/lib/api';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { SubscriptionOverviewCard } from '@/components/billing/SubscriptionOverviewCard';
import { UsageLimitsSummaryCard } from '@/components/billing/UsageLimitsSummaryCard';
import { PaymentMethodCard } from '@/components/billing/PaymentMethodCard';
import { InvoicesTable } from '@/components/billing/InvoicesTable';
import { ChangePlanModal } from '@/components/billing/ChangePlanModal';

export function BillingPage() {
  useEffect(() => {
    document.title = 'Billing - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [changePlanModalOpen, setChangePlanModalOpen] = useState(false);

  const {
    data: overview,
    isLoading,
    error,
    refetch,
    isRefetching,
  } = useQuery({
    queryKey: ['billing-overview'],
    queryFn: () => api.getBillingOverview(),
    retry: 1,
  });

  const portalMutation = useMutation({
    mutationFn: () => api.createPortalSession(`${window.location.origin}/admin/providers`),
    onSuccess: (result) => {
      window.location.href = result.data.url;
    },
    onError: () => {
      toast.error('Failed to open customer portal');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelSubscription(true),
    onSuccess: () => {
      toast.success('Subscription will be canceled at the end of the billing period');
      queryClient.invalidateQueries({ queryKey: ['billing-overview'] });
      setCancelDialogOpen(false);
    },
    onError: () => {
      toast.error('Failed to cancel subscription');
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: () => api.reactivateSubscription(),
    onSuccess: () => {
      toast.success('Subscription reactivated successfully');
      queryClient.invalidateQueries({ queryKey: ['billing-overview'] });
    },
    onError: () => {
      toast.error('Failed to reactivate subscription');
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="mt-4 text-muted-foreground">Loading billing information...</p>
        </div>
      </div>
    );
  }

  if (error || !overview?.data) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Billing & Subscription</h1>
          <p className="text-muted-foreground">Manage your subscription and billing</p>
        </div>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>Failed to load billing information. Please try again.</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isRefetching}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isRefetching ? 'animate-spin' : ''}`} />
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const data = overview.data;
  const isFree = data.plan.key === 'free';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Billing & Subscription</h1>
        <p className="text-muted-foreground">Manage your subscription and billing</p>
      </div>

      {/* Subscription Overview Card */}
      <SubscriptionOverviewCard
        plan={data.plan}
        subscription={data.subscription}
        onChangePlan={() => setChangePlanModalOpen(true)}
        onManageSubscription={() => portalMutation.mutate()}
        onCancelSubscription={() => setCancelDialogOpen(true)}
        onReactivateSubscription={() => reactivateMutation.mutate()}
        isManagingSubscription={portalMutation.isPending}
        isReactivating={reactivateMutation.isPending}
      />

      {/* Usage & Limits Summary Card */}
      <UsageLimitsSummaryCard
        usage={data.usage}
        entitlements={data.entitlements}
        usageLimitsUrl={data.links.usage_limits_url}
        onViewFullUsage={() => navigate(data.links.usage_limits_url)}
      />

      {/* Payment Method Card */}
      <PaymentMethodCard
        paymentMethod={data.payment_method}
        isFree={isFree}
        onUpdatePaymentMethod={() => portalMutation.mutate()}
        isUpdating={portalMutation.isPending}
      />

      {/* Invoices Table */}
      <InvoicesTable invoices={data.invoices} />

      {/* Links to Admin Pages */}
      {(data.links.usage_limits_url || data.links.entitlements_audit_url) && (
        <div className="text-sm text-muted-foreground space-y-1">
          {data.links.usage_limits_url && (
            <div>
              <Button
                variant="link"
                className="p-0 h-auto"
                onClick={() => navigate(data.links.usage_limits_url)}
              >
                View Usage & Limits →
              </Button>
            </div>
          )}
          {data.links.entitlements_audit_url && (
            <div>
              <Button
                variant="link"
                className="p-0 h-auto"
                onClick={() => navigate(data.links.entitlements_audit_url)}
              >
                View Entitlements Audit →
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Change Plan Modal */}
      <ChangePlanModal
        open={changePlanModalOpen}
        onOpenChange={setChangePlanModalOpen}
        currentPlanKey={data.plan.key}
      />

      {/* Cancel Confirmation Dialog */}
      <Dialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Cancel Subscription</DialogTitle>
            <DialogDescription>
              Are you sure you want to cancel your subscription? You will retain access until the end of your billing period.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelDialogOpen(false)}>
              Keep Subscription
            </Button>
            <Button
              variant="destructive"
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
            >
              {cancelMutation.isPending ? 'Canceling...' : 'Yes, Cancel'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
