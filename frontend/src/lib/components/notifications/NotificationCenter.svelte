<script lang="ts">
  import {
    centerOpen,
    clearNotifications,
    markAllNotificationsRead,
    markNotificationRead,
    notifications,
  } from '$lib/stores/notifications';
  import NotificationItem from './NotificationItem.svelte';

  function handleItemClick(id: string): void {
    markNotificationRead(id);
  }
</script>

{#if $centerOpen}
  <div class="absolute right-0 top-11 z-40 w-[min(360px,calc(100vw-32px))] overflow-hidden rounded border border-[#444936] bg-[#171a19] shadow-2xl shadow-black/40">
    <div class="flex items-center justify-between border-b border-[#30342b] px-4 py-3">
      <div>
        <p class="text-sm font-bold text-foreground">Notifications</p>
        <p class="text-xs text-muted-foreground">Recent control center events</p>
      </div>
      <button class="text-xs text-lemon hover:text-lemon-light" type="button" on:click={markAllNotificationsRead}>
        Mark read
      </button>
    </div>

    <div class="max-h-[420px] overflow-y-auto">
      {#if $notifications.length === 0}
        <div class="px-4 py-8 text-center text-sm text-muted-foreground">No notifications yet.</div>
      {:else}
        {#each $notifications as notification (notification.id)}
          {#if notification.href}
            <a href={notification.href} on:click={() => handleItemClick(notification.id)}>
              <NotificationItem {notification} />
            </a>
          {:else}
            <button class="block w-full text-left" type="button" on:click={() => handleItemClick(notification.id)}>
              <NotificationItem {notification} />
            </button>
          {/if}
        {/each}
      {/if}
    </div>

    {#if $notifications.length > 0}
      <div class="border-t border-[#30342b] p-3">
        <button class="ops-button w-full" type="button" on:click={clearNotifications}>Clear All</button>
      </div>
    {/if}
  </div>
{/if}
