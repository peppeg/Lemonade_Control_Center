<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import {
    dashboardData, dashboardLoading, lastRefresh,
    startDashboardPolling, stopDashboardPolling,
  } from '$lib/stores/dashboard';
  import { capabilities } from '$lib/stores/capabilities';
  import { connectionStatus } from '$lib/stores/connection';
  import { AlertTriangle, Check, Clock3, Cpu, HardDrive, Info, RefreshCw, Server, TimerReset } from 'lucide-svelte';
  import DiagnosticsPanel from '$lib/components/diagnostics/DiagnosticsPanel.svelte';
  import type { HardwareInfo, LastTaskInfo, LoadedModelInfo, ServerStatus } from '$lib/types';
  import { formatDuration, formatNumber, formatPercent, formatTPS } from '$lib/utils/format';

  $: data = $dashboardData;
  $: server = data.serverStatus;
  $: model = data.loadedModel;
  $: hardware = data.hardware;
  $: lastTask = data.lastTask;
  $: isLoading = $dashboardLoading === 'loading';
  $: readiness = $connectionStatus === 'connected' ? 'Connected' : $connectionStatus === 'degraded' ? 'Degraded' : $connectionStatus === 'checking' ? 'Checking' : 'Offline';

  onMount(() => {
    startDashboardPolling(10_000);
  });

  onDestroy(() => {
    stopDashboardPolling();
  });

  function value(value: string | number | null | undefined): string {
    if (value === null || value === undefined || value === '') return 'Unavailable';
    return String(value);
  }

  function hardwarePressure(hw: HardwareInfo | null): string {
    if (!hw) return 'Unavailable';
    const cpu = hw.cpu_percent < 35 ? 'low' : hw.cpu_percent < 75 ? 'medium' : 'high';
    return `RAM ${formatPercent(hw.ram_percent)} (${hw.ram_used_gb.toFixed(1)}/${hw.ram_total_gb.toFixed(1)} GB), CPU ${cpu}`;
  }

  function runtimeLabel(serverStatus: ServerStatus | null, loaded: LoadedModelInfo | null): string {
    const backend = loaded?.backend ?? serverStatus?.defaultBackend ?? 'unknown';
    const ctx = loaded?.ctxSize ? `ctx ${formatNumber(loaded.ctxSize)}` : 'ctx unknown';
    return `${backend} (${ctx})`;
  }

  function taskMetric(task: LastTaskInfo | null, key: keyof LastTaskInfo, suffix = ''): string {
    const raw = task?.[key];
    if (typeof raw !== 'number') return 'Unavailable';
    return `${raw}${suffix}`;
  }

  function percentWidth(value: number | null | undefined): string {
    if (typeof value !== 'number') return '0%';
    return `${Math.max(0, Math.min(100, value))}%`;
  }
</script>

<div class="space-y-6">
  <section class="ops-panel px-4 py-4">
    <div class="flex flex-wrap items-center gap-x-8 gap-y-3 text-sm">
      <div class="flex items-center gap-2">
        <span class="h-2.5 w-2.5 rounded-full {$connectionStatus === 'connected' ? 'bg-status-ok' : $connectionStatus === 'degraded' ? 'bg-status-warn' : 'bg-status-error'}"></span>
        <span class="ops-muted">Readiness:</span>
        <span class="ops-value">{readiness}</span>
      </div>
      <div class="hidden h-5 w-px bg-[#444936] md:block"></div>
      <div class="min-w-0">
        <span class="ops-muted">Model:</span>
        <span class="ops-value ml-2 text-lemon">{model?.name ?? 'No active model'}</span>
      </div>
      <div class="hidden h-5 w-px bg-[#444936] md:block"></div>
      <div>
        <span class="ops-muted">Runtime:</span>
        <span class="ops-value ml-2">{runtimeLabel(server, model)}</span>
      </div>
      <div class="basis-full">
        <span class="ops-muted">HW Pressure:</span>
        <span class="ops-value ml-2">{hardwarePressure(hardware)}</span>
      </div>
    </div>
  </section>

  {#if !$capabilities.internal_config || !$capabilities.internal_set}
    <section class="ops-banner ops-banner-danger">
      <AlertTriangle class="mt-0.5 h-5 w-5 shrink-0" />
      <div>
        <p class="font-semibold">Runtime Config is read-only</p>
        <p class="mt-1 text-sm text-[#ffd9d6]">
          Admin key is missing or server-side config writes are disabled. Runtime values can be inspected, but not saved to disk.
        </p>
      </div>
    </section>
  {/if}

  {#if !lastTask?.available}
    <section class="ops-banner ops-banner-muted">
      <Info class="mt-0.5 h-5 w-5 shrink-0" />
      <p class="text-sm text-[#d9dbcf]">No recent task stats available.</p>
    </section>
  {/if}

  <section class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
    <article class="ops-card p-4">
      <div class="flex items-center justify-between">
        <span class="ops-label">Server Status</span>
        <Server class="h-5 w-5 text-muted-foreground" />
      </div>
      <div class="mt-8 flex flex-col items-center">
        <div class="flex h-20 w-20 items-center justify-center rounded-full border-2 {$connectionStatus === 'connected' ? 'border-status-ok text-status-ok' : 'border-status-warn text-status-warn'}">
          <Check class="h-8 w-8" />
        </div>
        <p class="mt-3 text-lg font-bold uppercase">{server?.status === 'running' ? 'Ready' : readiness}</p>
      </div>
      <div class="mt-8 border-t border-[#34382d] pt-3 text-sm">
        <div class="flex justify-between gap-3">
          <span class="ops-muted">Version</span>
          <span class="ops-value">{value(server?.version)}</span>
        </div>
        <div class="mt-2 flex justify-between gap-3">
          <span class="ops-muted">API Port</span>
          <span class="ops-value">{value(server?.apiPort)}</span>
        </div>
      </div>
    </article>

    <article class="ops-card p-4">
      <div class="flex items-center justify-between">
        <span class="ops-label">Loaded Model</span>
        <Cpu class="h-5 w-5 text-muted-foreground" />
      </div>
      <h2 class="mt-6 break-words text-xl font-bold text-lemon">{model?.name ?? 'No model loaded'}</h2>
      <p class="mt-2 ops-value text-sm">{model?.backend ?? 'backend unknown'}</p>
      <div class="mt-10 grid grid-cols-2 gap-2">
        <div class="rounded border border-[#414632] bg-[#282b28] p-3">
          <p class="text-xs text-muted-foreground">Context Window</p>
          <p class="ops-value mt-1">{model?.ctxSize ? formatNumber(model.ctxSize) : 'Unavailable'}</p>
        </div>
        <div class="rounded border border-[#414632] bg-[#282b28] p-3">
          <p class="text-xs text-muted-foreground">Offload</p>
          <p class="ops-value mt-1">{model?.ngl ?? 'Unknown'}</p>
        </div>
      </div>
    </article>

    <article class="ops-card p-4">
      <div class="flex items-center justify-between">
        <span class="ops-label">Hardware</span>
        <HardDrive class="h-5 w-5 text-muted-foreground" />
      </div>
      <div class="mt-8 space-y-5">
        <div>
          <div class="mb-2 flex justify-between text-sm">
            <span>RAM Usage</span>
            <span>{hardware ? formatPercent(hardware.ram_percent) : 'Unavailable'}</span>
          </div>
          <div class="ops-progress"><span style:width={percentWidth(hardware?.ram_percent)}></span></div>
          <p class="mt-2 text-right ops-value text-sm">
            {hardware ? `${hardware.ram_used_gb.toFixed(1)} / ${hardware.ram_total_gb.toFixed(1)} GB` : 'Unavailable'}
          </p>
        </div>
        <div>
          <div class="mb-2 flex justify-between text-sm">
            <span>CPU Load</span>
            <span class="text-status-ok">{hardware ? formatPercent(hardware.cpu_percent) : 'Unavailable'}</span>
          </div>
          <div class="ops-progress"><span class="!bg-status-ok" style:width={percentWidth(hardware?.cpu_percent)}></span></div>
        </div>
      </div>
    </article>

    <article class="ops-card p-4">
      <div class="flex items-center justify-between">
        <span class="ops-label">Last Task</span>
        <TimerReset class="h-5 w-5 text-muted-foreground" />
      </div>
      {#if lastTask?.available}
        <div class="mt-7 grid grid-cols-2 gap-3">
          <div>
            <p class="text-xs text-muted-foreground">Input Tokens</p>
            <p class="ops-value text-xl">{taskMetric(lastTask, 'inputTokens')}</p>
          </div>
          <div>
            <p class="text-xs text-muted-foreground">Output Tokens</p>
            <p class="ops-value text-xl">{taskMetric(lastTask, 'outputTokens')}</p>
          </div>
          <div>
            <p class="text-xs text-muted-foreground">Generation</p>
            <p class="ops-value text-xl">{lastTask.generationTps ? formatTPS(lastTask.generationTps) : 'Unavailable'}</p>
          </div>
          <div>
            <p class="text-xs text-muted-foreground">Duration</p>
            <p class="ops-value text-xl">{lastTask.totalDurationSeconds ? formatDuration(lastTask.totalDurationSeconds) : 'Unavailable'}</p>
          </div>
        </div>
      {:else}
        <div class="mt-6 flex h-40 flex-col items-center justify-center border border-dashed border-[#454936] bg-[#101211] text-center">
          <Clock3 class="mb-4 h-10 w-10 text-[#5a5f45]" />
          <p class="text-sm text-muted-foreground">Waiting for incoming requests...</p>
        </div>
      {/if}
    </article>
  </section>

  <DiagnosticsPanel />

  {#if data.alerts.length > 0}
    <section class="ops-section space-y-3">
      {#each data.alerts as alert}
        <div class="ops-banner {alert.level === 'error' ? 'ops-banner-danger' : ''}">
          <AlertTriangle class="mt-0.5 h-5 w-5 shrink-0 text-status-warn" />
          <div>
            <p class="font-semibold">{alert.title}</p>
            <p class="mt-1 text-sm text-muted-foreground">{alert.description}</p>
            <p class="mt-1 text-sm text-lemon">{alert.suggestion}</p>
          </div>
        </div>
      {/each}
    </section>
  {/if}

  <div class="flex items-center justify-end gap-2 text-xs text-muted-foreground">
    <RefreshCw class="h-3.5 w-3.5 {isLoading ? 'animate-spin' : ''}" />
    <span>Last refresh: {$lastRefresh ? $lastRefresh.toLocaleTimeString() : 'pending'}</span>
  </div>
</div>
