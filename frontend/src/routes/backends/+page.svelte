<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { notify } from '$lib/stores/notifications';
  import ModalFrame from '$lib/components/models/ModalFrame.svelte';
  import { Copy, ExternalLink, Loader2, PackageCheck, PackagePlus, RefreshCw, Search } from 'lucide-svelte';
  import type { BackendReadinessCounts, BackendReadinessItem, BackendReadinessResponse } from '$lib/types';
  import {
    backendStateBadgeClass,
    backendStateLabel,
  } from '$lib/utils/backendReadiness';

  const emptyCounts: BackendReadinessCounts = { installed: 0, update_required: 0, installable: 0, unsupported: 0, other: 0 };
  let readiness: BackendReadinessResponse | null = null;
  let items: BackendReadinessItem[] = [];
  let loading = true;
  let error: string | null = null;
  let activeFilter = 'all';
  let search = '';
  let copiedAction: string | null = null;
  let installTarget: BackendReadinessItem | null = null;
  let installing = false;
  let installError: string | null = null;

  const filters = [
    { label: 'All', value: 'all' },
    { label: 'Updates', value: 'update_required' },
    { label: 'Installed', value: 'installed' },
    { label: 'Installable', value: 'installable' },
    { label: 'Unsupported', value: 'unsupported' },
  ];

  onMount(() => {
    refreshBackends();
  });

  $: counts = readiness?.counts ?? emptyCounts;
  $: filteredItems = items.filter((item) => {
    const body = `${item.recipe_name} ${item.recipe_key} ${item.backend_key} ${item.state} ${item.version ?? ''} ${item.message} ${item.action} ${item.devices.join(' ')}`.toLowerCase();
    const matchesFilter = activeFilter === 'all' || item.state === activeFilter;
    const matchesSearch = search.trim() === '' || body.includes(search.trim().toLowerCase());
    return matchesFilter && matchesSearch;
  });

  async function refreshBackends() {
    loading = true;
    error = null;
    const result = await api.lemonade.backendReadiness();
    if (result.ok) {
      readiness = result.data;
      items = result.data.items;
    } else {
      error = result.error;
      readiness = null;
      items = [];
    }
    loading = false;
  }

  function devicesLabel(devices: string[]): string {
    return devices.length > 0 ? devices.join(', ') : 'Unavailable';
  }

  function actionUrl(action: string): string | null {
    const match = action.match(/https?:\/\/[^\s]+/i);
    return match ? match[0].replace(/[),.;]+$/, '') : null;
  }

  function copyableAction(action: string): string {
    return actionUrl(action) ?? action;
  }

  async function copyAction(action: string) {
    await navigator.clipboard?.writeText(copyableAction(action));
    copiedAction = action;
    setTimeout(() => {
      if (copiedAction === action) copiedAction = null;
    }, 1600);
  }

  function openInstall(item: BackendReadinessItem) {
    installTarget = item;
    installError = null;
  }

  function closeInstall() {
    if (installing) return;
    installTarget = null;
    installError = null;
  }

  async function confirmInstall() {
    if (!installTarget || installing) return;
    installing = true;
    installError = null;
    const target = installTarget;
    const result = await api.lemonade.installBackend(target.recipe_key, target.backend_key);
    if (result.ok) {
      notify.success(
        target.state === 'update_required' ? 'Backend updated' : 'Backend installed',
        result.data.message,
        { href: '/backends' },
      );
      installTarget = null;
      await refreshBackends();
    } else {
      installError = result.error;
      notify.error('Backend action failed', result.error, { href: '/backends' });
    }
    installing = false;
  }
</script>

<div class="space-y-6">
  <section class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
    <div>
      <h2 class="ops-title">Backend Readiness</h2>
      <p class="ops-subtitle">Current Lemonade backend state from system-info.</p>
    </div>
    <button class="ops-button" type="button" on:click={refreshBackends} disabled={loading}>
      <RefreshCw class="h-4 w-4 {loading ? 'animate-spin' : ''}" />
      Refresh
    </button>
  </section>

  {#if error}
    <section class="ops-banner ops-banner-danger">{error}</section>
  {:else if readiness && !readiness.available}
    <section class="ops-banner text-status-warn">{readiness.message}</section>
  {/if}

  <section class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
    <article class="ops-card p-5">
      <div class="flex items-center justify-between">
        <span class="ops-label">Installed</span>
        <PackageCheck class="h-4 w-4 text-status-ok" />
      </div>
      <p class="mt-5 ops-value text-3xl font-bold">{loading ? '--' : counts.installed}</p>
    </article>
    <article class="ops-card p-5">
      <div class="flex items-center justify-between">
        <span class="ops-label">Update Required</span>
        <PackageCheck class="h-4 w-4 text-status-warn" />
      </div>
      <p class="mt-5 ops-value text-3xl font-bold">{loading ? '--' : counts.update_required}</p>
    </article>
    <article class="ops-card p-5">
      <div class="flex items-center justify-between">
        <span class="ops-label">Installable</span>
        <PackageCheck class="h-4 w-4 text-lemon" />
      </div>
      <p class="mt-5 ops-value text-3xl font-bold">{loading ? '--' : counts.installable}</p>
    </article>
    <article class="ops-card p-5">
      <div class="flex items-center justify-between">
        <span class="ops-label">Unsupported</span>
        <PackageCheck class="h-4 w-4 text-danger" />
      </div>
      <p class="mt-5 ops-value text-3xl font-bold">{loading ? '--' : counts.unsupported}</p>
    </article>
  </section>

  <section class="ops-panel overflow-hidden">
    <div class="flex flex-col gap-3 border-b border-[#34382d] p-3 lg:flex-row lg:items-center lg:justify-between">
      <div class="flex flex-wrap gap-2">
        {#each filters as filter}
          <button
            class="rounded border px-4 py-2 text-sm {activeFilter === filter.value ? 'border-[#596044] bg-[#111312] text-foreground' : 'border-transparent text-muted-foreground hover:bg-[#222522]'}"
            type="button"
            on:click={() => activeFilter = filter.value}
          >
            {filter.label}
          </button>
        {/each}
      </div>

      <label class="relative block">
        <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input class="ops-input ops-input-icon-left min-w-64" placeholder="Search backends..." bind:value={search} />
      </label>
    </div>

    <div class="overflow-x-auto">
      <table class="ops-table">
        <thead>
          <tr>
            <th>Recipe</th>
            <th>Backend</th>
            <th>State</th>
            <th>Version</th>
            <th>Devices</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {#if loading}
            <tr><td colspan="6" class="text-muted-foreground">Loading backend state...</td></tr>
          {:else if filteredItems.length === 0}
            <tr><td colspan="6" class="text-muted-foreground">No backends matched the current filters.</td></tr>
          {:else}
            {#each filteredItems as item}
              <tr>
                <td>
                  <span class="ops-value">{item.recipe_name}</span>
                  {#if item.experimental}
                    <span class="ops-badge ml-2">Experimental</span>
                  {/if}
                </td>
                <td class="ops-value">{item.backend_key}</td>
                <td><span class="ops-badge {backendStateBadgeClass(item.state)}">{backendStateLabel(item.state)}</span></td>
                <td class="ops-value">{item.version ?? 'Unavailable'}</td>
                <td class="text-muted-foreground">{devicesLabel(item.devices)}</td>
                <td class="w-[230px] max-w-[300px] align-top">
                  {#if item.state === 'installable' || item.state === 'update_required'}
                    <button
                      class="ops-button {item.state === 'update_required' ? 'ops-button-primary' : ''}"
                      type="button"
                      on:click={() => openInstall(item)}
                      disabled={installing}
                    >
                      <PackagePlus class="h-4 w-4" />
                      {item.state === 'update_required' ? 'Update' : 'Install'}
                    </button>
                  {/if}
                  {#if item.message || item.action || item.release_url || item.download_filename}
                    <details class="mt-2 text-xs">
                      <summary class="cursor-pointer text-muted-foreground hover:text-foreground">Technical details</summary>
                      <div class="mt-3 space-y-2 border-l border-[#444936] pl-3">
                        {#if item.message}<p class="text-muted-foreground">{item.message}</p>{/if}
                        {#if item.action}
                          <div class="grid grid-cols-[minmax(0,1fr)_32px] items-start gap-2">
                            {#if actionUrl(item.action)}
                              <a
                                class="min-w-0 break-all text-lemon hover:text-lemon-light hover:underline"
                                href={actionUrl(item.action) ?? undefined}
                                target="_blank"
                                rel="noreferrer"
                              >{actionUrl(item.action)}</a>
                            {:else}
                              <code class="ops-mono min-w-0 whitespace-normal break-words">{item.action}</code>
                            {/if}
                            <button
                              class="inline-flex h-8 w-8 items-center justify-center rounded border border-[#34382d] text-muted-foreground hover:text-foreground"
                              type="button"
                              title={actionUrl(item.action) ? 'Copy link' : 'Copy CLI fallback'}
                              aria-label={actionUrl(item.action) ? 'Copy link' : 'Copy CLI fallback'}
                              on:click={() => copyAction(item.action)}
                            >
                              <Copy class="h-3.5 w-3.5" />
                            </button>
                          </div>
                          {#if copiedAction === item.action}<p class="text-status-ok">Copied</p>{/if}
                        {/if}
                        {#if item.release_url}
                          <a class="inline-flex items-center gap-1 text-lemon hover:text-lemon-light" href={item.release_url} target="_blank" rel="noreferrer">
                            Release <ExternalLink class="h-3.5 w-3.5" />
                          </a>
                        {/if}
                        {#if item.download_filename}<p class="ops-mono break-all text-muted-foreground">{item.download_filename}</p>{/if}
                      </div>
                    </details>
                  {:else if item.state !== 'installable' && item.state !== 'update_required'}
                    <span class="text-muted-foreground">None</span>
                  {/if}
                </td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>
  </section>
</div>

<ModalFrame
  open={installTarget !== null}
  title={installTarget?.state === 'update_required' ? 'Update Backend' : 'Install Backend'}
  description={installTarget ? `${installTarget.recipe_key}:${installTarget.backend_key}` : ''}
  widthClass="sm:max-w-[500px]"
  on:close={closeInstall}
>
  {#if installTarget}
    <div class="space-y-4">
      <div class="ops-banner ops-banner-muted">
        <PackagePlus class="mt-0.5 h-5 w-5 shrink-0 text-lemon" />
        <div class="text-sm">
          <p class="font-semibold">
            {installTarget.state === 'update_required'
              ? 'Lemonade will download and replace the configured backend build.'
              : 'Lemonade will download and install this backend.'}
          </p>
          <p class="mt-1 text-muted-foreground">LCC calls Lemonade's public install API with force disabled. No shell command is executed.</p>
          {#if installTarget.state === 'update_required'}
            <p class="mt-2 text-status-warn">For the safest update, unload models currently using this backend before continuing, then reload and run a Smoke Test.</p>
          {/if}
        </div>
      </div>
      {#if installTarget.message}<p class="text-sm text-muted-foreground">{installTarget.message}</p>{/if}
      {#if installTarget.download_filename}
        <p class="ops-mono break-all text-xs text-muted-foreground">{installTarget.download_filename}</p>
      {/if}
      {#if installError}<div class="ops-banner ops-banner-danger">{installError}</div>{/if}
      <div class="flex justify-end gap-2">
        <button class="ops-button" type="button" on:click={closeInstall} disabled={installing}>Cancel</button>
        <button class="ops-button ops-button-primary" type="button" on:click={confirmInstall} disabled={installing}>
          {#if installing}<Loader2 class="h-4 w-4 animate-spin" />{/if}
          {installing ? 'Working' : installTarget.state === 'update_required' ? 'Confirm Update' : 'Confirm Install'}
        </button>
      </div>
    </div>
  {/if}
</ModalFrame>
