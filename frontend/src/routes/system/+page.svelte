<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { capabilities } from '$lib/stores/capabilities';
  import { notify } from '$lib/stores/notifications';
  import { unloadModel, unloadAction } from '$lib/stores/models';
  import { AlertTriangle, Bug, Cpu, Download, HardDrive, RefreshCw, Server, Thermometer } from 'lucide-svelte';
  import type { HardwareInfo } from '$lib/types';
  import { formatDuration, formatGB, formatPercent } from '$lib/utils/format';

  interface TemperatureReading {
    label: string;
    current: number;
    high?: number | null;
    critical?: number | null;
  }

  interface ProcessInfo {
    pid: number;
    name?: string;
    cpu_percent: number;
    rss_gb: number;
    vms_gb?: number;
    status?: string;
    uptime_seconds?: number | null;
  }

  interface LlamaServerInfo {
    found: boolean;
    process: ProcessInfo | null;
    params: Record<string, unknown> | null;
  }

  interface TopProcess {
    pid: number;
    name: string;
    rss_gb: number;
    cpu_percent: number;
  }

  let hardware: HardwareInfo | null = null;
  let temperatures: TemperatureReading[] = [];
  let tempsAvailable = false;
  let llamaServer: LlamaServerInfo | null = null;
  let processes: TopProcess[] = [];
  let serviceStatus = 'unknown';
  let loading = true;
  let error: string | null = null;
  let restartMessage: string | null = null;
  let restartLoading = false;
  let confirmStopUnload = false;

  $: canRestartService = $capabilities.cmd_systemctl && $capabilities.restart_enabled;

  onMount(() => {
    refreshSystem();
  });

  async function refreshSystem() {
    loading = true;
    error = null;

    const [hardwareResult, tempResult, llamaResult, processResult, serviceResult] = await Promise.all([
      api.system.hardware(),
      api.system.temperatures(),
      api.system.llamaServer(),
      api.system.processes(),
      api.system.service(),
    ]);

    if (hardwareResult.ok) hardware = hardwareResult.data;
    else error = hardwareResult.error;

    if (tempResult.ok) {
      temperatures = tempResult.data.readings as TemperatureReading[];
      tempsAvailable = tempResult.data.available;
    }

    if (llamaResult.ok) llamaServer = llamaResult.data as LlamaServerInfo;
    if (processResult.ok) processes = processResult.data.processes as TopProcess[];
    if (serviceResult.ok) serviceStatus = serviceResult.data.status;

    loading = false;
  }

  function percentWidth(value: number | null | undefined): string {
    if (typeof value !== 'number') return '0%';
    return `${Math.max(0, Math.min(100, value))}%`;
  }

  function bytesLabel(used: number | null | undefined, total: number | null | undefined): string {
    if (typeof used !== 'number' || typeof total !== 'number') return 'Unavailable';
    return `${used.toFixed(1)} GB / ${total.toFixed(1)} GB`;
  }

  async function restartService() {
    restartLoading = true;
    restartMessage = null;
    const result = await api.system.restart();
    restartMessage = result.ok ? result.data.message : result.error;
    if (result.ok) {
      notify.warning('Service restart requested', result.data.message || 'lemond.service restart command completed.', { href: '/system' });
    } else {
      notify.error('Service restart failed', result.error || 'systemctl restart failed.', { href: '/system' });
    }
    restartLoading = false;
    await refreshSystem();
  }

  async function stopAndUnload() {
    confirmStopUnload = false;
    const success = await unloadModel(undefined, { suppressNotification: true });
    if (success) {
      notify.warning('Emergency unload complete', 'The active model was unloaded from System recovery.', { href: '/system' });
    } else {
      notify.error('Emergency unload failed', $unloadAction.error || 'Lemonade rejected the unload request.', { href: '/system' });
    }
    await refreshSystem();
  }

  function commandLine(params: Record<string, unknown> | null | undefined): string {
    const raw = params?.raw_cmdline;
    return typeof raw === 'string' && raw.trim() ? raw : 'Command line unavailable.';
  }
</script>

<div class="space-y-4">
  {#if error}
    <section class="ops-banner ops-banner-danger">{error}</section>
  {/if}

  <section class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
    <article class="ops-card p-5">
      <div class="flex justify-between">
        <span class="ops-label">System RAM</span>
        <span>{hardware ? formatPercent(hardware.ram_percent) : 'Unavailable'}</span>
      </div>
      <div class="ops-progress mt-4"><span style:width={percentWidth(hardware?.ram_percent)}></span></div>
      <p class="mt-4 text-right ops-value">{hardware ? bytesLabel(hardware.ram_used_gb, hardware.ram_total_gb) : 'Unavailable'}</p>
      <div class="mt-3 flex justify-between text-xs text-muted-foreground">
        <span>Swap</span>
        <span class="ops-value">{hardware ? bytesLabel(hardware.swap_used_gb, hardware.swap_total_gb) : 'Unavailable'}</span>
      </div>
    </article>
    <article class="ops-card p-5">
      <div class="flex justify-between">
        <span class="ops-label">CPU Load</span>
        <span>{hardware ? formatPercent(hardware.cpu_percent) : 'Unavailable'}</span>
      </div>
      <div class="ops-progress mt-4"><span style:width={percentWidth(hardware?.cpu_percent)}></span></div>
      <p class="mt-4 text-right ops-value">{hardware ? `${hardware.cpu_count} logical cores` : 'Unavailable'}</p>
    </article>
    <article class="ops-card p-5">
      <div class="flex justify-between">
        <span class="ops-label">Root Disk</span>
        <span>{hardware?.disk_percent !== null && hardware?.disk_percent !== undefined ? formatPercent(hardware.disk_percent) : 'Unavailable'}</span>
      </div>
      <div class="ops-progress mt-4"><span style:width={percentWidth(hardware?.disk_percent)}></span></div>
      <p class="mt-4 text-right ops-value">{hardware ? bytesLabel(hardware.disk_used_gb, hardware.disk_total_gb) : 'Unavailable'}</p>
    </article>
    <article class="ops-card p-5">
      <div class="flex justify-between">
        <span class="ops-label">GPU Load</span>
        <span>{hardware?.gpu_available && typeof hardware.gpu_load_percent === 'number' ? formatPercent(hardware.gpu_load_percent) : 'Unavailable'}</span>
      </div>
      <div class="ops-progress mt-4"><span class="!bg-status-warn" style:width={percentWidth(hardware?.gpu_load_percent)}></span></div>
      <p class="mt-4 text-right ops-value">
        {hardware?.gpu_available && typeof hardware.gpu_temp_c === 'number' ? `${hardware.gpu_temp_c.toFixed(1)} C` : 'Temp unavailable'}
      </p>
    </article>
  </section>

  <section class="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_2fr]">
    <article class="ops-panel">
      <div class="ops-card-header justify-start gap-3">
        <Thermometer class="h-5 w-5" />
        <h2 class="ops-title">Thermals</h2>
      </div>
      <div class="p-5">
        {#if !tempsAvailable || temperatures.length === 0}
          <p class="text-sm text-muted-foreground">Temperature sensors are unavailable on this system.</p>
        {:else}
          <div class="divide-y divide-[#34382d]">
            {#each temperatures as reading}
              <div class="grid grid-cols-[1fr_auto_auto_auto] gap-4 py-3 text-sm">
                <span>{reading.label}</span>
                <span class="ops-value">{reading.current.toFixed(1)} C</span>
                <span class="text-muted-foreground">{reading.high ? `${reading.high.toFixed(1)} high` : 'high --'}</span>
                <span class="text-muted-foreground">{reading.critical ? `${reading.critical.toFixed(1)} crit` : 'crit --'}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </article>

    <article class="ops-panel">
      <div class="ops-card-header">
        <div class="flex items-center gap-3">
          <Cpu class="h-5 w-5 text-lemon" />
          <h2 class="ops-title">llama-server</h2>
          <span class="ops-badge {llamaServer?.found ? 'ops-badge-ok' : 'ops-badge-warn'}">{llamaServer?.found ? 'Running' : 'Not Found'}</span>
        </div>
        <span class="ops-value">PID: {llamaServer?.process?.pid ?? 'Unavailable'}</span>
      </div>

      <div class="grid grid-cols-2 gap-5 border-b border-[#34382d] p-5 md:grid-cols-4">
        <div>
          <span class="ops-label">RSS Memory</span>
          <p class="mt-2 ops-value text-xl">{llamaServer?.process ? formatGB(llamaServer.process.rss_gb) : 'Unavailable'}</p>
        </div>
        <div>
          <span class="ops-label">VMS</span>
          <p class="mt-2 ops-value text-xl">{llamaServer?.process?.vms_gb ? formatGB(llamaServer.process.vms_gb) : 'Unavailable'}</p>
        </div>
        <div>
          <span class="ops-label">CPU Usage</span>
          <p class="mt-2 ops-value text-xl">{llamaServer?.process ? `${llamaServer.process.cpu_percent.toFixed(1)}%` : 'Unavailable'}</p>
        </div>
        <div>
          <span class="ops-label">Uptime</span>
          <p class="mt-2 ops-value text-xl">{llamaServer?.process?.uptime_seconds ? formatDuration(llamaServer.process.uptime_seconds) : 'Unavailable'}</p>
        </div>
      </div>

      <details class="p-5">
        <summary class="cursor-pointer ops-label">Command Line</summary>
        <pre class="ops-terminal mt-4 max-h-36 overflow-auto p-3 whitespace-pre-wrap">{commandLine(llamaServer?.params)}</pre>
      </details>
    </article>
  </section>

  <section class="ops-panel">
    <div class="ops-card-header">
      <h2 class="text-lg font-bold">Top Processes (by RAM)</h2>
      <button class="ops-button" type="button" on:click={refreshSystem} disabled={loading}>
        <RefreshCw class="h-4 w-4 {loading ? 'animate-spin' : ''}" />
        Refresh
      </button>
    </div>
    <div class="overflow-x-auto">
      <table class="ops-table">
        <thead>
          <tr>
            <th>PID</th>
            <th>Command</th>
            <th class="text-right">RES</th>
            <th class="text-right">%CPU</th>
          </tr>
        </thead>
        <tbody>
          {#if processes.length === 0}
            <tr><td colspan="4" class="text-muted-foreground">No process data available.</td></tr>
          {:else}
            {#each processes as process}
              <tr>
                <td class="ops-value">{process.pid}</td>
                <td class="ops-value">{process.name}</td>
                <td class="text-right ops-value">{formatGB(process.rss_gb)}</td>
                <td class="text-right ops-value">{process.cpu_percent.toFixed(1)}</td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>
  </section>

  <section class="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
    <article class="ops-panel border-[#7a4742] bg-[#1b1312] p-6">
      <div class="flex items-start gap-4">
        <AlertTriangle class="mt-1 h-7 w-7 shrink-0 text-danger" />
        <div>
          <h2 class="text-2xl font-bold text-danger">Emergency Recovery</h2>
          <p class="mt-2 max-w-3xl text-sm text-[#ffcec8]">
            Stop & Unload interrupts active inference by unloading the current model. Restart Service restarts lemond.service and should only be used when the system is unresponsive or models fail to unload cleanly.
          </p>
          <p class="mt-2 text-xs text-muted-foreground">Service status: <span class="ops-value">{serviceStatus}</span></p>
          {#if !$capabilities.cmd_systemctl}
            <p class="mt-2 text-sm text-status-warn">Restart Service is unavailable because systemctl is not available.</p>
          {:else if !$capabilities.restart_enabled}
            <p class="mt-2 text-sm text-status-warn">Restart Service is disabled. Set <code class="ops-mono">ENABLE_RESTART=true</code> in the backend environment to enable it.</p>
          {/if}
          {#if restartMessage}
            <p class="mt-2 text-sm text-muted-foreground">{restartMessage}</p>
          {/if}
          <div class="mt-6 flex flex-wrap gap-4">
            {#if confirmStopUnload}
              <button class="ops-button ops-button-danger bg-[#ffb0a8] text-[#20100e] hover:bg-[#ffc4be]" type="button" on:click={stopAndUnload} disabled={$unloadAction.loading}>
                <Server class="h-4 w-4" />
                {$unloadAction.loading ? 'Unloading' : 'Confirm Unload'}
              </button>
              <button class="ops-button" type="button" on:click={() => confirmStopUnload = false}>Cancel</button>
            {:else}
              <button class="ops-button ops-button-danger" type="button" on:click={() => confirmStopUnload = true} disabled={$unloadAction.loading}>
                <Server class="h-4 w-4" />
                Stop & Unload
              </button>
            {/if}
            <button class="ops-button ops-button-danger bg-[#ffb0a8] text-[#20100e] hover:bg-[#ffc4be]" type="button" on:click={restartService} disabled={!canRestartService || restartLoading}>
              <RefreshCw class="h-4 w-4 {restartLoading ? 'animate-spin' : ''}" />
              Restart Service
            </button>
          </div>
        </div>
      </div>
    </article>

    <article class="ops-panel p-6">
      <div class="flex items-center gap-3">
        <Bug class="h-6 w-6 text-muted-foreground" />
        <h2 class="text-2xl font-bold">Diagnostics</h2>
      </div>
      <p class="mt-3 text-sm text-muted-foreground">
        Generate a snapshot of current logs, process states, and configuration probes for support.
      </p>
      <a class="ops-button mt-8 w-full" href={api.diagnosticBundleUrl()} download>
        <Download class="h-4 w-4" />
        Download .zip
      </a>
    </article>
  </section>
</div>
