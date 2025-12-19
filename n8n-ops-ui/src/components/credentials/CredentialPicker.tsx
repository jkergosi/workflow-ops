import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api-client';
import { Search, Key, Loader2 } from 'lucide-react';
import type { N8NCredentialRef } from '@/types/credentials';

interface CredentialPickerProps {
  environmentId: string;
  filterType?: string;
  value: string;
  onChange: (credentialId: string, credential: N8NCredentialRef | null) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function CredentialPicker({
  environmentId,
  filterType,
  value,
  onChange,
  placeholder = 'Select credential...',
  disabled = false,
}: CredentialPickerProps) {
  const [searchQuery, setSearchQuery] = useState('');

  const { data: credentialsData, isLoading } = useQuery({
    queryKey: ['cached-credentials', environmentId],
    queryFn: () => apiClient.getCredentials({ environmentId }),
    enabled: !!environmentId,
  });

  const credentials = credentialsData?.data || [];

  const filteredCredentials = useMemo(() => {
    let result = credentials;

    if (filterType) {
      result = result.filter((c: N8NCredentialRef) => c.type === filterType);
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (c: N8NCredentialRef) =>
          c.name?.toLowerCase().includes(query) ||
          c.type?.toLowerCase().includes(query)
      );
    }

    return result.sort((a: N8NCredentialRef, b: N8NCredentialRef) =>
      (a.name || '').localeCompare(b.name || '')
    );
  }, [credentials, filterType, searchQuery]);

  const selectedCredential = useMemo(
    () => credentials.find((c: N8NCredentialRef) => c.id === value) || null,
    [credentials, value]
  );

  useEffect(() => {
    if (value && selectedCredential) {
      onChange(value, selectedCredential);
    }
  }, [selectedCredential]);

  const handleSelect = (credId: string) => {
    const cred = credentials.find((c: N8NCredentialRef) => c.id === credId) || null;
    onChange(credId, cred);
  };

  if (!environmentId) {
    return (
      <Select disabled>
        <SelectTrigger>
          <SelectValue placeholder="Select environment first" />
        </SelectTrigger>
      </Select>
    );
  }

  return (
    <Select value={value} onValueChange={handleSelect} disabled={disabled || isLoading}>
      <SelectTrigger>
        {isLoading ? (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Loading credentials...</span>
          </div>
        ) : (
          <SelectValue placeholder={placeholder}>
            {selectedCredential && (
              <div className="flex items-center gap-2">
                <Key className="h-3.5 w-3.5 text-muted-foreground" />
                <span>{selectedCredential.name}</span>
                <span className="text-xs text-muted-foreground">({selectedCredential.type})</span>
              </div>
            )}
          </SelectValue>
        )}
      </SelectTrigger>
      <SelectContent>
        <div className="p-2 border-b">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search credentials..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8"
            />
          </div>
        </div>
        {filteredCredentials.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            {credentials.length === 0
              ? 'No credentials found in this environment'
              : 'No credentials match your search'}
          </div>
        ) : (
          filteredCredentials.map((cred: N8NCredentialRef) => (
            <SelectItem key={cred.id} value={cred.id}>
              <div className="flex items-center gap-2">
                <Key className="h-3.5 w-3.5 text-muted-foreground" />
                <span>{cred.name}</span>
                <span className="text-xs text-muted-foreground">({cred.type})</span>
              </div>
            </SelectItem>
          ))
        )}
      </SelectContent>
    </Select>
  );
}
