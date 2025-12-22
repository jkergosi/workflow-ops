// @ts-nocheck
// TODO: Fix TypeScript errors in this file
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  History,
  RefreshCw,
  Search,
  FileText,
  Shield,
  User,
  ArrowRight,
  Check,
  X,
  AlertTriangle,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import type { FeatureConfigAudit, FeatureAccessLog, Tenant } from '@/types';

export function EntitlementsAuditPage() {
  useEffect(() => {
    document.title = 'Entitlements Audit - n8n Ops';
    return () => {
      document.title = 'n8n Ops';
    };
  }, []);

  const [activeTab, setActiveTab] = useState('config');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTenantId, setSelectedTenantId] = useState<string>('');
  const [selectedFeatureKey, setSelectedFeatureKey] = useState<string>('');
  const [selectedResult, setSelectedResult] = useState<string>('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  // Fetch tenants for filter
  const { data: tenantsData } = useQuery({
    queryKey: ['tenants'],
    queryFn: () => apiClient.getTenants(),
  });

  // Fetch features for filter
  const { data: featuresData } = useQuery({
    queryKey: ['admin-features'],
    queryFn: () => apiClient.getAdminFeatures(),
  });

  // Fetch config audits
  const {
    data: configAuditsData,
    isLoading: configLoading,
    refetch: refetchConfig,
  } = useQuery({
    queryKey: ['feature-config-audits', selectedTenantId, selectedFeatureKey, page],
    queryFn: () =>
      apiClient.getFeatureConfigAudits({
        tenantId: selectedTenantId || undefined,
        featureKey: selectedFeatureKey || undefined,
        page,
        pageSize,
      }),
  });

  // Fetch access logs
  const {
    data: accessLogsData,
    isLoading: accessLoading,
    refetch: refetchAccess,
  } = useQuery({
    queryKey: ['feature-access-logs', selectedTenantId, selectedFeatureKey, selectedResult, page],
    queryFn: () =>
      apiClient.getFeatureAccessLogs({
        tenantId: selectedTenantId || undefined,
        featureKey: selectedFeatureKey || undefined,
        result: selectedResult || undefined,
        page,
        pageSize,
      }),
  });

  const tenants = tenantsData?.data?.tenants || [];
  const features = featuresData?.data?.features || [];
  const configAudits = configAuditsData?.data?.audits || [];
  const configTotal = configAuditsData?.data?.total || 0;
  const accessLogs = accessLogsData?.data?.logs || [];
  const accessTotal = accessLogsData?.data?.total || 0;

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const _formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'create':
        return <Badge variant="default">Create</Badge>;
      case 'update':
        return <Badge variant="secondary">Update</Badge>;
      case 'delete':
        return <Badge variant="destructive">Delete</Badge>;
      default:
        return <Badge variant="outline">{action}</Badge>;
    }
  };

  const getResultBadge = (result: string) => {
    switch (result) {
      case 'allowed':
        return (
          <Badge variant="default" className="flex items-center gap-1">
            <Check className="h-3 w-3" />
            Allowed
          </Badge>
        );
      case 'denied':
        return (
          <Badge variant="destructive" className="flex items-center gap-1">
            <X className="h-3 w-3" />
            Denied
          </Badge>
        );
      case 'limit_exceeded':
        return (
          <Badge variant="destructive" className="flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            Limit Exceeded
          </Badge>
        );
      default:
        return <Badge variant="outline">{result}</Badge>;
    }
  };

  const getEntityTypeBadge = (entityType: string) => {
    switch (entityType) {
      case 'plan_feature':
        return <Badge variant="outline">Plan Feature</Badge>;
      case 'tenant_plan':
        return <Badge variant="outline">Tenant Plan</Badge>;
      case 'tenant_override':
        return <Badge variant="outline">Tenant Override</Badge>;
      default:
        return <Badge variant="outline">{entityType}</Badge>;
    }
  };

  const renderValueDiff = (oldValue: any, newValue: any) => {
    const formatValue = (val: any) => {
      if (val === null || val === undefined) return '-';
      if (typeof val === 'object') {
        if (val.enabled !== undefined) return val.enabled ? 'Enabled' : 'Disabled';
        if (val.value !== undefined) {
          const v = val.value;
          return v === -1 || v >= 9999 ? 'Unlimited' : String(v);
        }
        return JSON.stringify(val);
      }
      return String(val);
    };

    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">{formatValue(oldValue)}</span>
        <ArrowRight className="h-3 w-3" />
        <span className="font-medium">{formatValue(newValue)}</span>
      </div>
    );
  };

  const handleRefresh = () => {
    if (activeTab === 'config') {
      refetchConfig();
    } else {
      refetchAccess();
    }
  };

  const handleClearFilters = () => {
    setSelectedTenantId('');
    setSelectedFeatureKey('');
    setSelectedResult('');
    setSearchTerm('');
    setPage(1);
  };

  const filteredConfigAudits = configAudits.filter((audit: FeatureConfigAudit) =>
    audit.featureKey?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    audit.reason?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    audit.changedByEmail?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredAccessLogs = accessLogs.filter((log: FeatureAccessLog) =>
    log.featureKey?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    log.userEmail?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    log.endpoint?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const totalPages = Math.ceil(
    (activeTab === 'config' ? configTotal : accessTotal) / pageSize
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Entitlements Audit</h1>
          <p className="text-muted-foreground">
            View configuration changes and access logs for feature entitlements
          </p>
        </div>
        <Button variant="outline" onClick={handleRefresh}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="w-48">
              <Select value={selectedTenantId || 'all'} onValueChange={(v) => setSelectedTenantId(v === 'all' ? '' : v)}>
                <SelectTrigger>
                  <SelectValue placeholder="All Tenants" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Tenants</SelectItem>
                  {tenants.map((tenant: Tenant) => (
                    <SelectItem key={tenant.id} value={tenant.id}>
                      {tenant.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-48">
              <Select value={selectedFeatureKey || 'all'} onValueChange={(v) => setSelectedFeatureKey(v === 'all' ? '' : v)}>
                <SelectTrigger>
                  <SelectValue placeholder="All Features" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Features</SelectItem>
                  {features.map((feature: any) => (
                    <SelectItem key={feature.id} value={feature.key}>
                      {feature.displayName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {activeTab === 'access' && (
              <div className="w-40">
                <Select value={selectedResult || 'all'} onValueChange={(v) => setSelectedResult(v === 'all' ? '' : v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="All Results" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Results</SelectItem>
                    <SelectItem value="allowed">Allowed</SelectItem>
                    <SelectItem value="denied">Denied</SelectItem>
                    <SelectItem value="limit_exceeded">Limit Exceeded</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9"
              />
            </div>
            <Button variant="outline" onClick={handleClearFilters}>
              Clear Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="config" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Config Changes ({configTotal})
          </TabsTrigger>
          <TabsTrigger value="access" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Access Logs ({accessTotal})
          </TabsTrigger>
        </TabsList>

        {/* Config Changes Tab */}
        <TabsContent value="config">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                Configuration Audit Log
              </CardTitle>
              <CardDescription>
                Track all changes to feature configurations, plan assignments, and overrides
              </CardDescription>
            </CardHeader>
            <CardContent>
              {configLoading ? (
                <div className="text-center py-8">Loading audit logs...</div>
              ) : filteredConfigAudits.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No configuration changes found
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Entity Type</TableHead>
                      <TableHead>Feature</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Value Change</TableHead>
                      <TableHead>Changed By</TableHead>
                      <TableHead>Reason</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredConfigAudits.map((audit: FeatureConfigAudit) => (
                      <TableRow key={audit.id}>
                        <TableCell className="text-sm">
                          {formatDateTime(audit.changedAt)}
                        </TableCell>
                        <TableCell>{getEntityTypeBadge(audit.entityType)}</TableCell>
                        <TableCell>
                          {audit.featureKey ? (
                            <span className="font-mono text-xs">{audit.featureKey}</span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>{getActionBadge(audit.action)}</TableCell>
                        <TableCell>
                          {renderValueDiff(audit.oldValue, audit.newValue)}
                        </TableCell>
                        <TableCell>
                          {audit.changedByEmail ? (
                            <div className="flex items-center gap-1 text-sm">
                              <User className="h-3 w-3" />
                              {audit.changedByEmail}
                            </div>
                          ) : (
                            <span className="text-muted-foreground">System</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <span className="text-sm text-muted-foreground max-w-[200px] truncate block">
                            {audit.reason || '-'}
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Access Logs Tab */}
        <TabsContent value="access">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Feature Access Log
              </CardTitle>
              <CardDescription>
                Track all feature access checks, including allowed and denied requests
              </CardDescription>
            </CardHeader>
            <CardContent>
              {accessLoading ? (
                <div className="text-center py-8">Loading access logs...</div>
              ) : filteredAccessLogs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No access logs found
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Feature</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Result</TableHead>
                      <TableHead>Usage</TableHead>
                      <TableHead>Endpoint</TableHead>
                      <TableHead>User</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredAccessLogs.map((log: FeatureAccessLog) => (
                      <TableRow key={log.id}>
                        <TableCell className="text-sm">
                          {formatDateTime(log.accessedAt)}
                        </TableCell>
                        <TableCell>
                          <span className="font-mono text-xs">{log.featureKey}</span>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">
                            {log.accessType === 'flag_check' ? 'Flag' : 'Limit'}
                          </Badge>
                        </TableCell>
                        <TableCell>{getResultBadge(log.result)}</TableCell>
                        <TableCell>
                          {log.limitValue !== null && log.limitValue !== undefined ? (
                            <span className="text-sm">
                              {log.currentValue ?? 0} / {log.limitValue === -1 ? '∞' : log.limitValue}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {log.endpoint ? (
                            <span className="font-mono text-xs truncate max-w-[200px] block">
                              {log.endpoint}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {log.userEmail ? (
                            <div className="flex items-center gap-1 text-sm">
                              <User className="h-3 w-3" />
                              {log.userEmail}
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages} ({activeTab === 'config' ? configTotal : accessTotal} total)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
