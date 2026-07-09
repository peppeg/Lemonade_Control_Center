<!--
  ModelActions — Action buttons for a model row.
  Shows different buttons depending on loaded state and capabilities.
-->
<script lang="ts">
  import { Button } from '$lib/components/ui/button';
  import LoadModelDialog from './LoadModelDialog.svelte';
  import UnloadConfirmDialog from './UnloadConfirmDialog.svelte';
  import DeleteConfirmDialog from './DeleteConfirmDialog.svelte';
  import CopyMenu from './CopyMenu.svelte';
  import { loadAction, unloadAction } from '$lib/stores/models';
  import type { ModelEntry } from '$lib/types';

  export let model: ModelEntry;
  export let deleteEnabled: boolean = false;

  let showLoadDialog = false;
  let showUnloadDialog = false;
  let showDeleteDialog = false;
</script>

<div class="flex items-center gap-1 justify-end">
  {#if model.isLoaded}
    <Button
      variant="ghost"
      size="sm"
      class="h-7 text-xs"
      on:click={() => showUnloadDialog = true}
      disabled={$unloadAction.loading}
    >
      Unload
    </Button>
  {:else}
    <Button
      variant="ghost"
      size="sm"
      class="h-7 text-xs"
      on:click={() => showLoadDialog = true}
      disabled={$loadAction.loading}
    >
      Load
    </Button>

    {#if deleteEnabled}
      <Button
        variant="ghost"
        size="sm"
        class="h-7 text-xs text-destructive hover:text-destructive"
        on:click={() => showDeleteDialog = true}
      >
        🗑
      </Button>
    {/if}
  {/if}

  <CopyMenu modelName={model.name} />
</div>

<LoadModelDialog modelName={model.name} modelSizeBytes={model.size} bind:open={showLoadDialog} />
<UnloadConfirmDialog modelName={model.name} bind:open={showUnloadDialog} />
{#if deleteEnabled}
  <DeleteConfirmDialog modelName={model.name} bind:open={showDeleteDialog} />
{/if}
