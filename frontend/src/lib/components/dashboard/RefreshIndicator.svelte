<!--
  RefreshIndicator — Shows seconds since last refresh + manual refresh button.
-->
<script lang="ts">
  import { secondsSinceRefresh, refreshDashboard, dashboardLoading } from '$lib/stores/dashboard';
  import { RefreshCw } from 'lucide-svelte';
  import { Button } from '$lib/components/ui/button';

  $: isRefreshing = $dashboardLoading === 'loading' || $dashboardLoading === 'partial';
</script>

<div class="flex items-center gap-2">
  <span class="text-xs text-muted-foreground">
    {#if isRefreshing}
      Refreshing…
    {:else if $secondsSinceRefresh < 5}
      Just now
    {:else}
      {$secondsSinceRefresh}s ago
    {/if}
  </span>
  <Button
    variant="ghost"
    size="icon"
    class="h-7 w-7"
    disabled={isRefreshing}
    on:click={() => refreshDashboard()}
  >
    <RefreshCw class="h-3.5 w-3.5 {isRefreshing ? 'animate-spin' : ''}" />
  </Button>
</div>
