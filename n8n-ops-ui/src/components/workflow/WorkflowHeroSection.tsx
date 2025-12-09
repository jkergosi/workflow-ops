import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  ArrowLeft,
  ExternalLink,
  PlayCircle,
  PauseCircle,
  Power,
  Copy,
  GitCompare,
  ArrowUpRight,
  CheckCircle2,
  AlertCircle,
  XCircle,
  AlertTriangle,
  Clock,
  Activity,
  Shield,
  Zap,
} from 'lucide-react';
import type { Workflow, EnvironmentType, DriftAnalysisResult, ExecutionMetricsSummary } from '@/types';
import { formatNodeType, type WorkflowAnalysis } from '@/lib/workflow-analysis';

interface WorkflowHeroSectionProps {
  workflow: Workflow;
  analysis: WorkflowAnalysis;
  executionMetrics: ExecutionMetricsSummary | null;
  driftStatus: DriftAnalysisResult | null;
  environment: EnvironmentType;
  isLoadingDrift: boolean;
  onOpenInN8N: () => void;
  onDisable: () => void;
  onClone: () => void;
  onViewDiff: () => void;
  onPromote: () => void;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffMinutes = Math.floor(diffMs / (1000 * 60));

  if (diffDays > 0) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  if (diffHours > 0) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  if (diffMinutes > 0) return `${diffMinutes} min${diffMinutes > 1 ? 's' : ''} ago`;
  return 'just now';
}

export function WorkflowHeroSection({
  workflow,
  analysis,
  executionMetrics,
  driftStatus,
  environment,
  isLoadingDrift,
  onOpenInN8N,
  onDisable,
  onClone,
  onViewDiff,
  onPromote,
}: WorkflowHeroSectionProps) {
  // Determine health status
  const getHealthStatus = () => {
    const issues: string[] = [];

    // Collect all issues first
    const hasCriticalSecurity = analysis.security.level === 'critical';
    const hasWarningSecurity = analysis.security.level === 'warning';
    const hasCriticalReliability = analysis.reliability.level === 'critical';
    const hasDrift = driftStatus?.hasDrift;
    const hasHighFailureRate = executionMetrics && executionMetrics.successRate < 80;

    if (hasCriticalSecurity) issues.push('Security issues');
    if (hasWarningSecurity) issues.push('Security warnings');
    if (hasDrift) issues.push('Git drift detected');
    if (hasHighFailureRate) issues.push(`${(100 - executionMetrics!.successRate).toFixed(0)}% failure rate`);
    if (hasCriticalReliability) issues.push('Reliability issues');

    // Determine overall status
    let status: 'healthy' | 'warning' | 'critical' = 'healthy';
    if (hasCriticalSecurity || hasCriticalReliability) {
      status = 'critical';
    } else if (hasWarningSecurity || hasDrift || hasHighFailureRate) {
      status = 'warning';
    }

    return { status, issues };
  };

  const health = getHealthStatus();

  // Get top 3 recommendations
  const topRecommendations = analysis.optimizations.slice(0, 3);

  return (
    <div className="space-y-4">
      {/* Header Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/workflows">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{workflow.name}</h1>
              {workflow.active ? (
                <Badge variant="success" className="flex items-center gap-1">
                  <PlayCircle className="h-3 w-3" />
                  Active
                </Badge>
              ) : (
                <Badge variant="outline" className="flex items-center gap-1">
                  <PauseCircle className="h-3 w-3" />
                  Inactive
                </Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              {analysis.graph.nodeCount} nodes | Last modified {formatTimeAgo(workflow.updatedAt)} | {environment}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onOpenInN8N}>
            <ExternalLink className="h-4 w-4 mr-2" />
            Open in N8N
          </Button>
          <Button
            variant={workflow.active ? 'destructive' : 'default'}
            size="sm"
            onClick={onDisable}
          >
            <Power className="h-4 w-4 mr-2" />
            {workflow.active ? 'Disable' : 'Enable'}
          </Button>
        </div>
      </div>

      {/* Three Insight Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        {/* Card 1: What It Does */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Activity className="h-4 w-4 text-blue-500" />
              What It Does
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">{analysis.summary.purpose}</p>
            {analysis.summary.triggerTypes.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {analysis.summary.triggerTypes.slice(0, 2).map((trigger, i) => (
                  <Badge key={i} variant="secondary" className="text-xs">
                    {formatNodeType(trigger)}
                  </Badge>
                ))}
              </div>
            )}
            {analysis.summary.externalSystems.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {analysis.summary.externalSystems.slice(0, 3).map((sys, i) => (
                  <Badge key={i} variant="outline" className="text-xs">
                    {sys}
                  </Badge>
                ))}
                {analysis.summary.externalSystems.length > 3 && (
                  <Badge variant="outline" className="text-xs">
                    +{analysis.summary.externalSystems.length - 3} more
                  </Badge>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Card 2: Is It Healthy? */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Shield className="h-4 w-4 text-green-500" />
              Is It Healthy?
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Health Status */}
            <div className="flex items-center gap-2">
              {health.status === 'healthy' ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : health.status === 'warning' ? (
                <AlertCircle className="h-5 w-5 text-yellow-500" />
              ) : (
                <XCircle className="h-5 w-5 text-red-500" />
              )}
              <span className="font-medium capitalize">{health.status}</span>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-2 gap-2 text-sm">
              {executionMetrics && executionMetrics.totalExecutions > 0 ? (
                <>
                  <div className="flex items-center gap-1">
                    <Zap className="h-3 w-3 text-muted-foreground" />
                    <span>{executionMetrics.successRate.toFixed(0)}% success</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3 text-muted-foreground" />
                    <span>{formatDuration(executionMetrics.avgDurationMs)} avg</span>
                  </div>
                </>
              ) : (
                <div className="col-span-2 text-muted-foreground text-xs">
                  No execution data
                </div>
              )}
            </div>

            {/* Drift Status */}
            <div className="flex items-center gap-2 text-sm">
              <GitCompare className="h-3 w-3 text-muted-foreground" />
              {isLoadingDrift ? (
                <span className="text-muted-foreground">Checking drift...</span>
              ) : driftStatus?.hasDrift ? (
                <span className="text-yellow-600">Drift detected</span>
              ) : driftStatus?.notInGit ? (
                <span className="text-muted-foreground">Not in Git</span>
              ) : driftStatus?.gitConfigured === false ? (
                <span className="text-muted-foreground">Git not configured</span>
              ) : (
                <span className="text-green-600">In sync with Git</span>
              )}
            </div>

            {/* Issues List */}
            {health.issues.length > 0 && (
              <div className="text-xs text-muted-foreground">
                {health.issues.join(' | ')}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Card 3: What To Fix */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-500" />
              What To Fix
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {topRecommendations.length > 0 ? (
              topRecommendations.map((rec, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <span className="font-medium text-muted-foreground">{i + 1}.</span>
                  <div className="flex-1">
                    <span>{rec.title}</span>
                    <Badge
                      variant={
                        rec.impact === 'high' ? 'destructive' :
                        rec.impact === 'medium' ? 'warning' : 'secondary'
                      }
                      className="ml-2 text-xs"
                    >
                      {rec.impact}
                    </Badge>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex items-center gap-2 text-sm text-green-600">
                <CheckCircle2 className="h-4 w-4" />
                No issues found!
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions Bar */}
      <div className="flex items-center gap-2 pt-2">
        <span className="text-sm text-muted-foreground mr-2">Quick Actions:</span>
        {driftStatus?.hasDrift && (
          <Button variant="outline" size="sm" onClick={onViewDiff}>
            <GitCompare className="h-4 w-4 mr-2" />
            View Diff
          </Button>
        )}
        {environment === 'dev' && (
          <Button variant="outline" size="sm" onClick={onPromote}>
            <ArrowUpRight className="h-4 w-4 mr-2" />
            Promote to Staging
          </Button>
        )}
        {environment === 'staging' && (
          <Button variant="outline" size="sm" onClick={onPromote}>
            <ArrowUpRight className="h-4 w-4 mr-2" />
            Promote to Production
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={onClone}>
          <Copy className="h-4 w-4 mr-2" />
          Clone
        </Button>
      </div>
    </div>
  );
}
