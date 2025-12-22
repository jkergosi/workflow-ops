import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  LayoutGrid,
  RefreshCw,
  Check,
  X,
  Edit,
  Info,
  Trash2,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import type { FeatureMatrixEntry, AdminPlan } from '@/types';

export function FeatureMatrixPage() {
  useEffect(() => {
    document.title = 'Feature Matrix - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  const queryClient = useQueryClient();
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedFeature, setSelectedFeature] = useState<FeatureMatrixEntry | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<AdminPlan | null>(null);
  const [editValue, setEditValue] = useState<boolean | number>(false);
  const [editReason, setEditReason] = useState('');

  // Fetch feature matrix
  const { data: matrixData, isLoading, refetch } = useQuery({
    queryKey: ['feature-matrix'],
    queryFn: () => apiClient.getFeatureMatrix(),
  });

  const matrix = matrixData?.data;

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({
      planId,
      featureKey,
      value,
      reason,
    }: {
      planId: string;
      featureKey: string;
      value: Record<string, any>;
      reason?: string;
    }) => apiClient.updatePlanFeatureValue(planId, featureKey, value, reason),
    onSuccess: () => {
      toast.success('Feature value updated successfully');
      queryClient.invalidateQueries({ queryKey: ['feature-matrix'] });
      setEditDialogOpen(false);
      resetEditForm();
    },
    onError: (error: any) => {
      const message = error.response?.data?.detail || 'Failed to update feature value';
      toast.error(message);
    },
  });

  // Clear cache mutation
  const clearCacheMutation = useMutation({
    mutationFn: () => apiClient.clearEntitlementsCache(),
    onSuccess: () => {
      toast.success('Entitlements cache cleared');
    },
    onError: () => {
      toast.error('Failed to clear cache');
    },
  });

  const resetEditForm = () => {
    setSelectedFeature(null);
    setSelectedPlan(null);
    setEditValue(false);
    setEditReason('');
  };

  const handleEditClick = (feature: FeatureMatrixEntry, plan: AdminPlan) => {
    setSelectedFeature(feature);
    setSelectedPlan(plan);
    const currentValue = feature.planValues[plan.name];
    setEditValue(currentValue);
    setEditDialogOpen(true);
  };

  const handleSaveEdit = () => {
    if (!selectedFeature || !selectedPlan) return;

    const value =
      selectedFeature.featureType === 'flag'
        ? { enabled: editValue as boolean }
        : { value: editValue as number };

    updateMutation.mutate({
      planId: selectedPlan.id,
      featureKey: selectedFeature.featureKey,
      value,
      reason: editReason || undefined,
    });
  };

  const getFeatureTypeBadge = (type: string) => {
    return type === 'flag' ? (
      <Badge variant="outline" className="text-xs">Flag</Badge>
    ) : (
      <Badge variant="secondary" className="text-xs">Limit</Badge>
    );
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge variant="default" className="text-xs">Active</Badge>;
      case 'deprecated':
        return <Badge variant="destructive" className="text-xs">Deprecated</Badge>;
      case 'hidden':
        return <Badge variant="outline" className="text-xs">Hidden</Badge>;
      default:
        return null;
    }
  };

  const renderCellValue = (feature: FeatureMatrixEntry, plan: AdminPlan) => {
    const value = feature.planValues[plan.name];

    if (feature.featureType === 'flag') {
      return value ? (
        <Check className="h-4 w-4 text-green-500 mx-auto" />
      ) : (
        <X className="h-4 w-4 text-muted-foreground mx-auto" />
      );
    } else {
      // Limit type
      const numValue = value as number;
      if (numValue === -1 || numValue >= 9999) {
        return <span className="text-sm font-medium">Unlimited</span>;
      }
      return <span className="text-sm font-medium">{numValue}</span>;
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Feature Matrix</h1>
          <p className="text-muted-foreground">Loading feature matrix...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Feature Matrix</h1>
          <p className="text-muted-foreground">
            Manage feature entitlements across all plans
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => clearCacheMutation.mutate()}
            disabled={clearCacheMutation.isPending}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Clear Cache
          </Button>
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <LayoutGrid className="h-8 w-8 text-muted-foreground" />
              <div>
                <p className="text-2xl font-bold">{matrix?.totalFeatures || 0}</p>
                <p className="text-sm text-muted-foreground">Total Features</p>
              </div>
            </div>
          </CardContent>
        </Card>
        {matrix?.plans.map((plan) => (
          <Card key={plan.id}>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <Badge variant="outline" className="h-8 px-3 uppercase">
                  {plan.name.slice(0, 3)}
                </Badge>
                <div>
                  <p className="text-2xl font-bold">{plan.displayName}</p>
                  <p className="text-sm text-muted-foreground">Plan</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Feature Matrix Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <LayoutGrid className="h-5 w-5" />
            Feature Entitlements
          </CardTitle>
          <CardDescription>
            Click on any cell to edit the feature value for that plan
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!matrix || matrix.features.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No features found. Add features to the database to see them here.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[250px]">Feature</TableHead>
                    <TableHead className="w-[80px]">Type</TableHead>
                    <TableHead className="w-[80px]">Status</TableHead>
                    {matrix.plans.map((plan) => (
                      <TableHead key={plan.id} className="text-center min-w-[100px]">
                        {plan.displayName}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {matrix.features.map((feature) => (
                    <TableRow key={feature.featureId}>
                      <TableCell>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <div className="flex items-center gap-2 cursor-help">
                                <div>
                                  <p className="font-medium">{feature.featureDisplayName}</p>
                                  <p className="text-xs text-muted-foreground font-mono">
                                    {feature.featureKey}
                                  </p>
                                </div>
                                {feature.description && (
                                  <Info className="h-3 w-3 text-muted-foreground" />
                                )}
                              </div>
                            </TooltipTrigger>
                            {feature.description && (
                              <TooltipContent>
                                <p className="max-w-xs">{feature.description}</p>
                              </TooltipContent>
                            )}
                          </Tooltip>
                        </TooltipProvider>
                      </TableCell>
                      <TableCell>{getFeatureTypeBadge(feature.featureType)}</TableCell>
                      <TableCell>{getStatusBadge(feature.status)}</TableCell>
                      {matrix.plans.map((plan) => (
                        <TableCell
                          key={plan.id}
                          className="text-center cursor-pointer hover:bg-muted/50 transition-colors"
                          onClick={() => handleEditClick(feature, plan)}
                        >
                          <div className="flex items-center justify-center gap-1 group">
                            {renderCellValue(feature, plan)}
                            <Edit className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                          </div>
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Feature Value</DialogTitle>
            <DialogDescription>
              Update {selectedFeature?.featureDisplayName} for {selectedPlan?.displayName} plan
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="p-3 bg-muted rounded-lg">
              <p className="text-sm font-medium">{selectedFeature?.featureDisplayName}</p>
              <p className="text-xs text-muted-foreground font-mono">
                {selectedFeature?.featureKey}
              </p>
              {selectedFeature?.description && (
                <p className="text-xs text-muted-foreground mt-1">
                  {selectedFeature.description}
                </p>
              )}
            </div>

            {selectedFeature?.featureType === 'flag' ? (
              <div className="flex items-center justify-between">
                <Label htmlFor="flag-value">Enabled</Label>
                <Switch
                  id="flag-value"
                  checked={editValue as boolean}
                  onCheckedChange={(checked) => setEditValue(checked)}
                />
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="limit-value">Limit Value</Label>
                <Input
                  id="limit-value"
                  type="number"
                  min={-1}
                  value={editValue as number}
                  onChange={(e) => setEditValue(parseInt(e.target.value, 10) || 0)}
                  placeholder="Enter limit (-1 for unlimited)"
                />
                <p className="text-xs text-muted-foreground">
                  Use -1 for unlimited
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="reason">Reason (optional)</Label>
              <Input
                id="reason"
                value={editReason}
                onChange={(e) => setEditReason(e.target.value)}
                placeholder="Why is this change being made?"
              />
              <p className="text-xs text-muted-foreground">
                This will be recorded in the audit log
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveEdit} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
