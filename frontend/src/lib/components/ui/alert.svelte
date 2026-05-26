<script lang="ts">
  import { cn } from '$lib/utils/cn';

  let { class: className = '' } = $$props;
  let { variant = 'default' } = $$props;
  let { icon = null } = $$props;
</script>

<div
  class={cn(
    'relative flex w-full items-center rounded-lg border border-border bg-background p-4',
    className
  )}
>
  {#if icon}
    <div
      class="mr-4 rounded-full p-1"
      class:bg-destructive={variant === 'destructive'}
      class:text-destructive-foreground={variant === 'destructive'}
    >
      <svelte:component this={icon} class="h-4 w-4" />
    </div>
  {/if}
  <div class="flex-1 space-y-1">
    <p class="text-sm font-medium leading-none">{$$slots.default?.()}</p>
  </div>
</div>
