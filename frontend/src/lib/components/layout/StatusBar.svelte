<!--
  StatusBar — Footer with live system info.

  Shows: Lemonade version, backend type, RAM usage, LCC version.
  Data comes from health polling (no additional API calls).
-->
<script lang="ts">
  import { healthData, connectionStatus } from '$lib/stores/connection';
  import { capabilities } from '$lib/stores/capabilities';
  import { Zap, HardDrive, Cpu } from 'lucide-svelte';
</script>

<footer class="flex items-center justify-between px-4 py-1 border-t border-border bg-card text-[11px] text-muted-foreground select-none min-h-[28px]">
  <!-- Left: Lemonade info -->
  <div class="flex items-center gap-3">
    {#if $connectionStatus !== 'disconnected'}
      <div class="flex items-center gap-1.5">
        <Zap class="h-3 w-3 text-lemon" />
        <span>Lemonade {$capabilities.lemonade_version ?? '—'}</span>
      </div>
      {#if $healthData?.lemonade_url}
        <span class="text-border">•</span>
        <span>{$healthData.lemonade_url}</span>
      {/if}
    {:else}
      <span class="text-status-error">Backend offline</span>
    {/if}
  </div>

  <!-- Right: LCC version + probe date -->
  <div class="flex items-center gap-3">
    {#if $capabilities.probe_timestamp}
      <span class="hidden md:inline">Probe: {new Date($capabilities.probe_timestamp).toLocaleDateString()}</span>
    {/if}
    <span>LCC v{$healthData?.app_version ?? '0.1.0'}</span>
  </div>
</footer>
