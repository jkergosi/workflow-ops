import { useQuery } from '@tanstack/react-query';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Layers, Plus, Workflow, Zap } from 'lucide-react';
import { useAppStore } from '@/store/use-app-store';
import { apiClient } from '@/lib/api-client';
import { useNavigate } from 'react-router-dom';
import type { TenantProviderSubscription } from '@/types';

export function ProviderSelector() {
  const navigate = useNavigate();
  const { selectedProvider, setSelectedProvider, providerDisplayName, setProviderDisplayName } = useAppStore();

  // Fetch active subscriptions
  const { data: subscriptionsData, isLoading } = useQuery({
    queryKey: ['active-provider-subscriptions'],
    queryFn: () => apiClient.getActiveProviderSubscriptions(),
  });

  const subscriptions: TenantProviderSubscription[] = subscriptionsData?.data || [];

  // Get icon for provider
  const getProviderIcon = (name: string) => {
    switch (name.toLowerCase()) {
      case 'n8n':
        return <Workflow className="h-3 w-3 mr-1.5 text-muted-foreground" />;
      case 'make':
        return <Zap className="h-3 w-3 mr-1.5 text-muted-foreground" />;
      default:
        return <Layers className="h-3 w-3 mr-1.5 text-muted-foreground" />;
    }
  };

  // Handle provider change
  const handleProviderChange = (value: string) => {
    if (value === 'add-provider') {
      navigate('/admin/settings?tab=provider');
      return;
    }

    const subscription = subscriptions.find((s) => s.provider?.name === value);
    if (subscription) {
      setSelectedProvider(value as 'n8n' | 'make');
      setProviderDisplayName(subscription.provider?.display_name || value);
    }
  };

  // If no subscriptions, show just the add button
  if (!isLoading && subscriptions.length === 0) {
    return (
      <div className="hidden md:flex items-center gap-2">
        <button
          onClick={() => navigate('/admin/settings?tab=provider')}
          className="flex items-center gap-1.5 h-8 px-3 text-xs border rounded-md hover:bg-accent"
        >
          <Plus className="h-3 w-3" />
          Add Provider
        </button>
      </div>
    );
  }

  // If only one subscription, just show it without dropdown
  if (!isLoading && subscriptions.length === 1) {
    const sub = subscriptions[0];
    return (
      <div className="hidden md:flex items-center gap-2">
        <div className="flex items-center h-8 px-3 text-xs border rounded-md bg-muted/30">
          {getProviderIcon(sub.provider?.name || '')}
          <span>{providerDisplayName || sub.provider?.display_name || sub.provider?.name}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="hidden md:flex items-center gap-2">
      <Select value={selectedProvider} onValueChange={handleProviderChange}>
        <SelectTrigger className="w-[140px] h-8 text-xs">
          {getProviderIcon(selectedProvider)}
          <SelectValue placeholder="Provider">
            {providerDisplayName || selectedProvider}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {subscriptions.map((sub) => (
            <SelectItem
              key={sub.id}
              value={sub.provider?.name || ''}
            >
              <div className="flex items-center gap-2">
                {sub.provider?.name === selectedProvider
                  ? providerDisplayName
                  : sub.provider?.display_name || sub.provider?.name}
              </div>
            </SelectItem>
          ))}
          <SelectItem value="add-provider">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Plus className="h-3 w-3" />
              Add Provider
            </div>
          </SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
