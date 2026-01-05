import React, { useCallback } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { useAppStore } from '@/store/use-app-store';
import { useFeatures } from '@/lib/features';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuGroup,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from '@/components/ui/dropdown-menu';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { useTheme } from '@/components/ThemeProvider';
import {
  LayoutDashboard,
  LayoutGrid,
  Server,
  Workflow,
  ListChecks,
  Activity,
  Users,
  UserCog,
  CreditCard,
  LogOut,
  Menu,
  X,
  Building2,
  Shield,
  BarChart3,
  Settings,
  Bell,
  Sparkles,
  UserCircle,
  Key,
  HelpCircle,
  Palette,
  ChevronDown,
  ChevronUp,
  Search,
  PanelLeftClose,
  PanelLeftOpen,
  History,
  Table,
  Camera,
  GitBranch,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { canSeePlatformNav, isAtLeastPlan, mapBackendRoleToFrontendRole, normalizePlan, type Plan, type Role } from '@/lib/permissions';
import { useHealthCheck } from '@/lib/use-health-check';

interface NavItem {
  id: string;
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  minPlan?: Plan; // minimum plan required to see this item
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navigationSections: NavSection[] = [
  {
    title: 'Operations',
    items: [
      { id: 'dashboard', name: 'Dashboard', href: '/', icon: LayoutDashboard },
      { id: 'environments', name: 'Environments', href: '/environments', icon: Server },
      { id: 'workflows', name: 'Workflows', href: '/workflows', icon: Workflow },
      { id: 'deployments', name: 'Deployments', href: '/deployments', icon: GitBranch, minPlan: 'pro' },
      { id: 'snapshots', name: 'Snapshots', href: '/snapshots', icon: Camera, minPlan: 'pro' },
    ],
  },
  {
    title: 'Observability',
    items: [
      { id: 'observability', name: 'Overview', href: '/observability', icon: Activity, minPlan: 'pro' },
      { id: 'executions', name: 'Executions', href: '/executions', icon: ListChecks },
      { id: 'activity', name: 'Activity', href: '/activity', icon: History },
    ],
  },
  {
    title: 'Identity & Secrets',
    items: [
      { id: 'credentials', name: 'Credentials', href: '/credentials', icon: Key },
      { id: 'n8nUsers', name: 'n8n Users', href: '/n8n-users', icon: UserCog, minPlan: 'pro' },
    ],
  },
  {
    title: 'Admin',
    items: [
      // Admin Dashboard - Pro/Agency/Enterprise only (insight-first control plane)
      { id: 'adminDashboard', name: 'Admin Dashboard', href: '/admin', icon: LayoutGrid, minPlan: 'pro' },
      { id: 'members', name: 'Members', href: '/admin/members', icon: Users },
      { id: 'usage', name: 'Usage', href: '/admin/usage', icon: BarChart3, minPlan: 'pro' },
      { id: 'providers', name: 'Billing & Plans', href: '/admin/providers', icon: CreditCard },
      { id: 'credentialHealth', name: 'Credential Health', href: '/admin/credential-health', icon: Shield, minPlan: 'pro' },
      { id: 'settings', name: 'Settings', href: '/admin/settings', icon: Settings },
    ],
  },
  {
    title: 'Platform',
    items: [
      { id: 'platformDashboard', name: 'Platform Dashboard', href: '/platform', icon: LayoutGrid },
      { id: 'platformTenants', name: 'Tenants', href: '/platform/tenants', icon: Building2 },
      { id: 'platformConsole', name: 'Support', href: '/platform/support', icon: HelpCircle },
      { id: 'platformFeatureMatrix', name: 'Feature Matrix', href: '/platform/feature-matrix', icon: Table },
      { id: 'platformEntitlements', name: 'Entitlements', href: '/platform/entitlements', icon: LayoutGrid },
      { id: 'platformOverrides', name: 'Tenant Overrides', href: '/platform/tenant-overrides', icon: Shield },
      { id: 'platformEntitlementsAudit', name: 'Entitlements Audit', href: '/platform/entitlements-audit', icon: History },
      { id: 'platformAdmins', name: 'Platform Admins', href: '/platform/admins', icon: Shield },
      { id: 'platformSettings', name: 'Settings', href: '/platform/settings', icon: Settings },
    ],
  },
];

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, tenant, logout, impersonating, stopImpersonating } = useAuth();
  const { sidebarOpen, toggleSidebar } = useAppStore();
  const { planName } = useFeatures();
  const { setTheme } = useTheme();
  const [searchOpen, setSearchOpen] = React.useState(false);
  
  // State for collapsible sections - default all sections to expanded
  const [expandedSections, setExpandedSections] = React.useState<Record<string, boolean>>(() => {
    const initialState: Record<string, boolean> = {};
    navigationSections.forEach((section) => {
      initialState[section.title] = true; // Default to expanded
    });
    return initialState;
  });

  // Get user's role mapped to frontend role system
  const getUserRole = useCallback((): Role => {
    if ((user as any)?.isPlatformAdmin) return 'platform_admin';
    if (!user?.role) return 'viewer';
    return mapBackendRoleToFrontendRole(user.role);
  }, [user?.role, (user as any)?.isPlatformAdmin]);

  // Health check for connection status indicator
  const { status: healthStatus } = useHealthCheck();

  const normalizedPlan = normalizePlan(planName);
  const userRole = getUserRole();
  const showPlatform = canSeePlatformNav(userRole) && !impersonating;

  const isNavItemVisible = useCallback(
    (sectionTitle: string, item: NavItem): boolean => {
      // Platform section - platform_admin only
      if (sectionTitle === 'Platform' && !showPlatform) return false;
      
      // Admin section - admin or platform_admin
      if (sectionTitle === 'Admin' && userRole !== 'admin' && userRole !== 'platform_admin') return false;
      
      // Feature Matrix - platform_admin only (requires platform admin API access)
      if (item.href === '/admin/feature-matrix' && userRole !== 'platform_admin') return false;
      
      // Operations section - viewer+ only
      if (sectionTitle === 'Operations') {
        const allowedRoles: Role[] = ['viewer', 'developer', 'admin', 'platform_admin'];
        if (!allowedRoles.includes(userRole)) return false;
      }
      
      // Identity & Secrets - admin only for credentials and n8n-users
      if (sectionTitle === 'Identity & Secrets') {
        if (item.href === '/credentials' && userRole !== 'admin') return false;
        if (item.href === '/n8n-users' && userRole !== 'admin') return false;
      }
      
      // Plan gating
      if (item.minPlan && !isAtLeastPlan(normalizedPlan, item.minPlan)) return false;
      
      return true;
    },
    [normalizedPlan, showPlatform, userRole]
  );

  // Build search items from navigation
  const searchItems = React.useMemo(() => {
    const items: Array<{ title: string; href: string; icon: React.ComponentType<{ className?: string }> }> = [];
    navigationSections.forEach((section) => {
      section.items.forEach((item) => {
        if (!isNavItemVisible(section.title, item)) return;
        items.push({ title: item.name, href: item.href, icon: item.icon });
      });
    });
    return items;
  }, [isNavItemVisible]);

  const toggleSection = (sectionTitle: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [sectionTitle]: !prev[sectionTitle],
    }));
  };

  const handleStopImpersonating = async () => {
    await stopImpersonating();
    // Refresh the page to reload data for original user
    window.location.reload();
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setSearchOpen((open) => !open);
      }
    };
    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 bg-card border-r shadow-sm transform transition-all duration-200 ease-in-out',
          'dark:bg-card/95 dark:backdrop-blur dark:supports-[backdrop-filter]:bg-card/80',
          sidebarOpen 
            ? 'w-64 translate-x-0' 
            : 'w-16 -translate-x-full lg:translate-x-0'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between h-16 px-4 border-b bg-muted/50 dark:bg-transparent relative">
            <div className={cn("flex items-center gap-2.5", !sidebarOpen && "justify-center w-full")}>
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow-sm">
                <Workflow className="h-5 w-5 text-primary-foreground" />
              </div>
              {sidebarOpen && <span className="text-lg font-semibold tracking-tight">WorkflowOps</span>}
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden h-8 w-8"
              onClick={toggleSidebar}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-2 py-4 overflow-y-auto custom-scrollbar">
            {navigationSections
              .filter((section) => {
                if (section.title === 'Platform' && !showPlatform) return false;
                if (section.title === 'Admin' && userRole !== 'admin' && userRole !== 'platform_admin') return false;
                const visibleItems = section.items.filter((item) => isNavItemVisible(section.title, item));
                return visibleItems.length > 0;
              })
              .map((section, sectionIndex) => {
              const isExpanded = expandedSections[section.title] ?? true;
              // Rename "Admin" to "Account" for Free plan users
              const displayTitle = normalizedPlan === 'free' && section.title === 'Admin' ? 'Account' : section.title;
              return (
                <div key={section.title} className={cn(sectionIndex > 0 && 'mt-6')}>
                  {sidebarOpen ? (
                    <button
                      onClick={() => toggleSection(section.title)}
                      className="w-full flex items-center justify-between px-3 py-2 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors"
                    >
                      <span>{displayTitle}</span>
                      {isExpanded ? (
                        <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                    </button>
                  ) : (
                    <div className="px-3 py-2 mb-1.5">
                      <div className="h-px bg-border" />
                    </div>
                  )}
                  {isExpanded && (
                    <div className="space-y-0.5">
                      {section.items
                        .filter((item) => isNavItemVisible(section.title, item))
                        .map((item) => {
                          const Icon = item.icon;
                          const isActive = location.pathname === item.href;
                          return (
                            <Link
                              key={item.href}
                              to={item.href}
                              className={cn(
                                'flex items-center gap-2.5 px-2.5 py-2 text-sm font-medium rounded-md transition-all duration-150',
                                isActive
                                  ? 'bg-primary text-primary-foreground shadow-sm'
                                  : 'text-foreground/70 hover:bg-accent hover:text-foreground',
                                !sidebarOpen && 'justify-center'
                              )}
                              title={!sidebarOpen ? item.name : undefined}
                            >
                              <Icon className={cn('h-4 w-4 flex-shrink-0', isActive && 'text-primary-foreground')} />
                              {sidebarOpen && <span className="flex-1">{item.name}</span>}
                            </Link>
                          );
                        })}
                    </div>
                  )}
                </div>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <div
        className={cn(
          'transition-all duration-200',
          sidebarOpen ? 'lg:pl-64' : 'lg:pl-16'
        )}
      >
        {/* Top Bar */}
        <div className="sticky top-0 z-40 h-14 bg-background border-b shadow-sm dark:bg-background/95 dark:backdrop-blur dark:supports-[backdrop-filter]:bg-background/80">
          <div className="flex items-center justify-between h-full px-4 lg:px-6">
            <div className="flex items-center gap-3 flex-1">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden h-8 w-8"
                onClick={toggleSidebar}
              >
                <Menu className="h-4 w-4" />
              </Button>
              
              <Button
                variant="ghost"
                size="icon"
                className="hidden lg:flex h-8 w-8"
                onClick={toggleSidebar}
                title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
              >
                {sidebarOpen ? (
                  <PanelLeftClose className="h-4 w-4" />
                ) : (
                  <PanelLeftOpen className="h-4 w-4" />
                )}
              </Button>
              
              {/* Search */}
              <Button
                variant="outline"
                className="relative h-9 w-full max-w-sm justify-start text-sm text-muted-foreground sm:pr-12 hidden sm:flex"
                onClick={() => setSearchOpen(true)}
              >
                <Search className="mr-2 h-4 w-4" />
                <span>Search...</span>
                <kbd className="pointer-events-none absolute right-1.5 top-1.5 hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium opacity-100 sm:flex">
                  <span className="text-xs">⌘</span>K
                </kbd>
              </Button>
            </div>

            <div className="flex items-center gap-2">
              {/* Impersonation Indicator (MANDATORY) */}
              {impersonating && (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2 px-2 py-1 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 rounded-md text-xs">
                    <span className="truncate max-w-[300px]">
                      Viewing as {user?.name || user?.email || '—'}
                      {tenant && <> ({tenant.name})</>}
                    </span>
                    <button
                      onClick={handleStopImpersonating}
                      className="hover:bg-yellow-200 dark:hover:bg-yellow-800 rounded p-0.5"
                      title="Stop impersonating"
                      aria-label="Stop impersonating"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              )}

              {/* Connection Status Indicator */}
              <div className="flex items-center gap-2 mr-2">
                <div
                  className={cn(
                    "h-2 w-2 rounded-full",
                    healthStatus === 'healthy' && "bg-green-500",
                    healthStatus === 'degraded' && "bg-yellow-500",
                    healthStatus === 'unhealthy' && "bg-red-500"
                  )}
                  title={
                    healthStatus === 'healthy' ? 'All systems operational' :
                    healthStatus === 'degraded' ? 'Some services degraded' :
                    'Service unavailable'
                  }
                />
              </div>

              {/* Notifications */}
              <Button variant="ghost" size="icon" className="h-8 w-8 relative">
                <Bell className="h-4 w-4" />
                <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-primary"></span>
              </Button>
              
              {/* User Menu */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="relative h-10 w-10 rounded-full p-0">
                    <div className="h-10 w-10 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-sm font-semibold shadow-sm">
                      {user?.name?.charAt(0).toUpperCase() || 'U'}
                    </div>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56" sideOffset={8}>
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col space-y-1">
                      <p className="text-sm font-medium leading-none">{user?.name}</p>
                      <p className="text-xs leading-none text-muted-foreground">{user?.email}</p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  
                  {/* Account Section */}
                  <DropdownMenuGroup>
                    <DropdownMenuItem asChild>
                      <Link to="/profile" className="cursor-pointer">
                        <UserCircle className="mr-2 h-4 w-4" />
                        Profile
                      </Link>
                    </DropdownMenuItem>
                    {user?.role === 'admin' && (
                      <>
                        <DropdownMenuItem asChild>
                          <Link to="/admin/providers" className="cursor-pointer">
                            <CreditCard className="mr-2 h-4 w-4" />
                            Billing & Plans
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem asChild>
                          <Link to="/admin/members" className="cursor-pointer">
                            <Users className="mr-2 h-4 w-4" />
                            Members
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem asChild>
                          <Link 
                            to="/admin/settings" 
                            className="cursor-pointer"
                            onClick={() => {
                              // #region agent log
                              fetch('http://127.0.0.1:7242/ingest/35363e7c-4fd6-4b04-adaf-3a3d3056abb3',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'AppLayout.tsx:452',message:'Settings link clicked',data:{userRole:user?.role},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
                              // #endregion
                            }}
                          >
                            <Settings className="mr-2 h-4 w-4" />
                            Settings
                          </Link>
                        </DropdownMenuItem>
                      </>
                    )}
                  </DropdownMenuGroup>
                  
                  <DropdownMenuSeparator />
                  
                  {/* Preferences Section */}
                  <DropdownMenuGroup>
                    <DropdownMenuLabel>Preferences</DropdownMenuLabel>
                    <DropdownMenuSub>
                      <DropdownMenuSubTrigger>
                        <Palette className="mr-2 h-4 w-4" />
                        Appearance
                      </DropdownMenuSubTrigger>
                      <DropdownMenuSubContent>
                        <DropdownMenuItem onClick={() => setTheme('light')}>
                          Light
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setTheme('dark')}>
                          Dark
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setTheme('system')}>
                          System
                        </DropdownMenuItem>
                      </DropdownMenuSubContent>
                    </DropdownMenuSub>
                  </DropdownMenuGroup>
                  
                  <DropdownMenuSeparator />
                  
                  <DropdownMenuItem asChild>
                    <Link to="/support" className="cursor-pointer">
                      <HelpCircle className="mr-2 h-4 w-4" />
                      Support Center
                    </Link>
                  </DropdownMenuItem>
                  
                  <DropdownMenuSeparator />
                  
                  {/* Account Actions */}
                  {planName !== 'enterprise' && (
                    <DropdownMenuItem asChild>
                      <Link to="/admin/providers" className="cursor-pointer">
                        <Sparkles className="mr-2 h-4 w-4" />
                        Upgrade Plan
                      </Link>
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
                    <LogOut className="mr-2 h-4 w-4" />
                    Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>

        {/* Command Palette */}
        <CommandDialog open={searchOpen} onOpenChange={setSearchOpen}>
          <CommandInput placeholder="Search pages, workflows, environments..." />
          <CommandList>
            <CommandEmpty>No results found.</CommandEmpty>
            <CommandGroup heading="Navigation">
              {searchItems.map((item) => {
                const Icon = item.icon;
                return (
                  <CommandItem
                    key={item.href}
                    onSelect={() => {
                      navigate(item.href);
                      setSearchOpen(false);
                    }}
                  >
                    <Icon className="mr-2 h-4 w-4" />
                    <span>{item.title}</span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </CommandDialog>

        {/* Page Content */}
        <main className="p-6 bg-muted/30 min-h-[calc(100vh-3.5rem)]">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={toggleSidebar}
        />
      )}
    </div>
  );
}
