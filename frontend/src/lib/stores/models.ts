/**
 * Models store — manages the list of models, loaded model detail,
 * and async action states (load, unload, delete).
 */
import { writable, derived, get } from 'svelte/store';
import { api } from '$lib/api/client';
import { notify } from '$lib/stores/notifications';
import type {
  ModelEntry,
  LoadedModelDetail,
  LoadModelOptions,
  ActionState,
} from '$lib/types';
import { formatGB } from '$lib/utils/format';

// ── Stores ──

export const models = writable<ModelEntry[]>([]);
export const loadedModel = writable<LoadedModelDetail | null>(null);
export const modelsLoading = writable(true);
export const modelsError = writable<string | null>(null);

// Action states (per-action loading/error)
export const loadAction = writable<ActionState>({ loading: false, error: null });
export const unloadAction = writable<ActionState>({ loading: false, error: null });
export const deleteAction = writable<ActionState>({ loading: false, error: null });

// ── Derived ──

export const loadedModelName = derived(loadedModel, ($m) => $m?.name ?? null);

export const modelCount = derived(models, ($m) => ({
  total: $m.length,
  loaded: $m.filter((m) => m.isLoaded).length,
}));


// ── Data Fetching ──

export async function refreshModels(): Promise<void> {
  modelsLoading.set(true);
  modelsError.set(null);

  // Fetch models list + running models + process info in parallel
  const [modelsResult, runningResult, processResult] = await Promise.allSettled([
    api.lemonade.models(),
    api.lemonade.running(),
    api.system.llamaServer(),
  ]);

  // Parse running model names for the "currently loaded" panel only.
  // The table itself must trust backend `is_loaded`.
  const runningNames = new Set<string>();
  if (runningResult.status === 'fulfilled' && runningResult.value.ok) {
    const runModels = runningResult.value.data.models as Array<Record<string, unknown>>;
    for (const m of runModels) {
      runningNames.add((m.name as string) ?? '');
    }
  }

  // Parse models list
  if (modelsResult.status === 'fulfilled' && modelsResult.value.ok) {
    const raw = modelsResult.value.data.models as Array<Record<string, unknown>>;
    const parsed: ModelEntry[] = raw.map((m) => {
      const name = (m.name as string) ?? (m.model as string) ?? 'unknown';
      const sizeBytes = (m.size as number) ?? null;
      return {
        name,
        model: (m.model as string) ?? null,
        size: sizeBytes,
        sizeFormatted: sizeBytes ? formatGB(sizeBytes / (1024 ** 3)) : '—',
        digest: (m.digest as string) ?? null,
        modifiedAt: (m.modified_at as string) ?? null,
        details: (m.details as Record<string, unknown>) ?? null,
        isLoaded: Boolean(m.is_loaded),
      };
    });

    // Sort: loaded first, then alphabetical
    parsed.sort((a, b) => {
      if (a.isLoaded !== b.isLoaded) return a.isLoaded ? -1 : 1;
      return a.name.localeCompare(b.name);
    });

    models.set(parsed);
  } else {
    modelsError.set('Failed to load models list');
  }

  // Parse loaded model detail (process info + cmdline)
  if (processResult.status === 'fulfilled' && processResult.value.ok) {
    const data = processResult.value.data;
    if (data.found) {
      const proc = data.process as Record<string, unknown>;
      const params = data.params as Record<string, unknown>;

      // Find the loaded model name from running list first.
      // Fallback to the first entry already marked loaded by the backend.
      const firstName =
        runningNames.values().next().value ??
        get(models).find((m) => m.isLoaded)?.name ??
        'Unknown';

      loadedModel.set({
        name: firstName,
        params: params ? {
          executable: (params.executable as string) ?? null,
          modelPath: (params.model_path as string) ?? null,
          ctxSize: (params.ctx_size as number) ?? null,
          port: (params.port as number) ?? null,
          host: (params.host as string) ?? null,
          ngl: (params.ngl as number) ?? null,
          backend: (params.backend as string) ?? null,
          mmap: (params.mmap as boolean) ?? null,
          jinja: (params.jinja as boolean) ?? false,
          mmproj: (params.mmproj as string) ?? null,
          contextShift: (params.context_shift as boolean) ?? null,
          keep: (params.keep as number) ?? null,
          reasoningFormat: (params.reasoning_format as string) ?? null,
          specType: (params.spec_type as string) ?? null,
          specDraftMax: (params.spec_draft_n_max as number) ?? null,
          specDraftPMin: (params.spec_draft_p_min as number) ?? null,
          rawCmdline: (params.raw_cmdline as string) ?? '',
        } : null,
        process: proc ? {
          pid: (proc.pid as number) ?? 0,
          rssGb: (proc.rss_gb as number) ?? 0,
          cpuPercent: (proc.cpu_percent as number) ?? 0,
          uptime: (proc.uptime_seconds as number)
            ? formatDuration(proc.uptime_seconds as number)
            : '—',
          uptimeSeconds: (proc.uptime_seconds as number) ?? 0,
        } : null,
      });
    } else {
      loadedModel.set(null);
    }
  }

  modelsLoading.set(false);
}


// ── Actions ──

export async function loadModel(opts: LoadModelOptions): Promise<boolean> {
  loadAction.set({ loading: true, error: null });
  const result = await api.lemonade.loadModel({
    model_name: opts.modelName,
    ctx_size: opts.ctxSize ?? undefined,
    llamacpp_backend: opts.llamacppBackend ?? undefined,
    llamacpp_args: opts.llamacppArgs || undefined,
    save_options: opts.saveOptions,
  });

  if (result.ok && result.data.success) {
    loadAction.set({ loading: false, error: null });
    await refreshModels();
    notify.success('Model loaded', opts.modelName, { href: '/models' });
    return true;
  } else {
    const msg = result.ok ? result.data.message : result.error;
    loadAction.set({ loading: false, error: msg });
    notify.error('Model load failed', msg || opts.modelName, { href: '/models' });
    return false;
  }
}

export async function unloadModel(name?: string, options: { suppressNotification?: boolean } = {}): Promise<boolean> {
  unloadAction.set({ loading: true, error: null });
  const result = await api.lemonade.unloadModel(name);

  if (result.ok) {
    unloadAction.set({ loading: false, error: null });
    await refreshModels();
    if (!options.suppressNotification) {
      notify.success('Model unloaded', name ?? 'Current model was unloaded.', { href: '/models' });
    }
    return true;
  } else {
    unloadAction.set({ loading: false, error: result.error });
    if (!options.suppressNotification) {
      notify.error('Unload failed', result.error || 'Lemonade rejected the unload request.', { href: '/models' });
    }
    return false;
  }
}

export async function deleteModel(name: string): Promise<boolean> {
  deleteAction.set({ loading: true, error: null });
  const result = await api.lemonade.deleteModel(name);

  if (result.ok) {
    deleteAction.set({ loading: false, error: null });
    await refreshModels();
    notify.success('Model deleted', name, { href: '/models' });
    return true;
  } else {
    deleteAction.set({ loading: false, error: result.error });
    notify.error('Delete failed', result.error || name, { href: '/models' });
    return false;
  }
}


// ── Helpers ──

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}
