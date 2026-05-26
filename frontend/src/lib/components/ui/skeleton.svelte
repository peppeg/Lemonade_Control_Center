<script lang="ts">
  export let class: className = '';
</script>

<div class="animate-pulse rounded-md bg-muted {className}" {...$$restProps}>
  <slot />
</div>
