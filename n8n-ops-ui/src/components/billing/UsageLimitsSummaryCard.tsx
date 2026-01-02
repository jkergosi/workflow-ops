// @ts-nocheck
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { formatLimit, isNearLimit } from '@/lib/billing-utils';

interface UsageLimitsSummaryCardProps {
  usage: {
    environments_used: number;
    team_members_used: number;
  };
  entitlements: {
    environments_limit: string | number;
    team_members_limit: string | number;
  };
  usageLimitsUrl?: string;
  onViewFullUsage?: () => void;
}

export function UsageLimitsSummaryCard({
  usage,
  entitlements,
  usageLimitsUrl,
  onViewFullUsage,
}: UsageLimitsSummaryCardProps) {
  const envNearLimit = isNearLimit(usage.environments_used, entitlements.environments_limit);
  const teamNearLimit = isNearLimit(usage.team_members_used, entitlements.team_members_limit);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Usage & Limits Summary</CardTitle>
        <CardDescription>Current usage against your plan limits</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm">Environments</span>
            <div className="flex items-center gap-2">
              <span
                className={`text-sm font-medium ${
                  envNearLimit ? 'text-yellow-600' : ''
                }`}
              >
                {usage.environments_used} / {formatLimit(entitlements.environments_limit)}
              </span>
              {envNearLimit && (
                <Badge variant="outline" className="text-yellow-600 border-yellow-600">
                  Near Limit
                </Badge>
              )}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Team Members</span>
            <div className="flex items-center gap-2">
              <span
                className={`text-sm font-medium ${
                  teamNearLimit ? 'text-yellow-600' : ''
                }`}
              >
                {usage.team_members_used} / {formatLimit(entitlements.team_members_limit)}
              </span>
              {teamNearLimit && (
                <Badge variant="outline" className="text-yellow-600 border-yellow-600">
                  Near Limit
                </Badge>
              )}
            </div>
          </div>
        </div>
        {usageLimitsUrl && (
          <Button
            variant="link"
            className="p-0 h-auto"
            onClick={onViewFullUsage}
          >
            View full usage & limits →
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

