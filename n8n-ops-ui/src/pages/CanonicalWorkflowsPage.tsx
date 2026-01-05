import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle2, AlertCircle, RefreshCw, GitBranch, Link2, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth';
import { apiClient } from '@/lib/api-client';
import type {
  CanonicalWorkflow,
  WorkflowEnvMap,
  WorkflowDiffState,
  Environment
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

  useEffect(() => {
    document.title = 'Canonical Workflows - WorkflowOps';
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [workflowsRes, mappingsRes, envsRes] = await Promise.all([
        apiClient.get('/canonical/canonical-workflows'),
        apiClient.get('/canonical/workflow-mappings'),
        apiClient.get('/environments')
      ]);

      setWorkflows(workflowsRes.data);
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
    const interval = setInterval(async () => {
      try {
        const response = await apiClient.get(`/background-jobs/${jobId}`);
        const job = response.data;

        if (job.status === 'completed') {
          clearInterval(interval);
          toast.success('Sync completed');
          loadData();
        } else if (job.status === 'failed') {
          clearInterval(interval);
          toast.error('Sync failed: ' + (job.error_message || 'Unknown error'));
        }
      } catch (error) {
        console.error('Error polling job status:', error);
      }
    }, 2000);
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
            <CardTitle>Canonical Workflows ({workflows.length})</CardTitle>
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
                      <TableCell>{workflow.displayName || 'Unnamed'}</TableCell>
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
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

