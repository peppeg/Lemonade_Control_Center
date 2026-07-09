/**
 * Typed API client for the LCC backend.
 *
 * In dev, calls go through the Vite proxy (/api → localhost:8000/api).
 * In unified runtime, FastAPI serves both this frontend and /api.
 * Handles errors gracefully — never throws uncaught, always returns
 * structured results that the UI can display.
 */
import { browser } from '$app/environment';
import type {
  HealthResponse,
  Capabilities,
  AppearanceConfig,
  ConnectionDoctorResponse,
  ConnectionTestResult,
  DiscoveryResult,
  LccConfigPublic,
  LemonadeDiscoveryResponse,
  LemonadeHealth,
  LemonadeSavedOptions,
  HardwareInfo,
  RuntimeConfigPublic,
  RuntimeConfigRequest,
  SecurityStatus,
  SetupConnectionRequest,
  SetupStatusResponse,
  SystemConfig,
  AlertHistoryEntry,
  BenchResult,
  BenchStoredResult,
  BenchSuite,
  DiagnosticReport,
  MetricPoint,
  ModelProfiles,
  Profile,
  ProfileConfig,
  SmartRecommendation,
  RunEvidenceSeed,
  SmokeTestResponse,
  TaskRecord,
  SuiteResult,
} from '$lib/types';

const BASE = '/api';
const LCC_KEY_STORAGE = 'lcc_api_key';

export function getLccApiKey(): string {
  if (!browser) return '';
  return localStorage.getItem(LCC_KEY_STORAGE) ?? '';
}

export function setLccApiKey(value: string): void {
  if (!browser) return;
  const trimmed = value.trim();
  if (trimmed) {
    localStorage.setItem(LCC_KEY_STORAGE, trimmed);
  } else {
    localStorage.removeItem(LCC_KEY_STORAGE);
  }
}

export function withLccKey(path: string): string {
  const key = getLccApiKey();
  if (!key) return path;
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}lcc_key=${encodeURIComponent(key)}`;
}

/** Wrapper for API results — avoids try/catch in every component */
export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status?: number };

async function request<T>(method: string, path: string, body?: unknown): Promise<ApiResult<T>> {
  try {
    const key = getLccApiKey();
    const opts: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(key ? { 'X-LCC-API-Key': key } : {}),
      },
    };
    if (body) opts.body = JSON.stringify(body);

    const resp = await fetch(`${BASE}${path}`, opts);

    if (!resp.ok) {
      const text = await resp.text().catch(() => 'Unknown error');
      return { ok: false, error: text, status: resp.status };
    }

    const data = await resp.json() as T;
    return { ok: true, data };
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Network error';
    return { ok: false, error: msg };
  }
}

async function get<T>(path: string): Promise<ApiResult<T>> {
  return request<T>('GET', path);
}

async function post<T>(path: string, body?: unknown): Promise<ApiResult<T>> {
  return request<T>('POST', path, body);
}

async function put<T>(path: string, body?: unknown): Promise<ApiResult<T>> {
  return request<T>('PUT', path, body);
}

async function del<T>(path: string): Promise<ApiResult<T>> {
  return request<T>('DELETE', path);
}

function enc(value: string): string {
  return encodeURIComponent(value);
}

export const api = {
  // ── Health & Capabilities (M1) ──
  health: () => get<HealthResponse>('/health'),
  capabilities: () => get<Capabilities>('/capabilities'),

  // ── LCC Access Control (M15) ──
  security: {
    status: () => get<SecurityStatus>('/security/status'),
  },

  // ── Setup & Settings (M14) ──
  setup: {
    status: () => get<SetupStatusResponse>('/setup/status'),
    testConnection: (body: SetupConnectionRequest) =>
      post<ConnectionTestResult>('/setup/test-connection', body),
    discoverLemonade: (listenMs = 2500) =>
      get<LemonadeDiscoveryResponse>(`/setup/discover-lemonade?listen_ms=${listenMs}`),
    discover: (runtime: RuntimeConfigRequest) =>
      post<DiscoveryResult>('/setup/discover', runtime),
    complete: (body: { runtime: RuntimeConfigRequest; system: SystemConfig; appearance: AppearanceConfig }) =>
      post<LccConfigPublic>('/setup/complete', body),
  },

  settings: {
    get: () => get<LccConfigPublic>('/settings'),
    updateSystem: (system: SystemConfig) => put<LccConfigPublic>('/settings/system', system),
    updateAppearance: (appearance: AppearanceConfig) => put<LccConfigPublic>('/settings/appearance', appearance),
    addRuntime: (runtime: RuntimeConfigRequest) => post<RuntimeConfigPublic>('/settings/runtimes', runtime),
    updateRuntime: (id: string, runtime: RuntimeConfigRequest) =>
      put<RuntimeConfigPublic>(`/settings/runtimes/${enc(id)}`, runtime),
    removeRuntime: (id: string) => del<{ deleted: boolean }>(`/settings/runtimes/${enc(id)}`),
    activateRuntime: (id: string) => post<{ active: string }>(`/settings/runtimes/${enc(id)}/activate`),
    testRuntime: (id: string) => post<ConnectionTestResult>(`/settings/runtimes/${enc(id)}/test`),
    discoverRuntime: (id: string) => post<DiscoveryResult>(`/settings/runtimes/${enc(id)}/discover`),
    connectionDoctor: (id: string) => post<ConnectionDoctorResponse>(`/settings/runtimes/${enc(id)}/doctor`),
  },

  // ── Lemonade API (M2, used from M4+) ──
  lemonade: {
    health: () => get<LemonadeHealth>('/lemonade/health'),
    stats: () => get<Record<string, unknown>>('/lemonade/stats'),
    systemInfo: () => get<Record<string, unknown>>('/lemonade/system-info'),
    models: (catalog = false) => get<{ models: unknown[]; source: string }>(`/lemonade/models${catalog ? '?catalog=true' : ''}`),
    running: () => get<{ models: unknown[] }>('/lemonade/running'),
    savedOptions: (modelName?: string) =>
      get<LemonadeSavedOptions>(`/lemonade/saved-options${modelName ? `?model_name=${enc(modelName)}` : ''}`),
    showModel: (name: string) => get<Record<string, unknown>>(`/lemonade/models/${encodeURIComponent(name)}`),
    loadModel: (body: {
      model_name: string;
      ctx_size?: number;
      llamacpp_backend?: string;
      llamacpp_args?: string;
      merge_args?: boolean;
      save_options?: boolean;
    }) => post<{ success: boolean; message: string; evidence?: RunEvidenceSeed | null }>('/lemonade/load', body),
    smokeTest: (body: { model_name: string; prompt?: string; max_tokens?: number; temperature?: number }) =>
      post<SmokeTestResponse>('/lemonade/smoke-test', body),
    runEvidence: (modelName?: string) =>
      get<{ results: RunEvidenceSeed[] }>(`/lemonade/run-evidence${modelName ? `?model_name=${enc(modelName)}` : ''}`),
    pullModel: (modelName: string) =>
      post<{ success: boolean; message: string; raw?: Record<string, unknown> }>('/lemonade/pull', { model_name: modelName }),
    unloadModel: (name?: string) =>
      post<{ success: boolean }>('/lemonade/unload', { model_name: name }),
    deleteModel: (name: string) =>
      del<{ success: boolean }>(`/lemonade/models/${encodeURIComponent(name)}`),
    getConfig: () => get<{ raw: Record<string, unknown>; available: boolean }>('/lemonade/config'),
    setConfig: (updates: Record<string, unknown>) =>
      post<Record<string, unknown>>('/lemonade/config', { updates }),
  },

  // ── System (M2, used from M4+) ──
  system: {
    hardware: () => get<HardwareInfo>('/system/hardware'),
    temperatures: () => get<{ readings: unknown[]; available: boolean }>('/system/temperatures'),
    processes: () => get<{ processes: unknown[] }>('/system/processes'),
    llamaServer: () => get<{ found: boolean; process: unknown; params: unknown }>('/system/llama-server'),
    service: () => get<{ active: boolean; status: string }>('/system/service'),
    restart: () => post<{ success: boolean; message: string }>('/system/restart'),
  },

  // ── Logs (M2, used from M7+) ──
  logs: {
    recent: (n = 100) => get<{ entries: unknown[]; total_lines: number }>(`/logs/recent?n=${n}`),
    lastTask: (maxTokens?: number) =>
      get<Record<string, unknown>>(`/logs/last-task${maxTokens ? `?max_tokens=${maxTokens}` : ''}`),
  },

  // ── Profiles (M10) ──
  profiles: {
    list: (modelName: string) => get<ModelProfiles>(`/profiles/${enc(modelName)}`),
    recommendation: (modelName: string, modelSizeGb?: number | null) => {
      const size = typeof modelSizeGb === 'number' ? `?model_size_gb=${modelSizeGb}` : '';
      return get<SmartRecommendation>(`/profiles/${enc(modelName)}/recommendation${size}`);
    },
    create: (modelName: string, body: { name: string; description?: string; icon?: string; config: ProfileConfig }) =>
      post<Profile>(`/profiles/${enc(modelName)}`, body),
    update: (
      modelName: string,
      profileId: string,
      body: { name?: string; description?: string; icon?: string; config?: ProfileConfig; is_default?: boolean },
    ) => put<Profile>(`/profiles/${enc(modelName)}/${enc(profileId)}`, body),
    delete: (modelName: string, profileId: string) =>
      del<{ deleted: boolean }>(`/profiles/${enc(modelName)}/${enc(profileId)}`),
    clone: (modelName: string, profileId: string, newName: string) =>
      post<Profile>(`/profiles/${enc(modelName)}/${enc(profileId)}/clone?new_name=${enc(newName)}`),
    setDefault: (modelName: string, profileId: string) =>
      post<{ default: string }>(`/profiles/${enc(modelName)}/${enc(profileId)}/set-default`),
    export: (modelName: string, profileId: string) =>
      get<Record<string, unknown>>(`/profiles/${enc(modelName)}/${enc(profileId)}/export`),
    importProfile: (modelName: string, body: Record<string, unknown>) =>
      post<Profile>(`/profiles/${enc(modelName)}/import`, body),
  },

  // ── Diagnostics (M11) ──
  diagnostics: {
    run: () => get<DiagnosticReport>('/diagnostics'),
    history: (limit = 50) => get<{ entries: AlertHistoryEntry[] }>(`/diagnostics/history?limit=${limit}`),
    dismiss: (ruleId: string) => post<{ dismissed: string }>(`/diagnostics/dismiss?rule_id=${enc(ruleId)}`),
  },

  // ── Metrics (M12) ──
  metrics: {
    history: (minutes = 30) => get<{ points: MetricPoint[]; total: number; retention_minutes: number }>(`/metrics/history?minutes=${minutes}`),
    latest: () => get<{ point: MetricPoint | null }>('/metrics/latest'),
    tasks: (n = 20) => get<{ tasks: TaskRecord[] }>(`/metrics/tasks?n=${n}`),
    clear: () => post<{ cleared: boolean }>('/metrics/clear'),
    tasksCsvUrl: () => `${BASE}${withLccKey('/metrics/tasks/csv')}`,
  },

  // ── Bench Lab (M13, backend-gated) ──
  bench: {
    suites: () => get<{ suites: BenchSuite[] }>('/bench/suites'),
    runQuick: (body: { model: string; prompt: string; max_tokens: number; temperature: number; system_prompt?: string }) =>
      post<BenchResult>('/bench/run', body),
    runSuite: (body: { model: string; suite_id: string }) =>
      post<SuiteResult>('/bench/run', body),
    results: () => get<{ results: BenchStoredResult[] }>('/bench/results'),
    clear: () => post<{ cleared: boolean }>('/bench/clear'),
    csvUrl: () => `${BASE}/bench/results/csv`,
    jsonUrl: () => `${BASE}/bench/results/json`,
    markdownUrl: () => `${BASE}/bench/results/markdown`,
  },

  // ── Diagnostic (M2, used from M9) ──
  diagnosticBundleUrl: () => `${BASE}${withLccKey('/diagnostic-bundle')}`,
};
