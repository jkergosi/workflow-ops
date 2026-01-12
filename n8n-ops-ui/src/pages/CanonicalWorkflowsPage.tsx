import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { PaginationControls } from '@/components/ui/pagination-controls';
import { CheckCircle2, AlertCircle, RefreshCw, GitBranch, Link2, FileText, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth';
import { apiClient } from '@/lib/api-client';
import type {
  CanonicalWorkflow,
  WorkflowEnvMap,
  WorkflowDiffState,
  Environment,
  PaginatedResponse
} from '@/types';

export function CanonicalWorkflowsPage() {
  const navigate = useNavigate();
  const { tenant } = useAuth();
  const [workflows, setWorkflows] = useState<CanonicalWorkflow[]>([]);
  const [mappings, setMappings] = useState<WorkflowEnvMap[]>([]);
  const [diffStates, setDiffStates] = useState<WorkflowDiffState[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedEnv, setSelectedEnv] = useState<string>('');

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(0);

  useEffect(() => {
    document.title = 'Canonical Workflows - WorkflowOps';
    loadData();
  }, [currentPage, pageSize]);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [workflowsRes, mappingsRes, envsRes] = await Promise.all([
        apiClient.getCanonicalWorkflows({
          page: currentPage,
          pageSize: pageSize
        }),
        apiClient.get('/canonical/workflow-mappings'),
        apiClient.get('/environments')
      ]);

      const paginatedData = workflowsRes.data as PaginatedResponse<CanonicalWorkflow>;
      setWorkflows(paginatedData.items);
      setTotalItems(paginatedData.total);
      setTotalPages(paginatedData.totalPages);

      setMappings(mappingsRes.data);
      setEnvironments(envsRes.data);

      if (envsRes.data.length > 0 && !selectedEnv) {
        setSelectedEnv(envsRes.data[0].id);
      }
    } catch (error: any) {
      toast.error('Failed to load canonical workflows');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSyncRepo = async (environmentId: string) => {
    try {
      const response = await apiClient.post(`/canonical/sync/repo/${environmentId}`);
      toast.success('Repository sync started');
      // Poll for completion
      pollJobStatus(response.data.jobId);
    } catch (error: any) {
      toast.error('Failed to start repository sync');
      console.error(error);
    }
  };

  const handleSyncEnv = async (environmentId: string) => {
    try {
      const response = await apiClient.post(`/canonical/sync/env/${environmentId}`);
      toast.success('Environment sync started');
      // Poll for completion
      pollJobStatus(response.data.jobId);
    } catch (error: any) {
      toast.error('Failed to start environment sync');
      console.error(error);
    }
  };

  const pollJobStatus = async (jobId: string) => {
    // Exponential backoff: start at 1s, max 10s, factor 1.5
    let delay = 1000;
    const maxDelay = 10000;
    const backoffFactor = 1.5;
    let attempts = 0;
    const maxAttempts = 60; // ~2-3 minutes max

    const poll = async () => {
      if (attempts >= maxAttempts) {
        toast.error('Sync is taking too long. Check Activity Center for status.');
        return;
      }
      attempts++;

      try {
        const response = await apiClient.get(`/background-jobs/${jobId}`);
        const job = response.data;

        if (job.status === 'completed') {
          toast.success('Sync completed');
          loadData();
          return;
        } else if (job.status === 'failed') {
          toast.error('Sync failed: ' + (job.error_message || 'Unknown error'));
          return;
        }

        // Still running - schedule next poll with exponential backoff
        delay = Math.min(delay * backoffFactor, maxDelay);
        setTimeout(poll, delay);
      } catch (error) {
        console.error('Error polling job status:', error);
        // On error, still retry with backoff
        delay = Math.min(delay * backoffFactor, maxDelay);
        setTimeout(poll, delay);
      }
    };

    // Start polling after initial delay
    setTimeout(poll, delay);
  };

  const getMappingForWorkflow = (canonicalId: string, envId: string): WorkflowEnvMap | undefined => {
    return mappings.find(m => m.canonicalId === canonicalId && m.environmentId === envId);
  };

  const getDiffForWorkflow = (canonicalId: string, sourceEnvId: string, targetEnvId: string): WorkflowDiffState | undefined => {
    return diffStates.find(d => 
      d.canonicalId === canonicalId && 
      d.sourceEnvId === sourceEnvId && 
      d.targetEnvId === targetEnvId
    );
  };

  const getEnvName = (envId: string): string => {
    return environments.find(e => e.id === envId)?.name || envId;
  };

  if (isLoading) {
    return (
      <div className="container mx-auto py-8">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Canonical Workflows</h1>
          <p className="text-muted-foreground mt-2">
            Manage workflow identity across environments
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={loadData}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button onClick={() => navigate('/canonical/onboarding')}>
            Onboarding
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        {/* Environment Sync Controls */}
        <Card>
          <CardHeader>
            <CardTitle>Environment Sync</CardTitle>
            <CardDescription>Sync workflows from Git or n8n</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {environments.map(env => (
                <div key={env.id} className="flex items-center justify-between p-4 border rounded">
                  <div>
                    <div className="font-medium">{env.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {env.gitRepoUrl ? 'Git configured' : 'No Git repo'}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {env.gitRepoUrl && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleSyncRepo(env.id)}
                      >
                        <GitBranch className="mr-2 h-4 w-4" />
                        Sync Git
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleSyncEnv(env.id)}
                    >
                      <RefreshCw className="mr-2 h-4 w-4" />
                      Sync n8n
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Workflows Table */}
        <Card>
          <CardHeader>
            <CardTitle>Canonical Workflows ({totalItems})</CardTitle>
            <CardDescription>Workflows with canonical identity</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Canonical ID</TableHead>
                  <TableHead>Display Name</TableHead>
                  {environments.map(env => (
                    <TableHead key={env.id}>{env.name}</TableHead>
                  ))}
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {workflows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={environments.length + 4} className="text-center text-muted-foreground">
                      No canonical workflows found
                    </TableCell>
                  </TableRow>
                ) : (
                  workflows.map(workflow => (
                    <TableRow key={workflow.canonicalId}>
                      <TableCell className="font-mono text-xs">
                        {workflow.canonicalId.substring(0, 8)}...
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span>{workflow.displayName || 'Unnamed'}</span>
                          {workflow.collisionWarnings && workflow.collisionWarnings.length > 0 && (
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <div className="flex items-center gap-1 cursor-help">
                                    <AlertTriangle className="h-4 w-4 text-amber-500" />
                                    <Badge variant="outline" className="text-xs border-amber-500 text-amber-700 dark:text-amber-400">
                                      Collision
                                    </Badge>
                                  </div>
                                </TooltipTrigger>
                                <TooltipContent className="max-w-md p-3">
                                  <div className="space-y-2">
                                    <div className="font-semibold text-sm">Hash Collision Detected</div>
                                    <div className="text-xs text-muted-foreground space-y-1">
                                      {workflow.collisionWarnings.map((warning, idx) => (
                                        <div key={idx} className="flex items-start gap-2">
                                          <span className="text-amber-500">•</span>
                                          <span>{warning}</span>
                                        </div>
                                      ))}
                                    </div>
                                    <div className="text-xs text-muted-foreground pt-1 border-t">
                                      The system has applied a deterministic fallback hash to prevent conflicts.
                                    </div>
                                  </div>
                                </TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}
                        </div>
                      </TableCell>
                      {environments.map(env => {
                        const mapping = getMappingForWorkflow(workflow.canonicalId, env.id);
                        return (
                          <TableCell key={env.id}>
                            {mapping ? (
                              <div className="flex items-center gap-2">
                                <CheckCircle2 className="h-4 w-4 text-green-500" />
                                <span className="text-xs text-muted-foreground">
                                  {mapping.n8nWorkflowId || 'Linked'}
                                </span>
                                {mapping.status && (
                                  <Badge variant="outline" className="text-xs">
                                    {mapping.status}
                                  </Badge>
                                )}
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">Not mapped</span>
                            )}
                          </TableCell>
                        );
                      })}
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(workflow.createdAt).toLocaleDateString()}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>

            <PaginationControls
              currentPage={currentPage}
              totalPages={totalPages}
              total={totalItems}
              pageSize={pageSize}
              onPageChange={setCurrentPage}
              onPageSizeChange={(newSize) => {
                setPageSize(newSize);
                setCurrentPage(1); // Reset to first page when page size changes
              }}
              isLoading={isLoading}
              itemLabel="workflows"
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

