<script lang="ts">
  import { page } from '$app/stores';
  import { capabilities, hasDangerZone } from '$lib/stores/capabilities';
  import { sidebarCollapsed, toggleSidebar } from '$lib/stores/sidebar';
  import { connectionStatus } from '$lib/stores/connection';
  import {
    LayoutDashboard, Cpu, Settings, ScrollText, Monitor,
    OctagonX, PanelLeftClose, PanelLeftOpen
  } from 'lucide-svelte';
  import { Button } from '$lib/components/ui/button';
  import { Separator } from '$lib/components/ui/separator';

  interface NavItem {
    href: string;
    label: string;
    icon: typeof LayoutDashboard;
    milestone: string;
  }

  const navItems: NavItem[] = [
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, milestone: 'M4' },
    { href: '/models',    label: 'Models',    icon: Cpu,             milestone: 'M5' },
    { href: '/config',    label: 'Config',    icon: Settings,        milestone: 'M6' },
    { href: '/logs',      label: 'Logs',      icon: ScrollText,      milestone: 'M7' },
    { href: '/system',    label: 'System',    icon: Monitor,         milestone: 'M8' },
  ];

  function isActive(href: string): boolean {
    return $page.url.pathname === href || $page.url.pathname.startsWith(href + '/');
  }

  // Keyboard shortcut: Ctrl+B
  function handleKeydown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault();
      toggleSidebar();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<aside
  class="group flex flex-col h-full border-r border-border bg-card transition-all duration-300 ease-in-out
         {$sidebarCollapsed ? 'w-16' : 'w-56'}"
>
  <!-- Logo + Toggle -->
  <div class="flex items-center justify-between px-3 py-4 border-b border-border min-h-[60px]">
    {#if !$sidebarCollapsed}
      <a href="/dashboard" class="flex items-center gap-2.5 group/logo">
        <span class="text-xl transition-transform group-hover/logo:scale-110">🍋</span>
        <div class="flex flex-col overflow-hidden">
          <span class="text-sm font-semibold text-foreground leading-tight truncate">Lemonade</span>
          <span class="text-[10px] text-muted-foreground leading-tight truncate">Control Center</span>
        </div>
      </a>
    {:else}
      <a href="/dashboard" class="mx-auto">
        <span class="text-xl hover:scale-110 transition-transform inline-block">🍋</span>
      </a>
    {/if}

    <Button
      variant="ghost"
      size="icon"
      class="h-7 w-7 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity
             {$sidebarCollapsed ? '!opacity-100 mx-auto' : ''}"
      on:click={toggleSidebar}
    >
      {#if $sidebarCollapsed}
        <PanelLeftOpen class="h-4 w-4" />
      {:else}
        <PanelLeftClose class="h-4 w-4" />
      {/if}
    </Button>
  </div>

  <!-- Navigation -->
  <nav class="flex-1 flex flex-col gap-0.5 px-2 py-3 overflow-y-auto">
    {#each navItems as item}
      <a
        href={item.href}
        title={$sidebarCollapsed ? item.label : ''}
        class="flex items-center gap-3 rounded-md text-sm transition-all duration-150
               {$sidebarCollapsed ? 'justify-center px-2 py-2.5' : 'px-3 py-2'}
               {isActive(item.href)
                 ? 'bg-lemon/10 text-lemon font-medium shadow-sm shadow-lemon/5'
                 : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'}"
      >
        <svelte:component
          this={item.icon}
          class="h-4 w-4 shrink-0 transition-colors
                 {isActive(item.href) ? 'text-lemon' : ''}"
        />
        {#if !$sidebarCollapsed}
          <span class="truncate">{item.label}</span>
        {/if}
      </a>
    {/each}
  </nav>

  <!-- Danger Zone -->
  {#if $hasDangerZone}
    <div class="px-2 pb-3">
      <Separator class="mb-3" />
      <Button
        variant="ghost"
        class="w-full gap-3 text-destructive hover:text-destructive hover:bg-destructive/10
               {$sidebarCollapsed ? 'justify-center px-2' : 'justify-start'}"
        disabled={$connectionStatus === 'disconnected'}
        title="Unload the current model from memory"
      >
        <OctagonX class="h-4 w-4 shrink-0" />
        {#if !$sidebarCollapsed}
          <span class="text-sm truncate">Stop & Unload</span>
        {/if}
      </Button>
    </div>
  {/if}
</aside>
