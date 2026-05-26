<script lang="ts">
  import * as TooltipPrimitive from 'bits-ui';
  import Content from './tooltip-content.svelte';
  import Trigger from './tooltip-trigger.svelte';

  let { open = $state(false) } = $$props;
  let { delayDuration = 100 } = $$props;
</script>

<TooltipPrimitive.Root {open} {delayDuration}>
  <slot name="trigger" {open} />
  <Content>
    <slot />
  </Content>
</TooltipPrimitive.Root>
