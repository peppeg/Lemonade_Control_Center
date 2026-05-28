<script lang="ts">
  export let title: string;
  export let value = '';
</script>

<section class="ops-panel">
  <div class="ops-card-header">
    <h2 class="ops-title">{title}</h2>
    {#if value}
      <span class="ops-value">{value}</span>
    {/if}
  </div>
  <div class="p-4">
    <slot />
  </div>
</section>
