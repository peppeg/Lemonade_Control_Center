import { writable } from 'svelte/store';
import { api } from '$lib/api/client';
import { notify } from '$lib/stores/notifications';
import type { BenchResult, BenchStoredResult, BenchSuite, SuiteResult } from '$lib/types';

export const benchSuites = writable<BenchSuite[]>([]);
export const benchResults = writable<BenchStoredResult[]>([]);
export const currentBenchResult = writable<BenchResult | SuiteResult | null>(null);
export const benchLoading = writable(false);
export const benchError = writable<string | null>(null);

export async function loadBenchData(): Promise<void> {
  benchError.set(null);
  const [suitesResult, resultsResult] = await Promise.allSettled([
    api.bench.suites(),
    api.bench.results(),
  ]);

  if (suitesResult.status === 'fulfilled' && suitesResult.value.ok) {
    benchSuites.set(suitesResult.value.data.suites);
  } else if (suitesResult.status === 'fulfilled' && !suitesResult.value.ok) {
    benchError.set(suitesResult.value.error);
  }

  if (resultsResult.status === 'fulfilled' && resultsResult.value.ok) {
    benchResults.set(resultsResult.value.data.results);
  }
}

export async function runQuickBench(input: {
  model: string;
  prompt: string;
  max_tokens: number;
  temperature: number;
  system_prompt?: string;
  workflow_profile_id?: string;
  workflow_profile_name?: string;
}): Promise<void> {
  benchLoading.set(true);
  benchError.set(null);
  const result = await api.bench.runQuick(input);
  if (result.ok) {
    currentBenchResult.set(result.data);
    notify.success('Quick benchmark completed', `${result.data.generation_tps} t/s`, { href: '/bench' });
    await loadBenchData();
  } else {
    benchError.set(result.error);
    notify.error('Benchmark failed', result.error, { href: '/bench' });
  }
  benchLoading.set(false);
}

export async function runSuiteBench(model: string, suiteId: string, workflowProfileId?: string, workflowProfileName?: string): Promise<void> {
  benchLoading.set(true);
  benchError.set(null);
  const result = await api.bench.runSuite({ model, suite_id: suiteId, workflow_profile_id: workflowProfileId, workflow_profile_name: workflowProfileName });
  if (result.ok) {
    currentBenchResult.set(result.data);
    notify.success('Suite benchmark completed', `${result.data.suite_name}: ${result.data.avg_gen_tps} t/s`, { href: '/bench' });
    await loadBenchData();
  } else {
    benchError.set(result.error);
    notify.error('Suite benchmark failed', result.error, { href: '/bench' });
  }
  benchLoading.set(false);
}

export async function annotateBenchResult(resultId: string, quality: number | null, notes: string): Promise<void> {
  const result = await api.bench.annotate(resultId, { manual_quality_score: quality, manual_notes: notes });
  if (result.ok) {
    notify.success('Bench assessment saved', resultId, { toastDuration: 2200 });
    await loadBenchData();
  } else {
    notify.error('Assessment failed', result.error);
  }
}

export async function clearBenchResults(): Promise<void> {
  const result = await api.bench.clear();
  if (result.ok) {
    benchResults.set([]);
    currentBenchResult.set(null);
    notify.info('Bench results cleared', 'All stored Bench Lab results were removed.');
  } else {
    notify.error('Clear failed', result.error);
  }
}

export function exportBench(format: 'csv' | 'json' | 'markdown'): void {
  const urls = {
    csv: api.bench.csvUrl(),
    json: api.bench.jsonUrl(),
    markdown: api.bench.markdownUrl(),
  };
  const anchor = document.createElement('a');
  anchor.href = urls[format];
  anchor.download = '';
  anchor.click();
}
