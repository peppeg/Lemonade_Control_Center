<!--
  CardSkeleton — Loading placeholder matching card dimensions.
-->
<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Skeleton } from '$lib/components/ui/skeleton';

  export let lines: number = 5;
</script>

<Card.Root>
  <Card.Header class="pb-3">
    <Skeleton class="h-4 w-32" />
  </Card.Header>
  <Card.Content class="space-y-2.5">
    {#each Array(lines) as _, i}
      <div class="flex justify-between">
        <Skeleton class="h-3 w-20" />
        <Skeleton class="h-3 w-16" />
      </div>
    {/each}
  </Card.Content>
</Card.Root>
