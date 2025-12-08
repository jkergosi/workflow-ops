import { useParams, useSearchParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { api } from '@/lib/api';
import { apiClient } from '@/lib/api-client';
import { analyzeWorkflow, type WorkflowAnalysis } from '@/lib/workflow-analysis';
import { WorkflowHeroSection } from '@/components/workflow/WorkflowHeroSection';
import { toast } from 'sonner';
import {
  ArrowLeft,
  PlayCircle,
  PauseCircle,
  Calendar,
  Clock,
  Activity,
  GitBranch,
  Box,
  Network,
  FileText,
  Shield,
  AlertTriangle,
  Zap,
  DollarSign,
  Lock,
  Wrench,
  Scale,
  GitCompare,
  Lightbulb,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Info,
  ChevronRight,
  Database,
  Globe,
  Mail,
  HardDrive,
  Server,
  Workflow as WorkflowIcon,
  RefreshCw,
} from 'lucide-react';
import type { EnvironmentType, Workflow, WorkflowNode, ExecutionMetricsSummary, Execution } from '@/types';

// Score badge component
function ScoreBadge({ score, level }: { score: number; level: string }) {
  const getVariant = () => {
    if (level === 'excellent' || level === 'fully-compliant' || level === 'low') return 'success';
    if (level === 'good' || level === 'compliant' || level === 'medium') return 'default';
    if (level === 'fair' || level === 'partial' || level === 'warning' || level === 'high') return 'warning';
    return 'destructive';
  };

  return (
    <Badge variant={getVariant()} className="text-sm font-medium">
      {score}/100 - {level.charAt(0).toUpperCase() + level.slice(1).replace('-', ' ')}
    </Badge>
  );
}

// Recommendation list component
function RecommendationList({ recommendations }: { recommendations: string[] }) {
  if (recommendations.length === 0) return null;
  return (
    <div className="mt-4 space-y-2">
      <h4 className="text-sm font-medium flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-yellow-500" />
        Recommendations
      </h4>
      <ul className="space-y-1">
        {recommendations.map((rec, i) => (
          <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
            <ChevronRight className="h-4 w-4 mt-0.5 flex-shrink-0" />
            {rec}
          </li>
        ))}
      </ul>
    </div>
  );
}

// Issue list component
function IssueList({ issues, type = 'warning' }: { issues: string[]; type?: 'warning' | 'error' | 'info' }) {
  if (issues.length === 0) return null;
  const Icon = type === 'error' ? XCircle : type === 'warning' ? AlertCircle : Info;
  const colorClass = type === 'error' ? 'text-red-500' : type === 'warning' ? 'text-yellow-500' : 'text-blue-500';

  return (
    <ul className="space-y-1">
      {issues.map((issue, i) => (
        <li key={i} className="text-sm flex items-start gap-2">
          <Icon className={`h-4 w-4 mt-0.5 flex-shrink-0 ${colorClass}`} />
          <span className="text-muted-foreground">{issue}</span>
        </li>
      ))}
    </ul>
  );
}

// Dependency icon component
function DependencyIcon({ type }: { type: string }) {
  const iconMap: Record<string, React.ReactNode> = {
    api: <Globe className="h-4 w-4" />,
    webhook: <Network className="h-4 w-4" />,
    subworkflow: <WorkflowIcon className="h-4 w-4" />,
    database: <Database className="h-4 w-4" />,
    file: <HardDrive className="h-4 w-4" />,
    email: <Mail className="h-4 w-4" />,
    queue: <Server className="h-4 w-4" />,
    ssh: <Server className="h-4 w-4" />,
    ftp: <Server className="h-4 w-4" />,
  };
  return iconMap[type] || <Box className="h-4 w-4" />;
}

// Helper to calculate execution metrics from executions
function calculateExecutionMetrics(executions: Execution[]): ExecutionMetricsSummary {
  if (!executions || executions.length === 0) {
    return {
      totalExecutions: 0,
      successCount: 0,
      failureCount: 0,
      successRate: 0,
      avgDurationMs: 0,
      p95DurationMs: 0,
      lastExecutedAt: null,
      recentExecutions: [],
    };
  }

  const successCount = executions.filter(e => e.status === 'success').length;
  const failureCount = executions.filter(e => e.status === 'error').length;
  const successRate = executions.length > 0 ? (successCount / executions.length) * 100 : 0;

  const durations = executions
    .filter(e => e.executionTime && e.executionTime > 0)
    .map(e => e.executionTime as number)
    .sort((a, b) => a - b);

  const avgDurationMs = durations.length > 0
    ? durations.reduce((a, b) => a + b, 0) / durations.length
    : 0;

  const p95Index = Math.floor(durations.length * 0.95);
  const p95DurationMs = durations.length > 0 ? durations[p95Index] || durations[durations.length - 1] : 0;

  const sortedByDate = [...executions].sort((a, b) =>
    new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime()
  );

  return {
    totalExecutions: executions.length,
    successCount,
    failureCount,
    successRate,
    avgDurationMs,
    p95DurationMs,
    lastExecutedAt: sortedByDate[0]?.startedAt || null,
    recentExecutions: sortedByDate.slice(0, 5),
  };
}

export function WorkflowDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const environment = (searchParams.get('environment') || 'dev') as EnvironmentType;
  const [activeTab, setActiveTab] = useState('overview');

  // Workflow query
  const { data: workflowResponse, isLoading, error } = useQuery({
    queryKey: ['workflow', id, environment],
    queryFn: async () => {
      const response = await api.getWorkflow(id!, environment);
      // Handle both ApiResponse<Workflow> and { data: Workflow } formats
      if ('success' in response && response.data) {
        return response.data as Workflow;
      }
      return (response as { data: Workflow }).data;
    },
    enabled: !!id,
  });

  const workflow = workflowResponse;

  // Drift detection query
  const { data: driftData, isLoading: isLoadingDrift } = useQuery({
    queryKey: ['workflow-drift', id, environment],
    queryFn: async () => {
      const response = await apiClient.getWorkflowDrift(id!, environment);
      return response.data;
    },
    enabled: !!id && !!workflow,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  // Executions query for metrics
  const { data: executionsData } = useQuery({
    queryKey: ['workflow-executions', id, environment],
    queryFn: async () => {
      // We need the environment ID, not type - for now use a workaround
      const response = await apiClient.getExecutions(undefined, id);
      return response.data;
    },
    enabled: !!id && !!workflow,
    staleTime: 2 * 60 * 1000, // Cache for 2 minutes
  });

  // Perform analysis
  const analysis: WorkflowAnalysis | null = useMemo(() => {
    if (!workflow) return null;
    // Cast to workflow-analysis Workflow type (compatible structure)
    return analyzeWorkflow(workflow as Parameters<typeof analyzeWorkflow>[0]);
  }, [workflow]);

  // Calculate execution metrics
  const executionMetrics: ExecutionMetricsSummary | null = useMemo(() => {
    if (!executionsData) return null;
    return calculateExecutionMetrics(executionsData as Execution[]);
  }, [executionsData]);

  // Activate/Deactivate mutation
  const toggleActiveMutation = useMutation({
    mutationFn: async () => {
      if (workflow?.active) {
        return apiClient.deactivateWorkflow(id!, environment);
      } else {
        return apiClient.activateWorkflow(id!, environment);
      }
    },
    onSuccess: () => {
      toast.success(workflow?.active ? 'Workflow disabled' : 'Workflow enabled');
      queryClient.invalidateQueries({ queryKey: ['workflow', id, environment] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to toggle workflow state');
    },
  });

  // Get N8N URL for opening workflows
  const getN8nUrl = () => {
    const devUrl = localStorage.getItem('dev_n8n_url') || 'http://localhost:5678';
    return devUrl;
  };

  const openInN8N = () => {
    if (!workflow) return;
    const n8nUrl = getN8nUrl();
    window.open(`${n8nUrl}/workflow/${workflow.id}`, '_blank');
  };

  const handleDisable = () => {
    toggleActiveMutation.mutate();
  };

  const handleClone = () => {
    toast.info('Clone feature coming soon');
    // Future: navigate(`/workflows/new?clone=${id}&environment=${environment}`);
  };

  const handleViewDiff = () => {
    setActiveTab('drift');
  };

  const handlePromote = () => {
    toast.info('Promotion feature coming soon');
    // Future: Open promotion dialog
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent"></div>
          <p className="mt-4 text-muted-foreground">Loading workflow...</p>
        </div>
      </div>
    );
  }

  if (error || !workflow || !analysis) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link to="/workflows">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Workflows
            </Button>
          </Link>
        </div>
        <Card>
          <CardContent className="py-8">
            <div className="text-center text-muted-foreground">
              {error ? 'Failed to load workflow' : 'Workflow not found'}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const triggerNodes: WorkflowNode[] = workflow.nodes?.filter((node: WorkflowNode) =>
    node.type.toLowerCase().includes('trigger') ||
    node.type.toLowerCase().includes('webhook')
  ) || [];

  return (
    <div className="space-y-6">
      {/* Hero Section - 10-Second Insights */}
      <WorkflowHeroSection
        workflow={workflow}
        analysis={analysis}
        executionMetrics={executionMetrics}
        driftStatus={driftData || null}
        environment={environment}
        isLoadingDrift={isLoadingDrift}
        onOpenInN8N={openInN8N}
        onDisable={handleDisable}
        onClone={handleClone}
        onViewDiff={handleViewDiff}
        onPromote={handlePromote}
      />

      {/* Quick Stats - Keep existing cards but simplified */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Status</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {workflow.active ? (
              <Badge variant="success" className="flex items-center gap-1 w-fit">
                <PlayCircle className="h-3 w-3" />
                Active
              </Badge>
            ) : (
              <Badge variant="outline" className="flex items-center gap-1 w-fit">
                <PauseCircle className="h-3 w-3" />
                Inactive
              </Badge>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Complexity</CardTitle>
            <Network className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analysis.graph.complexityScore}</div>
            <p className="text-xs text-muted-foreground capitalize">
              {analysis.graph.complexityLevel}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Nodes</CardTitle>
            <Box className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analysis.graph.nodeCount}</div>
            <p className="text-xs text-muted-foreground">
              {analysis.graph.edgeCount} connections
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Dependencies</CardTitle>
            <GitBranch className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analysis.dependencies.length}</div>
            <p className="text-xs text-muted-foreground">
              external systems
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Health</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {analysis.security.level === 'excellent' || analysis.security.level === 'good' ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : analysis.security.level === 'warning' ? (
                <AlertCircle className="h-5 w-5 text-yellow-500" />
              ) : (
                <XCircle className="h-5 w-5 text-red-500" />
              )}
              <span className="text-sm capitalize">{analysis.security.level}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="flex flex-wrap h-auto gap-1">
          <TabsTrigger value="overview" className="flex items-center gap-1">
            <FileText className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="structure" className="flex items-center gap-1">
            <Network className="h-4 w-4" />
            Structure
          </TabsTrigger>
          <TabsTrigger value="reliability" className="flex items-center gap-1">
            <AlertTriangle className="h-4 w-4" />
            Reliability
          </TabsTrigger>
          <TabsTrigger value="performance" className="flex items-center gap-1">
            <Zap className="h-4 w-4" />
            Performance
          </TabsTrigger>
          <TabsTrigger value="cost" className="flex items-center gap-1">
            <DollarSign className="h-4 w-4" />
            Cost
          </TabsTrigger>
          <TabsTrigger value="security" className="flex items-center gap-1">
            <Lock className="h-4 w-4" />
            Security
          </TabsTrigger>
          <TabsTrigger value="maintainability" className="flex items-center gap-1">
            <Wrench className="h-4 w-4" />
            Maintainability
          </TabsTrigger>
          <TabsTrigger value="governance" className="flex items-center gap-1">
            <Scale className="h-4 w-4" />
            Governance
          </TabsTrigger>
          <TabsTrigger value="drift" className="flex items-center gap-1">
            <GitCompare className="h-4 w-4" />
            Drift
          </TabsTrigger>
          <TabsTrigger value="optimize" className="flex items-center gap-1">
            <Lightbulb className="h-4 w-4" />
            Optimize
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Summary</CardTitle>
                <CardDescription>Plain-English workflow purpose</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Purpose</label>
                  <p className="text-sm mt-1">{analysis.summary.purpose}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Execution Summary</label>
                  <p className="text-sm mt-1">{analysis.summary.executionSummary}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Trigger Types</label>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {analysis.summary.triggerTypes.map((type, i) => (
                      <Badge key={i} variant="secondary">{type}</Badge>
                    ))}
                  </div>
                </div>
                {analysis.summary.externalSystems.length > 0 && (
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">External Systems</label>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {analysis.summary.externalSystems.map((sys, i) => (
                        <Badge key={i} variant="outline">{sys}</Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Basic Info */}
            <Card>
              <CardHeader>
                <CardTitle>Basic Information</CardTitle>
                <CardDescription>Workflow metadata</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-muted-foreground">Workflow ID</label>
                  <p className="font-mono text-sm">{workflow.id}</p>
                </div>
                {workflow.description && (
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Description</label>
                    <p className="text-sm">{workflow.description}</p>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                      <Calendar className="h-3 w-3" /> Created
                    </label>
                    <p className="text-sm">{new Date(workflow.createdAt).toLocaleDateString()}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3 w-3" /> Updated
                    </label>
                    <p className="text-sm">{new Date(workflow.updatedAt).toLocaleDateString()}</p>
                  </div>
                </div>
                {workflow.tags && workflow.tags.length > 0 && (
                  <div>
                    <label className="text-sm font-medium text-muted-foreground">Tags</label>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {workflow.tags.map((tag) => (
                        <Badge key={tag} variant="secondary" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* External Dependencies */}
          <Card>
            <CardHeader>
              <CardTitle>External Dependencies</CardTitle>
              <CardDescription>APIs, webhooks, subworkflows, and other external systems</CardDescription>
            </CardHeader>
            <CardContent>
              {analysis.dependencies.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Node Count</TableHead>
                      <TableHead>Nodes</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {analysis.dependencies.map((dep, i) => (
                      <TableRow key={i}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <DependencyIcon type={dep.type} />
                            <Badge variant="outline" className="capitalize">{dep.type}</Badge>
                          </div>
                        </TableCell>
                        <TableCell className="font-medium">{dep.name}</TableCell>
                        <TableCell className="text-muted-foreground">{dep.nodeCount}</TableCell>
                        <TableCell className="font-mono text-xs max-w-[200px] truncate">
                          {dep.nodes.join(', ') || '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No external dependencies detected
                </div>
              )}
            </CardContent>
          </Card>

          {/* Nodes Used */}
          <Card>
            <CardHeader>
              <CardTitle>Nodes Used ({analysis.nodes.length})</CardTitle>
              <CardDescription>All nodes in this workflow with their details</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Credentials</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {analysis.nodes.map((node) => (
                    <TableRow key={node.id}>
                      <TableCell className="font-medium">
                        {node.isTrigger && (
                          <Badge variant="success" className="mr-2 text-xs">Trigger</Badge>
                        )}
                        {node.name}
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="text-xs font-mono">
                          {node.type}
                        </Badge>
                      </TableCell>
                      <TableCell className="capitalize text-muted-foreground">
                        {node.category}
                      </TableCell>
                      <TableCell>
                        {node.isCredentialed ? (
                          <div className="flex items-center gap-1">
                            <Lock className="h-3 w-3 text-yellow-500" />
                            <span className="text-xs">Yes</span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground text-xs">None</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Triggers */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="h-4 w-4" />
                Triggers ({triggerNodes.length})
              </CardTitle>
              <CardDescription>How this workflow gets executed</CardDescription>
            </CardHeader>
            <CardContent>
              {triggerNodes.length > 0 ? (
                <div className="space-y-2">
                  {triggerNodes.map((node) => (
                    <div key={node.id} className="flex items-center gap-2 p-2 rounded-md bg-muted">
                      <Badge variant="outline" className="text-xs">
                        {node.type.replace('n8n-nodes-base.', '')}
                      </Badge>
                      <span className="text-sm">{node.name}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No trigger nodes found. This workflow needs to be executed manually.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Structure / Graph Assessment Tab */}
        <TabsContent value="structure" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Structural / Graph Assessment</span>
                <ScoreBadge score={analysis.graph.complexityScore} level={analysis.graph.complexityLevel} />
              </CardTitle>
              <CardDescription>Workflow graph structure and complexity analysis</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.graph.nodeCount}</div>
                  <div className="text-sm text-muted-foreground">Total Nodes</div>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.graph.edgeCount}</div>
                  <div className="text-sm text-muted-foreground">Connections</div>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.graph.maxDepth}</div>
                  <div className="text-sm text-muted-foreground">Max Depth</div>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.graph.maxBranching}</div>
                  <div className="text-sm text-muted-foreground">Max Branching</div>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <h4 className="font-medium">Flow Patterns</h4>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      {analysis.graph.isLinear ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      ) : (
                        <Info className="h-4 w-4 text-blue-500" />
                      )}
                      <span className="text-sm">Linear Flow: {analysis.graph.isLinear ? 'Yes' : 'No'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {analysis.graph.hasFanOut ? (
                        <Info className="h-4 w-4 text-blue-500" />
                      ) : (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      )}
                      <span className="text-sm">Fan-out Pattern: {analysis.graph.hasFanOut ? 'Yes' : 'No'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {analysis.graph.hasFanIn ? (
                        <Info className="h-4 w-4 text-blue-500" />
                      ) : (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      )}
                      <span className="text-sm">Fan-in Pattern: {analysis.graph.hasFanIn ? 'Yes' : 'No'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {analysis.graph.hasCycles ? (
                        <AlertCircle className="h-4 w-4 text-yellow-500" />
                      ) : (
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                      )}
                      <span className="text-sm">Cycles Detected: {analysis.graph.hasCycles ? 'Yes' : 'No'}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="font-medium">Entry/Exit Points</h4>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <PlayCircle className="h-4 w-4 text-green-500" />
                      <span className="text-sm">Trigger Nodes: {analysis.graph.triggerCount}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Box className="h-4 w-4 text-blue-500" />
                      <span className="text-sm">Sink Nodes: {analysis.graph.sinkCount}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-lg border">
                <h4 className="font-medium mb-2">Complexity Analysis</h4>
                <p className="text-sm text-muted-foreground">
                  This workflow has a complexity score of <strong>{analysis.graph.complexityScore}/100</strong> ({analysis.graph.complexityLevel}).
                  {analysis.graph.complexityLevel === 'simple' && ' The workflow is straightforward with minimal branching.'}
                  {analysis.graph.complexityLevel === 'moderate' && ' The workflow has some branching but is manageable.'}
                  {analysis.graph.complexityLevel === 'complex' && ' Consider breaking this workflow into smaller sub-workflows.'}
                  {analysis.graph.complexityLevel === 'very-complex' && ' This workflow should be refactored into smaller, more manageable pieces.'}
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Reliability Tab */}
        <TabsContent value="reliability" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Reliability & Failure Assessment</span>
                <ScoreBadge score={analysis.reliability.score} level={analysis.reliability.level} />
              </CardTitle>
              <CardDescription>Error handling, retry patterns, and failure risk analysis</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.reliability.continueOnFailCount}</div>
                  <div className="text-sm text-muted-foreground">Continue-on-Fail Nodes</div>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.reliability.errorHandlingNodes}</div>
                  <div className="text-sm text-muted-foreground">Error Handling Nodes</div>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.reliability.retryNodes}</div>
                  <div className="text-sm text-muted-foreground">Retry-Enabled Nodes</div>
                </div>
              </div>

              {analysis.reliability.missingErrorHandling.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-yellow-600">Missing Error Handling</h4>
                  <IssueList issues={analysis.reliability.missingErrorHandling} type="warning" />
                </div>
              )}

              {analysis.reliability.failureHotspots.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium">Failure Hotspots</h4>
                  <p className="text-sm text-muted-foreground mb-2">
                    These nodes are most likely to fail and should have proper error handling:
                  </p>
                  <IssueList issues={analysis.reliability.failureHotspots} type="info" />
                </div>
              )}

              <RecommendationList recommendations={analysis.reliability.recommendations} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Performance Tab */}
        <TabsContent value="performance" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Performance & Efficiency Assessment</span>
                <ScoreBadge score={analysis.performance.score} level={analysis.performance.level} />
              </CardTitle>
              <CardDescription>Execution duration, parallelism, and bottleneck analysis</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="p-4 rounded-lg bg-muted">
                  <div className="flex items-center gap-2">
                    {analysis.performance.hasParallelism ? (
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-yellow-500" />
                    )}
                    <span className="font-medium">Parallelism</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {analysis.performance.hasParallelism
                      ? 'Workflow utilizes parallel execution paths'
                      : 'Workflow runs sequentially - consider parallelizing'}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold capitalize">{analysis.performance.estimatedComplexity}</div>
                  <div className="text-sm text-muted-foreground">Estimated Execution Load</div>
                </div>
              </div>

              {analysis.performance.sequentialBottlenecks.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-yellow-600">Sequential Bottlenecks</h4>
                  <IssueList issues={analysis.performance.sequentialBottlenecks} type="warning" />
                </div>
              )}

              {analysis.performance.redundantCalls.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-red-600">Redundant Calls Detected</h4>
                  <IssueList issues={analysis.performance.redundantCalls} type="error" />
                </div>
              )}

              {analysis.performance.largePayloadRisks.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium">Large Payload Risks</h4>
                  <IssueList issues={analysis.performance.largePayloadRisks} type="info" />
                </div>
              )}

              <RecommendationList recommendations={analysis.performance.recommendations} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Cost Tab */}
        <TabsContent value="cost" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Cost & Usage Assessment</span>
                <Badge
                  variant={
                    analysis.cost.level === 'low' ? 'success' :
                    analysis.cost.level === 'medium' ? 'default' :
                    analysis.cost.level === 'high' ? 'warning' : 'destructive'
                  }
                  className="text-sm font-medium"
                >
                  {analysis.cost.level.toUpperCase()} COST
                </Badge>
              </CardTitle>
              <CardDescription>API usage, LLM costs, and execution frequency analysis</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="p-4 rounded-lg bg-muted">
                <div className="text-sm font-medium text-muted-foreground">Trigger Frequency</div>
                <div className="text-lg font-medium mt-1">{analysis.cost.triggerFrequency}</div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {analysis.cost.apiHeavyNodes.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="font-medium flex items-center gap-2">
                      <Globe className="h-4 w-4" />
                      API-Heavy Nodes ({analysis.cost.apiHeavyNodes.length})
                    </h4>
                    <div className="flex flex-wrap gap-1">
                      {analysis.cost.apiHeavyNodes.map((node, i) => (
                        <Badge key={i} variant="outline">{node}</Badge>
                      ))}
                    </div>
                  </div>
                )}

                {analysis.cost.llmNodes.length > 0 && (
                  <div className="space-y-2">
                    <h4 className="font-medium flex items-center gap-2 text-yellow-600">
                      <DollarSign className="h-4 w-4" />
                      LLM/AI Nodes ({analysis.cost.llmNodes.length})
                    </h4>
                    <div className="flex flex-wrap gap-1">
                      {analysis.cost.llmNodes.map((node, i) => (
                        <Badge key={i} variant="warning">{node}</Badge>
                      ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      LLM nodes can be expensive - monitor usage closely
                    </p>
                  </div>
                )}
              </div>

              {analysis.cost.costAmplifiers.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-yellow-600">Cost Amplifiers</h4>
                  <IssueList issues={analysis.cost.costAmplifiers} type="warning" />
                </div>
              )}

              {analysis.cost.throttlingCandidates.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium">Throttling Candidates</h4>
                  <IssueList issues={analysis.cost.throttlingCandidates} type="info" />
                </div>
              )}

              <RecommendationList recommendations={analysis.cost.recommendations} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Security & Secrets Assessment</span>
                <ScoreBadge score={analysis.security.score} level={analysis.security.level} />
              </CardTitle>
              <CardDescription>Credential usage, hardcoded secrets, and security risks</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.security.credentialCount}</div>
                  <div className="text-sm text-muted-foreground">Total Credentials Used</div>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.security.credentialTypes.length}</div>
                  <div className="text-sm text-muted-foreground">Unique Credential Types</div>
                </div>
              </div>

              {analysis.security.credentialTypes.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium">Credential Types</h4>
                  <div className="flex flex-wrap gap-1">
                    {analysis.security.credentialTypes.map((type, i) => (
                      <Badge key={i} variant="secondary" className="flex items-center gap-1">
                        <Lock className="h-3 w-3" />
                        {type}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {analysis.security.hardcodedSecretSignals.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-red-600">Hardcoded Secret Signals</h4>
                  <IssueList issues={analysis.security.hardcodedSecretSignals} type="error" />
                </div>
              )}

              {analysis.security.overPrivilegedRisks.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-yellow-600">Over-Privileged Risks</h4>
                  <IssueList issues={analysis.security.overPrivilegedRisks} type="warning" />
                </div>
              )}

              {analysis.security.secretReuseRisks.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium">Secret Reuse (Blast Radius)</h4>
                  <IssueList issues={analysis.security.secretReuseRisks} type="info" />
                </div>
              )}

              <RecommendationList recommendations={analysis.security.recommendations} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Maintainability Tab */}
        <TabsContent value="maintainability" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Maintainability Assessment</span>
                <ScoreBadge score={analysis.maintainability.score} level={analysis.maintainability.level} />
              </CardTitle>
              <CardDescription>Naming consistency, documentation, and readability analysis</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.maintainability.namingConsistency}%</div>
                  <div className="text-sm text-muted-foreground">Naming Consistency</div>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.maintainability.logicalGroupingScore}%</div>
                  <div className="text-sm text-muted-foreground">Logical Grouping</div>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.maintainability.readabilityScore}%</div>
                  <div className="text-sm text-muted-foreground">Readability Score</div>
                </div>
              </div>

              {analysis.maintainability.missingDescriptions.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-yellow-600">Missing Descriptions</h4>
                  <IssueList issues={analysis.maintainability.missingDescriptions} type="warning" />
                </div>
              )}

              {analysis.maintainability.missingAnnotations.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium">Nodes with Default/Generic Names</h4>
                  <div className="flex flex-wrap gap-1">
                    {analysis.maintainability.missingAnnotations.slice(0, 10).map((node, i) => (
                      <Badge key={i} variant="outline">{node}</Badge>
                    ))}
                    {analysis.maintainability.missingAnnotations.length > 10 && (
                      <Badge variant="secondary">+{analysis.maintainability.missingAnnotations.length - 10} more</Badge>
                    )}
                  </div>
                </div>
              )}

              {analysis.maintainability.nodeReuseOpportunities.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium">Node Reuse Opportunities</h4>
                  <IssueList issues={analysis.maintainability.nodeReuseOpportunities} type="info" />
                </div>
              )}

              <RecommendationList recommendations={analysis.maintainability.recommendations} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Governance Tab */}
        <TabsContent value="governance" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Governance & Compliance Assessment</span>
                <ScoreBadge score={analysis.governance.score} level={analysis.governance.level} />
              </CardTitle>
              <CardDescription>Auditability, environment portability, and compliance analysis</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.governance.auditability}%</div>
                  <div className="text-sm text-muted-foreground">Auditability</div>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.governance.environmentPortability}%</div>
                  <div className="text-sm text-muted-foreground">Environment Portability</div>
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="flex items-center gap-2">
                    {analysis.governance.promotionSafety ? (
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-500" />
                    )}
                    <span className="font-medium">
                      {analysis.governance.promotionSafety ? 'Prod Safe' : 'Not Prod Safe'}
                    </span>
                  </div>
                  <div className="text-sm text-muted-foreground">Promotion Safety</div>
                </div>
              </div>

              {analysis.governance.piiExposureRisks.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-red-600">PII Exposure Risks</h4>
                  <IssueList issues={analysis.governance.piiExposureRisks} type="error" />
                </div>
              )}

              {analysis.governance.retentionIssues.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-yellow-600">Retention Issues</h4>
                  <IssueList issues={analysis.governance.retentionIssues} type="warning" />
                </div>
              )}

              <RecommendationList recommendations={analysis.governance.recommendations} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Drift Tab - Now with Real API Data */}
        <TabsContent value="drift" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Drift & Consistency Assessment</CardTitle>
                  <CardDescription>Git vs runtime comparison and sync status</CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => queryClient.invalidateQueries({ queryKey: ['workflow-drift', id, environment] })}
                  disabled={isLoadingDrift}
                >
                  <RefreshCw className={`h-4 w-4 mr-2 ${isLoadingDrift ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {isLoadingDrift ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-center">
                    <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-solid border-primary border-r-transparent"></div>
                    <p className="mt-2 text-sm text-muted-foreground">Checking Git sync status...</p>
                  </div>
                </div>
              ) : !driftData?.gitConfigured ? (
                <div className="p-4 rounded-lg bg-muted">
                  <div className="flex items-center gap-2">
                    <Info className="h-5 w-5 text-blue-500" />
                    <span className="font-medium">Git Not Configured</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    {driftData?.message || 'Configure GitHub integration in the environment settings to enable drift detection.'}
                  </p>
                </div>
              ) : driftData?.notInGit ? (
                <div className="p-4 rounded-lg bg-muted">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-5 w-5 text-yellow-500" />
                    <span className="font-medium">Not Tracked in Git</span>
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    This workflow has not been synced to GitHub yet. Use "Backup to GitHub" to add it.
                  </p>
                </div>
              ) : (
                <>
                  {/* Sync Status */}
                  <div className="p-4 rounded-lg bg-muted">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {driftData?.hasDrift ? (
                          <AlertCircle className="h-5 w-5 text-yellow-500" />
                        ) : (
                          <CheckCircle2 className="h-5 w-5 text-green-500" />
                        )}
                        <span className="font-medium">
                          {driftData?.hasDrift ? 'Drift Detected' : 'In Sync with Git'}
                        </span>
                      </div>
                      {driftData?.lastCommitSha && (
                        <div className="text-sm text-muted-foreground">
                          Last commit: <code className="bg-muted-foreground/20 px-1 rounded">{driftData.lastCommitSha.substring(0, 7)}</code>
                          {driftData.lastCommitDate && (
                            <span className="ml-2">
                              {new Date(driftData.lastCommitDate).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Drift Summary */}
                  {driftData?.hasDrift && driftData.summary && (
                    <div className="grid gap-4 md:grid-cols-3">
                      <div className="p-4 rounded-lg border">
                        <div className="text-2xl font-bold text-green-600">+{driftData.summary.nodesAdded}</div>
                        <div className="text-sm text-muted-foreground">Nodes Added</div>
                      </div>
                      <div className="p-4 rounded-lg border">
                        <div className="text-2xl font-bold text-red-600">-{driftData.summary.nodesRemoved}</div>
                        <div className="text-sm text-muted-foreground">Nodes Removed</div>
                      </div>
                      <div className="p-4 rounded-lg border">
                        <div className="text-2xl font-bold text-yellow-600">{driftData.summary.nodesModified}</div>
                        <div className="text-sm text-muted-foreground">Nodes Modified</div>
                      </div>
                    </div>
                  )}

                  {/* Differences List */}
                  {driftData?.hasDrift && driftData.differences && driftData.differences.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium">Changes Detected</h4>
                      <div className="max-h-[300px] overflow-y-auto border rounded-lg">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Path</TableHead>
                              <TableHead>Type</TableHead>
                              <TableHead>Git Value</TableHead>
                              <TableHead>Runtime Value</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {driftData.differences.slice(0, 20).map((diff, i) => (
                              <TableRow key={i}>
                                <TableCell className="font-mono text-xs">{diff.path}</TableCell>
                                <TableCell>
                                  <Badge
                                    variant={
                                      diff.type === 'added' ? 'success' :
                                      diff.type === 'removed' ? 'destructive' : 'warning'
                                    }
                                  >
                                    {diff.type}
                                  </Badge>
                                </TableCell>
                                <TableCell className="text-xs max-w-[150px] truncate">
                                  {diff.gitValue !== null ? String(diff.gitValue) : '-'}
                                </TableCell>
                                <TableCell className="text-xs max-w-[150px] truncate">
                                  {diff.runtimeValue !== null ? String(diff.runtimeValue) : '-'}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                        {driftData.differences.length > 20 && (
                          <div className="p-2 text-center text-sm text-muted-foreground border-t">
                            +{driftData.differences.length - 20} more changes
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Connection Changed */}
                  {driftData?.summary?.connectionsChanged && (
                    <div className="p-3 rounded-lg border border-yellow-200 bg-yellow-50 dark:bg-yellow-950/20">
                      <div className="flex items-center gap-2">
                        <AlertCircle className="h-4 w-4 text-yellow-600" />
                        <span className="text-sm font-medium">Node connections have changed</span>
                      </div>
                    </div>
                  )}

                  {/* Settings Changed */}
                  {driftData?.summary?.settingsChanged && (
                    <div className="p-3 rounded-lg border border-yellow-200 bg-yellow-50 dark:bg-yellow-950/20">
                      <div className="flex items-center gap-2">
                        <AlertCircle className="h-4 w-4 text-yellow-600" />
                        <span className="text-sm font-medium">Workflow settings have changed</span>
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Static analysis (kept for additional context) */}
              {analysis.drift.environmentDivergence.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-yellow-600">Environment Divergence</h4>
                  <IssueList issues={analysis.drift.environmentDivergence} type="warning" />
                </div>
              )}

              {analysis.drift.duplicateSuspects.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium">Potential Duplicates</h4>
                  <IssueList issues={analysis.drift.duplicateSuspects} type="info" />
                </div>
              )}

              <RecommendationList recommendations={analysis.drift.recommendations} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Optimization Tab */}
        <TabsContent value="optimize" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Optimization Opportunities</CardTitle>
              <CardDescription>Ranked recommendations for improving this workflow</CardDescription>
            </CardHeader>
            <CardContent>
              {analysis.optimizations.length > 0 ? (
                <div className="space-y-4">
                  {analysis.optimizations.map((opt, i) => (
                    <div
                      key={i}
                      className={`p-4 rounded-lg border ${
                        opt.impact === 'high' ? 'border-red-200 bg-red-50 dark:bg-red-950/20' :
                        opt.impact === 'medium' ? 'border-yellow-200 bg-yellow-50 dark:bg-yellow-950/20' :
                        'border-gray-200 bg-gray-50 dark:bg-gray-800/20'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={
                              opt.impact === 'high' ? 'destructive' :
                              opt.impact === 'medium' ? 'warning' : 'secondary'
                            }
                          >
                            {opt.impact.toUpperCase()}
                          </Badge>
                          <h4 className="font-medium">{opt.title}</h4>
                        </div>
                        <Badge variant="outline" className="capitalize">{opt.category.replace('-', ' ')}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mt-2">{opt.description}</p>
                      <div className="flex gap-4 mt-3 text-xs">
                        <span className="text-muted-foreground">
                          <strong>Impact:</strong> {opt.impact}
                        </span>
                        <span className="text-muted-foreground">
                          <strong>Effort:</strong> {opt.effort}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-500" />
                  <p>No optimization opportunities detected. This workflow looks well-optimized!</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
