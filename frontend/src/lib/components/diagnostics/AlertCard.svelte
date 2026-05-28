<script lang="ts">
  import { ChevronDown, ChevronRight, X } from 'lucide-svelte';
  import { dismissDiagnostic } from '$lib/stores/diagnostics';
  import type { DiagnosticAlert } from '$lib/types';

  export let alert: DiagnosticAlert;
  export let compact = false;

  let open = !compact;

  $: severityClass = {
    critical: 'ops-banner-danger',
    high: 'ops-banner-danger',
    medium: 'ops-banner-muted',
    low: 'ops-banner-muted',
    info: 'ops-banner-muted',
  }[alert.severity];
</script>

<article class="ops-banner {severityClass}">
  <button class="mt-0.5 text-muted-foreground hover:text-foreground" type="button" on:click={() => open = !open} aria-label="Toggle alert details">
    {#if open}
      <ChevronDown class="h-4 w-4" />
    {:else}
      <ChevronRight class="h-4 w-4" />
    {/if}
  </button>
  <div class="min-w-0 flex-1">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="ops-badge {alert.severity === 'critical' || alert.severity === 'high' ? 'ops-badge-danger' : alert.severity === 'medium' ? 'ops-badge-warn' : ''}">
            {alert.severity}
          </span>
          <p class="font-semibold">{alert.title}</p>
        </div>
        <p class="mt-2 text-sm text-muted-foreground">{alert.description}</p>
      </div>
      <button class="ops-button" type="button" on:click={() => dismissDiagnostic(alert.rule_id)}>
        <X class="h-4 w-4" />
        Dismiss
      </button>
    </div>

    {#if open}
      <div class="mt-4 grid grid-cols-1 gap-3 text-sm lg:grid-cols-2">
        <div class="ops-card p-3">
          <span class="ops-label">Impact</span>
          <p class="mt-2 text-muted-foreground">{alert.impact}</p>
        </div>
        <div class="ops-card p-3">
          <span class="ops-label">Suggestion</span>
          <p class="mt-2 text-lemon">{alert.suggestion}</p>
        </div>
      </div>
      {#if Object.keys(alert.evidence).length > 0}
        <pre class="ops-terminal mt-3 max-h-44 overflow-auto p-3">{JSON.stringify(alert.evidence, null, 2)}</pre>
      {/if}
    {/if}
  </div>
</article>
