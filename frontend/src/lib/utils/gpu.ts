import type { HardwareInfo } from '$lib/types';

export interface GpuMemory {
  usedGb: number;
  totalGb: number | null;
  percent: number | null;
  detail: string;
}

/**
 * Combine dedicated VRAM and GTT. On APUs such as Strix Halo most model weights
 * live in GTT (shared system memory), so VRAM alone understates GPU memory use.
 */
export function gpuMemory(hardware: HardwareInfo | null | undefined): GpuMemory | null {
  if (!hardware?.gpu_available) return null;
  const { gpu_vram_used_gb: vram, gpu_gtt_used_gb: gtt } = hardware;
  if (typeof vram !== 'number' && typeof gtt !== 'number') return null;

  const usedGb = (vram ?? 0) + (gtt ?? 0);
  const vramTotal = hardware.gpu_vram_total_gb;
  const gttTotal = hardware.gpu_gtt_total_gb;
  const totalGb = typeof vramTotal === 'number' || typeof gttTotal === 'number' ? (vramTotal ?? 0) + (gttTotal ?? 0) : null;
  const parts = [
    typeof gtt === 'number' ? `GTT ${gtt.toFixed(1)} GB` : null,
    typeof vram === 'number' ? `VRAM ${vram.toFixed(1)} GB` : null
  ].filter(Boolean);

  return {
    usedGb,
    totalGb,
    percent: totalGb ? (usedGb / totalGb) * 100 : null,
    detail: parts.join(' · ')
  };
}
