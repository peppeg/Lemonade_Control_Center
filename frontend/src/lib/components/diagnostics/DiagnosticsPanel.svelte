<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { Activity, ArrowRight, RefreshCw } from 'lucide-svelte';
  import {
    diagnosticReport,
    diagnosticsLastRun,
    diagnosticsLoading,
    runDiagnostics,
    startDiagnosticsPolling,
    stopDiagnosticsPolling,
  } from '$lib/stores/diagnostics';
  import AlertCard from './AlertCard.svelte';

  onMount(() => {
    startDiagnosticsPolling(30_000);
  });

  onDestroy(() => {
    stopDiagnosticsPolling();
  });

  $: alerts = $diagnosticReport?.alerts ?? [];
  $: topAlerts = alerts.slice(0, 3);
</script>

<section class="ops-panel">
  <div class="ops-card-header">
    <div class="flex items-center gap-3">
      <Activity class="h-5 w-5 text-lemon" />
      <div>
        <h2 class="ops-title">Diagnostics</h2>
        <p class="ops-subtitle">
          {$diagnosticReport
            ? `${$diagnosticReport.warnings} warnings, ${$diagnosticReport.errors} critical, ${$diagnosticReport.passed}/${$diagnosticReport.total_rules} rules passed`
            : 'No diagnostic report yet'}
        </p>
      </div>
    </div>
    <button class="ops-button" type="button" on:click={() => runDiagnostics(true)} disabled={$diagnosticsLoading}>
      <RefreshCw class="h-4 w-4 {$diagnosticsLoading ? 'animate-spin' : ''}" />
      Run
    </button>
  </div>

  <div class="space-y-3 p-5">
    {#if topAlerts.length === 0}
      <p class="text-sm text-muted-foreground">No active diagnostic alerts.</p>
    {:else}
      {#each topAlerts as alert (alert.rule_id)}
        <AlertCard {alert} compact />
      {/each}
    {/if}
    <div class="flex items-center justify-between text-xs text-muted-foreground">
      <span>Last check: {$diagnosticsLastRun ? $diagnosticsLastRun.toLocaleTimeString() : 'pending'}</span>
      <a class="inline-flex items-center gap-1 text-lemon hover:text-lemon-light" href="/diagnostics">
        View all diagnostics
        <ArrowRight class="h-3.5 w-3.5" />
      </a>
    </div>
  </div>
</section>
