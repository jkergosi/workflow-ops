import type { Environment, EnvironmentClass } from '@/types';

const CLASS_PRIORITY: Record<EnvironmentClass, number> = {
  dev: 0,
  staging: 1,
  production: 2,
};

function normalizeToEnvironmentClass(value: string | undefined): EnvironmentClass | undefined {
  if (!value) return undefined;
  const v = value.toLowerCase().trim();
  if (v === 'dev' || v === 'development') return 'dev';
  if (v === 'stage' || v === 'staging') return 'staging';
  if (v === 'prod' || v === 'production') return 'production';
  return undefined;
}

function getEnvironmentClass(env: Pick<Environment, 'environmentClass' | 'type'>): EnvironmentClass | undefined {
  return env.environmentClass || normalizeToEnvironmentClass(env.type);
}

export function sortEnvironments(environments: Environment[]): Environment[] {
  return [...environments].sort((a, b) => {
    const aClass = getEnvironmentClass(a);
    const bClass = getEnvironmentClass(b);
    const aPri = aClass ? CLASS_PRIORITY[aClass] : 999;
    const bPri = bClass ? CLASS_PRIORITY[bClass] : 999;

    if (aPri !== bPri) return aPri - bPri;

    const aName = (a.name || '').toLowerCase();
    const bName = (b.name || '').toLowerCase();
    if (aName !== bName) return aName.localeCompare(bName);

    return a.id.localeCompare(b.id);
  });
}

export function resolveEnvironment(
  environments: Environment[] | undefined,
  selected: string | undefined
): Environment | undefined {
  if (!environments || environments.length === 0 || !selected) return undefined;

  const byId = environments.find((e) => e.id === selected);
  if (byId) return byId;

  const selectedClass = normalizeToEnvironmentClass(selected);
  if (selectedClass) {
    const byClass = environments.find((e) => getEnvironmentClass(e) === selectedClass);
    if (byClass) return byClass;
  }

  const byType = environments.find((e) => e.type === selected);
  if (byType) return byType;

  return undefined;
}

export function getDefaultEnvironmentId(environments: Environment[] | undefined): string | undefined {
  if (!environments || environments.length === 0) return undefined;
  const sorted = sortEnvironments(environments);
  const devEnv = sorted.find((e) => getEnvironmentClass(e) === 'dev');
  return devEnv?.id || sorted[0]?.id;
}

export function getEnvironmentNameForSelection(
  environments: Environment[] | undefined,
  selected: string | undefined
): string | undefined {
  return resolveEnvironment(environments, selected)?.name;
}


