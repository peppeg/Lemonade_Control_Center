<script lang="ts">
  import { page } from '$app/stores';
  import { capabilities, hasDangerZone } from '$lib/stores/capabilities';
  import { sidebarCollapsed, toggleSidebar } from '$lib/stores/sidebar';
  import { connectionStatus } from '$lib/stores/connection';
  import {
    LayoutDashboard, Cpu, Settings, ScrollText, Monitor, Activity, LineChart, FlaskConical,
    PanelLeft, Server
  } from 'lucide-svelte';

  interface NavItem {
    href: string;
    label: string;
    icon: typeof LayoutDashboard;
    milestone: string;
    requiresBench?: boolean;
  }

  const navItems: NavItem[] = [
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, milestone: 'M4' },
    { href: '/models',    label: 'Models',    icon: Cpu,             milestone: 'M5' },
    { href: '/config',    label: 'Configuration', icon: Settings,    milestone: 'M6' },
    { href: '/logs',      label: 'Logs & Stats',  icon: ScrollText,  milestone: 'M7' },
    { href: '/system',    label: 'System',    icon: Monitor,         milestone: 'M8' },
    { href: '/diagnostics', label: 'Diagnostics', icon: Activity,     milestone: 'M11' },
    { href: '/hardware', label: 'Hardware', icon: LineChart,          milestone: 'M12' },
    { href: '/bench', label: 'Bench Lab', icon: FlaskConical,          milestone: 'M13', requiresBench: true },
  ];

  $: currentPath = $page.url.pathname;

  function isActive(href: string, pathname: string): boolean {
    return pathname === href || pathname.startsWith(href + '/');
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
  class="group relative flex h-full flex-col border-r border-[#34392d] bg-[#171a19] transition-all duration-200 ease-in-out
         {$sidebarCollapsed ? 'w-[72px]' : 'w-[200px]'}"
>
  <!-- Logo + Toggle -->
  {#if !$sidebarCollapsed}
    <div class="flex min-h-[80px] items-center border-b border-[#34392d] px-4 py-4">
      <a href="/dashboard" class="group/logo flex min-w-0 flex-col">
        <span class="truncate text-lg font-black leading-tight text-lemon">Lemonade</span>
        <span class="truncate text-[11px] leading-tight text-[#e0e3d2]">
          Control Center
        </span>
      </a>
    </div>
  {:else}
    <div class="relative flex min-h-[80px] items-center justify-center border-b border-[#34392d] px-0 py-4">
      <a href="/dashboard" class="shrink-0">
        <div class="flex h-8 w-8 items-center justify-center rounded border border-[#51583c] text-sm font-black text-lemon">
          L
        </div>
      </a>
    </div>
  {/if}

  <button
    type="button"
    class="absolute -right-3 top-6 z-20 inline-flex h-6 w-6 items-center justify-center rounded border border-[#444936] bg-[#171a19] text-muted-foreground shadow-sm transition-colors hover:border-[#6b7349] hover:bg-[#242822] hover:text-foreground"
    on:click={toggleSidebar}
    aria-label={$sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
    title={$sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
  >
    <PanelLeft class="h-3.5 w-3.5" />
  </button>

  <!-- Navigation -->
  <nav class="flex flex-1 flex-col gap-0 px-0 py-4">
    {#each navItems as item}
      {#if !item.requiresBench || $capabilities.bench_lab}
        <a
          href={item.href}
          title={$sidebarCollapsed ? item.label : ''}
          class="relative flex items-center gap-3 text-sm transition-colors duration-150
                 {$sidebarCollapsed ? 'justify-center px-2 py-3' : 'px-5 py-3'}
                 {isActive(item.href, currentPath)
                   ? 'bg-[#4a4d49] text-lemon font-semibold'
                   : 'text-[#d8dccb] hover:text-foreground hover:bg-[#222522]'}"
        >
          {#if isActive(item.href, currentPath)}
            <span class="absolute left-0 top-0 h-full w-1 bg-lemon"></span>
          {/if}
          <svelte:component
            this={item.icon}
            class="h-4 w-4 shrink-0 transition-colors
                   {isActive(item.href, currentPath) ? 'text-lemon' : ''}"
          />
          {#if !$sidebarCollapsed}
            <span class="truncate">{item.label}</span>
          {/if}
        </a>
      {/if}
    {/each}
  </nav>

  <!-- Danger Zone -->
  {#if $hasDangerZone}
    <div class="border-t border-[#34392d] px-2 py-3">
      <a
        href="/system"
        class="inline-flex min-h-10 w-full items-center gap-3 rounded px-3 py-2 text-sm text-danger transition-colors hover:bg-[#321715] hover:text-danger
               {$connectionStatus === 'disconnected' ? 'pointer-events-none opacity-45' : ''}
               {$sidebarCollapsed ? 'justify-center px-2' : 'justify-start'}"
        aria-disabled={$connectionStatus === 'disconnected'}
        title="Open System emergency recovery"
      >
        <Server class="h-4 w-4 shrink-0" />
        {#if !$sidebarCollapsed}
          <span class="text-sm truncate">Stop & Unload</span>
        {/if}
      </a>
    </div>
  {/if}
</aside>
