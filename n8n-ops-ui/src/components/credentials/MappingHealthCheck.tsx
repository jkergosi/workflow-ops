import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import {
  ShieldCheck, CheckCircle2, XCircle, AlertTriangle, Loader2, RefreshCw
} from 'lucide-react';
import type { Environment } from '@/types';
import type { MappingValidationReport, MappingIssue } from '@/types/credentials';

interface MappingHealthCheckProps {
  onFixMapping?: (mappingId: string) => void;
}

export function MappingHealthCheck({ onFixMapping }: MappingHealthCheckProps) {
  const queryClient = useQueryClient();
  const [selectedEnvId, setSelectedEnvId] = useState<string>('all');

  const { data: envsData } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const environments: Environment[] = envsData?.data || [];

  const validateMutation = useMutation({
    mutationFn: () =>
      apiClient.validateCredentialMappings(selectedEnvId === 'all' ? undefined : selectedEnvId),
    onSuccess: (data) => {
      const report = data.data as MappingValidationReport;
      if (report.issues.length === 0) {
        toast.success(`All ${report.total} mappings are valid`);
      } else {
        toast.warning(`Found ${report.issues.length} issues in ${report.total} mappings`);
      }
      queryClient.invalidateQueries({ queryKey: ['credential-mappings'] });
      queryClient.invalidateQueries({ queryKey: ['credential-matrix'] });
    },
    onError: (error: any) => {
      toast.error(`Validation failed: ${error.message}`);
    },
  });

  const report = validateMutation.data?.data as MappingValidationReport | undefined;

  const getIssueBadge = (issue: string) => {
    switch (issue) {
      case 'credential_not_found':
        return (
          <Badge variant="destructive" className="gap-1">
            <XCircle className="h-3 w-3" />
            Not Found
          </Badge>
        );
      case 'type_mismatch':
        return (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200 gap-1">
            <XCircle className="h-3 w-3" />
            Type Mismatch
          </Badge>
        );
      case 'name_changed':
        return (
          <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200 gap-1">
            <AlertTriangle className="h-3 w-3" />
            Name Changed
          </Badge>
        );
      default:
        return <Badge variant="outline">{issue}</Badge>;
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5" />
          Mapping Health Check
        </CardTitle>
        <CardDescription>
          Validate that all credential mappings still resolve to valid N8N credentials
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="text-sm font-medium mb-1.5 block">Environment Filter</label>
            <Select value={selectedEnvId} onValueChange={setSelectedEnvId}>
              <SelectTrigger>
                <SelectValue placeholder="All environments" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Environments</SelectItem>
                {environments.map((env) => (
                  <SelectItem key={env.id} value={env.id}>
                    {env.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={() => validateMutation.mutate()} disabled={validateMutation.isPending}>
            {validateMutation.isPending ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Validate Mappings
          </Button>
        </div>

        {report && (
          <>
            <div className="grid grid-cols-4 gap-4 pt-4 border-t">
              <Card>
                <CardContent className="pt-4">
                  <div className="text-2xl font-bold">{report.total}</div>
                  <div className="text-sm text-muted-foreground">Total Mappings</div>
                </CardContent>
              </Card>
              <Card className="border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-950/50">
                <CardContent className="pt-4">
                  <div className="text-2xl font-bold text-green-700 dark:text-green-400 flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5" />
                    {report.valid}
                  </div>
                  <div className="text-sm text-green-600 dark:text-green-500">Valid</div>
                </CardContent>
              </Card>
              <Card className="border-red-200 bg-red-50/50 dark:border-red-800 dark:bg-red-950/50">
                <CardContent className="pt-4">
                  <div className="text-2xl font-bold text-red-700 dark:text-red-400 flex items-center gap-2">
                    <XCircle className="h-5 w-5" />
                    {report.invalid}
                  </div>
                  <div className="text-sm text-red-600 dark:text-red-500">Invalid</div>
                </CardContent>
              </Card>
              <Card className="border-yellow-200 bg-yellow-50/50 dark:border-yellow-800 dark:bg-yellow-950/50">
                <CardContent className="pt-4">
                  <div className="text-2xl font-bold text-yellow-700 dark:text-yellow-400 flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5" />
                    {report.stale}
                  </div>
                  <div className="text-sm text-yellow-600 dark:text-yellow-500">Stale</div>
                </CardContent>
              </Card>
            </div>

            {report.issues.length > 0 && (
              <div className="pt-4">
                <h4 className="font-medium mb-2">Issues Found</h4>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Logical Credential</TableHead>
                      <TableHead>Environment</TableHead>
                      <TableHead>Issue</TableHead>
                      <TableHead>Details</TableHead>
                      <TableHead className="w-[100px]">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {report.issues.map((issue: MappingIssue) => (
                      <TableRow key={issue.mappingId}>
                        <TableCell className="font-medium">{issue.logicalName}</TableCell>
                        <TableCell>{issue.environmentName}</TableCell>
                        <TableCell>{getIssueBadge(issue.issue)}</TableCell>
                        <TableCell className="text-sm text-muted-foreground max-w-[300px] truncate">
                          {issue.message}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => onFixMapping?.(issue.mappingId)}
                          >
                            Fix
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            {report.issues.length === 0 && (
              <div className="text-center py-8 text-green-600">
                <CheckCircle2 className="h-12 w-12 mx-auto mb-4" />
                <p className="font-medium">All mappings are healthy!</p>
                <p className="text-sm text-muted-foreground">
                  All {report.total} credential mappings resolve to valid N8N credentials.
                </p>
              </div>
            )}
          </>
        )}

        {!report && !validateMutation.isPending && (
          <div className="text-center py-8 text-muted-foreground">
            <ShieldCheck className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Click "Validate Mappings" to check credential health</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
