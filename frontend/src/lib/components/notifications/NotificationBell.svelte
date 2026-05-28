<script lang="ts">
  import { Bell } from 'lucide-svelte';
  import {
    centerOpen,
    hasUnreadError,
    toggleNotificationCenter,
    unreadCount,
  } from '$lib/stores/notifications';
  import NotificationCenter from './NotificationCenter.svelte';
</script>

<div class="relative">
  <button
    class="relative flex h-8 w-8 items-center justify-center rounded border border-transparent text-muted-foreground hover:border-[#4a4f3a] hover:bg-[#1a1d1b] hover:text-foreground {$centerOpen ? 'border-[#4a4f3a] bg-[#1a1d1b] text-foreground' : ''}"
    type="button"
    aria-label="Open notifications"
    aria-expanded={$centerOpen}
    on:click={toggleNotificationCenter}
  >
    <Bell class="h-4 w-4" />
    {#if $unreadCount > 0}
      <span class="absolute -right-1 -top-1 min-w-4 rounded bg-lemon px-1 text-[10px] font-bold leading-4 text-[#111310] {$hasUnreadError ? 'bg-danger text-[#20100e]' : ''}">
        {$unreadCount > 9 ? '9+' : $unreadCount}
      </span>
    {/if}
  </button>
  <NotificationCenter />
</div>
