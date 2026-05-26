<script>
  import { page } from '$app/stores';
  import { Button } from '$lib/components/ui/button';
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
  <Button href="/dashboard">Back to Dashboard</Button>
</div>
