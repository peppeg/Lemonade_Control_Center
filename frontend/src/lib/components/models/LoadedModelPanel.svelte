<!--
  LoadedModelPanel — Prominent card showing the currently loaded model
  with runtime params, process info, and quick actions.
-->
<script lang="ts">
  import * as Card from '$lib/components/ui/card';
  import { Badge } from '$lib/components/ui/badge';
  import { Button } from '$lib/components/ui/button';
  import { Separator } from '$lib/components/ui/separator';
  import RuntimeParamsTable from './RuntimeParamsTable.svelte';
  import UnloadConfirmDialog from './UnloadConfirmDialog.svelte';
  import StatItem from '$lib/components/dashboard/StatItem.svelte';
  import { Cpu } from 'lucide-svelte';
  import { unloadAction } from '$lib/stores/models';
  import type { LoadedModelDetail } from '$lib/types';
  import { formatGB } from '$lib/utils/format';

  export let model: LoadedModelDetail;

  let showUnloadDialog = false;
</script>

<Card.Root class="border-lemon/20 bg-lemon/[0.02]">
  <Card.Header class="flex flex-row items-center justify-between pb-2">
    <div class="flex items-center gap-2 min-w-0">
      <Cpu class="h-5 w-5 text-lemon shrink-0" />
      <Card.Title class="text-base font-semibold truncate">{model.name}</Card.Title>
    </div>
    <Badge variant="outline" class="text-[10px] text-status-ok border-status-ok shrink-0">
      Active
    </Badge>
  </Card.Header>

  <Card.Content class="space-y-4">
    <!-- Runtime Parameters -->
    {#if model.params}
      <RuntimeParamsTable params={model.params} />
    {/if}

    <!-- Process Info -->
    {#if model.process}
      <div>
        <span class="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Process
        </span>
        <div class="grid grid-cols-2 gap-x-6 mt-1">
          <StatItem label="PID" value={model.process.pid} mono />
          <StatItem label="RSS" value={formatGB(model.process.rssGb)} />
          <StatItem label="CPU" value={model.process.cpuPercent} unit="%" />
          <StatItem label="Uptime" value={model.process.uptime} />
        </div>
      </div>
    {/if}

    <Separator />

    <!-- Actions -->
    <div class="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        on:click={() => showUnloadDialog = true}
        disabled={$unloadAction.loading}
      >
        {#if $unloadAction.loading}
          Unloading…
        {:else}
          Unload
        {/if}
      </Button>

    </div>

    {#if $unloadAction.error}
      <p class="text-xs text-status-error">{$unloadAction.error}</p>
    {/if}
  </Card.Content>
</Card.Root>

<UnloadConfirmDialog
  modelName={model.name}
  bind:open={showUnloadDialog}
/>
