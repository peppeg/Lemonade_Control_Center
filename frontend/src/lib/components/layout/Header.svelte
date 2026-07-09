<script lang="ts">
  import { page } from '$app/stores';
  import ConnectionBadge from './ConnectionBadge.svelte';
  import NotificationBell from '$lib/components/notifications/NotificationBell.svelte';
  import { Menu, RefreshCw } from 'lucide-svelte';
  import { Button } from '$lib/components/ui/button';
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher<{ toggleMobileNav: void }>();

  // Breadcrumb from current route
  const routeLabels: Record<string, string> = {
    '/dashboard': 'Dashboard',
    '/models': 'Models',
    '/config': 'Configuration',
    '/logs': 'Logs & Stats',
    '/system': 'System',
    '/backends': 'Backends',
  };

  $: currentLabel = routeLabels[$page.url.pathname] || 'Dashboard';
</script>

<header class="flex min-h-[60px] items-center justify-between border-b border-[#34392d] bg-[#0f1111] px-5">
  <!-- Left: Mobile hamburger + breadcrumb -->
  <div class="flex items-center gap-3">
    <!-- Mobile hamburger (hidden on desktop) -->
    <Button
      variant="ghost"
      size="icon"
      class="h-8 w-8 lg:hidden"
      on:click={() => dispatch('toggleMobileNav')}
      aria-label="Open navigation"
    >
      <Menu class="h-4 w-4" />
    </Button>

    <h1 class="text-lg font-bold text-foreground">Lemonade Control Center</h1>
    <span class="hidden border-l border-[#34392d] pl-3 text-xs text-muted-foreground md:inline">
      {currentLabel}
    </span>
  </div>

  <!-- Right: Connection indicator -->
  <div class="flex items-center gap-3">
    <NotificationBell />
    <ConnectionBadge />
    <button
      class="flex h-8 w-8 items-center justify-center rounded border border-transparent text-muted-foreground hover:border-[#4a4f3a] hover:bg-[#1a1d1b] hover:text-foreground"
      type="button"
      aria-label="Refresh page"
      on:click={() => location.reload()}
    >
      <RefreshCw class="h-4 w-4" />
    </button>
  </div>
</header>
