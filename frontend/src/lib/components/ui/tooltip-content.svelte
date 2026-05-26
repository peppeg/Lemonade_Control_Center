<script lang="ts">
  import { cn } from '$lib/utils/cn';

  export let className = '';
  export let sideOffset = 4;
</script>

<div
  class={cn(
    'z-50 overflow-hidden rounded-md border border-border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95 duration-200',
    className
  )}
  style="--side-offset: {sideOffset}px;"
  {...$$restProps}
>
  <slot />
</div>
