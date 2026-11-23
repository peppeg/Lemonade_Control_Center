/**
 * Dashboard store — aggregates data from multiple backend endpoints
 * and runs the smart alert engine.
 *
 * Polls on a relaxed interval. Each card can show independently:
 * if one endpoint fails, the others still render.
 */
import { writable } from 'svelte/store';
import { api } from '$lib/api/client';
import type {
  DashboardData,
  ServerStatus,
  LoadedModelInfo,
  LastTaskInfo,
  HardwareInfo,
  SmartAlert,
  DashboardLoadingState,
} from '$lib/types';
import { canChat, parseLoadedModel } from '$lib/utils/loadedModels';
import { configuredBackend } from '$lib/utils/runtimeConfig';

// ── Stores ──

export const dashboardData = writable<DashboardData>({
  serverStatus: null,
  loadedModels: [],
  lastTask: null,
  hardware: null,
  runtimeConfigAvailable: null,
  alerts: [],
  timestamp: new Date(),
});

export const dashboardLoading = writable<DashboardLoadingState>('loading');
export const lastRefresh = writable<Date | null>(null);
export const secondsSinceRefresh = writable<number>(0);

let pollInterval: ReturnType<typeof setInterval> | null = null;
let tickInterval: ReturnType<typeof setInterval> | null = null;
let hasLoadedOnce = false;

// ── Data Fetching ──

export async function refreshDashboard(): Promise<void> {
  // Skeleton only on first load. Later refreshes keep the old data visible.
  dashboardLoading.set(hasLoadedOnce ? 'partial' : 'loading');

  // Fire all requests in parallel — each one independent
  const [
    healthResult,
    hardwareResult,
    loadedResult,
    lastTaskResult,
    configResult,
  ] = await Promise.allSettled([
    api.lemonade.health(),
    api.system.hardware(),
    api.lemonade.loaded(),
    api.logs.lastTask(),
    api.lemonade.getConfig(),
  ]);

  // ── Parse Server Status ──
  let serverStatus: ServerStatus | null = null;
  if (healthResult.status === 'fulfilled' && healthResult.value.ok) {
    const h = healthResult.value.data;
    const raw = h.raw as Record<string, unknown>;
    serverStatus = {
      status: h.status === 'ok' || h.status === 'running' ? 'running' : 'unknown',
      version: h.version,
      apiPort: (raw.port as number) ?? 13305,
      websocketPort: h.websocket_port,
      globalTimeout: (raw.global_timeout as number) ?? null,
      maxLoadedModels: (raw.max_loaded_models as number) ?? null,
      defaultBackend: null,
    };
  }

  // ── Parse Loaded Models ──
  let loadedModels: LoadedModelInfo[] = [];
  if (loadedResult.status === 'fulfilled' && loadedResult.value.ok) {
    loadedModels = loadedResult.value.data.models.map((raw) => {
      const { name, type, params, process } = parseLoadedModel(raw);
      return {
        name,
        type,
        backend: params?.backend ?? null,
        ctxSize: params?.ctxSize ?? null,
        ngl: params?.ngl ?? null,
        mmap: params?.mmap ?? null,
        jinja: params?.jinja ?? false,
        specType: params?.specType ?? null,
        specDraftMax: params?.specDraftMax ?? null,
        reasoningFormat: params?.reasoningFormat ?? null,
        mmproj: params?.mmproj ?? null,
        pid: process?.pid ?? null,
        rssGb: process?.rssGb ?? null,
        cpuPercent: process?.cpuPercent ?? null,
        uptime: process?.uptime ?? null,
        uptimeSeconds: process?.uptimeSeconds ?? null,
      };
    });
  }

  // ── Parse Last Task ──
  let lastTask: LastTaskInfo | null = null;
  if (lastTaskResult.status === 'fulfilled' && lastTaskResult.value.ok) {
    const t = lastTaskResult.value.data as Record<string, unknown>;
    if (t.available) {
      const fr = t.finish_reason as Record<string, unknown> | null;
      lastTask = {
        available: true,
        inputTokens: (t.input_tokens as number) ?? null,
        outputTokens: (t.output_tokens as number) ?? null,
        promptEvalTps: (t.prompt_eval_tps as number) ?? null,
        generationTps: (t.generation_tps as number) ?? null,
        ttftSeconds: (t.ttft_seconds as number) ?? null,
        totalDurationSeconds: (t.total_duration_seconds as number) ?? null,
        finishReason: (fr?.reason as string) ?? null,
        finishConfidence: (fr?.confidence as 'confirmed' | 'inferred' | 'unknown') ?? 'unknown',
        finishEvidence: (fr?.evidence as string) ?? null,
      };
    }
  }

  // ── Parse Hardware ──
  let hardware: HardwareInfo | null = null;
  if (hardwareResult.status === 'fulfilled' && hardwareResult.value.ok) {
    hardware = hardwareResult.value.data;
  }

  // ── Parse Config (for alerts) ──
  let globalTimeout: number | null = serverStatus?.globalTimeout ?? null;
  let configMaxTokens: number | null = null;
  let runtimeConfigAvailable = false;
  if (configResult.status === 'fulfilled' && configResult.value.ok) {
    // Type assertion needed: ApiResult<T> for getConfig returns { ok: true; data: { raw; available } }
    const cfg = configResult.value as { data: { raw: Record<string, unknown>; available: boolean } };
    if (cfg.data.available && cfg.data.raw) {
      runtimeConfigAvailable = true;
      globalTimeout = (cfg.data.raw.global_timeout as number) ?? globalTimeout;
      configMaxTokens = (cfg.data.raw.max_tokens as number) ?? null;
      if (serverStatus) serverStatus.defaultBackend = configuredBackend(cfg.data.raw);
    }
  }

  // ── Generate Alerts ──
  const alerts = generateAlerts(
    loadedModels.find(canChat) ?? null, lastTask, hardware, globalTimeout, configMaxTokens
  );

  // ── Determine overall loading state ──
  const hasAny = serverStatus || loadedModels.length > 0 || lastTask || hardware;
  const hasAll = serverStatus && hardware;
  const state: DashboardLoadingState = hasAll ? 'loaded' : hasAny ? 'partial' : 'error';

  // ── Update store ──
  dashboardData.set({
    serverStatus,
    loadedModels,
    lastTask,
    hardware,
    runtimeConfigAvailable,
    alerts,
    timestamp: new Date(),
  });

  dashboardLoading.set(state);
  lastRefresh.set(new Date());
  secondsSinceRefresh.set(0);
  hasLoadedOnce = true;
}


// ── Polling ──

export function startDashboardPolling(intervalMs = 10_000): void {
  refreshDashboard();
  stopDashboardPolling();
  pollInterval = setInterval(refreshDashboard, intervalMs);

  // Tick counter: update "Xs ago" every second
  tickInterval = setInterval(() => {
    secondsSinceRefresh.update((n) => n + 1);
  }, 1000);
}

export function stopDashboardPolling(): void {
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
  if (tickInterval) { clearInterval(tickInterval); tickInterval = null; }
}


// ═══════════════════════════════════════════════
// SMART ALERT ENGINE
// ═══════════════════════════════════════════════

function generateAlerts(
  model: LoadedModelInfo | null,
  task: LastTaskInfo | null,
  hw: HardwareInfo | null,
  globalTimeout: number | null,
  configMaxTokens: number | null,
): SmartAlert[] {
  const alerts: SmartAlert[] = [];

  // ── Alert 1: Timeout mismatch ──
  if (globalTimeout && task?.generationTps && task?.outputTokens) {
    const estimatedTime = task.outputTokens / task.generationTps;
    if (globalTimeout < estimatedTime) {
      alerts.push({
        id: 'timeout-mismatch',
        level: 'warning',
        title: 'Timeout mismatch',
        icon: '⏰',
        description:
          `Global timeout (${globalTimeout}s) < estimated generation time (~${Math.round(estimatedTime)}s). ` +
          `At ${task.generationTps.toFixed(1)} t/s, ${task.outputTokens.toLocaleString()} tokens ≈ ${Math.round(estimatedTime)}s.`,
        suggestion: `Increase global_timeout to at least ${Math.ceil(estimatedTime * 1.2)}s, or reduce max_tokens.`,
      });
    }
  }

  // ── Alert 2: Probable truncation (inferred) ──
  if (task?.finishReason === 'length' && task.finishConfidence === 'inferred') {
    alerts.push({
      id: 'truncation-inferred',
      level: 'warning',
      title: 'Probable truncation',
      icon: '✂️',
      description:
        `The last task generated ${task.outputTokens?.toLocaleString() ?? '?'} tokens, ` +
        `which matches a max_tokens boundary. finish_reason = length (inferred).`,
      suggestion: 'If the output was cut short, increase max_tokens or check your client config.',
    });
  }

  // ── Alert 3: Confirmed truncation ──
  if (task?.finishReason === 'length' && task.finishConfidence === 'confirmed') {
    alerts.push({
      id: 'truncation-confirmed',
      level: 'error',
      title: 'Output truncated',
      icon: '🛑',
      description:
        `The last task was truncated at ${task.outputTokens?.toLocaleString() ?? '?'} tokens. ` +
        `finish_reason = length (confirmed by API).`,
      suggestion: 'Increase max_tokens to allow longer output.',
    });
  }

  // ── Alert 4: High RAM usage ──
  if (hw && hw.ram_percent > 90) {
    alerts.push({
      id: 'ram-pressure',
      level: 'warning',
      title: 'High RAM usage',
      icon: '🧠',
      description:
        `RAM usage is at ${hw.ram_percent}% (${hw.ram_used_gb.toFixed(1)}/${hw.ram_total_gb.toFixed(1)} GB). ` +
        `Performance may be degraded.`,
      suggestion: 'Consider reducing ctx_size or unloading unused models.',
    });
  }

  // ── Alert 5: High temperature ──
  // (Will be enriched in M8 when we add temperature to dashboard data)

  // ── Alert 6: Context residual warning ──
  if (model?.ctxSize && configMaxTokens) {
    const residual = model.ctxSize - configMaxTokens;
    if (residual < 2000) {
      alerts.push({
        id: 'context-residual',
        level: 'warning',
        title: 'Low context headroom',
        icon: '📏',
        description:
          `ctx_size (${model.ctxSize.toLocaleString()}) - max_tokens (${configMaxTokens.toLocaleString()}) ` +
          `= ${residual.toLocaleString()} tokens left for input + history.`,
        suggestion: 'Increase ctx_size or reduce max_tokens to leave more room for input.',
      });
    }
  }

  return alerts;
}
