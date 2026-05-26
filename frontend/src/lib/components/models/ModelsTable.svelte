<!--
  ModelsTable — Table of all downloaded models with actions.
-->
<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Badge } from '$lib/components/ui/badge';
  import ModelRow from './ModelRow.svelte';
  import { Skeleton } from '$lib/components/ui/skeleton';
  import { Package } from 'lucide-svelte';
  import type { ModelEntry } from '$lib/types';

  export let models: ModelEntry[];
  export let loading: boolean = false;
  export let deleteEnabled: boolean = false;
</script>

<Card.Root>
  <Card.Header class="flex flex-row items-center justify-between pb-2">
    <div class="flex items-center gap-2">
      <Package class="h-4 w-4 text-muted-foreground" />
      <Card.Title class="text-sm font-medium">Downloaded Models</Card.Title>
    </div>
    <Badge variant="secondary" class="text-[10px]">
      {models.length} model{models.length !== 1 ? 's' : ''}
    </Badge>
  </Card.Header>

  <Card.Content class="p-0">
    {#if loading}
      <div class="p-4 space-y-3">
        {#each Array(3) as _}
          <div class="flex items-center justify-between">
            <Skeleton class="h-4 w-48" />
            <Skeleton class="h-4 w-24" />
          </div>
        {/each}
      </div>
    {:else if models.length === 0}
      <div class="p-8 text-center text-sm text-muted-foreground">
        No models found. Pull a model using the Lemonade CLI.
      </div>
    {:else}
      <!-- Table header -->
      <div class="grid grid-cols-[1fr_80px_80px_auto] gap-2 px-4 py-2 border-b border-border text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
        <span>Name</span>
        <span class="text-right">Size</span>
        <span class="text-center">Status</span>
        <span class="text-right">Actions</span>
      </div>

      <!-- Table rows -->
      <div class="divide-y divide-border">
        {#each models as model (model.name)}
          <ModelRow {model} {deleteEnabled} />
        {/each}
      </div>
    {/if}
  </Card.Content>
</Card.Root>
