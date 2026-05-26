<script>
  import { page } from '$app/stores';
  import { AlertTriangle } from 'lucide-svelte';
</script>

<div class="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
  <div class="rounded-full bg-destructive/10 p-4 mb-4">
    <AlertTriangle class="h-8 w-8 text-destructive" />
  </div>
  <h1 class="text-2xl font-semibold mb-2">
    {$page.status}
  </h1>
  <p class="text-muted-foreground mb-6 max-w-md">
    {$page.error?.message ?? 'Something went wrong.'}
  </p>
  <a href="/dashboard" class="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2">
    Back to Dashboard
  </a>
</div>
