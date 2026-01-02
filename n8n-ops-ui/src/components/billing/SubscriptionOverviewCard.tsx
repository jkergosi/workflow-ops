// @ts-nocheck
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Calendar, AlertCircle } from 'lucide-react';

interface SubscriptionOverviewCardProps {
  plan: { key: string; name: string; is_custom: boolean };
  subscription: {
    status: string;
    interval: string;
    current_period_end: string | null;
    cancel_at_period_end: boolean;
    next_amount_cents: number | null;
    currency: string;
  };
  onChangePlan: () => void;
  onManageSubscription: () => void;
  onCancelSubscription: () => void;
  onReactivateSubscription: () => void;
  isManagingSubscription: boolean;
  isReactivating: boolean;
}

export function SubscriptionOverviewCard({
  plan,
  subscription,
  onChangePlan,
  onManageSubscription,
  onCancelSubscription,
  onReactivateSubscription,
  isManagingSubscription,
  isReactivating,
}: SubscriptionOverviewCardProps) {
  const isFree = plan.key === 'free';
  const status = subscription.status;
  const isPastDue = status === 'past_due' || status === 'unpaid';
  const isCanceled = status === 'canceled' || subscription.cancel_at_period_end;

  const formatCurrency = (cents: number | null, currency: string = 'USD') => {
    if (cents === null || cents === undefined) return '—';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(cents / 100);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
        return 'default';
      case 'trialing':
        return 'secondary';
      case 'past_due':
      case 'unpaid':
        return 'destructive';
      case 'canceled':
        return 'outline';
      default:
        return 'outline';
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Subscription Overview</CardTitle>
        <CardDescription>Your current subscription details</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-2xl font-bold">{plan.name}</p>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={getStatusBadgeVariant(status)}>{status}</Badge>
              {subscription.interval && (
                <span className="text-sm text-muted-foreground capitalize">
                  {subscription.interval}ly billing
                </span>
              )}
            </div>
          </div>
        </div>

        {subscription.current_period_end && (
          <div className="flex items-center gap-2 text-sm">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            {isCanceled ? (
              <span>Cancels on {formatDate(subscription.current_period_end)}</span>
            ) : (
              <span>Next invoice: {formatDate(subscription.current_period_end)}</span>
            )}
            {subscription.next_amount_cents && !isCanceled && (
              <span className="text-muted-foreground">
                ({formatCurrency(subscription.next_amount_cents, subscription.currency)})
              </span>
            )}
          </div>
        )}

        {isPastDue && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Your payment is past due. Please update your payment method to continue service.
            </AlertDescription>
          </Alert>
        )}

        <div className="flex gap-2 pt-2">
          <Button onClick={onChangePlan} variant="default">
            Change Plan
          </Button>
          {!isFree && (
            <Button
              onClick={onManageSubscription}
              variant="outline"
              disabled={isManagingSubscription}
            >
              {isManagingSubscription ? 'Opening...' : 'Manage Subscription'}
            </Button>
          )}
          {!isFree && !isCanceled && (
            <Button
              onClick={onCancelSubscription}
              variant="ghost"
              className="text-red-500 hover:text-red-600"
            >
              Cancel Subscription
            </Button>
          )}
          {isCanceled && !isFree && (
            <Button
              onClick={onReactivateSubscription}
              variant="default"
              disabled={isReactivating}
            >
              {isReactivating ? 'Reactivating...' : 'Reactivate Subscription'}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

