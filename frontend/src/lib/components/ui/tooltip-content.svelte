<script lang="ts">
  import * as TooltipPrimitive from 'bits-ui';
  import { cn } from '$lib/utils/cn';

  let { class: className = '' } = $$props;
  let { sideOffset = 4 } = $$props;
</script>

<TooltipPrimitive.Content
  class={cn(
    'z-50 overflow-hidden rounded-md border border-border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md animate-in fade-in-0 zoom-in-95 duration-200',
    className
  )}
  {sideOffset}
  {...$$restProps}
>
  <slot />
</TooltipPrimitive.Content>
