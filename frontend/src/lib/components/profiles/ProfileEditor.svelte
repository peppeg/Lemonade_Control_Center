<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { Profile, ProfileConfig } from '$lib/types';

  export let profile: Profile | null = null;
  export let submitLabel = 'Save Profile';

  const dispatch = createEventDispatcher<{
    save: { name: string; description: string; icon: string; config: ProfileConfig };
    cancel: void;
  }>();

  let name = '';
  let description = '';
  let icon = 'profile';
  let ctxSize: number | null = 16384;
  let globalTimeout: number | null = 600;
  let backend = 'vulkan';
  let llamacppArgs = '';
  let maxTokens: number | null = 4000;
  let temperature: number | null = 0.3;
  let appTimeout: number | null = 300;
  let stopSequences = '<|im_end|>';

  $: if (profile) {
    name = profile.name;
    description = profile.description;
    icon = profile.icon;
    ctxSize = profile.config.ctx_size;
    globalTimeout = profile.config.global_timeout;
    backend = profile.config.llamacpp_backend ?? 'auto';
    llamacppArgs = profile.config.llamacpp_args ?? '';
    maxTokens = profile.config.max_tokens;
    temperature = profile.config.temperature;
    appTimeout = profile.config.app_timeout;
    stopSequences = profile.config.stop_sequences ?? '';
  }

  function save() {
    dispatch('save', {
      name,
      description,
      icon,
      config: {
        ctx_size: emptyToNull(ctxSize),
        global_timeout: emptyToNull(globalTimeout),
        llamacpp_backend: backend === 'auto' ? null : backend,
        llamacpp_args: llamacppArgs.trim() || null,
        max_tokens: emptyToNull(maxTokens),
        temperature: emptyToNull(temperature),
        app_timeout: emptyToNull(appTimeout),
        stop_sequences: stopSequences.trim() || null,
      },
    });
  }

  function emptyToNull<T>(value: T | null): T | null {
    return value === null || value === '' ? null : value;
  }
</script>

<section class="ops-panel p-5">
  <div class="mb-5">
    <h2 class="ops-title">{profile ? 'Edit Profile' : 'Create Custom Profile'}</h2>
    <p class="ops-subtitle">Keep runtime flags explicit. Profiles store exactly what will be applied.</p>
  </div>

  <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
    <label class="block space-y-2">
      <span class="ops-label">Name</span>
      <input class="ops-input" bind:value={name} placeholder="Coding ROCm" />
    </label>
    <label class="block space-y-2">
      <span class="ops-label">Icon label</span>
      <input class="ops-input" bind:value={icon} placeholder="code" />
    </label>
    <label class="block space-y-2 md:col-span-2">
      <span class="ops-label">Description</span>
      <input class="ops-input" bind:value={description} placeholder="Short operational note" />
    </label>
    <label class="block space-y-2">
      <span class="ops-label">ctx_size</span>
      <input class="ops-input" type="number" min="1" bind:value={ctxSize} />
    </label>
    <label class="block space-y-2">
      <span class="ops-label">global_timeout (s)</span>
      <input class="ops-input" type="number" min="1" bind:value={globalTimeout} />
    </label>
    <label class="block space-y-2">
      <span class="ops-label">llamacpp_backend</span>
      <select class="ops-select" bind:value={backend}>
        <option value="auto">auto</option>
        <option value="vulkan">vulkan</option>
        <option value="rocm">rocm</option>
        <option value="cpu">cpu</option>
        <option value="cuda">cuda</option>
      </select>
    </label>
    <label class="block space-y-2">
      <span class="ops-label">max_tokens</span>
      <input class="ops-input" type="number" min="1" bind:value={maxTokens} />
    </label>
    <label class="block space-y-2">
      <span class="ops-label">temperature</span>
      <input class="ops-input" type="number" min="0" max="2" step="0.05" bind:value={temperature} />
    </label>
    <label class="block space-y-2">
      <span class="ops-label">app_timeout (s)</span>
      <input class="ops-input" type="number" min="1" bind:value={appTimeout} />
    </label>
    <label class="block space-y-2 md:col-span-2">
      <span class="ops-label">llamacpp_args</span>
      <input class="ops-input" bind:value={llamacppArgs} placeholder="--flash-attn --no-mmap -np 1" />
    </label>
    <label class="block space-y-2 md:col-span-2">
      <span class="ops-label">stop_sequences</span>
      <textarea class="ops-textarea" bind:value={stopSequences} placeholder="One sequence per line"></textarea>
    </label>
  </div>

  <div class="mt-5 flex justify-end gap-3">
    {#if profile}
      <button class="ops-button" type="button" on:click={() => dispatch('cancel')}>Cancel</button>
    {/if}
    <button class="ops-button ops-button-primary" type="button" on:click={save} disabled={!name.trim()}>
      {submitLabel}
    </button>
  </div>
</section>
