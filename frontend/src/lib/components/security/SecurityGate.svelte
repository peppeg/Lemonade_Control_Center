<script lang="ts">
  import { onMount } from 'svelte';
  import { ShieldAlert, Loader2 } from 'lucide-svelte';
  import {
    clearLccKey,
    loadSecurityStatus,
    saveLccKey,
    securityError,
    securityLoading,
    securityStatus,
  } from '$lib/stores/security';

  let keyInput = '';
  let saving = false;
  let localError: string | null = null;

  onMount(() => {
    loadSecurityStatus();
  });

  $: mustAuthenticate = Boolean($securityStatus?.auth_required && !$securityStatus.authenticated);
  $: blocked = Boolean($securityStatus?.blocked);

  async function submitKey() {
    localError = null;
    if (!keyInput.trim()) {
      localError = 'Enter the LCC API key.';
      return;
    }
    saving = true;
    const ok = await saveLccKey(keyInput);
    saving = false;
    if (!ok) {
      localError = 'The key was rejected by Lemonade Control Center.';
    } else {
      keyInput = '';
    }
  }
</script>

{#if mustAuthenticate || blocked}
  <div class="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
    <section class="w-full max-w-md border border-[#4a4d39] bg-[#171918] shadow-2xl">
      <div class="border-b border-[#30342b] px-5 py-4">
        <div class="flex items-center gap-3">
          <ShieldAlert class="h-5 w-5 text-lemon" />
          <h2 class="ops-title">LCC API Key Required</h2>
        </div>
        <p class="ops-subtitle mt-2">
          {blocked
            ? 'This request is coming from LAN/remote, but the backend has no LCC_API_KEY configured.'
            : 'This browser is not on localhost. Enter the LCC API key to continue.'}
        </p>
      </div>

      <div class="space-y-4 p-5">
        {#if blocked}
          <div class="ops-banner ops-banner-danger">
            <p class="text-sm">
              Set <code class="ops-mono">LCC_API_KEY</code> in <code class="ops-mono">backend/.env</code> or bind the app to
              <code class="ops-mono">127.0.0.1</code>.
            </p>
          </div>
        {:else}
          <label class="block space-y-2">
            <span class="ops-label">LCC API key</span>
            <input
              class="ops-input"
              type="password"
              bind:value={keyInput}
              autocomplete="current-password"
              on:keydown={(event) => event.key === 'Enter' && submitKey()}
            />
          </label>
          {#if localError || $securityError}
            <div class="ops-banner ops-banner-danger">
              <p class="text-sm">{localError || $securityError}</p>
            </div>
          {/if}
          <div class="flex justify-end gap-2">
            <button class="ops-button" type="button" on:click={clearLccKey}>Clear</button>
            <button class="ops-button ops-button-primary" type="button" on:click={submitKey} disabled={saving || $securityLoading}>
              {#if saving || $securityLoading}
                <Loader2 class="h-4 w-4 animate-spin" />
                Checking
              {:else}
                Continue
              {/if}
            </button>
          </div>
        {/if}
      </div>
    </section>
  </div>
{/if}
