<!--
  ConnectionBadge — Animated dot with status label and tooltip.

  States:
    🟢 Connected   — Backend + Lemonade OK
    🟡 Degraded    — Backend OK, Lemonade unreachable
    🔴 Offline     — Backend unreachable
    ⚪ Checking... — Initial poll in progress
-->
<script lang="ts">
  import { connectionStatus, connectionLabel, connectionColorClass, healthData } from '$lib/stores/connection';

  $: tooltipText = (() => {
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

<div
  class="ops-badge {$connectionStatus === 'connected' ? 'ops-badge-ok' : $connectionStatus === 'degraded' ? 'ops-badge-warn' : $connectionStatus === 'disconnected' ? 'ops-badge-danger' : ''}"
  title={tooltipText}
>
  <!-- Animated dot -->
  <span class="relative flex h-2.5 w-2.5">
    {#if $connectionStatus === 'connected'}
      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-status-ok opacity-40"></span>
    {/if}
    <span class="relative inline-flex h-2.5 w-2.5 rounded-full {$connectionColorClass}"
          style="background-color: currentColor;"></span>
  </span>

  <span class="hidden sm:inline">
    {$connectionLabel.toUpperCase()}
  </span>
</div>
