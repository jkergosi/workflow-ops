import { useMemo, useCallback, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  Handle,

} from 'reactflow';
import type { Node, Edge, NodeProps } from 'reactflow';
import 'reactflow/dist/style.css';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Play,
  AlertTriangle,
  Key,
  Zap,
  GitBranch,
  Database,
  Globe,
  Code,
  Settings,
  Bot,
  ArrowRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
} from 'lucide-react';
import type { Workflow, WorkflowNode, Execution } from '@/types';
import { apiClient } from '@/lib/api-client';
import { NodeTooltip, EdgeTooltip } from './GraphTooltip';
import { NodeDetailsPanel } from './NodeDetailsPanel';

interface WorkflowGraphTabProps {
  workflow: Workflow;
}

// Node category icons and colors
const categoryConfig: Record<string, { icon: React.ElementType; color: string; bgColor: string; borderColor: string }> = {
  trigger: { icon: Play, color: 'text-green-700', bgColor: 'bg-green-50 dark:bg-green-950', borderColor: 'border-green-500' },
  error: { icon: AlertTriangle, color: 'text-red-700', bgColor: 'bg-red-50 dark:bg-red-950', borderColor: 'border-red-500' },
  logic: { icon: GitBranch, color: 'text-purple-700', bgColor: 'bg-purple-50 dark:bg-purple-950', borderColor: 'border-purple-500' },
  database: { icon: Database, color: 'text-blue-700', bgColor: 'bg-blue-50 dark:bg-blue-950', borderColor: 'border-blue-500' },
  api: { icon: Globe, color: 'text-orange-700', bgColor: 'bg-orange-50 dark:bg-orange-950', borderColor: 'border-orange-500' },
  code: { icon: Code, color: 'text-gray-700', bgColor: 'bg-gray-50 dark:bg-gray-800', borderColor: 'border-gray-500' },
  ai: { icon: Bot, color: 'text-pink-700', bgColor: 'bg-pink-50 dark:bg-pink-950', borderColor: 'border-pink-500' },
  transform: { icon: Settings, color: 'text-cyan-700', bgColor: 'bg-cyan-50 dark:bg-cyan-950', borderColor: 'border-cyan-500' },
  credential: { icon: Key, color: 'text-yellow-700', bgColor: 'bg-yellow-50 dark:bg-yellow-950', borderColor: 'border-yellow-500' },
  default: { icon: Zap, color: 'text-slate-700', bgColor: 'bg-slate-50 dark:bg-slate-800', borderColor: 'border-slate-400' },
};

// Custom node component
function CustomNode({ data, selected }: NodeProps) {
  const config = categoryConfig[data.category] || categoryConfig.default;
  const Icon = config.icon;

  return (
    <div
      className={`
        relative px-4 py-3 rounded-lg border-2 shadow-lg min-w-[180px] max-w-[220px]
        transition-all duration-200
        ${config.bgColor} ${config.borderColor}
        ${selected ? 'ring-2 ring-blue-500 ring-offset-2' : ''}
        ${data.isTrigger ? 'border-l-4 border-l-green-500' : ''}
        ${data.isError ? 'border-l-4 border-l-red-500' : ''}
      `}
    >
      {/* Input Handle */}
      {!data.isTrigger && (
        <Handle
          type="target"
          position={Position.Left}
          className="!w-3 !h-3 !bg-slate-400 !border-2 !border-white"
        />
      )}

      {/* Header with icon and badges */}
      <div className="flex items-start gap-2 mb-1">
        <div className={`p-1.5 rounded ${config.bgColor} ${config.color}`}>
          <Icon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap gap-1 mb-1">
            {data.isTrigger && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-green-500 text-white">
                TRIGGER
              </span>
            )}
            {data.isError && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-red-500 text-white">
                ERROR
              </span>
            )}
            {data.hasCredentials && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-yellow-500 text-white">
                <Key className="w-2.5 h-2.5 mr-0.5" />
                AUTH
              </span>
            )}
            {data.isBranching && (
              <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-500 text-white">
                <GitBranch className="w-2.5 h-2.5 mr-0.5" />
                BRANCH
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Node name */}
      <div className="font-semibold text-sm text-slate-900 dark:text-slate-100 truncate" title={data.label}>
        {data.label}
      </div>

      {/* Node type */}
      <div className="text-[10px] text-slate-500 dark:text-slate-400 truncate mt-0.5" title={data.nodeType}>
        {data.nodeType}
      </div>

      {/* Output Handle(s) */}
      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-slate-400 !border-2 !border-white"
      />

      {/* Multiple output indicator */}
      {data.outputCount > 1 && (
        <div className="absolute -right-1 top-1/2 -translate-y-1/2 flex flex-col gap-1">
          {Array.from({ length: Math.min(data.outputCount, 3) }).map((_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full ${i === 0 ? 'bg-slate-400' : i === 1 ? 'bg-red-400' : 'bg-orange-400'}`}
              title={i === 0 ? 'Main output' : i === 1 ? 'Error/Alt output' : `Output ${i + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

const nodeTypes = {
  custom: CustomNode,
};

// Helper functions
function isTriggerNode(nodeType: string): boolean {
  const typeLower = nodeType.toLowerCase();
  return typeLower.includes('trigger') || typeLower.includes('webhook') || typeLower.includes('schedule') || typeLower.includes('cron');
}

function isErrorNode(nodeType: string, nodeName: string): boolean {
  const typeLower = nodeType.toLowerCase();
  const nameLower = nodeName.toLowerCase();
  return typeLower.includes('error') || nameLower.includes('error') || typeLower.includes('catch') || typeLower.includes('stop');
}

function isBranchingNode(nodeType: string): boolean {
  const typeLower = nodeType.toLowerCase();
  return typeLower.includes('switch') || typeLower.includes('if') || typeLower.includes('router') || typeLower.includes('split');
}

// Helper function to get branch label from node and output index
function getBranchLabel(
  node: WorkflowNode,
  outputIndex: number,
  outputType: string
): string {
  const typeLower = node.type.toLowerCase();
  
  if (typeLower.includes('if')) {
    return outputIndex === 0 ? 'true' : 'false';
  }
  
  if (typeLower.includes('switch')) {
    const rules = node.parameters?.rules || node.parameters?.conditions;
    if (Array.isArray(rules) && rules[outputIndex]) {
      return rules[outputIndex].value || `case ${outputIndex + 1}`;
    }
    return `case ${outputIndex + 1}`;
  }
  
  if (typeLower.includes('split')) {
    return `batch ${outputIndex + 1}`;
  }
  
  if (outputType === 'error') {
    return 'error';
  }
  
  return '';
}

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

function calculateNodeMetricsWithIO(
  executions: Execution[],
  nodes: WorkflowNode[]
): Map<string, NodeMetrics> {
  const metrics = new Map<string, NodeMetrics>();
  
  nodes.forEach(node => {
    const nodeExecutions = executions.filter(exec => {
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
    const sortedExecutions = [...nodeExecutions].sort((a, b) => 
      new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime()
    );
    
    sortedExecutions.forEach(exec => {
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
}

function getNodeCategory(nodeType: string, nodeName: string, hasCredentials: boolean): string {
  const typeLower = nodeType.toLowerCase();

  if (isTriggerNode(nodeType)) return 'trigger';
  if (isErrorNode(nodeType, nodeName)) return 'error';
  if (typeLower.includes('switch') || typeLower.includes('if') || typeLower.includes('merge') || typeLower.includes('router')) return 'logic';
  if (typeLower.includes('postgres') || typeLower.includes('mysql') || typeLower.includes('mongo') || typeLower.includes('redis') || typeLower.includes('database')) return 'database';
  if (typeLower.includes('http') || typeLower.includes('api') || typeLower.includes('webhook') || typeLower.includes('request')) return 'api';
  if (typeLower.includes('code') || typeLower.includes('function') || typeLower.includes('javascript')) return 'code';
  if (typeLower.includes('openai') || typeLower.includes('anthropic') || typeLower.includes('llm') || typeLower.includes('ai') || typeLower.includes('agent') || typeLower.includes('langchain')) return 'ai';
  if (typeLower.includes('set') || typeLower.includes('item') || typeLower.includes('transform') || typeLower.includes('convert')) return 'transform';
  if (hasCredentials) return 'credential';

  return 'default';
}

function formatNodeType(nodeType: string): string {
  return nodeType
    .replace('n8n-nodes-base.', '')
    .replace('@n8n/n8n-nodes-langchain.', '')
    .replace(/([A-Z])/g, ' $1')
    .trim();
}

// Layout calculation
function calculateLayout(nodes: WorkflowNode[], connections: Record<string, any>): { nodes: Node[]; edges: Edge[] } {
  const nodeById = new Map<string, WorkflowNode>();
  const nodeByName = new Map<string, WorkflowNode>();
  nodes.forEach(node => {
    nodeById.set(node.id, node);
    if (node.name) nodeByName.set(node.name, node);
  });

  const outgoing = new Map<string, { targetId: string; outputIndex: number }[]>();
  const incoming = new Map<string, string[]>();
  nodes.forEach(node => {
    outgoing.set(node.id, []);
    incoming.set(node.id, []);
  });

  const edges: Edge[] = [];
  const outputCounts = new Map<string, number>();

  // Parse connections
  if (connections) {
    Object.entries(connections).forEach(([sourceName, outputs]) => {
      if (!outputs || typeof outputs !== 'object') return;

      const sourceNode = nodeByName.get(sourceName);
      if (!sourceNode) return;
      const sourceId = sourceNode.id;

      Object.entries(outputs as Record<string, any[][]>).forEach(([outputType, outputConnections]) => {
        if (!Array.isArray(outputConnections)) return;

        // Track max output index for this node
        const maxOutput = Math.max(outputCounts.get(sourceId) || 0, outputConnections.length);
        outputCounts.set(sourceId, maxOutput);

        outputConnections.forEach((connectionArray, outputIndex) => {
          if (!Array.isArray(connectionArray)) return;

          connectionArray.forEach((conn: { node: string; type?: string; index?: number }) => {
            const targetNode = nodeByName.get(conn.node);
            if (!targetNode) return;
            const targetId = targetNode.id;

            outgoing.get(sourceId)?.push({ targetId, outputIndex });
            incoming.get(targetId)?.push(sourceId);

            // Determine edge style based on output index
            const isMainPath = outputIndex === 0;
            const isErrorPath = outputType === 'error' || outputIndex > 0;

            let edgeColor = '#64748b'; // slate-500 - main path
            let strokeWidth = 2;
            let animated = false;
            let edgeLabel = '';

            // Get branch label if it's a branch node
            if (isBranchingNode(sourceNode.type)) {
              edgeLabel = getBranchLabel(sourceNode, outputIndex, outputType);
            }

            if (isErrorPath) {
              if (outputType === 'error') {
                edgeColor = '#ef4444'; // red-500 - error path
                edgeLabel = 'error';
                animated = true;
              } else if (outputIndex === 1 && !edgeLabel) {
                edgeColor = '#ef4444'; // red-500 - false path for IF
                edgeLabel = 'false';
                animated = true;
              } else if (outputIndex > 1 && !edgeLabel) {
                edgeColor = '#f97316'; // orange-500 - alternate paths
                edgeLabel = `alt ${outputIndex}`;
              }
              strokeWidth = 2;
            }

            edges.push({
              id: `${sourceId}-${targetId}-${outputIndex}`,
              source: sourceId,
              target: targetId,
              type: 'smoothstep',
              animated,
              style: {
                stroke: edgeColor,
                strokeWidth,
              },
              markerEnd: {
                type: MarkerType.ArrowClosed,
                color: edgeColor,
                width: 20,
                height: 20,
              },
              label: edgeLabel || undefined,
              labelStyle: {
                fill: edgeColor,
                fontSize: 10,
                fontWeight: 600,
              },
              labelBgStyle: {
                fill: 'white',
                fillOpacity: 0.9,
              },
            });
          });
        });
      });
    });
  }

  // Calculate layers using topological sort
  const layers = new Map<string, number>();
  const visited = new Set<string>();

  function assignLayer(nodeId: string, layer: number) {
    if (visited.has(nodeId)) {
      layers.set(nodeId, Math.max(layers.get(nodeId) || 0, layer));
      return;
    }
    visited.add(nodeId);
    layers.set(nodeId, layer);

    const children = outgoing.get(nodeId) || [];
    children.forEach(({ targetId }) => assignLayer(targetId, layer + 1));
  }

  // Find and process triggers first
  const triggers = nodes.filter(n => isTriggerNode(n.type));
  const nonTriggersNoIncoming = nodes.filter(n =>
    !isTriggerNode(n.type) && (incoming.get(n.id)?.length || 0) === 0
  );

  [...triggers, ...nonTriggersNoIncoming].forEach(node => assignLayer(node.id, 0));

  // Handle disconnected nodes
  nodes.forEach(node => {
    if (!layers.has(node.id)) {
      layers.set(node.id, 0);
    }
  });

  // Group by layer
  const layerGroups = new Map<number, string[]>();
  layers.forEach((layer, nodeId) => {
    if (!layerGroups.has(layer)) layerGroups.set(layer, []);
    layerGroups.get(layer)!.push(nodeId);
  });

  // Position nodes
  const nodeWidth = 220;
  const nodeHeight = 100;
  const horizontalGap = 100;
  const verticalGap = 50;

  const flowNodes: Node[] = [];

  layerGroups.forEach((nodeIds, layer) => {
    const totalHeight = nodeIds.length * nodeHeight + (nodeIds.length - 1) * verticalGap;
    const startY = -totalHeight / 2;

    nodeIds.forEach((nodeId, index) => {
      const node = nodeById.get(nodeId);
      if (!node) return;

      const hasCredentials = !!(node.credentials && Object.keys(node.credentials).length > 0);
      const category = getNodeCategory(node.type, node.name || '', hasCredentials);

      flowNodes.push({
        id: node.id,
        type: 'custom',
        position: {
          x: layer * (nodeWidth + horizontalGap),
          y: startY + index * (nodeHeight + verticalGap),
        },
        data: {
          label: node.name || node.id,
          nodeType: formatNodeType(node.type),
          category,
          isTrigger: isTriggerNode(node.type),
          isError: isErrorNode(node.type, node.name || ''),
          isBranching: isBranchingNode(node.type),
          hasCredentials,
          outputCount: outputCounts.get(node.id) || 1,
        },
      });
    });
  });

  return { nodes: flowNodes, edges };
}

export function WorkflowGraphTab({ workflow }: WorkflowGraphTabProps) {
  const [showLegend, setShowLegend] = useState(true);
  const [hoveredNode, setHoveredNode] = useState<Node | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<Edge | null>(null);
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });

  // Fetch executions for metrics
  const { data: executions = [] } = useQuery({
    queryKey: ['executions', workflow.id, workflow.environment],
    queryFn: async () => {
      // Get environment ID from workflow or use environment type
      // For now, we'll pass the workflow ID and let the API handle it
      const response = await apiClient.getExecutions(undefined, workflow.id);
      return response.data || [];
    },
    enabled: !!workflow.id,
  });

  // Calculate node metrics
  const nodeMetrics = useMemo(() => {
    if (!executions.length) return new Map<string, NodeMetrics>();
    return calculateNodeMetricsWithIO(executions, workflow.nodes);
  }, [executions, workflow.nodes]);

  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    if (!workflow.nodes || workflow.nodes.length === 0) {
      return { nodes: [], edges: [] };
    }
    return calculateLayout(workflow.nodes, workflow.connections || {});
  }, [workflow]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Get last status and error for a node
  const getNodeStatus = useCallback((nodeId: string) => {
    const metrics = nodeMetrics.get(nodeId);
    if (!metrics) return undefined;
    
    return {
      status: metrics.lastStatus,
      error: metrics.lastError,
    };
  }, [nodeMetrics]);

  // Handle node hover
  const onNodeMouseEnter = useCallback((event: React.MouseEvent, node: Node) => {
    setHoveredNode(node);
    setTooltipPosition({ x: event.clientX, y: event.clientY });
  }, []);

  const onNodeMouseLeave = useCallback(() => {
    setHoveredNode(null);
  }, []);

  const onNodeMouseMove = useCallback((event: React.MouseEvent) => {
    setTooltipPosition({ x: event.clientX + 10, y: event.clientY + 10 });
  }, []);

  // Handle node click
  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    const workflowNode = workflow.nodes.find(n => n.id === node.id);
    setSelectedNode(workflowNode || null);
    setHoveredNode(null); // Close tooltip when opening panel
  }, [workflow]);

  // Handle edge hover
  const onEdgeMouseEnter = useCallback((event: React.MouseEvent, edge: Edge) => {
    setHoveredEdge(edge);
    setTooltipPosition({ x: event.clientX, y: event.clientY });
  }, []);

  const onEdgeMouseLeave = useCallback(() => {
    setHoveredEdge(null);
  }, []);

  const onEdgeMouseMove = useCallback((event: React.MouseEvent) => {
    setTooltipPosition({ x: event.clientX + 10, y: event.clientY + 10 });
  }, []);

  // Get edge info for tooltip
  const getEdgeInfo = useCallback((edge: Edge) => {
    const sourceNode = workflow.nodes.find(n => n.id === edge.source);
    if (!sourceNode) return null;
    
    const isErrorPath = edge.label === 'error' || edge.animated;
    const branchLabel = edge.label || undefined;
    
    // Extract condition from node parameters if it's a branch node
    let condition: string | undefined;
    if (isBranchingNode(sourceNode.type)) {
      if (sourceNode.type.toLowerCase().includes('if')) {
        condition = sourceNode.parameters?.conditions?.expression || 
                   sourceNode.parameters?.value1;
      } else if (sourceNode.type.toLowerCase().includes('switch')) {
        const rules = sourceNode.parameters?.rules || sourceNode.parameters?.conditions;
        if (Array.isArray(rules)) {
          const matchLabel = edge.label?.match(/case (\d+)/);
          if (matchLabel) {
            const ruleIndex = parseInt(matchLabel[1]) - 1;
            if (rules[ruleIndex]) {
              condition = rules[ruleIndex].value || rules[ruleIndex].condition;
            }
          }
        }
      }
    }
    
    return {
      branchLabel,
      condition,
      isErrorPath,
    };
  }, [workflow.nodes]);

  // Statistics
  const stats = useMemo(() => {
    const triggerCount = nodes.filter(n => n.data?.isTrigger).length;
    const errorCount = nodes.filter(n => n.data?.isError).length;
    const branchCount = nodes.filter(n => n.data?.isBranching).length;
    const credentialCount = nodes.filter(n => n.data?.hasCredentials).length;
    const errorPaths = initialEdges.filter(e => e.animated).length;
    const altPaths = initialEdges.filter(e => e.label && e.label !== 'error').length;

    return { triggerCount, errorCount, branchCount, credentialCount, errorPaths, altPaths };
  }, [nodes, initialEdges]);

  if (!workflow.nodes || workflow.nodes.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Workflow Graph</CardTitle>
          <CardDescription>Visual DAG representation</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12 text-muted-foreground">
            No nodes found in this workflow
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Legend Card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg flex items-center gap-2">
                <GitBranch className="h-5 w-5" />
                Workflow DAG
              </CardTitle>
              <CardDescription>Interactive directed acyclic graph visualization</CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => setShowLegend(!showLegend)}>
              {showLegend ? 'Hide' : 'Show'} Legend
            </Button>
          </div>
        </CardHeader>

        {showLegend && (
          <CardContent className="pt-0">
            {/* Stats */}
            <div className="flex flex-wrap gap-3 mb-4">
              <Badge variant="outline" className="text-sm">
                {workflow.nodes.length} Nodes
              </Badge>
              <Badge variant="outline" className="text-sm">
                {initialEdges.length} Connections
              </Badge>
              {stats.triggerCount > 0 && (
                <Badge className="bg-green-500 text-sm">
                  {stats.triggerCount} Trigger{stats.triggerCount > 1 ? 's' : ''}
                </Badge>
              )}
              {stats.branchCount > 0 && (
                <Badge className="bg-purple-500 text-sm">
                  {stats.branchCount} Branch{stats.branchCount > 1 ? 'es' : ''}
                </Badge>
              )}
              {stats.errorPaths > 0 && (
                <Badge className="bg-red-500 text-sm">
                  {stats.errorPaths} Error Path{stats.errorPaths > 1 ? 's' : ''}
                </Badge>
              )}
              {stats.credentialCount > 0 && (
                <Badge className="bg-yellow-500 text-white text-sm">
                  {stats.credentialCount} Authenticated
                </Badge>
              )}
            </div>

            {/* Legend */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-green-500"></div>
                <span>Trigger</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-red-500"></div>
                <span>Error Handler</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-purple-500"></div>
                <span>Branch/Logic</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-yellow-500"></div>
                <span>Authenticated</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-8 h-0.5 bg-slate-500"></div>
                <span>Main Path</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-8 h-0.5 bg-red-500" style={{ backgroundImage: 'repeating-linear-gradient(90deg, #ef4444 0, #ef4444 4px, transparent 4px, transparent 8px)' }}></div>
                <span>Error Path</span>
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Graph */}
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <div style={{ height: '650px', width: '100%' }} className="bg-slate-50 dark:bg-slate-900">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              onNodeMouseEnter={onNodeMouseEnter}
              onNodeMouseLeave={onNodeMouseLeave}
              onNodeMouseMove={onNodeMouseMove}
              onEdgeMouseEnter={onEdgeMouseEnter}
              onEdgeMouseLeave={onEdgeMouseLeave}
              onEdgeMouseMove={onEdgeMouseMove}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.2, maxZoom: 1.5 }}
              minZoom={0.1}
              maxZoom={2}
              defaultEdgeOptions={{
                type: 'smoothstep',
              }}
              proOptions={{ hideAttribution: true }}
            >
              <Background color="#94a3b8" gap={20} size={1} />
              <Controls
                showZoom={true}
                showFitView={true}
                showInteractive={false}
              />
              <MiniMap
                nodeStrokeWidth={3}
                nodeColor={(n) => {
                  if (n.data?.isTrigger) return '#22c55e';
                  if (n.data?.isError) return '#ef4444';
                  if (n.data?.isBranching) return '#a855f7';
                  if (n.data?.hasCredentials) return '#eab308';
                  if (n.data?.category === 'ai') return '#ec4899';
                  if (n.data?.category === 'database') return '#3b82f6';
                  if (n.data?.category === 'api') return '#f97316';
                  return '#64748b';
                }}
                maskColor="rgba(0,0,0,0.1)"
                className="!bg-white dark:!bg-slate-800"
              />
            </ReactFlow>
          </div>
        </CardContent>
      </Card>

      {/* Path Analysis */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Path Analysis</CardTitle>
          <CardDescription>Execution flow breakdown</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="p-4 rounded-lg bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800">
              <div className="flex items-center gap-2 mb-2">
                <Play className="h-5 w-5 text-green-600" />
                <h4 className="font-semibold text-green-800 dark:text-green-200">Entry Points</h4>
              </div>
              <p className="text-2xl font-bold text-green-700 dark:text-green-300">{stats.triggerCount}</p>
              <p className="text-sm text-green-600 dark:text-green-400">
                {stats.triggerCount === 0 ? 'Manual execution only' :
                 stats.triggerCount === 1 ? 'Single trigger workflow' :
                 'Multiple triggers detected'}
              </p>
            </div>

            <div className="p-4 rounded-lg bg-purple-50 dark:bg-purple-950 border border-purple-200 dark:border-purple-800">
              <div className="flex items-center gap-2 mb-2">
                <GitBranch className="h-5 w-5 text-purple-600" />
                <h4 className="font-semibold text-purple-800 dark:text-purple-200">Branch Points</h4>
              </div>
              <p className="text-2xl font-bold text-purple-700 dark:text-purple-300">{stats.branchCount}</p>
              <p className="text-sm text-purple-600 dark:text-purple-400">
                {stats.branchCount === 0 ? 'Linear execution flow' :
                 `${stats.branchCount} conditional branch${stats.branchCount > 1 ? 'es' : ''}`}
              </p>
            </div>

            <div className="p-4 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-5 w-5 text-red-600" />
                <h4 className="font-semibold text-red-800 dark:text-red-200">Error Handling</h4>
              </div>
              <p className="text-2xl font-bold text-red-700 dark:text-red-300">{stats.errorPaths}</p>
              <p className="text-sm text-red-600 dark:text-red-400">
                {stats.errorPaths === 0 ? 'No explicit error paths' :
                 `${stats.errorPaths} error path${stats.errorPaths > 1 ? 's' : ''} configured`}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Node Hover Tooltip */}
      {hoveredNode && !selectedNode && (
        <div
          className="fixed pointer-events-none z-50"
          style={{
            left: `${tooltipPosition.x}px`,
            top: `${tooltipPosition.y}px`,
          }}
        >
          <NodeTooltip
            node={hoveredNode}
            workflowNode={workflow.nodes.find(n => n.id === hoveredNode.id)!}
            lastStatus={getNodeStatus(hoveredNode.id)?.status}
            lastError={getNodeStatus(hoveredNode.id)?.error}
          />
        </div>
      )}

      {/* Edge Hover Tooltip */}
      {hoveredEdge && (
        <div
          className="fixed pointer-events-none z-50"
          style={{
            left: `${tooltipPosition.x}px`,
            top: `${tooltipPosition.y}px`,
          }}
        >
          {(() => {
            const edgeInfo = getEdgeInfo(hoveredEdge);
            if (!edgeInfo) return null;
            
            return (
              <EdgeTooltip
                edge={hoveredEdge}
                branchLabel={edgeInfo.branchLabel}
                condition={edgeInfo.condition}
                isErrorPath={edgeInfo.isErrorPath}
              />
            );
          })()}
        </div>
      )}

      {/* Node Details Panel */}
      {selectedNode && (
        <NodeDetailsPanel
          node={selectedNode}
          metrics={nodeMetrics.get(selectedNode.id)}
          executions={executions}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}
