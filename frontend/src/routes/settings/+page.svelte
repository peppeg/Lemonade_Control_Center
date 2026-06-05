<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import { notify } from '$lib/stores/notifications';
  import type {
    AccessMode,
    AppearanceConfig,
    DiscoveryCheck,
    DiscoveryResult,
    LccConfigPublic,
    RuntimeConfigPublic,
    RuntimeConfigRequest,
    RuntimeType,
    SystemConfig,
  } from '$lib/types';
  import {
    CheckCircle2,
    CircleAlert,
    Cpu,
    Pencil,
    Palette,
    Plus,
    RefreshCw,
    Search,
    ServerCog,
    Shield,
    SlidersHorizontal,
    Trash2,
    X,
  } from 'lucide-svelte';

  type Tab = 'connection' | 'system' | 'appearance' | 'about';

  const tabs: { id: Tab; label: string }[] = [
    { id: 'connection', label: 'Connection' },
    { id: 'system', label: 'System' },
    { id: 'appearance', label: 'Appearance' },
    { id: 'about', label: 'About' },
  ];

  let activeTab: Tab = 'connection';
  let config: LccConfigPublic | null = null;
  let loading = true;
  let error: string | null = null;
  let testingRuntimeId: string | null = null;
  let discoveringRuntimeId: string | null = null;
  let removingRuntimeId: string | null = null;
  let savingRuntime = false;
  let savingSystem = false;
  let savingAppearance = false;
  let editingRuntimeId: string | 'new' | null = null;
  let runtimeForm: RuntimeConfigRequest = emptyRuntimeForm();
  let runtimeSecret = '';
  let discoveryRuntimeId: string | null = null;
  let discoveryResult: DiscoveryResult | null = null;

  let systemForm: SystemConfig = {
    os_type: 'linux_systemd',
    service_name: 'lemond.service',
    enable_system_commands: true,
    enable_restart: false,
    enable_delete: false,
  };

  let appearanceForm: AppearanceConfig = {
    theme: 'dark',
    accent_color: 'lemon',
    polling_interval_s: 5,
    sidebar_position: 'left',
  };

  $: activeRuntime = config?.runtimes.find((runtime) => runtime.id === config?.active_runtime_id) ?? null;

  onMount(() => {
    loadSettings();
  });

  async function loadSettings() {
    loading = true;
    error = null;
    const result = await api.settings.get();
    if (result.ok) {
      applyConfig(result.data);
    } else {
      error = result.error;
    }
    loading = false;
  }

  function applyConfig(nextConfig: LccConfigPublic) {
    config = nextConfig;
    systemForm = { ...nextConfig.system };
    appearanceForm = { ...nextConfig.appearance };
  }

  async function testRuntime(runtime: RuntimeConfigPublic) {
    testingRuntimeId = runtime.id;
    const result = await api.settings.testRuntime(runtime.id);
    if (result.ok && result.data.success) {
      notify.success('Runtime connected', `${runtime.name} responded in ${result.data.latency_ms}ms`);
      await loadSettings();
    } else {
      const message = result.ok ? result.data.error : result.error;
      notify.error('Runtime test failed', message || runtime.name);
    }
    testingRuntimeId = null;
  }

  async function activateRuntime(runtime: RuntimeConfigPublic) {
    const result = await api.settings.activateRuntime(runtime.id);
    if (result.ok) {
      notify.success('Runtime activated', runtime.name);
      await loadSettings();
    } else {
      notify.error('Runtime activation failed', result.error);
    }
  }

  async function saveSystem() {
    savingSystem = true;
    const result = await api.settings.updateSystem(systemForm);
    if (result.ok) {
      applyConfig(result.data);
      notify.success('System settings saved', systemForm.service_name);
    } else {
      notify.error('System settings failed', result.error);
    }
    savingSystem = false;
  }

  async function saveAppearance() {
    savingAppearance = true;
    const result = await api.settings.updateAppearance(appearanceForm);
    if (result.ok) {
      applyConfig(result.data);
      notify.success('Appearance settings saved', appearanceForm.theme);
    } else {
      notify.error('Appearance settings failed', result.error);
    }
    savingAppearance = false;
  }

  function statusClass(runtime: RuntimeConfigPublic): string {
    if (runtime.test_status === 'ok') return 'ops-badge-ok';
    if (runtime.test_status === 'error') return 'ops-badge-danger';
    return '';
  }

  function emptyRuntimeForm(): RuntimeConfigRequest {
    return {
      id: 'lemonade-local',
      type: 'lemonade',
      name: 'Local Lemonade',
      url: 'http://localhost:13305',
      admin_key: null,
      is_active: false,
      access_mode: 'local',
      capabilities_count: 0,
      test_status: 'untested',
    };
  }

  function defaultUrl(type: RuntimeType): string {
    if (type === 'ollama') return 'http://localhost:11434';
    if (type === 'llamacpp') return 'http://localhost:8080';
    if (type === 'custom') return 'http://localhost:8000';
    return 'http://localhost:13305';
  }

  function defaultName(type: RuntimeType): string {
    if (type === 'ollama') return 'Local Ollama';
    if (type === 'llamacpp') return 'Direct llama.cpp';
    if (type === 'custom') return 'Custom Runtime';
    return 'Local Lemonade';
  }

  function startAddRuntime() {
    const next = emptyRuntimeForm();
    const suffix = config ? config.runtimes.length + 1 : 1;
    next.id = `lemonade-local-${suffix}`;
    editingRuntimeId = 'new';
    runtimeForm = next;
    runtimeSecret = '';
  }

  function startEditRuntime(runtime: RuntimeConfigPublic) {
    editingRuntimeId = runtime.id;
    runtimeForm = {
      id: runtime.id,
      type: runtime.type,
      name: runtime.name,
      url: runtime.url,
      admin_key: null,
      is_active: runtime.is_active,
      access_mode: runtime.access_mode,
      capabilities_count: runtime.capabilities_count,
      last_tested: runtime.last_tested,
      test_status: runtime.test_status,
    };
    runtimeSecret = '';
  }

  function cancelRuntimeEdit() {
    editingRuntimeId = null;
    runtimeForm = emptyRuntimeForm();
    runtimeSecret = '';
  }

  function changeRuntimeType(type: RuntimeType) {
    runtimeForm = {
      ...runtimeForm,
      type,
      name: runtimeForm.name.trim() ? runtimeForm.name : defaultName(type),
      url: defaultUrl(type),
    };
    if (editingRuntimeId === 'new') {
      runtimeForm = { ...runtimeForm, id: slugify(runtimeForm.name || defaultName(type)) };
    }
  }

  async function saveRuntime() {
    if (!editingRuntimeId) return;
    if (!runtimeForm.id.trim() || !runtimeForm.name.trim() || !runtimeForm.url.trim()) {
      notify.warning('Runtime form incomplete', 'ID, name, and URL are required.');
      return;
    }

    savingRuntime = true;
    const payload: RuntimeConfigRequest = {
      ...runtimeForm,
      id: runtimeForm.id.trim(),
      name: runtimeForm.name.trim(),
      url: runtimeForm.url.trim(),
      admin_key: runtimeSecret.trim() || null,
    };

    const result = editingRuntimeId === 'new'
      ? await api.settings.addRuntime(payload)
      : await api.settings.updateRuntime(editingRuntimeId, payload);

    if (result.ok) {
      notify.success(editingRuntimeId === 'new' ? 'Runtime added' : 'Runtime updated', payload.name);
      cancelRuntimeEdit();
      await loadSettings();
    } else {
      notify.error('Runtime save failed', result.error);
    }
    savingRuntime = false;
  }

  async function removeRuntime(runtime: RuntimeConfigPublic) {
    if (!window.confirm(`Remove runtime "${runtime.name}"?`)) return;
    removingRuntimeId = runtime.id;
    const result = await api.settings.removeRuntime(runtime.id);
    if (result.ok) {
      notify.success('Runtime removed', runtime.name);
      if (editingRuntimeId === runtime.id) cancelRuntimeEdit();
      await loadSettings();
    } else {
      notify.error('Runtime removal failed', result.error);
    }
    removingRuntimeId = null;
  }

  async function discoverRuntime(runtime: RuntimeConfigPublic) {
    discoveringRuntimeId = runtime.id;
    const result = await api.settings.discoverRuntime(runtime.id);
    if (result.ok) {
      discoveryRuntimeId = runtime.id;
      discoveryResult = result.data;
      notify.success('Discovery complete', `${result.data.passed}/${result.data.total} checks passed`);
      await loadSettings();
    } else {
      notify.error('Discovery failed', result.error);
    }
    discoveringRuntimeId = null;
  }

  function checkClass(check: DiscoveryCheck): string {
    if (check.status === 'ok') return 'text-status-ok';
    if (check.status === 'warning' || check.status === 'skip') return 'text-status-warn';
    return 'text-status-error';
  }

  function slugify(value: string): string {
    return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'runtime';
  }
</script>

<div class="space-y-4">
  <section class="ops-panel p-5">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <h2 class="ops-title">Settings</h2>
        <p class="ops-subtitle">Persistent LCC configuration for runtime access, system permissions, and UI behavior.</p>
      </div>
      <button class="ops-button" type="button" on:click={loadSettings} disabled={loading}>
        <RefreshCw class="h-4 w-4 {loading ? 'animate-spin' : ''}" />
        Reload
      </button>
    </div>
  </section>

  <section class="ops-panel p-2">
    <div class="flex flex-wrap gap-2">
      {#each tabs as tab}
        <button
          class="ops-button {activeTab === tab.id ? 'ops-button-primary' : ''}"
          type="button"
          on:click={() => activeTab = tab.id}
        >
          {tab.label}
        </button>
      {/each}
    </div>
  </section>

  {#if error}
    <div class="ops-banner ops-banner-danger">
      <CircleAlert class="mt-0.5 h-5 w-5 shrink-0" />
      <div>
        <p class="font-semibold">Settings unavailable.</p>
        <p class="mt-1 text-sm">{error}</p>
      </div>
    </div>
  {:else if loading}
    <div class="ops-panel p-5">
      <p class="ops-muted">Loading settings...</p>
    </div>
  {:else if config}
    {#if activeTab === 'connection'}
      <section class="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1fr]">
        <article class="ops-panel">
          <div class="ops-card-header">
            <div class="flex items-center gap-3">
              <ServerCog class="h-5 w-5 text-lemon" />
              <h2 class="ops-title">Active Runtime</h2>
            </div>
            <span class="ops-badge {activeRuntime?.test_status === 'ok' ? 'ops-badge-ok' : ''}">
              {activeRuntime?.test_status ?? 'untested'}
            </span>
          </div>
          <div class="ops-card-body space-y-4">
            {#if activeRuntime}
              <div>
                <p class="ops-label">{activeRuntime.type}</p>
                <p class="ops-value mt-1 text-xl">{activeRuntime.name}</p>
                <p class="ops-muted mt-1 break-all">{activeRuntime.url}</p>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div class="border border-[#30342b] bg-[#111312] p-3">
                  <p class="ops-label">admin key</p>
                  <p class="ops-value mt-1">{activeRuntime.admin_key_configured ? 'configured' : 'not set'}</p>
                </div>
                <div class="border border-[#30342b] bg-[#111312] p-3">
                  <p class="ops-label">access</p>
                  <p class="ops-value mt-1">{activeRuntime.access_mode}</p>
                </div>
              </div>
              <button class="ops-button" type="button" on:click={() => testRuntime(activeRuntime)} disabled={testingRuntimeId === activeRuntime.id}>
                <RefreshCw class="h-4 w-4 {testingRuntimeId === activeRuntime.id ? 'animate-spin' : ''}" />
                Test Active Runtime
              </button>
            {:else}
              <p class="ops-muted">No active runtime configured.</p>
            {/if}
          </div>
        </article>

        <article class="ops-panel">
          <div class="ops-card-header">
            <div class="flex items-center gap-3">
              <Cpu class="h-5 w-5 text-lemon" />
              <h2 class="ops-title">Configured Runtimes</h2>
            </div>
            <button class="ops-button" type="button" on:click={startAddRuntime}>
              <Plus class="h-4 w-4" />
              Add Runtime
            </button>
          </div>
          <div class="ops-card-body space-y-3">
            {#each config.runtimes as runtime}
              <div class="border border-[#30342b] bg-[#111312] p-4">
                <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-2">
                      <p class="ops-value">{runtime.name}</p>
                      {#if runtime.is_active}
                        <span class="ops-badge ops-badge-ok">Active</span>
                      {/if}
                      <span class="ops-badge {statusClass(runtime)}">{runtime.test_status}</span>
                    </div>
                    <p class="ops-muted mt-1 break-all">{runtime.type} · {runtime.url}</p>
                    <p class="ops-muted mt-1 text-xs">
                      {runtime.capabilities_count} capabilities · admin key {runtime.admin_key_configured ? 'configured' : 'not set'}
                      {#if runtime.type !== 'lemonade'}
                        · prepared runtime
                      {/if}
                    </p>
                  </div>
                  <div class="flex shrink-0 flex-wrap gap-2">
                    <button class="ops-button" type="button" on:click={() => testRuntime(runtime)} disabled={testingRuntimeId === runtime.id}>
                      <RefreshCw class="h-4 w-4 {testingRuntimeId === runtime.id ? 'animate-spin' : ''}" />
                      Test
                    </button>
                    <button class="ops-button" type="button" on:click={() => discoverRuntime(runtime)} disabled={discoveringRuntimeId === runtime.id}>
                      <Search class="h-4 w-4 {discoveringRuntimeId === runtime.id ? 'animate-pulse' : ''}" />
                      Discover
                    </button>
                    <button class="ops-button" type="button" on:click={() => startEditRuntime(runtime)}>
                      <Pencil class="h-4 w-4" />
                      Edit
                    </button>
                    <button
                      class="ops-button"
                      type="button"
                      on:click={() => activateRuntime(runtime)}
                      disabled={runtime.is_active || runtime.type !== 'lemonade'}
                      title={runtime.type !== 'lemonade' ? 'Only Lemonade runtimes can be activated in M14.' : 'Activate runtime'}
                    >
                      Activate
                    </button>
                    <button class="ops-button" type="button" on:click={() => removeRuntime(runtime)} disabled={removingRuntimeId === runtime.id || config.runtimes.length <= 1}>
                      <Trash2 class="h-4 w-4" />
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            {/each}

            {#if editingRuntimeId}
              <div class="border border-[#4b4f39] bg-[#171a18] p-4">
                <div class="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <h3 class="ops-title text-base">{editingRuntimeId === 'new' ? 'Add Runtime' : 'Edit Runtime'}</h3>
                    <p class="ops-subtitle">Runtime credentials are submitted to the backend and redacted from settings responses.</p>
                  </div>
                  <button class="ops-button" type="button" on:click={cancelRuntimeEdit} title="Cancel runtime edit">
                    <X class="h-4 w-4" />
                  </button>
                </div>

                <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <label class="block space-y-2">
                    <span class="ops-label">runtime id</span>
                    <input class="ops-input" bind:value={runtimeForm.id} disabled={editingRuntimeId !== 'new'} />
                  </label>
                  <label class="block space-y-2">
                    <span class="ops-label">runtime type</span>
                    <select
                      class="ops-select"
                      bind:value={runtimeForm.type}
                      on:change={(event) => changeRuntimeType(event.currentTarget.value as RuntimeType)}
                    >
                      <option value="lemonade">lemonade</option>
                      <option value="ollama">ollama</option>
                      <option value="llamacpp">llamacpp</option>
                      <option value="custom">custom</option>
                    </select>
                  </label>
                  <label class="block space-y-2">
                    <span class="ops-label">runtime name</span>
                    <input class="ops-input" bind:value={runtimeForm.name} />
                  </label>
                  <label class="block space-y-2">
                    <span class="ops-label">access mode</span>
                    <select class="ops-select" bind:value={runtimeForm.access_mode}>
                      <option value="local">local</option>
                      <option value="ssh_tunnel">ssh_tunnel</option>
                      <option value="tailscale">tailscale</option>
                      <option value="remote">remote</option>
                    </select>
                  </label>
                  <label class="block space-y-2 md:col-span-2">
                    <span class="ops-label">runtime URL</span>
                    <input class="ops-input" bind:value={runtimeForm.url} />
                  </label>
                  <label class="block space-y-2 md:col-span-2">
                    <span class="ops-label">admin key</span>
                    <input
                      class="ops-input"
                      type="password"
                      bind:value={runtimeSecret}
                      placeholder={editingRuntimeId === 'new' ? 'Optional' : 'Leave blank to keep the current key'}
                    />
                  </label>
                </div>

                <div class="mt-4 flex flex-wrap gap-2">
                  <button class="ops-button ops-button-primary" type="button" on:click={saveRuntime} disabled={savingRuntime}>
                    {savingRuntime ? 'Saving' : editingRuntimeId === 'new' ? 'Add Runtime' : 'Save Runtime'}
                  </button>
                  <button class="ops-button" type="button" on:click={cancelRuntimeEdit}>Cancel</button>
                </div>
              </div>
            {/if}

            {#if discoveryResult && discoveryRuntimeId}
              <div class="border border-[#30342b] bg-[#101211] p-4">
                <div class="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div>
                    <h3 class="ops-title text-base">Discovery Result</h3>
                    <p class="ops-subtitle">{discoveryResult.passed}/{discoveryResult.total} checks passed for {discoveryRuntimeId}.</p>
                  </div>
                  <span class="ops-badge">{discoveryResult.total} checks</span>
                </div>
                <div class="overflow-hidden border border-[#30342b]">
                  <table class="ops-table">
                    <thead>
                      <tr>
                        <th>Check</th>
                        <th>Endpoint</th>
                        <th>Status</th>
                        <th>Detail</th>
                      </tr>
                    </thead>
                    <tbody>
                      {#each discoveryResult.checks as check}
                        <tr>
                          <td class={checkClass(check)}>{check.name}</td>
                          <td class="ops-mono text-xs">{check.endpoint}</td>
                          <td><span class="ops-badge">{check.status}</span></td>
                          <td class="text-sm text-muted-foreground">{check.detail}</td>
                        </tr>
                      {/each}
                    </tbody>
                  </table>
                </div>
              </div>
            {/if}
          </div>
        </article>
      </section>
    {:else if activeTab === 'system'}
      <section class="ops-panel">
        <div class="ops-card-header">
          <div class="flex items-center gap-3">
            <Shield class="h-5 w-5 text-lemon" />
            <h2 class="ops-title">System Permissions</h2>
          </div>
          <span class="ops-badge">Backend-owned</span>
        </div>
        <div class="ops-card-body max-w-3xl space-y-5">
          <label class="block space-y-2">
            <span class="ops-label">OS type</span>
            <select class="ops-select" bind:value={systemForm.os_type}>
              <option value="linux_systemd">linux_systemd</option>
              <option value="windows">windows</option>
              <option value="macos">macos</option>
              <option value="docker">docker</option>
              <option value="other">other</option>
            </select>
          </label>
          <label class="block space-y-2">
            <span class="ops-label">service name</span>
            <input class="ops-input" bind:value={systemForm.service_name} />
          </label>
          <div class="grid grid-cols-1 gap-2 md:grid-cols-3">
            <label class="flex min-h-11 items-center gap-3 border border-[#3f432d] bg-[#181b1a] px-3 py-2">
              <input type="checkbox" bind:checked={systemForm.enable_system_commands} />
              <span class="ops-value text-sm">system commands</span>
            </label>
            <label class="flex min-h-11 items-center gap-3 border border-[#3f432d] bg-[#181b1a] px-3 py-2">
              <input type="checkbox" bind:checked={systemForm.enable_restart} />
              <span class="ops-value text-sm">restart service</span>
            </label>
            <label class="flex min-h-11 items-center gap-3 border border-[#3f432d] bg-[#181b1a] px-3 py-2">
              <input type="checkbox" bind:checked={systemForm.enable_delete} />
              <span class="ops-value text-sm">model delete</span>
            </label>
          </div>
          <div class="ops-banner ops-banner-muted">
            <CircleAlert class="mt-0.5 h-5 w-5 shrink-0 text-status-warn" />
            <p class="text-sm">Restart and delete preferences are stored here, but the actual backend actions remain gated by `.env` safety flags.</p>
          </div>
          <button class="ops-button ops-button-primary" type="button" on:click={saveSystem} disabled={savingSystem}>
            {savingSystem ? 'Saving' : 'Save System Settings'}
          </button>
        </div>
      </section>
    {:else if activeTab === 'appearance'}
      <section class="ops-panel">
        <div class="ops-card-header">
          <div class="flex items-center gap-3">
            <Palette class="h-5 w-5 text-lemon" />
            <h2 class="ops-title">Appearance</h2>
          </div>
          <span class="ops-badge">Stored</span>
        </div>
        <div class="ops-card-body max-w-3xl space-y-5">
          <label class="block space-y-2">
            <span class="ops-label">theme</span>
            <select class="ops-select" bind:value={appearanceForm.theme}>
              <option value="dark">dark</option>
              <option value="light">light</option>
              <option value="system">system</option>
            </select>
          </label>
          <label class="block space-y-2">
            <span class="ops-label">accent color</span>
            <select class="ops-select" bind:value={appearanceForm.accent_color}>
              <option value="lemon">lemon</option>
              <option value="purple">purple</option>
              <option value="blue">blue</option>
              <option value="green">green</option>
            </select>
          </label>
          <label class="block space-y-2">
            <span class="ops-label">polling interval (seconds)</span>
            <input class="ops-input" type="number" min="2" max="60" bind:value={appearanceForm.polling_interval_s} />
          </label>
          <div class="ops-banner ops-banner-muted">
            <CircleAlert class="mt-0.5 h-5 w-5 shrink-0 text-status-warn" />
            <p class="text-sm">Theme, accent, polling interval, and sidebar position are persisted now. Live application is deferred until the setup/settings flow is fully activated.</p>
          </div>
          <button class="ops-button ops-button-primary" type="button" on:click={saveAppearance} disabled={savingAppearance}>
            {savingAppearance ? 'Saving' : 'Save Appearance'}
          </button>
        </div>
      </section>
    {:else}
      <section class="ops-panel">
        <div class="ops-card-header">
          <div class="flex items-center gap-3">
            <SlidersHorizontal class="h-5 w-5 text-lemon" />
            <h2 class="ops-title">About</h2>
          </div>
          <span class="ops-badge">M14</span>
        </div>
        <div class="ops-card-body grid grid-cols-1 gap-3 md:grid-cols-3">
          <div class="border border-[#30342b] bg-[#111312] p-4">
            <p class="ops-label">setup</p>
            <p class="ops-value mt-1">{config.setup_complete ? 'complete' : 'not complete'}</p>
          </div>
          <div class="border border-[#30342b] bg-[#111312] p-4">
            <p class="ops-label">config version</p>
            <p class="ops-value mt-1">{config.version}</p>
          </div>
          <div class="border border-[#30342b] bg-[#111312] p-4">
            <p class="ops-label">active runtime</p>
            <p class="ops-value mt-1">{config.active_runtime_id ?? 'none'}</p>
          </div>
          <div class="ops-banner ops-banner-muted md:col-span-3">
            <CheckCircle2 class="mt-0.5 h-5 w-5 shrink-0" />
            <p class="text-sm">
              M14 backend settings are active. Existing app API routes now use the active Lemonade runtime URL. Non-Lemonade runtimes are prepared but not routable yet.
            </p>
          </div>
          <div class="border border-[#30342b] bg-[#111312] p-4 md:col-span-3">
            <p class="ops-label">Credits</p>
            <div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <p class="ops-value">Project owner</p>
                <p class="ops-muted mt-1">
                  Peppe / peppeg ·
                  <a class="text-lemon hover:underline" href="https://github.com/peppeg" target="_blank" rel="noreferrer">GitHub</a>
                  ·
                  <a class="text-lemon hover:underline" href="https://yourfuture.me" target="_blank" rel="noreferrer">yourfuture.me</a>
                </p>
              </div>
              <div>
                <p class="ops-value">Development assistance</p>
                <p class="ops-muted mt-1">OpenAI Codex, Qwen3-Coder-Next-GGUF, Google Stitch</p>
              </div>
              <div>
                <p class="ops-value">Runtime ecosystem</p>
                <p class="ops-muted mt-1">Lemonade Server, llama.cpp, FastAPI, SvelteKit</p>
              </div>
              <div>
                <p class="ops-value">Development workstation</p>
                <p class="ops-muted mt-1">Corsaier AI Workstation 300 · Fedora Linux 44 Workstation · Kernel 7.0.9-202.fc44.x86_64 · AMD Strix Halo · 128 GB RAM</p>
              </div>
              <div>
                <p class="ops-value">Project repository</p>
                <p class="ops-muted mt-1">
                  <a class="text-lemon hover:underline" href="https://github.com/peppeg/Lemonade_Control_Center" target="_blank" rel="noreferrer">github.com/peppeg/Lemonade_Control_Center</a>
                  · Apache-2.0
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    {/if}
  {/if}
</div>
