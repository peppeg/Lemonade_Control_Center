<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api/client';
  import { notify } from '$lib/stores/notifications';
  import type {
    AccessMode,
    AppearanceConfig,
    ConnectionTestResult,
    DiscoveryCheck,
    DiscoveryResult,
    RuntimeConfigRequest,
    RuntimeType,
    SystemConfig,
  } from '$lib/types';
  import {
    CheckCircle2,
    CircleAlert,
    CircleDot,
    Loader2,
    Network,
    RefreshCw,
    ServerCog,
    Settings,
    Shield,
  } from 'lucide-svelte';

  type StepId = 'welcome' | 'connection' | 'system' | 'discovery' | 'complete';

  const steps: { id: StepId; label: string }[] = [
    { id: 'welcome', label: 'Welcome' },
    { id: 'connection', label: 'Connection' },
    { id: 'system', label: 'System' },
    { id: 'discovery', label: 'Discovery' },
    { id: 'complete', label: 'Complete' },
  ];

  const runtimeChoices: {
    type: Exclude<RuntimeType, 'custom'>;
    label: string;
    enabled: boolean;
    badge?: string;
  }[] = [
    { type: 'lemonade', label: 'lemonade', enabled: true },
    { type: 'ollama', label: 'ollama', enabled: false, badge: 'Later' },
    { type: 'llamacpp', label: 'llama.cpp', enabled: false, badge: 'Later' },
  ];

  let stepIndex = 0;
  let runtimeType: Exclude<RuntimeType, 'custom'> = 'lemonade';
  let runtimeName = 'Local Lemonade';
  let runtimeUrl = 'http://localhost:13305';
  let adminKey = '';
  let accessMode: AccessMode = 'local';

  let connectionTesting = false;
  let connectionResult: ConnectionTestResult | null = null;

  let discoveryRunning = false;
  let discoveryResult: DiscoveryResult | null = null;

  let completing = false;

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

  $: currentStep = steps[stepIndex];
  $: runtimeId = `${runtimeType}-${slugify(runtimeName || runtimeType)}`;
  $: canGoNext =
    currentStep.id === 'welcome'
      || currentStep.id === 'system'
      || (currentStep.id === 'connection' && connectionResult?.success)
      || (currentStep.id === 'discovery' && discoveryResult !== null);

  function defaultUrl(type: Exclude<RuntimeType, 'custom'>): string {
    if (type === 'ollama') return 'http://localhost:11434';
    if (type === 'llamacpp') return 'http://localhost:8080';
    return 'http://localhost:13305';
  }

  function selectRuntime(type: Exclude<RuntimeType, 'custom'>) {
    runtimeType = type;
    runtimeUrl = defaultUrl(type);
    runtimeName = type === 'lemonade' ? 'Local Lemonade' : type === 'ollama' ? 'Local Ollama' : 'Direct llama.cpp';
    connectionResult = null;
    discoveryResult = null;
  }

  function buildRuntime(): RuntimeConfigRequest {
    return {
      id: runtimeId,
      type: runtimeType,
      name: runtimeName.trim() || runtimeType,
      url: runtimeUrl.trim(),
      admin_key: adminKey.trim() || null,
      is_active: true,
      access_mode: accessMode,
      capabilities_count: discoveryResult?.passed ?? 0,
      test_status: connectionResult?.success ? 'ok' : 'untested',
    };
  }

  async function testConnection() {
    connectionTesting = true;
    connectionResult = null;
    discoveryResult = null;
    const result = await api.setup.testConnection({
      type: runtimeType,
      url: runtimeUrl.trim(),
      admin_key: adminKey.trim() || null,
    });
    if (result.ok) {
      connectionResult = result.data;
      if (result.data.success) {
        notify.success('Runtime connected', `${runtimeName} responded in ${result.data.latency_ms}ms`);
      } else {
        notify.error('Runtime test failed', result.data.error || runtimeName);
      }
    } else {
      connectionResult = {
        success: false,
        version: null,
        models_count: 0,
        error: result.error,
        latency_ms: 0,
      };
      notify.error('Runtime test failed', result.error);
    }
    connectionTesting = false;
  }

  async function runDiscovery() {
    discoveryRunning = true;
    discoveryResult = null;
    const result = await api.setup.discover(buildRuntime());
    if (result.ok) {
      discoveryResult = result.data;
      notify.success('Discovery complete', `${result.data.passed}/${result.data.total} checks passed`);
    } else {
      notify.error('Discovery failed', result.error);
    }
    discoveryRunning = false;
  }

  async function finishSetup() {
    completing = true;
    const result = await api.setup.complete({
      runtime: buildRuntime(),
      system: systemForm,
      appearance: appearanceForm,
    });
    if (result.ok) {
      adminKey = '';
      notify.success('Setup complete', result.data.active_runtime_id || runtimeName);
      await goto('/dashboard');
    } else {
      notify.error('Setup failed', result.error);
    }
    completing = false;
  }

  function nextStep() {
    if (!canGoNext || stepIndex >= steps.length - 1) return;
    stepIndex += 1;
  }

  function previousStep() {
    if (stepIndex <= 0) return;
    stepIndex -= 1;
  }

  function slugify(value: string): string {
    return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'runtime';
  }

  function checkIcon(check: DiscoveryCheck): typeof CheckCircle2 {
    if (check.status === 'ok') return CheckCircle2;
    if (check.status === 'warning' || check.status === 'skip') return CircleAlert;
    return CircleAlert;
  }

  function checkClass(status: DiscoveryCheck['status']): string {
    if (status === 'ok') return 'text-status-ok';
    if (status === 'warning' || status === 'skip') return 'text-status-warn';
    return 'text-status-error';
  }
</script>

<div class="mx-auto max-w-6xl space-y-4">
  <section class="ops-panel p-5">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <h2 class="ops-title">Setup Wizard</h2>
        <p class="ops-subtitle">Configure runtime connection and system capabilities.</p>
      </div>
      <div class="flex max-w-full flex-nowrap gap-2 overflow-x-auto pb-1 lg:overflow-visible lg:pb-0">
        {#each steps as step, index}
          <button
            class="ops-button shrink-0 px-3 {stepIndex === index ? 'ops-button-primary' : ''}"
            type="button"
            on:click={() => stepIndex = index}
          >
            <CircleDot class="h-4 w-4" />
            {step.label}
          </button>
        {/each}
      </div>
    </div>
  </section>

  <section class="ops-panel min-h-[560px]">
    <div class="ops-card-header">
      <div class="flex items-center gap-3">
        {#if currentStep.id === 'welcome'}
          <ServerCog class="h-5 w-5 text-lemon" />
        {:else if currentStep.id === 'connection'}
          <Network class="h-5 w-5 text-lemon" />
        {:else if currentStep.id === 'system'}
          <Shield class="h-5 w-5 text-lemon" />
        {:else if currentStep.id === 'discovery'}
          <RefreshCw class="h-5 w-5 text-lemon" />
        {:else}
          <CheckCircle2 class="h-5 w-5 text-lemon" />
        {/if}
        <h2 class="ops-title">{currentStep.label}</h2>
      </div>
      <span class="ops-badge">Step {stepIndex + 1}/{steps.length}</span>
    </div>

    <div class="ops-card-body">
      {#if currentStep.id === 'welcome'}
        <div class="grid min-h-[420px] grid-cols-1 gap-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div class="space-y-5">
            <p class="ops-label">Lemonade Control Center</p>
            <h1 class="text-3xl font-black leading-tight text-foreground lg:text-5xl">Prepare the control plane before changing runtime behavior.</h1>
            <p class="max-w-2xl text-base leading-7 text-muted-foreground">
              This wizard stores runtime access, system permissions, and UI preferences in the backend. It does not start, stop, or expose a remote server by itself.
            </p>
            <button class="ops-button ops-button-primary" type="button" on:click={nextStep}>Get Started</button>
          </div>
          <div class="grid grid-cols-1 gap-3">
            <div class="border border-[#30342b] bg-[#111312] p-4">
              <p class="ops-label">Runtime</p>
              <p class="ops-value mt-1">Lemonade first, Ollama and llama.cpp prepared as stubs.</p>
            </div>
            <div class="border border-[#30342b] bg-[#111312] p-4">
              <p class="ops-label">Security</p>
              <p class="ops-value mt-1">Admin key is stored backend-side and redacted in settings responses.</p>
            </div>
            <div class="border border-[#30342b] bg-[#111312] p-4">
              <p class="ops-label">Activation</p>
              <p class="ops-value mt-1">Incomplete installations are routed here automatically until setup is finished.</p>
            </div>
          </div>
        </div>
      {:else if currentStep.id === 'connection'}
        <div class="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_0.9fr]">
          <div class="space-y-5">
            <div>
              <p class="ops-label">runtime type</p>
              <div class="mt-3 flex flex-wrap gap-2">
                {#each runtimeChoices as choice}
                  <button
                    class="ops-button {runtimeType === choice.type ? 'ops-button-primary' : ''}"
                    type="button"
                    on:click={() => choice.enabled && selectRuntime(choice.type)}
                    disabled={!choice.enabled}
                    title={choice.enabled ? 'Configure this runtime' : 'Prepared for future runtime support'}
                  >
                    {choice.label}
                    {#if choice.badge}
                      <span class="ops-badge ml-1 text-[10px]">{choice.badge}</span>
                    {/if}
                  </button>
                {/each}
              </div>
              <p class="ops-muted mt-2 text-xs">
                Initial setup configures Lemonade. Ollama and direct llama.cpp are prepared for future runtime support.
              </p>
            </div>

            <label class="block space-y-2">
              <span class="ops-label">runtime name</span>
              <input class="ops-input" bind:value={runtimeName} />
            </label>

            <label class="block space-y-2">
              <span class="ops-label">runtime URL</span>
              <input class="ops-input" bind:value={runtimeUrl} />
            </label>

            <label class="block space-y-2">
              <span class="ops-label">admin key</span>
              <input class="ops-input" type="password" bind:value={adminKey} placeholder="Optional for basic health checks" />
            </label>

            <label class="block space-y-2">
              <span class="ops-label">access mode</span>
              <select class="ops-select" bind:value={accessMode}>
                <option value="local">local</option>
                <option value="ssh_tunnel">ssh_tunnel</option>
                <option value="tailscale">tailscale</option>
                <option value="remote">remote</option>
              </select>
            </label>

            <button class="ops-button ops-button-primary" type="button" on:click={testConnection} disabled={connectionTesting || !runtimeUrl.trim()}>
              {#if connectionTesting}
                <Loader2 class="h-4 w-4 animate-spin" />
                Testing
              {:else}
                <RefreshCw class="h-4 w-4" />
                Test Connection
              {/if}
            </button>
          </div>

          <div class="space-y-3">
            <div class="border border-[#30342b] bg-[#111312] p-4">
              <p class="ops-label">runtime id</p>
              <p class="ops-value mt-1 break-all">{runtimeId}</p>
            </div>
            {#if connectionResult}
              <div class="ops-banner {connectionResult.success ? 'ops-banner-muted' : 'ops-banner-danger'}">
                {#if connectionResult.success}
                  <CheckCircle2 class="mt-0.5 h-5 w-5 shrink-0 text-status-ok" />
                {:else}
                  <CircleAlert class="mt-0.5 h-5 w-5 shrink-0" />
                {/if}
                <div>
                  <p class="font-semibold">{connectionResult.success ? 'Connection OK' : 'Connection failed'}</p>
                  <p class="mt-1 text-sm">
                    {#if connectionResult.success}
                      Version {connectionResult.version ?? 'unknown'} · {connectionResult.models_count} models · {connectionResult.latency_ms}ms
                    {:else}
                      {connectionResult.error}
                    {/if}
                  </p>
                </div>
              </div>
            {:else}
              <div class="ops-banner ops-banner-muted">
                <CircleAlert class="mt-0.5 h-5 w-5 shrink-0 text-status-warn" />
                <p class="text-sm">Run the connection test before continuing.</p>
              </div>
            {/if}
          </div>
        </div>
      {:else if currentStep.id === 'system'}
        <div class="max-w-3xl space-y-5">
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
            <p class="text-sm">Restart and delete remain backend-gated by environment flags. This wizard stores the requested preference only.</p>
          </div>
        </div>
      {:else if currentStep.id === 'discovery'}
        <div class="space-y-5">
          <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p class="ops-label">auto-discovery</p>
              <p class="ops-subtitle">Probe runtime endpoints and local system capabilities.</p>
            </div>
            <button class="ops-button ops-button-primary" type="button" on:click={runDiscovery} disabled={discoveryRunning}>
              {#if discoveryRunning}
                <Loader2 class="h-4 w-4 animate-spin" />
                Running
              {:else}
                <RefreshCw class="h-4 w-4" />
                Run Discovery
              {/if}
            </button>
          </div>

          {#if discoveryResult}
            <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div class="border border-[#30342b] bg-[#111312] p-4">
                <p class="ops-label">passed</p>
                <p class="ops-value mt-1 text-xl">{discoveryResult.passed}/{discoveryResult.total}</p>
              </div>
              <div class="border border-[#30342b] bg-[#111312] p-4">
                <p class="ops-label">runtime</p>
                <p class="ops-value mt-1 text-xl">{runtimeType}</p>
              </div>
              <div class="border border-[#30342b] bg-[#111312] p-4">
                <p class="ops-label">access</p>
                <p class="ops-value mt-1 text-xl">{accessMode}</p>
              </div>
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
                      <td>
                        <div class="flex items-center gap-2">
                          <svelte:component this={checkIcon(check)} class="h-4 w-4 shrink-0 {checkClass(check.status)}" />
                          <span>{check.name}</span>
                        </div>
                      </td>
                      <td class="ops-mono text-xs">{check.endpoint}</td>
                      <td><span class="ops-badge">{check.status}</span></td>
                      <td class="text-sm text-muted-foreground">{check.detail}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <div class="ops-banner ops-banner-muted">
              <CircleAlert class="mt-0.5 h-5 w-5 shrink-0 text-status-warn" />
              <p class="text-sm">Run discovery before completing setup.</p>
            </div>
          {/if}
        </div>
      {:else}
        <div class="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_0.9fr]">
          <div class="space-y-4">
            <div class="border border-[#30342b] bg-[#111312] p-4">
              <p class="ops-label">runtime</p>
              <p class="ops-value mt-1 text-xl">{runtimeName}</p>
              <p class="ops-muted mt-1 break-all">{runtimeType} · {runtimeUrl}</p>
            </div>
            <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div class="border border-[#30342b] bg-[#111312] p-4">
                <p class="ops-label">admin key</p>
                <p class="ops-value mt-1">{adminKey.trim() ? 'configured' : 'not set'}</p>
              </div>
              <div class="border border-[#30342b] bg-[#111312] p-4">
                <p class="ops-label">capabilities</p>
                <p class="ops-value mt-1">{discoveryResult ? `${discoveryResult.passed}/${discoveryResult.total}` : 'not run'}</p>
              </div>
            </div>
            <button class="ops-button ops-button-primary" type="button" on:click={finishSetup} disabled={completing || !discoveryResult}>
              {#if completing}
                <Loader2 class="h-4 w-4 animate-spin" />
                Saving
              {:else}
                Finish Setup
              {/if}
            </button>
          </div>
          <div class="ops-banner ops-banner-muted">
            <Settings class="mt-0.5 h-5 w-5 shrink-0 text-lemon" />
            <div>
              <p class="font-semibold">After completion</p>
              <p class="mt-1 text-sm">
                The backend writes `data/config.json`, clears the admin key from this form, and returns to the dashboard. You can edit these values from Settings.
              </p>
            </div>
          </div>
        </div>
      {/if}
    </div>

    {#if currentStep.id !== 'welcome'}
      <div class="flex flex-col-reverse gap-2 border-t border-[#30342b] px-5 py-4 sm:flex-row sm:justify-between">
        <button class="ops-button" type="button" on:click={previousStep} disabled={stepIndex === 0}>Back</button>
        {#if currentStep.id !== 'complete'}
          <button class="ops-button ops-button-primary" type="button" on:click={nextStep} disabled={!canGoNext}>Next</button>
        {:else}
          <button class="ops-button" type="button" on:click={() => goto('/dashboard')}>Go to Dashboard</button>
        {/if}
      </div>
    {/if}
  </section>
</div>
