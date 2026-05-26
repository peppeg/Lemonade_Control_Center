<script lang="ts">
  export let size: 'sm' | 'md' | 'lg' = 'md';

  const sizes = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-8 w-8' };
</script>

<div class="flex items-center justify-center">
  <div class="animate-spin rounded-full border-2 border-muted border-t-lemon {sizes[size]}"></div>
</div>
