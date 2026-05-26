<!--
  ServerStatusCard — Lemonade server overview.
-->
<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Badge } from '$lib/components/ui/badge';
  import StatItem from './StatItem.svelte';
  import CardSkeleton from './CardSkeleton.svelte';
  import { Server } from 'lucide-svelte';
  import type { ServerStatus } from '$lib/types';

  export let data: ServerStatus | null;
  export let loading: boolean = false;

  $: statusColor = data?.status === 'running'
    ? 'text-status-ok'
    : data?.status === 'stopped'
      ? 'text-status-error'
      : 'text-status-off';

  $: statusLabel = data?.status === 'running' ? 'Running' : data?.status ?? 'Unknown';
</script>

{#if loading && !data}
  <CardSkeleton lines={6} />
{:else}
  <Card.Root class="card-hover">
    <Card.Header class="flex flex-row items-center justify-between pb-2">
      <div class="flex items-center gap-2">
        <Server class="h-4 w-4 text-muted-foreground" />
        <Card.Title class="text-sm font-medium">Server Status</Card.Title>
      </div>
      {#if data}
        <Badge
          variant="outline"
          class="text-[10px] {statusColor} border-current"
        >
          {statusLabel}
        </Badge>
      {/if}
    </Card.Header>
    <Card.Content>
      {#if data}
        <div class="space-y-0.5">
          <StatItem label="Version" value={data.version} />
          <StatItem label="API Port" value={data.apiPort} />
          <StatItem label="WebSocket Port" value={data.websocketPort} />
          <StatItem label="Global Timeout" value={data.globalTimeout} unit="s" />
          <StatItem label="Max Loaded Models" value={data.maxLoadedModels} />
          <StatItem label="Default Backend" value={data.defaultBackend} />
        </div>
      {:else}
        <p class="text-sm text-muted-foreground text-center py-4">
          Cannot reach Lemonade server
        </p>
      {/if}
    </Card.Content>
  </Card.Root>
{/if}
