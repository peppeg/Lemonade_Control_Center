/** Models loaded by Lemonade, as served by /api/lemonade/loaded. */
import type { LoadedModelDetail } from '$lib/types';
import { formatDuration } from '$lib/utils/format';

export interface LoadedModelResponse {
  name: string;
  type: string | null;
  server: {
    found: boolean;
    process: Record<string, unknown> | null;
    params: Record<string, unknown> | null;
  };
}

export function parseLoadedModel(model: LoadedModelResponse): LoadedModelDetail {
  const { process, params } = model.server;
  return {
    name: model.name,
    type: model.type,
    params: params
      ? {
          executable: (params.executable as string) ?? null,
          modelPath: (params.model_path as string) ?? null,
          ctxSize: (params.ctx_size as number) ?? null,
          port: (params.port as number) ?? null,
          host: (params.host as string) ?? null,
          ngl: (params.ngl as number) ?? null,
          backend: (params.backend as string) ?? null,
          mmap: (params.mmap as boolean) ?? null,
          jinja: (params.jinja as boolean) ?? false,
          mmproj: (params.mmproj as string) ?? null,
          contextShift: (params.context_shift as boolean) ?? null,
          keep: (params.keep as number) ?? null,
          reasoningFormat: (params.reasoning_format as string) ?? null,
          specType: (params.spec_type as string) ?? null,
          specDraftMax: (params.spec_draft_n_max as number) ?? null,
          specDraftPMin: (params.spec_draft_p_min as number) ?? null,
          rawCmdline: (params.raw_cmdline as string) ?? '',
        }
      : null,
    process: process
      ? {
          pid: (process.pid as number) ?? 0,
          rssGb: (process.rss_gb as number) ?? 0,
          cpuPercent: (process.cpu_percent as number) ?? 0,
          uptime: process.uptime_seconds ? formatDuration(process.uptime_seconds as number) : '—',
          uptimeSeconds: (process.uptime_seconds as number) ?? 0,
        }
      : null,
  };
}

/** Whether chat requests make sense. Older Lemonade versions do not report the type. */
export function canChat(model: { type: string | null }): boolean {
  return model.type === null || model.type === 'llm';
}
