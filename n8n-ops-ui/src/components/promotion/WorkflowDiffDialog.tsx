import { useQuery } from '@tanstack/react-query';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  AlertCircle,
  CheckCircle2,
  Plus,
  Minus,
  Edit,
  GitCompare,
  Loader2,
  XCircle,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import type { WorkflowDiffResult, WorkflowDifference } from '@/types';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface WorkflowDiffDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workflowId: string;
  workflowName: string;
  sourceEnvironmentId: string;
  targetEnvironmentId: string;
  sourceEnvironmentName?: string;
  targetEnvironmentName?: string;
}

export function WorkflowDiffDialog({
  open,
  onOpenChange,
  workflowId,
  workflowName,
  sourceEnvironmentId,
  targetEnvironmentId,
  sourceEnvironmentName,
  targetEnvironmentName,
}: WorkflowDiffDialogProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['workflow-diff', workflowId, sourceEnvironmentId, targetEnvironmentId],
    queryFn: () =>
      apiClient.getWorkflowDiff(workflowId, sourceEnvironmentId, targetEnvironmentId),
    enabled: open && !!workflowId && !!sourceEnvironmentId && !!targetEnvironmentId,
  });

  const diffResult = data?.data;

  const getDiffTypeBadge = (type: string) => {
    switch (type) {
      case 'added':
        return (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 gap-1">
            <Plus className="h-3 w-3" />
            Added
          </Badge>
        );
      case 'removed':
        return (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200 gap-1">
            <Minus className="h-3 w-3" />
            Removed
          </Badge>
        );
      case 'modified':
        return (
          <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200 gap-1">
            <Edit className="h-3 w-3" />
            Modified
          </Badge>
        );
      default:
        return <Badge variant="outline">{type}</Badge>;
    }
  };

  const groupDifferencesByCategory = (differences: WorkflowDifference[]) => {
    const nodes: WorkflowDifference[] = [];
    const connections: WorkflowDifference[] = [];
    const settings: WorkflowDifference[] = [];
    const other: WorkflowDifference[] = [];

    differences.forEach((diff) => {
      if (diff.path.startsWith('nodes[')) {
        nodes.push(diff);
      } else if (diff.path.startsWith('connections')) {
        connections.push(diff);
      } else if (diff.path.startsWith('settings.')) {
        settings.push(diff);
      } else {
        other.push(diff);
      }
    });

    return { nodes, connections, settings, other };
  };

  const formatValue = (value: any): string => {
    if (value === null || value === undefined) {
      return 'null';
    }
    if (typeof value === 'object') {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  };

  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitCompare className="h-5 w-5" />
            Workflow Diff: {workflowName}
          </DialogTitle>
          <DialogDescription>
            Comparing workflow between {sourceEnvironmentName || 'source'} and{' '}
            {targetEnvironmentName || 'target'}
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-muted-foreground">Loading diff...</span>
          </div>
        )}

        {error && (
          <Alert variant="destructive">
            <XCircle className="h-4 w-4" />
            <AlertDescription>
              Failed to load workflow diff: {error instanceof Error ? error.message : 'Unknown error'}
            </AlertDescription>
          </Alert>
        )}

        {diffResult && (
          <div className="space-y-4">
            {/* Summary Card */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Summary</CardTitle>
              </CardHeader>
              <CardContent>
                {!diffResult.targetVersion ? (
                  <Alert>
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                      This is a new workflow that doesn't exist in the target environment.
                    </AlertDescription>
                  </Alert>
                ) : (
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">
                        {diffResult.summary.nodesAdded}
                      </div>
                      <div className="text-sm text-muted-foreground">Nodes Added</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-red-600">
                        {diffResult.summary.nodesRemoved}
                      </div>
                      <div className="text-sm text-muted-foreground">Nodes Removed</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-yellow-600">
                        {diffResult.summary.nodesModified}
                      </div>
                      <div className="text-sm text-muted-foreground">Nodes Modified</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold">
                        {diffResult.summary.connectionsChanged ? (
                          <CheckCircle2 className="h-6 w-6 text-yellow-600 mx-auto" />
                        ) : (
                          <XCircle className="h-6 w-6 text-gray-400 mx-auto" />
                        )}
                      </div>
                      <div className="text-sm text-muted-foreground">Connections</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold">
                        {diffResult.summary.settingsChanged ? (
                          <CheckCircle2 className="h-6 w-6 text-yellow-600 mx-auto" />
                        ) : (
                          <XCircle className="h-6 w-6 text-gray-400 mx-auto" />
                        )}
                      </div>
                      <div className="text-sm text-muted-foreground">Settings</div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Differences */}
            {diffResult.differences.length === 0 ? (
              <Alert>
                <CheckCircle2 className="h-4 w-4" />
                <AlertDescription>
                  {diffResult.targetVersion
                    ? 'No differences found between source and target workflows.'
                    : 'This is a new workflow with no existing version to compare.'}
                </AlertDescription>
              </Alert>
            ) : (
              <Accordion type="multiple" className="w-full">
                {(() => {
                  const { nodes, connections, settings, other } = groupDifferencesByCategory(
                    diffResult.differences
                  );

                  return (
                    <>
                      {/* Nodes Section */}
                      {nodes.length > 0 && (
                        <AccordionItem value="nodes">
                          <AccordionTrigger>
                            <div className="flex items-center gap-2">
                              <span>Nodes</span>
                              <Badge variant="secondary">{nodes.length}</Badge>
                            </div>
                          </AccordionTrigger>
                          <AccordionContent>
                            <div className="space-y-3">
                              {nodes.map((diff, idx) => (
                                <Card key={idx} className="border-l-4 border-l-yellow-500">
                                  <CardContent className="pt-4">
                                    <div className="flex items-start justify-between mb-2">
                                      <div className="flex items-center gap-2">
                                        <span className="font-medium">{diff.path}</span>
                                        {getDiffTypeBadge(diff.type)}
                                      </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-4 text-sm">
                                      <div>
                                        <div className="font-medium text-muted-foreground mb-1">
                                          Source
                                        </div>
                                        <pre className="bg-muted p-2 rounded text-xs overflow-auto max-h-32">
                                          {formatValue(diff.sourceValue)}
                                        </pre>
                                      </div>
                                      <div>
                                        <div className="font-medium text-muted-foreground mb-1">
                                          Target
                                        </div>
                                        <pre className="bg-muted p-2 rounded text-xs overflow-auto max-h-32">
                                          {formatValue(diff.targetValue)}
                                        </pre>
                                      </div>
                                    </div>
                                  </CardContent>
                                </Card>
                              ))}
                            </div>
                          </AccordionContent>
                        </AccordionItem>
                      )}

                      {/* Connections Section */}
                      {connections.length > 0 && (
                        <AccordionItem value="connections">
                          <AccordionTrigger>
                            <div className="flex items-center gap-2">
                              <span>Connections</span>
                              <Badge variant="secondary">{connections.length}</Badge>
                            </div>
                          </AccordionTrigger>
                          <AccordionContent>
                            <div className="space-y-3">
                              {connections.map((diff, idx) => (
                                <Card key={idx} className="border-l-4 border-l-yellow-500">
                                  <CardContent className="pt-4">
                                    <div className="flex items-start justify-between mb-2">
                                      <span className="font-medium">{diff.path}</span>
                                      {getDiffTypeBadge(diff.type)}
                                    </div>
                                    <div className="grid grid-cols-2 gap-4 text-sm">
                                      <div>
                                        <div className="font-medium text-muted-foreground mb-1">
                                          Source
                                        </div>
                                        <pre className="bg-muted p-2 rounded text-xs overflow-auto max-h-32">
                                          {formatValue(diff.sourceValue)}
                                        </pre>
                                      </div>
                                      <div>
                                        <div className="font-medium text-muted-foreground mb-1">
                                          Target
                                        </div>
                                        <pre className="bg-muted p-2 rounded text-xs overflow-auto max-h-32">
                                          {formatValue(diff.targetValue)}
                                        </pre>
                                      </div>
                                    </div>
                                  </CardContent>
                                </Card>
                              ))}
                            </div>
                          </AccordionContent>
                        </AccordionItem>
                      )}

                      {/* Settings Section */}
                      {settings.length > 0 && (
                        <AccordionItem value="settings">
                          <AccordionTrigger>
                            <div className="flex items-center gap-2">
                              <span>Settings</span>
                              <Badge variant="secondary">{settings.length}</Badge>
                            </div>
                          </AccordionTrigger>
                          <AccordionContent>
                            <div className="space-y-3">
                              {settings.map((diff, idx) => (
                                <Card key={idx} className="border-l-4 border-l-yellow-500">
                                  <CardContent className="pt-4">
                                    <div className="flex items-start justify-between mb-2">
                                      <span className="font-medium">{diff.path}</span>
                                      {getDiffTypeBadge(diff.type)}
                                    </div>
                                    <div className="grid grid-cols-2 gap-4 text-sm">
                                      <div>
                                        <div className="font-medium text-muted-foreground mb-1">
                                          Source
                                        </div>
                                        <pre className="bg-muted p-2 rounded text-xs overflow-auto max-h-32">
                                          {formatValue(diff.sourceValue)}
                                        </pre>
                                      </div>
                                      <div>
                                        <div className="font-medium text-muted-foreground mb-1">
                                          Target
                                        </div>
                                        <pre className="bg-muted p-2 rounded text-xs overflow-auto max-h-32">
                                          {formatValue(diff.targetValue)}
                                        </pre>
                                      </div>
                                    </div>
                                  </CardContent>
                                </Card>
                              ))}
                            </div>
                          </AccordionContent>
                        </AccordionItem>
                      )}

                      {/* Other Section */}
                      {other.length > 0 && (
                        <AccordionItem value="other">
                          <AccordionTrigger>
                            <div className="flex items-center gap-2">
                              <span>Other</span>
                              <Badge variant="secondary">{other.length}</Badge>
                            </div>
                          </AccordionTrigger>
                          <AccordionContent>
                            <div className="space-y-3">
                              {other.map((diff, idx) => (
                                <Card key={idx} className="border-l-4 border-l-yellow-500">
                                  <CardContent className="pt-4">
                                    <div className="flex items-start justify-between mb-2">
                                      <span className="font-medium">{diff.path}</span>
                                      {getDiffTypeBadge(diff.type)}
                                    </div>
                                    <div className="grid grid-cols-2 gap-4 text-sm">
                                      <div>
                                        <div className="font-medium text-muted-foreground mb-1">
                                          Source
                                        </div>
                                        <pre className="bg-muted p-2 rounded text-xs overflow-auto max-h-32">
                                          {formatValue(diff.sourceValue)}
                                        </pre>
                                      </div>
                                      <div>
                                        <div className="font-medium text-muted-foreground mb-1">
                                          Target
                                        </div>
                                        <pre className="bg-muted p-2 rounded text-xs overflow-auto max-h-32">
                                          {formatValue(diff.targetValue)}
                                        </pre>
                                      </div>
                                    </div>
                                  </CardContent>
                                </Card>
                              ))}
                            </div>
                          </AccordionContent>
                        </AccordionItem>
                      )}
                    </>
                  );
                })()}
              </Accordion>
            )}

            {/* Close Button */}
            <div className="flex justify-end pt-4">
              <Button onClick={() => onOpenChange(false)}>Close</Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
