<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Download } from 'lucide-svelte';
  import type { LemonadeSavedOptions } from '$lib/types';

  export let data: LemonadeSavedOptions | null = null;
  export let loading = false;

  const dispatch = createEventDispatcher<{ importOptions: LemonadeSavedOptions }>();
</script>

<section class="ops-panel">
  <div class="ops-card-header">
    <div>
      <h2 class="ops-title">Lemonade Saved Options</h2>
      <p class="ops-subtitle">Read-only state from Lemonade recipe_options.json. These are the defaults Lemonade has saved outside LCC.</p>
    </div>
    {#if data?.available}
      <span class="ops-badge ops-badge-ok">Available</span>
    {:else}
      <span class="ops-badge {loading ? '' : 'ops-badge-warn'}">{loading ? 'Loading' : 'Unavailable'}</span>
    {/if}
  </div>

  <div class="space-y-4 p-5">
    {#if loading}
      <p class="text-sm text-muted-foreground">Reading Lemonade saved options...</p>
    {:else if !data}
      <p class="text-sm text-muted-foreground">Saved options have not been loaded yet.</p>
    {:else if !data.available}
      <div class="ops-banner ops-banner-muted">
        <div>
          <p class="font-semibold">No readable Lemonade saved options file.</p>
          <p class="mt-1 text-sm text-muted-foreground">{data.error ?? 'recipe_options.json is not available.'}</p>
          <p class="mt-2 break-all ops-value text-xs">{data.path}</p>
        </div>
      </div>
    {:else if data.selected_options}
      <div class="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_2fr]">
        <div class="ops-card p-4">
          <span class="ops-label">Matched Key</span>
          <p class="mt-2 break-all ops-value text-lemon">{data.selected_key}</p>
          <span class="ops-label mt-5 block">Source File</span>
          <p class="mt-2 break-all text-xs text-muted-foreground">{data.path}</p>
          <button class="ops-button mt-5 w-full" type="button" on:click={() => dispatch('importOptions', data as LemonadeSavedOptions)}>
            <Download class="h-4 w-4" />
            Import as LCC Profile
          </button>
        </div>
        <div>
          <span class="ops-label">Saved Load Options</span>
          <pre class="ops-terminal mt-3 max-h-56 overflow-auto p-3">{JSON.stringify(data.selected_options, null, 2)}</pre>
        </div>
      </div>
    {:else}
      <div class="ops-banner ops-banner-muted">
        <div>
          <p class="font-semibold">No saved Lemonade options for this model.</p>
          <p class="mt-1 text-sm text-muted-foreground">
            Lemonade has {Object.keys(data.options).length} saved option {Object.keys(data.options).length === 1 ? 'entry' : 'entries'}, but none matched this model name.
          </p>
          <p class="mt-2 break-all ops-value text-xs">{data.path}</p>
        </div>
      </div>
    {/if}

    {#if data?.available && Object.keys(data.options).length > 0}
      <details>
        <summary class="cursor-pointer ops-label">All Lemonade saved options ({Object.keys(data.options).length})</summary>
        <pre class="ops-terminal mt-3 max-h-80 overflow-auto p-3">{JSON.stringify(data.options, null, 2)}</pre>
      </details>
    {/if}
  </div>
</section>
