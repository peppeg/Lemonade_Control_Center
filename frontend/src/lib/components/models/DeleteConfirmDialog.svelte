<!--
  DeleteConfirmDialog — Double confirmation: user must type the model name.
-->
<script lang="ts">
  import ModalFrame from './ModalFrame.svelte';
  import { Button } from '$lib/components/ui/button';
  import { deleteModel, deleteAction } from '$lib/stores/models';
  import { AlertTriangle, Loader2 } from 'lucide-svelte';

  export let modelName: string;
  export let open: boolean = false;

  let confirmText = '';

  $: canDelete = confirmText === modelName;

  async function handleDelete() {
    if (!canDelete) return;
    const success = await deleteModel(modelName);
    if (success) {
      open = false;
      confirmText = '';
    }
  }

  function handleClose() {
    confirmText = '';
    open = false;
  }
</script>

<ModalFrame
  {open}
  title="Delete Model"
  description="This will permanently delete the model files from disk. This action cannot be undone."
  widthClass="sm:max-w-[450px]"
  on:close={handleClose}
>

    <div class="space-y-3 py-2">
      <div class="flex items-center gap-2 rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2">
        <AlertTriangle class="h-4 w-4 shrink-0 text-destructive" />
        <p class="text-xs font-mono text-destructive break-all">{modelName}</p>
      </div>

      <div class="space-y-1.5">
        <label for="delete-confirm-input" class="text-sm font-medium">
          Type the model name to confirm:
        </label>
        <input
          id="delete-confirm-input"
          type="text"
          bind:value={confirmText}
          placeholder={modelName}
          class="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm font-mono
                 focus:outline-none focus:ring-2 focus:ring-destructive/50"
          spellcheck="false"
        />
      </div>
    </div>

    {#if $deleteAction.error}
      <div class="rounded-md bg-status-error/10 border border-status-error/30 px-3 py-2 text-xs text-status-error">
        {$deleteAction.error}
      </div>
    {/if}

    <div class="mt-5 flex items-center justify-end gap-2">
      <Button variant="outline" on:click={handleClose}>Cancel</Button>
      <Button
        variant="destructive"
        on:click={handleDelete}
        disabled={!canDelete || $deleteAction.loading}
      >
        {#if $deleteAction.loading}
          <Loader2 class="h-4 w-4 mr-2 animate-spin" /> Deleting…
        {:else}
          Delete permanently
        {/if}
      </Button>
    </div>
</ModalFrame>
