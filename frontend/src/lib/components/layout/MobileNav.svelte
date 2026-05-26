<!--
  MobileNav — Sheet overlay for sidebar on small screens.
-->
<script lang="ts">
  import { page } from '$app/stores';
  import Sheet from '$lib/components/ui/sheet';
  import {
    LayoutDashboard, Cpu, Settings, ScrollText, Monitor, OctagonX
  } from 'lucide-svelte';

  export let open = false;

  const navItems = [
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/models',    label: 'Models',    icon: Cpu },
    { href: '/config',    label: 'Config',    icon: Settings },
    { href: '/logs',      label: 'Logs',      icon: ScrollText },
    { href: '/system',    label: 'System',    icon: Monitor },
  ];

  function isActive(href: string): boolean {
    return $page.url.pathname.startsWith(href);
  }

  function navigate() {
    open = false;
  }
</script>

<Sheet bind:open side="left">
  <div class="px-4 py-4 border-b border-border">
    <div class="flex items-center gap-2">
      <span class="text-xl">🍋</span>
      <span class="text-sm font-semibold">Lemonade Control Center</span>
    </div>
  </div>

  <nav class="flex flex-col gap-0.5 px-2 py-3">
    {#each navItems as item}
      <a
        href={item.href}
        class="flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors
               {isActive(item.href)
                 ? 'bg-lemon/10 text-lemon font-medium'
                 : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'}"
        on:click={navigate}
      >
        <svelte:component this={item.icon} class="h-4 w-4" />
        <span>{item.label}</span>
      </a>
    {/each}
  </nav>
</Sheet>
