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
  bench_lab: boolean;
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

export interface LemonadeSavedOptions {
  available: boolean;
  path: string;
  options: Record<string, Record<string, unknown>>;
  model_name: string | null;
  selected_key: string | null;
  selected_options: Record<string, unknown> | null;
  error: string | null;
}

// ── Setup & Settings (M14) ──

export type RuntimeType = 'lemonade' | 'ollama' | 'llamacpp' | 'custom';
export type AccessMode = 'local' | 'ssh_tunnel' | 'tailscale' | 'remote';
export type RuntimeTestStatus = 'untested' | 'ok' | 'error';
export type OsType = 'linux_systemd' | 'windows' | 'macos' | 'docker' | 'other';
export type Theme = 'dark' | 'light' | 'system';
export type SidebarPosition = 'left' | 'right';
export type DiscoveryStatus = 'ok' | 'warning' | 'error' | 'skip';

export interface RuntimeConfigPublic {
  id: string;
  type: RuntimeType;
  name: string;
  url: string;
  admin_key_configured: boolean;
  is_active: boolean;
  access_mode: AccessMode;
  capabilities_count: number;
  last_tested: string | null;
  test_status: RuntimeTestStatus;
}

export interface RuntimeConfigRequest {
  id: string;
  type: RuntimeType;
  name: string;
  url: string;
  admin_key?: string | null;
  is_active?: boolean;
  access_mode?: AccessMode;
  capabilities_count?: number;
  last_tested?: string | null;
  test_status?: RuntimeTestStatus;
}

export interface SystemConfig {
  os_type: OsType;
  service_name: string;
  enable_system_commands: boolean;
  enable_restart: boolean;
  enable_delete: boolean;
}

export interface AppearanceConfig {
  theme: Theme;
  accent_color: string;
  polling_interval_s: number;
  sidebar_position: SidebarPosition;
}

export interface LccConfigPublic {
  setup_complete: boolean;
  setup_date: string | null;
  version: string;
  runtimes: RuntimeConfigPublic[];
  active_runtime_id: string | null;
  system: SystemConfig;
  appearance: AppearanceConfig;
}

export interface SetupStatusResponse {
  setup_complete: boolean;
  active_runtime_id: string | null;
}

export interface SecurityStatus {
  auth_required: boolean;
  authenticated: boolean;
  key_configured: boolean;
  lan_client: boolean;
  client_host: string | null;
  blocked: boolean;
  mode: 'localhost' | 'lan';
}

export interface SetupConnectionRequest {
  type: Exclude<RuntimeType, 'custom'>;
  url: string;
  admin_key?: string | null;
}

export interface ConnectionTestResult {
  success: boolean;
  version: string | null;
  models_count: number;
  error: string | null;
  latency_ms: number;
}

export interface DiscoveryCheck {
  name: string;
  endpoint: string;
  status: DiscoveryStatus;
  detail: string;
}

export interface DiscoveryResult {
  checks: DiscoveryCheck[];
  total: number;
  passed: number;
  capabilities_json: Record<string, boolean>;
}

export interface LemonadeDiscoveryCandidate {
  name: string;
  url: string;
  source: 'udp_beacon' | 'http_fallback' | 'manual';
  reachable: boolean;
  hostname: string | null;
  version: string | null;
  status: string | null;
  model_loaded: string | null;
  latency_ms: number | null;
  detail: string | null;
}

export interface LemonadeDiscoveryResponse {
  candidates: LemonadeDiscoveryCandidate[];
  total: number;
  udp_listen_ms: number;
}

export interface ConnectionDoctorCheck {
  name: string;
  status: DiscoveryStatus;
  detail: string;
}

export interface ConnectionDoctorResponse {
  runtime_id: string;
  target_url: string;
  normalized_url: string;
  reachable: boolean;
  version: string | null;
  status: string | null;
  loaded_model: string | null;
  local_target: boolean;
  api_available: boolean;
  host_telemetry_available: boolean;
  process_evidence: 'found' | 'not_running' | 'unavailable';
  admin_config_available: boolean;
  telemetry_enabled: boolean | null;
  checks: ConnectionDoctorCheck[];
  warnings: string[];
  recommended_next_action: string;
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
  gpu_available: boolean;
  gpu_name: string | null;
  gpu_load_percent: number | null;
  gpu_temp_c: number | null;
  disk_total_gb: number | null;
  disk_used_gb: number | null;
  disk_free_gb: number | null;
  disk_percent: number | null;
  disk_path: string | null;
}

// ═══════════════════════════════════════════════
// Dashboard Types (M4)
// ═══════════════════════════════════════════════

/** Aggregated dashboard data from multiple endpoints. */
export interface DashboardData {
  serverStatus: ServerStatus | null;
  loadedModel: LoadedModelInfo | null;
  lastTask: LastTaskInfo | null;
  hardware: HardwareInfo | null;
  runtimeConfigAvailable: boolean | null;
  alerts: SmartAlert[];
  timestamp: Date;
}

export interface ServerStatus {
  status: 'running' | 'stopped' | 'error' | 'unknown';
  version: string | null;
  apiPort: number;
  websocketPort: number | null;
  globalTimeout: number | null;
  maxLoadedModels: number | null;
  defaultBackend: string | null;
}

export interface LoadedModelInfo {
  name: string;
  backend: string | null;
  ctxSize: number | null;
  ngl: number | null;
  mmap: boolean | null;
  jinja: boolean;
  specType: string | null;
  specDraftMax: number | null;
  reasoningFormat: string | null;
  mmproj: string | null;
  pid: number | null;
  rssGb: number | null;
  cpuPercent: number | null;
  uptime: string | null;
  uptimeSeconds: number | null;
}

export interface LastTaskInfo {
  available: boolean;
  inputTokens: number | null;
  outputTokens: number | null;
  promptEvalTps: number | null;
  generationTps: number | null;
  ttftSeconds: number | null;
  totalDurationSeconds: number | null;
  finishReason: string | null;
  finishConfidence: 'confirmed' | 'inferred' | 'unknown';
  finishEvidence: string | null;
}

/** Smart alert generated by the dashboard alert engine. */
export interface SmartAlert {
  id: string;
  level: 'warning' | 'error' | 'info';
  title: string;
  description: string;
  suggestion: string;
  icon: string;
}

export type DashboardLoadingState = 'loading' | 'loaded' | 'error' | 'partial';

// ═══════════════════════════════════════════════
// Models Types (M5)
// ═══════════════════════════════════════════════

export interface ModelEntry {
  name: string;
  model: string | null;
  size: number | null;
  sizeFormatted: string;
  digest: string | null;
  modifiedAt: string | null;
  details: Record<string, unknown> | null;
  isLoaded: boolean;
  downloaded: boolean;
}

export interface RuntimeParams {
  executable: string | null;
  modelPath: string | null;
  ctxSize: number | null;
  port: number | null;
  host: string | null;
  ngl: number | null;
  backend: string | null;
  mmap: boolean | null;
  jinja: boolean;
  mmproj: string | null;
  contextShift: boolean | null;
  keep: number | null;
  reasoningFormat: string | null;
  specType: string | null;
  specDraftMax: number | null;
  specDraftPMin: number | null;
  rawCmdline: string;
}

export interface LoadedModelDetail {
  name: string;
  params: RuntimeParams | null;
  process: {
    pid: number;
    rssGb: number;
    cpuPercent: number;
    uptime: string;
    uptimeSeconds: number;
  } | null;
}

export interface LoadModelOptions {
  modelName: string;
  ctxSize: number | null;
  llamacppBackend: string | null;
  llamacppArgs: string;
  mergeArgs: boolean;
  saveOptions: boolean;
}

export interface RunEvidenceSeed {
  id: string;
  kind: 'smoke_test' | 'load_attempt';
  model_name: string;
  prompt: string;
  response_text: string;
  success: boolean;
  error: string | null;
  load_message: string | null;
  requested_backend: string | null;
  requested_ctx_size: number | null;
  requested_llamacpp_args: string | null;
  merge_args: boolean | null;
  save_options: boolean | null;
  input_tokens: number;
  output_tokens: number;
  prompt_eval_tps: number;
  generation_tps: number;
  ttft_seconds: number;
  total_seconds: number;
  finish_reason: string;
  finish_confidence: string;
  observed_pid: number | null;
  observed_backend: string | null;
  observed_ctx_size: number | null;
  process_rss_gb: number | null;
  ram_used_before_gb: number | null;
  ram_used_after_gb: number | null;
  swap_used_before_gb: number | null;
  swap_used_after_gb: number | null;
  warnings: string[];
  timestamp: string;
}

export interface SmokeTestResponse {
  success: boolean;
  message: string;
  evidence: RunEvidenceSeed;
}

export interface ActionState {
  loading: boolean;
  error: string | null;
}

// ═══════════════════════════════════════════════
// Notification Types (M9)
// ═══════════════════════════════════════════════

export type NotificationLevel = 'success' | 'error' | 'warning' | 'info';

export interface Notification {
  id: string;
  level: NotificationLevel;
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  href: string | null;
  toastDuration: number;
}

export interface ToastData {
  id: string;
  level: NotificationLevel;
  title: string;
  message: string;
  href: string | null;
  duration: number;
  exiting: boolean;
}

// ═══════════════════════════════════════════════
// Profile Types (M10)
// ═══════════════════════════════════════════════

export interface ProfileConfig {
  ctx_size: number | null;
  global_timeout: number | null;
  llamacpp_backend: string | null;
  llamacpp_args: string | null;
  max_tokens: number | null;
  temperature: number | null;
  app_timeout: number | null;
  stop_sequences: string | null;
}

export interface Profile {
  id: string;
  name: string;
  description: string;
  icon: string;
  config: ProfileConfig;
  is_builtin: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface ModelProfiles {
  model_name: string;
  default_profile_id: string | null;
  profiles: Profile[];
}

export interface SmartRecommendation {
  model_name: string;
  model_size_gb: number | null;
  model_loaded: boolean;
  ram_total_gb: number;
  ram_available_gb: number;
  planning_headroom_gb: number | null;
  reserved_system_gb: number | null;
  recommended_ctx: number;
  safe_max_ctx: number;
  risk_threshold_ctx: number;
  warnings: string[];
  notes: string[];
}

// ═══════════════════════════════════════════════
// Diagnostics Types (M11)
// ═══════════════════════════════════════════════

export type DiagnosticSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info';
export type AlertStatus = 'active' | 'resolved' | 'dismissed';

export interface DiagnosticAlert {
  rule_id: string;
  rule_name: string;
  severity: DiagnosticSeverity;
  title: string;
  description: string;
  impact: string;
  suggestion: string;
  evidence: Record<string, unknown>;
  timestamp: string;
  status: AlertStatus;
}

export interface RuleResult {
  rule_id: string;
  rule_name: string;
  description: string;
  passed: boolean;
  alert: DiagnosticAlert | null;
  execution_time_ms: number;
}

export interface DiagnosticReport {
  timestamp: string;
  total_rules: number;
  passed: number;
  warnings: number;
  errors: number;
  results: RuleResult[];
  alerts: DiagnosticAlert[];
  execution_time_ms: number;
}

export interface AlertHistoryEntry {
  timestamp: string;
  rule_id: string;
  rule_name: string;
  severity: DiagnosticSeverity;
  event: 'appeared' | 'resolved' | 'dismissed';
  title: string;
}

// ═══════════════════════════════════════════════
// Metrics Types (M12)
// ═══════════════════════════════════════════════

export interface MetricPoint {
  t: string;
  ram_used: number;
  ram_total: number;
  ram_pct: number;
  cpu_pct: number;
  swap_used: number;
  gpu_load_pct: number | null;
  gpu_temp_c: number | null;
  temps: Record<string, number>;
}

export interface TaskRecord {
  timestamp: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  prompt_tps: number;
  gen_tps: number;
  ttft_seconds: number;
  total_seconds: number;
  finish_reason: string;
  finish_confidence: string;
}

export type TimeRange = 5 | 15 | 30;

// ═══════════════════════════════════════════════
// Bench Lab Types (M13)
// ═══════════════════════════════════════════════

export interface BenchPrompt {
  id: string;
  name: string;
  prompt: string;
  system_prompt: string;
  max_tokens: number;
  temperature: number;
  expected_format: string | null;
  tags: string[];
}

export interface BenchSuite {
  id: string;
  name: string;
  description: string;
  icon: string;
  prompts: BenchPrompt[];
  recommended_ctx: number;
  recommended_temp: number;
  estimated_minutes: number;
}

export interface BenchResult {
  prompt_id: string;
  prompt_name: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  prompt_eval_tps: number;
  generation_tps: number;
  ttft_seconds: number;
  total_seconds: number;
  finish_reason: string;
  finish_confidence: string;
  response_preview: string;
  response_full: string;
  timestamp: string;
  error: string | null;
}

export interface SuiteResult {
  suite_id: string;
  suite_name: string;
  model: string;
  results: BenchResult[];
  avg_gen_tps: number;
  avg_ttft: number;
  total_tokens: number;
  total_seconds: number;
  truncated_count: number;
  error_count: number;
  timestamp: string;
}

export type BenchStoredResult = BenchResult | SuiteResult;
