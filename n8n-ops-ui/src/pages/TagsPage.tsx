import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { api } from '@/lib/api';
import { useAppStore } from '@/store/use-app-store';
import { Search, ArrowUpDown, ArrowUp, ArrowDown, X, Tag as TagIcon, Calendar, Download, RefreshCw } from 'lucide-react';
import type { EnvironmentType } from '@/types';
import { toast } from 'sonner';

type SortField = 'name' | 'createdAt' | 'updatedAt';
type SortDirection = 'asc' | 'desc';

export function TagsPage() {
  const selectedEnvironment = useAppStore((state) => state.selectedEnvironment);
  const setSelectedEnvironment = useAppStore((state) => state.setSelectedEnvironment);
  const queryClient = useQueryClient();

  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [isSyncing, setIsSyncing] = useState(false);

  // Fetch environments to get environment ID
  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => api.getEnvironments(),
  });

  // Get current environment ID
  const currentEnvironmentId = useMemo(() => {
    if (!environments?.data) return undefined;
    const env = environments.data.find((e) => e.type === selectedEnvironment);
    return env?.id;
  }, [environments, selectedEnvironment]);

  // Fetch tags from database
  const { data: tags, isLoading, refetch } = useQuery({
    queryKey: ['tags', currentEnvironmentId],
    queryFn: async () => {
      if (!currentEnvironmentId) return { data: [] };
      return api.getTags(currentEnvironmentId);
    },
    enabled: !!currentEnvironmentId,
  });

  // Sync mutation to refresh from N8N (tags only)
  const syncMutation = useMutation({
    mutationFn: async () => {
      const envsToSync = environments?.data?.filter((env: any) =>
        selectedEnvironment === 'dev' || env.type === selectedEnvironment
      ) || [];

      const results = [];
      for (const env of envsToSync) {
        const result = await api.syncTagsOnly(env.id);
        results.push({ env: env.name, ...result.data });
      }
      return results;
    },
    onSuccess: (results) => {
      setIsSyncing(false);
      const totalTags = results.reduce((sum, r) => sum + (r.synced || 0), 0);
      toast.success(`Synced ${totalTags} tags from N8N`);
      queryClient.invalidateQueries({ queryKey: ['tags'] });
    },
    onError: (error: any) => {
      setIsSyncing(false);
      const message = error.response?.data?.detail || 'Failed to sync from N8N';
      toast.error(message);
    },
  });

  const handleSyncFromN8N = () => {
    toast.info('Syncing from N8N...');
    setIsSyncing(true);
    syncMutation.mutate();
  };

  // Filter and sort tags
  const filteredAndSortedTags = useMemo(() => {
    if (!tags?.data) return [];

    let result = [...tags.data];

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter((tag) => {
        const matchesName = tag.name.toLowerCase().includes(query);
        return matchesName;
      });
    }

    // Apply sorting
    result.sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (sortField) {
        case 'name':
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
          break;
        case 'createdAt':
          aValue = a.createdAt ? new Date(a.createdAt).getTime() : 0;
          bValue = b.createdAt ? new Date(b.createdAt).getTime() : 0;
          break;
        case 'updatedAt':
          aValue = a.updatedAt ? new Date(a.updatedAt).getTime() : 0;
          bValue = b.updatedAt ? new Date(b.updatedAt).getTime() : 0;
          break;
        default:
          return 0;
      }

      if (aValue < bValue) return sortDirection === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return result;
  }, [tags, searchQuery, sortField, sortDirection]);

  // Pagination calculations
  const { paginatedTags, totalPages, totalTags } = useMemo(() => {
    const total = filteredAndSortedTags.length;
    const pages = Math.ceil(total / pageSize);
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    const paginated = filteredAndSortedTags.slice(startIndex, endIndex);

    return {
      paginatedTags: paginated,
      totalPages: pages,
      totalTags: total,
    };
  }, [filteredAndSortedTags, currentPage, pageSize]);

  // Reset to page 1 when filters change
  const resetPage = () => {
    if (currentPage !== 1) {
      setCurrentPage(1);
    }
  };

  // Reset page when search or environment changes
  useEffect(() => {
    resetPage();
  }, [searchQuery, selectedEnvironment]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="h-3 w-3 ml-1 inline opacity-30" />;
    }
    return sortDirection === 'asc' ? (
      <ArrowUp className="h-3 w-3 ml-1 inline" />
    ) : (
      <ArrowDown className="h-3 w-3 ml-1 inline" />
    );
  };

  const clearFilters = () => {
    setSearchQuery('');
  };

  const hasActiveFilters = searchQuery;

  const formatDate = (dateString?: string) => {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(date);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Tags</h1>
          <p className="text-muted-foreground">
            View and manage workflow tags from n8n
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => refetch()} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button
            onClick={handleSyncFromN8N}
            variant="default"
            size="sm"
            disabled={isSyncing}
          >
            <Download className={`h-4 w-4 mr-2 ${isSyncing ? 'animate-spin' : ''}`} />
            Sync from N8N
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Search Filter */}
            <div className="space-y-2">
              <Label htmlFor="search">Search</Label>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="search"
                  placeholder="Search by tag name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>

            {/* Environment Filter */}
            <div className="space-y-2">
              <Label htmlFor="environment">Environment</Label>
              <select
                id="environment"
                value={selectedEnvironment}
                onChange={(e) => setSelectedEnvironment(e.target.value as EnvironmentType)}
                className="flex h-9 w-full rounded-md border border-input bg-background text-foreground px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <option value="dev">Development</option>
                <option value="staging">Staging</option>
                <option value="production">Production</option>
              </select>
            </div>
          </div>

          {hasActiveFilters && (
            <div className="mt-4 flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {totalTags} tag{totalTags !== 1 ? 's' : ''} found
              </span>
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="h-3 w-3 mr-1" />
                Clear filters
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tags in {selectedEnvironment}</CardTitle>
          <CardDescription>
            View all tags available in the selected environment
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">Loading tags...</div>
          ) : totalTags === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {hasActiveFilters ? 'No tags match your filters' : 'No tags found'}
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('name')}>
                      Tag Name {getSortIcon('name')}
                    </TableHead>
                    <TableHead>Tag ID</TableHead>
                    <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('createdAt')}>
                      Created {getSortIcon('createdAt')}
                    </TableHead>
                    <TableHead className="cursor-pointer hover:bg-muted/50" onClick={() => handleSort('updatedAt')}>
                      Last Updated {getSortIcon('updatedAt')}
                    </TableHead>
                    <TableHead>Last Synced</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {paginatedTags.map((tag) => (
                    <TableRow key={tag.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <TagIcon className="h-4 w-4 text-muted-foreground" />
                          <Badge variant="secondary">{tag.name}</Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground font-mono">
                        {tag.tagId}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(tag.createdAt)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(tag.updatedAt)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        <div className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {formatDate(tag.lastSyncedAt)}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination Controls */}
              <div className="mt-4 flex items-center justify-between border-t pt-4">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="pageSize" className="text-sm text-muted-foreground">
                      Rows per page:
                    </Label>
                    <select
                      id="pageSize"
                      value={pageSize}
                      onChange={(e) => {
                        setPageSize(Number(e.target.value));
                        setCurrentPage(1);
                      }}
                      className="h-8 w-20 rounded-md border border-input bg-background text-foreground px-2 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    >
                      <option value={10}>10</option>
                      <option value={25}>25</option>
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                    </select>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, totalTags)} of {totalTags} tags
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                  >
                    First
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(currentPage - 1)}
                    disabled={currentPage === 1}
                  >
                    Previous
                  </Button>
                  <div className="flex items-center gap-1">
                    <span className="text-sm">
                      Page {currentPage} of {totalPages}
                    </span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(currentPage + 1)}
                    disabled={currentPage === totalPages}
                  >
                    Next
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage === totalPages}
                  >
                    Last
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
