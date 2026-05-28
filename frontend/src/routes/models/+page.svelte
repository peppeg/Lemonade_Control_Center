<script lang="ts">
  import { onMount } from 'svelte';
  import {
    models, loadedModel, modelsLoading, modelsError, refreshModels,
    unloadAction,
  } from '$lib/stores/models';
  import { capabilities } from '$lib/stores/capabilities';
  import { Clipboard, Info, RefreshCw, Search, TriangleAlert } from 'lucide-svelte';
  import LoadModelDialog from '$lib/components/models/LoadModelDialog.svelte';
  import UnloadConfirmDialog from '$lib/components/models/UnloadConfirmDialog.svelte';
  import DeleteConfirmDialog from '$lib/components/models/DeleteConfirmDialog.svelte';
  import { notify } from '$lib/stores/notifications';
  import type { ModelEntry } from '$lib/types';
  import { formatGB } from '$lib/utils/format';

  let isRefreshing = false;
  let filter = '';
  let loadTarget: string | null = null;
  let unloadTarget: string | null = null;
  let deleteTarget: string | null = null;
  let loadDialogOpen = false;
  let unloadDialogOpen = false;
  let deleteDialogOpen = false;

  onMount(() => {
    refreshModels();
  });

  $: filteredModels = $models.filter((model) =>
    model.name.toLowerCase().includes(filter.trim().toLowerCase())
  );

  async function handleRefresh() {
    isRefreshing = true;
    await refreshModels();
    isRefreshing = false;
  }

  async function copyCli(name: string) {
    const command = `lemonade load ${name}`;
    await navigator.clipboard?.writeText(command);
    notify.info('CLI copied', command, { toastOnly: true, toastDuration: 2200 });
  }

  function openLoad(name: string) {
    loadTarget = name;
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

  $: if (!loadDialogOpen) loadTarget = null;
  $: if (!unloadDialogOpen) unloadTarget = null;
  $: if (!deleteDialogOpen) deleteTarget = null;

  function modelFormat(model: ModelEntry): string {
    const details = model.details ?? {};
    const format = details.format as string | undefined;
    const quant = details.quantization_level as string | undefined;
    const family = details.family as string | undefined;
    return [format, quant || family].filter(Boolean).join('/') || 'Unknown';
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
          <button class="ops-button" type="button" title="Inspect runtime parameters">
            <Info class="h-4 w-4" />
            Details
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
      <h2 class="ops-title">Local Inventory</h2>
      <label class="relative block w-full max-w-xs">
        <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input class="ops-input pl-9" placeholder="Filter models..." bind:value={filter} />
      </label>
    </div>

    {#if $modelsLoading}
      <div class="p-8 text-sm text-muted-foreground">Loading local inventory...</div>
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
                  {:else}
                    <span class="ops-badge">Available</span>
                  {/if}
                </td>
                <td>
                  <div class="flex justify-end gap-2">
                    {#if model.isLoaded}
                      <button class="ops-button" type="button" disabled>In Use</button>
                    {:else}
                      <button class="ops-button ops-button-primary" type="button" on:click={() => openLoad(model.name)}>
                        Load
                      </button>
                    {/if}
                    {#if $capabilities.delete_enabled && !model.isLoaded}
                      <button class="ops-button ops-button-danger" type="button" on:click={() => openDelete(model.name)}>
                        Delete
                      </button>
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
  <LoadModelDialog modelName={loadTarget} bind:open={loadDialogOpen} />
{/if}

{#if unloadTarget}
  <UnloadConfirmDialog modelName={unloadTarget} bind:open={unloadDialogOpen} />
{/if}

{#if deleteTarget}
  <DeleteConfirmDialog modelName={deleteTarget} bind:open={deleteDialogOpen} />
{/if}
