/**
 * Sidebar state store — persisted in localStorage.
 */
import { writable } from 'svelte/store';
import { browser } from '$app/environment';

const STORAGE_KEY = 'lcc-sidebar-collapsed';

function getInitial(): boolean {
  if (!browser) return false;
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === 'true';
}

export const sidebarCollapsed = writable<boolean>(getInitial());

// Persist to localStorage on change
if (browser) {
  sidebarCollapsed.subscribe((val) => {
    localStorage.setItem(STORAGE_KEY, String(val));
  });
}

export function toggleSidebar(): void {
  sidebarCollapsed.update((v) => !v);
}
