<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { Download, Pause, Play, RefreshCw, Trash2 } from 'lucide-svelte';
  import ChartPanel from '$lib/components/hardware/ChartPanel.svelte';
  import SvgBarChart from '$lib/components/hardware/SvgBarChart.svelte';
  import SvgLineChart from '$lib/components/hardware/SvgLineChart.svelte';
  import {
    clearMetricsHistory,
    connectMetricsWs,
    disconnectMetricsWs,
    exportTasksCsv,
    loadMetrics,
    metricsLoading,
    metricsPaused,
    metricsWsConnected,
    setTimeRange,
    taskHistory,
    timeRange,
    timeSeriesData,
    toggleMetricsPause,
  } from '$lib/stores/metrics';
  import type { MetricPoint, TimeRange } from '$lib/types';

  const ranges: TimeRange[] = [5, 15, 30];

  onMount(() => {
    loadMetrics();
    connectMetricsWs();
  });

  onDestroy(() => {
    disconnectMetricsWs();
  });

  $: labels = $timeSeriesData.map(formatTime);
  $: ramValues = $timeSeriesData.map((point) => point.ram_used);
  $: ramTotal = latest($timeSeriesData)?.ram_total ?? 0;
  $: cpuValues = $timeSeriesData.map((point) => point.cpu_pct);
  $: gpuValues = $timeSeriesData.map((point) => point.gpu_load_pct).filter((value): value is number => typeof value === 'number');
  $: tempValues = $timeSeriesData.map(primaryTemperature).filter((value): value is number => typeof value === 'number');
  $: gpuTempValues = $timeSeriesData.map((point) => point.gpu_temp_c).filter((value): value is number => typeof value === 'number');
  $: tpsValues = $taskHistory.map((task) => task.gen_tps);
  $: ttftValues = $taskHistory.map((task) => task.ttft_seconds);
  $: throughputValues = $taskHistory.map((task) => task.output_tokens);
  $: taskLabels = $taskHistory.map((task) => new Date(task.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));

  function latest(points: MetricPoint[]): MetricPoint | null {
    return points.at(-1) ?? null;
  }

  function formatTime(point: MetricPoint): string {
    return new Date(parseMetricTimestamp(point.t)).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function primaryTemperature(point: MetricPoint): number | null {
    const values = Object.values(point.temps);
    if (values.length === 0) return null;
    return Math.max(...values);
  }

  function parseMetricTimestamp(value: string): number {
    const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
    return new Date(hasTimezone ? value : `${value}Z`).getTime();
  }
</script>

<div class="space-y-5">
  <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
    <div>
      <h1 class="text-3xl font-bold">Hardware Monitor</h1>
      <p class="mt-2 max-w-3xl text-sm text-muted-foreground">
        Real-time time-series metrics for RAM, CPU, GPU load, thermals, and task performance.
      </p>
    </div>
    <div class="flex flex-wrap gap-2">
      <div class="flex gap-1 rounded border border-[#444936] bg-[#2b2d2a] p-1">
        {#each ranges as range}
          <button
            class="rounded px-3 py-2 ops-mono text-xs {$timeRange === range ? 'bg-[#4a4d49] text-lemon' : 'text-[#e3e5d3] hover:bg-[#363935]'}"
            type="button"
            on:click={() => setTimeRange(range)}
          >
            {range}m
          </button>
        {/each}
      </div>
      <button class="ops-button" type="button" on:click={toggleMetricsPause}>
        {#if $metricsPaused}<Play class="h-4 w-4" /> Resume{:else}<Pause class="h-4 w-4" /> Pause{/if}
      </button>
      <button class="ops-button" type="button" on:click={loadMetrics} disabled={$metricsLoading}>
        <RefreshCw class="h-4 w-4 {$metricsLoading ? 'animate-spin' : ''}" />
        Refresh
      </button>
      <button class="ops-button" type="button" on:click={exportTasksCsv}>
        <Download class="h-4 w-4" />
        Export CSV
      </button>
      <button class="ops-button ops-button-danger" type="button" on:click={clearMetricsHistory}>
        <Trash2 class="h-4 w-4" />
        Clear
      </button>
    </div>
  </div>

  <section class="ops-panel px-4 py-3">
    <div class="flex flex-wrap gap-x-8 gap-y-2 text-sm">
      <span class="ops-muted">Stream: <span class="ops-value {$metricsWsConnected ? 'text-status-ok' : 'text-status-warn'}">{$metricsWsConnected ? 'live' : 'offline'}</span></span>
      <span class="ops-muted">Samples: <span class="ops-value">{$timeSeriesData.length}</span></span>
      <span class="ops-muted">Tasks: <span class="ops-value">{$taskHistory.length}</span></span>
    </div>
  </section>

  <section class="grid grid-cols-1 gap-4 xl:grid-cols-2">
    <ChartPanel title="RAM" value={latest($timeSeriesData) ? `${latest($timeSeriesData)?.ram_used.toFixed(1)} / ${latest($timeSeriesData)?.ram_total.toFixed(1)} GB` : 'No data'}>
      <SvgLineChart title="RAM usage" values={ramValues} {labels} yMax={ramTotal || null} unit=" GB" />
    </ChartPanel>

    <ChartPanel title="CPU" value={latest($timeSeriesData) ? `${latest($timeSeriesData)?.cpu_pct.toFixed(1)}%` : 'No data'}>
      <SvgLineChart title="CPU usage" values={cpuValues} {labels} yMax={100} unit="%" color="#40f078" />
    </ChartPanel>

    <ChartPanel title="Temperature" value={tempValues.at(-1) !== undefined ? `${tempValues.at(-1)?.toFixed(1)} C` : 'No sensors'}>
      <SvgLineChart title="Temperature" values={tempValues} {labels} yMax={100} unit=" C" color="#f2c94c" />
    </ChartPanel>

    <ChartPanel title="GPU Load" value={gpuValues.at(-1) !== undefined ? `${gpuValues.at(-1)?.toFixed(1)}%${gpuTempValues.at(-1) !== undefined ? ` / ${gpuTempValues.at(-1)?.toFixed(1)} C` : ''}` : 'No data'}>
      <SvgLineChart title="GPU load" values={gpuValues} {labels} yMax={100} unit="%" color="#ffb84d" />
    </ChartPanel>

    <ChartPanel title="TPS per Task" value={tpsValues.at(-1) !== undefined ? `${tpsValues.at(-1)?.toFixed(1)} t/s` : 'No tasks'}>
      <SvgBarChart title="TPS per task" values={tpsValues} labels={taskLabels} unit=" t/s" color="#d8ff00" />
    </ChartPanel>

    <ChartPanel title="TTFT per Task" value={ttftValues.at(-1) !== undefined ? `${ttftValues.at(-1)?.toFixed(2)}s` : 'No tasks'}>
      <SvgBarChart title="TTFT per task" values={ttftValues} labels={taskLabels} unit="s" color="#ffb0a8" />
    </ChartPanel>

    <div class="xl:col-span-2">
      <ChartPanel title="Token Throughput" value={throughputValues.at(-1) !== undefined ? `${throughputValues.at(-1)} output tokens` : 'No tasks'}>
        <SvgLineChart title="Output tokens per task" values={throughputValues} labels={taskLabels} color="#efff7a" />
      </ChartPanel>
    </div>
  </section>
</div>
