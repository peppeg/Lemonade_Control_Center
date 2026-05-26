/**
 * Connection status store — polls backend health every N seconds.
 *
 * States:
 *   connected    → backend OK + Lemonade reachable
 *   degraded     → backend OK + Lemonade unreachable
 *   disconnected → backend unreachable
 *   checking     → initial state before first poll
 */
import { writable, derived } from 'svelte/store';
import type { ConnectionStatus, HealthResponse } from '$lib/types';
import { api } from '$lib/api/client';

export const connectionStatus = writable<ConnectionStatus>('checking');
export const healthData = writable<HealthResponse | null>(null);
export const lastHealthCheck = writable<Date | null>(null);

let pollInterval: ReturnType<typeof setInterval> | null = null;
let isPolling = false;

async function checkHealth(): Promise<void> {
  if (isPolling) return; // Prevent overlapping polls
  isPolling = true;

  try {
    const result = await api.health();
    lastHealthCheck.set(new Date());

    if (result.ok) {
      healthData.set(result.data);
      connectionStatus.set(
        result.data.lemonade_reachable ? 'connected' : 'degraded'
      );
    } else {
      healthData.set(null);
      connectionStatus.set('disconnected');
    }
  } catch {
    healthData.set(null);
    connectionStatus.set('disconnected');
  } finally {
    isPolling = false;
  }
}

export function startHealthPolling(intervalMs = 5000): void {
  checkHealth(); // Immediate first check
  stopHealthPolling(); // Clear any existing interval
  pollInterval = setInterval(checkHealth, intervalMs);
}

export function stopHealthPolling(): void {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

/** Derived: human-readable status label */
export const connectionLabel = derived(connectionStatus, ($s) => {
  switch ($s) {
    case 'connected': return 'Connected';
    case 'degraded': return 'Degraded';
    case 'disconnected': return 'Offline';
    case 'checking': return 'Checking…';
  }
});

/** Derived: CSS color class for the status dot */
export const connectionColorClass = derived(connectionStatus, ($s) => {
  switch ($s) {
    case 'connected': return 'text-status-ok';
    case 'degraded': return 'text-status-warn';
    case 'disconnected': return 'text-status-error';
    case 'checking': return 'text-status-off';
  }
});
