import { 
  X, Key, AlertTriangle, RefreshCw, Settings, 
  CheckCircle2, XCircle, Clock, Play, Database
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { WorkflowNode, Execution } from '@/types';
import { NodeConfigView } from './NodeConfigView';

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

interface NodeDetailsPanelProps {
  node: WorkflowNode | null;
  metrics?: NodeMetrics;
  executions?: Execution[];
  onClose: () => void;
}

export function NodeDetailsPanel({ 
  node, 
  metrics, 
  executions = [],
  onClose 
}: NodeDetailsPanelProps) {
  if (!node) return null;
  
  // Extract sample I/O from executions
  const sampleInput = metrics?.sampleInput;
  const sampleOutput = metrics?.sampleOutput;
  
  // Get credential info
  const credentials = node.credentials || {};
  const credentialEntries = Object.entries(credentials);
  
  return (
    <div className="fixed right-0 top-0 h-full w-96 bg-white dark:bg-slate-900 shadow-xl z-50 overflow-y-auto border-l border-slate-200 dark:border-slate-800">
      <Card className="border-0 rounded-none h-full shadow-none">
        <CardHeader className="border-b sticky top-0 bg-white dark:bg-slate-900 z-10">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <CardTitle className="truncate">{node.name || node.id}</CardTitle>
              <div className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                {node.type.replace('n8n-nodes-base.', '').replace('@n8n/', '')}
              </div>
            </div>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </CardHeader>
        
        <CardContent className="pt-4">
          <Tabs defaultValue="basic" className="w-full">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="basic" className="text-xs">Basic</TabsTrigger>
              <TabsTrigger value="execution" className="text-xs">Execution</TabsTrigger>
              <TabsTrigger value="io" className="text-xs">I/O</TabsTrigger>
              <TabsTrigger value="config" className="text-xs">Config</TabsTrigger>
            </TabsList>
            
            {/* Basic Tab */}
            <TabsContent value="basic" className="space-y-4 mt-4">
              <div>
                <h3 className="text-sm font-semibold mb-2">Node Information</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Type:</span>
                    <Badge variant="outline" className="text-xs">{node.type}</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Status:</span>
                    <Badge variant={node.disabled ? "destructive" : "default"}>
                      {node.disabled ? 'Disabled' : 'Enabled'}
                    </Badge>
                  </div>
                  {node.typeVersion && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">Version:</span>
                      <span className="text-slate-700 dark:text-slate-300">{node.typeVersion}</span>
                    </div>
                  )}
                </div>
              </div>
              
              {node.notes && (
                <div>
                  <h3 className="text-sm font-semibold mb-2">Notes</h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400">{node.notes}</p>
                </div>
              )}
            </TabsContent>
            
            {/* Execution Tab */}
            <TabsContent value="execution" className="space-y-4 mt-4">
              {metrics ? (
                <>
                  <div>
                    <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                      <Play className="h-4 w-4" />
                      Execution Status
                    </h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">Last Status:</span>
                        <div className="flex items-center gap-2">
                          {metrics.lastStatus === 'success' && (
                            <>
                              <CheckCircle2 className="h-4 w-4 text-green-500" />
                              <span className="text-green-600">Success</span>
                            </>
                          )}
                          {metrics.lastStatus === 'error' && (
                            <>
                              <XCircle className="h-4 w-4 text-red-500" />
                              <span className="text-red-600">Error</span>
                            </>
                          )}
                          {metrics.lastStatus === 'running' && (
                            <>
                              <Clock className="h-4 w-4 text-blue-500 animate-spin" />
                              <span className="text-blue-600">Running</span>
                            </>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex justify-between">
                        <span className="text-slate-500">Average Duration:</span>
                        <span className="font-semibold">{Math.round(metrics.avgDuration)}ms</span>
                      </div>
                      
                      <div className="flex justify-between">
                        <span className="text-slate-500">Failure Rate:</span>
                        <span className={`font-semibold ${metrics.failureRate > 0.1 ? 'text-red-600' : ''}`}>
                          {(metrics.failureRate * 100).toFixed(1)}%
                        </span>
                      </div>
                      
                      <div className="flex justify-between">
                        <span className="text-slate-500">Total Executions:</span>
                        <span className="font-semibold">{metrics.executionCount}</span>
                      </div>
                    </div>
                  </div>
                  
                  {metrics.lastError && (
                    <div>
                      <h3 className="text-sm font-semibold mb-2 flex items-center gap-2 text-red-600">
                        <AlertTriangle className="h-4 w-4" />
                        Last Error
                      </h3>
                      <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950 p-2 rounded border border-red-200 dark:border-red-800">
                        {metrics.lastError}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-sm text-slate-500 text-center py-8">
                  No execution data available
                </div>
              )}
            </TabsContent>
            
            {/* I/O Tab */}
            <TabsContent value="io" className="space-y-4 mt-4">
              {sampleInput || sampleOutput ? (
                <>
                  {sampleInput && (
                    <div>
                      <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                        <Database className="h-4 w-4" />
                        Sample Input
                      </h3>
                      <pre className="text-xs bg-slate-50 dark:bg-slate-800 p-3 rounded border border-slate-200 dark:border-slate-700 overflow-x-auto max-h-48 overflow-y-auto">
                        {JSON.stringify(sampleInput, null, 2)}
                      </pre>
                    </div>
                  )}
                  
                  {sampleOutput && (
                    <div>
                      <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
                        <Database className="h-4 w-4" />
                        Sample Output
                      </h3>
                      <pre className="text-xs bg-slate-50 dark:bg-slate-800 p-3 rounded border border-slate-200 dark:border-slate-700 overflow-x-auto max-h-48 overflow-y-auto">
                        {JSON.stringify(sampleOutput, null, 2)}
                      </pre>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-sm text-slate-500 text-center py-8">
                  No I/O samples available
                </div>
              )}
            </TabsContent>
            
            {/* Config Tab */}
            <TabsContent value="config" className="space-y-4 mt-4">
              {/* Type-aware configuration view */}
              <NodeConfigView node={node} />
              
              {/* Retry Configuration */}
              {(node.parameters?.retryOnFail || node.parameters?.continueOnFail) && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <RefreshCw className="h-4 w-4" />
                      Retry Configuration
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-sm space-y-1">
                      {node.parameters.retryOnFail && (
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-3 w-3 text-green-500" />
                          <span>Retry on Fail: Enabled</span>
                        </div>
                      )}
                      {node.parameters.continueOnFail && (
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-3 w-3 text-green-500" />
                          <span>Continue on Fail: Enabled</span>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}
              
              {/* Credentials */}
              {credentialEntries.length > 0 && (
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Key className="h-4 w-4" />
                      Credentials
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {credentialEntries.map(([credType, credId]) => (
                        <div key={credType} className="flex items-center justify-between p-2 bg-slate-50 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700">
                          <div>
                            <div className="text-sm font-semibold">{credType}</div>
                            <div className="text-xs text-slate-500">{credId?.id || credId || 'Not specified'}</div>
                          </div>
                          <Badge variant={credId ? "default" : "destructive"}>
                            {credId ? 'Configured' : 'Missing'}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

