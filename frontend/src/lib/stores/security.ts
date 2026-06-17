import { writable } from 'svelte/store';
import { api, setLccApiKey } from '$lib/api/client';
import type { SecurityStatus } from '$lib/types';

export const securityStatus = writable<SecurityStatus | null>(null);
export const securityLoading = writable(false);
export const securityError = writable<string | null>(null);

export async function loadSecurityStatus(): Promise<SecurityStatus | null> {
  securityLoading.set(true);
  securityError.set(null);
  const result = await api.security.status();
  securityLoading.set(false);
  if (result.ok) {
    securityStatus.set(result.data);
    return result.data;
  }
  securityError.set(result.error);
  return null;
}

export async function saveLccKey(value: string): Promise<boolean> {
  setLccApiKey(value);
  const status = await loadSecurityStatus();
  return Boolean(status?.authenticated);
}

export async function clearLccKey(): Promise<void> {
  setLccApiKey('');
  await loadSecurityStatus();
}
