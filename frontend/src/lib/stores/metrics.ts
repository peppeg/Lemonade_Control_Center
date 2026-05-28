import { get, writable } from 'svelte/store';
import { api } from '$lib/api/client';
import { notify } from '$lib/stores/notifications';
import type { MetricPoint, TaskRecord, TimeRange } from '$lib/types';

export const timeSeriesData = writable<MetricPoint[]>([]);
export const taskHistory = writable<TaskRecord[]>([]);
export const metricsLoading = writable(true);
export const timeRange = writable<TimeRange>(15);
export const metricsPaused = writable(false);
export const metricsWsConnected = writable(false);

let ws: WebSocket | null = null;
const MAX_POINTS = 360;

export async function loadMetrics(): Promise<void> {
  metricsLoading.set(true);
  const range = get(timeRange);
  const [historyResult, taskResult] = await Promise.allSettled([
    api.metrics.history(range),
    api.metrics.tasks(20),
  ]);

  if (historyResult.status === 'fulfilled' && historyResult.value.ok) {
    timeSeriesData.set(historyResult.value.data.points);
  }
  if (taskResult.status === 'fulfilled' && taskResult.value.ok) {
    taskHistory.set(taskResult.value.data.tasks);
  }
  metricsLoading.set(false);
}

export function connectMetricsWs(): void {
  disconnectMetricsWs();
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${window.location.host}/ws/metrics`);
  ws.onopen = () => metricsWsConnected.set(true);
  ws.onclose = () => {
    metricsWsConnected.set(false);
    ws = null;
  };
  ws.onerror = () => metricsWsConnected.set(false);
  ws.onmessage = (event) => {
    if (get(metricsPaused)) return;
    try {
      const message = JSON.parse(event.data) as { type?: string; data?: MetricPoint };
      if (message.type !== 'metric' || !message.data) return;
      const cutoff = Date.now() - get(timeRange) * 60 * 1000;
      timeSeriesData.update((points) =>
        [...points, message.data as MetricPoint]
          .filter((point) => new Date(point.t).getTime() >= cutoff)
          .slice(-MAX_POINTS),
      );
    } catch {
      // Ignore malformed websocket messages.
    }
  };
}

export function disconnectMetricsWs(): void {
  if (ws) {
    ws.close();
    ws = null;
  }
  metricsWsConnected.set(false);
}

export function setTimeRange(range: TimeRange): void {
  timeRange.set(range);
  loadMetrics();
}

export function toggleMetricsPause(): void {
  metricsPaused.update((value) => !value);
}

export async function clearMetricsHistory(): Promise<void> {
  const result = await api.metrics.clear();
  if (result.ok) {
    timeSeriesData.set([]);
    taskHistory.set([]);
    notify.info('Metrics cleared', 'Hardware and task history buffers were cleared.');
  } else {
    notify.error('Clear metrics failed', result.error);
  }
}

export function exportTasksCsv(): void {
  const anchor = document.createElement('a');
  anchor.href = api.metrics.tasksCsvUrl();
  anchor.download = 'lcc-tasks.csv';
  anchor.click();
}
