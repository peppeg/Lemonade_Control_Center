<script lang="ts">
  import { onMount } from 'svelte';
  import { Activity, RefreshCw } from 'lucide-svelte';
  import AlertCard from '$lib/components/diagnostics/AlertCard.svelte';
  import {
    diagnosticHistory,
    diagnosticReport,
    diagnosticsError,
    diagnosticsLastRun,
    diagnosticsLoading,
    loadDiagnosticHistory,
    runDiagnostics,
  } from '$lib/stores/diagnostics';

  type Tab = 'active' | 'history' | 'rules';
  let activeTab: Tab = 'active';

  onMount(() => {
    runDiagnostics(false);
    loadDiagnosticHistory();
  });
</script>

<div class="space-y-5">
  <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
    <div>
      <div class="flex items-center gap-3">
        <Activity class="h-7 w-7 text-lemon" />
        <h1 class="text-3xl font-bold">Diagnostics</h1>
      </div>
      <p class="mt-2 max-w-3xl text-sm text-muted-foreground">
        Active alerts, rule results, and state transitions from the diagnostic engine.
      </p>
    </div>
    <button class="ops-button ops-button-primary" type="button" on:click={() => runDiagnostics(true)} disabled={$diagnosticsLoading}>
      <RefreshCw class="h-4 w-4 {$diagnosticsLoading ? 'animate-spin' : ''}" />
      Re-run
    </button>
  </div>

  {#if $diagnosticsError}
    <section class="ops-banner ops-banner-danger">{$diagnosticsError}</section>
  {/if}

  <section class="grid grid-cols-2 gap-4 md:grid-cols-4">
    <article class="ops-card p-4">
      <span class="ops-label">Active Alerts</span>
      <p class="mt-2 ops-value text-2xl">{$diagnosticReport?.alerts.length ?? 0}</p>
    </article>
    <article class="ops-card p-4">
      <span class="ops-label">Warnings</span>
      <p class="mt-2 ops-value text-2xl text-status-warn">{$diagnosticReport?.warnings ?? 0}</p>
    </article>
    <article class="ops-card p-4">
      <span class="ops-label">Critical</span>
      <p class="mt-2 ops-value text-2xl text-status-error">{$diagnosticReport?.errors ?? 0}</p>
    </article>
    <article class="ops-card p-4">
      <span class="ops-label">Rules Passed</span>
      <p class="mt-2 ops-value text-2xl">{$diagnosticReport ? `${$diagnosticReport.passed}/${$diagnosticReport.total_rules}` : '0/0'}</p>
    </article>
  </section>

  <div class="flex flex-wrap gap-2 rounded border border-[#444936] bg-[#2b2d2a] p-1">
    <button class="rounded px-4 py-2 ops-mono text-sm {activeTab === 'active' ? 'bg-[#4a4d49] text-lemon' : 'text-[#e3e5d3] hover:bg-[#363935]'}" type="button" on:click={() => activeTab = 'active'}>Active</button>
    <button class="rounded px-4 py-2 ops-mono text-sm {activeTab === 'history' ? 'bg-[#4a4d49] text-lemon' : 'text-[#e3e5d3] hover:bg-[#363935]'}" type="button" on:click={() => activeTab = 'history'}>History</button>
    <button class="rounded px-4 py-2 ops-mono text-sm {activeTab === 'rules' ? 'bg-[#4a4d49] text-lemon' : 'text-[#e3e5d3] hover:bg-[#363935]'}" type="button" on:click={() => activeTab = 'rules'}>All Rules</button>
  </div>

  {#if activeTab === 'active'}
    <section class="space-y-3">
      {#if !$diagnosticReport}
        <p class="text-sm text-muted-foreground">Diagnostics have not run yet.</p>
      {:else if $diagnosticReport.alerts.length === 0}
        <div class="ops-banner ops-banner-muted">No active diagnostic alerts.</div>
      {:else}
        {#each $diagnosticReport.alerts as alert (alert.rule_id)}
          <AlertCard {alert} />
        {/each}
      {/if}
    </section>
  {:else if activeTab === 'history'}
    <section class="ops-panel">
      <div class="ops-card-header">
        <h2 class="ops-title">Alert Timeline</h2>
        <span class="text-xs text-muted-foreground">Last run: {$diagnosticsLastRun ? $diagnosticsLastRun.toLocaleTimeString() : 'pending'}</span>
      </div>
      <div class="divide-y divide-[#30342b]">
        {#if $diagnosticHistory.length === 0}
          <p class="p-5 text-sm text-muted-foreground">No history entries yet.</p>
        {:else}
          {#each $diagnosticHistory as entry}
            <div class="grid grid-cols-[120px_120px_1fr] gap-4 p-4 text-sm">
              <span class="ops-value">{new Date(entry.timestamp).toLocaleTimeString()}</span>
              <span class="ops-badge">{entry.event}</span>
              <span>{entry.title}</span>
            </div>
          {/each}
        {/if}
      </div>
    </section>
  {:else}
    <section class="ops-panel">
      <div class="ops-card-header">
        <h2 class="ops-title">Rules Overview</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="ops-table">
          <thead>
            <tr>
              <th>Rule</th>
              <th>Status</th>
              <th>Description</th>
              <th class="text-right">Time</th>
            </tr>
          </thead>
          <tbody>
            {#each $diagnosticReport?.results ?? [] as result}
              <tr>
                <td class="ops-value">{result.rule_id}</td>
                <td>
                  <span class="ops-badge {result.passed ? 'ops-badge-ok' : 'ops-badge-warn'}">{result.passed ? 'Passed' : 'Triggered'}</span>
                </td>
                <td>{result.description}</td>
                <td class="text-right ops-value">{result.execution_time_ms.toFixed(1)} ms</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </section>
  {/if}
</div>
