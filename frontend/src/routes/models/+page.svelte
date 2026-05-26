<script>
  import PageHeader from '$lib/components/shared/PageHeader.svelte';
  import PlaceholderCard from '$lib/components/shared/PlaceholderCard.svelte';
  import { Cpu } from 'lucide-svelte';
</script>

<div class="space-y-6">
  <PageHeader
    title="Models"
    description="Browse, load, unload, and manage your downloaded models."
    milestone="M5"
    icon={Cpu}
  />
  <PlaceholderCard
    milestone="5"
    features={['Model Table', 'Load/Unload', 'Runtime Parameters', 'Cmdline Parser', 'Delete (gated)']}
  />
</div>
