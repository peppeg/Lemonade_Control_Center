<!--
  LoadedModelCard — Currently loaded model with parsed runtime parameters.
-->
<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Badge } from '$lib/components/ui/badge';
  import StatItem from './StatItem.svelte';
  import CardSkeleton from './CardSkeleton.svelte';
  import { Cpu, ArrowRight } from 'lucide-svelte';
  import type { LoadedModelInfo } from '$lib/types';
  import { formatGB } from '$lib/utils/format';

  export let data: LoadedModelInfo | null;
  export let loading: boolean = false;
</script>

{#if loading && !data}
  <CardSkeleton lines={7} />
{:else}
  <Card.Root class="card-hover">
    <Card.Header class="flex flex-row items-center justify-between pb-2">
      <div class="flex items-center gap-2">
        <Cpu class="h-4 w-4 text-muted-foreground" />
        <Card.Title class="text-sm font-medium">Loaded Model</Card.Title>
      </div>
      {#if data}
        <Badge variant="outline" class="text-[10px] text-status-ok border-status-ok">Active</Badge>
      {/if}
    </Card.Header>
    <Card.Content>
      {#if data}
        <!-- Model name -->
        <p class="text-sm font-semibold text-lemon truncate mb-3" title={data.name}>
          {data.name}
        </p>

        <!-- Key params -->
        <div class="space-y-0.5">
          <StatItem label="Backend" value={data.backend ?? 'unknown'} />
          <StatItem label="Context" value={data.ctxSize?.toLocaleString() ?? null} />
          <StatItem label="GPU Layers" value={data.ngl} />
          <StatItem label="mmap" value={data.mmap === null ? null : data.mmap ? 'on' : 'off'} />
          {#if data.specType}
            <StatItem label="Speculative" value={data.specType} />
            {#if data.specDraftMax}
              <StatItem label="Draft max" value={data.specDraftMax} />
            {/if}
          {/if}
          {#if data.reasoningFormat}
            <StatItem label="Reasoning" value={data.reasoningFormat} />
          {/if}
        </div>

        <!-- Process info -->
        <div class="border-t border-border mt-3 pt-2 space-y-0.5">
          <StatItem label="PID" value={data.pid} mono />
          <StatItem label="RSS" value={data.rssGb ? formatGB(data.rssGb) : null} />
          <StatItem label="CPU" value={data.cpuPercent !== null ? `${data.cpuPercent}%` : null} />
          <StatItem label="Uptime" value={data.uptime} />
        </div>

        <!-- Link to models page -->
        <a href="/models" class="flex items-center gap-1 text-xs text-lemon mt-3 hover:underline">
          Details <ArrowRight class="h-3 w-3" />
        </a>
      {:else}
        <div class="flex flex-col items-center py-4 text-center">
          <p class="text-sm text-muted-foreground mb-1">No model loaded</p>
          <a
            href="/models"
            class="mt-2 inline-flex h-9 items-center rounded-md border border-input bg-background px-3 text-xs font-medium hover:bg-accent hover:text-accent-foreground"
          >
            Load a model
          </a>
        </div>
      {/if}
    </Card.Content>
  </Card.Root>
{/if}
