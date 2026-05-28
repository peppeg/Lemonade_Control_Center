import { derived, writable } from 'svelte/store';
import { api } from '$lib/api/client';
import { notify } from '$lib/stores/notifications';
import type { AlertHistoryEntry, DiagnosticReport } from '$lib/types';

export const diagnosticReport = writable<DiagnosticReport | null>(null);
export const diagnosticHistory = writable<AlertHistoryEntry[]>([]);
export const diagnosticsLoading = writable(false);
export const diagnosticsError = writable<string | null>(null);
export const diagnosticsLastRun = writable<Date | null>(null);

export const activeAlertCount = derived(
  diagnosticReport,
  ($report) => $report?.alerts.length ?? 0,
);

export const hasSeriousAlert = derived(
  diagnosticReport,
  ($report) => $report?.alerts.some((alert) => ['critical', 'high'].includes(alert.severity)) ?? false,
);

let pollInterval: ReturnType<typeof setInterval> | null = null;

export async function runDiagnostics(showToast = false): Promise<void> {
  diagnosticsLoading.set(true);
  diagnosticsError.set(null);

  const result = await api.diagnostics.run();
  if (result.ok) {
    diagnosticReport.set(result.data);
    diagnosticsLastRun.set(new Date());
    if (showToast) {
      notify.info('Diagnostics complete', `${result.data.alerts.length} active alerts`, { href: '/diagnostics' });
    }
  } else {
    diagnosticsError.set(result.error);
    if (showToast) notify.error('Diagnostics failed', result.error, { href: '/diagnostics' });
  }

  diagnosticsLoading.set(false);
}

export async function loadDiagnosticHistory(): Promise<void> {
  const result = await api.diagnostics.history();
  if (result.ok) {
    diagnosticHistory.set(result.data.entries);
  }
}

export async function dismissDiagnostic(ruleId: string): Promise<void> {
  const result = await api.diagnostics.dismiss(ruleId);
  if (result.ok) {
    notify.info('Alert dismissed', ruleId, { toastDuration: 2500 });
    await runDiagnostics(false);
    await loadDiagnosticHistory();
  } else {
    notify.error('Dismiss failed', result.error);
  }
}

export function startDiagnosticsPolling(intervalMs = 30_000): void {
  runDiagnostics(false);
  stopDiagnosticsPolling();
  pollInterval = setInterval(() => runDiagnostics(false), intervalMs);
}

export function stopDiagnosticsPolling(): void {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}
