// Workflow Analysis Types and Functions

export interface WorkflowNode {
  id: string;
  name: string;
  type: string;
  parameters?: Record<string, unknown>;
  position?: [number, number];
  credentials?: Record<string, unknown>;
}

export interface WorkflowConnection {
  node: string;
  type: string;
  index: number;
}

export interface Workflow {
  id: string;
  name: string;
  active: boolean;
  nodes?: WorkflowNode[];
  connections?: Record<string, Record<string, WorkflowConnection[][]>>;
  settings?: Record<string, unknown>;
  tags?: string[];
  createdAt?: string;
  updatedAt?: string;
}

export interface GraphAnalysis {
  nodeCount: number;
  edgeCount: number;
  complexityScore: number;
  complexityLevel: 'simple' | 'moderate' | 'complex' | 'very-complex';
  maxDepth: number;
  maxBranching: number;
  isLinear: boolean;
  hasFanOut: boolean;
  hasFanIn: boolean;
  hasCycles: boolean;
  triggerCount: number;
  sinkCount: number;
}

export interface NodeAnalysis {
  id: string;
  name: string;
  type: string;
  category: string;
  isCredentialed: boolean;
  isTrigger: boolean;
}

export interface DependencyAnalysis {
  name: string;
  type: 'api' | 'database' | 'service' | 'file' | 'other';
  nodeCount: number;
  nodes: string[];
}

export interface SummaryAnalysis {
  purpose: string;
  executionSummary: string;
  triggerTypes: string[];
  externalSystems: string[];
}

export interface ReliabilityAnalysis {
  score: number;
  level: 'excellent' | 'good' | 'warning' | 'critical';
  continueOnFailCount: number;
  errorHandlingNodes: number;
  retryNodes: number;
  missingErrorHandling: string[];
  failureHotspots: string[];
  recommendations: string[];
}

export interface PerformanceAnalysis {
  score: number;
  level: 'excellent' | 'good' | 'warning' | 'critical';
  hasParallelism: boolean;
  estimatedComplexity: 'low' | 'medium' | 'high';
  sequentialBottlenecks: string[];
  redundantCalls: string[];
  largePayloadRisks: string[];
  recommendations: string[];
}

export interface CostAnalysis {
  level: 'low' | 'medium' | 'high' | 'very-high';
  triggerFrequency: string;
  apiHeavyNodes: string[];
  llmNodes: string[];
  costAmplifiers: string[];
  throttlingCandidates: string[];
  recommendations: string[];
}

export interface SecurityAnalysis {
  score: number;
  level: 'excellent' | 'good' | 'warning' | 'critical';
  credentialCount: number;
  credentialTypes: string[];
  hardcodedSecretSignals: string[];
  overPrivilegedRisks: string[];
  secretReuseRisks: string[];
  recommendations: string[];
}

export interface MaintainabilityAnalysis {
  score: number;
  level: 'excellent' | 'good' | 'warning' | 'critical';
  namingConsistency: number;
  logicalGroupingScore: number;
  readabilityScore: number;
  missingDescriptions: string[];
  missingAnnotations: string[];
  nodeReuseOpportunities: string[];
  recommendations: string[];
}

export interface GovernanceAnalysis {
  score: number;
  level: 'excellent' | 'good' | 'warning' | 'critical';
  auditability: number;
  environmentPortability: number;
  promotionSafety: boolean;
  piiExposureRisks: string[];
  retentionIssues: string[];
  recommendations: string[];
}

export interface DriftAnalysis {
  hasGitMismatch: boolean;
  environmentDivergence: string[];
  duplicateSuspects: string[];
  partialCopies: string[];
  recommendations: string[];
}

export interface OptimizationSuggestion {
  title: string;
  description: string;
  impact: 'low' | 'medium' | 'high';
  effort: 'low' | 'medium' | 'high';
  category: 'performance' | 'cost' | 'reliability' | 'security' | 'maintainability';
}

export interface WorkflowAnalysis {
  graph: GraphAnalysis;
  nodes: NodeAnalysis[];
  dependencies: DependencyAnalysis[];
  summary: SummaryAnalysis;
  reliability: ReliabilityAnalysis;
  performance: PerformanceAnalysis;
  cost: CostAnalysis;
  security: SecurityAnalysis;
  maintainability: MaintainabilityAnalysis;
  governance: GovernanceAnalysis;
  drift: DriftAnalysis;
  optimizations: OptimizationSuggestion[];
}

// Helper functions

/**
 * Format node type for user-friendly display
 * e.g., "n8n-nodes-base.executeWorkflow" → "Execute Workflow"
 */
export function formatNodeType(type: string): string {
  // Remove common prefixes
  let cleaned = type
    .replace('n8n-nodes-base.', '')
    .replace('@n8n/n8n-nodes-langchain.', '')
    .replace('n8n-nodes-', '');

  // Handle special cases with proper names
  const specialCases: Record<string, string> = {
    'executeWorkflow': 'Execute Workflow',
    'httpRequest': 'HTTP Request',
    'if': 'IF',
    'switch': 'Switch',
    'set': 'Set',
    'code': 'Code',
    'webhook': 'Webhook',
    'scheduleTrigger': 'Schedule Trigger',
    'manualTrigger': 'Manual Trigger',
    'splitInBatches': 'Split In Batches',
    'noOp': 'No Operation',
    'merge': 'Merge',
    'functionItem': 'Function Item',
    'function': 'Function',
    'itemLists': 'Item Lists',
    'dateTime': 'Date & Time',
    'wait': 'Wait',
    'respondToWebhook': 'Respond to Webhook',
    'errorTrigger': 'Error Trigger',
    'executeCommand': 'Execute Command',
    'readWriteFile': 'Read/Write File',
    'localFileTrigger': 'Local File Trigger',
    'stickyNote': 'Sticky Note',
    'start': 'Start',
    'stopAndError': 'Stop And Error',
    'filter': 'Filter',
    'removeDuplicates': 'Remove Duplicates',
    'sort': 'Sort',
    'limit': 'Limit',
    'aggregate': 'Aggregate',
    'renameKeys': 'Rename Keys',
    'convertToFile': 'Convert to File',
    'extractFromFile': 'Extract from File',
    'markdown': 'Markdown',
    'html': 'HTML',
    'xml': 'XML',
    'crypto': 'Crypto',
    'compression': 'Compression',
    'moveBinaryData': 'Move Binary Data',
    'spreadsheetFile': 'Spreadsheet File',
  };

  if (specialCases[cleaned]) {
    return specialCases[cleaned];
  }

  // Convert camelCase to Title Case with spaces
  // e.g., "googleSheets" → "Google Sheets"
  return cleaned
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, str => str.toUpperCase())
    .trim();
}

function getNodeCategory(type: string): string {
  const typeLC = type.toLowerCase();
  if (typeLC.includes('trigger') || typeLC.includes('webhook')) return 'trigger';
  if (typeLC.includes('http') || typeLC.includes('api')) return 'api';
  if (typeLC.includes('postgres') || typeLC.includes('mysql') || typeLC.includes('mongo') || typeLC.includes('database')) return 'database';
  if (typeLC.includes('if') || typeLC.includes('switch') || typeLC.includes('merge')) return 'logic';
  if (typeLC.includes('code') || typeLC.includes('function')) return 'code';
  if (typeLC.includes('set') || typeLC.includes('item')) return 'transform';
  if (typeLC.includes('openai') || typeLC.includes('anthropic') || typeLC.includes('llm')) return 'ai';
  return 'other';
}

function isTriggerNode(type: string): boolean {
  const typeLC = type.toLowerCase();
  return typeLC.includes('trigger') || typeLC.includes('webhook') || typeLC.includes('schedule') || typeLC.includes('cron');
}

function countConnections(connections: Record<string, Record<string, WorkflowConnection[][]>> | undefined): number {
  if (!connections) return 0;
  let count = 0;
  for (const nodeConns of Object.values(connections)) {
    for (const outputConns of Object.values(nodeConns)) {
      for (const connArray of outputConns) {
        count += connArray.length;
      }
    }
  }
  return count;
}

function calculateComplexity(nodeCount: number, edgeCount: number, maxBranching: number): { score: number; level: GraphAnalysis['complexityLevel'] } {
  // Simple scoring: nodes + edges + branching factor
  const score = Math.min(100, Math.round((nodeCount * 3 + edgeCount * 2 + maxBranching * 5)));

  if (score < 25) return { score, level: 'simple' };
  if (score < 50) return { score, level: 'moderate' };
  if (score < 75) return { score, level: 'complex' };
  return { score, level: 'very-complex' };
}

function inferPurpose(nodes: WorkflowNode[]): string {
  const types = nodes.map(n => n.type.toLowerCase());

  if (types.some(t => t.includes('webhook'))) {
    if (types.some(t => t.includes('slack') || t.includes('discord'))) {
      return 'Webhook-triggered workflow that sends notifications';
    }
    return 'Webhook-triggered automation workflow';
  }

  if (types.some(t => t.includes('schedule') || t.includes('cron'))) {
    return 'Scheduled automation that runs on a regular interval';
  }

  if (types.some(t => t.includes('openai') || t.includes('anthropic'))) {
    return 'AI-powered workflow using language models';
  }

  if (types.some(t => t.includes('postgres') || t.includes('mysql'))) {
    return 'Database-driven workflow for data processing';
  }

  return 'Automation workflow for data processing and integration';
}

function inferExecutionSummary(nodes: WorkflowNode[]): string {
  const nodeCount = nodes.length;
  const triggers = nodes.filter(n => isTriggerNode(n.type));
  const outputs = nodes.filter(n => n.type.toLowerCase().includes('send') || n.type.toLowerCase().includes('write'));

  let summary = `Workflow with ${nodeCount} nodes`;
  if (triggers.length > 0) {
    summary += `, triggered by ${triggers.map(t => t.name).join(', ')}`;
  }
  if (outputs.length > 0) {
    summary += `, outputs to ${outputs.length} destination(s)`;
  }
  return summary;
}

function extractExternalSystems(nodes: WorkflowNode[]): string[] {
  const systems = new Set<string>();

  for (const node of nodes) {
    const typeLC = node.type.toLowerCase();
    if (typeLC.includes('http')) systems.add('HTTP/REST APIs');
    if (typeLC.includes('postgres')) systems.add('PostgreSQL');
    if (typeLC.includes('mysql')) systems.add('MySQL');
    if (typeLC.includes('mongo')) systems.add('MongoDB');
    if (typeLC.includes('slack')) systems.add('Slack');
    if (typeLC.includes('discord')) systems.add('Discord');
    if (typeLC.includes('google')) systems.add('Google Services');
    if (typeLC.includes('openai')) systems.add('OpenAI');
    if (typeLC.includes('anthropic')) systems.add('Anthropic');
    if (typeLC.includes('github')) systems.add('GitHub');
    if (typeLC.includes('email') || typeLC.includes('smtp')) systems.add('Email');
    if (typeLC.includes('s3') || typeLC.includes('aws')) systems.add('AWS');
  }

  return Array.from(systems);
}

function extractDependencies(nodes: WorkflowNode[]): DependencyAnalysis[] {
  const deps: Map<string, DependencyAnalysis> = new Map();

  for (const node of nodes) {
    const systems = extractExternalSystems([node]);
    for (const sys of systems) {
      const existing = deps.get(sys);
      if (existing) {
        existing.nodeCount++;
        existing.nodes.push(node.name);
      } else {
        deps.set(sys, {
          name: sys,
          type: categorizeSystem(sys),
          nodeCount: 1,
          nodes: [node.name],
        });
      }
    }
  }

  return Array.from(deps.values());
}

function categorizeSystem(name: string): DependencyAnalysis['type'] {
  const nameLC = name.toLowerCase();
  if (nameLC.includes('api') || nameLC.includes('http')) return 'api';
  if (nameLC.includes('sql') || nameLC.includes('mongo') || nameLC.includes('database')) return 'database';
  if (nameLC.includes('s3') || nameLC.includes('file')) return 'file';
  return 'service';
}

function analyzeReliability(nodes: WorkflowNode[]): ReliabilityAnalysis {
  const errorHandlingNodes = nodes.filter(n =>
    n.type.toLowerCase().includes('error') ||
    n.type.toLowerCase().includes('try') ||
    n.type.toLowerCase().includes('catch')
  ).length;

  const retryNodes = nodes.filter(n =>
    n.parameters?.retry ||
    n.type.toLowerCase().includes('retry')
  ).length;

  const continueOnFailCount = nodes.filter(n =>
    n.parameters?.continueOnFail === true
  ).length;

  const score = Math.min(100, 50 + errorHandlingNodes * 10 + retryNodes * 10 + continueOnFailCount * 5);

  return {
    score,
    level: score >= 80 ? 'excellent' : score >= 60 ? 'good' : score >= 40 ? 'warning' : 'critical',
    continueOnFailCount,
    errorHandlingNodes,
    retryNodes,
    missingErrorHandling: nodes.filter(n =>
      (n.type.toLowerCase().includes('http') || n.type.toLowerCase().includes('api')) &&
      !n.parameters?.continueOnFail
    ).map(n => `${n.name} lacks error handling`),
    failureHotspots: nodes.filter(n =>
      n.type.toLowerCase().includes('code') || n.type.toLowerCase().includes('function')
    ).map(n => `${n.name} is a potential failure point`),
    recommendations: generateReliabilityRecommendations(errorHandlingNodes, retryNodes, nodes.length),
  };
}

function generateReliabilityRecommendations(errorHandling: number, retry: number, total: number): string[] {
  const recs: string[] = [];
  if (errorHandling === 0 && total > 3) {
    recs.push('Add error handling nodes to catch and handle failures gracefully');
  }
  if (retry === 0 && total > 5) {
    recs.push('Consider adding retry logic for external API calls');
  }
  if (recs.length === 0) {
    recs.push('Reliability looks good! Consider adding monitoring for production use.');
  }
  return recs;
}

function analyzePerformance(nodes: WorkflowNode[], edgeCount: number): PerformanceAnalysis {
  const hasParallelism = edgeCount > nodes.length;
  const apiCalls = nodes.filter(n => n.type.toLowerCase().includes('http')).length;
  const dbCalls = nodes.filter(n =>
    n.type.toLowerCase().includes('postgres') ||
    n.type.toLowerCase().includes('mysql')
  ).length;

  const complexity = apiCalls + dbCalls > 5 ? 'high' : apiCalls + dbCalls > 2 ? 'medium' : 'low';
  const score = 100 - (apiCalls * 5 + dbCalls * 5);

  return {
    score: Math.max(0, Math.min(100, score)),
    level: score >= 80 ? 'excellent' : score >= 60 ? 'good' : score >= 40 ? 'warning' : 'critical',
    hasParallelism,
    estimatedComplexity: complexity,
    sequentialBottlenecks: nodes.filter(n => n.type.toLowerCase().includes('wait')).map(n => `${n.name} introduces delay`),
    redundantCalls: [],
    largePayloadRisks: nodes.filter(n => n.type.toLowerCase().includes('batch')).map(n => `${n.name} may process large payloads`),
    recommendations: hasParallelism ? ['Good use of parallelism'] : ['Consider parallelizing independent operations'],
  };
}

function analyzeCost(nodes: WorkflowNode[]): CostAnalysis {
  const triggers = nodes.filter(n => isTriggerNode(n.type));
  const hasSchedule = triggers.some(t => t.type.toLowerCase().includes('schedule') || t.type.toLowerCase().includes('cron'));
  const hasWebhook = triggers.some(t => t.type.toLowerCase().includes('webhook'));

  const llmNodes = nodes.filter(n =>
    n.type.toLowerCase().includes('openai') ||
    n.type.toLowerCase().includes('anthropic') ||
    n.type.toLowerCase().includes('llm')
  );

  const apiHeavyNodes = nodes.filter(n => n.type.toLowerCase().includes('http'));

  const level = llmNodes.length > 2 ? 'very-high' : llmNodes.length > 0 ? 'high' : apiHeavyNodes.length > 3 ? 'medium' : 'low';

  return {
    level,
    triggerFrequency: hasSchedule ? 'Scheduled execution' : hasWebhook ? 'On-demand (webhook)' : 'Manual',
    apiHeavyNodes: apiHeavyNodes.map(n => n.name),
    llmNodes: llmNodes.map(n => n.name),
    costAmplifiers: llmNodes.length > 0 ? ['LLM usage significantly impacts costs'] : [],
    throttlingCandidates: apiHeavyNodes.length > 3 ? ['Consider rate limiting API calls'] : [],
    recommendations: llmNodes.length > 0
      ? ['Consider caching LLM responses', 'Use smaller models where appropriate']
      : ['Cost profile looks reasonable'],
  };
}

function analyzeSecurity(nodes: WorkflowNode[]): SecurityAnalysis {
  const credentialedNodes = nodes.filter(n => n.credentials && Object.keys(n.credentials).length > 0);
  const credentialTypes = new Set<string>();

  for (const node of credentialedNodes) {
    if (node.credentials) {
      for (const credType of Object.keys(node.credentials)) {
        credentialTypes.add(credType);
      }
    }
  }

  const hardcodedSecretSignals = nodes.filter(n => {
    const params = JSON.stringify(n.parameters || {}).toLowerCase();
    return params.includes('password') || params.includes('api_key') || params.includes('secret');
  }).map(n => `${n.name} may contain hardcoded secrets`);

  const score = 100 - (hardcodedSecretSignals.length * 20);

  return {
    score: Math.max(0, Math.min(100, score)),
    level: score >= 80 ? 'excellent' : score >= 60 ? 'good' : score >= 40 ? 'warning' : 'critical',
    credentialCount: credentialedNodes.length,
    credentialTypes: Array.from(credentialTypes),
    hardcodedSecretSignals,
    overPrivilegedRisks: [],
    secretReuseRisks: credentialTypes.size > 5 ? ['Many credential types in use - review for least privilege'] : [],
    recommendations: hardcodedSecretSignals.length > 0
      ? ['Move hardcoded secrets to credential store', 'Review credential usage']
      : ['Security practices look good'],
  };
}

function analyzeMaintainability(nodes: WorkflowNode[]): MaintainabilityAnalysis {
  const missingDescriptions = nodes.filter(n => !n.name || n.name.startsWith('Node')).map(n => `${n.name || n.id} has a default name`);
  const wellNamed = nodes.filter(n => n.name && !n.name.startsWith('Node') && n.name.length > 3);

  const namingConsistency = nodes.length > 0 ? Math.round((wellNamed.length / nodes.length) * 100) : 100;
  const readabilityScore = namingConsistency;
  const logicalGroupingScore = Math.min(100, namingConsistency + 20);

  const score = Math.round((namingConsistency + readabilityScore + logicalGroupingScore) / 3);

  return {
    score,
    level: score >= 80 ? 'excellent' : score >= 60 ? 'good' : score >= 40 ? 'warning' : 'critical',
    namingConsistency,
    logicalGroupingScore,
    readabilityScore,
    missingDescriptions,
    missingAnnotations: nodes.filter(n => !n.name || n.name.length < 4).map(n => n.name || n.id),
    nodeReuseOpportunities: [],
    recommendations: namingConsistency < 80
      ? ['Improve node naming for better readability', 'Add descriptions to complex nodes']
      : ['Maintainability looks good'],
  };
}

function analyzeGovernance(nodes: WorkflowNode[]): GovernanceAnalysis {
  const hasEnvVars = nodes.some(n => {
    const params = JSON.stringify(n.parameters || {});
    return params.includes('$env') || params.includes('process.env');
  });

  const environmentPortability = hasEnvVars ? 80 : 60;
  const auditability = nodes.every(n => n.name && n.name.length > 3) ? 90 : 60;

  const piiExposureRisks = nodes.filter(n => {
    const params = JSON.stringify(n.parameters || {}).toLowerCase();
    return params.includes('email') || params.includes('phone') || params.includes('ssn');
  }).map(n => `${n.name} may handle PII data`);

  const score = Math.round((environmentPortability + auditability) / 2);

  return {
    score,
    level: score >= 80 ? 'excellent' : score >= 60 ? 'good' : score >= 40 ? 'warning' : 'critical',
    auditability,
    environmentPortability,
    promotionSafety: piiExposureRisks.length === 0,
    piiExposureRisks,
    retentionIssues: [],
    recommendations: piiExposureRisks.length > 0
      ? ['Review PII handling practices', 'Ensure data retention policies are followed']
      : ['Governance looks good'],
  };
}

function analyzeDrift(): DriftAnalysis {
  // Drift analysis would typically compare with Git/other environments
  // For now, return defaults
  return {
    hasGitMismatch: false,
    environmentDivergence: [],
    duplicateSuspects: [],
    partialCopies: [],
    recommendations: ['Regularly sync with version control to track changes'],
  };
}

function generateOptimizations(nodes: WorkflowNode[], analysis: Partial<WorkflowAnalysis>): OptimizationSuggestion[] {
  const suggestions: OptimizationSuggestion[] = [];

  if (nodes.length > 20) {
    suggestions.push({
      title: 'Split into sub-workflows',
      description: 'Large workflows are harder to maintain. Consider breaking into smaller, reusable sub-workflows.',
      impact: 'high',
      effort: 'medium',
      category: 'maintainability',
    });
  }

  if (analysis.cost?.llmNodes && analysis.cost.llmNodes.length > 1) {
    suggestions.push({
      title: 'Implement LLM response caching',
      description: 'Cache responses for similar inputs to reduce API costs and improve performance.',
      impact: 'high',
      effort: 'medium',
      category: 'cost',
    });
  }

  if (analysis.reliability?.errorHandlingNodes === 0) {
    suggestions.push({
      title: 'Add error handling',
      description: 'Implement try-catch patterns and error handling nodes for robust execution.',
      impact: 'high',
      effort: 'low',
      category: 'reliability',
    });
  }

  return suggestions;
}

// Main analysis function
export function analyzeWorkflow(workflow: Workflow): WorkflowAnalysis {
  const nodes = workflow.nodes || [];
  const connections = workflow.connections;

  // Graph analysis
  const nodeCount = nodes.length;
  const edgeCount = countConnections(connections);
  const triggerCount = nodes.filter(n => isTriggerNode(n.type)).length;
  const sinkCount = nodes.filter(n => {
    const nodeId = n.id;
    // Check if this node has outgoing connections
    return !connections || !connections[nodeId] || Object.keys(connections[nodeId] || {}).length === 0;
  }).length;

  const maxBranching = connections
    ? Math.max(1, ...Object.values(connections).map(nc =>
        Object.values(nc).reduce((sum, conns) => sum + conns.flat().length, 0)
      ))
    : 1;

  const { score: complexityScore, level: complexityLevel } = calculateComplexity(nodeCount, edgeCount, maxBranching);

  const graph: GraphAnalysis = {
    nodeCount,
    edgeCount,
    complexityScore,
    complexityLevel,
    maxDepth: Math.ceil(Math.log2(nodeCount + 1)),
    maxBranching,
    isLinear: maxBranching <= 1,
    hasFanOut: maxBranching > 2,
    hasFanIn: sinkCount < nodeCount - triggerCount,
    hasCycles: false, // Would need proper cycle detection
    triggerCount,
    sinkCount,
  };

  // Node analysis
  const nodeAnalysis: NodeAnalysis[] = nodes.map(node => ({
    id: node.id,
    name: node.name,
    type: node.type,
    category: getNodeCategory(node.type),
    isCredentialed: !!(node.credentials && Object.keys(node.credentials).length > 0),
    isTrigger: isTriggerNode(node.type),
  }));

  // Dependencies
  const dependencies = extractDependencies(nodes);

  // Summary
  const summary: SummaryAnalysis = {
    purpose: inferPurpose(nodes),
    executionSummary: inferExecutionSummary(nodes),
    triggerTypes: nodes.filter(n => isTriggerNode(n.type)).map(n => n.type),
    externalSystems: extractExternalSystems(nodes),
  };

  // Detailed analyses
  const reliability = analyzeReliability(nodes);
  const performance = analyzePerformance(nodes, edgeCount);
  const cost = analyzeCost(nodes);
  const security = analyzeSecurity(nodes);
  const maintainability = analyzeMaintainability(nodes);
  const governance = analyzeGovernance(nodes);
  const drift = analyzeDrift();

  const partialAnalysis = { cost, reliability };
  const optimizations = generateOptimizations(nodes, partialAnalysis);

  return {
    graph,
    nodes: nodeAnalysis,
    dependencies,
    summary,
    reliability,
    performance,
    cost,
    security,
    maintainability,
    governance,
    drift,
    optimizations,
  };
}
