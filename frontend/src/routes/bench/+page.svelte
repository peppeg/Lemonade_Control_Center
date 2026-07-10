<script lang="ts">
  import { onMount } from 'svelte';
  import { capabilities } from '$lib/stores/capabilities';
  import { models, refreshModels } from '$lib/stores/models';
  import TestResult from '$lib/components/bench/TestResult.svelte';
  import {
    benchError,
    benchLoading,
    benchResults,
    benchSuites,
    clearBenchResults,
    currentBenchResult,
    exportBench,
    loadBenchData,
    runQuickBench,
    runSuiteBench,
  } from '$lib/stores/bench';
  import type { BenchStoredResult } from '$lib/types';
  import { loadWorkflowDefaults } from '$lib/utils/workflowDefaults';

  type Tab = 'quick' | 'suites' | 'results' | 'compare';
  let tab: Tab = 'quick';
  let selectedModel = '';
  let prompt = 'Write a Python function that implements a binary search tree with insert, delete, and search operations. Include type hints and docstrings.';
  let systemPrompt = '';
  let maxTokens = 2000;
  let temperature = 0.3;

  onMount(() => {
    const defaults = loadWorkflowDefaults();
    maxTokens = defaults.maxOutputTokens;
    temperature = defaults.temperature;
    refreshModels();
    loadBenchData();
  });

  $: if (!selectedModel && $models.length > 0) {
    selectedModel = $models[0].name;
  }

  function resultName(result: BenchStoredResult): string {
    return 'suite_name' in result ? result.suite_name : result.prompt_name;
  }

  function resultTps(result: BenchStoredResult): string {
    return String('avg_gen_tps' in result ? result.avg_gen_tps : result.generation_tps);
  }
</script>

{#if !$capabilities.bench_lab}
  <section class="ops-panel p-6">
    <h1 class="text-3xl font-bold">Bench Lab</h1>
    <p class="mt-3 max-w-3xl text-sm text-muted-foreground">
      Bench Lab is disabled. Set <code class="ops-mono">ENABLE_BENCH_LAB=true</code> in the backend environment to expose benchmark endpoints and enable this page.
    </p>
  </section>
{:else}
  <div class="space-y-5">
    <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div>
        <h1 class="text-3xl font-bold">Bench Lab</h1>
        <p class="mt-2 max-w-3xl text-sm text-muted-foreground">
          Optional benchmark lab for quick tests, predefined suites, stored results, and export.
        </p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button class="ops-button" type="button" on:click={() => exportBench('csv')}>CSV</button>
        <button class="ops-button" type="button" on:click={() => exportBench('json')}>JSON</button>
        <button class="ops-button" type="button" on:click={() => exportBench('markdown')}>Markdown</button>
        <button class="ops-button ops-button-danger" type="button" on:click={clearBenchResults}>Clear</button>
      </div>
    </div>

    {#if $benchError}
      <section class="ops-banner ops-banner-danger">{$benchError}</section>
    {/if}

    <div class="flex flex-wrap gap-2 rounded border border-[#444936] bg-[#2b2d2a] p-1">
      {#each ['quick', 'suites', 'results', 'compare'] as item}
        <button class="rounded px-4 py-2 ops-mono text-sm {tab === item ? 'bg-[#4a4d49] text-lemon' : 'text-[#e3e5d3] hover:bg-[#363935]'}" type="button" on:click={() => tab = item as Tab}>
          {item}
        </button>
      {/each}
    </div>

    {#if tab === 'quick'}
      <section class="ops-panel p-5">
        <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label class="block space-y-2">
            <span class="ops-label">Model</span>
            <select class="ops-select" bind:value={selectedModel}>
              {#each $models as model}
                <option value={model.name}>{model.name}</option>
              {/each}
            </select>
          </label>
          <label class="block space-y-2">
            <span class="ops-label">max_tokens</span>
            <input class="ops-input" type="number" min="1" bind:value={maxTokens} />
          </label>
          <label class="block space-y-2">
            <span class="ops-label">temperature</span>
            <input class="ops-input" type="number" min="0" max="2" step="0.05" bind:value={temperature} />
          </label>
          <label class="block space-y-2">
            <span class="ops-label">system_prompt</span>
            <input class="ops-input" bind:value={systemPrompt} placeholder="Optional" />
          </label>
          <label class="block space-y-2 md:col-span-2">
            <span class="ops-label">Prompt</span>
            <textarea class="ops-textarea min-h-44" bind:value={prompt}></textarea>
          </label>
        </div>
        <div class="mt-5 flex justify-end">
          <button class="ops-button ops-button-primary" type="button" disabled={!selectedModel || !prompt.trim() || $benchLoading} on:click={() => runQuickBench({ model: selectedModel, prompt, max_tokens: maxTokens, temperature, system_prompt: systemPrompt })}>
            {$benchLoading ? 'Running' : 'Run Test'}
          </button>
        </div>
      </section>
    {:else if tab === 'suites'}
      <section class="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {#each $benchSuites as suite}
          <article class="ops-panel p-5">
            <div class="flex items-start justify-between gap-4">
              <div>
                <h2 class="ops-title">{suite.name}</h2>
                <p class="ops-subtitle">{suite.description}</p>
                <p class="mt-3 text-sm text-muted-foreground">{suite.prompts.length} prompts, about {suite.estimated_minutes} min, temp {suite.recommended_temp}</p>
              </div>
              <button class="ops-button ops-button-primary" type="button" disabled={!selectedModel || $benchLoading} on:click={() => runSuiteBench(selectedModel, suite.id)}>
                Run All
              </button>
            </div>
            <details class="mt-4">
              <summary class="cursor-pointer ops-label">Prompts</summary>
              <ul class="mt-3 space-y-2 text-sm text-muted-foreground">
                {#each suite.prompts as suitePrompt}
                  <li><span class="ops-value">{suitePrompt.name}</span>: {suitePrompt.prompt}</li>
                {/each}
              </ul>
            </details>
          </article>
        {/each}
      </section>
    {:else if tab === 'results'}
      <section class="ops-panel">
        <div class="ops-card-header">
          <h2 class="ops-title">Stored Results</h2>
          <button class="ops-button" type="button" on:click={loadBenchData}>Refresh</button>
        </div>
        <div class="overflow-x-auto">
          <table class="ops-table">
            <thead>
              <tr><th>Timestamp</th><th>Model</th><th>Run</th><th class="text-right">TPS</th><th class="text-right">Tokens</th><th>Status</th></tr>
            </thead>
            <tbody>
              {#each $benchResults as result}
                <tr>
                  <td class="ops-value">{new Date(result.timestamp).toLocaleString()}</td>
                  <td class="ops-value">{result.model}</td>
                  <td>{resultName(result)}</td>
                  <td class="text-right ops-value">{resultTps(result)}</td>
                  <td class="text-right ops-value">{'total_tokens' in result ? result.total_tokens : result.output_tokens}</td>
                  <td><span class="ops-badge {('error' in result && result.error) || ('error_count' in result && result.error_count > 0) ? 'ops-badge-danger' : 'ops-badge-ok'}">stored</span></td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {:else}
      <section class="ops-panel p-5">
        <h2 class="ops-title">Compare</h2>
        <p class="ops-subtitle">Comparison uses stored results. Run the same suite on multiple models, then compare average TPS, TTFT, total tokens, and errors here.</p>
        <div class="mt-5 overflow-x-auto">
          <table class="ops-table">
            <thead><tr><th>Model</th><th>Run</th><th class="text-right">TPS</th><th class="text-right">TTFT</th><th class="text-right">Tokens</th></tr></thead>
            <tbody>
              {#each $benchResults as result}
                <tr>
                  <td class="ops-value">{result.model}</td>
                  <td>{resultName(result)}</td>
                  <td class="text-right ops-value">{resultTps(result)}</td>
                  <td class="text-right ops-value">{'avg_ttft' in result ? result.avg_ttft : result.ttft_seconds}s</td>
                  <td class="text-right ops-value">{'total_tokens' in result ? result.total_tokens : result.output_tokens}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}

    {#if $currentBenchResult}
      <TestResult result={$currentBenchResult} />
    {/if}
  </div>
{/if}
