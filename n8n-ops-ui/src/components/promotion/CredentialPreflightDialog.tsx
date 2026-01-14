import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Key,
  Settings,
  Loader2,
} from 'lucide-react';
import type {
  CredentialPreflightResult,
  CredentialIssue,
  ResolvedMapping,
} from '@/types/credentials';

interface CredentialPreflightDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preflightResult: CredentialPreflightResult | null;
  onProceed: () => void;
  onCancel: () => void;
  onMapCredential?: (issue: CredentialIssue) => void;
  isLoading?: boolean;
  targetEnvironmentName?: string;
}

export function CredentialPreflightDialog({
  open,
  onOpenChange,
  preflightResult,
  onProceed,
  onCancel,
  onMapCredential,
  isLoading = false,
  targetEnvironmentName,
}: CredentialPreflightDialogProps) {
  const [activeTab, setActiveTab] = useState('issues');

  if (!preflightResult) return null;

  const hasBlockingIssues = preflightResult.blocking_issues.length > 0;
  const hasWarnings = preflightResult.warnings.length > 0;
  const hasResolved = preflightResult.resolved_mappings.length > 0;
  const totalIssues = preflightResult.blocking_issues.length + preflightResult.warnings.length;

  const getIssueTypeBadge = (issueType: string, isBlocking: boolean) => {
    if (isBlocking) {
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          Blocking
        </Badge>
      );
    }
    switch (issueType) {
      case 'missing_mapping':
        return (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200 gap-1">
            <Key className="h-3 w-3" />
            Missing Mapping
          </Badge>
        );
      case 'mapped_missing_in_target':
        return (
          <Badge variant="outline" className="bg-orange-50 text-orange-700 border-orange-200 gap-1">
            <AlertTriangle className="h-3 w-3" />
            Not in Target
          </Badge>
        );
      case 'no_logical_credential':
        return (
          <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200 gap-1">
            <Settings className="h-3 w-3" />
            No Logical
          </Badge>
        );
      default:
        return <Badge variant="outline">{issueType}</Badge>;
    }
  };

  const renderIssueRow = (issue: CredentialIssue, index: number) => (
    <TableRow key={`${issue.workflow_id}-${issue.logical_credential_key}-${index}`}>
      <TableCell>
        <div className="flex flex-col">
          <span className="font-medium text-sm">{issue.workflow_name}</span>
          <span className="text-xs text-muted-foreground truncate max-w-[150px]">
            {issue.workflow_id}
          </span>
        </div>
      </TableCell>
      <TableCell>
        <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
          {issue.logical_credential_key}
        </code>
      </TableCell>
      <TableCell>{getIssueTypeBadge(issue.issue_type, issue.is_blocking)}</TableCell>
      <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">
        {issue.message}
      </TableCell>
      <TableCell>
        {onMapCredential && (issue.issue_type === 'missing_mapping' || issue.issue_type === 'mapped_missing_in_target') && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onMapCredential(issue)}
            className="gap-1"
          >
            <Key className="h-3 w-3" />
            Map Now
          </Button>
        )}
      </TableCell>
    </TableRow>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {hasBlockingIssues ? (
              <>
                <XCircle className="h-5 w-5 text-destructive" />
                Credential Check Failed
              </>
            ) : hasWarnings ? (
              <>
                <AlertTriangle className="h-5 w-5 text-yellow-500" />
                Credential Warnings
              </>
            ) : (
              <>
                <CheckCircle2 className="h-5 w-5 text-green-500" />
                Credentials Ready
              </>
            )}
          </DialogTitle>
          <DialogDescription>
            {hasBlockingIssues
              ? `${preflightResult.blocking_issues.length} credential mapping(s) must be fixed before deploying${targetEnvironmentName ? ` to ${targetEnvironmentName}` : ''}.`
              : hasWarnings
              ? `${preflightResult.warnings.length} warning(s) found. Review before proceeding.`
              : 'All credential mappings are valid for this deployment.'}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {/* Summary Cards */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <Card className={hasBlockingIssues ? 'border-red-200 bg-red-50/50' : ''}>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center gap-2">
                  <XCircle className={`h-4 w-4 ${hasBlockingIssues ? 'text-red-600' : 'text-muted-foreground'}`} />
                  <span className="text-sm font-medium">Blocking</span>
                </div>
                <div className="text-2xl font-bold mt-1">{preflightResult.blocking_issues.length}</div>
              </CardContent>
            </Card>
            <Card className={hasWarnings ? 'border-yellow-200 bg-yellow-50/50' : ''}>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className={`h-4 w-4 ${hasWarnings ? 'text-yellow-600' : 'text-muted-foreground'}`} />
                  <span className="text-sm font-medium">Warnings</span>
                </div>
                <div className="text-2xl font-bold mt-1">{preflightResult.warnings.length}</div>
              </CardContent>
            </Card>
            <Card className="border-green-200 bg-green-50/50">
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <span className="text-sm font-medium">Resolved</span>
                </div>
                <div className="text-2xl font-bold mt-1">{preflightResult.resolved_mappings.length}</div>
              </CardContent>
            </Card>
          </div>

          {/* Tabs for Issues and Resolved */}
          {(totalIssues > 0 || hasResolved) && (
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="mb-3">
                {totalIssues > 0 && (
                  <TabsTrigger value="issues" className="gap-1">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    Issues ({totalIssues})
                  </TabsTrigger>
                )}
                {hasResolved && (
                  <TabsTrigger value="resolved" className="gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Resolved ({preflightResult.resolved_mappings.length})
                  </TabsTrigger>
                )}
              </TabsList>

              {totalIssues > 0 && (
                <TabsContent value="issues" className="mt-0">
                  <Card>
                    <CardContent className="p-0">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-[180px]">Workflow</TableHead>
                            <TableHead>Credential</TableHead>
                            <TableHead className="w-[130px]">Issue</TableHead>
                            <TableHead>Details</TableHead>
                            <TableHead className="w-[100px]">Action</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {preflightResult.blocking_issues.map((issue, idx) =>
                            renderIssueRow(issue, idx)
                          )}
                          {preflightResult.warnings.map((issue, idx) =>
                            renderIssueRow(issue, idx)
                          )}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>

                  {onMapCredential && hasBlockingIssues && (
                    <Alert className="mt-3">
                      <Key className="h-4 w-4" />
                      <AlertTitle>Quick Fix</AlertTitle>
                      <AlertDescription>
                        Click "Map Now" on each blocking issue to create the required credential mapping,
                        or go to <strong>Credentials → Credential Matrix</strong> to manage all mappings.
                      </AlertDescription>
                    </Alert>
                  )}
                </TabsContent>
              )}

              {hasResolved && (
                <TabsContent value="resolved" className="mt-0">
                  <Card>
                    <CardContent className="p-0">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Logical Credential</TableHead>
                            <TableHead className="w-[50px]"></TableHead>
                            <TableHead>Target Credential</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {preflightResult.resolved_mappings.map((mapping: ResolvedMapping, idx: number) => (
                            <TableRow key={idx}>
                              <TableCell>
                                <div className="flex flex-col">
                                  <code className="text-xs bg-muted px-1.5 py-0.5 rounded w-fit">
                                    {mapping.logical_key}
                                  </code>
                                  <span className="text-xs text-muted-foreground mt-1">
                                    Source: {mapping.source_physical_name}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell>
                                <ArrowRight className="h-4 w-4 text-muted-foreground" />
                              </TableCell>
                              <TableCell>
                                <div className="flex flex-col">
                                  <span className="font-medium text-sm">{mapping.target_physical_name}</span>
                                  <span className="text-xs text-muted-foreground">
                                    ID: {mapping.target_physical_id || 'N/A'}
                                  </span>
                                </div>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </CardContent>
                  </Card>
                </TabsContent>
              )}
            </Tabs>
          )}

          {/* No credentials needed */}
          {!hasBlockingIssues && !hasWarnings && !hasResolved && (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertTitle>No Credentials Required</AlertTitle>
              <AlertDescription>
                The selected workflows do not use any credentials that require mapping.
              </AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            onClick={onProceed}
            disabled={hasBlockingIssues || isLoading}
            variant={hasBlockingIssues ? 'secondary' : 'default'}
          >
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Processing...
              </>
            ) : hasBlockingIssues ? (
              'Fix Issues to Continue'
            ) : hasWarnings ? (
              'Proceed with Warnings'
            ) : (
              'Continue to Deploy'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
