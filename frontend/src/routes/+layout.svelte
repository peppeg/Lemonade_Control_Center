<!--
  Root layout — Assembles the entire app shell.

  Desktop: sidebar + header + content + status bar
  Mobile: hidden sidebar + sheet nav + header + content + status bar
-->
<script>
  import '../app.css';
  import Sidebar from '$lib/components/layout/Sidebar.svelte';
  import Header from '$lib/components/layout/Header.svelte';
  import StatusBar from '$lib/components/layout/StatusBar.svelte';
  import MobileNav from '$lib/components/layout/MobileNav.svelte';
  import { onMount } from 'svelte';
  import { loadCapabilities } from '$lib/stores/capabilities';
  import { startHealthPolling, stopHealthPolling } from '$lib/stores/connection';

  let mobileNavOpen = false;

  onMount(() => {
    loadCapabilities();
    startHealthPolling(5000);

    return () => {
      stopHealthPolling();
    };
  });
</script>

<div class="flex h-screen overflow-hidden bg-background">
  <!-- Desktop Sidebar (hidden on mobile) -->
  <div class="hidden lg:block">
    <Sidebar />
  </div>

  <!-- Mobile Nav Sheet -->
  <MobileNav bind:open={mobileNavOpen} />

  <!-- Main content area -->
  <div class="flex flex-col flex-1 overflow-hidden min-w-0">
    <!-- Header -->
    <Header on:toggleMobileNav={() => mobileNavOpen = true} />

    <!-- Page content with smooth transition -->
    <main class="flex-1 overflow-y-auto">
      <div class="p-4 md:p-6 max-w-7xl mx-auto w-full">
        <slot />
      </div>
    </main>

    <!-- Status bar -->
    <StatusBar />
  </div>
</div>
