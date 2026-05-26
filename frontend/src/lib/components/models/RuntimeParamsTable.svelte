<!--
  RuntimeParamsTable — Parsed llama-server command line parameters.
  Shows only parameters that have a value (no nulls).
-->
<script lang="ts">
  import type { RuntimeParams } from '$lib/types';
  import { Button } from '$lib/components/ui/button';
  import { Copy, Check } from 'lucide-svelte';

  export let params: RuntimeParams;

  let copiedRaw = false;

  // Build display rows from params, filtering nulls
  interface ParamRow {
    label: string;
    value: string;
  }

  $: rows = buildRows(params);

  function buildRows(p: RuntimeParams): ParamRow[] {
    const r: ParamRow[] = [];
    if (p.ctxSize !== null) r.push({ label: 'ctx-size', value: p.ctxSize.toLocaleString() });
    if (p.backend) r.push({ label: 'backend', value: p.backend });
    if (p.ngl !== null) r.push({ label: 'ngl', value: String(p.ngl) });
    if (p.mmap !== null) r.push({ label: 'mmap', value: p.mmap ? 'on' : 'off' });
    if (p.jinja) r.push({ label: 'jinja', value: 'on' });
    if (p.contextShift !== null) r.push({ label: 'context-shift', value: p.contextShift ? 'on' : 'off' });
    if (p.keep !== null) r.push({ label: 'keep', value: String(p.keep) });
    if (p.reasoningFormat) r.push({ label: 'reasoning-format', value: p.reasoningFormat });
    if (p.specType) r.push({ label: 'speculative', value: p.specType });
    if (p.specDraftMax !== null) r.push({ label: 'draft max', value: String(p.specDraftMax) });
    if (p.specDraftPMin !== null) r.push({ label: 'draft p-min', value: String(p.specDraftPMin) });
    if (p.mmproj) r.push({ label: 'mmproj', value: 'yes' });
    if (p.port !== null) r.push({ label: 'port', value: String(p.port) });
    return r;
  }

  async function copyRawCmdline() {
    try {
      await navigator.clipboard.writeText(params.rawCmdline);
      copiedRaw = true;
      setTimeout(() => copiedRaw = false, 2000);
    } catch {}
  }
</script>

<div class="space-y-2">
  <div class="flex items-center justify-between">
    <span class="text-xs font-medium text-muted-foreground uppercase tracking-wider">
      Runtime Parameters
    </span>
    <Button
      variant="ghost"
      size="sm"
      class="h-6 text-[10px] gap-1"
      on:click={copyRawCmdline}
    >
      {#if copiedRaw}
        <Check class="h-3 w-3 text-status-ok" /> Copied
      {:else}
        <Copy class="h-3 w-3" /> Copy cmdline
      {/if}
    </Button>
  </div>

  <div class="rounded-md border border-border overflow-hidden">
    <table class="w-full text-sm">
      <tbody>
        {#each rows as row, i}
          <tr class="{i % 2 === 0 ? 'bg-muted/30' : ''}">
            <td class="px-3 py-1.5 text-xs text-muted-foreground font-mono w-40">{row.label}</td>
            <td class="px-3 py-1.5 text-xs font-medium font-mono">{row.value}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>
