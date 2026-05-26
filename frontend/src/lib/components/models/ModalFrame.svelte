<!--
  ModalFrame — Local M5-only modal wrapper.
  Not a global UI primitive, not shadcn, not bits-ui.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  export let open: boolean = false;
  export let title: string = '';
  export let description: string = '';
  export let widthClass: string = 'sm:max-w-[480px]';

  const dispatch = createEventDispatcher<{ close: void }>();

  function close() {
    dispatch('close');
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && open) close();
  }
</script>

{#if open}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4" role="presentation" on:keydown={handleKeydown}>
    <button
      type="button"
      class="absolute inset-0 bg-black/60"
      aria-label="Close dialog"
      on:click={close}
    ></button>

    <div
      role="dialog"
      aria-modal="true"
      class="relative z-10 w-full rounded-lg border border-border bg-card shadow-xl {widthClass}"
    >
      <div class="border-b border-border px-5 py-4">
        <h2 class="text-base font-semibold">{title}</h2>
        {#if description}
          <p class="mt-1 text-sm text-muted-foreground">{description}</p>
        {/if}
      </div>

      <div class="px-5 py-4">
        <slot />
      </div>
    </div>
  </div>
{/if}
