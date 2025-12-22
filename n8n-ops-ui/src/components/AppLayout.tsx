import React, { useCallback } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { useAppStore } from '@/store/use-app-store';
import { useFeatures, type PlanFeatures } from '@/lib/features';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
import { ThemeToggle } from '@/components/ThemeToggle';
import { useTheme } from '@/components/ThemeProvider';
import { ProviderSelector } from '@/components/ProviderSelector';
import {
  LayoutDashboard,
  LayoutGrid,
  Server,
  Workflow,
  ListChecks,
  Camera,
  Rocket,
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
  FileText,
  Bell,
  Sparkles,
  Crown,
  UserCircle,
  Key,
  HelpCircle,
  Palette,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Search,
  PanelLeftClose,
  PanelLeftOpen,
  History,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { isMenuItemVisible, mapBackendRoleToFrontendRole, type Role } from '@/lib/permissions';

interface NavItem {
  id: string;
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  requiredPlan?: 'pro' | 'agency' | 'enterprise';
  feature?: keyof PlanFeatures | string;
  comingSoon?: boolean;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navigationSections: NavSection[] = [
  {
    title: 'N8N Ops',
    items: [
      { id: 'dashboard', name: 'Dashboard', href: '/', icon: LayoutDashboard },
      { id: 'environments', name: 'Environments', href: '/environments', icon: Server },
      { id: 'workflows', name: 'Workflows', href: '/workflows', icon: Workflow },
      { id: 'executions', name: 'Executions', href: '/executions', icon: ListChecks },
    ],
  },
  {
    title: 'Operations',
    items: [
      { id: 'deployments', name: 'Deployments', href: '/deployments', icon: Rocket, requiredPlan: 'pro', feature: 'workflow_ci_cd' },
      { id: 'snapshots', name: 'Snapshots', href: '/snapshots', icon: Camera, feature: 'snapshots_enabled' },
    ],
  },
  {
    title: 'Observability',
    items: [
      { id: 'observability', name: 'Observability', href: '/observability', icon: Activity, feature: 'observability_basic' },
      { id: 'alerts', name: 'Alerts', href: '/alerts', icon: Bell, requiredPlan: 'pro', feature: 'observability_alerts' },
    ],
  },
  {
    title: 'Identity & Secrets',
    items: [
      { id: 'credentials', name: 'Credentials', href: '/credentials', icon: Key },
      { id: 'users', name: 'n8n Users', href: '/n8n-users', icon: UserCog },
    ],
  },
  {
    title: 'Support',
    items: [
      { id: 'support', name: 'Support', href: '/support', icon: HelpCircle },
    ],
  },
  {
    title: 'Admin',
    items: [
      { id: 'tenants', name: 'Tenants', href: '/admin/tenants', icon: Building2, requiredPlan: 'enterprise' },
      { id: 'plans', name: 'Plans', href: '/admin/plans', icon: CreditCard, requiredPlan: 'enterprise' },
      { id: 'usage', name: 'Usage & Limits', href: '/admin/usage', icon: BarChart3, requiredPlan: 'enterprise' },
      { id: 'billing', name: 'System Billing', href: '/admin/billing', icon: CreditCard, requiredPlan: 'enterprise' },
      { id: 'credentialHealth', name: 'Credential Health', href: '/admin/credential-health', icon: Shield, requiredPlan: 'enterprise' },
      { id: 'featureMatrix', name: 'Feature Matrix', href: '/admin/entitlements/matrix', icon: LayoutGrid, requiredPlan: 'enterprise' },
      { id: 'tenantOverrides', name: 'Tenant Overrides', href: '/admin/entitlements/overrides', icon: Shield, requiredPlan: 'enterprise' },
      { id: 'entitlementsAudit', name: 'Entitlements Audit', href: '/admin/entitlements/audit', icon: History, requiredPlan: 'enterprise' },
      { id: 'auditLogs', name: 'Audit Logs', href: '/admin/audit-logs', icon: FileText, requiredPlan: 'pro', feature: 'audit_logs_enabled' },
      { id: 'security', name: 'Security', href: '/admin/security', icon: Shield, requiredPlan: 'enterprise', feature: 'sso_saml' },
      { id: 'systemSettings', name: 'System Settings', href: '/admin/settings', icon: Settings },
      { id: 'supportConfig', name: 'Support Config', href: '/admin/support-config', icon: HelpCircle },
    ],
  },
];

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, availableUsers, loginAs } = useAuth();
  const { sidebarOpen, toggleSidebar } = useAppStore();
  const { canUseFeature, planName } = useFeatures();
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
    if (!user?.role) return 'user';
    return mapBackendRoleToFrontendRole(user.role);
  }, [user?.role]);

  // Check if a nav item is accessible based on plan
  const isFeatureAvailable = useCallback((item: NavItem): boolean => {
    if (!item.feature) return true;
    return canUseFeature(item.feature);
  }, [canUseFeature]);

  // Build search items from navigation
  const searchItems = React.useMemo(() => {
    const items: Array<{ title: string; href: string; icon: React.ComponentType<{ className?: string }> }> = [];
    const userRole = getUserRole();
    navigationSections.forEach((section) => {
      section.items.forEach((item) => {
        if (isMenuItemVisible(item.id, userRole) && isFeatureAvailable(item)) {
          items.push({ title: item.name, href: item.href, icon: item.icon });
        }
      });
    });
    return items;
  }, [getUserRole, isFeatureAvailable]);

  const toggleSection = (sectionTitle: string) => {
    setExpandedSections((prev) => ({
      ...prev,
      [sectionTitle]: !prev[sectionTitle],
    }));
  };

  const handleUserSwitch = async (userId: string) => {
    await loginAs(userId);
    // Refresh the page to reload data for new user
    window.location.reload();
  };

  const handleLogout = () => {
    logout();
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
          'fixed inset-y-0 left-0 z-50 bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80 border-r transform transition-all duration-200 ease-in-out',
          sidebarOpen 
            ? 'w-64 translate-x-0' 
            : 'w-16 -translate-x-full lg:translate-x-0'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between h-16 px-4 border-b relative">
            <div className={cn("flex items-center gap-2.5", !sidebarOpen && "justify-center w-full")}>
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow-sm">
                <Workflow className="h-5 w-5 text-primary-foreground" />
              </div>
              {sidebarOpen && <span className="text-lg font-semibold tracking-tight">N8N Ops</span>}
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
            {navigationSections.map((section, sectionIndex) => {
              const isExpanded = expandedSections[section.title] ?? true;
              return (
                <div key={section.title} className={cn(sectionIndex > 0 && 'mt-6')}>
                  {sidebarOpen ? (
                    <button
                      onClick={() => toggleSection(section.title)}
                      className="w-full flex items-center justify-between px-3 py-2 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors"
                    >
                      <span>{section.title}</span>
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
                        .filter((item) => isMenuItemVisible(item.id, getUserRole()))
                        .map((item) => {
                          const Icon = item.icon;
                          const isActive = location.pathname === item.href;
                          const isAvailable = isFeatureAvailable(item);
                          return (
                            <Link
                              key={item.href}
                              to={item.href}
                              className={cn(
                                'flex items-center gap-2.5 px-2.5 py-2 text-sm font-medium rounded-md transition-all duration-150',
                                isActive
                                  ? 'bg-primary text-primary-foreground shadow-sm'
                                  : 'text-foreground/70 hover:bg-accent hover:text-foreground',
                                !isAvailable && 'opacity-50',
                                !sidebarOpen && 'justify-center'
                              )}
                              title={!sidebarOpen ? item.name : undefined}
                            >
                              <Icon className={cn('h-4 w-4 flex-shrink-0', isActive && 'text-primary-foreground')} />
                              {sidebarOpen && <span className="flex-1">{item.name}</span>}
                              {sidebarOpen && !isAvailable && item.requiredPlan && (
                                <span className="flex items-center">
                                  {item.requiredPlan === 'enterprise' ? (
                                    <Crown className="h-3 w-3 text-amber-500" />
                                  ) : (
                                    <Sparkles className="h-3 w-3 text-blue-500" />
                                  )}
                                </span>
                              )}
                            </Link>
                          );
                        })}
                    </div>
                  )}
                </div>
              );
            })}
          </nav>

          {/* User Info & Menu */}
          {sidebarOpen && (
            <div className="p-3 border-t">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md hover:bg-accent transition-colors text-left">
                    <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-sm font-semibold shadow-sm">
                      {user?.name?.charAt(0).toUpperCase() || 'U'}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{user?.name}</p>
                      <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                    </div>
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                  </button>
                </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56" side="right" sideOffset={8}>
                {/* Account Section */}
                <DropdownMenuGroup>
                  <DropdownMenuLabel>Account</DropdownMenuLabel>
                  <DropdownMenuItem asChild>
                    <Link to="/profile" className="cursor-pointer">
                      <UserCircle className="mr-2 h-4 w-4" />
                      Profile
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/billing" className="cursor-pointer">
                      <CreditCard className="mr-2 h-4 w-4" />
                      Subscription
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link to="/team" className="cursor-pointer">
                      <Users className="mr-2 h-4 w-4" />
                      Team
                    </Link>
                  </DropdownMenuItem>
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
                
                {/* Help Section */}
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    <HelpCircle className="mr-2 h-4 w-4" />
                    Help
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent>
                    <DropdownMenuItem asChild>
                      <Link to="/help" className="cursor-pointer">
                        Help Center
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <a href="https://docs.n8n-ops.com" target="_blank" rel="noopener noreferrer" className="cursor-pointer">
                        Documentation
                      </a>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link to="/report-bug" className="cursor-pointer">
                        Report Bug
                      </Link>
                    </DropdownMenuItem>
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
                
                <DropdownMenuSeparator />
                
                {/* Account Actions */}
                {planName !== 'enterprise' && (
                  <DropdownMenuItem asChild>
                    <Link to="/billing" className="cursor-pointer">
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
          )}
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
        <div className="sticky top-0 z-40 h-14 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 border-b">
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
              {/* Dev User Switcher */}
              {availableUsers.length > 0 && (
                <div className="hidden md:flex items-center gap-2">
                  <Select value={user?.id} onValueChange={handleUserSwitch}>
                    <SelectTrigger className="w-[180px] h-8 text-xs">
                      <SelectValue placeholder="Select user" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableUsers.map((u) => (
                        <SelectItem key={u.id} value={u.id}>
                          {u.name} ({u.email})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Provider Selector */}
              <ProviderSelector />

              <Badge variant="outline" className="hidden sm:flex text-xs h-7">
                Environment: <span className="ml-1 font-semibold">dev</span>
              </Badge>
              
              {/* Notifications */}
              <Button variant="ghost" size="icon" className="h-8 w-8 relative">
                <Bell className="h-4 w-4" />
                <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-primary"></span>
              </Button>
              
              <ThemeToggle />
              
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
                    <DropdownMenuItem asChild>
                      <Link to="/billing" className="cursor-pointer">
                        <CreditCard className="mr-2 h-4 w-4" />
                        Subscription
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link to="/team" className="cursor-pointer">
                        <Users className="mr-2 h-4 w-4" />
                        Team
                      </Link>
                    </DropdownMenuItem>
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
                  
                  {/* Help Section */}
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger>
                      <HelpCircle className="mr-2 h-4 w-4" />
                      Help
                    </DropdownMenuSubTrigger>
                    <DropdownMenuSubContent>
                      <DropdownMenuItem asChild>
                        <Link to="/help" className="cursor-pointer">
                          Help Center
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild>
                        <a href="https://docs.n8n-ops.com" target="_blank" rel="noopener noreferrer" className="cursor-pointer">
                          Documentation
                        </a>
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild>
                        <Link to="/report-bug" className="cursor-pointer">
                          Report Bug
                        </Link>
                      </DropdownMenuItem>
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                  
                  <DropdownMenuSeparator />
                  
                  {/* Account Actions */}
                  {planName !== 'enterprise' && (
                    <DropdownMenuItem asChild>
                      <Link to="/billing" className="cursor-pointer">
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
        <main className="p-6">
          <Outlet />
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
