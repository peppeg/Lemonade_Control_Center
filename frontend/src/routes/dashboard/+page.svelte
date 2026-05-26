<script lang="ts">
  import PageHeader from '$lib/components/shared/PageHeader.svelte';
  import * as Card from '$lib/components/ui/card';
  import { Badge } from '$lib/components/ui/badge';
  import { capabilities } from '$lib/stores/capabilities';
  import { connectionStatus, healthData, lastHealthCheck } from '$lib/stores/connection';
  import {
    LayoutDashboard,
    Activity,
    ShieldCheck,
    TimerReset,
    Cpu,
    Settings,
    ScrollText,
    Monitor
  } from 'lucide-svelte';

  const upcomingSections = [
    { label: 'Models', milestone: 'M5', icon: Cpu },
    { label: 'Configuration', milestone: 'M6', icon: Settings },
    { label: 'Logs & Stats', milestone: 'M7', icon: ScrollText },
    { label: 'System', milestone: 'M8', icon: Monitor }
  ];

  $: enabledCapabilities = Object.entries($capabilities)
    .filter(([key, value]) => typeof value === 'boolean' && value)
    .map(([key]) => key)
    .sort();

  $: statusTone =
    $connectionStatus === 'connected'
      ? 'text-status-ok'
      : $connectionStatus === 'degraded'
        ? 'text-status-warn'
        : $connectionStatus === 'disconnected'
          ? 'text-status-error'
          : 'text-status-off';

  $: statusLabel =
    $connectionStatus === 'connected'
      ? 'Backend and Lemonade reachable'
      : $connectionStatus === 'degraded'
        ? 'Backend reachable, Lemonade degraded'
        : $connectionStatus === 'disconnected'
          ? 'Backend offline'
          : 'Initial probe in progress';
</script>

<div class="space-y-6">
  <PageHeader
    title="Dashboard"
    description="Milestone 3 shell status. This page confirms routing, layout, polling, and capability probing are active."
    milestone="M3"
    icon={LayoutDashboard}
  />

  <div class="grid gap-4 xl:grid-cols-3">
    <Card.Root class="xl:col-span-2">
      <Card.Content class="space-y-4">
        <div class="flex items-start justify-between gap-3">
          <div class="space-y-1.5">
            <div class="flex items-center gap-2">
              <Activity class="h-4 w-4 text-lemon" />
              <h2 class="text-sm font-semibold text-foreground">Runtime Status</h2>
            </div>
            <p class="text-sm text-muted-foreground">
              The frontend shell is mounted and polling the backend through the Vite proxy.
            </p>
          </div>
          <Badge variant="outline" class={statusTone}>{$connectionStatus}</Badge>
        </div>

        <div class="grid gap-3 md:grid-cols-3">
          <div class="rounded-lg border border-border bg-muted/30 p-3">
            <p class="text-xs uppercase tracking-wide text-muted-foreground">Connection</p>
            <p class="mt-1 text-sm font-medium text-foreground">{statusLabel}</p>
          </div>
          <div class="rounded-lg border border-border bg-muted/30 p-3">
            <p class="text-xs uppercase tracking-wide text-muted-foreground">Lemonade URL</p>
            <p class="mt-1 text-sm font-medium text-foreground break-all">
              {$healthData?.lemonade_url ?? 'Not reported yet'}
            </p>
          </div>
          <div class="rounded-lg border border-border bg-muted/30 p-3">
            <p class="text-xs uppercase tracking-wide text-muted-foreground">Last Probe</p>
            <p class="mt-1 text-sm font-medium text-foreground">
              {$lastHealthCheck ? $lastHealthCheck.toLocaleTimeString() : 'Waiting for first check'}
            </p>
          </div>
        </div>
      </Card.Content>
    </Card.Root>

    <Card.Root>
      <Card.Content class="space-y-4">
        <div class="flex items-center gap-2">
          <ShieldCheck class="h-4 w-4 text-lemon" />
          <h2 class="text-sm font-semibold text-foreground">Capability Probe</h2>
        </div>
        <div class="space-y-2">
          <div class="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
            <span class="text-sm text-muted-foreground">Enabled flags</span>
            <span class="text-sm font-semibold text-foreground">{enabledCapabilities.length}</span>
          </div>
          <div class="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
            <span class="text-sm text-muted-foreground">Lemonade version</span>
            <span class="text-sm font-semibold text-foreground">
              {$capabilities.lemonade_version ?? 'Unknown'}
            </span>
          </div>
          <div class="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
            <span class="text-sm text-muted-foreground">Probe timestamp</span>
            <span class="text-sm font-semibold text-foreground">
              {$capabilities.probe_timestamp
                ? new Date($capabilities.probe_timestamp).toLocaleTimeString()
                : 'Pending'}
            </span>
          </div>
        </div>
      </Card.Content>
    </Card.Root>
  </div>

  <div class="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
    <Card.Root>
      <Card.Content class="space-y-4">
        <div class="flex items-center gap-2">
          <TimerReset class="h-4 w-4 text-lemon" />
          <h2 class="text-sm font-semibold text-foreground">What M3 Delivers</h2>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <div class="rounded-lg border border-border bg-muted/30 p-3">
            <p class="text-sm font-medium text-foreground">Application shell</p>
            <p class="mt-1 text-sm text-muted-foreground">
              Sidebar, header, mobile navigation, status bar and route layout are wired.
            </p>
          </div>
          <div class="rounded-lg border border-border bg-muted/30 p-3">
            <p class="text-sm font-medium text-foreground">Live backend hooks</p>
            <p class="mt-1 text-sm text-muted-foreground">
              Health polling and capability probing run from the root layout after mount.
            </p>
          </div>
          <div class="rounded-lg border border-border bg-muted/30 p-3">
            <p class="text-sm font-medium text-foreground">Progressive pages</p>
            <p class="mt-1 text-sm text-muted-foreground">
              Route placeholders are in place so later milestones can attach real features without
              reworking navigation.
            </p>
          </div>
          <div class="rounded-lg border border-border bg-muted/30 p-3">
            <p class="text-sm font-medium text-foreground">Safe failure mode</p>
            <p class="mt-1 text-sm text-muted-foreground">
              If the backend is offline, the shell still renders and the UI stays readable.
            </p>
          </div>
        </div>
      </Card.Content>
    </Card.Root>

    <Card.Root>
      <Card.Content class="space-y-4">
        <h2 class="text-sm font-semibold text-foreground">Upcoming Sections</h2>
        <div class="space-y-2">
          {#each upcomingSections as section}
            <div class="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2.5">
              <div class="flex items-center gap-2">
                <svelte:component this={section.icon} class="h-4 w-4 text-muted-foreground" />
                <span class="text-sm text-foreground">{section.label}</span>
              </div>
              <Badge variant="secondary">{section.milestone}</Badge>
            </div>
          {/each}
        </div>
      </Card.Content>
    </Card.Root>
  </div>
</div>
