<!--
  ConnectionBadge — Animated dot with status label and tooltip.

  States:
    🟢 Connected   — Backend + Lemonade OK
    🟡 Degraded    — Backend OK, Lemonade unreachable
    🔴 Offline     — Backend unreachable
    ⚪ Checking... — Initial poll in progress
-->
<script lang="ts">
  import {
    connectionStatus, connectionLabel, connectionColorClass,
    healthData, lastHealthCheck
  } from '$lib/stores/connection';
  import * as Tooltip from '$lib/components/ui/tooltip';
  import { formatTime } from '$lib/utils/format';

  const tooltipText = $derived(() => {
    switch ($connectionStatus) {
      case 'connected':
        return `Lemonade reachable at ${$healthData?.lemonade_url ?? 'unknown'}`;
      case 'degraded':
        return `Backend OK but Lemonade not responding at ${$healthData?.lemonade_url ?? 'unknown'}`;
      case 'disconnected':
        return 'Cannot reach the LCC backend. Is it running?';
      case 'checking':
        return 'Checking connection...';
    }
  })();
</script>

<Tooltip.Root openDelay={200}>
  <Tooltip.Trigger>
    <div class="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted/50 hover:bg-muted transition-colors cursor-default">
      <!-- Animated dot -->
      <span class="relative flex h-2.5 w-2.5">
        {#if $connectionStatus === 'connected'}
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-status-ok opacity-40"></span>
        {/if}
        <span class="relative inline-flex rounded-full h-2.5 w-2.5 {$connectionColorClass}"
              style="background-color: currentColor;"></span>
      </span>

      <span class="text-xs font-medium text-muted-foreground hidden sm:inline">
        {$connectionLabel}
      </span>
    </div>
  </Tooltip.Trigger>
  <Tooltip.Content side="bottom">
    <p class="max-w-[250px]">{tooltipText}</p>
    {#if $lastHealthCheck}
      <p class="text-xs text-muted-foreground mt-1">
        Last check: {formatTime($lastHealthCheck.toISOString())}
      </p>
    {/if}
  </Tooltip.Content>
</Tooltip.Root>
