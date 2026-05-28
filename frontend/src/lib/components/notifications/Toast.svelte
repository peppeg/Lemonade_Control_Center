<script lang="ts">
  import { CheckCircle2, CircleAlert, CircleX, Info, X } from 'lucide-svelte';
  import type { ToastData } from '$lib/types';
  import { dismissToast } from '$lib/stores/notifications';

  export let toast: ToastData;

  $: borderClass = {
    success: 'border-[#135b2d]',
    error: 'border-[#70302d]',
    warning: 'border-[#5a4720]',
    info: 'border-[#444936]',
  }[toast.level];
  $: iconClass = {
    success: 'text-status-ok',
    error: 'text-status-error',
    warning: 'text-status-warn',
    info: 'text-muted-foreground',
  }[toast.level];
  $: Icon = {
    success: CheckCircle2,
    error: CircleX,
    warning: CircleAlert,
    info: Info,
  }[toast.level];
</script>

<div class="w-full max-w-sm rounded border bg-[#171a19] p-4 shadow-2xl shadow-black/35 transition-all duration-150 {borderClass} {toast.exiting ? 'translate-x-4 opacity-0' : 'translate-x-0 opacity-100'}">
  <div class="flex items-start gap-3">
    <Icon class="mt-0.5 h-5 w-5 shrink-0 {iconClass}" />
    <div class="min-w-0 flex-1">
      <p class="text-sm font-semibold text-foreground">{toast.title}</p>
      <p class="mt-1 break-words text-xs leading-5 text-muted-foreground">{toast.message}</p>
    </div>
    <button
      class="shrink-0 rounded p-1 text-muted-foreground hover:bg-[#252827] hover:text-foreground"
      type="button"
      aria-label="Dismiss notification"
      on:click={() => dismissToast(toast.id)}
    >
      <X class="h-4 w-4" />
    </button>
  </div>
</div>
