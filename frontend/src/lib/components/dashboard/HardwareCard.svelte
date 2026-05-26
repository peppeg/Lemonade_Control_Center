<!--
  HardwareCard — RAM, CPU, Disk snapshot with visual progress bars.
-->
<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import CardSkeleton from './CardSkeleton.svelte';
  import { HardDrive } from 'lucide-svelte';
  import type { HardwareInfo } from '$lib/types';
  import { formatGB, formatPercent } from '$lib/utils/format';

  export let data: HardwareInfo | null;
  export let loading: boolean = false;

  function barColor(pct: number): string {
    if (pct > 90) return 'bg-status-error';
    if (pct > 75) return 'bg-status-warn';
    return 'bg-lemon';
  }
</script>

{#if loading && !data}
  <CardSkeleton lines={4} />
{:else}
  <Card.Root class="card-hover">
    <Card.Header class="flex flex-row items-center gap-2 pb-2">
      <HardDrive class="h-4 w-4 text-muted-foreground" />
      <Card.Title class="text-sm font-medium">Hardware</Card.Title>
    </Card.Header>
    <Card.Content>
      {#if data}
        <div class="space-y-3">
          <!-- RAM -->
          <div>
            <div class="flex justify-between text-xs mb-1">
              <span class="text-muted-foreground">RAM</span>
              <span>{formatGB(data.ram_used_gb)} / {formatGB(data.ram_total_gb)} ({formatPercent(data.ram_percent)})</span>
            </div>
            <div class="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500 {barColor(data.ram_percent)}"
                style="width: {data.ram_percent}%"
              ></div>
            </div>
          </div>

          <!-- CPU -->
          <div>
            <div class="flex justify-between text-xs mb-1">
              <span class="text-muted-foreground">CPU</span>
              <span>{formatPercent(data.cpu_percent)} ({data.cpu_count} cores)</span>
            </div>
            <div class="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500 {barColor(data.cpu_percent)}"
                style="width: {data.cpu_percent}%"
              ></div>
            </div>
          </div>

          <!-- Disk -->
          {#if data.disk_total_gb}
            <div>
              <div class="flex justify-between text-xs mb-1">
                <span class="text-muted-foreground">Disk</span>
                <span>{formatGB(data.disk_used_gb ?? 0)} / {formatGB(data.disk_total_gb)}</span>
              </div>
              <div class="h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500 {barColor(data.disk_percent ?? 0)}"
                  style="width: {data.disk_percent ?? 0}%"
                ></div>
              </div>
            </div>
          {/if}

          <!-- Swap (only if non-zero) -->
          {#if data.swap_total_gb > 0}
            <div class="text-xs text-muted-foreground">
              Swap: {formatGB(data.swap_used_gb)} / {formatGB(data.swap_total_gb)}
            </div>
          {/if}
        </div>
      {:else}
        <p class="text-sm text-muted-foreground text-center py-4">
          Hardware data unavailable
        </p>
      {/if}
    </Card.Content>
  </Card.Root>
{/if}
