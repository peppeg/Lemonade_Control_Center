<!--
  CopyMenu — Copy model name to clipboard.
-->
<script lang="ts">
  import { Button } from '$lib/components/ui/button';
  import { Copy, Check } from 'lucide-svelte';

  export let modelName: string;

  let copied = false;

  async function copyName() {
    try {
      await navigator.clipboard.writeText(modelName);
      copied = true;
      setTimeout(() => copied = false, 2000);
    } catch {}
  }
</script>

<Button
  variant="ghost"
  size="icon"
  class="h-7 w-7"
  title={copied ? 'Copied!' : 'Copy model name'}
  on:click={copyName}
>
  {#if copied}
    <Check class="h-3.5 w-3.5 text-status-ok" />
  {:else}
    <Copy class="h-3.5 w-3.5" />
  {/if}
</Button>
