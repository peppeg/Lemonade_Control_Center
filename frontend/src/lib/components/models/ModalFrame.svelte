<!--
  ModalFrame — Local M5-only modal wrapper.
  Not a global UI primitive, not shadcn, not bits-ui.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { X } from 'lucide-svelte';

  export let open: boolean = false;
  export let title: string = '';
  export let description: string = '';
  export let widthClass: string = 'sm:max-w-[520px]';

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
      class="absolute inset-0 bg-black/70 backdrop-blur-sm"
      aria-label="Close dialog"
      on:click={close}
    ></button>

    <div
      role="dialog"
      aria-modal="true"
      class="relative z-10 max-h-[90vh] w-full overflow-hidden rounded border border-[#4a4d39] bg-[#171918] shadow-2xl {widthClass}"
    >
      <div class="flex items-start justify-between gap-4 border-b border-[#30342b] px-5 py-4">
        <div class="min-w-0">
          <h2 class="ops-title text-lg">{title}</h2>
          {#if description}
            <p class="ops-subtitle break-all">{description}</p>
          {/if}
        </div>
        <button class="ops-button min-h-8 px-2" type="button" aria-label="Close dialog" on:click={close}>
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="max-h-[calc(90vh-80px)] overflow-y-auto px-5 py-4">
        <slot />
      </div>
    </div>
</div>
{/if}
