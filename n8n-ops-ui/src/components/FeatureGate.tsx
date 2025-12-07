import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useFeatures, type PlanFeatures, FEATURE_DISPLAY_NAMES, FEATURE_REQUIRED_PLANS } from '@/lib/features';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Lock, Sparkles, Crown, ArrowRight } from 'lucide-react';

interface FeatureGateProps {
  feature: keyof PlanFeatures;
  children: React.ReactNode;
  fallback?: React.ReactNode;
  showUpgradePrompt?: boolean;
}

/**
 * Gate content based on feature availability.
 * If feature is available, renders children.
 * If not, renders fallback or upgrade prompt.
 */
export function FeatureGate({ feature, children, fallback, showUpgradePrompt = true }: FeatureGateProps) {
  const { canUseFeature } = useFeatures();

  if (canUseFeature(feature)) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  if (showUpgradePrompt) {
    const requiredPlan = FEATURE_REQUIRED_PLANS[feature];
    return <UpgradePrompt feature={feature} requiredPlan={requiredPlan || 'pro'} />;
  }

  return null;
}

interface UpgradePromptProps {
  feature: keyof PlanFeatures;
  requiredPlan: 'pro' | 'enterprise';
  compact?: boolean;
}

/**
 * Displays an upgrade prompt for locked features.
 */
export function UpgradePrompt({ feature, requiredPlan, compact = false }: UpgradePromptProps) {
  const navigate = useNavigate();
  const displayName = FEATURE_DISPLAY_NAMES[feature];

  if (compact) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Lock className="h-3 w-3" />
        <span>Requires {requiredPlan === 'enterprise' ? 'Enterprise' : 'Pro'} plan</span>
        <Button variant="link" size="sm" className="h-auto p-0" onClick={() => navigate('/billing')}>
          Upgrade
        </Button>
      </div>
    );
  }

  return (
    <Card className="border-dashed">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Lock className="h-5 w-5 text-muted-foreground" />
          {displayName}
        </CardTitle>
        <CardDescription>
          This feature requires a {requiredPlan === 'enterprise' ? 'Enterprise' : 'Pro'} plan.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button onClick={() => navigate('/billing')} className="gap-2">
          {requiredPlan === 'enterprise' ? (
            <Crown className="h-4 w-4" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          Upgrade to {requiredPlan === 'enterprise' ? 'Enterprise' : 'Pro'}
          <ArrowRight className="h-4 w-4" />
        </Button>
      </CardContent>
    </Card>
  );
}

interface LockedFeatureBadgeProps {
  plan: 'pro' | 'enterprise';
  className?: string;
}

/**
 * Badge indicating a feature is locked to a specific plan.
 */
export function LockedFeatureBadge({ plan, className }: LockedFeatureBadgeProps) {
  return (
    <Badge variant="outline" className={`gap-1 ${className || ''}`}>
      {plan === 'enterprise' ? (
        <Crown className="h-3 w-3" />
      ) : (
        <Sparkles className="h-3 w-3" />
      )}
      {plan === 'enterprise' ? 'Enterprise' : 'Pro'}
    </Badge>
  );
}

interface ComingSoonBadgeProps {
  className?: string;
}

/**
 * Badge indicating a feature is coming soon (placeholder).
 */
export function ComingSoonBadge({ className }: ComingSoonBadgeProps) {
  return (
    <Badge variant="secondary" className={`gap-1 ${className || ''}`}>
      Coming Soon
    </Badge>
  );
}

interface FeatureLimitDisplayProps {
  resource: 'environments' | 'team_members';
  showUpgradeButton?: boolean;
}

/**
 * Displays current usage vs limit for a resource.
 */
export function FeatureLimitDisplay({ resource, showUpgradeButton = true }: FeatureLimitDisplayProps) {
  const navigate = useNavigate();
  const { usage, features, isAtLimit } = useFeatures();

  if (!usage || !features) return null;

  const resourceUsage = usage[resource];
  if (!resourceUsage) return null;

  const max = resource === 'environments' ? features.max_environments : features.max_team_members;
  const current = resourceUsage.current;
  const atLimit = isAtLimit(resource);
  const label = resource === 'environments' ? 'Environments' : 'Team Members';

  return (
    <div className={`flex items-center gap-2 text-sm ${atLimit ? 'text-amber-600' : 'text-muted-foreground'}`}>
      <span>
        {current} / {max === 'unlimited' ? 'Unlimited' : max} {label}
      </span>
      {atLimit && showUpgradeButton && (
        <Button variant="link" size="sm" className="h-auto p-0 text-amber-600" onClick={() => navigate('/billing')}>
          Upgrade for more
        </Button>
      )}
    </div>
  );
}

interface PlanBadgeProps {
  plan?: string;
  className?: string;
}

/**
 * Displays a badge for the current plan.
 */
export function PlanBadge({ plan, className }: PlanBadgeProps) {
  const { planName } = useFeatures();
  const displayPlan = plan || planName;

  const variants: Record<string, { variant: 'default' | 'secondary' | 'outline'; icon: React.ReactNode }> = {
    free: { variant: 'outline', icon: null },
    pro: { variant: 'default', icon: <Sparkles className="h-3 w-3 mr-1" /> },
    enterprise: { variant: 'secondary', icon: <Crown className="h-3 w-3 mr-1" /> },
  };

  const config = variants[displayPlan] || variants.free;

  return (
    <Badge variant={config.variant} className={className}>
      {config.icon}
      {displayPlan.charAt(0).toUpperCase() + displayPlan.slice(1)}
    </Badge>
  );
}

/**
 * Hook-based feature check for conditional rendering in components.
 */
export function useFeatureCheck(feature: keyof PlanFeatures) {
  const { canUseFeature, getRequiredPlan, planName } = useFeatures();
  const isAvailable = canUseFeature(feature);
  const requiredPlan = getRequiredPlan(feature);

  return {
    isAvailable,
    requiredPlan,
    currentPlan: planName,
    needsUpgrade: !isAvailable && requiredPlan !== null,
  };
}
