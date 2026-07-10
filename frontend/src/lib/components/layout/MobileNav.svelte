<!--
  MobileNav — Sheet overlay for sidebar on small screens.
-->
<script lang="ts">
  import { page } from '$app/stores';
  import Sheet from '$lib/components/ui/sheet';
  import {
    FileClock, LayoutDashboard, Cpu, Settings, ScrollText, Monitor, PackageCheck
  } from 'lucide-svelte';

  export let open = false;

  const navItems = [
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/models',    label: 'Models',    icon: Cpu },
    { href: '/config',    label: 'Configuration', icon: Settings },
    { href: '/logs',      label: 'Logs & Stats',  icon: ScrollText },
    { href: '/system',    label: 'System',    icon: Monitor },
    { href: '/backends',  label: 'Backends',  icon: PackageCheck },
    { href: '/evidence', label: 'Run Evidence', icon: FileClock },
  ];

  $: currentPath = $page.url.pathname;

  function isActive(href: string, pathname: string): boolean {
    return pathname === href || pathname.startsWith(href + '/');
  }

  function navigate() {
    open = false;
  }
</script>

<Sheet bind:open side="left">
  <div class="border-b border-[#34392d] px-4 py-4">
    <div class="flex flex-col">
      <span class="text-lg font-black leading-tight text-lemon">Lemonade</span>
      <span class="text-xs text-muted-foreground">Control Center</span>
    </div>
  </div>

  <nav class="flex flex-col gap-0.5 px-2 py-3">
    {#each navItems as item}
      <a
        href={item.href}
        class="flex items-center gap-3 rounded px-3 py-2.5 text-sm transition-colors
               {isActive(item.href, currentPath)
                 ? 'bg-[#4a4d49] text-lemon font-semibold'
                 : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'}"
        on:click={navigate}
      >
        <svelte:component this={item.icon} class="h-4 w-4" />
        <span>{item.label}</span>
      </a>
    {/each}
  </nav>
</Sheet>
