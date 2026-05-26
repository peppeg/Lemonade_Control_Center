<script>
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  onMount(() => {
    goto('/dashboard', { replaceState: true });
  });
</script>

<!-- Brief flash while redirecting -->
<div class="flex items-center justify-center h-full">
  <span class="text-2xl animate-pulse">🍋</span>
</div>
