/**
 * Capabilities store — loaded once at app startup, refreshable.
 *
 * The UI uses this to enable/disable features:
 *   {#if $capabilities.delete_enabled}
 *     <DeleteButton />
 *   {/if}
 */
import { writable, derived } from 'svelte/store';
import type { Capabilities } from '$lib/types';
import { api } from '$lib/api/client';

const DEFAULTS: Capabilities = {
  health: false, stats: false, system_info: false,
  load: false, unload: false, delete: false, delete_enabled: false, pull: false,
  internal_config: false, internal_set: false,
  ollama_tags: false, ollama_ps: false, ollama_show: false, ollama_version: false,
  openai_models: false,
  websocket: false, websocket_port: null,
  cmd_systemctl: false, cmd_journalctl: false, cmd_sensors: false,
  restart_enabled: false,
  bench_lab: false,
  lemonade_version: null, probe_timestamp: null,
};

export const capabilities = writable<Capabilities>(DEFAULTS);
export const capabilitiesLoaded = writable(false);
export const capabilitiesError = writable<string | null>(null);

export async function loadCapabilities(): Promise<void> {
  const result = await api.capabilities();
  if (result.ok) {
    capabilities.set(result.data);
    capabilitiesError.set(null);
  } else {
    console.warn('Failed to load capabilities:', result.error);
    capabilitiesError.set(result.error);
    // Keep defaults — everything disabled, app still shows UI
  }
  capabilitiesLoaded.set(true);
}

/** Derived: are any "dangerous" actions enabled? */
export const hasDangerZone = derived(capabilities, ($c) =>
  $c.unload || $c.restart_enabled
);
