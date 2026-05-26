<!--
  PageHeader — Reusable page title with icon and milestone badge.
-->
<script lang="ts">
  import { Badge } from '$lib/components/ui/badge';
  import type { ComponentType } from 'svelte';

  export let title: string;
  export let description: string = '';
  export let milestone: string = '';
  export let icon: ComponentType | null = null;
</script>

<div class="space-y-1">
  <div class="flex items-center gap-3">
    {#if icon}
      <svelte:component this={icon} class="h-6 w-6 text-lemon" />
    {/if}
    <h1 class="text-2xl font-semibold tracking-tight">{title}</h1>
    {#if milestone}
      <Badge variant="outline" class="text-[10px] text-muted-foreground">{milestone}</Badge>
    {/if}
  </div>
  {#if description}
    <p class="text-sm text-muted-foreground">{description}</p>
  {/if}
</div>
