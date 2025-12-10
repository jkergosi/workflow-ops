import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { apiClient } from '@/lib/api-client';
import { EnvironmentSequence } from '@/components/pipeline/EnvironmentSequence';
import { StageCard } from '@/components/pipeline/StageCard';
import { ArrowLeft, Save } from 'lucide-react';
import { toast } from 'sonner';
import type { Pipeline, PipelineStage, Environment, RiskLevel } from '@/types';

export function PipelineEditorPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const isNew = !id || id === 'new';

  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: () => apiClient.getEnvironments(),
  });

  const { data: existingPipeline } = useQuery({
    queryKey: ['pipeline', id],
    queryFn: () => (id && !isNew ? apiClient.getPipeline(id) : Promise.resolve(null)),
    enabled: !isNew && !!id,
  });

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    isActive: true,
    environmentIds: [] as string[],
  });

  const [stages, setStages] = useState<PipelineStage[]>([]);

  useEffect(() => {
    if (existingPipeline?.data) {
      const pipeline = existingPipeline.data;
      setFormData({
        name: pipeline.name,
        description: pipeline.description || '',
        isActive: pipeline.isActive,
        environmentIds: pipeline.environmentIds,
      });
      setStages(pipeline.stages);
    }
  }, [existingPipeline]);

  const availableEnvironments = useMemo(() => {
    return environments?.data?.filter((env) => env.isActive) || [];
  }, [environments]);

  const createMutation = useMutation({
    mutationFn: () =>
      apiClient.createPipeline({
        name: formData.name,
        description: formData.description,
        isActive: formData.isActive,
        environmentIds: formData.environmentIds,
        stages,
      }),
    onSuccess: (data) => {
      toast.success('Pipeline created successfully');
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
      navigate(`/pipelines/${data.data.id}`);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create pipeline');
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      apiClient.updatePipeline(id!, {
        name: formData.name,
        description: formData.description,
        isActive: formData.isActive,
        environmentIds: formData.environmentIds,
        stages,
      }),
    onSuccess: () => {
      toast.success('Pipeline updated successfully');
      queryClient.invalidateQueries({ queryKey: ['pipelines'] });
      queryClient.invalidateQueries({ queryKey: ['pipeline', id] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update pipeline');
    },
  });

  const handleEnvironmentIdsChange = (newEnvironmentIds: string[]) => {
    // Filter out any undefined or invalid IDs
    const validEnvironmentIds = newEnvironmentIds.filter(id => id && typeof id === 'string' && id.trim() !== '');
    setFormData({ ...formData, environmentIds: validEnvironmentIds });
    
    const newStages: PipelineStage[] = [];
    for (let i = 0; i < validEnvironmentIds.length - 1; i++) {
      const sourceId = validEnvironmentIds[i];
      const targetId = validEnvironmentIds[i + 1];
      
      // Validate that both IDs are valid
      if (!sourceId || !targetId || sourceId === 'undefined' || targetId === 'undefined') {
        console.warn(`Skipping stage creation: invalid environment IDs (source: ${sourceId}, target: ${targetId})`);
        continue;
      }
      
      const existingStage = stages.find(
        (s) => s.sourceEnvironmentId === sourceId && s.targetEnvironmentId === targetId
      );
      
      if (existingStage) {
        newStages.push(existingStage);
      } else {
        const targetEnv = availableEnvironments.find((e) => e.id === targetId);
        // Smart defaults based on environment name/type (production environments typically need stricter rules)
        const envName = targetEnv?.name?.toLowerCase() || '';
        const envType = targetEnv?.type?.toLowerCase() || '';
        const isProduction = envName.includes('prod') || envType === 'production';
        
        newStages.push({
          sourceEnvironmentId: sourceId,
          targetEnvironmentId: targetId,
          gates: {
            requireCleanDrift: false,
            runPreFlightValidation: false,
            credentialsExistInTarget: false,
            nodesSupportedInTarget: false,
            webhooksAvailable: false,
            targetEnvironmentHealthy: false,
            maxAllowedRiskLevel: 'High' as RiskLevel,
          },
          approvals: {
            requireApproval: false,
          },
          policyFlags: {
            // Smart defaults: production environments typically disallow placeholders and hotfix overwrites
            allowPlaceholderCredentials: !isProduction,
            allowOverwritingHotfixes: !isProduction,
            allowForcePromotionOnConflicts: false,
          },
        });
      }
    }
    
    setStages(newStages);
  };

  const handleStageChange = (index: number, updatedStage: PipelineStage) => {
    const newStages = [...stages];
    newStages[index] = updatedStage;
    setStages(newStages);
  };

  const handleSave = () => {
    if (!formData.name.trim()) {
      toast.error('Pipeline name is required');
      return;
    }

    if (formData.environmentIds.length < 2) {
      toast.error('At least 2 environments are required');
      return;
    }

    // Validate that all environment IDs are valid
    const invalidIds = formData.environmentIds.filter(id => !id || typeof id !== 'string' || id.trim() === '' || id === 'undefined');
    if (invalidIds.length > 0) {
      toast.error('Invalid environment IDs detected. Please reselect environments.');
      return;
    }

    // Validate that all stages have valid environment IDs
    const invalidStages = stages.filter(stage => 
      !stage.sourceEnvironmentId || 
      !stage.targetEnvironmentId ||
      stage.sourceEnvironmentId === 'undefined' ||
      stage.targetEnvironmentId === 'undefined'
    );
    if (invalidStages.length > 0) {
      toast.error('Some stages have invalid environment IDs. Please reconfigure stages.');
      return;
    }

    if (stages.length !== formData.environmentIds.length - 1) {
      toast.error('Stage configuration mismatch');
      return;
    }

    if (isNew) {
      createMutation.mutate();
    } else {
      updateMutation.mutate();
    }
  };

  const getEnvironment = (id: string): Environment | undefined => {
    return availableEnvironments.find((env) => env.id === id);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/pipelines')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold">
              {isNew ? 'Create Pipeline' : 'Edit Pipeline'}
            </h1>
            <p className="text-muted-foreground">
              Define promotion rules and workflows between environments
            </p>
          </div>
        </div>
        <Button
          onClick={handleSave}
          disabled={createMutation.isPending || updateMutation.isPending}
        >
          <Save className="h-4 w-4 mr-2" />
          {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save'}
        </Button>
      </div>

      {/* Pipeline Header */}
      <Card>
        <CardHeader>
          <CardTitle>Pipeline Information</CardTitle>
          <CardDescription>Basic information about this pipeline</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Pipeline Name *</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., Standard Promotion Pipeline"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Optional description of this pipeline"
              rows={3}
            />
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="isActive"
              checked={formData.isActive}
              onCheckedChange={(checked) => setFormData({ ...formData, isActive: checked === true })}
            />
            <Label htmlFor="isActive" className="cursor-pointer">
              Active (inactive pipelines cannot be used for promotions)
            </Label>
          </div>
        </CardContent>
      </Card>

      {/* Environment Sequence */}
      <EnvironmentSequence
        environments={availableEnvironments}
        selectedEnvironmentIds={formData.environmentIds}
        onChange={handleEnvironmentIdsChange}
      />

      {/* Stage Configuration */}
      {stages.length > 0 && (
        <div className="space-y-4">
          <div>
            <h2 className="text-2xl font-bold mb-2">Stage Configuration</h2>
            <p className="text-muted-foreground">
              Configure promotion rules for each environment transition
            </p>
          </div>
          {stages.map((stage, index) => {
            const sourceEnv = getEnvironment(stage.sourceEnvironmentId);
            const targetEnv = getEnvironment(stage.targetEnvironmentId);
            
            return (
              <StageCard
                key={`${stage.sourceEnvironmentId}-${stage.targetEnvironmentId}`}
                stage={stage}
                sourceEnv={sourceEnv}
                targetEnv={targetEnv}
                onChange={(updatedStage) => handleStageChange(index, updatedStage)}
              />
            );
          })}
        </div>
      )}

      {/* Save Button (bottom) */}
      <div className="flex justify-end gap-2 pb-6">
        <Button variant="outline" onClick={() => navigate('/pipelines')}>
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          disabled={createMutation.isPending || updateMutation.isPending}
        >
          <Save className="h-4 w-4 mr-2" />
          {createMutation.isPending || updateMutation.isPending ? 'Saving...' : 'Save Pipeline'}
        </Button>
      </div>
    </div>
  );
}

