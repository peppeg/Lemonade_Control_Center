export interface BackendReadinessItem {
  recipeKey: string;
  recipeName: string;
  backendKey: string;
  state: string;
  version: string | null;
  message: string;
  action: string;
  devices: string[];
  releaseUrl: string | null;
  experimental: boolean;
}

export interface BackendReadinessCounts {
  installed: number;
  updateRequired: number;
  installable: number;
  unsupported: number;
  other: number;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : [];
}

export function extractBackendReadiness(systemInfo: Record<string, unknown> | null | undefined): BackendReadinessItem[] {
  const recipes = asRecord(systemInfo?.recipes);

  return Object.entries(recipes).flatMap(([recipeKey, recipeValue]) => {
    const recipe = asRecord(recipeValue);
    const backends = asRecord(recipe.backends);
    const recipeName = asString(recipe.web_display_name) || asString(recipe.display_name) || recipeKey;
    const experimental = recipe.experimental === true;

    return Object.entries(backends).map(([backendKey, backendValue]) => {
      const backend = asRecord(backendValue);
      return {
        recipeKey,
        recipeName,
        backendKey,
        state: asString(backend.state) || 'unknown',
        version: asString(backend.version) || null,
        message: asString(backend.message),
        action: asString(backend.action),
        devices: asStringArray(backend.devices),
        releaseUrl: asString(backend.release_url) || null,
        experimental,
      };
    });
  }).sort((a, b) => {
    const rank = (item: BackendReadinessItem) => {
      if (item.state === 'update_required') return 0;
      if (item.state === 'installed') return 1;
      if (item.state === 'installable') return 2;
      if (item.state === 'unsupported') return 4;
      return 3;
    };
    return rank(a) - rank(b) || a.recipeName.localeCompare(b.recipeName) || a.backendKey.localeCompare(b.backendKey);
  });
}

export function backendReadinessCounts(items: BackendReadinessItem[]): BackendReadinessCounts {
  return items.reduce<BackendReadinessCounts>((counts, item) => {
    if (item.state === 'installed') counts.installed += 1;
    else if (item.state === 'update_required') counts.updateRequired += 1;
    else if (item.state === 'installable') counts.installable += 1;
    else if (item.state === 'unsupported') counts.unsupported += 1;
    else counts.other += 1;
    return counts;
  }, { installed: 0, updateRequired: 0, installable: 0, unsupported: 0, other: 0 });
}

export function backendStateLabel(state: string): string {
  if (state === 'update_required') return 'Update required';
  if (state === 'installed') return 'Installed';
  if (state === 'installable') return 'Installable';
  if (state === 'unsupported') return 'Unsupported';
  return state || 'Unknown';
}

export function backendStateBadgeClass(state: string): string {
  if (state === 'installed') return 'ops-badge-ok';
  if (state === 'update_required') return 'ops-badge-warn';
  if (state === 'unsupported') return 'ops-badge-danger';
  return '';
}
