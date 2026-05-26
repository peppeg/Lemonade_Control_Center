<script lang="ts">
  import { onMount } from 'svelte';
  import {
    models, loadedModel, modelsLoading, modelsError, refreshModels,
  } from '$lib/stores/models';
  import { capabilities } from '$lib/stores/capabilities';
  import { Cpu, RefreshCw } from 'lucide-svelte';
  import { Button } from '$lib/components/ui/button';
  import PageHeader from '$lib/components/shared/PageHeader.svelte';
  import LoadedModelPanel from '$lib/components/models/LoadedModelPanel.svelte';
  import ModelsTable from '$lib/components/models/ModelsTable.svelte';

  let isRefreshing = false;

  onMount(() => {
    refreshModels();
  });

  async function handleRefresh() {
    isRefreshing = true;
    await refreshModels();
    isRefreshing = false;
  }

</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="flex items-start justify-between gap-4">
    <PageHeader
      title="Models"
      description="Manage downloaded models — load, unload, configure, and delete."
      icon={Cpu}
    />
    <Button
      variant="outline"
      size="sm"
      class="shrink-0"
      on:click={handleRefresh}
      disabled={isRefreshing}
    >
      <RefreshCw class="h-3.5 w-5 mr-1.5 {isRefreshing ? 'animate-spin' : ''}" />
      Refresh
    </Button>
  </div>

  <!-- Error banner -->
  {#if $modelsError}
    <div class="rounded-md bg-status-error/10 border border-status-error/30 px-4 py-3 text-sm text-status-error">
      {$modelsError}
    </div>
  {/if}

  <!-- Loaded Model Panel (if any) -->
  {#if $loadedModel}
    <LoadedModelPanel model={$loadedModel} />
  {/if}

  <!-- All Models Table -->
  <ModelsTable
    models={$models}
    loading={$modelsLoading}
    deleteEnabled={$capabilities.delete_enabled}
  />
</div>
