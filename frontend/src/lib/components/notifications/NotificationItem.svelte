<script lang="ts">
  import { CheckCircle2, CircleAlert, CircleX, Info } from 'lucide-svelte';
  import type { Notification } from '$lib/types';

  export let notification: Notification;

  $: ageLabel = formatAge(notification.timestamp);
  $: levelClass = {
    success: 'text-status-ok',
    error: 'text-status-error',
    warning: 'text-status-warn',
    info: 'text-muted-foreground',
  }[notification.level];
  $: Icon = {
    success: CheckCircle2,
    error: CircleX,
    warning: CircleAlert,
    info: Info,
  }[notification.level];

  function formatAge(timestamp: Date): string {
    const seconds = Math.max(0, Math.round((Date.now() - timestamp.getTime()) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.round(minutes / 60);
    return `${hours}h ago`;
  }
</script>

<div class="flex gap-3 border-b border-[#30342b] px-4 py-3 last:border-b-0 {notification.read ? 'opacity-70' : ''}">
  <Icon class="mt-0.5 h-4 w-4 shrink-0 {levelClass}" />
  <div class="min-w-0 flex-1">
    <div class="flex items-start justify-between gap-3">
      <p class="truncate text-sm font-semibold text-foreground">{notification.title}</p>
      <span class="shrink-0 text-[11px] text-muted-foreground">{ageLabel}</span>
    </div>
    <p class="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{notification.message}</p>
  </div>
</div>
