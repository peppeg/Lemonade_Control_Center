<script lang="ts">
  import { cardVariants } from './variants';
</script>

<div class={cardVariants()} {...$$restProps}>
  <slot />
</div>
