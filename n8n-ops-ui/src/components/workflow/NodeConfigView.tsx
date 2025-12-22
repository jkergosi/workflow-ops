import { 
  Globe, Database, Code, GitBranch, Clock, 
  Mail, Settings
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { WorkflowNode } from '@/types';

interface NodeConfigViewProps {
  node: WorkflowNode;
}

export function NodeConfigView({ node }: NodeConfigViewProps) {
  const nodeType = node.type.toLowerCase();
  const params = node.parameters || {};

  // HTTP Request Node
  if (nodeType.includes('httprequest') || nodeType.includes('http')) {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Globe className="h-4 w-4" />
              Request Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-slate-500 mb-1">Method</div>
                <Badge variant="outline">{params.method || 'GET'}</Badge>
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">Authentication</div>
                <Badge variant={params.authentication ? "default" : "secondary"}>
                  {params.authentication || 'None'}
                </Badge>
              </div>
            </div>
            
            <div>
              <div className="text-xs text-slate-500 mb-1">URL</div>
              <div className="font-mono text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border break-all">
                {params.url || params.path || 'Not set'}
              </div>
            </div>
            
            {params.headers && Object.keys(params.headers).length > 0 && (
              <div>
                <div className="text-xs text-slate-500 mb-2">Headers</div>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {Object.entries(params.headers).map(([key, value]) => (
                    <div key={key} className="flex justify-between text-xs font-mono bg-slate-50 dark:bg-slate-800 p-1.5 rounded">
                      <span className="text-slate-600 dark:text-slate-400">{key}:</span>
                      <span className="text-slate-900 dark:text-slate-100">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {params.body && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Body</div>
                <pre className="text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border overflow-x-auto max-h-64 overflow-y-auto">
                  {typeof params.body === 'string' ? params.body : JSON.stringify(params.body, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Database Nodes (PostgreSQL, MySQL, etc.)
  if (nodeType.includes('postgres') || nodeType.includes('mysql') || 
      nodeType.includes('mongo') || nodeType.includes('database')) {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Database className="h-4 w-4" />
              Query Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>
              <div className="text-xs text-slate-500 mb-1">Operation</div>
              <Badge variant="outline">{params.operation || 'Select'}</Badge>
            </div>
            
            {params.query && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Query</div>
                <pre className="text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border font-mono overflow-x-auto max-h-80 overflow-y-auto">
                  {params.query}
                </pre>
              </div>
            )}
            
            {params.table && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Table</div>
                <div className="font-mono text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border">
                  {params.table}
                </div>
              </div>
            )}
            
            {params.fields && (
              <div>
                <div className="text-xs text-slate-500 mb-2">Fields</div>
                <div className="flex flex-wrap gap-1">
                  {(Array.isArray(params.fields) ? params.fields : Object.keys(params.fields)).map((field: string) => (
                    <Badge key={field} variant="secondary" className="text-xs">{field}</Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // IF / Switch / Router Nodes
  if (nodeType.includes('if') || nodeType.includes('switch') || nodeType.includes('router')) {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <GitBranch className="h-4 w-4" />
              Conditions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {nodeType.includes('if') && params.conditions && (
              <div>
                <div className="text-xs text-slate-500 mb-2">Expression</div>
                <div className="font-mono text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border">
                  {params.conditions.expression || 
                   `${params.value1 || ''} ${params.operation || '=='} ${params.value2 || ''}`}
                </div>
              </div>
            )}
            
            {nodeType.includes('switch') && params.rules && Array.isArray(params.rules) && (
              <div>
                <div className="text-xs text-slate-500 mb-2">Cases</div>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {params.rules.map((rule: any, index: number) => (
                    <div key={index} className="border border-slate-200 dark:border-slate-700 rounded p-2">
                      <div className="flex items-center justify-between mb-1">
                        <Badge variant="outline">Case {index + 1}</Badge>
                        {rule.value && (
                          <span className="text-xs text-slate-500 font-mono">{rule.value}</span>
                        )}
                      </div>
                      {rule.condition && (
                        <div className="text-xs font-mono text-slate-600 dark:text-slate-400">
                          {rule.condition}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {params.mode && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Mode</div>
                <Badge variant="outline">{params.mode}</Badge>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Code / Function Nodes
  if (nodeType.includes('code') || nodeType.includes('function') || nodeType.includes('javascript')) {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Code className="h-4 w-4" />
              Code
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {params.jsCode && (
              <div>
                <div className="text-xs text-slate-500 mb-1">JavaScript Code</div>
                <pre className="text-xs bg-slate-900 text-slate-100 p-3 rounded border overflow-x-auto max-h-96 overflow-y-auto font-mono">
                  {params.jsCode}
                </pre>
              </div>
            )}
            
            {params.language && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Language</div>
                <Badge variant="outline">{params.language}</Badge>
              </div>
            )}
            
            {params.functionCode && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Function Code</div>
                <pre className="text-xs bg-slate-900 text-slate-100 p-3 rounded border overflow-x-auto max-h-96 overflow-y-auto font-mono">
                  {params.functionCode}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Set / Transform Nodes
  if (nodeType.includes('set') || nodeType.includes('item') || nodeType.includes('transform')) {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Field Mappings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {params.assignments && Array.isArray(params.assignments) && (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {params.assignments.map((assignment: any, index: number) => (
                  <div key={index} className="border border-slate-200 dark:border-slate-700 rounded p-2">
                    <div className="flex items-center gap-2">
                      <div className="flex-1">
                        <div className="text-xs text-slate-500">Field</div>
                        <div className="font-mono text-xs">{assignment.id || assignment.name || `Field ${index + 1}`}</div>
                      </div>
                      <div className="flex-1">
                        <div className="text-xs text-slate-500">Value</div>
                        <div className="font-mono text-xs truncate">{String(assignment.value || '')}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {params.values && (
              <div>
                <div className="text-xs text-slate-500 mb-2">Values</div>
                <div className="space-y-1 max-h-80 overflow-y-auto">
                  {Object.entries(params.values).map(([key, value]) => (
                    <div key={key} className="flex justify-between text-xs bg-slate-50 dark:bg-slate-800 p-1.5 rounded">
                      <span className="font-mono text-slate-600 dark:text-slate-400">{key}:</span>
                      <span className="font-mono text-slate-900 dark:text-slate-100 truncate ml-2">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Trigger Nodes (including executeWorkflowTrigger)
  if (nodeType.includes('trigger') || nodeType.includes('webhook') || nodeType.includes('schedule') || nodeType.includes('cron')) {
    const paramEntries = Object.entries(params).filter(([key]) => !key.startsWith('_'));

    return (
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Trigger Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {params.webhookId && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Webhook ID</div>
                <div className="font-mono text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border">
                  {params.webhookId}
                </div>
              </div>
            )}

            {params.path && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Path</div>
                <div className="font-mono text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border">
                  {params.path}
                </div>
              </div>
            )}

            {params.rule && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Schedule Rule</div>
                <div className="font-mono text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border">
                  {params.rule.expression || params.rule.cronExpression || JSON.stringify(params.rule)}
                </div>
              </div>
            )}

            {params.httpMethod && (
              <div>
                <div className="text-xs text-slate-500 mb-1">HTTP Method</div>
                <Badge variant="outline">{params.httpMethod}</Badge>
              </div>
            )}

            {/* Show all other parameters for trigger nodes like executeWorkflowTrigger */}
            {paramEntries
              .filter(([key]) => !['webhookId', 'path', 'rule', 'httpMethod'].includes(key))
              .map(([key, value]) => (
                <div key={key}>
                  <div className="text-xs text-slate-500 mb-1 capitalize">
                    {key.replace(/([A-Z])/g, ' $1')}
                  </div>
                  {typeof value === 'object' ? (
                    <pre className="text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border overflow-x-auto font-mono whitespace-pre-wrap">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  ) : (
                    <div className="font-mono text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border break-words">
                      {String(value)}
                    </div>
                  )}
                </div>
              ))}

            {/* Show message if no parameters */}
            {paramEntries.length === 0 && (
              <div className="text-xs text-slate-500 italic">
                No parameters configured
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Email Nodes
  if (nodeType.includes('email') || nodeType.includes('smtp')) {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Mail className="h-4 w-4" />
              Email Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-slate-500 mb-1">To</div>
                <div className="font-mono text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border">
                  {params.to || 'Not set'}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">From</div>
                <div className="font-mono text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border">
                  {params.from || 'Not set'}
                </div>
              </div>
            </div>
            
            {params.subject && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Subject</div>
                <div className="text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border">
                  {params.subject}
                </div>
              </div>
            )}
            
            {params.text && (
              <div>
                <div className="text-xs text-slate-500 mb-1">Body</div>
                <div className="text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border max-h-64 overflow-y-auto">
                  {params.text}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Generic fallback - show important fields in organized sections
  const importantFields = [
    'url', 'path', 'method', 'operation', 'query', 'table',
    'expression', 'condition', 'value', 'code', 'function',
    'to', 'from', 'subject', 'message', 'body'
  ];
  
  const hasImportantFields = importantFields.some(field => params[field]);
  
  if (hasImportantFields) {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Key Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {importantFields.map(field => {
              if (!params[field]) return null;
              const value = params[field];
              
              return (
                <div key={field}>
                  <div className="text-xs text-slate-500 mb-1 capitalize">{field.replace(/([A-Z])/g, ' $1')}</div>
                  {typeof value === 'object' ? (
                    <pre className="text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border overflow-x-auto max-h-64 overflow-y-auto">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  ) : (
                    <div className="font-mono text-xs bg-slate-50 dark:bg-slate-800 p-2 rounded border break-words">
                      {String(value)}
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      </div>
    );
  }

  // Final fallback - organized generic view
  const paramEntries = Object.entries(params).filter(([key]) => !key.startsWith('_'));

  if (paramEntries.length === 0) {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Configuration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-slate-500 italic">
              No parameters configured
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-xs space-y-2">
            {paramEntries.map(([key, value]) => (
              <div key={key} className="border-b border-slate-100 dark:border-slate-800 pb-2 last:border-b-0">
                <div className="font-semibold text-slate-700 dark:text-slate-300 mb-1 capitalize">
                  {key.replace(/([A-Z])/g, ' $1')}
                </div>
                {typeof value === 'object' ? (
                  <pre className="text-xs text-slate-600 dark:text-slate-400 font-mono whitespace-pre-wrap break-words">
                    {JSON.stringify(value, null, 2)}
                  </pre>
                ) : (
                  <div className="text-xs text-slate-600 dark:text-slate-400 font-mono break-words">
                    {String(value)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}














