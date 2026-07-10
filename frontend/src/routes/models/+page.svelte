<script lang="ts">
  import { onMount } from 'svelte';
  import {
    models, loadedModel, modelsLoading, modelsError, modelsSource, refreshModels,
    pullAction, pullModel, unloadAction,
  } from '$lib/stores/models';
  import { capabilities } from '$lib/stores/capabilities';
  import { api } from '$lib/api/client';
  import { Activity, Clipboard, Download, Info, RefreshCw, Search, TriangleAlert } from 'lucide-svelte';
  import LoadModelDialog from '$lib/components/models/LoadModelDialog.svelte';
  import UnloadConfirmDialog from '$lib/components/models/UnloadConfirmDialog.svelte';
  import DeleteConfirmDialog from '$lib/components/models/DeleteConfirmDialog.svelte';
  import { notify } from '$lib/stores/notifications';
  import type { ModelEntry, RunEvidenceSeed } from '$lib/types';
  import { formatGB } from '$lib/utils/format';
  import { loadWorkflowDefaults } from '$lib/utils/workflowDefaults';

  let isRefreshing = false;
  let filter = '';
  let loadTarget: string | null = null;
  let loadTargetSize: number | null = null;
  let unloadTarget: string | null = null;
  let deleteTarget: string | null = null;
  let loadDialogOpen = false;
  let unloadDialogOpen = false;
  let deleteDialogOpen = false;
  let catalogLoaded = false;
  let smokeRunning = false;
  let latestSmoke: RunEvidenceSeed | null = null;

  onMount(() => {
    refreshModels();
  });

  $: filteredModels = $models.filter((model) =>
    model.name.toLowerCase().includes(filter.trim().toLowerCase())
  );
  $: remoteCount = $models.filter((model) => !model.downloaded).length;
  $: downloadedCount = $models.filter((model) => model.downloaded).length;
  $: sourceLabel = formatSourceLabel($modelsSource);

  async function handleRefresh() {
    isRefreshing = true;
    await refreshModels();
    catalogLoaded = false;
    isRefreshing = false;
  }

  async function handleCatalogRefresh() {
    isRefreshing = true;
    await refreshModels(true);
    catalogLoaded = true;
    isRefreshing = false;
  }

  async function copyCli(name: string) {
    const command = `lemonade load ${name}`;
    await navigator.clipboard?.writeText(command);
    notify.info('CLI copied', command, { toastOnly: true, toastDuration: 2200 });
  }

  function openLoad(model: ModelEntry) {
    loadTarget = model.name;
    loadTargetSize = model.size;
    loadDialogOpen = true;
  }

  function openUnload(name: string) {
    unloadTarget = name;
    unloadDialogOpen = true;
  }

  function openDelete(name: string) {
    deleteTarget = name;
    deleteDialogOpen = true;
  }

  async function downloadModel(model: ModelEntry) {
    const confirmed = window.confirm(
      `Download "${model.name}" through Lemonade?\n\n` +
      'This may be a large download and can take a while. The model will be installed into Lemonade storage.',
    );
    if (!confirmed) return;
    await pullModel(model.name);
  }

  async function runSmokeTest() {
    const modelName = $loadedModel?.name;
    if (!modelName) return;
    smokeRunning = true;
    try {
      const defaults = loadWorkflowDefaults();
      const result = await api.lemonade.smokeTest({
        model_name: modelName,
        max_tokens: Math.min(defaults.maxOutputTokens, 256),
        temperature: defaults.temperature,
        app_timeout_seconds: defaults.appTimeoutSeconds,
        stop_sequences: defaults.stopSequences,
      });
      if (result.ok) {
        latestSmoke = result.data.evidence;
        if (result.data.success) {
          notify.success('Smoke test passed', `${formatTPS(result.data.evidence.generation_tps)} · ${result.data.evidence.total_seconds.toFixed(2)}s`);
        } else {
          notify.error('Smoke test failed', result.data.evidence.error ?? result.data.message);
        }
      } else {
        notify.error('Smoke test failed', result.error);
      }
    } finally {
      smokeRunning = false;
    }
  }

  $: if (!loadDialogOpen) {
    loadTarget = null;
    loadTargetSize = null;
  }
  $: if (!unloadDialogOpen) unloadTarget = null;
  $: if (!deleteDialogOpen) deleteTarget = null;

  function modelFormat(model: ModelEntry): string {
    const details = model.details ?? {};
    const format = details.format as string | undefined;
    const quant = details.quantization_level as string | undefined;
    const family = details.family as string | undefined;
    return [format, quant || family].filter(Boolean).join('/') || 'Unknown';
  }

  function formatSourceLabel(source: string): string {
    if (source === 'merged_catalog') return 'local inventory + Lemonade catalog';
    if (source === 'openai_models') return 'Lemonade catalog';
    if (source === 'ollama_tags') return 'local inventory';
    return 'no source';
  }

  function formatTPS(value: number): string {
    return value > 0 ? `${value.toFixed(1)} tok/s` : 'unknown';
  }

  function formatEvidenceValue(value: number | null, unit = ''): string {
    if (value === null || !Number.isFinite(value)) return 'unknown';
    return `${value.toLocaleString()}${unit}`;
  }
</script>

<div class="space-y-6">
  <section class="ops-panel">
    <div class="ops-card-header">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-3">
          <h2 class="ops-title">Active Model</h2>
          {#if $loadedModel}
            <span class="ops-badge ops-badge-ok">Active</span>
          {:else}
            <span class="ops-badge">None</span>
          {/if}
        </div>
        <p class="mt-3 break-all ops-value text-lemon">
          {$loadedModel?.name ?? 'No model is currently loaded'}
        </p>
      </div>
      <div class="flex flex-wrap justify-end gap-2">
        {#if $loadedModel}
          <button class="ops-button" type="button" on:click={() => copyCli($loadedModel?.name ?? '')}>
            <Clipboard class="h-4 w-4" />
            CLI
          </button>
          <a class="ops-button" href="/system" title="Inspect runtime process details">
            <Info class="h-4 w-4" />
            Details
          </a>
          <button class="ops-button ops-button-primary" type="button" on:click={runSmokeTest} disabled={smokeRunning}>
            <Activity class="h-4 w-4 {smokeRunning ? 'animate-pulse' : ''}" />
            {smokeRunning ? 'Testing' : 'Smoke Test'}
          </button>
          <button
            class="ops-button ops-button-danger"
            type="button"
            on:click={() => $loadedModel?.name && openUnload($loadedModel.name)}
            disabled={$unloadAction.loading}
          >
            <TriangleAlert class="h-4 w-4" />
            {$unloadAction.loading ? 'Unloading' : 'Unload'}
          </button>
        {/if}
        <button class="ops-button" type="button" on:click={handleRefresh} disabled={isRefreshing}>
          <RefreshCw class="h-4 w-4 {isRefreshing ? 'animate-spin' : ''}" />
          Refresh
        </button>
      </div>
    </div>

    {#if latestSmoke}
      <div class="border-t border-[#30342b] p-5">
        <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="ops-label">Latest Run Evidence Seed</h3>
              <span class="ops-badge {latestSmoke.success ? 'ops-badge-ok' : 'ops-badge-danger'}">
                {latestSmoke.success ? 'passed' : 'failed'}
              </span>
              {#if latestSmoke.completion_error_kind}
                <span class="ops-badge ops-badge-danger">{latestSmoke.completion_error_kind}</span>
              {/if}
            </div>
            <p class="ops-muted mt-2 break-all text-sm">{latestSmoke.response_text || latestSmoke.error || 'No response text captured.'}</p>
          </div>
          <span class="ops-muted text-xs">{new Date(latestSmoke.timestamp).toLocaleString()}</span>
        </div>
        <dl class="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4 xl:grid-cols-10">
          <div>
            <dt class="ops-label">TTFT</dt>
            <dd class="ops-value mt-1">{latestSmoke.ttft_seconds.toFixed(3)}s</dd>
          </div>
          <div>
            <dt class="ops-label">TPS</dt>
            <dd class="ops-value mt-1">{formatTPS(latestSmoke.generation_tps)}</dd>
          </div>
          <div>
            <dt class="ops-label">tokens</dt>
            <dd class="ops-value mt-1">{latestSmoke.input_tokens}/{latestSmoke.output_tokens}</dd>
          </div>
          <div>
            <dt class="ops-label">finish</dt>
            <dd class="ops-value mt-1">{latestSmoke.finish_reason}</dd>
          </div>
          <div>
            <dt class="ops-label">backend</dt>
            <dd class="ops-value mt-1">{latestSmoke.observed_backend ?? 'unknown'}</dd>
          </div>
          <div>
            <dt class="ops-label">ctx</dt>
            <dd class="ops-value mt-1">{formatEvidenceValue(latestSmoke.observed_ctx_size)}</dd>
          </div>
          <div>
            <dt class="ops-label">PID</dt>
            <dd class="ops-value mt-1">{latestSmoke.observed_pid ?? 'unknown'}</dd>
          </div>
          <div>
            <dt class="ops-label">RAM delta</dt>
            <dd class="ops-value mt-1">
              {latestSmoke.ram_used_before_gb !== null && latestSmoke.ram_used_after_gb !== null
                ? `${(latestSmoke.ram_used_after_gb - latestSmoke.ram_used_before_gb).toFixed(1)} GB`
                : 'unknown'}
            </dd>
          </div>
          <div>
            <dt class="ops-label">endpoint</dt>
            <dd class="ops-value mt-1 break-all">{latestSmoke.completion_endpoint ?? 'unknown'}</dd>
          </div>
          <div>
            <dt class="ops-label">token source</dt>
            <dd class="ops-value mt-1">{latestSmoke.token_count_source}</dd>
          </div>
        </dl>
        {#if latestSmoke.warnings.length > 0}
          <div class="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            {#each latestSmoke.warnings as warning}
              <div class="border border-[#4b4f39] bg-[#171a18] p-3 text-sm text-status-warn">{warning}</div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <div class="grid grid-cols-1 gap-8 p-5 lg:grid-cols-2">
      <div>
        <h3 class="ops-label mb-4">Runtime Parameters</h3>
        {#if $loadedModel?.params}
          <dl class="space-y-3 text-sm">
            <div class="flex justify-between gap-4">
              <dt class="ops-muted">backend</dt>
              <dd class="ops-value">{$loadedModel.params.backend ?? 'unknown'}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="ops-muted">context_size</dt>
              <dd class="ops-value">{$loadedModel.params.ctxSize?.toLocaleString() ?? 'unknown'}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="ops-muted">gpu_layers</dt>
              <dd class="ops-value">{$loadedModel.params.ngl ?? 'unknown'}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="ops-muted">mmap</dt>
              <dd class="ops-value">{$loadedModel.params.mmap === null ? 'unknown' : $loadedModel.params.mmap ? 'on' : 'off'}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="ops-muted">reasoning</dt>
              <dd class="ops-value">{$loadedModel.params.reasoningFormat ?? 'auto'}</dd>
            </div>
          </dl>
        {:else}
          <p class="text-sm text-muted-foreground">Runtime parameters are unavailable until llama-server is detected.</p>
        {/if}
      </div>

      <div>
        <h3 class="ops-label mb-4">Process Telemetry</h3>
        {#if $loadedModel?.process}
          <dl class="space-y-3 text-sm">
            <div class="flex justify-between gap-4">
              <dt class="ops-muted">PID</dt>
              <dd class="ops-value">{$loadedModel.process.pid}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="ops-muted">RSS Memory</dt>
              <dd class="ops-value">{formatGB($loadedModel.process.rssGb)}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="ops-muted">CPU Usage</dt>
              <dd class="ops-value">{$loadedModel.process.cpuPercent.toFixed(1)}%</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="ops-muted">Uptime</dt>
              <dd class="ops-value">{$loadedModel.process.uptime}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="ops-muted">Throughput</dt>
              <dd class="ops-value">Unknown</dd>
            </div>
          </dl>
        {:else}
          <p class="text-sm text-muted-foreground">No process telemetry available.</p>
        {/if}
      </div>
    </div>
  </section>

  {#if $modelsError}
    <section class="ops-banner ops-banner-danger">
      <TriangleAlert class="mt-0.5 h-5 w-5 shrink-0" />
      <p class="text-sm">{$modelsError}</p>
    </section>
  {/if}

  <section class="ops-panel">
    <div class="ops-card-header">
      <div>
        <h2 class="ops-title">Model Inventory</h2>
        <p class="ops-subtitle">
          {catalogLoaded
            ? `${downloadedCount} downloaded, ${remoteCount} remote from ${sourceLabel}.`
            : 'Local models. Refresh remote catalog to search downloadable models.'}
        </p>
      </div>
      <div class="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
        <button class="ops-button whitespace-nowrap" type="button" on:click={handleCatalogRefresh} disabled={isRefreshing}>
          <RefreshCw class="h-4 w-4 {isRefreshing ? 'animate-spin' : ''}" />
          Refresh Remote Catalog
        </button>
        <label class="relative block w-full max-w-xs">
          <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input class="ops-input ops-input-icon-left" placeholder="Filter models..." bind:value={filter} />
        </label>
      </div>
    </div>

    {#if $modelsLoading}
      <div class="p-8 text-sm text-muted-foreground">Loading model inventory...</div>
    {:else if filteredModels.length === 0}
      <div class="p-8 text-sm text-muted-foreground">No matching models found.</div>
    {:else}
      <div class="overflow-x-auto">
        <table class="ops-table">
          <thead>
            <tr>
              <th>Model Name</th>
              <th>Format</th>
              <th class="text-right">Size</th>
              <th>Status</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each filteredModels as model (model.name)}
              <tr class="hover:bg-[#1f221f]">
                <td class="ops-value break-all">{model.name}</td>
                <td class="ops-value">{modelFormat(model)}</td>
                <td class="text-right ops-value">{model.sizeFormatted}</td>
                <td>
                  {#if model.isLoaded}
                    <span class="ops-badge ops-badge-ok">Active</span>
                  {:else if model.downloaded}
                    <span class="ops-badge">Downloaded</span>
                  {:else}
                    <span class="ops-badge ops-badge-warn">Remote</span>
                  {/if}
                </td>
                <td>
                  <div class="flex justify-end gap-2">
                    {#if !model.downloaded}
                      <button
                        class="ops-button ops-button-primary"
                        type="button"
                        on:click={() => downloadModel(model)}
                        disabled={!$capabilities.pull || $pullAction.loading}
                      >
                        <Download class="h-4 w-4 {$pullAction.loading && $pullAction.modelName === model.name ? 'animate-pulse' : ''}" />
                        {$pullAction.loading && $pullAction.modelName === model.name ? 'Downloading' : 'Download'}
                      </button>
                    {:else}
                      <a class="ops-button" href={`/models/${encodeURIComponent(model.name)}${model.size ? `?size=${model.size}` : ''}`}>
                        Profiles
                      </a>
                      {#if model.isLoaded}
                        <button class="ops-button" type="button" disabled>In Use</button>
                      {:else}
                        <button class="ops-button ops-button-primary" type="button" on:click={() => openLoad(model)}>
                          Load
                        </button>
                      {/if}
                      {#if $capabilities.delete_enabled && !model.isLoaded}
                        <button class="ops-button ops-button-danger" type="button" on:click={() => openDelete(model.name)}>
                          Delete
                        </button>
                      {/if}
                    {/if}
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
</div>

{#if loadTarget}
  <LoadModelDialog modelName={loadTarget} modelSizeBytes={loadTargetSize} bind:open={loadDialogOpen} />
{/if}

{#if unloadTarget}
  <UnloadConfirmDialog modelName={unloadTarget} bind:open={unloadDialogOpen} />
{/if}

{#if deleteTarget}
  <DeleteConfirmDialog modelName={deleteTarget} bind:open={deleteDialogOpen} />
{/if}
