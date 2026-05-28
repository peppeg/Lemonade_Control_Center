<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Copy, Database, Download, Pencil, Play, Power, Star, Trash2 } from 'lucide-svelte';
  import type { Profile } from '$lib/types';

  export let profile: Profile;
  export let active = false;

  const dispatch = createEventDispatcher<{
    apply: Profile;
    applyLoad: Profile;
    edit: Profile;
    clone: Profile;
    export: Profile;
    delete: Profile;
    default: Profile;
    saveLemonade: Profile;
  }>();

  function ctxLabel(value: number | null): string {
    if (!value) return 'default';
    return value >= 1024 ? `${Math.round(value / 1024)}K` : String(value);
  }
</script>

<article class="ops-card p-5 {active ? 'border-lemon bg-[#1d2118]' : ''}">
  <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
    <div class="min-w-0">
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="text-lg font-bold">{profile.name}</h3>
        {#if profile.is_default}
          <span class="ops-badge ops-badge-ok">Default</span>
        {/if}
        {#if profile.is_builtin}
          <span class="ops-badge">Built-in</span>
        {/if}
        {#if active}
          <span class="ops-badge ops-badge-warn">Active</span>
        {/if}
      </div>
      {#if profile.description}
        <p class="mt-2 text-sm text-muted-foreground">{profile.description}</p>
      {/if}
    </div>

    <div class="flex flex-wrap gap-2">
      <button class="ops-button ops-button-primary" type="button" on:click={() => dispatch('apply', profile)}>
        <Play class="h-4 w-4" />
        Apply
      </button>
      <button class="ops-button" type="button" on:click={() => dispatch('applyLoad', profile)}>
        <Power class="h-4 w-4" />
        Apply & Load
      </button>
      <button class="ops-button" type="button" on:click={() => dispatch('saveLemonade', profile)}>
        <Database class="h-4 w-4" />
        Save to Lemonade
      </button>
      <button class="ops-button" type="button" on:click={() => dispatch('edit', profile)}>
        <Pencil class="h-4 w-4" />
        Edit
      </button>
      <button class="ops-button" type="button" on:click={() => dispatch('clone', profile)}>
        <Copy class="h-4 w-4" />
        Clone
      </button>
      <button class="ops-button" type="button" on:click={() => dispatch('export', profile)}>
        <Download class="h-4 w-4" />
        Export
      </button>
      <button class="ops-button" type="button" on:click={() => dispatch('default', profile)} disabled={profile.is_default}>
        <Star class="h-4 w-4" />
        Default
      </button>
      <button class="ops-button ops-button-danger" type="button" on:click={() => dispatch('delete', profile)} disabled={profile.is_builtin}>
        <Trash2 class="h-4 w-4" />
        Delete
      </button>
    </div>
  </div>

  <dl class="mt-5 grid grid-cols-2 gap-3 text-sm md:grid-cols-4 xl:grid-cols-8">
    <div>
      <dt class="ops-label">ctx_size</dt>
      <dd class="mt-1 ops-value">{ctxLabel(profile.config.ctx_size)}</dd>
    </div>
    <div>
      <dt class="ops-label">timeout</dt>
      <dd class="mt-1 ops-value">{profile.config.global_timeout ? `${profile.config.global_timeout}s` : 'default'}</dd>
    </div>
    <div>
      <dt class="ops-label">backend</dt>
      <dd class="mt-1 ops-value">{profile.config.llamacpp_backend ?? 'default'}</dd>
    </div>
    <div>
      <dt class="ops-label">max_tokens</dt>
      <dd class="mt-1 ops-value">{profile.config.max_tokens ?? 'default'}</dd>
    </div>
    <div>
      <dt class="ops-label">temperature</dt>
      <dd class="mt-1 ops-value">{profile.config.temperature ?? 'default'}</dd>
    </div>
    <div>
      <dt class="ops-label">app_timeout</dt>
      <dd class="mt-1 ops-value">{profile.config.app_timeout ? `${profile.config.app_timeout}s` : 'default'}</dd>
    </div>
    <div class="md:col-span-2">
      <dt class="ops-label">llamacpp_args</dt>
      <dd class="mt-1 truncate ops-value">{profile.config.llamacpp_args || 'none'}</dd>
    </div>
  </dl>
</article>
