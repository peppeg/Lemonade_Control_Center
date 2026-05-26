<!--
  StatItem — Single key/value stat row used inside cards.
  Compact, with optional icon and color.
-->
<script lang="ts">
  export let label: string;
  export let value: string | number | null;
  export let unit: string = '';
  export let muted: boolean = false;
  export let mono: boolean = false;
</script>

<div class="flex items-baseline justify-between gap-4 py-0.5">
  <span class="text-xs text-muted-foreground shrink-0">{label}</span>
  <span
    class="text-sm font-medium text-right truncate
           {muted ? 'text-muted-foreground' : 'text-foreground'}
           {mono ? 'font-mono text-xs' : ''}"
  >
    {#if value !== null && value !== undefined}
      {value}{unit}
    {:else}
      <span class="text-muted-foreground/50">—</span>
    {/if}
  </span>
</div>
