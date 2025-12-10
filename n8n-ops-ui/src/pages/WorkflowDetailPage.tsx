import { useParams, useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState, useCallback, useEffect } from 'react';
import { ArrowUpDown, Filter } from 'lucide-react';
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
import { analyzeWorkflow, formatNodeType, type WorkflowAnalysis, type NodeAnalysis } from '@/lib/workflow-analysis';
import { WorkflowHeroSection } from '@/components/workflow/WorkflowHeroSection';
import { WorkflowGraphTab } from '@/components/workflow/WorkflowGraphTab';
import { NodeDetailsPanel } from '@/components/workflow/NodeDetailsPanel';
import { toast } from 'sonner';
import {
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
  History,
  Layers,
  Share2,
  ExternalLink,
  Code,
  Copy,
  Check,
  Download,
  Maximize2,
  Minimize2,
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

// Governance explanation helpers
function getAuditabilityExplanation(score: number, nodes: NodeAnalysis[]): string | null {
  if (score >= 100) return null;
  if (score >= 90) return "All nodes have meaningful names for audit trail tracking.";
  const poorlyNamed = nodes.filter(n => !n.name || n.name.length <= 3).length;
  return `${poorlyNamed} node(s) have default or short names. Rename nodes to describe their purpose for better audit trails.`;
}

function getPortabilityExplanation(score: number): string | null {
  if (score >= 100) return null;
  if (score >= 80) return "Workflow uses environment variables for configuration.";
  return "No environment variables detected. Hardcoded values may cause issues when promoting between environments. Use $env references for URLs and environment-specific settings.";
}

function getProdSafeExplanation(isSafe: boolean, piiRisks: string[]): string | null {
  if (isSafe) return null;
  return `${piiRisks.length} node(s) may handle PII data (email, phone, SSN). Review data handling and ensure compliance before promoting to production.`;
}

// JSON Tree Node Component
function JsonTreeNode({
  keyName,
  value,
  depth = 0,
  defaultExpanded = true,
  isLast = true,
}: {
  keyName?: string;
  value: unknown;
  depth?: number;
  defaultExpanded?: boolean;
  isLast?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const indent = depth * 16;

  const isObject = value !== null && typeof value === 'object' && !Array.isArray(value);
  const isArray = Array.isArray(value);
  const isExpandable = isObject || isArray;

  const renderValue = () => {
    if (value === null) return <span className="json-null">null</span>;
    if (typeof value === 'boolean') return <span className="json-bool">{value.toString()}</span>;
    if (typeof value === 'number') return <span className="json-number">{value}</span>;
    if (typeof value === 'string') {
      // Truncate very long strings
      const displayStr = value.length > 100 ? value.slice(0, 100) + '...' : value;
      return <span className="json-string">"{displayStr}"</span>;
    }
    return null;
  };

  const comma = !isLast ? ',' : '';

  if (!isExpandable) {
    return (
      <div style={{ paddingLeft: indent }} className="leading-6">
        {keyName !== undefined && (
          <>
            <span className="json-key">"{keyName}"</span>
            <span className="text-foreground">: </span>
          </>
        )}
        {renderValue()}
        <span className="text-foreground">{comma}</span>
      </div>
    );
  }

  const entries = isArray ? value : Object.entries(value as Record<string, unknown>);
  const itemCount = isArray ? value.length : Object.keys(value as Record<string, unknown>).length;
  const openBracket = isArray ? '[' : '{';
  const closeBracket = isArray ? ']' : '}';

  return (
    <div>
      <div
        style={{ paddingLeft: indent }}
        className="leading-6 flex items-center cursor-pointer hover:bg-gray-200/50 dark:hover:bg-zinc-700/50 -mx-2 px-2 rounded"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="w-4 h-4 flex items-center justify-center mr-1 text-muted-foreground select-none text-xs font-bold">
          {expanded ? '−' : '+'}
        </span>
        {keyName !== undefined && (
          <>
            <span className="json-key">"{keyName}"</span>
            <span className="text-foreground">: </span>
          </>
        )}
        <span className="text-foreground">{openBracket}</span>
        {!expanded && (
          <>
            <span className="text-muted-foreground ml-1">
              {isArray ? `${itemCount} items` : `${itemCount} keys`}
            </span>
            <span className="text-foreground">{closeBracket}{comma}</span>
          </>
        )}
      </div>
      {expanded && (
        <>
          {isArray ? (
            (value as unknown[]).map((item, idx) => (
              <JsonTreeNode
                key={idx}
                value={item}
                depth={depth + 1}
                defaultExpanded={defaultExpanded}
                isLast={idx === (value as unknown[]).length - 1}
              />
            ))
          ) : (
            Object.entries(value as Record<string, unknown>).map(([k, v], idx, arr) => (
              <JsonTreeNode
                key={k}
                keyName={k}
                value={v}
                depth={depth + 1}
                defaultExpanded={defaultExpanded}
                isLast={idx === arr.length - 1}
              />
            ))
          )}
          <div style={{ paddingLeft: indent }} className="leading-6">
            <span className="w-4 h-4 inline-block mr-1"></span>
            <span className="text-foreground">{closeBracket}{comma}</span>
          </div>
        </>
      )}
    </div>
  );
}

// JSON Viewer Tab Component
function JsonViewerTab({ workflow }: { workflow: Workflow }) {
  const [copied, setCopied] = useState(false);
  const [allExpanded, setAllExpanded] = useState(true);
  const [viewMode, setViewMode] = useState<'tree' | 'raw'>('tree');
  const [treeKey, setTreeKey] = useState(0); // Force re-render for expand/collapse all
  const [isViewerExpanded, setIsViewerExpanded] = useState(false);

  // Prepare workflow JSON for export (n8n compatible format)
  const exportableJson = useMemo(() => {
    return {
      name: workflow.name,
      nodes: workflow.nodes,
      connections: workflow.connections,
      active: workflow.active,
      settings: workflow.settings || {},
      staticData: workflow.staticData || null,
      tags: workflow.tags?.map(tag => typeof tag === 'string' ? tag : tag?.name) || [],
      ...(workflow.pinData && { pinData: workflow.pinData }),
    };
  }, [workflow]);

  // Full JSON for copy/download
  const fullJsonString = useMemo(() => {
    return JSON.stringify(exportableJson, null, 2);
  }, [exportableJson]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(fullJsonString);
      setCopied(true);
      toast.success('JSON copied to clipboard');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Failed to copy to clipboard');
    }
  }, [fullJsonString]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([fullJsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${workflow.name.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('JSON file downloaded');
  }, [fullJsonString, workflow.name]);

  const toggleExpandAll = useCallback(() => {
    setAllExpanded(prev => !prev);
    setTreeKey(prev => prev + 1); // Force tree to re-render with new default
  }, []);

  // Syntax highlighting for raw JSON
  const highlightJson = useCallback((json: string) => {
    const escaped = json
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    const result: string[] = [];
    let i = 0;

    while (i < escaped.length) {
      if (escaped[i] === '"') {
        let end = i + 1;
        while (end < escaped.length && escaped[end] !== '"') {
          if (escaped[end] === '\\') end++;
          end++;
        }
        end++;

        const str = escaped.slice(i, end);
        let afterStr = end;
        while (afterStr < escaped.length && /\s/.test(escaped[afterStr])) afterStr++;

        if (escaped[afterStr] === ':') {
          result.push(`<span class="json-key">${str}</span>`);
        } else {
          result.push(`<span class="json-string">${str}</span>`);
        }
        i = end;
      }
      else if (escaped.slice(i, i + 4) === 'true') {
        result.push('<span class="json-bool">true</span>');
        i += 4;
      }
      else if (escaped.slice(i, i + 5) === 'false') {
        result.push('<span class="json-bool">false</span>');
        i += 5;
      }
      else if (escaped.slice(i, i + 4) === 'null') {
        result.push('<span class="json-null">null</span>');
        i += 4;
      }
      else if (/[-\d]/.test(escaped[i]) && (i === 0 || /[\s\[\{:,]/.test(escaped[i - 1]))) {
        let end = i;
        if (escaped[end] === '-') end++;
        while (end < escaped.length && /[\d.]/.test(escaped[end])) end++;
        if (escaped[end] === 'e' || escaped[end] === 'E') {
          end++;
          if (escaped[end] === '+' || escaped[end] === '-') end++;
          while (end < escaped.length && /\d/.test(escaped[end])) end++;
        }
        result.push(`<span class="json-number">${escaped.slice(i, end)}</span>`);
        i = end;
      }
      else {
        result.push(escaped[i]);
        i++;
      }
    }

    return result.join('');
  }, []);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Code className="h-5 w-5" />
              Workflow JSON
            </CardTitle>
            <CardDescription>
              View and export the workflow definition in n8n-compatible JSON format
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center border rounded-md">
              <Button
                variant={viewMode === 'tree' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('tree')}
                className="rounded-r-none"
              >
                Tree
              </Button>
              <Button
                variant={viewMode === 'raw' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('raw')}
                className="rounded-l-none"
              >
                Raw
              </Button>
            </div>
            {viewMode === 'tree' && (
              <Button
                variant="outline"
                size="sm"
                onClick={toggleExpandAll}
              >
                {allExpanded ? 'Collapse All' : 'Expand All'}
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="flex items-center gap-1"
            >
              {copied ? (
                <>
                  <Check className="h-4 w-4" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4" />
                  Copy
                </>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              className="flex items-center gap-1"
            >
              <Download className="h-4 w-4" />
              Download
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* JSON Stats */}
        <div className="mb-4 flex flex-wrap gap-4 text-sm text-muted-foreground">
          <span>
            <strong>{workflow.nodes?.length || 0}</strong> nodes
          </span>
          <span>
            <strong>{Object.keys(workflow.connections || {}).length}</strong> connection groups
          </span>
          <span>
            <strong>{(fullJsonString.length / 1024).toFixed(1)}</strong> KB
          </span>
          <span>
            <strong>{fullJsonString.split('\n').length}</strong> lines
          </span>
        </div>

        {/* JSON Viewer */}
        <div className="relative px-5">
          <div className="absolute top-2 right-7 z-10">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsViewerExpanded(!isViewerExpanded)}
              title={isViewerExpanded ? 'Collapse viewer' : 'Expand viewer'}
              className="bg-white/80 dark:bg-zinc-900/80 backdrop-blur-sm"
            >
              {isViewerExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </Button>
          </div>
          {viewMode === 'tree' ? (
            <div
              className="p-4 rounded-lg bg-gray-100 dark:bg-zinc-800 overflow-auto text-sm font-mono border border-gray-200 dark:border-zinc-700 transition-all duration-300"
              style={{ height: isViewerExpanded ? 'calc(100vh - 300px)' : '500px', minHeight: isViewerExpanded ? '500px' : undefined }}
            >
              <JsonTreeNode
                key={treeKey}
                value={exportableJson}
                defaultExpanded={allExpanded}
              />
            </div>
          ) : (
            <pre
              className="p-4 rounded-lg bg-gray-100 dark:bg-zinc-800 overflow-auto text-sm font-mono leading-relaxed border border-gray-200 dark:border-zinc-700 transition-all duration-300"
              style={{ height: isViewerExpanded ? 'calc(100vh - 300px)' : '500px', minHeight: isViewerExpanded ? '500px' : undefined, tabSize: 2 }}
            >
              <code
                dangerouslySetInnerHTML={{
                  __html: highlightJson(fullJsonString),
                }}
              />
            </pre>
          )}
        </div>

      </CardContent>
    </Card>
  );
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
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(null);
  const [recommendationFilter, setRecommendationFilter] = useState<string>('all');
  const [recommendationSort, setRecommendationSort] = useState<{ field: string; direction: 'asc' | 'desc' }>({ field: 'impact', direction: 'desc' });

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

  // Update document title
  useEffect(() => {
    if (workflow?.name) {
      document.title = `Workflow: ${workflow.name}`;
    }
    return () => {
      document.title = 'n8n Ops';
    };
  }, [workflow?.name]);

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

  // Perform analysis - use stored analysis if available, otherwise compute client-side
  const analysis: WorkflowAnalysis | null = useMemo(() => {
    if (!workflow) return null;
    // Use stored analysis from database if available
    if (workflow.analysis) {
      return workflow.analysis as WorkflowAnalysis;
    }
    // Fallback to client-side computation for backward compatibility
    return analyzeWorkflow(workflow as Parameters<typeof analyzeWorkflow>[0]);
  }, [workflow]);

  // Calculate execution metrics
  const executionMetrics: ExecutionMetricsSummary | null = useMemo(() => {
    if (!executionsData) return null;
    return calculateExecutionMetrics(executionsData as Execution[]);
  }, [executionsData]);

  // Calculate node metrics with I/O samples
  interface NodeMetrics {
    nodeId: string;
    avgDuration: number;
    failureRate: number;
    lastStatus: 'success' | 'error' | 'running';
    executionCount: number;
    lastError?: string;
    sampleInput?: any;
    sampleOutput?: any;
  }

  const nodeMetrics = useMemo(() => {
    if (!workflow || !executionsData || !Array.isArray(executionsData)) {
      return new Map<string, NodeMetrics>();
    }
    
    const metrics = new Map<string, NodeMetrics>();
    
    workflow.nodes.forEach(node => {
      const nodeExecutions = executionsData.filter((exec: Execution) => {
        const execData = exec.data?.data?.resultData?.runData;
        return execData && execData[node.name];
      });
      
      if (nodeExecutions.length === 0) {
        metrics.set(node.id, {
          nodeId: node.id,
          avgDuration: 0,
          failureRate: 0,
          lastStatus: 'success',
          executionCount: 0,
        });
        return;
      }
      
      const durations: number[] = [];
      let errorCount = 0;
      let lastStatus: 'success' | 'error' | 'running' = 'success';
      let lastError: string | undefined;
      let sampleInput: any;
      let sampleOutput: any;
      
      // Process most recent execution first
      const sortedExecutions = [...nodeExecutions].sort((a: Execution, b: Execution) => 
        new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime()
      );
      
      sortedExecutions.forEach((exec: Execution) => {
        const nodeData = exec.data?.data?.resultData?.runData?.[node.name];
        if (nodeData && Array.isArray(nodeData)) {
          const latestRun = nodeData[nodeData.length - 1];
          
          if (latestRun.executionTime) durations.push(latestRun.executionTime);
          if (latestRun.error) {
            errorCount++;
            if (!lastError) {
              lastError = latestRun.error.message || JSON.stringify(latestRun.error);
            }
          }
          
          // Extract I/O samples from first successful execution
          if (!sampleInput && latestRun.data?.main?.[0]) {
            sampleInput = latestRun.data.main[0];
          }
          if (!sampleOutput && latestRun.data?.main?.[0] && !latestRun.error) {
            sampleOutput = latestRun.data.main[0];
          }
        }
        
        if (exec.status === 'error') {
          lastStatus = 'error';
        } else if (exec.status === 'running') {
          lastStatus = 'running';
        }
      });
      
      const avgDuration = durations.length > 0
        ? durations.reduce((a, b) => a + b, 0) / durations.length
        : 0;
      
      const failureRate = nodeExecutions.length > 0
        ? errorCount / nodeExecutions.length
        : 0;
      
      metrics.set(node.id, {
        nodeId: node.id,
        avgDuration,
        failureRate,
        lastStatus,
        executionCount: nodeExecutions.length,
        lastError,
        sampleInput,
        sampleOutput,
      });
    });
    
    return metrics;
  }, [workflow, executionsData]);

  // Collect all recommendations from all advisory tabs
  interface UnifiedRecommendation {
    id: string;
    text: string;
    description: string;
    category: string;
    impact?: 'low' | 'medium' | 'high';
    effort?: 'low' | 'medium' | 'high';
    source: 'reliability' | 'performance' | 'cost' | 'security' | 'maintainability' | 'governance' | 'drift' | 'optimization';
  }

  // Helper to check if recommendation is actionable
  const isActionable = (text: string): boolean => {
    if (!text || text.trim().length < 10) return false;
    
    const lowerText = text.toLowerCase();
    
    // Filter out informational messages
    const nonActionablePatterns = [
      'no issues',
      'no problems',
      'no recommendations',
      'looks good',
      'well configured',
      'properly configured',
      'no action needed',
      'no changes required',
      'analysis failed',
      'could not generate',
    ];
    
    if (nonActionablePatterns.some(pattern => lowerText.includes(pattern))) {
      return false;
    }
    
    // Check for actionable verbs
    const actionableVerbs = [
      'add', 'enable', 'configure', 'set', 'update', 'remove', 'delete',
      'implement', 'create', 'install', 'fix', 'resolve', 'improve',
      'optimize', 'reduce', 'increase', 'decrease', 'change', 'modify',
      'review', 'audit', 'validate', 'test', 'monitor', 'document',
      'refactor', 'restructure', 'consolidate', 'separate', 'split',
    ];
    
    return actionableVerbs.some(verb => lowerText.includes(verb));
  };

  // Helper to generate description from recommendation text
  const generateDescription = (text: string, category: string, source: string): string => {
    const lowerText = text.toLowerCase();
    
    // Extract key information and create clear description
    if (lowerText.includes('error handling') || lowerText.includes('error handler')) {
      return 'Add error handling nodes to catch and manage failures gracefully, preventing workflow crashes and improving reliability.';
    }
    
    if (lowerText.includes('retry') || lowerText.includes('retry on fail')) {
      return 'Enable retry logic on nodes that may fail due to transient issues (network, API rate limits). This improves workflow success rates.';
    }
    
    if (lowerText.includes('credential') || lowerText.includes('authentication')) {
      return 'Configure proper credentials for nodes that require authentication. Missing or invalid credentials will cause workflow failures.';
    }
    
    if (lowerText.includes('parallel') || lowerText.includes('concurrent')) {
      return 'Restructure workflow to execute independent operations in parallel, reducing total execution time and improving performance.';
    }
    
    if (lowerText.includes('cost') || lowerText.includes('expensive') || lowerText.includes('api call')) {
      return 'Optimize API usage and reduce unnecessary calls to lower operational costs. Consider caching, batching, or reducing frequency.';
    }
    
    if (lowerText.includes('security') || lowerText.includes('secret') || lowerText.includes('credential')) {
      return 'Review and secure sensitive data handling. Ensure credentials are properly managed and secrets are not hardcoded.';
    }
    
    if (lowerText.includes('name') || lowerText.includes('naming')) {
      return 'Use descriptive node names that clearly indicate their purpose. This improves workflow readability and maintainability.';
    }
    
    if (lowerText.includes('environment') || lowerText.includes('env variable')) {
      return 'Use environment variables instead of hardcoded values for configuration. This enables safe promotion between environments.';
    }
    
    if (lowerText.includes('drift') || lowerText.includes('git') || lowerText.includes('version')) {
      return 'Sync workflow changes with version control to prevent configuration drift and maintain consistency across environments.';
    }
    
    if (lowerText.includes('complex') || lowerText.includes('simplify')) {
      return 'Break down complex workflows into smaller, more manageable components. This improves maintainability and reduces errors.';
    }
    
    // For optimizations, use the title as description context
    if (source === 'optimization') {
      return `Optimization opportunity: ${text}`;
    }
    
    // Default: expand on the recommendation
    return `Action required: ${text}. This improvement will enhance ${category} and overall workflow quality.`;
  };

  const allRecommendations = useMemo(() => {
    if (!analysis) return [];
    
    const recommendations: UnifiedRecommendation[] = [];
    let idCounter = 0;

    // Add recommendations from each category
    const categories = [
      { source: 'reliability' as const, items: analysis.reliability.recommendations },
      { source: 'performance' as const, items: analysis.performance.recommendations },
      { source: 'cost' as const, items: analysis.cost.recommendations },
      { source: 'security' as const, items: analysis.security.recommendations },
      { source: 'maintainability' as const, items: analysis.maintainability.recommendations },
      { source: 'governance' as const, items: analysis.governance.recommendations },
      { source: 'drift' as const, items: analysis.drift.recommendations },
    ];

    categories.forEach(({ source, items }) => {
      items.forEach((text) => {
        // Only include actionable recommendations
        if (isActionable(text)) {
          recommendations.push({
            id: `rec-${idCounter++}`,
            text,
            description: generateDescription(text, source, source),
            category: source,
            source,
          });
        }
      });
    });

    // Add optimizations (they are always actionable)
    analysis.optimizations.forEach((opt) => {
      recommendations.push({
        id: `opt-${idCounter++}`,
        text: opt.description,
        description: generateDescription(opt.description, opt.category, 'optimization'),
        category: opt.category,
        impact: opt.impact,
        effort: opt.effort,
        source: 'optimization',
      });
    });

    return recommendations;
  }, [analysis]);

  // Filter and sort recommendations
  const filteredAndSortedRecommendations = useMemo(() => {
    let filtered = allRecommendations;

    // Apply category filter
    if (recommendationFilter !== 'all') {
      filtered = filtered.filter(rec => rec.category === recommendationFilter || rec.source === recommendationFilter);
    }

    // Apply sorting
    const sorted = [...filtered].sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (recommendationSort.field) {
        case 'category':
          aValue = a.category;
          bValue = b.category;
          break;
        case 'source':
          aValue = a.source;
          bValue = b.source;
          break;
        case 'impact':
          const impactOrder = { high: 3, medium: 2, low: 1, undefined: 0 };
          aValue = impactOrder[a.impact || 'undefined'];
          bValue = impactOrder[b.impact || 'undefined'];
          break;
        case 'effort':
          const effortOrder = { low: 1, medium: 2, high: 3, undefined: 0 };
          aValue = effortOrder[a.effort || 'undefined'];
          bValue = effortOrder[b.effort || 'undefined'];
          break;
        default:
          aValue = a.text;
          bValue = b.text;
      }

      if (aValue < bValue) return recommendationSort.direction === 'asc' ? -1 : 1;
      if (aValue > bValue) return recommendationSort.direction === 'asc' ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [allRecommendations, recommendationFilter, recommendationSort]);

  const handleSort = useCallback((field: string) => {
    setRecommendationSort(prev => ({
      field,
      direction: prev.field === field && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  }, []);

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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Workflow Details</h1>
            <p className="text-muted-foreground">
              View and manage workflow details
            </p>
          </div>
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Workflow</h1>
        </div>
      </div>

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
          <TabsTrigger value="recommendations" className="flex items-center gap-1">
            <Lightbulb className="h-4 w-4" />
            Recommendations
          </TabsTrigger>
          <TabsTrigger value="graph" className="flex items-center gap-1">
            <Share2 className="h-4 w-4" />
            Graph
          </TabsTrigger>
          <TabsTrigger value="nodes" className="flex items-center gap-1">
            <Layers className="h-4 w-4" />
            Nodes
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
          <TabsTrigger value="versions" className="flex items-center gap-1">
            <History className="h-4 w-4" />
            Versions
          </TabsTrigger>
          <TabsTrigger value="optimize" className="flex items-center gap-1">
            <Lightbulb className="h-4 w-4" />
            Optimize
          </TabsTrigger>
          <TabsTrigger value="json" className="flex items-center gap-1">
            <Code className="h-4 w-4" />
            JSON
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Summary */}
            <Card>
              <CardHeader>
                <CardTitle>Summary</CardTitle>
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
                      {workflow.tags.map((tag: any, index: number) => {
                        const tagName = typeof tag === 'string' ? tag : tag?.name || '';
                        const tagKey = typeof tag === 'string' ? tag : tag?.id || index;
                        return (
                          <Badge key={tagKey} variant="secondary" className="text-xs">
                            {tagName}
                          </Badge>
                        );
                      })}
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
        </TabsContent>

        {/* Recommendations Tab */}
        <TabsContent value="recommendations" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5" />
                Actionable Recommendations ({filteredAndSortedRecommendations.length})
              </CardTitle>
              <CardDescription>
                Actionable improvements from all advisory tabs - filtered to show only items requiring action
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Filters */}
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Filter by Category:</span>
                </div>
                <select
                  value={recommendationFilter}
                  onChange={(e) => setRecommendationFilter(e.target.value)}
                  className="px-3 py-1.5 text-sm border rounded-md bg-background"
                >
                  <option value="all">All Categories</option>
                  <option value="reliability">Reliability</option>
                  <option value="performance">Performance</option>
                  <option value="cost">Cost</option>
                  <option value="security">Security</option>
                  <option value="maintainability">Maintainability</option>
                  <option value="governance">Governance</option>
                  <option value="drift">Drift</option>
                  <option value="optimization">Optimization</option>
                </select>
              </div>

              {/* Recommendations Table */}
              {filteredAndSortedRecommendations.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[30%]">
                        <button
                          onClick={() => handleSort('text')}
                          className="flex items-center gap-1 hover:text-foreground"
                        >
                          Recommendation
                          <ArrowUpDown className="h-3 w-3" />
                        </button>
                      </TableHead>
                      <TableHead className="w-[40%]">
                        Description
                      </TableHead>
                      <TableHead>
                        <button
                          onClick={() => handleSort('category')}
                          className="flex items-center gap-1 hover:text-foreground"
                        >
                          Category
                          <ArrowUpDown className="h-3 w-3" />
                        </button>
                      </TableHead>
                      <TableHead>
                        <button
                          onClick={() => handleSort('impact')}
                          className="flex items-center gap-1 hover:text-foreground"
                        >
                          Impact
                          <ArrowUpDown className="h-3 w-3" />
                        </button>
                      </TableHead>
                      <TableHead>
                        <button
                          onClick={() => handleSort('effort')}
                          className="flex items-center gap-1 hover:text-foreground"
                        >
                          Effort
                          <ArrowUpDown className="h-3 w-3" />
                        </button>
                      </TableHead>
                      <TableHead className="w-[100px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredAndSortedRecommendations.map((rec) => {
                      // Map source to tab name
                      const tabMap: Record<string, string> = {
                        'reliability': 'reliability',
                        'performance': 'performance',
                        'cost': 'cost',
                        'security': 'security',
                        'maintainability': 'maintainability',
                        'governance': 'governance',
                        'drift': 'drift',
                        'optimization': 'optimize',
                      };
                      
                      const targetTab = tabMap[rec.source] || rec.source;
                      
                      return (
                        <TableRow key={rec.id}>
                          <TableCell className="font-medium">{rec.text}</TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {rec.description}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="capitalize">
                              {rec.category}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {rec.impact ? (
                              <Badge
                                variant={
                                  rec.impact === 'high' ? 'destructive' :
                                  rec.impact === 'medium' ? 'warning' :
                                  'secondary'
                                }
                                className="capitalize"
                              >
                                {rec.impact}
                              </Badge>
                            ) : (
                              <span className="text-muted-foreground text-sm">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {rec.effort ? (
                              <Badge
                                variant={
                                  rec.effort === 'high' ? 'destructive' :
                                  rec.effort === 'medium' ? 'warning' :
                                  'secondary'
                                }
                                className="capitalize"
                              >
                                {rec.effort}
                              </Badge>
                            ) : (
                              <span className="text-muted-foreground text-sm">-</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setActiveTab(targetTab)}
                              className="flex items-center gap-1 text-xs"
                            >
                              <ExternalLink className="h-3 w-3" />
                              View Details
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-500" />
                  <p>No actionable recommendations found for the selected filter.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Graph Tab - DAG Visualization */}
        <TabsContent value="graph" className="space-y-6">
          <WorkflowGraphTab workflow={workflow} />
        </TabsContent>

        {/* Nodes Tab */}
        <TabsContent value="nodes" className="space-y-6">
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
                  {analysis.nodes.map((nodeAnalysis) => {
                    // Find the full workflow node
                    const workflowNode = workflow?.nodes.find(n => n.id === nodeAnalysis.id);
                    if (!workflowNode) return null;
                    
                    return (
                      <TableRow 
                        key={nodeAnalysis.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => setSelectedNode(workflowNode)}
                      >
                        <TableCell className="font-medium">
                          {nodeAnalysis.isTrigger && (
                            <Badge variant="success" className="mr-2 text-xs">Trigger</Badge>
                          )}
                          {nodeAnalysis.name}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary" className="text-xs">
                            {formatNodeType(nodeAnalysis.type)}
                          </Badge>
                        </TableCell>
                        <TableCell className="capitalize text-muted-foreground">
                          {nodeAnalysis.category}
                        </TableCell>
                        <TableCell>
                          {nodeAnalysis.isCredentialed ? (
                            <div className="flex items-center gap-1">
                              <Lock className="h-3 w-3 text-yellow-500" />
                              <span className="text-xs">Yes</span>
                            </div>
                          ) : (
                            <span className="text-muted-foreground text-xs">None</span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Node Categories Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Node Categories</CardTitle>
              <CardDescription>Distribution of node types in this workflow</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
                {Object.entries(
                  analysis.nodes.reduce((acc: Record<string, number>, node) => {
                    acc[node.category] = (acc[node.category] || 0) + 1;
                    return acc;
                  }, {})
                ).map(([category, count]) => (
                  <div key={category} className="p-3 rounded-lg bg-muted text-center">
                    <div className="text-2xl font-bold">{count}</div>
                    <div className="text-xs text-muted-foreground capitalize">{category}</div>
                  </div>
                ))}
              </div>
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
                        {formatNodeType(node.type)}
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
                  {analysis.governance.auditability < 100 && (
                    <p className="text-xs text-yellow-600 dark:text-yellow-500 mt-2">
                      {getAuditabilityExplanation(analysis.governance.auditability, analysis.nodes)}
                    </p>
                  )}
                </div>
                <div className="p-4 rounded-lg bg-muted">
                  <div className="text-2xl font-bold">{analysis.governance.environmentPortability}%</div>
                  <div className="text-sm text-muted-foreground">Environment Portability</div>
                  {analysis.governance.environmentPortability < 100 && (
                    <p className="text-xs text-yellow-600 dark:text-yellow-500 mt-2">
                      {getPortabilityExplanation(analysis.governance.environmentPortability)}
                    </p>
                  )}
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
                  {!analysis.governance.promotionSafety && (
                    <p className="text-xs text-red-600 dark:text-red-500 mt-2">
                      {getProdSafeExplanation(analysis.governance.promotionSafety, analysis.governance.piiExposureRisks)}
                    </p>
                  )}
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

        {/* Versions Tab */}
        <TabsContent value="versions" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Version History</CardTitle>
              <CardDescription>Track changes and workflow versions over time</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Current Version Info */}
                <div className="p-4 rounded-lg bg-muted">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium">Current Version</h4>
                      <p className="text-sm text-muted-foreground mt-1">
                        Last updated: {new Date(workflow.updatedAt).toLocaleString()}
                      </p>
                    </div>
                    <Badge variant="success">Active</Badge>
                  </div>
                </div>

                {/* Git Sync Status */}
                {driftData?.gitConfigured ? (
                  <div className="space-y-4">
                    <h4 className="font-medium flex items-center gap-2">
                      <GitCompare className="h-4 w-4" />
                      GitHub Commits
                    </h4>
                    {driftData?.lastCommitSha ? (
                      <div className="border rounded-lg divide-y">
                        <div className="p-4 flex items-center justify-between">
                          <div>
                            <div className="flex items-center gap-2">
                              <code className="text-sm bg-muted px-2 py-0.5 rounded">
                                {driftData.lastCommitSha.substring(0, 7)}
                              </code>
                              <span className="text-sm text-muted-foreground">
                                Latest commit
                              </span>
                            </div>
                            {driftData.lastCommitDate && (
                              <p className="text-xs text-muted-foreground mt-1">
                                {new Date(driftData.lastCommitDate).toLocaleString()}
                              </p>
                            )}
                          </div>
                          {driftData.hasDrift ? (
                            <Badge variant="warning">Has Changes</Badge>
                          ) : (
                            <Badge variant="success">In Sync</Badge>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-8 text-muted-foreground border rounded-lg">
                        <History className="h-8 w-8 mx-auto mb-2 opacity-50" />
                        <p>No Git history available</p>
                        <p className="text-xs mt-1">Sync to GitHub to start tracking versions</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-4 rounded-lg border border-dashed">
                    <div className="text-center text-muted-foreground">
                      <GitCompare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                      <p>GitHub not configured</p>
                      <p className="text-xs mt-1">Configure GitHub integration in environment settings to enable version tracking</p>
                    </div>
                  </div>
                )}

                {/* Workflow Snapshots */}
                <div className="space-y-4">
                  <h4 className="font-medium flex items-center gap-2">
                    <History className="h-4 w-4" />
                    Workflow Snapshots
                  </h4>
                  <div className="text-center py-8 text-muted-foreground border rounded-lg">
                    <Layers className="h-8 w-8 mx-auto mb-2 opacity-50" />
                    <p>Snapshot history coming soon</p>
                    <p className="text-xs mt-1">Snapshots are created before deployments and major changes</p>
                  </div>
                </div>

                {/* Workflow Metadata */}
                <div className="space-y-4">
                  <h4 className="font-medium">Workflow Timeline</h4>
                  <div className="border rounded-lg divide-y">
                    <div className="p-4 flex items-center gap-4">
                      <div className="w-2 h-2 rounded-full bg-green-500"></div>
                      <div>
                        <p className="text-sm font-medium">Created</p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(workflow.createdAt).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="p-4 flex items-center gap-4">
                      <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                      <div>
                        <p className="text-sm font-medium">Last Modified</p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(workflow.updatedAt).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    {workflow.lastSyncedAt && (
                      <div className="p-4 flex items-center gap-4">
                        <div className="w-2 h-2 rounded-full bg-purple-500"></div>
                        <div>
                          <p className="text-sm font-medium">Last Synced</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(workflow.lastSyncedAt).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* JSON Tab */}
        <TabsContent value="json" className="space-y-6">
          <JsonViewerTab workflow={workflow} />
        </TabsContent>
      </Tabs>

      {/* Node Details Panel */}
      {selectedNode && (
        <NodeDetailsPanel
          node={selectedNode}
          metrics={nodeMetrics.get(selectedNode.id)}
          executions={executionsData as Execution[] || []}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}
