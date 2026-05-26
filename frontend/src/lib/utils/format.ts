/**
 * Formatting helpers for display values.
 */

/** Format bytes to human-readable GB */
export function formatGB(gb: number): string {
  if (gb >= 100) return `${Math.round(gb)} GB`;
  if (gb >= 10) return `${gb.toFixed(1)} GB`;
  return `${gb.toFixed(2)} GB`;
}

/** Format percentage */
export function formatPercent(pct: number): string {
  return `${Math.round(pct)}%`;
}

/** Format tokens/second */
export function formatTPS(tps: number): string {
  if (tps >= 100) return `${Math.round(tps)} t/s`;
  return `${tps.toFixed(1)} t/s`;
}

/** Format seconds to human-readable duration */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) {
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    return `${m}m ${s}s`;
  }
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

/** Format ISO date to short locale string */
export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric'
    });
  } catch {
    return iso;
  }
}

/** Format ISO date to time string */
export function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  } catch {
    return iso;
  }
}

/** Format large numbers with commas */
export function formatNumber(n: number): string {
  return n.toLocaleString();
}
