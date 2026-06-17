<!--
  LoadModelDialog — explicit Lemonade load planner.
  Structured controls are compiled into llamacpp_args before calling the backend.
-->
<script lang="ts">
  import ModalFrame from './ModalFrame.svelte';
  import { loadModel, loadAction } from '$lib/stores/models';
  import { AlertTriangle, Cpu, Loader2, Save, SlidersHorizontal, Terminal } from 'lucide-svelte';

  export let modelName: string;
  export let open = false;

  let ctxSize: number | null = null;
  let selectedCtx = 'default';
  let backend = 'auto';
  let flashAttention = false;
  let noContextShift = false;
  let mmapMode = 'default';
  let parallelSlots: number | null = null;
  let reasoningOff = false;
  let manualArgs = '';
  let mergeArgs = true;
  let saveOptions = false;

  const ctxPresets = [
    { label: 'Default', value: 'default', size: null, note: 'Lemonade' },
    { label: '8K', value: '8k', size: 8192, note: 'Safe' },
    { label: '16K', value: '16k', size: 16384, note: 'Coding' },
    { label: '32K', value: '32k', size: 32768, note: 'Long' },
    { label: '64K', value: '64k', size: 65536, note: 'Heavy' },
    { label: '128K', value: '128k', size: 131072, note: 'Stress' },
    { label: '256K', value: '256k', size: 262144, note: 'Extreme' },
    { label: 'Custom', value: 'custom', size: null, note: 'Manual' },
  ];

  const backendOptions = [
    { value: 'auto', label: 'auto' },
    { value: 'vulkan', label: 'vulkan' },
    { value: 'rocm', label: 'rocm' },
    { value: 'metal', label: 'metal' },
    { value: 'cpu', label: 'cpu' },
  ];

  const forbiddenManualArgFlags = [
    '-m',
    '--model',
    '--port',
    '--ctx-size',
    '-c',
    '-ngl',
    '--jinja',
    '--mmproj',
    '--embeddings',
    '--reranking',
  ];

  $: {
    if (selectedCtx === 'default') {
      ctxSize = null;
    } else if (selectedCtx !== 'custom') {
      const preset = ctxPresets.find((item) => item.value === selectedCtx);
      ctxSize = preset?.size ?? null;
    }
  }

  $: compiledArgs = buildArgs();
  $: blockedManualArgs = findForbiddenManualArgs(manualArgs);
  $: effectiveCtx = selectedCtx === 'default' ? null : ctxSize;
  $: canLoad = (selectedCtx === 'default' || Boolean(ctxSize && ctxSize > 0)) && blockedManualArgs.length === 0;

  async function handleLoad() {
    if (!canLoad) return;

    const success = await loadModel({
      modelName,
      ctxSize: effectiveCtx,
      llamacppBackend: backend === 'auto' ? null : backend,
      llamacppArgs: compiledArgs,
      mergeArgs,
      saveOptions,
    });

    if (success) {
      open = false;
      resetForm();
    }
  }

  function buildArgs(): string {
    const args: string[] = [];

    if (flashAttention) args.push('--flash-attn', 'on');
    if (mmapMode === 'on') args.push('--mmap');
    if (mmapMode === 'off') args.push('--no-mmap');
    if (parallelSlots !== null && parallelSlots > 0) args.push('-np', String(parallelSlots));
    if (noContextShift) args.push('--no-context-shift');
    if (reasoningOff) args.push('--reasoning', 'off');
    if (manualArgs.trim()) args.push(manualArgs.trim());

    return args.join(' ').trim();
  }

  function resetForm() {
    ctxSize = null;
    selectedCtx = 'default';
    backend = 'auto';
    flashAttention = false;
    noContextShift = false;
    mmapMode = 'default';
    parallelSlots = null;
    reasoningOff = false;
    manualArgs = '';
    mergeArgs = true;
    saveOptions = false;
  }

  function findForbiddenManualArgs(value: string): string[] {
    const tokens = value.match(/"[^"]*"|'[^']*'|\S+/g) ?? [];
    const blocked = new Set<string>();

    for (const rawToken of tokens) {
      const token = rawToken.replace(/^['"]|['"]$/g, '');
      const normalized = token.includes('=') ? token.split('=')[0] : token;
      if (forbiddenManualArgFlags.includes(normalized)) {
        blocked.add(normalized);
      }
    }

    return Array.from(blocked).sort();
  }

  function closeDialog() {
    open = false;
    resetForm();
  }
</script>

<ModalFrame
  {open}
  title="Load Model"
  description={modelName}
  widthClass="sm:max-w-[980px]"
  on:close={closeDialog}
>
  <div class="space-y-5">
    <section class="grid grid-cols-1 gap-3 md:grid-cols-3">
      <div class="border border-[#30342b] bg-[#111312] p-4">
        <div class="mb-3 flex items-center gap-2">
          <SlidersHorizontal class="h-4 w-4 text-lemon" />
          <h3 class="ops-label">Runtime Plan</h3>
        </div>
        <p class="ops-muted text-sm">Choose explicit load settings before sending the request to Lemonade.</p>
      </div>
      <div class="border border-[#30342b] bg-[#111312] p-4">
        <p class="ops-label">ctx_size</p>
        <p class="ops-value mt-2 text-lg">{effectiveCtx ? effectiveCtx.toLocaleString() : 'Default'}</p>
      </div>
      <div class="border border-[#30342b] bg-[#111312] p-4">
        <p class="ops-label">backend</p>
        <p class="ops-value mt-2 text-lg">{backend}</p>
      </div>
    </section>

    <section class="space-y-3">
      <div class="flex items-center justify-between gap-3">
        <div>
          <h3 class="ops-label">Context Window</h3>
          <p class="ops-subtitle">Large context sizes increase RAM and KV cache pressure.</p>
        </div>
        {#if selectedCtx === '128k' || selectedCtx === '256k'}
          <span class="ops-badge ops-badge-warn">Stress</span>
        {/if}
      </div>

      <div class="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
        {#each ctxPresets as preset}
          <button
            class="border px-3 py-3 text-left transition-colors {selectedCtx === preset.value ? 'border-lemon bg-[#d8ff00] text-[#111310]' : 'border-[#3f432d] bg-[#202320] text-foreground hover:border-[#6d744a] hover:bg-[#282c27]'}"
            type="button"
            on:click={() => selectedCtx = preset.value}
          >
            <span class="block font-mono text-sm font-bold uppercase">{preset.label}</span>
            <span class="mt-1 block text-[11px] uppercase opacity-75">{preset.note}</span>
          </button>
        {/each}
      </div>

      {#if selectedCtx === 'custom'}
        <label class="block space-y-2">
          <span class="ops-label">custom ctx_size</span>
          <input class="ops-input" type="number" min="1" bind:value={ctxSize} placeholder="262144" />
        </label>
      {/if}
    </section>

    <section class="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_1fr]">
      <div class="space-y-4 border border-[#30342b] bg-[#111312] p-4">
        <div class="flex items-center gap-2">
          <Cpu class="h-4 w-4 text-lemon" />
          <h3 class="ops-label">Backend & Memory</h3>
        </div>

        <label class="block space-y-2">
          <span class="ops-label">llamacpp_backend</span>
          <div class="ops-segmented">
            {#each backendOptions as option}
              <button
                class="ops-segment {backend === option.value ? 'ops-segment-active' : ''}"
                type="button"
                aria-pressed={backend === option.value}
                on:click={() => backend = option.value}
              >
                {option.label}
              </button>
            {/each}
          </div>
        </label>

        <fieldset class="space-y-2">
          <legend class="ops-label">memory map</legend>
          <div class="grid grid-cols-3 gap-2">
            {#each ['default', 'on', 'off'] as value}
              <button
                class="ops-button min-h-9 px-2 {mmapMode === value ? 'ops-button-primary' : ''}"
                type="button"
                on:click={() => mmapMode = value}
              >
                {value === 'on' ? '--mmap' : value === 'off' ? '--no-mmap' : 'default'}
              </button>
            {/each}
          </div>
        </fieldset>
      </div>

      <div class="space-y-4 border border-[#30342b] bg-[#111312] p-4">
        <div class="flex items-center gap-2">
          <Terminal class="h-4 w-4 text-lemon" />
          <h3 class="ops-label">Lemonade-safe llama.cpp args</h3>
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label class="block space-y-2">
            <span class="ops-label">parallel slots (-np)</span>
            <input class="ops-input" type="number" min="1" bind:value={parallelSlots} placeholder="1" />
          </label>
        </div>

        <div class="flex flex-wrap gap-2">
          <label class="flex min-h-10 items-center gap-3 border border-[#3f432d] bg-[#181b1a] px-3 py-2">
            <input type="checkbox" bind:checked={flashAttention} />
            <span class="ops-value whitespace-nowrap text-sm">--flash-attn</span>
          </label>
          <label class="flex min-h-10 items-center gap-3 border border-[#3f432d] bg-[#181b1a] px-3 py-2">
            <input type="checkbox" bind:checked={reasoningOff} />
            <span class="ops-value whitespace-nowrap text-sm">--reasoning off</span>
          </label>
          <label class="flex min-h-10 items-center gap-3 border border-[#3f432d] bg-[#181b1a] px-3 py-2">
            <input type="checkbox" bind:checked={noContextShift} />
            <span class="ops-value whitespace-nowrap text-sm">--no-context-shift</span>
          </label>
        </div>
      </div>
    </section>

    <section class="border border-[#30342b] bg-[#101211] p-3">
      <div class="mb-2 flex items-center gap-2">
        <AlertTriangle class="h-4 w-4 text-status-warn" />
        <span class="ops-label">Managed by Lemonade</span>
      </div>
      <p class="ops-muted text-sm">
        Model path, port, ctx-size flag, GPU layer split, chat template/Jinja, mmproj, embeddings and reranking flags are managed by Lemonade and are not sent through manual args.
      </p>
    </section>

    <section class="border border-[#30342b] bg-[#101211] p-3">
      <label class="flex items-start gap-3">
        <input class="mt-1" type="checkbox" bind:checked={mergeArgs} />
        <span>
          <span class="ops-value text-sm">Merge with global Lemonade args</span>
          <span class="ops-muted mt-1 block text-xs">
            When disabled, this load request replaces global llama.cpp args for the model.
          </span>
        </span>
      </label>
    </section>

    <section class="space-y-3">
      <label class="block space-y-2">
        <span class="ops-label">Advanced manual llamacpp_args</span>
        <textarea class="ops-textarea ops-mono" bind:value={manualArgs} placeholder="Advanced args, e.g. --no-context-shift"></textarea>
      </label>

      <div class="border border-[#30342b] bg-[#101211] p-3">
        <div class="mb-2 flex items-center gap-2">
          <Terminal class="h-4 w-4 text-lemon" />
          <span class="ops-label">compiled llamacpp_args</span>
        </div>
        <p class="ops-value min-h-6 break-all text-sm">{compiledArgs || 'none'}</p>
      </div>
    </section>

    <label class="flex items-start gap-3 border border-[#30342b] bg-[#111312] p-3">
      <input class="mt-1" type="checkbox" bind:checked={saveOptions} />
      <span>
        <span class="flex items-center gap-2 ops-value text-sm">
          <Save class="h-4 w-4 text-lemon" />
          Save as default for this model
        </span>
        <span class="ops-muted mt-1 block text-xs">Lemonade will persist these runtime options for future loads.</span>
      </span>
    </label>

    {#if !canLoad}
      <div class="flex gap-3 border border-[#5a4720] bg-[#2e2719] p-3 text-status-warn">
        <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" />
        <p class="text-sm">
          {blockedManualArgs.length > 0
            ? `Remove Lemonade-managed manual args: ${blockedManualArgs.join(', ')}.`
            : 'Custom ctx_size must be greater than zero.'}
        </p>
      </div>
    {/if}

    {#if $loadAction.error}
      <div class="flex gap-3 border border-[#70302d] bg-[#321715] p-3 text-status-error">
        <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0" />
        <p class="text-sm">{$loadAction.error}</p>
      </div>
    {/if}

    <div class="flex flex-col-reverse gap-2 border-t border-[#30342b] pt-4 sm:flex-row sm:justify-end">
      <button class="ops-button" type="button" on:click={closeDialog}>Cancel</button>
      <button class="ops-button ops-button-primary" type="button" on:click={handleLoad} disabled={$loadAction.loading || !canLoad}>
        {#if $loadAction.loading}
          <Loader2 class="h-4 w-4 animate-spin" />
          Loading
        {:else}
          Load Model
        {/if}
      </button>
    </div>
  </div>
</ModalFrame>
