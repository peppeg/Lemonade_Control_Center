<script lang="ts">
  import type { BenchResult, SuiteResult } from '$lib/types';

  export let result: BenchResult | SuiteResult;

  function isSuite(value: BenchResult | SuiteResult): value is SuiteResult {
    return 'results' in value;
  }
</script>

<section class="ops-panel">
  <div class="ops-card-header">
    <h2 class="ops-title">Latest Result</h2>
    <span class="ops-badge {isSuite(result) ? '' : result.error ? 'ops-badge-danger' : 'ops-badge-ok'}">
      {isSuite(result) ? 'Suite' : result.error ? 'Error' : 'Done'}
    </span>
  </div>
  <div class="space-y-4 p-5">
    {#if isSuite(result)}
      <div class="grid grid-cols-2 gap-3 md:grid-cols-5">
        <div><span class="ops-label">Suite</span><p class="ops-value">{result.suite_name}</p></div>
        <div><span class="ops-label">Avg TPS</span><p class="ops-value">{result.avg_gen_tps}</p></div>
        <div><span class="ops-label">Avg TTFT</span><p class="ops-value">{result.avg_ttft}s</p></div>
        <div><span class="ops-label">Tokens</span><p class="ops-value">{result.total_tokens}</p></div>
        <div><span class="ops-label">Errors</span><p class="ops-value">{result.error_count}</p></div>
      </div>
    {:else}
      <div class="grid grid-cols-2 gap-3 md:grid-cols-6">
        <div><span class="ops-label">Input</span><p class="ops-value">{result.input_tokens}</p></div>
        <div><span class="ops-label">Output</span><p class="ops-value">{result.output_tokens}</p></div>
        <div><span class="ops-label">Prompt TPS</span><p class="ops-value">{result.prompt_eval_tps}</p></div>
        <div><span class="ops-label">Gen TPS</span><p class="ops-value">{result.generation_tps}</p></div>
        <div><span class="ops-label">TTFT</span><p class="ops-value">{result.ttft_seconds}s</p></div>
        <div><span class="ops-label">Total</span><p class="ops-value">{result.total_seconds}s</p></div>
      </div>
      {#if result.error}
        <div class="ops-banner ops-banner-danger">{result.error}</div>
      {:else}
        <details>
          <summary class="cursor-pointer ops-label">Response</summary>
          <pre class="ops-terminal mt-3 max-h-96 overflow-auto p-3 whitespace-pre-wrap">{result.response_full}</pre>
        </details>
      {/if}
    {/if}
    <details>
      <summary class="cursor-pointer ops-label">Raw metrics JSON</summary>
      <pre class="ops-terminal mt-3 max-h-80 overflow-auto p-3">{JSON.stringify(result, null, 2)}</pre>
    </details>
  </div>
</section>
