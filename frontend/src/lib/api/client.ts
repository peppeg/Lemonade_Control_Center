/**
 * Typed API client for the LCC backend.
 *
 * All calls go through the Vite proxy in dev (/api → localhost:8000/api).
 * Handles errors gracefully — never throws uncaught, always returns
 * structured results that the UI can display.
 */
import type {
  HealthResponse,
  Capabilities,
  LemonadeHealth,
  HardwareInfo,
} from '$lib/types';

const BASE = '/api';

/** Wrapper for API results — avoids try/catch in every component */
export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status?: number };

async function request<T>(method: string, path: string, body?: unknown): Promise<ApiResult<T>> {
  try {
    const opts: RequestInit = {
      method,
      headers: { 'Content-Type': 'application/json' },
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

async function del<T>(path: string): Promise<ApiResult<T>> {
  return request<T>('DELETE', path);
}

export const api = {
  // ── Health & Capabilities (M1) ──
  health: () => get<HealthResponse>('/health'),
  capabilities: () => get<Capabilities>('/capabilities'),

  // ── Lemonade API (M2, used from M4+) ──
  lemonade: {
    health: () => get<LemonadeHealth>('/lemonade/health'),
    stats: () => get<Record<string, unknown>>('/lemonade/stats'),
    systemInfo: () => get<Record<string, unknown>>('/lemonade/system-info'),
    models: () => get<{ models: unknown[]; source: string }>('/lemonade/models'),
    running: () => get<{ models: unknown[] }>('/lemonade/running'),
    showModel: (name: string) => get<Record<string, unknown>>(`/lemonade/models/${encodeURIComponent(name)}`),
    loadModel: (
    body: {
      model_name: string;
      ctx_size?: number;
      llamacpp_backend?: string;
      llamacpp_args?: string;
      save_options?: boolean;
    }
  ) => post<{ success: boolean; message: string }>('/lemonade/load', body),
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

  // ── Diagnostic (M2, used from M9) ──
  diagnosticBundleUrl: () => `${BASE}/diagnostic-bundle`,
};
