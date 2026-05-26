<script>
  import PageHeader from '$lib/components/shared/PageHeader.svelte';
  import PlaceholderCard from '$lib/components/shared/PlaceholderCard.svelte';
  import { LayoutDashboard } from 'lucide-svelte';
</script>

<div class="space-y-6">
  <PageHeader
    title="Dashboard"
    description="Health status, model info, last task stats, and smart alerts."
    milestone="M4"
    icon={LayoutDashboard}
  />
  <PlaceholderCard
    milestone="4"
    features={['Server Status', 'Loaded Model', 'Last Task Stats', 'Smart Alerts', 'Auto-refresh']}
  />
</div>
