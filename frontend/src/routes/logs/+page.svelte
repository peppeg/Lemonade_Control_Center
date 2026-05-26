<script>
  import PageHeader from '$lib/components/shared/PageHeader.svelte';
  import PlaceholderCard from '$lib/components/shared/PlaceholderCard.svelte';
  import { ScrollText } from 'lucide-svelte';
</script>

<div class="space-y-6">
  <PageHeader
    title="Logs & Stats"
    description="Parsed task stats, filtered log viewer, and live streaming."
    milestone="M7"
    icon={ScrollText}
  />
  <PlaceholderCard
    milestone="7"
    features={['Last Task Card', 'Finish Reason', 'Log Viewer', 'Filters', 'WebSocket Live', 'Export']}
  />
</div>
