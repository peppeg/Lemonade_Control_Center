<script lang="ts">
  import { type VariantProps, tv } from 'tailwind-variants';

  const separatorVariants = tv({
    base: 'shrink-0 bg-border',
    variants: {
      orientation: {
        horizontal: 'h-[1px] w-full',
        vertical: 'h-full w-[1px]',
      },
    },
    defaultVariants: {
      orientation: 'horizontal',
    },
  });

  export let orientation: VariantProps<typeof separatorVariants>['orientation'] = 'horizontal';
</script>

<div
  class={separatorVariants({ orientation })}
  data-orientation={orientation}
  {...$$restProps}
></div>
