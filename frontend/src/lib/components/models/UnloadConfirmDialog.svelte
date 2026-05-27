<script lang="ts">
  import ModalFrame from './ModalFrame.svelte';
  import { Button } from '$lib/components/ui/button';
  import { unloadModel, unloadAction } from '$lib/stores/models';
  import { Loader2 } from 'lucide-svelte';

  export let modelName: string;
  export let open: boolean = false;

  async function handleUnload() {
    const success = await unloadModel(modelName);
    if (success) open = false;
  }
</script>

<ModalFrame
  {open}
  title="Unload Model"
  description={`This will unload ${modelName} from memory. Any ongoing generation will be interrupted.`}
  widthClass="sm:max-w-[400px]"
  on:close={() => (open = false)}
>

    {#if $unloadAction.error}
      <div class="rounded-md bg-status-error/10 border border-status-error/30 px-3 py-2 text-xs text-status-error">
        {$unloadAction.error}
      </div>
    {/if}

    <div class="mt-5 flex items-center justify-end gap-2">
      <Button variant="outline" on:click={() => open = false}>Cancel</Button>
      <Button
        variant="destructive"
        on:click={handleUnload}
        disabled={$unloadAction.loading}
      >
        {#if $unloadAction.loading}
          <Loader2 class="h-4 w-4 mr-2 animate-spin" /> Unloading…
        {:else}
          Unload
        {/if}
      </Button>
    </div>
</ModalFrame>
