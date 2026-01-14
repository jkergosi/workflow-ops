import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import {
  AlertTriangle,
  Clock,
  Timer,
  BarChart3,
} from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { useFeatures } from '@/lib/features';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { DriftIncident } from '@/types';

export function DriftDashboardPage() {
  const { canUseFeature } = useFeatures();

  useEffect(() => {
    document.title = 'Drift Dashboard - WorkflowOps';
    return () => {
      document.title = 'WorkflowOps';
    };
  }, []);

  // Check feature access (Agency+)
  const hasDriftDashboard = canUseFeature('drift_ttl_sla');

  // Fetch all incidents
  const { data: incidentsData } = useQuery({
    queryKey: ['incidents', 'all'],
    queryFn: async () => {
      const response = await apiClient.getIncidents({
        pageSize: 100,
      });
      return response.data;
    },
    enabled: hasDriftDashboard,
  });

  // Fetch environments for lookup
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: async () => {
      const response = await apiClient.getEnvironments();
      return response.data;
    },
  });

  // Fetch stats
  const { data: stats } = useQuery({
    queryKey: ['incident-stats'],
    queryFn: async () => {
      const response = await apiClient.getIncidentStats();
      return response.data;
    },
    enabled: hasDriftDashboard,
  });

  const incidents = incidentsData?.items || [];
  const statsData = stats || { total: 0, open: 0, by_status: {} };

  // Calculate expired incidents
  const now = new Date();
  const expiredIncidents = incidents.filter((incident: DriftIncident) => {
    if (!incident.expires_at) return false;
    return new Date(incident.expires_at) < now;
  });

  // Active incidents (not closed)
  const activeIncidents = incidents.filter(
    (incident: DriftIncident) => incident.status !== 'closed'
  );

  // Calculate average resolution time (for closed incidents in last 30 days)
  const thirtyDaysAgo = new Date();
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
  const recentClosed = incidents.filter(
    (incident: DriftIncident) =>
      incident.status === 'closed' &&
      incident.closed_at &&
      new Date(incident.closed_at) >= thirtyDaysAgo
  );

  const avgResolutionTime =
    recentClosed.length > 0
      ? recentClosed.reduce((acc: number, incident: DriftIncident) => {
          if (incident.detected_at && incident.closed_at) {
            const detected = new Date(incident.detected_at);
            const closed = new Date(incident.closed_at);
            return acc + (closed.getTime() - detected.getTime());
          }
          return acc;
        }, 0) /
        recentClosed.length /
        (1000 * 60 * 60) // Convert to hours
      : 0;

  const getEnvironmentName = (envId: string) => {
    const env = environments?.find((e: any) => e.id === envId);
    return env?.name || envId.slice(0, 8);
  };

  const getTimeUntilExpiration = (expiresAt: string | null | undefined) => {
    if (!expiresAt) return null;
    const expires = new Date(expiresAt);
    if (expires < now) return 'Expired';
    return formatDistanceToNow(expires, { addSuffix: true });
  };

  if (!hasDriftDashboard) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="h-6 w-6" />
            Drift Dashboard
          </h1>
          <p className="text-muted-foreground">
            Comprehensive view of drift incidents with TTL/SLA tracking
          </p>
        </div>
        <Card>
          <CardContent className="py-12 text-center">
            <BarChart3 className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">Upgrade Required</h3>
            <p className="text-muted-foreground mb-4">
              Drift Dashboard with TTL/SLA tracking requires an Agency plan or higher.
            </p>
            <Button asChild>
              <Link to="/billing">View Plans</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="h-6 w-6" />
            Drift Dashboard
          </h1>
          <p className="text-muted-foreground">
            Comprehensive view of drift incidents with TTL/SLA tracking
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active Incidents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeIncidents.length}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {statsData.by_status?.detected || 0} detected,{' '}
              {statsData.by_status?.acknowledged || 0} acknowledged
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Expired</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">
              {expiredIncidents.length}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Action required</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Resolved (30d)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {recentClosed.length}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Closed in last 30 days
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Avg Resolution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {avgResolutionTime > 0
                ? `${Math.round(avgResolutionTime)}h`
                : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Average time to resolve
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Expired Incidents (Action Required) */}
      {expiredIncidents.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Expired Incidents (Action Required)
            </CardTitle>
            <CardDescription>
              These incidents have exceeded their TTL and may be blocking deployments
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Environment</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Detected</TableHead>
                  <TableHead>Expired</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {expiredIncidents.map((incident: DriftIncident) => {
                  const expiredAt = incident.expires_at
                    ? formatDistanceToNow(new Date(incident.expires_at), {
                        addSuffix: true,
                      })
                    : 'Unknown';
                  const detectedAt = incident.detected_at
                    ? formatDistanceToNow(new Date(incident.detected_at), {
                        addSuffix: true,
                      })
                    : 'Unknown';

                  return (
                    <TableRow key={incident.id}>
                      <TableCell>
                        <Link
                          to={`/environments/${incident.environment_id}`}
                          className="text-primary hover:underline"
                        >
                          {getEnvironmentName(incident.environment_id)}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <div className="font-medium">
                          {incident.title || 'Untitled Incident'}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {detectedAt}
                      </TableCell>
                      <TableCell>
                        <Badge variant="destructive" className="gap-1">
                          <Timer className="h-3 w-3" />
                          {expiredAt}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{incident.status}</Badge>
                      </TableCell>
                      <TableCell>
                        <Button asChild variant="outline" size="sm">
                          <Link to={`/incidents/${incident.id}`}>View</Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Active Incidents */}
      <Card>
        <CardHeader>
          <CardTitle>Active Incidents</CardTitle>
          <CardDescription>
            All non-closed drift incidents with TTL tracking
          </CardDescription>
        </CardHeader>
        <CardContent>
          {activeIncidents.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No active incidents
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Environment</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Expires In</TableHead>
                  <TableHead>Owner</TableHead>
                  <TableHead>Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeIncidents.map((incident: DriftIncident) => {
                  const expiresIn = getTimeUntilExpiration(incident.expires_at);
                  const isExpired = incident.expires_at
                    ? new Date(incident.expires_at) < now
                    : false;

                  return (
                    <TableRow key={incident.id}>
                      <TableCell>
                        <Link
                          to={`/environments/${incident.environment_id}`}
                          className="text-primary hover:underline"
                        >
                          {getEnvironmentName(incident.environment_id)}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <div className="font-medium">
                          {incident.title || 'Untitled Incident'}
                        </div>
                        {incident.severity && (
                          <Badge
                            variant="outline"
                            className="mt-1 text-xs"
                          >
                            {incident.severity.toUpperCase()}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{incident.status}</Badge>
                      </TableCell>
                      <TableCell>
                        {expiresIn ? (
                          <Badge
                            variant={isExpired ? 'destructive' : 'secondary'}
                            className="gap-1"
                          >
                            <Clock className="h-3 w-3" />
                            {expiresIn}
                          </Badge>
                        ) : (
                          <span className="text-sm text-muted-foreground">No TTL</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {incident.owner_user_id
                          ? incident.owner_user_id.slice(0, 8)
                          : '-'}
                      </TableCell>
                      <TableCell>
                        <Button asChild variant="outline" size="sm">
                          <Link to={`/incidents/${incident.id}`}>View</Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

