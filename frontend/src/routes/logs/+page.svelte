<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { Activity, Download, Gauge, Search, Timer, TimerReset } from 'lucide-svelte';
  import { formatDuration, formatNumber, formatTPS } from '$lib/utils/format';

  interface FinishReason {
    reason?: string;
    confidence?: string;
    evidence?: string;
  }

  interface LastTaskStats {
    available?: boolean;
    input_tokens?: number | null;
    output_tokens?: number | null;
    prompt_eval_tps?: number | null;
    generation_tps?: number | null;
    ttft_seconds?: number | null;
    total_duration_seconds?: number | null;
    finish_reason?: FinishReason;
    raw_log_lines?: string[];
  }

  interface LogEntry {
    timestamp?: string | null;
    level?: string;
    message?: string;
    raw?: string;
  }

  let lastTask: LastTaskStats | null = null;
  let logs: LogEntry[] = [];
  let loading = true;
  let error: string | null = null;
  let activeFilter = 'all';
  let activePanel: 'stats' | 'logs' = 'stats';
  let search = '';

  const filters = [
    { label: 'All', value: 'all' },
    { label: 'Error', value: 'error' },
    { label: 'Warning', value: 'warning' },
    { label: 'Perf', value: 'performance' },
    { label: 'Model', value: 'model' },
    { label: 'Gen', value: 'generation' },
  ];

  onMount(() => {
    refreshLogs();
  });

  $: filteredLogs = logs.filter((entry) => {
    const level = entry.level ?? 'info';
    const body = `${entry.message ?? ''} ${entry.raw ?? ''}`.toLowerCase();
    const matchesLevel = activeFilter === 'all' || level === activeFilter;
    const matchesSearch = search.trim() === '' || body.includes(search.trim().toLowerCase());
    return matchesLevel && matchesSearch;
  });

  async function refreshLogs() {
    loading = true;
    error = null;
    const [taskResult, logsResult] = await Promise.all([
      api.logs.lastTask(),
      api.logs.recent(200),
    ]);

    if (taskResult.ok) {
      lastTask = taskResult.data as LastTaskStats;
    } else {
      error = taskResult.error;
    }

    if (logsResult.ok) {
      logs = logsResult.data.entries as LogEntry[];
    } else {
      error = logsResult.error;
    }
    loading = false;
  }

  function metricNumber(value: number | null | undefined): string {
    if (typeof value !== 'number') return 'Unavailable';
    return formatNumber(value);
  }

  function durationMs(seconds: number | null | undefined): string {
    if (typeof seconds !== 'number') return 'Unavailable';
    if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
    return formatDuration(seconds);
  }

  function confidenceLabel(value: string | undefined): string {
    if (!value) return 'Unknown';
    if (value === 'confirmed') return 'Confirmed';
    if (value === 'inferred') return 'Inferred';
    return 'Unknown';
  }

  function levelClass(level: string | undefined): string {
    if (level === 'error') return 'text-danger';
    if (level === 'warning') return 'text-status-warn';
    if (level === 'performance') return 'text-[#76a9ff]';
    if (level === 'generation') return 'text-[#c28cff]';
    if (level === 'model') return 'text-lemon';
    return 'text-status-ok';
  }

  function exportLogs() {
    const text = filteredLogs.map((entry) => entry.raw || entry.message || '').join('\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `lcc-logs-${new Date().toISOString().slice(0, 19)}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
</script>

<div class="space-y-6">
  <section class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
    <div>
      <h2 class="ops-title">Performance & Telemetry</h2>
      <p class="ops-subtitle">Real execution metrics parsed from Lemonade logs.</p>
    </div>
    <div class="flex items-center gap-2 rounded border border-[#444936] bg-[#202321] p-1">
      <button
        class="rounded px-4 py-2 text-sm {activePanel === 'stats' ? 'bg-[#111312] text-foreground' : 'text-muted-foreground hover:bg-[#292c29] hover:text-foreground'}"
        type="button"
        on:click={() => activePanel = 'stats'}
      >
        Stats
      </button>
      <button
        class="rounded px-4 py-2 text-sm {activePanel === 'logs' ? 'bg-[#111312] text-foreground' : 'text-muted-foreground hover:bg-[#292c29] hover:text-foreground'}"
        type="button"
        on:click={() => activePanel = 'logs'}
      >
        Logs
      </button>
    </div>
  </section>

  {#if error}
    <section class="ops-banner ops-banner-danger">{error}</section>
  {/if}

  {#if activePanel === 'stats'}
    <section class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <article class="ops-card p-5">
        <div class="flex justify-between">
          <span class="ops-label">Input Tokens</span>
          <Activity class="h-4 w-4 text-muted-foreground" />
        </div>
        <p class="mt-5 ops-value text-3xl font-bold">{metricNumber(lastTask?.input_tokens)}</p>
        <p class="mt-4 text-sm text-muted-foreground">Last Task</p>
      </article>
      <article class="ops-card p-5">
        <div class="flex justify-between">
          <span class="ops-label">Output Tokens</span>
          <Activity class="h-4 w-4 text-muted-foreground" />
        </div>
        <p class="mt-5 ops-value text-3xl font-bold">{metricNumber(lastTask?.output_tokens)}</p>
        <p class="mt-4 text-sm text-muted-foreground">Last Task</p>
      </article>
      <article class="ops-card p-5">
        <div class="flex justify-between">
          <span class="ops-label">Time To First Token</span>
          <Timer class="h-4 w-4 text-muted-foreground" />
        </div>
        <p class="mt-5 ops-value text-3xl font-bold">{durationMs(lastTask?.ttft_seconds)}</p>
        <p class="mt-4 text-sm text-muted-foreground">TTFT</p>
      </article>
      <article class="ops-card p-5">
        <div class="flex justify-between">
          <span class="ops-label">Total Duration</span>
          <TimerReset class="h-4 w-4 text-muted-foreground" />
        </div>
        <p class="mt-5 ops-value text-3xl font-bold">{durationMs(lastTask?.total_duration_seconds)}</p>
        <p class="mt-4 text-sm text-muted-foreground">Last Task</p>
      </article>
    </section>

    <section class="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
      <article class="ops-panel">
        <div class="ops-card-header justify-start gap-3">
          <Gauge class="h-5 w-5 text-muted-foreground" />
          <h2 class="text-lg font-bold">Throughput Speeds</h2>
        </div>
        <div class="grid min-h-40 grid-cols-1 gap-8 p-6 md:grid-cols-2">
          <div class="md:border-r md:border-[#34382d]">
            <p class="text-sm">Prompt Evaluation</p>
            <p class="mt-2 ops-value text-3xl">{lastTask?.prompt_eval_tps ? formatTPS(lastTask.prompt_eval_tps) : 'Unavailable'}</p>
          </div>
          <div>
            <p class="text-sm">Generation Speed</p>
            <p class="mt-2 ops-value text-3xl">{lastTask?.generation_tps ? formatTPS(lastTask.generation_tps) : 'Unavailable'}</p>
          </div>
        </div>
      </article>

      <article class="ops-panel">
        <div class="ops-card-header justify-start gap-3">
          <Activity class="h-5 w-5 text-muted-foreground" />
          <h2 class="text-lg font-bold">Execution Result</h2>
        </div>
        <div class="space-y-5 p-5 text-sm">
          <div class="flex justify-between gap-4">
            <span>Finish Reason</span>
            <span class="ops-badge ops-badge-ok">{lastTask?.finish_reason?.reason ?? 'unknown'}</span>
          </div>
          <div class="flex justify-between gap-4">
            <span>Confidence</span>
            <span class="ops-value">{confidenceLabel(lastTask?.finish_reason?.confidence)}</span>
          </div>
          <div>
            <p>Evidence</p>
            <div class="mt-3 rounded border border-[#444936] bg-[#090a0a] p-3 ops-value">
              {lastTask?.finish_reason?.evidence || 'Unavailable'}
            </div>
          </div>
        </div>
      </article>
    </section>
  {/if}

  {#if activePanel === 'logs'}
    <section class="ops-panel overflow-hidden">
      <div class="flex flex-col gap-3 border-b border-[#34382d] p-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex flex-wrap gap-2">
          {#each filters as filter}
            <button
              class="rounded border px-4 py-2 text-sm {activeFilter === filter.value ? 'border-[#596044] bg-[#111312] text-foreground' : 'border-transparent text-muted-foreground hover:bg-[#222522]'}"
              type="button"
              on:click={() => activeFilter = filter.value}
            >
              {filter.label}
            </button>
          {/each}
        </div>

        <div class="flex flex-col gap-2 sm:flex-row">
          <label class="relative block">
            <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input class="ops-input min-w-64 pl-9" placeholder="Search logs..." bind:value={search} />
          </label>
          <button class="ops-button" type="button" on:click={exportLogs}>
            <Download class="h-4 w-4" />
            Export
          </button>
        </div>
      </div>

      <div class="ops-terminal min-h-[520px] overflow-auto p-4">
        {#if loading}
          <p class="text-muted-foreground">Loading logs...</p>
        {:else if filteredLogs.length === 0}
          <p class="text-muted-foreground">No logs matched the current filters.</p>
        {:else}
          {#each filteredLogs as entry}
            <div class="grid grid-cols-[120px_86px_1fr] gap-3 rounded px-2 py-0.5 {entry.level === 'error' ? 'bg-[#3a1d1b]' : ''}">
              <span class="text-muted-foreground">{entry.timestamp ?? '--:--:--'}</span>
              <span class={levelClass(entry.level)}>[{(entry.level ?? 'info').toUpperCase()}]</span>
              <span class="break-words">{entry.message ?? entry.raw}</span>
            </div>
          {/each}
        {/if}
      </div>
    </section>
  {/if}
</div>
