import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ArrowRight, X, ChevronUp, ChevronDown } from 'lucide-react';
import type { Environment } from '@/types';
import { sortEnvironments } from '@/lib/environment-utils';

interface EnvironmentSequenceProps {
  environments: Environment[];
  selectedEnvironmentIds?: string[];
  onChange: (environmentIds: string[]) => void;
}

export function EnvironmentSequence({
  environments,
  selectedEnvironmentIds = [],
  onChange,
}: EnvironmentSequenceProps) {
  const availableEnvironments = sortEnvironments(environments).filter(
    (env) => !selectedEnvironmentIds.includes(env.id)
  );

  const handleAddEnvironment = (environmentId: string) => {
    onChange([...selectedEnvironmentIds, environmentId]);
  };

  const handleRemoveEnvironment = (index: number) => {
    const newIds = selectedEnvironmentIds.filter((_, i) => i !== index);
    onChange(newIds);
  };

  const handleMoveUp = (index: number) => {
    if (index === 0) return;
    const newIds = [...selectedEnvironmentIds];
    [newIds[index - 1], newIds[index]] = [newIds[index], newIds[index - 1]];
    onChange(newIds);
  };

  const handleMoveDown = (index: number) => {
    if (index === selectedEnvironmentIds.length - 1) return;
    const newIds = [...selectedEnvironmentIds];
    [newIds[index], newIds[index + 1]] = [newIds[index + 1], newIds[index]];
    onChange(newIds);
  };

  const getEnvironment = (id: string) => {
    return environments.find((env) => env.id === id);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Environment Sequence</CardTitle>
        <CardDescription>
          Define the ordered list of environments for this pipeline. Each adjacent pair forms a promotion stage.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {selectedEnvironmentIds.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <p className="mb-4">No environments selected</p>
            <p className="text-sm">Add at least 2 environments to create a pipeline</p>
          </div>
        ) : (
          <div className="space-y-3">
            {selectedEnvironmentIds.map((envId, index) => {
              const env = getEnvironment(envId);
              return (
                <div
                  key={`${envId}-${index}`}
                  className="flex items-center gap-3 p-3 border rounded-lg bg-muted/50"
                >
                  <div className="flex items-center gap-2 flex-1">
                    <span className="text-sm font-medium text-muted-foreground w-8">
                      {index + 1}.
                    </span>
                    <div className="flex-1">
                      <div className="font-medium">{env?.name || envId}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleMoveUp(index)}
                      disabled={index === 0}
                      title="Move up"
                    >
                      <ChevronUp className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleMoveDown(index)}
                      disabled={index === selectedEnvironmentIds.length - 1}
                      title="Move down"
                    >
                      <ChevronDown className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleRemoveEnvironment(index)}
                      title="Remove"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {selectedEnvironmentIds.length > 0 && (
          <div className="flex items-center gap-2 pt-2">
            {selectedEnvironmentIds.map((envId, index) => {
              if (index === selectedEnvironmentIds.length - 1) return null;
              const env = getEnvironment(envId);
              const nextEnv = getEnvironment(selectedEnvironmentIds[index + 1]);
              return (
                <div key={`arrow-${index}`} className="flex items-center gap-2">
                  <div className="text-sm font-medium">{env?.name || envId}</div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  {index === selectedEnvironmentIds.length - 2 && (
                    <div className="text-sm font-medium">{nextEnv?.name || selectedEnvironmentIds[index + 1]}</div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {availableEnvironments.length > 0 && (
          <div className="pt-4 border-t">
            <div className="flex items-center gap-2">
              <Select
                value=""
                onValueChange={handleAddEnvironment}
              >
                <SelectTrigger className="flex-1">
                  <SelectValue placeholder="Add environment..." />
                </SelectTrigger>
                <SelectContent>
                  {availableEnvironments.map((env) => (
                    <SelectItem key={env.id} value={env.id}>
                      {env.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        {selectedEnvironmentIds.length < 2 && (
          <div className="text-sm text-muted-foreground pt-2">
            Minimum 2 environments required to create a pipeline
          </div>
        )}
      </CardContent>
    </Card>
  );
}

