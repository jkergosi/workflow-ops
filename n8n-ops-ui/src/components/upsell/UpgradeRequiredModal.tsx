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
import { ArrowRight, Sparkles, Crown } from 'lucide-react';

interface UpgradeRequiredModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  requiredPlan: 'pro' | 'agency' | 'enterprise';
  featureName: string;
  benefits: string[];
}

export function UpgradeRequiredModal({
  open,
  onOpenChange,
  requiredPlan,
  featureName,
  benefits,
}: UpgradeRequiredModalProps) {
  const navigate = useNavigate();

  const handleUpgrade = () => {
    onOpenChange(false);
    navigate('/admin/providers');
  };

  const planDisplayName = requiredPlan === 'enterprise' ? 'Enterprise' : requiredPlan === 'agency' ? 'Agency' : 'Pro';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upgrade Required</DialogTitle>
          <DialogDescription>
            {featureName} is available on {planDisplayName} plans.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <p className="text-sm text-muted-foreground">
            Upgrade to {planDisplayName} to access this feature and more:
          </p>
          <ul className="space-y-2 text-sm">
            {benefits.map((benefit, index) => (
              <li key={index} className="flex items-start gap-2">
                <span className="text-primary mt-0.5">•</span>
                <span>{benefit}</span>
              </li>
            ))}
          </ul>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleUpgrade} className="gap-2">
            {requiredPlan === 'enterprise' ? (
              <Crown className="h-4 w-4" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Upgrade to {planDisplayName}
            <ArrowRight className="h-4 w-4" />
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

