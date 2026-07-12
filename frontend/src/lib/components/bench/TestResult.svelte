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
      <div class="grid gap-3 text-sm md:grid-cols-3">
        <div><span class="ops-label">Model</span><p class="ops-value">{result.observed_model_name ?? result.model}</p></div>
        <div><span class="ops-label">Profile</span><p class="ops-value">{result.workflow_profile_name ?? 'No profile'}</p></div>
        <div><span class="ops-label">Runtime</span><p class="ops-value">{result.runtime_label ?? result.runtime_id ?? 'Unavailable'}</p></div>
      </div>
      <div class="space-y-3">
        {#each result.results as promptResult}
          <details class="border border-[#34382d] bg-[#111312] p-4">
            <summary class="cursor-pointer ops-value">{promptResult.prompt_name} · {promptResult.generation_tps} tok/s · {promptResult.error ? 'failed' : 'completed'}</summary>
            <div class="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <div><span class="ops-label">TTFT</span><p>{promptResult.ttft_seconds}s</p></div>
              <div><span class="ops-label">Tokens</span><p>{promptResult.input_tokens}/{promptResult.output_tokens}</p></div>
              <div><span class="ops-label">Backend</span><p>{promptResult.observed_backend ?? 'Unavailable'}</p></div>
              <div><span class="ops-label">RAM delta</span><p>{promptResult.ram_used_before_gb !== null && promptResult.ram_used_after_gb !== null ? `${(promptResult.ram_used_after_gb - promptResult.ram_used_before_gb).toFixed(1)} GB` : 'Unavailable'}</p></div>
            </div>
            <h3 class="ops-label mt-4">Prompt</h3>
            <pre class="ops-terminal mt-2 max-h-56 overflow-auto whitespace-pre-wrap p-3">{promptResult.prompt}</pre>
            {#if promptResult.reasoning_text}
              <h3 class="ops-label mt-4">Reasoning</h3>
              <pre class="ops-terminal mt-2 max-h-72 overflow-auto whitespace-pre-wrap p-3">{promptResult.reasoning_text}</pre>
            {/if}
            <h3 class="ops-label mt-4">Output</h3>
            <pre class="ops-terminal mt-2 max-h-96 overflow-auto whitespace-pre-wrap p-3">{promptResult.response_full || promptResult.error || 'No output'}</pre>
          </details>
        {/each}
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
      <div class="grid gap-3 text-sm md:grid-cols-4">
        <div><span class="ops-label">Profile</span><p class="ops-value">{result.workflow_profile_name ?? 'No profile'}</p></div>
        <div><span class="ops-label">Runtime</span><p class="ops-value">{result.runtime_label ?? result.runtime_id ?? 'Unavailable'}</p></div>
        <div><span class="ops-label">Backend</span><p class="ops-value">{result.observed_backend ?? 'Unavailable'}</p></div>
        <div><span class="ops-label">Context</span><p class="ops-value">{result.observed_ctx_size ?? 'Unavailable'}</p></div>
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
