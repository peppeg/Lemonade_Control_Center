<!--
  AlertItem — Single alert row with icon, title, description, and suggestion.
-->
<script lang="ts">
  import type { SmartAlert } from '$lib/types';
  import { ChevronDown } from 'lucide-svelte';

  export let alert: SmartAlert;

  let expanded = false;

  const levelStyles: Record<string, string> = {
    error: 'border-status-error/30 bg-status-error/5',
    warning: 'border-status-warn/30 bg-status-warn/5',
    info: 'border-border bg-muted/30',
  };
</script>

<button
  class="w-full text-left rounded-md border px-3 py-2.5 transition-colors cursor-pointer
         {levelStyles[alert.level] ?? levelStyles.info}"
  on:click={() => expanded = !expanded}
>
  <div class="flex items-start gap-2.5">
    <span class="text-base shrink-0 mt-0.5">{alert.icon}</span>
    <div class="flex-1 min-w-0">
      <div class="flex items-center justify-between gap-2">
        <span class="text-sm font-medium">{alert.title}</span>
        <ChevronDown
          class="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform
                 {expanded ? 'rotate-180' : ''}"
        />
      </div>
      {#if expanded}
        <p class="text-xs text-muted-foreground mt-1.5 leading-relaxed">
          {alert.description}
        </p>
        <p class="text-xs text-lemon mt-1.5">
          💡 {alert.suggestion}
        </p>
      {:else}
        <p class="text-xs text-muted-foreground mt-0.5 truncate">
          {alert.description}
        </p>
      {/if}
    </div>
  </div>
</button>
