<script lang="ts">
  import { page } from '$app/stores';
  import ConnectionBadge from './ConnectionBadge.svelte';
  import { Menu } from 'lucide-svelte';
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
  };

  const currentLabel = $derived(routeLabels[$page.url.pathname] || 'Dashboard');
</script>

<header class="flex items-center justify-between px-4 py-2.5 border-b border-border bg-card/80 backdrop-blur-sm min-h-[52px]">
  <!-- Left: Mobile hamburger + breadcrumb -->
  <div class="flex items-center gap-3">
    <!-- Mobile hamburger (hidden on desktop) -->
    <Button
      variant="ghost"
      size="icon"
      class="h-8 w-8 lg:hidden"
      on:click={() => dispatch('toggleMobileNav')}
    >
      <Menu class="h-4 w-4" />
    </Button>

    <!-- Breadcrumb -->
    <nav class="flex items-center gap-1.5 text-sm">
      <span class="text-muted-foreground hidden sm:inline">LCC</span>
      <span class="text-muted-foreground/50 hidden sm:inline">/</span>
      <span class="font-medium text-foreground">{currentLabel}</span>
    </nav>
  </div>

  <!-- Right: Connection indicator -->
  <ConnectionBadge />
</header>
