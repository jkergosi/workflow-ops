import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { apiClient } from '@/lib/api-client';
import { Grid3X3, CheckCircle2, XCircle, AlertTriangle, Plus, Pencil, Loader2, Unlink } from 'lucide-react';
import type { LogicalCredential, CredentialMapping, CredentialMatrixCell, CredentialMatrixEnvironment } from '@/types/credentials';

interface CredentialMatrixProps {
  onCreateMapping?: (logicalId: string, envId: string) => void;
  onEditMapping?: (mappingId: string, logicalId: string, envId: string) => void;
  onUnmapMapping?: (mappingId: string) => void;
  onEditLogical?: (logical: LogicalCredential) => void;
}

export function CredentialMatrix({
  onCreateMapping,
  onEditMapping,
  onUnmapMapping,
  onEditLogical,
}: CredentialMatrixProps) {
  const { data: matrixData, isLoading } = useQuery({
    queryKey: ['credential-matrix'],
    queryFn: () => apiClient.getCredentialMatrix(),
  });

  const matrix = matrixData?.data;
  const logicalCredentials: LogicalCredential[] = matrix?.logical_credentials || [];
  const environments: CredentialMatrixEnvironment[] = matrix?.environments || [];
  const matrixMap: Record<string, Record<string, CredentialMatrixCell | null>> = matrix?.matrix || {};

  const getCellContent = (cell: CredentialMatrixCell | null, logicalId: string, envId: string) => {
    if (!cell) {
      return (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-full text-muted-foreground hover:text-foreground"
                onClick={() => onCreateMapping?.(logicalId, envId)}
              >
                <Plus className="h-4 w-4 mr-1" />
                Map
              </Button>
            </TooltipTrigger>
            <TooltipContent>Create mapping for this environment</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    }

    const statusIcon = () => {
      switch (cell.status) {
        case 'valid':
          return <CheckCircle2 className="h-4 w-4 text-green-600" />;
        case 'invalid':
          return <XCircle className="h-4 w-4 text-red-600" />;
        case 'stale':
          return <AlertTriangle className="h-4 w-4 text-yellow-600" />;
        default:
          return <CheckCircle2 className="h-4 w-4 text-gray-400" />;
      }
    };

    return (
      <div className="flex items-center gap-1">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 flex-1 justify-start gap-2"
                onClick={() => onEditMapping?.(cell.mappingId!, logicalId, envId)}
              >
                {statusIcon()}
                <span className="truncate text-sm">{cell.physicalName || cell.physicalCredentialId}</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <div className="space-y-1">
                <div className="font-medium">{cell.physicalName}</div>
                <div className="text-xs text-muted-foreground">Type: {cell.physicalType}</div>
                <div className="text-xs text-muted-foreground">ID: {cell.physicalCredentialId}</div>
                <div className="text-xs">Status: {cell.status || 'unknown'}</div>
              </div>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  onUnmapMapping?.(cell.mappingId!);
                }}
              >
                <Unlink className="h-3 w-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Unmap this credential</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    );
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (logicalCredentials.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Grid3X3 className="h-5 w-5" />
            Mapping
          </CardTitle>
          <CardDescription>
            Cross-environment view of credential aliases and their mappings to physical credentials. Mapping = alias → physical credential per environment.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <Grid3X3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No credential aliases defined yet.</p>
            <p className="text-sm mt-1">
              Create credential aliases to map them to physical credentials across environments.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Grid3X3 className="h-5 w-5" />
          Mapping
        </CardTitle>
        <CardDescription>
          Cross-environment view of credential aliases and their mappings to physical credentials. Mapping = alias → physical credential per environment.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[200px] min-w-[200px]">Credential Alias</TableHead>
                {environments.map((env) => (
                  <TableHead key={env.id} className="min-w-[180px]">
                    <span>{env.name}</span>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {logicalCredentials.map((lc) => (
                <TableRow key={lc.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-auto p-0 hover:bg-transparent"
                        onClick={() => onEditLogical?.(lc)}
                      >
                        <span className="truncate">{lc.name}</span>
                        <Pencil className="h-3 w-3 ml-1 opacity-0 group-hover:opacity-100" />
                      </Button>
                    </div>
                    {lc.requiredType && (
                      <span className="text-xs text-muted-foreground block">{lc.requiredType}</span>
                    )}
                  </TableCell>
                  {environments.map((env) => (
                    <TableCell key={env.id} className="p-1">
                      {getCellContent(matrixMap[lc.id]?.[env.id] || null, lc.id, env.id)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <div className="mt-4 flex items-center gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-1">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <span>Valid</span>
          </div>
          <div className="flex items-center gap-1">
            <XCircle className="h-4 w-4 text-red-600" />
            <span>Invalid</span>
          </div>
          <div className="flex items-center gap-1">
            <AlertTriangle className="h-4 w-4 text-yellow-600" />
            <span>Stale</span>
          </div>
          <div className="flex items-center gap-1">
            <Plus className="h-4 w-4" />
            <span>Not Mapped</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
