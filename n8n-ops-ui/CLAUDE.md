# N8N Ops Frontend

React frontend for N8N Ops platform.

## Running

```bash
npm run dev -- --port <FRONTEND_PORT>
```

Check port in `../.env.local` (default: 3000 for main worktree).

## Pages

### Core Workflow Management
| Page | Route | Description |
|------|-------|-------------|
| `WorkflowsPage` | `/workflows` | List, search, filter, upload, delete workflows |
| `WorkflowDetailPage` | `/workflows/:id` | Tabs: Overview, Graph, Nodes, Analysis |
| `ExecutionsPage` | `/executions` | Execution history by environment/workflow |
| `CredentialsPage` | `/credentials` | View credential metadata |
| `TagsPage` | `/tags` | Manage workflow tags |

### Environment Management
| Page | Route | Description |
|------|-------|-------------|
| `EnvironmentsPage` | `/environments` | List N8N instances, sync, backup |
| `EnvironmentDetailPage` | `/environments/:id` | Environment details, workflows, settings |
| `EnvironmentSetupPage` | `/environments/new` | Create/edit environment |
| `RestorePage` | `/environments/:id/restore` | Restore from snapshots |

### Deployment & Promotion
| Page | Route | Description |
|------|-------|-------------|
| `PipelinesPage` | `/pipelines` | List promotion pipelines |
| `PipelineEditorPage` | `/pipelines/:id` | Edit pipeline stages, gates, approvals |
| `PromotionPage` | `/promote` | Execute workflow promotions |
| `DeploymentsPage` | `/deployments` | Deployment history, status |
| `DeploymentDetailPage` | `/deployments/:id` | Individual deployment details |
| `NewDeploymentPage` | `/deployments/new` | Create new deployment |
| `SnapshotsPage` | `/snapshots` | Environment snapshot history |

### Drift & Incidents
| Page | Route | Description |
|------|-------|-------------|
| `DriftDashboardPage` | `/drift-dashboard` | Drift overview, history, and analytics |
| `IncidentsPage` | `/incidents` | List drift incidents, filter by status |
| `IncidentDetailPage` | `/incidents/:id` | Incident details, acknowledge, resolve |

### Activity Center
| Page | Route | Description |
|------|-------|-------------|
| `ActivityCenterPage` | `/activity` | Unified activity feed |
| `ActivityDetailPage` | `/activity/:id` | Activity item details |

### Team & Admin
| Page | Route | Description |
|------|-------|-------------|
| `DashboardPage` | `/` | Overview stats |
| `TeamPage` | `/team` | Team members, roles |
| `BillingPage` | `/billing` | Subscription management |
| `ProfilePage` | `/profile` | User profile |
| `N8NUsersPage` | `/n8n-users` | N8N instance users |
| `ObservabilityPage` | `/observability` | Execution analytics |
| `AlertsPage` | `/alerts` | Alert configuration |
| `LoginPage` | `/login` | User authentication |
| `OnboardingPage` | `/onboarding` | New user setup |

### Support Pages
| Page | Route | Description |
|------|-------|-------------|
| `SupportHomePage` | `/support` | Support hub with options |
| `ReportBugPage` | `/support/bug/new` | Submit bug reports |
| `RequestFeaturePage` | `/support/feature/new` | Request new features |
| `GetHelpPage` | `/support/help/new` | Get help with issues |

### Admin Pages (`/admin/*`)
| Page | Route | Description |
|------|-------|-------------|
| `TenantsPage` | `/admin/tenants` | Multi-tenant admin |
| `TenantDetailPage` | `/admin/tenants/:id` | Individual tenant management |
| `SystemBillingPage` | `/admin/billing` | System billing |
| `PlansPage` | `/admin/plans` | Subscription plans |
| `UsagePage` | `/admin/usage` | Usage statistics |
| `PerformancePage` | `/admin/performance` | Performance metrics |
| `AuditLogsPage` | `/admin/audit-logs` | User action logs |
| `NotificationsPage` | `/admin/notifications` | System notifications |
| `SecurityPage` | `/admin/security` | Security settings |
| `SettingsPage` | `/admin/settings` | System settings |
| `FeatureMatrixPage` | `/admin/feature-matrix` | Plan feature comparison |
| `TenantOverridesPage` | `/admin/tenant-overrides` | Per-tenant feature overrides |
| `EntitlementsAuditPage` | `/admin/entitlements-audit` | Entitlement change history |
| `SupportConfigPage` | `/admin/support-config` | Support system settings |
| `CredentialHealthPage` | `/admin/credential-health` | Credential monitoring |
| `DriftPoliciesPage` | `/admin/drift-policies` | Drift detection policy config |

## State Management

### Zustand Store (`src/store/use-app-store.ts`)
```typescript
const { selectedEnvironment, setSelectedEnvironment } = useAppStore();
const { sidebarOpen, setSidebarOpen } = useAppStore();
```

### TanStack Query
```typescript
const { data, isLoading } = useQuery({
  queryKey: ['workflows', environmentId],
  queryFn: () => apiClient.getWorkflows(environmentId),
});

const mutation = useMutation({
  mutationFn: (data) => apiClient.createPipeline(data),
  onSuccess: () => queryClient.invalidateQueries(['pipelines']),
});
```

## API Client (`src/lib/api-client.ts`)

```typescript
import { apiClient } from '@/lib/api-client';

// Environments
await apiClient.getEnvironments();
await apiClient.createEnvironment(data);
await apiClient.syncEnvironment(id);
await apiClient.getEnvironmentCapabilities(id);

// Workflows
await apiClient.getWorkflows(environmentId, forceRefresh);
await apiClient.uploadWorkflows(files, environmentId, syncToGithub);
await apiClient.activateWorkflow(id, environmentId);

// Pipelines
await apiClient.getPipelines();
await apiClient.createPipeline(data);

// Promotions
await apiClient.initiatePromotion(request);
await apiClient.executePromotion(id);

// Deployments & Snapshots
await apiClient.getDeployments({ status, page });
await apiClient.getSnapshots({ environmentId, type });

// Auth (dev mode)
await apiClient.getDevUsers();
await apiClient.devLoginAs(userId);
```

## Auth (`src/lib/auth.tsx`)

Dev mode auto-login:
```typescript
const { user, tenant, isAuthenticated, isLoading } = useAuth();
const { loginAs, logout } = useAuth();
```

- Auto-login as first user in database
- Falls back to dummy user if API fails
- No Auth0 in local development

## Features & Permissions

### Feature Gating (`src/lib/features.tsx`)
```typescript
const { hasFeature, planFeatures } = useFeatures();

if (hasFeature('environment_promotion')) {
  // Show pipelines
}

// Or use component
<FeatureGate feature="scheduled_backup">
  <ScheduleButton />
</FeatureGate>
```

### Role Permissions (`src/lib/permissions.ts`)
```typescript
import { canAccessRoute, mapBackendRoleToFrontendRole } from '@/lib/permissions';

const userRole = mapBackendRoleToFrontendRole(user.role);
if (canAccessRoute('/admin/tenants', userRole)) {
  // Show admin link
}
```

## Components

### Layout
- `AppLayout.tsx` - Main layout with sidebar navigation
- `ThemeProvider.tsx` - Dark/light theme context
- `FeatureGate.tsx` - Conditional feature rendering

### UI Components (`src/components/ui/`)
shadcn/ui components: `button`, `card`, `dialog`, `table`, `tabs`, `input`, `select`, `checkbox`, `switch`, `badge`, `dropdown-menu`, `command`, `tooltip`, `alert`, `alert-dialog`, `textarea`, `multi-select`

### Workflow Components (`src/components/workflow/`)
- `WorkflowGraphTab.tsx` - Interactive graph with react-flow
- `WorkflowHeroSection.tsx` - Workflow header, metadata
- `NodeDetailsPanel.tsx` - Selected node details
- `NodeConfigView.tsx` - Node parameters, credentials
- `WorkflowActionsMenu.tsx` - Context menu for workflow actions
- `DirectEditWarningDialog.tsx` - Warning for production direct edits
- `HardDeleteConfirmDialog.tsx` - Confirmation for permanent deletion

### Pipeline Components (`src/components/pipeline/`)
- `EnvironmentSequence.tsx` - Visual env promotion path
- `StageCard.tsx` - Stage config (gates, approvals, schedule)

## Custom Hooks (`src/hooks/`)

| Hook | Purpose |
|------|---------|
| `useWorkflowActionPolicy.ts` | Fetches workflow action permissions based on environment class |
| `useEnvironmentCapabilities.ts` | Fetches environment capabilities and action guards |

### Workflow Action Policy (`src/lib/workflow-action-policy.ts`)
```typescript
// Determines what workflow actions are allowed based on environment class
import { getActionPolicy, ActionPolicy } from '@/lib/workflow-action-policy';

const policy = getActionPolicy(environmentClass, userRole);
if (policy.canDirectEdit) {
  // Show edit button
}
```

## Types (`src/types/index.ts`)

Key interfaces:
```typescript
interface Environment { id, name, type, baseUrl, apiKey, environmentClass, provider, ... }
interface Workflow { id, name, active, tags, nodes, ... }
interface Pipeline { id, name, stages, environmentIds, ... }
interface PipelineStage { sourceEnvironmentId, targetEnvironmentId, gates, approvals, ... }
interface Deployment { id, status, sourceEnvironmentId, targetEnvironmentId, ... }
interface Snapshot { id, environmentId, gitCommitSha, type, ... }
interface DriftIncident { id, status, severity, workflowId, environmentId, ... }
interface DriftPolicy { id, tenantId, ttlHours, slaHours, autoResolve, retentionDaysDriftChecks, ... }
interface WorkflowActionPolicy { canDirectEdit, canDelete, canActivate, requiresApproval, ... }
interface ProviderInfo { id, name, displayName, isActive, ... }
interface ProviderPlan { id, providerId, name, priceMonthly, maxEnvironments, ... }
interface TenantProviderSubscription { id, tenantId, providerId, planId, status, ... }
```

## Environment Variables

```env
# API base URL (must include /api/v1)
VITE_API_BASE_URL=http://localhost:4000/api/v1

# Mock API (for development without backend)
VITE_USE_MOCK_API=false

# Auth0 (disabled in dev)
VITE_AUTH0_DOMAIN=xxx
VITE_AUTH0_CLIENT_ID=xxx
```

## Adding New Pages

1. Create page in `src/pages/NewPage.tsx`
2. Add API methods in `src/lib/api-client.ts`
3. Add types in `src/types/index.ts`
4. Add route in `src/App.tsx`:
   ```tsx
   <Route path="/newpage" element={<RoleProtectedRoute><NewPage /></RoleProtectedRoute>} />
   ```
5. Add nav item in `src/components/AppLayout.tsx`

## Coding Patterns

### Page Structure
```tsx
export function NewPage() {
  const { selectedEnvironment } = useAppStore();

  const { data, isLoading, error } = useQuery({
    queryKey: ['items', selectedEnvironment],
    queryFn: () => apiClient.getItems(selectedEnvironment),
  });

  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Page Title</h1>
      {/* Content */}
    </div>
  );
}
```

### Mutations with Toast
```tsx
const mutation = useMutation({
  mutationFn: apiClient.createItem,
  onSuccess: () => {
    toast.success('Item created');
    queryClient.invalidateQueries(['items']);
  },
  onError: (error) => {
    toast.error(`Failed: ${error.message}`);
  },
});
```

### Styling
- TailwindCSS utility classes
- `className="space-y-4"` for vertical spacing
- `className="grid gap-4 md:grid-cols-2 lg:grid-cols-3"` for responsive grids
- shadcn/ui components from `@/components/ui/`
