import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface ProviderSubscription {
  id: string;
  provider: {
    id: string;
    name: string;
    display_name: string;
  };
  plan: {
    id: string;
    name: string;
    display_name: string;
  };
  status: string;
}

interface ProvidersChipsProps {
  subscriptions: ProviderSubscription[];
  maxVisible?: number;
}

export function ProvidersChips({ subscriptions, maxVisible = 2 }: ProvidersChipsProps) {
  if (!subscriptions || subscriptions.length === 0) {
    return (
      <span className="text-sm text-muted-foreground">No providers</span>
    );
  }

  const visible = subscriptions.slice(0, maxVisible);
  const overflow = subscriptions.slice(maxVisible);

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {visible.map((sub) => (
        <Badge
          key={sub.id}
          variant={sub.status === 'active' ? 'default' : 'secondary'}
          className="text-xs"
        >
          {sub.provider?.display_name || sub.provider?.name || 'Unknown'} · {sub.plan?.display_name || sub.plan?.name || '—'}
        </Badge>
      ))}
      {overflow.length > 0 && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Badge variant="outline" className="text-xs cursor-help">
                +{overflow.length}
              </Badge>
            </TooltipTrigger>
            <TooltipContent>
              <div className="space-y-1">
                {overflow.map((sub) => (
                  <div key={sub.id} className="text-xs">
                    {sub.provider?.display_name || sub.provider?.name || 'Unknown'} · {sub.plan?.display_name || sub.plan?.name || '—'}
                  </div>
                ))}
              </div>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
}

