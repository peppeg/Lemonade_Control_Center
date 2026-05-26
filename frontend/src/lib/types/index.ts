/**
 * Shared TypeScript types for the LCC frontend.
 * These mirror the Pydantic schemas from the backend.
 */

// ── Health & Connection ──

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  app_name: string;
  app_version: string;
  lemonade_url: string;
  lemonade_reachable: boolean;
  lemonade_version: string | null;
}

export type ConnectionStatus = 'connected' | 'degraded' | 'disconnected' | 'checking';

// ── Capabilities ──

export interface Capabilities {
  health: boolean;
  stats: boolean;
  system_info: boolean;
  load: boolean;
  unload: boolean;
  delete: boolean;
  delete_enabled: boolean;
  pull: boolean;
  internal_config: boolean;
  internal_set: boolean;
  ollama_tags: boolean;
  ollama_ps: boolean;
  ollama_show: boolean;
  ollama_version: boolean;
  openai_models: boolean;
  websocket: boolean;
  websocket_port: number | null;
  cmd_systemctl: boolean;
  cmd_journalctl: boolean;
  cmd_sensors: boolean;
  restart_enabled: boolean;
  lemonade_version: string | null;
  probe_timestamp: string | null;
}

// ── Navigation ──

export interface NavItem {
  href: string;
  label: string;
  icon: string;
  milestone: string;
  requiresCapability?: keyof Capabilities;
}

// ── Lemonade Health (from /api/lemonade/health) ──

export interface LemonadeHealth {
  raw: Record<string, unknown>;
  version: string | null;
  status: string;
  loaded_models: Record<string, unknown>[];
  websocket_port: number | null;
}

// ── Hardware ──

export interface HardwareInfo {
  ram_total_gb: number;
  ram_used_gb: number;
  ram_available_gb: number;
  ram_percent: number;
  swap_total_gb: number;
  swap_used_gb: number;
  cpu_percent: number;
  cpu_count: number;
  disk_total_gb: number | null;
  disk_used_gb: number | null;
  disk_free_gb: number | null;
  disk_percent: number | null;
  disk_path: string | null;
}
