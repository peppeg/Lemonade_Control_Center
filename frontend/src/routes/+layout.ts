/**
 * Root layout load — runs once at app startup.
 * Disables SSR (SPA mode) and loads initial data.
 */
import { loadCapabilities } from '$lib/stores/capabilities';
import { startHealthPolling } from '$lib/stores/connection';
import type { LayoutLoad } from './$types';

export const ssr = false;
export const prerender = false;

export const load: LayoutLoad = async () => {
  // Load capabilities first (what features are available)
  await loadCapabilities();
  // Start polling health every 5 seconds
  startHealthPolling(5000);
  return {};
};
