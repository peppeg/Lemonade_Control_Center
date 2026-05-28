<script lang="ts">
  import { AlertTriangle, Info, Sparkles } from 'lucide-svelte';
  import type { SmartRecommendation } from '$lib/types';
  import { formatGB } from '$lib/utils/format';

  export let data: SmartRecommendation;

  function ctxLabel(ctx: number): string {
    return ctx >= 1024 ? `${Math.round(ctx / 1024)}K` : String(ctx);
  }
</script>

<section class="ops-panel p-5">
  <div class="flex items-center gap-3">
    <Sparkles class="h-5 w-5 text-lemon" />
    <div>
      <h2 class="ops-title">Smart Recommendation</h2>
      <p class="ops-subtitle">Hardware-aware context guidance for this model.</p>
    </div>
  </div>

  <div class="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
    <div class="ops-card p-4">
      <span class="ops-label">Recommended ctx_size</span>
      <p class="mt-2 ops-value text-2xl text-lemon">{ctxLabel(data.recommended_ctx)}</p>
    </div>
    <div class="ops-card p-4">
      <span class="ops-label">Safe Max</span>
      <p class="mt-2 ops-value text-2xl">{ctxLabel(data.safe_max_ctx)}</p>
    </div>
    <div class="ops-card p-4">
      <span class="ops-label">Risk Threshold</span>
      <p class="mt-2 ops-value text-2xl text-status-warn">{ctxLabel(data.risk_threshold_ctx)}</p>
    </div>
  </div>

  <div class="mt-5 flex flex-wrap gap-3 text-sm text-muted-foreground">
    {#if data.model_size_gb}
      <span>Model: <strong class="ops-value">~{formatGB(data.model_size_gb)}</strong></span>
    {/if}
    <span>RAM: <strong class="ops-value">{formatGB(data.ram_total_gb)}</strong></span>
    <span>Available: <strong class="ops-value">{formatGB(data.ram_available_gb)}</strong></span>
  </div>

  {#if data.warnings.length > 0 || data.notes.length > 0}
    <div class="mt-5 space-y-2">
      {#each data.warnings as warning}
        <div class="ops-banner ops-banner-muted py-3 text-sm text-status-warn">
          <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" />
          <span>{warning}</span>
        </div>
      {/each}
      {#each data.notes as note}
        <div class="ops-banner ops-banner-muted py-3 text-sm">
          <Info class="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <span>{note}</span>
        </div>
      {/each}
    </div>
  {/if}
</section>
