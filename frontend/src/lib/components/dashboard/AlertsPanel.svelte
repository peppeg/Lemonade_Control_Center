<!--
  AlertsPanel — Container for all active smart alerts.
-->
<script lang="ts">
  import AlertItem from './AlertItem.svelte';
  import { Badge } from '$lib/components/ui/badge';
  import { ShieldAlert } from 'lucide-svelte';
  import type { SmartAlert } from '$lib/types';

  export let alerts: SmartAlert[] = [];

  $: warningCount = alerts.filter(a => a.level === 'warning').length;
  $: errorCount = alerts.filter(a => a.level === 'error').length;
</script>

{#if alerts.length > 0}
  <div class="space-y-2">
    <div class="flex items-center gap-2">
      <ShieldAlert class="h-4 w-4 text-status-warn" />
      <span class="text-sm font-medium">Alerts</span>
      {#if errorCount > 0}
        <Badge variant="destructive" class="text-[10px]">{errorCount} error{errorCount > 1 ? 's' : ''}</Badge>
      {/if}
      {#if warningCount > 0}
        <Badge variant="outline" class="text-[10px] text-status-warn border-status-warn">
          {warningCount} warning{warningCount > 1 ? 's' : ''}
        </Badge>
      {/if}
    </div>

    <div class="space-y-1.5">
      {#each alerts as alert (alert.id)}
        <AlertItem {alert} />
      {/each}
    </div>
  </div>
{/if}
