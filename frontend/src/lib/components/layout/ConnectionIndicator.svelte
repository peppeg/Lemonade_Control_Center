<script lang="ts">
  import { connectionStatus } from '$lib/stores/connection';
  import { Circle } from 'lucide-svelte';
  import * as Tooltip from '$lib/components/ui/tooltip';

  const labels: Record<string, string> = {
    connected: 'Connected to Lemonade',
    degraded: 'Backend OK, Lemonade unreachable',
    disconnected: 'Backend unreachable',
    checking: 'Checking connection...',
  };

  const colors: Record<string, string> = {
    connected: 'text-status-ok',
    degraded: 'text-status-warn',
    disconnected: 'text-status-error',
    checking: 'text-status-off',
  };
</script>

<Tooltip.Root>
  <Tooltip.Trigger>
    <div class="flex items-center gap-2 px-3 py-1.5 rounded-md bg-muted/50">
      <Circle
        class="h-3 w-3 fill-current {$connectionStatus in colors ? colors[$connectionStatus] : ''}"
      />
      <span class="text-xs font-medium text-muted-foreground">
        {$connectionStatus === 'connected' ? 'Connected' :
         $connectionStatus === 'degraded' ? 'Degraded' :
         $connectionStatus === 'disconnected' ? 'Offline' :
         'Checking...'}
      </span>
    </div>
  </Tooltip.Trigger>
  <Tooltip.Content>
    <p>{labels[$connectionStatus]}</p>
  </Tooltip.Content>
</Tooltip.Root>
