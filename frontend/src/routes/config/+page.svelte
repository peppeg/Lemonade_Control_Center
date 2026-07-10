<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { notify } from '$lib/stores/notifications';
  import { loadWorkflowDefaults, resetWorkflowDefaults, saveWorkflowDefaults } from '$lib/utils/workflowDefaults';
  import { AlertCircle, ServerCog, SlidersHorizontal } from 'lucide-svelte';

  type PresetName = 'Safe' | 'Coding' | 'Long Context' | 'Stress' | 'Executor Strict';

  const presets: PresetName[] = ['Safe', 'Coding', 'Long Context', 'Stress', 'Executor Strict'];
  const tokenOptions = [256, 1024, 2048, 4096];
  const backendOptions = ['auto', 'rocm', 'vulkan', 'cpu', 'cuda'];

  let activePreset: string = 'Coding';
  let runtimeConfig: Record<string, unknown> = {};
  let runtimeError: string | null = null;
  let runtimeReadable = false;
  let runtimeLoading = true;
  let runtimeSaving = false;

  let contextSize = 128000;
  let globalTimeoutSeconds = 300;
  let primaryBackend = 'auto';

  let maxOutputTokens = 2048;
  let temperature = 0.7;
  let appTimeoutSeconds = 300;
  let stopSequences = ['<|im_end|>', '\\n\\nUser:'];
  let newStopSequence = '';
  let localMessage: string | null = null;

  $: canWriteRuntime = runtimeReadable && !runtimeLoading && !runtimeError;

  onMount(() => {
    loadLocalDefaults();
    loadRuntimeConfig();
  });

  async function loadRuntimeConfig() {
    runtimeLoading = true;
    runtimeError = null;

    const result = await api.lemonade.getConfig();
    if (result.ok && result.data.available) {
      runtimeConfig = result.data.raw ?? {};
      contextSize = Number(runtimeConfig.ctx_size ?? runtimeConfig.context_size ?? contextSize);
      globalTimeoutSeconds = Number(runtimeConfig.global_timeout ?? globalTimeoutSeconds);
      const llamacppConfig = runtimeConfig.llamacpp as Record<string, unknown> | undefined;
      primaryBackend = String(
        llamacppConfig?.backend
          ?? runtimeConfig['llamacpp.backend']
          ?? runtimeConfig.llamacpp_backend
          ?? runtimeConfig.backend
          ?? primaryBackend
      );
      runtimeReadable = true;
    } else {
      runtimeReadable = false;
      runtimeError = result.ok
        ? 'Runtime Config returned unavailable.'
        : result.error || 'LEMONADE_ADMIN_API_KEY is missing or /internal/config is unavailable.';
    }
    runtimeLoading = false;
  }

  async function saveRuntimeConfig() {
    if (!canWriteRuntime) return;
    runtimeSaving = true;
    runtimeError = null;

    const updates = {
      ctx_size: contextSize,
      global_timeout: globalTimeoutSeconds,
      'llamacpp.backend': primaryBackend,
    };

    const result = await api.lemonade.setConfig(updates);
    if (result.ok) {
      const currentLlamacpp = runtimeConfig.llamacpp as Record<string, unknown> | undefined;
      runtimeConfig = {
        ...runtimeConfig,
        ctx_size: contextSize,
        global_timeout: globalTimeoutSeconds,
        llamacpp: { ...(currentLlamacpp ?? {}), backend: primaryBackend },
      };
      notify.success('Runtime config saved', `ctx_size ${contextSize}, timeout ${globalTimeoutSeconds}s`);
    } else {
      runtimeError = result.error;
      notify.error('Runtime config failed', result.error || 'Lemonade did not accept the update.');
    }
    runtimeSaving = false;
  }

  function applyPreset(preset: PresetName) {
    activePreset = preset;
    if (preset === 'Safe') {
      maxOutputTokens = 1024;
      temperature = 0.3;
      appTimeoutSeconds = 180;
    } else if (preset === 'Coding') {
      maxOutputTokens = 2048;
      temperature = 0.7;
      appTimeoutSeconds = 300;
    } else if (preset === 'Long Context') {
      maxOutputTokens = 4096;
      temperature = 0.6;
      appTimeoutSeconds = 600;
    } else if (preset === 'Stress') {
      maxOutputTokens = 4096;
      temperature = 0.9;
      appTimeoutSeconds = 900;
    } else {
      maxOutputTokens = 1024;
      temperature = 0.2;
      appTimeoutSeconds = 240;
      stopSequences = ['<|im_end|>', '\\n\\nUser:', 'Observation:'];
    }
  }

  function addStopSequence() {
    const value = newStopSequence.trim();
    if (!value || stopSequences.includes(value)) return;
    stopSequences = [...stopSequences, value];
    newStopSequence = '';
  }

  function removeStopSequence(value: string) {
    stopSequences = stopSequences.filter((entry) => entry !== value);
  }

  function saveLocalDefaults() {
    saveWorkflowDefaults({
      maxOutputTokens,
      temperature,
      appTimeoutSeconds,
      stopSequences,
      activePreset,
    });
    localMessage = 'LCC Workflow Defaults saved.';
    notify.success('Workflow defaults saved', activePreset, { toastDuration: 2500 });
  }

  function loadLocalDefaults() {
    const defaults = loadWorkflowDefaults();
    maxOutputTokens = defaults.maxOutputTokens;
    temperature = defaults.temperature;
    appTimeoutSeconds = defaults.appTimeoutSeconds;
    stopSequences = defaults.stopSequences;
    activePreset = defaults.activePreset;
  }

  function resetLocalDefaults() {
    const defaults = resetWorkflowDefaults();
    activePreset = 'Coding';
    maxOutputTokens = defaults.maxOutputTokens;
    temperature = defaults.temperature;
    appTimeoutSeconds = defaults.appTimeoutSeconds;
    stopSequences = defaults.stopSequences;
    localMessage = 'LCC Workflow Defaults reset.';
    notify.info('Workflow defaults reset', 'LCC request behavior is back to Coding.');
  }
</script>

<div class="space-y-4">
  <section class="ops-panel p-5">
    <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <h2 class="ops-title">Configuration Presets</h2>
        <p class="ops-subtitle">Presets fill LCC workflow defaults and visible runtime fields. Server-side writes still require admin capability.</p>
      </div>
      <div class="flex flex-wrap gap-2 rounded border border-[#444936] bg-[#2b2d2a] p-1">
        {#each presets as preset}
          <button
            class="rounded px-4 py-2 ops-mono text-sm {activePreset === preset ? 'bg-[#4a4d49] text-lemon' : 'text-[#e3e5d3] hover:bg-[#363935]'}"
            type="button"
            on:click={() => applyPreset(preset)}
          >
            {preset}
          </button>
        {/each}
      </div>
    </div>
  </section>

  <section class="grid grid-cols-1 gap-4 xl:grid-cols-2">
    <article class="ops-panel min-h-[620px]">
      <div class="ops-card-header">
        <div class="flex items-center gap-3">
          <ServerCog class="h-5 w-5 {canWriteRuntime ? 'text-lemon' : 'text-muted-foreground'}" />
          <h2 class="ops-title">Runtime Config</h2>
        </div>
        <span class="ops-badge">{canWriteRuntime ? 'Server-side writable' : 'Server-side'}</span>
      </div>

      <div class="ops-card-body space-y-6">
        {#if runtimeError}
          <div class="ops-banner ops-banner-danger">
            <AlertCircle class="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p class="font-semibold">Runtime Config unavailable.</p>
              <p class="mt-1 text-sm"><code class="ops-mono">LEMONADE_ADMIN_API_KEY</code> may be missing. LCC Workflow Defaults still work locally.</p>
            </div>
          </div>
        {:else if runtimeLoading}
          <div class="ops-banner ops-banner-muted">Loading Runtime Config...</div>
        {/if}

        <div class="space-y-5 {canWriteRuntime ? '' : 'opacity-45'}">
          <label class="block space-y-2">
            <span class="ops-label">Context Size (tokens)</span>
            <input class="ops-input" type="number" bind:value={contextSize} disabled={!canWriteRuntime} />
          </label>

          <label class="block space-y-2">
            <span class="ops-label">Global Timeout (s)</span>
            <input class="ops-input" type="number" min="1" bind:value={globalTimeoutSeconds} disabled={!canWriteRuntime} />
          </label>

          <label class="block space-y-2">
            <span class="ops-label">Primary Backend</span>
            <div class="ops-segmented">
              {#each backendOptions as option}
                <button
                  class="ops-segment {primaryBackend === option ? 'ops-segment-active' : ''}"
                  type="button"
                  aria-pressed={primaryBackend === option}
                  disabled={!canWriteRuntime}
                  on:click={() => primaryBackend = option}
                >
                  {option}
                </button>
              {/each}
            </div>
          </label>
        </div>

        <div class="border-t border-[#34382d] pt-5">
          <button class="ops-button" type="button" on:click={loadRuntimeConfig}>Reload Runtime Config</button>
          <button class="ops-button ops-button-primary ml-2" type="button" on:click={saveRuntimeConfig} disabled={!canWriteRuntime || runtimeSaving}>
            {runtimeSaving ? 'Saving' : 'Save Runtime Config'}
          </button>
        </div>
      </div>
    </article>

    <article class="ops-panel min-h-[620px]">
      <div class="ops-card-header">
        <div class="flex items-center gap-3">
          <SlidersHorizontal class="h-5 w-5 text-lemon" />
          <h2 class="ops-title">LCC Workflow Defaults</h2>
        </div>
        <span class="ops-badge">LCC requests</span>
      </div>

      <div class="ops-card-body flex min-h-[540px] flex-col">
        <div class="space-y-7">
          <div>
            <span class="ops-label">Max Output Tokens</span>
            <div class="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
              {#each tokenOptions as option}
                <button
                  class="h-11 rounded border ops-mono {maxOutputTokens === option ? 'border-lemon bg-lemon text-[#111310]' : 'border-[#444936] bg-[#202321] text-foreground hover:bg-[#2b2e2a]'}"
                  type="button"
                  on:click={() => maxOutputTokens = option}
                >
                  {option}
                </button>
              {/each}
            </div>
          </div>

          <div>
            <div class="flex items-center justify-between">
              <span class="ops-label">Temperature</span>
              <span class="ops-badge">{temperature.toFixed(2)}</span>
            </div>
            <input class="mt-4 w-full accent-lemon" type="range" min="0" max="2" step="0.05" bind:value={temperature} />
            <div class="mt-2 flex justify-between text-xs text-muted-foreground">
              <span>0.0 Deterministic</span>
              <span>2.0 Creative</span>
            </div>
          </div>

          <label class="block space-y-2">
            <span class="ops-label">App Timeout (s)</span>
            <div class="relative">
              <input class="ops-input pr-12" type="number" min="1" bind:value={appTimeoutSeconds} />
              <span class="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-muted-foreground">sec</span>
            </div>
          </label>

          <div>
            <span class="ops-label">Stop Sequences</span>
            <div class="mt-3 flex min-h-16 flex-wrap items-center gap-2 border border-[#444936] bg-[#161817] p-3">
              {#each stopSequences as sequence}
                <span class="inline-flex items-center gap-2 rounded border border-[#4a4d39] bg-[#303330] px-3 py-2 ops-mono text-sm">
                  {sequence}
                  <button type="button" class="text-muted-foreground hover:text-foreground" on:click={() => removeStopSequence(sequence)} aria-label="Remove stop sequence">
                    x
                  </button>
                </span>
              {/each}
              <input
                class="min-w-40 flex-1 bg-transparent px-2 py-2 ops-mono text-sm outline-none placeholder:text-[#777b70]"
                placeholder="Add sequence..."
                bind:value={newStopSequence}
                on:keydown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    addStopSequence();
                  }
                }}
              />
            </div>
          </div>
        </div>

        <div class="mt-auto border-t border-[#34382d] pt-6">
          {#if localMessage}
            <p class="mb-3 text-sm text-muted-foreground">{localMessage}</p>
          {/if}
          <div class="flex justify-end gap-3">
            <button class="ops-button" type="button" on:click={resetLocalDefaults}>Reset Defaults</button>
            <button class="ops-button ops-button-primary" type="button" on:click={saveLocalDefaults}>Save Workflow Defaults</button>
          </div>
        </div>
      </div>
    </article>
  </section>
</div>
