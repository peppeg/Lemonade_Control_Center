<script>
  import PageHeader from '$lib/components/shared/PageHeader.svelte';
  import PlaceholderCard from '$lib/components/shared/PlaceholderCard.svelte';
  import { Settings } from 'lucide-svelte';
</script>

<div class="space-y-6">
  <PageHeader
    title="Configuration"
    description="Runtime config and request defaults — buttons, fields, or raw JSON."
    milestone="M6"
    icon={Settings}
  />
  <PlaceholderCard
    milestone="6"
    features={['Quick Buttons', 'Manual Fields', 'JSON Editor', 'Presets', 'Apply & Load']}
  />
</div>
