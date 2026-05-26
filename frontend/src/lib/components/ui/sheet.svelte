<script lang="ts">
  export let open = $bindable(false);
  export let side: 'top' | 'bottom' | 'left' | 'right' = 'left';
</script>

<div class="fixed inset-0 z-50">
  <div
    class="fixed inset-0 bg-background/80 backdrop-blur-sm transition-opacity"
    class:inset-0={side === 'left' || side === 'right'}
    class:top-0={side === 'top'}
    class:bottom-0={side === 'bottom'}
    class:left-0={side === 'left'}
    class:right-0={side === 'right'}
    on:click={() => (open = false)}
  />

  <div
    class="fixed z-50 flex h-full w-64 flex-col bg-background shadow-lg transition-transform duration-300"
    class:left-0={side === 'left'}
    class:right-0={side === 'right'}
    class:top-0={side === 'top'}
    class:bottom-0={side === 'bottom'}
    class:translate-x-0={side === 'left' && open}
    class:-translate-x-full={side === 'left' && !open}
    class:translate-y-0={side === 'top' && open}
    class:-translate-y-full={side === 'top' && !open}
  >
    <slot />
  </div>
</div>
