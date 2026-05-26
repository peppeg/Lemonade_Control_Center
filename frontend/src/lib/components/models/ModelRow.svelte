<!--
  ModelRow — Single row in the models table.
-->
<script lang="ts">
  import { Badge } from '$lib/components/ui/badge';
  import ModelActions from './ModelActions.svelte';
  import type { ModelEntry } from '$lib/types';

  export let model: ModelEntry;
  export let deleteEnabled: boolean = false;
</script>

<div class="grid grid-cols-[1fr_80px_80px_auto] gap-2 px-4 py-2.5 items-center hover:bg-muted/30 transition-colors">
  <!-- Name -->
  <div class="min-w-0">
    <span class="text-sm font-medium truncate block" title={model.name}>
      {model.name}
    </span>
    {#if model.details}
      {@const family = model.details.family as string}
      {@const quant = model.details.quantization_level as string}
      {#if family || quant}
        <span class="text-[10px] text-muted-foreground">
          {[family, quant].filter(Boolean).join(' • ')}
        </span>
      {/if}
    {/if}
  </div>

  <!-- Size -->
  <span class="text-xs text-muted-foreground text-right font-mono">
    {model.sizeFormatted}
  </span>

  <!-- Status -->
  <div class="flex justify-center">
    {#if model.isLoaded}
      <Badge variant="outline" class="text-[10px] text-status-ok border-status-ok">
        loaded
      </Badge>
    {:else}
      <Badge variant="secondary" class="text-[10px]">saved</Badge>
    {/if}
  </div>

  <!-- Actions -->
  <ModelActions {model} {deleteEnabled} />
</div>
