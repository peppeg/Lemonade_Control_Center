<script>
  import PageHeader from '$lib/components/shared/PageHeader.svelte';
  import PlaceholderCard from '$lib/components/shared/PlaceholderCard.svelte';
  import { Monitor } from 'lucide-svelte';
</script>

<div class="space-y-6">
  <PageHeader
    title="System"
    description="Hardware stats, emergency controls, and diagnostic bundle."
    milestone="M8"
    icon={Monitor}
  />
  <PlaceholderCard
    milestone="8"
    features={['RAM/CPU/Disk', 'Temperatures', 'llama-server PID', 'Stop & Unload', 'Restart (gated)', 'Diagnostic Bundle']}
  />
</div>
