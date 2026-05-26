<!--
  PlaceholderCard — "Coming in M{X}" card for unimplemented pages.

  Shows a preview of what the page will contain.
-->
<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Badge } from '$lib/components/ui/badge';
  import { Construction } from 'lucide-svelte';

  export let milestone: string;
  export let features: string[] = [];
</script>

<Card.Root class="border-dashed border-muted-foreground/25">
  <Card.Content class="flex flex-col items-center justify-center py-12 text-center">
    <div class="rounded-full bg-muted p-3 mb-4">
      <Construction class="h-6 w-6 text-muted-foreground" />
    </div>
    <p class="text-muted-foreground font-medium mb-1">
      Coming in Milestone {milestone}
    </p>
    {#if features.length > 0}
      <div class="flex flex-wrap gap-1.5 mt-3 justify-center">
        {#each features as feature}
          <Badge variant="secondary" class="text-[10px]">{feature}</Badge>
        {/each}
      </div>
    {/if}
  </Card.Content>
</Card.Root>
