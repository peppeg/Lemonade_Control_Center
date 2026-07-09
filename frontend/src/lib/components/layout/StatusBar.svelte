<!--
  StatusBar — Footer with live system info.

  Shows: Lemonade version, backend type, RAM usage, LCC version.
  Data comes from health polling (no additional API calls).
-->
<script lang="ts">
  import { healthData, connectionStatus } from '$lib/stores/connection';
  import { capabilities } from '$lib/stores/capabilities';
  import { Zap } from 'lucide-svelte';
</script>

<footer class="flex min-h-[28px] items-center justify-between border-t border-[#34392d] bg-[#111312] px-4 py-1 text-[11px] text-muted-foreground select-none">
  <!-- Left: Lemonade info -->
  <div class="flex items-center gap-3">
    {#if $connectionStatus !== 'disconnected'}
      <div class="flex items-center gap-1.5">
        <Zap class="h-3 w-3 text-lemon" />
        <span>Lemonade {$capabilities.lemonade_version ?? 'unknown'}</span>
      </div>
      {#if $healthData?.lemonade_url}
        <span class="text-[#4a4f3a]">|</span>
        <span class="ops-mono">{$healthData.lemonade_url}</span>
      {/if}
    {:else}
      <span class="text-status-error">Backend offline</span>
    {/if}
  </div>

  <!-- Right: LCC version + probe date -->
  <div class="flex items-center gap-3">
    {#if $capabilities.probe_timestamp}
      <span class="hidden md:inline">Probe: {new Date($capabilities.probe_timestamp).toLocaleString()}</span>
    {/if}
    <span>LCC v{$healthData?.app_version ?? '0.2.0'}</span>
  </div>
</footer>
