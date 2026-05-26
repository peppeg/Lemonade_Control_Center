<!--
  LastTaskCard — Stats from the last completed inference task.
  Shows token counts, speeds, TTFT, duration, and finish reason with confidence.
-->
<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Badge } from '$lib/components/ui/badge';
  import StatItem from './StatItem.svelte';
  import CardSkeleton from './CardSkeleton.svelte';
  import { Activity, ArrowRight } from 'lucide-svelte';
  import type { LastTaskInfo } from '$lib/types';
  import { formatTPS, formatDuration, formatNumber } from '$lib/utils/format';

  export let data: LastTaskInfo | null;
  export let loading: boolean = false;

  $: finishBadgeVariant = (() => {
    if (!data?.finishReason) return 'secondary';
    if (data.finishReason === 'length') return 'destructive';
    return 'secondary';
  })();

  $: finishLabel = (() => {
    if (!data?.finishReason || data.finishReason === 'unknown') return null;
    const conf = data.finishConfidence === 'inferred' ? ' (inferred)' : '';
    return `${data.finishReason}${conf}`;
  })();
</script>

{#if loading && !data}
  <CardSkeleton lines={8} />
{:else}
  <Card.Root class="card-hover">
    <Card.Header class="flex flex-row items-center justify-between pb-2">
      <div class="flex items-center gap-2">
        <Activity class="h-4 w-4 text-muted-foreground" />
        <Card.Title class="text-sm font-medium">Last Task</Card.Title>
      </div>
      {#if finishLabel}
        <Badge
          variant={finishBadgeVariant}
          class="text-[10px]"
          title={data?.finishEvidence
            ? data.finishConfidence === 'inferred'
              ? `${data.finishEvidence} — inferred from logs`
              : data.finishEvidence
            : `Finish reason: ${data?.finishReason}`}
        >
          {finishLabel}
          {#if data?.finishConfidence === 'inferred'}⚠{/if}
        </Badge>
      {/if}
    </Card.Header>
    <Card.Content>
      {#if data?.available}
        <div class="grid grid-cols-2 gap-x-6 gap-y-0.5">
          <!-- Left column: Tokens -->
          <StatItem
            label="Input"
            value={data.inputTokens !== null ? formatNumber(data.inputTokens) : null}
            unit=" tok"
          />
          <StatItem
            label="Output"
            value={data.outputTokens !== null ? formatNumber(data.outputTokens) : null}
            unit=" tok"
          />

          <!-- Right column: Speeds -->
          <StatItem
            label="Prompt eval"
            value={data.promptEvalTps !== null ? formatTPS(data.promptEvalTps) : null}
          />
          <StatItem
            label="Generation"
            value={data.generationTps !== null ? formatTPS(data.generationTps) : null}
          />

          <!-- Timing -->
          <StatItem
            label="TTFT"
            value={data.ttftSeconds !== null ? `${data.ttftSeconds}s` : null}
          />
          <StatItem
            label="Total"
            value={data.totalDurationSeconds !== null ? formatDuration(data.totalDurationSeconds) : null}
          />
        </div>

        <!-- Link to logs page -->
        <a href="/logs" class="flex items-center gap-1 text-xs text-lemon mt-3 hover:underline">
          Full logs <ArrowRight class="h-3 w-3" />
        </a>
      {:else}
        <p class="text-sm text-muted-foreground text-center py-4">
          No recent task data available
        </p>
      {/if}
    </Card.Content>
  </Card.Root>
{/if}
