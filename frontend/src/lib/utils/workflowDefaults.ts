export interface WorkflowDefaults {
  maxOutputTokens: number;
  temperature: number;
  appTimeoutSeconds: number;
  stopSequences: string[];
  activePreset: string;
  activeProfileId: string | null;
  activeProfileModelName: string | null;
}

const STORAGE_KEY = 'lcc.workflowDefaults';
const LEGACY_STORAGE_KEY = 'lcc.requestDefaults';

export const DEFAULT_WORKFLOW_DEFAULTS: WorkflowDefaults = {
  maxOutputTokens: 2048,
  temperature: 0.7,
  appTimeoutSeconds: 300,
  stopSequences: ['<|im_end|>', '\n\nUser:'],
  activePreset: 'Coding',
  activeProfileId: null,
  activeProfileModelName: null,
};

export function loadWorkflowDefaults(): WorkflowDefaults {
  if (typeof localStorage === 'undefined') return cloneDefaults();
  const current = localStorage.getItem(STORAGE_KEY);
  const legacy = current ? null : localStorage.getItem(LEGACY_STORAGE_KEY);
  const raw = current ?? legacy;
  if (!raw) return cloneDefaults();

  try {
    const defaults = normalizeWorkflowDefaults(JSON.parse(raw));
    if (legacy) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(defaults));
      localStorage.removeItem(LEGACY_STORAGE_KEY);
    }
    return defaults;
  } catch {
    return cloneDefaults();
  }
}

export function saveWorkflowDefaults(defaults: WorkflowDefaults): WorkflowDefaults {
  const normalized = normalizeWorkflowDefaults(defaults);
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  }
  return normalized;
}

export function resetWorkflowDefaults(): WorkflowDefaults {
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  }
  return cloneDefaults();
}

function normalizeWorkflowDefaults(value: unknown): WorkflowDefaults {
  const record = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return {
    maxOutputTokens: numberInRange(record.maxOutputTokens, 1, 65536, DEFAULT_WORKFLOW_DEFAULTS.maxOutputTokens),
    temperature: numberInRange(record.temperature, 0, 2, DEFAULT_WORKFLOW_DEFAULTS.temperature),
    appTimeoutSeconds: numberInRange(record.appTimeoutSeconds, 1, 3600, DEFAULT_WORKFLOW_DEFAULTS.appTimeoutSeconds),
    stopSequences: Array.isArray(record.stopSequences)
      ? record.stopSequences.filter((item): item is string => typeof item === 'string' && item.length > 0)
      : [...DEFAULT_WORKFLOW_DEFAULTS.stopSequences],
    activePreset: typeof record.activePreset === 'string' && record.activePreset ? record.activePreset : DEFAULT_WORKFLOW_DEFAULTS.activePreset,
    activeProfileId: typeof record.activeProfileId === 'string' && record.activeProfileId ? record.activeProfileId : null,
    activeProfileModelName: typeof record.activeProfileModelName === 'string' && record.activeProfileModelName ? record.activeProfileModelName : null,
  };
}

function numberInRange(value: unknown, min: number, max: number, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value)
    ? Math.max(min, Math.min(max, value))
    : fallback;
}

function cloneDefaults(): WorkflowDefaults {
  return { ...DEFAULT_WORKFLOW_DEFAULTS, stopSequences: [...DEFAULT_WORKFLOW_DEFAULTS.stopSequences] };
}
