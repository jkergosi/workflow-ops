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
import { ThemeToggle } from '@/components/ThemeToggle';
import { PlanBadge } from '@/components/FeatureGate';
import { useTheme } from '@/components/ThemeProvider';
import {
  LayoutDashboard,
  Server,
  Workflow,
  ListChecks,
  Tag,
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
  Book,
  Bug,
  Palette,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  requiredPlan?: 'pro' | 'enterprise';
  feature?: keyof PlanFeatures;
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
      { name: 'Dashboard', href: '/', icon: LayoutDashboard },
      { name: 'Environments', href: '/environments', icon: Server },
      { name: 'Workflows', href: '/workflows', icon: Workflow },
      { name: 'Executions', href: '/executions', icon: ListChecks },
      { name: 'Tags', href: '/tags', icon: Tag },
      { name: 'Snapshots', href: '/snapshots', icon: Camera },
      { name: 'Deployments', href: '/deployments', icon: Rocket, requiredPlan: 'pro', feature: 'environment_promotion' },
      { name: 'Observability', href: '/observability', icon: Activity, requiredPlan: 'pro', feature: 'execution_metrics' },
      { name: 'N8N Users', href: '/n8n-users', icon: UserCog },
      { name: 'Credentials', href: '/credentials', icon: Key },
    ],
  },
  {
    title: 'Admin',
    items: [
      { name: 'Tenants', href: '/admin/tenants', icon: Building2, requiredPlan: 'enterprise' },
      { name: 'System Billing', href: '/admin/billing', icon: CreditCard, requiredPlan: 'enterprise' },
      { name: 'Performance', href: '/admin/performance', icon: BarChart3, requiredPlan: 'enterprise' },
      { name: 'Audit Logs', href: '/admin/audit-logs', icon: FileText, requiredPlan: 'pro', feature: 'audit_logs' },
      { name: 'Notifications', href: '/admin/notifications', icon: Bell, requiredPlan: 'pro', feature: 'alerting' },
      { name: 'Security', href: '/admin/security', icon: Shield, requiredPlan: 'enterprise', feature: 'sso_scim' },
      { name: 'Settings', href: '/admin/settings', icon: Settings },
    ],
  },
];

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, availableUsers, loginAs } = useAuth();
  const { sidebarOpen, toggleSidebar } = useAppStore();
  const { canUseFeature, planName } = useFeatures();
  const { theme, setTheme } = useTheme();

  const handleUserSwitch = async (userId: string) => {
    await loginAs(userId);
    // Refresh the page to reload data for new user
    window.location.reload();
  };

  // Check if a nav item is accessible based on plan
  const isFeatureAvailable = (item: NavItem): boolean => {
    if (!item.feature) return true;
    return canUseFeature(item.feature);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-card border-r transform transition-transform duration-200 ease-in-out',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between h-16 px-6 border-b">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                <Workflow className="h-5 w-5 text-primary-foreground" />
              </div>
              <span className="text-lg font-bold">N8N Ops</span>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              onClick={toggleSidebar}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-4 py-4 overflow-y-auto">
            {navigationSections.map((section, sectionIndex) => (
              <div key={section.title} className={cn(sectionIndex > 0 && 'mt-6')}>
                <h3 className="px-3 mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {section.title}
                </h3>
                <div className="space-y-1">
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = location.pathname === item.href;
                    const isAvailable = isFeatureAvailable(item);
                    return (
                      <Link
                        key={item.href}
                        to={item.href}
                        className={cn(
                          'flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg transition-colors',
                          isActive
                            ? 'bg-primary text-primary-foreground'
                            : 'text-foreground/80 hover:bg-accent hover:text-accent-foreground',
                          !isAvailable && 'opacity-60'
                        )}
                      >
                        <Icon className="h-5 w-5" />
                        <span className="flex-1">{item.name}</span>
                        {!isAvailable && item.requiredPlan && (
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
              </div>
            ))}
          </nav>

          {/* User Info & Menu */}
          <div className="p-4 border-t">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-accent transition-colors text-left">
                  <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-sm font-semibold">
                    {user?.name?.charAt(0).toUpperCase() || 'U'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{user?.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                  </div>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
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
                  <DropdownMenuItem asChild>
                    <Link to="/profile/api-keys" className="cursor-pointer">
                      <Key className="mr-2 h-4 w-4" />
                      API Keys
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

      {/* Main Content */}
      <div
        className={cn(
          'transition-all duration-200',
          sidebarOpen ? 'lg:pl-64' : 'pl-0'
        )}
      >
        {/* Top Bar */}
        <div className="sticky top-0 z-40 h-16 bg-card border-b">
          <div className="flex items-center justify-between h-full px-6">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleSidebar}
            >
              <Menu className="h-5 w-5" />
            </Button>

            <div className="flex items-center gap-4">
              {/* Dev User Switcher */}
              {availableUsers.length > 0 && (
                <div className="flex items-center gap-2">
                  <UserCircle className="h-4 w-4 text-muted-foreground" />
                  <Select value={user?.id} onValueChange={handleUserSwitch}>
                    <SelectTrigger className="w-[200px]">
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
              <Badge variant="outline">
                Environment: <span className="ml-1 font-semibold">dev</span>
              </Badge>
              <ThemeToggle />
            </div>
          </div>
        </div>

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
