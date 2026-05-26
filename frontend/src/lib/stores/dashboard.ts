/**
 * Dashboard store — aggregates data from multiple backend endpoints
 * and runs the smart alert engine.
 *
 * Polls every 10 seconds. Each card can show independently:
 * if one endpoint fails, the others still render.
 */
import { writable, get } from 'svelte/store';
import { api } from '$lib/api/client';
import { capabilities } from '$lib/stores/capabilities';
import type {
  DashboardData,
  ServerStatus,
  LoadedModelInfo,
  LastTaskInfo,
  HardwareInfo,
  SmartAlert,
  DashboardLoadingState,
} from '$lib/types';
import { formatDuration } from '$lib/utils/format';

// ── Stores ──

export const dashboardData = writable<DashboardData>({
  serverStatus: null,
  loadedModel: null,
  lastTask: null,
  hardware: null,
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

  // Fetch only dashboard-specific data.
  // Do not reload capabilities and do not interfere with global health polling.
  const canReadConfig = get(capabilities).internal_config;

  // Fire all requests in parallel — each one independent
  const [
    healthResult,
    hardwareResult,
    llamaResult,
    lastTaskResult,
    runningResult,
    configResult,
  ] = await Promise.allSettled([
    api.lemonade.health(),
    api.system.hardware(),
    api.system.llamaServer(),
    api.logs.lastTask(),
    api.lemonade.running(),
    canReadConfig
      ? api.lemonade.getConfig()
      : Promise.resolve({ ok: false, error: 'config unavailable' as const }),
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
      defaultBackend: (raw.llamacpp_backend as string) ?? null,
    };
  }

  // ── Parse Loaded Model ──
  let loadedModel: LoadedModelInfo | null = null;
  if (runningResult.status === 'fulfilled' && runningResult.value.ok) {
    const models = runningResult.value.data.models;
    if (models && models.length > 0) {
      const m = models[0] as Record<string, unknown>;

      // Enrich with llama-server process info
      let pid: number | null = null;
      let rssGb: number | null = null;
      let cpuPercent: number | null = null;
      let uptime: string | null = null;
      let uptimeSeconds: number | null = null;
      let ctxSize: number | null = null;
      let ngl: number | null = null;
      let backend: string | null = null;
      let mmap: boolean | null = null;
      let jinja = false;
      let specType: string | null = null;
      let specDraftMax: number | null = null;
      let reasoningFormat: string | null = null;
      let mmproj: string | null = null;

      if (llamaResult.status === 'fulfilled' && llamaResult.value.ok) {
        const info = llamaResult.value.data;
        if (info.found) {
          const proc = info.process as Record<string, unknown>;
          const params = info.params as Record<string, unknown>;
          pid = (proc?.pid as number) ?? null;
          rssGb = (proc?.rss_gb as number) ?? null;
          cpuPercent = (proc?.cpu_percent as number) ?? null;
          uptimeSeconds = (proc?.uptime_seconds as number) ?? null;
          uptime = uptimeSeconds ? formatDuration(uptimeSeconds) : null;
          ctxSize = (params?.ctx_size as number) ?? null;
          ngl = (params?.ngl as number) ?? null;
          backend = (params?.backend as string) ?? null;
          mmap = (params?.mmap as boolean) ?? null;
          jinja = (params?.jinja as boolean) ?? false;
          specType = (params?.spec_type as string) ?? null;
          specDraftMax = (params?.spec_draft_n_max as number) ?? null;
          reasoningFormat = (params?.reasoning_format as string) ?? null;
          mmproj = (params?.mmproj as string) ?? null;
        }
      }

      loadedModel = {
        name: (m.name as string) ?? 'Unknown',
        backend,
        ctxSize,
        ngl,
        mmap,
        jinja,
        specType,
        specDraftMax,
        reasoningFormat,
        mmproj,
        pid,
        rssGb,
        cpuPercent,
        uptime,
        uptimeSeconds,
      };
    }
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
  if (configResult.status === 'fulfilled' && configResult.value.ok) {
    const cfg = configResult.value.data;
    if (cfg.available && cfg.raw) {
      globalTimeout = (cfg.raw.global_timeout as number) ?? globalTimeout;
      configMaxTokens = (cfg.raw.max_tokens as number) ?? null;
    }
  }

  // ── Generate Alerts ──
  const alerts = generateAlerts(
    serverStatus, loadedModel, lastTask, hardware, globalTimeout, configMaxTokens
  );

  // ── Determine overall loading state ──
  const hasAny = serverStatus || loadedModel || lastTask || hardware;
  const hasAll = serverStatus && hardware;
  const state: DashboardLoadingState = hasAll ? 'loaded' : hasAny ? 'partial' : 'error';

  // ── Update store ──
  dashboardData.set({
    serverStatus,
    loadedModel,
    lastTask,
    hardware,
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
  server: ServerStatus | null,
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

  // ── Alert 7: No model loaded (idle) ──
  if (server?.status === 'running' && !model) {
    alerts.push({
      id: 'no-model',
      level: 'info',
      title: 'No model loaded',
      icon: '💤',
      description: 'Lemonade is running but no model is loaded.',
      suggestion: 'Go to Models to load one.',
    });
  }

  return alerts;
}
