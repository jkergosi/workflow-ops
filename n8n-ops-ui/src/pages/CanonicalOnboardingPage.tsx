import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { CheckCircle2, AlertCircle, Loader2, GitBranch, Link2, FileCheck } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/lib/auth';
import { apiClient } from '@/lib/api-client';
import type {
  OnboardingPreflight,
  OnboardingInventoryRequest,
  OnboardingInventoryResponse,
  MigrationPRRequest,
  MigrationPRResponse,
  OnboardingCompleteCheck,
  Environment
} from '@/types';

type OnboardingPhase = 'preflight' | 'inventory' | 'migration-pr' | 'link-resolution' | 'complete';

export function CanonicalOnboardingPage() {
  const navigate = useNavigate();
  const { tenant } = useAuth();
  const [phase, setPhase] = useState<OnboardingPhase>('preflight');
  const [isLoading, setIsLoading] = useState(false);
  const [preflight, setPreflight] = useState<OnboardingPreflight | null>(null);
  const [inventoryJobId, setInventoryJobId] = useState<string | null>(null);
  const [inventoryProgress, setInventoryProgress] = useState(0);
  const [tenantSlug, setTenantSlug] = useState('');
  const [migrationPR, setMigrationPR] = useState<MigrationPRResponse | null>(null);
  const [onboardingComplete, setOnboardingComplete] = useState<OnboardingCompleteCheck | null>(null);

  useEffect(() => {
    document.title = 'Canonical Workflow Onboarding - WorkflowOps';
    loadPreflight();
  }, []);

  const loadPreflight = async () => {
    try {
      const response = await apiClient.get('/canonical/onboarding/preflight');
      setPreflight(response.data);
      
      // If already onboarded, redirect
      if (!response.data.isPreCanonical) {
        navigate('/canonical/workflows');
        return;
      }
    } catch (error: any) {
      toast.error('Failed to load preflight checks');
      console.error(error);
    }
  };

  const startInventory = async () => {
    if (!preflight || !tenant) return;

    setIsLoading(true);
    try {
      // Get anchor environment (first environment or user-selected)
      const anchorEnv = preflight.environments[0];
      if (!anchorEnv) {
        toast.error('No environments found');
        return;
      }

      // Prepare environment configs
      const environmentConfigs = preflight.environments.map(env => ({
        environmentId: env.id,
        gitRepoUrl: env.gitRepoUrl || '',
        gitFolder: env.gitFolder || env.environmentType?.toLowerCase() || 'default'
      }));

      const request: OnboardingInventoryRequest = {
        anchorEnvironmentId: anchorEnv.id,
        environmentConfigs
      };

      const response = await apiClient.post<OnboardingInventoryResponse>(
        '/canonical/onboarding/inventory',
        request
      );

      setInventoryJobId(response.data.jobId);
      setPhase('inventory');
      
      // Poll for inventory progress
      pollInventoryProgress(response.data.jobId);
    } catch (error: any) {
      toast.error('Failed to start inventory');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const pollInventoryProgress = async (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const response = await apiClient.get(`/background-jobs/${jobId}`);
        const job = response.data;

        if (job.progress?.percentage) {
          setInventoryProgress(job.progress.percentage);
        }

        if (job.status === 'completed') {
          clearInterval(interval);
          setInventoryProgress(100);
          // Move to migration PR phase
          setPhase('migration-pr');
          // Generate tenant slug
          if (tenant?.name) {
            const slug = tenant.name.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-+/g, '-');
            setTenantSlug(slug);
          }
        } else if (job.status === 'failed') {
          clearInterval(interval);
          toast.error('Inventory failed: ' + (job.error_message || 'Unknown error'));
        }
      } catch (error) {
        console.error('Error polling inventory progress:', error);
      }
    }, 2000);
  };

  const createMigrationPR = async () => {
    if (!tenantSlug) {
      toast.error('Tenant slug is required');
      return;
    }

    setIsLoading(true);
    try {
      const request: MigrationPRRequest = { tenantSlug };
      const response = await apiClient.post<MigrationPRResponse>(
        '/canonical/onboarding/migration-pr',
        request
      );

      if (response.data.error) {
        toast.error('Failed to create migration PR: ' + response.data.error);
        return;
      }

      setMigrationPR(response.data);
      setPhase('link-resolution');
    } catch (error: any) {
      toast.error('Failed to create migration PR');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const checkOnboardingComplete = async () => {
    try {
      const response = await apiClient.get<OnboardingCompleteCheck>('/canonical/onboarding/complete');
      setOnboardingComplete(response.data);

      if (response.data.isComplete) {
        setPhase('complete');
      }
    } catch (error: any) {
      toast.error('Failed to check onboarding status');
      console.error(error);
    }
  };

  const renderPreflight = () => (
    <Card>
      <CardHeader>
        <CardTitle>Preflight Checks</CardTitle>
        <CardDescription>Review your current setup before migrating to canonical workflows</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {preflight && (
          <>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                {preflight.hasLegacyWorkflows ? (
                  <AlertCircle className="h-5 w-5 text-yellow-500" />
                ) : (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                )}
                <span>Legacy Workflows: {preflight.hasLegacyWorkflows ? 'Found' : 'None'}</span>
              </div>
              <div className="flex items-center gap-2">
                {preflight.hasLegacyGitLayout ? (
                  <AlertCircle className="h-5 w-5 text-yellow-500" />
                ) : (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                )}
                <span>Git Layout: {preflight.hasLegacyGitLayout ? 'Legacy' : 'Canonical'}</span>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Environments ({preflight.environments.length})</Label>
              {preflight.environments.map(env => (
                <div key={env.id} className="p-2 border rounded">
                  <div className="font-medium">{env.name}</div>
                  <div className="text-sm text-muted-foreground">
                    {env.gitRepoUrl ? 'Git configured' : 'No Git repo'}
                    {env.gitFolder && ` • Folder: ${env.gitFolder}`}
                  </div>
                </div>
              ))}
            </div>

            <Button onClick={startInventory} disabled={isLoading} className="w-full">
              {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Start Inventory
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );

  const renderInventory = () => (
    <Card>
      <CardHeader>
        <CardTitle>Inventory Phase</CardTitle>
        <CardDescription>Scanning workflows and generating canonical IDs</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Progress</span>
            <span>{inventoryProgress}%</span>
          </div>
          <Progress value={inventoryProgress} />
        </div>
        <p className="text-sm text-muted-foreground">
          This may take a few minutes depending on the number of workflows...
        </p>
      </CardContent>
    </Card>
  );

  const renderMigrationPR = () => (
    <Card>
      <CardHeader>
        <CardTitle>Create Migration PR</CardTitle>
        <CardDescription>Generate a pull request with all canonical workflows</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="tenant-slug">Tenant Slug</Label>
          <Input
            id="tenant-slug"
            value={tenantSlug}
            onChange={(e) => setTenantSlug(e.target.value)}
            placeholder="acme-inc"
            pattern="[a-z0-9-]+"
          />
          <p className="text-sm text-muted-foreground">
            Used for the migration branch name: migration/canonical-workflows/{tenantSlug}
          </p>
        </div>

        <Button onClick={createMigrationPR} disabled={isLoading || !tenantSlug} className="w-full">
          {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <GitBranch className="mr-2 h-4 w-4" />}
          Create Migration PR
        </Button>

        {migrationPR?.prUrl && (
          <Alert>
            <AlertDescription>
              <a href={migrationPR.prUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                View Pull Request
              </a>
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );

  const renderLinkResolution = () => (
    <Card>
      <CardHeader>
        <CardTitle>Link Resolution</CardTitle>
        <CardDescription>Resolve workflow mappings between environments</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Review and resolve any ambiguous workflow links. Auto-linked workflows are already mapped.
        </p>
        <Button onClick={checkOnboardingComplete} className="w-full">
          Check Completion Status
        </Button>
      </CardContent>
    </Card>
  );

  const renderComplete = () => (
    <Card>
      <CardHeader>
        <CardTitle>Onboarding Complete!</CardTitle>
        <CardDescription>Your canonical workflow system is ready</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2 text-green-600">
          <CheckCircle2 className="h-5 w-5" />
          <span>All workflows have been migrated to the canonical system</span>
        </div>
        <Button onClick={() => navigate('/canonical/workflows')} className="w-full">
          View Canonical Workflows
        </Button>
      </CardContent>
    </Card>
  );

  return (
    <div className="container mx-auto py-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Canonical Workflow Onboarding</h1>
        <p className="text-muted-foreground mt-2">
          Migrate your workflows to the canonical workflow identity system
        </p>
      </div>

      <div className="space-y-6">
        {phase === 'preflight' && renderPreflight()}
        {phase === 'inventory' && renderInventory()}
        {phase === 'migration-pr' && renderMigrationPR()}
        {phase === 'link-resolution' && renderLinkResolution()}
        {phase === 'complete' && renderComplete()}
      </div>
    </div>
  );
}

