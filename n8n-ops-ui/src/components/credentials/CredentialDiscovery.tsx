import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import {
  Search, Key, CheckCircle2, XCircle, Plus, Loader2, RefreshCw, Workflow
} from 'lucide-react';
import type { Environment } from '@/types';
import type { DiscoveredCredential } from '@/types/credentials';

interface CredentialDiscoveryProps {
  onCreateLogical?: (logicalKey: string, type: string, name: string) => void;
  onCreateMapping?: (logicalId: string, envId: string) => void;
}

export function CredentialDiscovery({
  onCreateLogical,
  onCreateMapping,
}: CredentialDiscoveryProps) {
  const queryClient = useQueryClient();
  const [selectedEnvId, setSelectedEnvId] = useState<string>('');

  const { data: envsData } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const environments: Environment[] = envsData?.data || [];

  const {
    data: discoveredData,
    isLoading: isDiscovering,
    refetch: runDiscovery,
  } = useQuery({
    queryKey: ['discovered-credentials', selectedEnvId],
    queryFn: () => apiClient.discoverCredentials(selectedEnvId),
    enabled: false,
  });

  const discovered: DiscoveredCredential[] = discoveredData?.data || [];

  const createLogicalMutation = useMutation({
    mutationFn: (data: { name: string; required_type: string; description?: string; tenant_id: string }) =>
      apiClient.createLogicalCredential(data),
    onSuccess: () => {
      toast.success('Credential alias created');
      queryClient.invalidateQueries({ queryKey: ['logical-credentials'] });
      queryClient.invalidateQueries({ queryKey: ['discovered-credentials'] });
      runDiscovery();
    },
    onError: (error: any) => {
      toast.error(`Failed to create: ${error.message}`);
    },
  });

  const handleDiscover = () => {
    if (!selectedEnvId) {
      toast.error('Please select an environment first');
      return;
    }
    runDiscovery();
  };

  const handleCreateLogical = (cred: DiscoveredCredential) => {
    if (onCreateLogical) {
      onCreateLogical(cred.logicalKey, cred.type, cred.name);
    } else {
      createLogicalMutation.mutate({
        name: cred.logicalKey,
        required_type: cred.type,
        description: `Auto-discovered from workflow scan`,
        tenant_id: '00000000-0000-0000-0000-000000000000',
      });
    }
  };

  const handleCreateAllMissing = () => {
    const missing = discovered.filter((d) => !d.existingLogicalId);
    if (missing.length === 0) {
      toast.info('All credentials already have credential alias definitions');
      return;
    }

    missing.forEach((cred) => {
      createLogicalMutation.mutate({
        name: cred.logicalKey,
        required_type: cred.type,
        description: `Auto-discovered from workflow scan`,
        tenant_id: '00000000-0000-0000-0000-000000000000',
      });
    });
  };

  const getStatusBadge = (status: string, hasLogical: boolean) => {
    if (!hasLogical) {
      return (
        <Badge variant="outline" className="bg-gray-50 text-gray-700">
          No Alias
        </Badge>
      );
    }
    if (status === 'mapped') {
      return (
        <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
          <CheckCircle2 className="h-3 w-3 mr-1" />
          Mapped
        </Badge>
      );
    }
    return (
      <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
        <XCircle className="h-3 w-3 mr-1" />
        Unmapped
      </Badge>
    );
  };

  const missingCount = discovered.filter((d) => !d.existingLogicalId).length;
  const unmappedCount = discovered.filter((d) => d.existingLogicalId && d.mappingStatus !== 'mapped').length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Search className="h-5 w-5" />
          Credential Discovery
        </CardTitle>
        <CardDescription>
          Scan workflows to discover credential references and create credential aliases
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="text-sm font-medium mb-1.5 block">Environment to Scan</label>
            <Select value={selectedEnvId} onValueChange={setSelectedEnvId}>
              <SelectTrigger>
                <SelectValue placeholder="Select environment..." />
              </SelectTrigger>
              <SelectContent>
                {environments.map((env) => (
                  <SelectItem key={env.id} value={env.id}>
                    {env.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={handleDiscover} disabled={!selectedEnvId || isDiscovering}>
            {isDiscovering ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Scan Workflows
          </Button>
        </div>

        {discovered.length > 0 && (
          <>
            <div className="flex items-center justify-between border-t pt-4">
              <div className="flex gap-4 text-sm">
                <span>
                  Found <strong>{discovered.length}</strong> credentials
                </span>
                {missingCount > 0 && (
                  <span className="text-yellow-600">
                    {missingCount} without credential alias definition
                  </span>
                )}
                {unmappedCount > 0 && (
                  <span className="text-orange-600">
                    {unmappedCount} unmapped in this environment
                  </span>
                )}
              </div>
              {missingCount > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCreateAllMissing}
                  disabled={createLogicalMutation.isPending}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  Create All Missing ({missingCount})
                </Button>
              )}
            </div>

            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Credential</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Used By</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[120px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {discovered.map((cred) => (
                  <TableRow key={cred.logicalKey}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Key className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">{cred.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{cred.type}</code>
                    </TableCell>
                    <TableCell>
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div className="flex items-center gap-1 cursor-help">
                              <Workflow className="h-4 w-4 text-muted-foreground" />
                              <span>{cred.workflowCount} workflow{cred.workflowCount !== 1 ? 's' : ''}</span>
                            </div>
                          </TooltipTrigger>
                          <TooltipContent>
                            <div className="max-w-xs">
                              {cred.workflows.slice(0, 5).map((wf) => (
                                <div key={wf.id} className="text-sm">{wf.name}</div>
                              ))}
                              {cred.workflows.length > 5 && (
                                <div className="text-xs text-muted-foreground mt-1">
                                  and {cred.workflows.length - 5} more...
                                </div>
                              )}
                            </div>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </TableCell>
                    <TableCell>
                      {getStatusBadge(cred.mappingStatus, !!cred.existingLogicalId)}
                    </TableCell>
                    <TableCell>
                      {!cred.existingLogicalId ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleCreateLogical(cred)}
                          disabled={createLogicalMutation.isPending}
                        >
                          <Plus className="h-3 w-3 mr-1" />
                          Create
                        </Button>
                      ) : cred.mappingStatus !== 'mapped' ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onCreateMapping?.(cred.existingLogicalId!, selectedEnvId)}
                        >
                          Map
                        </Button>
                      ) : (
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </>
        )}

        {!isDiscovering && discovered.length === 0 && selectedEnvId && (
          <div className="text-center py-8 text-muted-foreground">
            <Search className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Click "Scan Workflows" to discover credentials</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
