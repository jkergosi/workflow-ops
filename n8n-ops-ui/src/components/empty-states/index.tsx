/**
 * Preset Empty States
 *
 * Pre-configured empty state components for common scenarios.
 * These provide consistent messaging, illustrations, and CTAs
 * for specific areas of the application.
 */
import { useNavigate } from "react-router-dom"
import { InformativeEmptyState, type InformativeEmptyStateProps } from "@/components/ui/informative-empty-state"
import {
  Plus,
  Server,
  GitBranch,
  Rocket,
  RefreshCw,
  FileText,
} from "lucide-react"

// ============================================================================
// ENVIRONMENTS EMPTY STATE
// ============================================================================
interface EnvironmentsEmptyStateProps {
  onAddEnvironment?: () => void
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function EnvironmentsEmptyState({
  onAddEnvironment,
  size = 'md',
  showCard = false,
}: EnvironmentsEmptyStateProps) {
  return (
    <InformativeEmptyState
      title="No environments connected"
      description="Connect your n8n instances to start monitoring workflows, tracking changes, and deploying updates across environments."
      secondaryText="Environments are the foundation for workflow management and GitOps."
      illustration="no-environments"
      size={size}
      showCard={showCard}
      primaryAction={
        onAddEnvironment
          ? {
              label: "Add Your First Environment",
              onClick: onAddEnvironment,
              icon: Plus,
            }
          : undefined
      }
      featureBullets={[
        "Monitor workflow health and execution status",
        "Track changes between environments",
        "Enable automated deployments with pipelines",
      ]}
      helpLinks={[
        {
          label: "Learn about environments",
          href: "https://docs.workflowops.io/environments",
          external: true,
        },
      ]}
    />
  )
}

// ============================================================================
// WORKFLOWS EMPTY STATE
// ============================================================================
interface WorkflowsEmptyStateProps {
  environmentName?: string
  onSync?: () => void
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function WorkflowsEmptyState({
  environmentName,
  onSync,
  size = 'md',
  showCard = false,
}: WorkflowsEmptyStateProps) {
  return (
    <InformativeEmptyState
      title="No workflows found"
      description={
        environmentName
          ? `No workflows have been synced from ${environmentName} yet. Run a sync to discover workflows from your n8n instance.`
          : "No workflows have been synced yet. Connect an environment and run a sync to discover workflows."
      }
      illustration="no-workflows"
      size={size}
      showCard={showCard}
      primaryAction={
        onSync
          ? {
              label: "Sync Workflows",
              onClick: onSync,
              icon: RefreshCw,
            }
          : undefined
      }
      featureBullets={[
        "Workflows are automatically discovered during sync",
        "Track versions and changes over time",
        "Deploy workflows to other environments",
      ]}
    />
  )
}

// ============================================================================
// DEPLOYMENTS EMPTY STATE
// ============================================================================
interface DeploymentsEmptyStateProps {
  hasPipelines?: boolean
  onCreateDeployment?: () => void
  onCreatePipeline?: () => void
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function DeploymentsEmptyState({
  hasPipelines = false,
  onCreateDeployment,
  onCreatePipeline,
  size = 'md',
  showCard = false,
}: DeploymentsEmptyStateProps) {
  return (
    <InformativeEmptyState
      title={hasPipelines ? "No deployments yet" : "Create a pipeline to deploy workflows"}
      description={
        hasPipelines
          ? "You haven't deployed any workflows yet. Start a new deployment to promote workflows between environments."
          : "Pipelines define how workflows move between environments. Create your first pipeline to enable deployments."
      }
      illustration="no-deployments"
      size={size}
      showCard={showCard}
      primaryAction={
        hasPipelines && onCreateDeployment
          ? {
              label: "Create Deployment",
              onClick: onCreateDeployment,
              icon: Rocket,
            }
          : onCreatePipeline
          ? {
              label: "Create Pipeline",
              onClick: onCreatePipeline,
              icon: GitBranch,
            }
          : undefined
      }
      featureBullets={
        hasPipelines
          ? [
              "Select workflows to deploy",
              "Preview changes before deployment",
              "Track deployment history and rollback if needed",
            ]
          : [
              "Define source and target environments",
              "Configure approval workflows",
              "Enable automated deployments",
            ]
      }
      helpLinks={[
        {
          label: hasPipelines ? "Deployment guide" : "Pipeline setup guide",
          href: hasPipelines
            ? "https://docs.workflowops.io/deployments"
            : "https://docs.workflowops.io/pipelines",
          external: true,
        },
      ]}
    />
  )
}

// ============================================================================
// PIPELINES EMPTY STATE
// ============================================================================
interface PipelinesEmptyStateProps {
  onCreatePipeline?: () => void
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function PipelinesEmptyState({
  onCreatePipeline,
  size = 'md',
  showCard = false,
}: PipelinesEmptyStateProps) {
  return (
    <InformativeEmptyState
      title="No pipelines configured"
      description="Pipelines automate workflow deployments between environments. Define your deployment stages and approval processes."
      illustration="no-pipelines"
      size={size}
      showCard={showCard}
      primaryAction={
        onCreatePipeline
          ? {
              label: "Create Your First Pipeline",
              onClick: onCreatePipeline,
              icon: Plus,
            }
          : undefined
      }
      featureBullets={[
        "Define multi-stage deployment flows",
        "Add approval gates for production",
        "Track deployment progress in real-time",
      ]}
      videoTutorial={{
        title: "Getting started with pipelines",
        url: "https://docs.workflowops.io/videos/pipelines-intro",
        duration: "3 min",
      }}
    />
  )
}

// ============================================================================
// INCIDENTS EMPTY STATE (Positive - All Clear!)
// ============================================================================
interface IncidentsEmptyStateProps {
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function IncidentsEmptyState({
  size = 'md',
  showCard = false,
}: IncidentsEmptyStateProps) {
  return (
    <InformativeEmptyState
      title="All environments are in sync"
      description="No drift incidents detected. Your environments are synchronized with their Git source of truth."
      secondaryText="WorkflowOps continuously monitors for configuration drift."
      illustration="no-incidents"
      size={size}
      showCard={showCard}
      featureBullets={[
        "Drift is automatically detected during sync",
        "Incidents are created when changes are found",
        "Resolve incidents by promoting or reverting changes",
      ]}
    />
  )
}

// ============================================================================
// CREDENTIALS EMPTY STATE
// ============================================================================
interface CredentialsEmptyStateProps {
  onAddCredential?: () => void
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function CredentialsEmptyState({
  onAddCredential,
  size = 'md',
  showCard = false,
}: CredentialsEmptyStateProps) {
  return (
    <InformativeEmptyState
      title="No credentials tracked"
      description="Credentials are discovered during environment sync. They help ensure workflows have the required connections before deployment."
      illustration="no-credentials"
      size={size}
      showCard={showCard}
      secondaryAction={
        onAddCredential
          ? {
              label: "Sync Environment",
              onClick: onAddCredential,
              icon: RefreshCw,
              variant: 'outline',
            }
          : undefined
      }
      featureBullets={[
        "Credentials are synced from n8n automatically",
        "Preflight checks ensure credentials exist before deployment",
        "Sensitive data is never stored",
      ]}
    />
  )
}

// ============================================================================
// ACTIVITY EMPTY STATE
// ============================================================================
interface ActivityEmptyStateProps {
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function ActivityEmptyState({
  size = 'md',
  showCard = false,
}: ActivityEmptyStateProps) {
  return (
    <InformativeEmptyState
      title="No recent activity"
      description="Activity will appear here as you sync environments, deploy workflows, and manage your n8n instances."
      illustration="no-activity"
      size={size}
      showCard={showCard}
      featureBullets={[
        "Track syncs, deployments, and changes",
        "Monitor background job progress",
        "Review audit history",
      ]}
    />
  )
}

// ============================================================================
// SEARCH RESULTS EMPTY STATE
// ============================================================================
interface SearchEmptyStateProps {
  searchQuery?: string
  onClearSearch?: () => void
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function SearchEmptyState({
  searchQuery,
  onClearSearch,
  size = 'sm',
  showCard = false,
}: SearchEmptyStateProps) {
  return (
    <InformativeEmptyState
      title="No results found"
      description={
        searchQuery
          ? `No items match "${searchQuery}". Try adjusting your search terms or filters.`
          : "No items match your current filters. Try adjusting your criteria."
      }
      illustration="no-search-results"
      size={size}
      showCard={showCard}
      secondaryAction={
        onClearSearch
          ? {
              label: "Clear Search",
              onClick: onClearSearch,
              variant: 'outline',
            }
          : undefined
      }
    />
  )
}

// ============================================================================
// GETTING STARTED EMPTY STATE
// ============================================================================
interface GettingStartedEmptyStateProps {
  onGetStarted?: () => void
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function GettingStartedEmptyState({
  onGetStarted,
  size = 'lg',
  showCard = false,
}: GettingStartedEmptyStateProps) {
  const navigate = useNavigate()

  return (
    <InformativeEmptyState
      title="Welcome to WorkflowOps!"
      description="Get started by connecting your first n8n environment. Once connected, you can sync workflows, track changes, and deploy updates."
      illustration="getting-started"
      size={size}
      showCard={showCard}
      primaryAction={{
        label: "Connect Your First Environment",
        onClick: onGetStarted || (() => navigate('/environments')),
        icon: Server,
      }}
      secondaryAction={{
        label: "View Documentation",
        onClick: () => window.open('https://docs.workflowops.io', '_blank'),
        variant: 'outline',
        icon: FileText,
      }}
      featureBullets={[
        "Connect multiple n8n instances",
        "Sync and version control workflows",
        "Deploy changes with pipelines",
        "Monitor drift and incidents",
      ]}
      videoTutorial={{
        title: "Quick Start Guide",
        url: "https://docs.workflowops.io/videos/quick-start",
        duration: "5 min",
      }}
    />
  )
}

// ============================================================================
// CONNECTION ERROR EMPTY STATE
// ============================================================================
interface ConnectionErrorEmptyStateProps {
  onRetry?: () => void
  errorMessage?: string
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function ConnectionErrorEmptyState({
  onRetry,
  errorMessage,
  size = 'md',
  showCard = false,
}: ConnectionErrorEmptyStateProps) {
  return (
    <InformativeEmptyState
      title="Unable to connect"
      description={
        errorMessage ||
        "We're having trouble connecting to the service. This might be a temporary issue."
      }
      secondaryText="Check your network connection and try again."
      illustration="connection-error"
      size={size}
      showCard={showCard}
      primaryAction={
        onRetry
          ? {
              label: "Try Again",
              onClick: onRetry,
              icon: RefreshCw,
            }
          : undefined
      }
      helpLinks={[
        {
          label: "Check system status",
          href: "https://status.workflowops.io",
          external: true,
        },
      ]}
    />
  )
}

// ============================================================================
// GENERIC DATA EMPTY STATE
// ============================================================================
interface DataEmptyStateProps {
  title?: string
  description?: string
  onAction?: () => void
  actionLabel?: string
  size?: InformativeEmptyStateProps['size']
  showCard?: boolean
}

export function DataEmptyState({
  title = "No data available",
  description = "There's nothing to display here yet.",
  onAction,
  actionLabel = "Get Started",
  size = 'md',
  showCard = false,
}: DataEmptyStateProps) {
  return (
    <InformativeEmptyState
      title={title}
      description={description}
      illustration="no-data"
      size={size}
      showCard={showCard}
      primaryAction={
        onAction
          ? {
              label: actionLabel,
              onClick: onAction,
              icon: Plus,
            }
          : undefined
      }
    />
  )
}
