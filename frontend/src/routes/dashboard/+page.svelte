<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import {
    dashboardData, dashboardLoading,
    startDashboardPolling, stopDashboardPolling,
  } from '$lib/stores/dashboard';
  import { LayoutDashboard } from 'lucide-svelte';

  import PageHeader from '$lib/components/shared/PageHeader.svelte';
  import RefreshIndicator from '$lib/components/dashboard/RefreshIndicator.svelte';
  import ServerStatusCard from '$lib/components/dashboard/ServerStatusCard.svelte';
  import LoadedModelCard from '$lib/components/dashboard/LoadedModelCard.svelte';
  import LastTaskCard from '$lib/components/dashboard/LastTaskCard.svelte';
  import HardwareCard from '$lib/components/dashboard/HardwareCard.svelte';
  import AlertsPanel from '$lib/components/dashboard/AlertsPanel.svelte';

  $: isLoading = $dashboardLoading === 'loading';

  onMount(() => {
    startDashboardPolling(10_000); // Refresh every 10 seconds
  });

  onDestroy(() => {
    stopDashboardPolling();
  });
</script>

<div class="space-y-6">
  <!-- Page header with refresh indicator -->
  <div class="flex items-start justify-between gap-4">
    <PageHeader
      title="Dashboard"
      description="Lemonade server status at a glance."
      icon={LayoutDashboard}
    />
    <RefreshIndicator />
  </div>

  <!-- Cards grid -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <ServerStatusCard
      data={$dashboardData.serverStatus}
      loading={isLoading}
    />
    <LoadedModelCard
      data={$dashboardData.loadedModel}
      loading={isLoading}
    />
    <HardwareCard
      data={$dashboardData.hardware}
      loading={isLoading}
    />
    <LastTaskCard
      data={$dashboardData.lastTask}
      loading={isLoading}
    />
  </div>

  <!-- Smart alerts (below cards, full width) -->
  <AlertsPanel alerts={$dashboardData.alerts} />
</div>
