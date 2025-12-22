// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { apiClient } from '@/lib/api-client';
import type { Environment } from '@/types';
import type { LogicalCredential, CredentialMapping } from '@/types/credentials';
import { Shield, Server, Globe, Plus, Pencil, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { CredentialPicker } from '@/components/credentials/CredentialPicker';
import { Combobox } from '@/components/ui/combobox';
import type { N8NCredentialRef } from '@/types/credentials';

export function CredentialHealthPage() {
  useEffect(() => {
    document.title = 'Credential Health - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  const queryClient = useQueryClient();
  const [selectedEnvId, setSelectedEnvId] = useState<string | undefined>(undefined);
  const [selectedProvider, setSelectedProvider] = useState<string | undefined>(undefined);

  // Dialog states
  const [showLogicalDialog, setShowLogicalDialog] = useState(false);
  const [editingLogical, setEditingLogical] = useState<any | null>(null);
  const [deleteLogicalId, setDeleteLogicalId] = useState<string | null>(null);

  const [showMappingDialog, setShowMappingDialog] = useState(false);
  const [editingMapping, setEditingMapping] = useState<any | null>(null);
  const [deleteMappingId, setDeleteMappingId] = useState<string | null>(null);

  // Form states for logical credential
  const [logicalName, setLogicalName] = useState('');
  const [logicalType, setLogicalType] = useState('');
  const [logicalDescription, setLogicalDescription] = useState('');

  // Form states for mapping
  const [mappingLogicalId, setMappingLogicalId] = useState('');
  const [mappingEnvId, setMappingEnvId] = useState('');
  const [mappingPhysicalId, setMappingPhysicalId] = useState('');
  const [mappingPhysicalName, setMappingPhysicalName] = useState('');
  const [mappingPhysicalType, setMappingPhysicalType] = useState('');
  const [mappingProvider, setMappingProvider] = useState('n8n');

  const { data: envsData } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const { data: providersData } = useQuery({
    queryKey: ['providers-active'],
    queryFn: () => apiClient.getActiveProviders(),
  });

  const { data: logicalCredsData, isLoading: loadingLogical } = useQuery({
    queryKey: ['logical-credentials'],
    queryFn: () => apiClient.listLogicalCredentials(),
  });

  const { data: mappingsData, isLoading: loadingMappings } = useQuery({
    queryKey: ['credential-mappings', selectedEnvId, selectedProvider],
    queryFn: () =>
      apiClient.listCredentialMappings({
        environmentId: selectedEnvId,
        provider: selectedProvider,
      }),
    enabled: true,
  });

  // Fetch all cached credentials to get available types for autocomplete
  const { data: allCredentialsData } = useQuery({
    queryKey: ['all-cached-credentials'],
    queryFn: () => apiClient.getCredentials(),
  });

  // Extract unique credential types for autocomplete
  const availableCredentialTypes = useMemo(() => {
    const types = new Set<string>();
    (allCredentialsData?.data || []).forEach((cred: any) => {
      if (cred.type) types.add(cred.type);
    });
    return Array.from(types).sort();
  }, [allCredentialsData]);

  // Mutations for logical credentials
  const createLogicalMutation = useMutation({
    mutationFn: (data: { name: string; required_type?: string; description?: string; tenant_id: string }) =>
      apiClient.createLogicalCredential(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logical-credentials'] });
      toast.success('Credential alias created');
      closeLogicalDialog();
    },
    onError: (error: any) => {
      toast.error(`Failed to create: ${error.message}`);
    },
  });

  const updateLogicalMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => apiClient.updateLogicalCredential(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logical-credentials'] });
      toast.success('Credential alias updated');
      closeLogicalDialog();
    },
    onError: (error: any) => {
      toast.error(`Failed to update: ${error.message}`);
    },
  });

  const deleteLogicalMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteLogicalCredential(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logical-credentials'] });
      queryClient.invalidateQueries({ queryKey: ['credential-mappings'] });
      toast.success('Credential alias deleted');
      setDeleteLogicalId(null);
    },
    onError: (error: any) => {
      toast.error(`Failed to delete: ${error.message}`);
    },
  });

  // Mutations for mappings
  const createMappingMutation = useMutation({
    mutationFn: (data: any) => apiClient.createCredentialMapping(data),
    onSuccess: (_data, variables) => {
      // Switch to the environment filter to show the newly created mapping
      if (variables.environment_id && variables.environment_id !== selectedEnvId) {
        setSelectedEnvId(variables.environment_id);
      }
      queryClient.invalidateQueries({ queryKey: ['credential-mappings'], refetchType: 'all' });
      queryClient.invalidateQueries({ queryKey: ['credential-matrix'] });
      toast.success('Mapping created');
      closeMappingDialog();
    },
    onError: (error: any) => {
      toast.error(`Failed to create mapping: ${error.message}`);
    },
  });

  const updateMappingMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => apiClient.updateCredentialMapping(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credential-mappings'], refetchType: 'all' });
      queryClient.invalidateQueries({ queryKey: ['credential-matrix'] });
      toast.success('Mapping updated');
      closeMappingDialog();
    },
    onError: (error: any) => {
      toast.error(`Failed to update mapping: ${error.message}`);
    },
  });

  const deleteMappingMutation = useMutation({
    mutationFn: (id: string) => apiClient.deleteCredentialMapping(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credential-mappings'], refetchType: 'all' });
      queryClient.invalidateQueries({ queryKey: ['credential-matrix'] });
      toast.success('Mapping deleted');
      setDeleteMappingId(null);
    },
    onError: (error: any) => {
      toast.error(`Failed to delete mapping: ${error.message}`);
    },
  });

  // Auto-select first environment
  useEffect(() => {
    if (!selectedEnvId && envsData?.data?.length) {
      setSelectedEnvId(envsData.data[0].id);
    }
  }, [envsData, selectedEnvId]);

  // Auto-select provider if multi-provider
  useEffect(() => {
    if (!selectedProvider && providersData?.data?.providers?.length) {
      const first = providersData.data.providers[0];
      if (first?.provider) setSelectedProvider(first.provider);
    }
  }, [providersData, selectedProvider]);

  const envOptions: Environment[] = envsData?.data || [];
  const providers = providersData?.data?.providers || [];
  const logicalCreds = logicalCredsData?.data || [];
  const mappings = mappingsData?.data || [];

  // Helper functions
  const openCreateLogical = () => {
    setEditingLogical(null);
    setLogicalName('');
    setLogicalType('');
    setLogicalDescription('');
    setShowLogicalDialog(true);
  };

  const openEditLogical = (cred: any) => {
    setEditingLogical(cred);
    setLogicalName(cred.name || '');
    setLogicalType(cred.required_type || '');
    setLogicalDescription(cred.description || '');
    setShowLogicalDialog(true);
  };

  const closeLogicalDialog = () => {
    setShowLogicalDialog(false);
    setEditingLogical(null);
    setLogicalName('');
    setLogicalType('');
    setLogicalDescription('');
  };

  const handleSaveLogical = () => {
    if (!logicalName.trim()) {
      toast.error('Name is required');
      return;
    }

    const data = {
      name: logicalName.trim(),
      required_type: logicalType.trim() || undefined,
      description: logicalDescription.trim() || undefined,
      tenant_id: '00000000-0000-0000-0000-000000000000', // Will be overwritten by backend
    };

    if (editingLogical) {
      updateLogicalMutation.mutate({ id: editingLogical.id, data });
    } else {
      createLogicalMutation.mutate(data);
    }
  };

  const openCreateMapping = () => {
    setEditingMapping(null);
    setMappingLogicalId('');
    setMappingEnvId(selectedEnvId || '');
    setMappingPhysicalId('');
    setMappingPhysicalName('');
    setMappingPhysicalType('');
    setMappingProvider(selectedProvider || 'n8n');
    setShowMappingDialog(true);
  };

  const openEditMapping = (mapping: any) => {
    setEditingMapping(mapping);
    setMappingLogicalId(mapping.logical_credential_id || '');
    setMappingEnvId(mapping.environment_id || '');
    setMappingPhysicalId(mapping.physical_credential_id || '');
    setMappingPhysicalName(mapping.physical_name || '');
    setMappingPhysicalType(mapping.physical_type || '');
    setMappingProvider(mapping.provider || 'n8n');
    setShowMappingDialog(true);
  };

  const closeMappingDialog = () => {
    setShowMappingDialog(false);
    setEditingMapping(null);
  };

  const handleSaveMapping = () => {
    if (!mappingLogicalId || !mappingEnvId || !mappingPhysicalId) {
      toast.error('Credential alias, environment, and physical credential ID are required');
      return;
    }

    const data = {
      logical_credential_id: mappingLogicalId,
      environment_id: mappingEnvId,
      physical_credential_id: mappingPhysicalId,
      physical_name: mappingPhysicalName.trim() || undefined,
      physical_type: mappingPhysicalType.trim() || undefined,
      provider: mappingProvider || 'n8n',
      status: 'valid',
      tenant_id: '00000000-0000-0000-0000-000000000000', // Will be overwritten by backend
    };

    if (editingMapping) {
      updateMappingMutation.mutate({
        id: editingMapping.id,
        data: {
          physical_credential_id: data.physical_credential_id,
          physical_name: data.physical_name,
          physical_type: data.physical_type,
          status: data.status,
        },
      });
    } else {
      createMappingMutation.mutate(data);
    }
  };

  // Get logical credential name by ID
  const getLogicalName = (id: string) => {
    const cred = logicalCreds.find((c: any) => c.id === id);
    return cred?.name || id;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Credential Health</h1>
          <p className="text-muted-foreground">
            Manage credential aliases and their environment mappings.
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Environment
            </CardTitle>
            <CardDescription>Select the target environment</CardDescription>
          </CardHeader>
          <CardContent>
            <Select value={selectedEnvId} onValueChange={setSelectedEnvId}>
              <SelectTrigger>
                <SelectValue placeholder="Select environment" />
              </SelectTrigger>
              <SelectContent>
                {envOptions.map((env) => (
                  <SelectItem key={env.id} value={env.id}>
                    {env.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5" />
              Provider
            </CardTitle>
            <CardDescription>Filter by provider (optional)</CardDescription>
          </CardHeader>
          <CardContent>
            <Select value={selectedProvider || 'all'} onValueChange={(v) => setSelectedProvider(v === 'all' ? undefined : v)}>
              <SelectTrigger>
                <SelectValue placeholder="All providers" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All providers</SelectItem>
                <SelectItem value="n8n">n8n</SelectItem>
                {providers.filter((p: any) => p.provider !== 'n8n').map((p: any) => (
                  <SelectItem key={p.provider} value={p.provider}>
                    {p.provider}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Logical Credentials Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Credential Aliases
              </CardTitle>
              <CardDescription>Environment-agnostic credential aliases</CardDescription>
            </div>
            <Button size="sm" onClick={openCreateLogical}>
              <Plus className="h-4 w-4 mr-1" />
              Add
            </Button>
          </CardHeader>
          <CardContent>
            {loadingLogical ? (
              <div className="py-4 text-sm text-muted-foreground">Loading...</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="w-[80px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {logicalCreds.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-sm text-muted-foreground">
                        No credential aliases defined
                      </TableCell>
                    </TableRow>
                  )}
                  {logicalCreds.map((c: any) => (
                    <TableRow key={c.id}>
                      <TableCell className="font-medium">{c.name}</TableCell>
                      <TableCell>{c.required_type || 'Any'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-[150px] truncate">
                        {c.description || '-'}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" onClick={() => openEditLogical(c)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setDeleteLogicalId(c.id)}>
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Credential Mappings Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Credential Mappings
              </CardTitle>
              <CardDescription>Mappings in target environment/provider</CardDescription>
            </div>
            <Button size="sm" onClick={openCreateMapping} disabled={logicalCreds.length === 0}>
              <Plus className="h-4 w-4 mr-1" />
              Add
            </Button>
          </CardHeader>
          <CardContent>
            {loadingMappings ? (
              <div className="py-4 text-sm text-muted-foreground">Loading...</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Credential Alias</TableHead>
                    <TableHead>Physical Credential</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[80px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mappings.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-sm text-muted-foreground">
                        No mappings for this filter
                      </TableCell>
                    </TableRow>
                  )}
                  {mappings.map((m: any) => (
                    <TableRow key={m.id}>
                      <TableCell className="font-medium">{getLogicalName(m.logical_credential_id)}</TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span>{m.physical_name || m.physical_credential_id}</span>
                          <span className="text-xs text-muted-foreground">{m.physical_type || 'unknown'}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={m.status === 'valid' ? 'default' : 'outline'}>
                          {m.status || 'unknown'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" onClick={() => openEditMapping(m)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setDeleteMappingId(m.id)}>
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Logical Credential Dialog */}
      <Dialog open={showLogicalDialog} onOpenChange={setShowLogicalDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingLogical ? 'Edit' : 'Create'} Credential Alias</DialogTitle>
            <DialogDescription>
              Define an environment-agnostic credential alias that can be mapped to physical credentials per environment.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">Name *</Label>
              <Input
                id="name"
                value={logicalName}
                onChange={(e) => setLogicalName(e.target.value)}
                placeholder="e.g., slackApi:prod-slack"
              />
              <p className="text-xs text-muted-foreground">
                Use format "type:name" to match workflow credential references
              </p>
            </div>
            <div className="grid gap-2">
              <Label>Required Type</Label>
              <Combobox
                options={availableCredentialTypes.map((type) => ({ value: type, label: type }))}
                value={logicalType}
                onChange={setLogicalType}
                placeholder="Select or enter type..."
                searchPlaceholder="Search types..."
                emptyText="No matching types"
                allowCustom={true}
              />
              <p className="text-xs text-muted-foreground">
                Select from known types or type a custom value
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={logicalDescription}
                onChange={(e) => setLogicalDescription(e.target.value)}
                placeholder="Optional description"
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeLogicalDialog}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveLogical}
              disabled={createLogicalMutation.isPending || updateLogicalMutation.isPending}
            >
              {editingLogical ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Mapping Dialog */}
      <Dialog open={showMappingDialog} onOpenChange={setShowMappingDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingMapping ? 'Edit' : 'Create'} Credential Mapping</DialogTitle>
            <DialogDescription>
              Map a credential alias to a physical credential in a specific environment. Mapping = alias → physical credential per environment.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="logical">Credential Alias *</Label>
              <Select value={mappingLogicalId} onValueChange={setMappingLogicalId} disabled={!!editingMapping}>
                <SelectTrigger>
                  <SelectValue placeholder="Select credential alias" />
                </SelectTrigger>
                <SelectContent>
                  {logicalCreds.map((c: any) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="env">Environment *</Label>
              <Select value={mappingEnvId} onValueChange={setMappingEnvId} disabled={!!editingMapping}>
                <SelectTrigger>
                  <SelectValue placeholder="Select environment" />
                </SelectTrigger>
                <SelectContent>
                  {envOptions.map((env) => (
                    <SelectItem key={env.id} value={env.id}>
                      {env.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider">Provider</Label>
              <Select value={mappingProvider} onValueChange={setMappingProvider} disabled={!!editingMapping}>
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="n8n">n8n</SelectItem>
                  {providers.map((p: any) => (
                    p.provider !== 'n8n' && (
                      <SelectItem key={p.provider} value={p.provider}>
                        {p.provider}
                      </SelectItem>
                    )
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Physical Credential *</Label>
              <CredentialPicker
                environmentId={mappingEnvId}
                filterType={logicalCreds.find((c: any) => c.id === mappingLogicalId)?.required_type}
                value={mappingPhysicalId}
                onChange={(id: string, cred: N8NCredentialRef | null) => {
                  setMappingPhysicalId(id);
                  if (cred) {
                    setMappingPhysicalName(cred.name);
                    setMappingPhysicalType(cred.type);
                  }
                }}
                placeholder="Select credential from N8N..."
                disabled={!mappingEnvId}
              />
              <p className="text-xs text-muted-foreground">
                Select a credential from the N8N environment
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeMappingDialog}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveMapping}
              disabled={createMappingMutation.isPending || updateMappingMutation.isPending}
            >
              {editingMapping ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Logical Confirmation */}
      <AlertDialog open={!!deleteLogicalId} onOpenChange={() => setDeleteLogicalId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Credential Alias?</AlertDialogTitle>
            <AlertDialogDescription>
              This will also delete all mappings for this credential. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteLogicalId && deleteLogicalMutation.mutate(deleteLogicalId)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Mapping Confirmation */}
      <AlertDialog open={!!deleteMappingId} onOpenChange={() => setDeleteMappingId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Mapping?</AlertDialogTitle>
            <AlertDialogDescription>
              This mapping will be removed. Workflows using this credential may fail to promote.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMappingId && deleteMappingMutation.mutate(deleteMappingId)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
