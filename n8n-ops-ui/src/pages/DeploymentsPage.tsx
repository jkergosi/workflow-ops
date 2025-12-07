import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { mockApi } from '@/lib/mock-api';
import { api } from '@/lib/api';
import { Rocket, ArrowRight, Sparkles, Crown, Lock, GitCompare, CheckCircle, AlertTriangle, Clock } from 'lucide-react';
import { useFeatures } from '@/lib/features';
import { UpgradePrompt } from '@/components/FeatureGate';

export function DeploymentsPage() {
  const navigate = useNavigate();
  const { canUseFeature, features } = useFeatures();
  const hasPromotion = canUseFeature('environment_promotion');
  const promotionType = features?.environment_promotion;
  const isAutomated = promotionType === 'automated';

  const [promoteDialogOpen, setPromoteDialogOpen] = useState(false);
  const [sourceEnv, setSourceEnv] = useState<string>('');
  const [targetEnv, setTargetEnv] = useState<string>('');
  const [_selectedWorkflow, _setSelectedWorkflow] = useState<string>('');

  const { data: deployments, isLoading } = useQuery({
    queryKey: ['deployments'],
    queryFn: () => mockApi.getDeployments(),
  });

  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.getEnvironments(),
  });

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'success':
        return 'success';
      case 'failed':
        return 'destructive';
      case 'running':
        return 'default';
      case 'pending_approval':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  const handleStartPromotion = () => {
    setPromoteDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Deployments</h1>
          <p className="text-muted-foreground">
            Track workflow deployments and promote across environments
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasPromotion ? (
            <Button onClick={handleStartPromotion}>
              <Rocket className="h-4 w-4 mr-2" />
              Promote Workflow
            </Button>
          ) : (
            <Button variant="outline" disabled>
              <Lock className="h-4 w-4 mr-2" />
              Promote Workflow
              <Badge variant="outline" className="ml-2 gap-1">
                <Sparkles className="h-3 w-3" />
                Pro
              </Badge>
            </Button>
          )}
        </div>
      </div>

      {/* Feature gate for promotions */}
      {!hasPromotion && (
        <UpgradePrompt feature="environment_promotion" requiredPlan="pro" />
      )}

      {/* Promotions Overview - only show for Pro+ */}
      {hasPromotion && (
        <div className="grid gap-6 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Promotion Type</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                {isAutomated ? (
                  <>
                    <Crown className="h-5 w-5 text-amber-500" />
                    <span className="text-lg font-semibold">Automated</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-5 w-5 text-blue-500" />
                    <span className="text-lg font-semibold">Manual</span>
                  </>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {isAutomated
                  ? 'CI/CD integration with approval workflows'
                  : 'One-click promotion between environments'}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Pending Approvals</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-amber-500" />
                <span className="text-2xl font-bold">0</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {isAutomated
                  ? 'Workflows awaiting approval'
                  : 'Upgrade to Enterprise for approval workflows'}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">This Week</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                <span className="text-2xl font-bold">{deployments?.data?.length || 0}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Successful promotions
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Credential Remapping - Enterprise only */}
      {hasPromotion && !features?.credential_remapping && (
        <Card className="border-dashed">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Lock className="h-4 w-4 text-muted-foreground" />
              Credential Remapping
              <Badge variant="outline" className="gap-1">
                <Crown className="h-3 w-3 text-amber-500" />
                Enterprise
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Automatically remap credentials when promoting between environments.
              <Button variant="link" className="p-0 h-auto ml-1" onClick={() => navigate('/billing')}>
                Upgrade to Enterprise
              </Button>
            </p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Rocket className="h-5 w-5" />
            Deployment History
          </CardTitle>
          <CardDescription>Recent workflow deployments and promotions</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading deployments...</div>
          ) : deployments?.data?.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Rocket className="h-12 w-12 mx-auto mb-4 opacity-20" />
              <p>No deployments yet</p>
              {hasPromotion && (
                <Button variant="link" onClick={handleStartPromotion}>
                  Create your first promotion
                </Button>
              )}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Workflow</TableHead>
                  <TableHead>Environments</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Triggered By</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Duration</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deployments?.data?.map((deployment) => (
                  <TableRow key={deployment.id}>
                    <TableCell className="font-medium">{deployment.workflowName}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{deployment.sourceEnvironment}</Badge>
                        <ArrowRight className="h-3 w-3" />
                        <Badge variant="outline">{deployment.targetEnvironment}</Badge>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={getStatusVariant(deployment.status)}>
                        {deployment.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {deployment.triggeredBy}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(deployment.startedAt).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {deployment.completedAt
                        ? `${Math.round(
                            (new Date(deployment.completedAt).getTime() -
                              new Date(deployment.startedAt).getTime()) /
                              1000
                          )}s`
                        : '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Promote Workflow Dialog */}
      <Dialog open={promoteDialogOpen} onOpenChange={setPromoteDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Rocket className="h-5 w-5" />
              Promote Workflow
            </DialogTitle>
            <DialogDescription>
              Select source and target environments for promotion
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Source Environment</label>
              <Select value={sourceEnv} onValueChange={setSourceEnv}>
                <SelectTrigger>
                  <SelectValue placeholder="Select source environment" />
                </SelectTrigger>
                <SelectContent>
                  {environments?.data?.map((env) => (
                    <SelectItem key={env.id} value={env.id}>
                      {env.name} ({env.type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex justify-center">
              <ArrowRight className="h-6 w-6 text-muted-foreground" />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Target Environment</label>
              <Select value={targetEnv} onValueChange={setTargetEnv}>
                <SelectTrigger>
                  <SelectValue placeholder="Select target environment" />
                </SelectTrigger>
                <SelectContent>
                  {environments?.data
                    ?.filter((env) => env.id !== sourceEnv)
                    .map((env) => (
                      <SelectItem key={env.id} value={env.id}>
                        {env.name} ({env.type})
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>

            <div className="bg-muted p-3 rounded-md">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5" />
                <p className="text-xs text-muted-foreground">
                  This is a placeholder for the promotion feature. Full implementation coming soon.
                </p>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setPromoteDialogOpen(false)}>
              Cancel
            </Button>
            <Button disabled>
              <GitCompare className="h-4 w-4 mr-2" />
              Validate & Promote
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
