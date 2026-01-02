// @ts-nocheck
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CreditCard, AlertCircle } from 'lucide-react';

interface PaymentMethodCardProps {
  paymentMethod: {
    brand: string;
    last4: string;
    exp_month: number;
    exp_year: number;
  } | null;
  isFree: boolean;
  onUpdatePaymentMethod: () => void;
  isUpdating: boolean;
}

export function PaymentMethodCard({
  paymentMethod,
  isFree,
  onUpdatePaymentMethod,
  isUpdating,
}: PaymentMethodCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Payment Method</CardTitle>
        <CardDescription>Your default payment method</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {paymentMethod ? (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <CreditCard className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="font-medium capitalize">
                  {paymentMethod.brand} •••• {paymentMethod.last4}
                </p>
                <p className="text-sm text-muted-foreground">
                  Expires {paymentMethod.exp_month}/{paymentMethod.exp_year}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={onUpdatePaymentMethod}
              disabled={isUpdating}
            >
              Update Payment Method
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {!isFree && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  No payment method on file. Please add a payment method to continue service.
                </AlertDescription>
              </Alert>
            )}
            <Button
              variant={isFree ? 'outline' : 'default'}
              onClick={onUpdatePaymentMethod}
              disabled={isUpdating}
            >
              Add Payment Method
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

