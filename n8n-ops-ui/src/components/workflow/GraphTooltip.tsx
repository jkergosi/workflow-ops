import type { Node, Edge } from 'reactflow';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, AlertTriangle, XCircle, Clock } from 'lucide-react';
import type { WorkflowNode } from '@/types';

interface NodeTooltipProps {
  node: Node;
  workflowNode: WorkflowNode;
  lastStatus?: 'success' | 'error' | 'running';
  lastError?: string;
}

export function NodeTooltip({ node, workflowNode, lastStatus, lastError }: NodeTooltipProps) {
  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-3 max-w-xs z-50">
      <div className="flex items-start gap-2 mb-2">
        <div className="font-semibold text-sm text-slate-900 dark:text-slate-100">
          {workflowNode.name || node.id}
        </div>
        {lastStatus && (
          <div className="ml-auto">
            {lastStatus === 'success' && (
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            )}
            {lastStatus === 'error' && (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
            {lastStatus === 'running' && (
              <Clock className="h-4 w-4 text-blue-500 animate-spin" />
            )}
          </div>
        )}
      </div>
      
      <div className="text-xs text-slate-600 dark:text-slate-400 mb-2">
        {workflowNode.type.replace('n8n-nodes-base.', '').replace('@n8n/', '')}
      </div>
      
      {workflowNode.disabled && (
        <Badge variant="outline" className="text-xs">Disabled</Badge>
      )}
      
      {lastError && (
        <div className="mt-2 text-xs text-red-600 dark:text-red-400 flex items-start gap-1">
          <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />
          <span className="line-clamp-2">{lastError}</span>
        </div>
      )}
      
      {workflowNode.notes && (
        <div className="mt-2 text-xs text-slate-500 dark:text-slate-400 italic">
          {workflowNode.notes}
        </div>
      )}
    </div>
  );
}

interface EdgeTooltipProps {
  edge: Edge;
  branchLabel?: string;
  condition?: string;
  executionPercentage?: number;
  isErrorPath?: boolean;
}

export function EdgeTooltip({ 
  edge, 
  branchLabel, 
  condition, 
  executionPercentage,
  isErrorPath 
}: EdgeTooltipProps) {
  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-3 max-w-xs z-50">
      {isErrorPath && (
        <div className="flex items-center gap-1 mb-2 text-red-600 dark:text-red-400">
          <AlertTriangle className="h-3 w-3" />
          <span className="text-xs font-semibold">Error Path</span>
        </div>
      )}
      
      {branchLabel && (
        <div className="text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1">
          {branchLabel}
        </div>
      )}
      
      {condition && (
        <div className="text-xs text-slate-600 dark:text-slate-400 font-mono mb-2">
          {condition}
        </div>
      )}
      
      {executionPercentage !== undefined && (
        <div className="text-xs text-slate-500 dark:text-slate-400">
          {executionPercentage.toFixed(1)}% of executions
        </div>
      )}
    </div>
  );
}

