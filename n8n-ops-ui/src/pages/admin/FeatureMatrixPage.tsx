import { useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { toast } from 'sonner';
import type { FeatureMatrixEntry, AdminPlan } from '@/types';

export function FeatureMatrixPage() {
  useEffect(() => {
    document.title = 'Feature Matrix - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  const queryClient = useQueryClient();
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedFeature, setSelectedFeature] = useState<FeatureMatrixEntry | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<AdminPlan | null>(null);
  const [editValue, setEditValue] = useState<boolean | number>(false);
  const [editReason, setEditReason] = useState('');

  // Filter and sort state
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [planFilter, setPlanFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'name' | 'type' | 'status'>('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Fetch feature matrix
  const { data: matrixData, isLoading, refetch } = useQuery({
    queryKey: ['feature-matrix'],
    queryFn: () => apiClient.getFeatureMatrix(),
  });

  const matrix = matrixData?.data;

  // Filtered and sorted features
  const filteredAndSortedFeatures = useMemo(() => {
    if (!matrix?.features) return [];

    let filtered = [...matrix.features];

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (f) =>
          f.featureDisplayName.toLowerCase().includes(query) ||
          f.featureKey.toLowerCase().includes(query) ||
          f.description?.toLowerCase().includes(query)
      );
    }

    // Apply type filter
    if (typeFilter !== 'all') {
      filtered = filtered.filter((f) => f.featureType === typeFilter);
    }

    // Apply plan filter - show features enabled/available for selected plan
    if (planFilter !== 'all') {
      filtered = filtered.filter((f) => {
        const planValue = f.planValues[planFilter];
        // For flags, show if enabled (true)
        // For limits, show if value exists and > 0
        if (f.featureType === 'flag') {
          return planValue === true;
        } else {
          return typeof planValue === 'number' && planValue !== 0;
        }
      });
    }

    // Apply sorting
    filtered.sort((a, b) => {
      let compareA: string;
      let compareB: string;

      switch (sortBy) {
        case 'type':
          compareA = a.featureType;
          compareB = b.featureType;
          break;
        case 'status':
          compareA = a.status;
          compareB = b.status;
          break;
        case 'name':
        default:
          compareA = a.featureDisplayName;
          compareB = b.featureDisplayName;
          break;
      }

      const result = compareA.localeCompare(compareB);
      return sortOrder === 'asc' ? result : -result;
    });

    return filtered;
  }, [matrix?.features, searchQuery, typeFilter, planFilter, sortBy, sortOrder]);

  const handleSort = (column: 'name' | 'type' | 'status') => {
    if (sortBy === column) {
      // Toggle sort order
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      // New column, default to ascending
      setSortBy(column);
      setSortOrder('asc');
    }
  };

  const getSortIcon = (column: 'name' | 'type' | 'status') => {
    if (sortBy !== column) {
      return <ArrowUpDown className="h-3 w-3 ml-1 inline" />;
    }
    return sortOrder === 'asc' ? (
      <ArrowUp className="h-3 w-3 ml-1 inline" />
    ) : (
      <ArrowDown className="h-3 w-3 ml-1 inline" />
    );
  };

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

      {/* Feature Matrix Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <LayoutGrid className="h-5 w-5" />
                Feature Entitlements
              </CardTitle>
              <CardDescription>
                Click on any cell to edit the feature value for that plan
              </CardDescription>
            </div>
            <div className="text-sm text-muted-foreground">
              Showing {filteredAndSortedFeatures.length} of {matrix?.features?.length || 0} features
            </div>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap gap-3 mt-4">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search features..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="flag">Flag</SelectItem>
                <SelectItem value="limit">Limit</SelectItem>
              </SelectContent>
            </Select>
            <Select value={planFilter} onValueChange={setPlanFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="All Plans" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Plans</SelectItem>
                {[...(matrix?.plans || [])].sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0)).map((plan) => (
                  <SelectItem key={plan.id} value={plan.name}>
                    {plan.displayName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {!matrix || filteredAndSortedFeatures.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {matrix?.features?.length === 0
                ? 'No features found. Add features to the database to see them here.'
                : 'No features match your filters. Try adjusting your search or filters.'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead
                      className="w-[250px] cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('name')}
                    >
                      <div className="flex items-center">
                        Feature
                        {getSortIcon('name')}
                      </div>
                    </TableHead>
                    <TableHead
                      className="w-[80px] cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('type')}
                    >
                      <div className="flex items-center">
                        Type
                        {getSortIcon('type')}
                      </div>
                    </TableHead>
                    <TableHead
                      className="w-[80px] cursor-pointer hover:bg-muted/50"
                      onClick={() => handleSort('status')}
                    >
                      <div className="flex items-center">
                        Status
                        {getSortIcon('status')}
                      </div>
                    </TableHead>
                    {[...(matrix.plans || [])].sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0)).map((plan) => (
                      <TableHead key={plan.id} className="text-center min-w-[100px]">
                        {plan.displayName}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredAndSortedFeatures.map((feature) => (
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
                      {[...(matrix.plans || [])].sort((a, b) => (a.sortOrder || 0) - (b.sortOrder || 0)).map((plan) => (
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
