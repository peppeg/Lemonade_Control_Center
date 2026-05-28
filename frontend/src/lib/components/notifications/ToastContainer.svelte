<script lang="ts">
  import { toasts } from '$lib/stores/notifications';
  import Toast from './Toast.svelte';
</script>

<div class="pointer-events-none fixed bottom-10 right-4 z-50 flex w-[calc(100vw-32px)] max-w-sm flex-col gap-3">
  {#each $toasts as toast (toast.id)}
    <div class="pointer-events-auto">
      <Toast {toast} />
    </div>
  {/each}
</div>
