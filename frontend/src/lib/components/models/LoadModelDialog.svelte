<!--
  LoadModelDialog — Dialog to load a model with optional config.
  Allows setting ctx_size, backend, and extra args.
-->
<script lang="ts">
  import ModalFrame from './ModalFrame.svelte';
  import { Button } from '$lib/components/ui/button';
  import { loadModel, loadAction } from '$lib/stores/models';
  import { Loader2 } from 'lucide-svelte';

  export let modelName: string;
  export let open: boolean = false;

  // Form state
  let ctxSize: number | null = null;
  let selectedCtx: string = 'default';
  let backend: string = 'auto';
  let llamacppArgs: string = '';
  let saveOptions: boolean = false;

  const ctxPresets = [
    { label: 'Default', value: 'default', size: null },
    { label: '8K', value: '8k', size: 8192, desc: 'Safe' },
    { label: '16K', value: '16k', size: 16384, desc: 'Coding' },
    { label: '32K', value: '32k', size: 32768, desc: 'Long' },
    { label: '64K', value: '64k', size: 65536, desc: 'Stress' },
    { label: '128K', value: '128k', size: 131072, desc: 'Experimental' },
    { label: 'Custom', value: 'custom', size: null },
  ];

  const backends = [
    { value: 'auto', label: 'Auto' },
    { value: 'vulkan', label: 'Vulkan' },
    { value: 'rocm', label: 'ROCm' },
    { value: 'cpu', label: 'CPU' },
  ];

  $: {
    if (selectedCtx === 'custom') {
      // Keep custom value
    } else if (selectedCtx === 'default') {
      ctxSize = null;
    } else {
      const preset = ctxPresets.find(p => p.value === selectedCtx);
      ctxSize = preset?.size ?? null;
    }
  }

  async function handleLoad() {
    const success = await loadModel({
      modelName,
      ctxSize: selectedCtx === 'default' ? null : ctxSize,
      llamacppBackend: backend === 'auto' ? null : backend,
      llamacppArgs,
      saveOptions,
    });
    if (success) {
      open = false;
      resetForm();
    }
  }

  function resetForm() {
    ctxSize = null;
    selectedCtx = 'default';
    backend = 'auto';
    llamacppArgs = '';
    saveOptions = false;
  }
</script>

<ModalFrame
  {open}
  title="Load Model"
  description={modelName}
  widthClass="sm:max-w-[480px]"
  on:close={() => {
    open = false;
    resetForm();
  }}
>

    <div class="space-y-5 py-2">
      <!-- Context Size -->
      <div class="space-y-2">
        <label class="text-sm font-medium">Context Size</label>
        <div class="flex flex-wrap gap-1.5">
          {#each ctxPresets as preset}
            <Button
              variant={selectedCtx === preset.value ? 'default' : 'outline'}
              size="sm"
              class="h-7 text-xs {selectedCtx === preset.value ? 'bg-lemon text-black hover:bg-lemon-dark' : ''}"
              on:click={() => selectedCtx = preset.value}
            >
              {preset.label}
              {#if preset.desc}
                <span class="text-[9px] opacity-70 ml-1">{preset.desc}</span>
              {/if}
            </Button>
          {/each}
        </div>
        {#if selectedCtx === 'custom'}
          <input
            type="number"
            bind:value={ctxSize}
            placeholder="e.g. 32768"
            class="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm
                   focus:outline-none focus:ring-2 focus:ring-lemon/50"
          />
        {/if}
      </div>

      <!-- Backend -->
      <div class="space-y-2">
        <label class="text-sm font-medium">Backend</label>
        <div class="flex gap-1.5">
          {#each backends as b}
            <Button
              variant={backend === b.value ? 'default' : 'outline'}
              size="sm"
              class="h-7 text-xs {backend === b.value ? 'bg-lemon text-black hover:bg-lemon-dark' : ''}"
              on:click={() => backend = b.value}
            >
              {b.label}
            </Button>
          {/each}
        </div>
      </div>

      <!-- Extra Args (advanced) -->
      <div class="space-y-2">
        <label class="text-sm font-medium">Extra llama.cpp args <span class="text-muted-foreground font-normal">(optional)</span></label>
        <input
          type="text"
          bind:value={llamacppArgs}
          placeholder="e.g. --no-mmap --keep 256"
          class="w-full rounded-md border border-border bg-background px-3 py-1.5 text-sm font-mono
                 focus:outline-none focus:ring-2 focus:ring-lemon/50"
        />
      </div>

      <!-- Save options checkbox -->
      <label class="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" bind:checked={saveOptions}
               class="rounded border-border" />
        <span class="text-sm text-muted-foreground">Save as default for this model</span>
      </label>
    </div>

    {#if $loadAction.error}
      <div class="rounded-md bg-status-error/10 border border-status-error/30 px-3 py-2 text-xs text-status-error">
        {$loadAction.error}
      </div>
    {/if}

    <div class="mt-5 flex items-center justify-end gap-2">
      <Button
        variant="outline"
        on:click={() => {
          open = false;
          resetForm();
        }}
      >
        Cancel
      </Button>
      <Button
        on:click={handleLoad}
        disabled={$loadAction.loading}
        class="bg-lemon text-black hover:bg-lemon-dark"
      >
        {#if $loadAction.loading}
          <Loader2 class="h-4 w-4 mr-2 animate-spin" /> Loading…
        {:else}
          Load Model
        {/if}
      </Button>
    </div>
</ModalFrame>
