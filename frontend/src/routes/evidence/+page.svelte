<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api/client';
  import type { RunEvidenceSeed } from '$lib/types';
  import { Download, FileClock, RefreshCw, Search } from 'lucide-svelte';

  type KindFilter = 'all' | RunEvidenceSeed['kind'];
  type StatusFilter = 'all' | 'passed' | 'failed';

  let evidence: RunEvidenceSeed[] = [];
  let selected: RunEvidenceSeed | null = null;
  let loading = true;
  let detailLoading = false;
  let error: string | null = null;
  let search = '';
  let kindFilter: KindFilter = 'all';
  let statusFilter: StatusFilter = 'all';

  const kindFilters: { label: string; value: KindFilter }[] = [
    { label: 'All runs', value: 'all' },
    { label: 'Smoke tests', value: 'smoke_test' },
    { label: 'Load attempts', value: 'load_attempt' },
  ];

  onMount(async () => {
    await refreshEvidence();
    const requestedId = new URLSearchParams(window.location.search).get('run');
    if (requestedId && evidence.some((item) => item.id === requestedId)) {
      await selectEvidence(requestedId);
    }
  });

  $: filteredEvidence = evidence.filter((item) => {
    const query = search.trim().toLowerCase();
    if (!query) return true;
    return `${item.model_name} ${item.requested_model_name ?? ''} ${item.observed_model_name ?? ''} ${item.runtime_id ?? ''} ${item.runtime_label ?? ''} ${item.workflow_profile_id ?? ''} ${item.workflow_profile_name ?? ''} ${item.id} ${item.observed_backend ?? ''} ${item.error ?? ''}`
      .toLowerCase()
      .includes(query);
  });
  $: if (!loading && !filteredEvidence.some((item) => item.id === selected?.id)) {
    selected = filteredEvidence[0] ?? null;
  }

  async function refreshEvidence() {
    loading = true;
    error = null;
    const result = await api.lemonade.runEvidence({
      kind: kindFilter === 'all' ? undefined : kindFilter,
      success: statusFilter === 'all' ? undefined : statusFilter === 'passed',
    });
    if (result.ok) {
      evidence = result.data.results;
      if (selected) {
        const current = evidence.find((item) => item.id === selected?.id);
        selected = current ?? evidence[0] ?? null;
      } else {
        selected = evidence[0] ?? null;
      }
    } else {
      evidence = [];
      selected = null;
      error = result.error;
    }
    loading = false;
  }

  async function applyKind(value: KindFilter) {
    kindFilter = value;
    await refreshEvidence();
  }

  async function applyStatus(value: StatusFilter) {
    statusFilter = value;
    await refreshEvidence();
  }

  async function selectEvidence(id: string) {
    if (selected?.id === id || detailLoading) return;
    detailLoading = true;
    const result = await api.lemonade.runEvidenceDetail(id);
    if (result.ok) {
      selected = result.data;
    } else {
      error = result.error;
    }
    detailLoading = false;
  }

  function formatTimestamp(value: string): string {
    return new Date(value).toLocaleString();
  }

  function formatKind(kind: RunEvidenceSeed['kind']): string {
    return kind === 'smoke_test' ? 'Smoke test' : 'Load attempt';
  }

  function formatNumber(value: number | null, digits = 1): string {
    return value === null ? 'Unavailable' : value.toFixed(digits);
  }

  function formatContext(value: number | null): string {
    return value === null ? 'Unavailable' : value.toLocaleString();
  }

  function memoryDelta(before: number | null, after: number | null): string {
    if (before === null || after === null) return 'Unavailable';
    const delta = after - before;
    return `${delta >= 0 ? '+' : ''}${delta.toFixed(1)} GB`;
  }

  function logLevelClass(level: string): string {
    if (level === 'error') return 'text-danger';
    if (level === 'warning') return 'text-status-warn';
    if (level === 'performance') return 'text-[#76a9ff]';
    if (level === 'backend') return 'text-[#7fd7c4]';
    if (level === 'update') return 'text-[#ffcf7a]';
    return 'text-status-ok';
  }
</script>

<div class="space-y-6">
  <section class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
    <div>
      <h2 class="ops-title">Run Evidence</h2>
      <p class="ops-subtitle">Recorded load attempts and completion checks.</p>
    </div>
    <button class="ops-button" type="button" on:click={refreshEvidence} disabled={loading}>
      <RefreshCw class="h-4 w-4 {loading ? 'animate-spin' : ''}" />
      Refresh
    </button>
  </section>

  {#if error}
    <section class="ops-banner ops-banner-danger">{error}</section>
  {/if}

  <section class="grid min-h-[620px] gap-5 2xl:grid-cols-[minmax(430px,0.85fr)_minmax(0,1.4fr)]">
    <div class="ops-panel min-w-0 overflow-hidden">
      <div class="space-y-3 border-b border-[#34382d] p-3">
        <div class="flex flex-wrap gap-2">
          {#each kindFilters as filter}
            <button
              class="rounded border px-3 py-2 text-sm {kindFilter === filter.value ? 'border-[#596044] bg-[#111312] text-foreground' : 'border-transparent text-muted-foreground hover:bg-[#222522]'}"
              type="button"
              on:click={() => applyKind(filter.value)}
            >
              {filter.label}
            </button>
          {/each}
        </div>
        <div class="grid gap-3 sm:grid-cols-[1fr_auto]">
          <label class="relative block">
            <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input class="ops-input ops-input-icon-left w-full" placeholder="Search runs..." bind:value={search} />
          </label>
          <select class="ops-input min-w-32" bind:value={statusFilter} on:change={() => applyStatus(statusFilter)} aria-label="Filter by result">
            <option value="all">All results</option>
            <option value="passed">Passed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      <div class="max-h-[700px] overflow-auto">
        <table class="ops-table">
          <thead>
            <tr>
              <th>Run</th>
              <th>Result</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {#if loading}
              <tr><td colspan="3" class="text-muted-foreground">Loading run evidence...</td></tr>
            {:else if filteredEvidence.length === 0}
              <tr><td colspan="3" class="text-muted-foreground">No evidence matched the current filters.</td></tr>
            {:else}
              {#each filteredEvidence as item}
                <tr class={selected?.id === item.id ? 'bg-[#222522]' : ''}>
                  <td class="max-w-[240px]">
                    <button class="block w-full text-left" type="button" on:click={() => selectEvidence(item.id)}>
                      <span class="ops-value block truncate">{item.model_name}</span>
                      <span class="mt-1 block text-xs text-muted-foreground">{formatKind(item.kind)}</span>
                      <span class="mt-1 block truncate text-xs text-muted-foreground">
                        {item.runtime_label ?? item.runtime_id ?? 'Runtime unavailable'}
                        {item.workflow_profile_name ? ` · ${item.workflow_profile_name}` : ''}
                      </span>
                      {#if item.observed_model_name && item.observed_model_name !== (item.requested_model_name ?? item.model_name)}
                        <span class="mt-1 block truncate text-xs text-muted-foreground">Observed: {item.observed_model_name}</span>
                      {/if}
                    </button>
                  </td>
                  <td>
                    <span class="ops-badge {item.success ? 'ops-badge-ok' : 'ops-badge-danger'}">
                      {item.success ? 'passed' : 'failed'}
                    </span>
                  </td>
                  <td class="whitespace-nowrap text-xs text-muted-foreground">{formatTimestamp(item.timestamp)}</td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>
    </div>

    <div class="ops-panel min-w-0 overflow-hidden">
      {#if selected}
        <div class="flex flex-col gap-4 border-b border-[#34382d] p-5 lg:flex-row lg:items-start lg:justify-between">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <FileClock class="h-4 w-4 text-lemon" />
              <h3 class="ops-title truncate">{selected.model_name}</h3>
              <span class="ops-badge {selected.success ? 'ops-badge-ok' : 'ops-badge-danger'}">
                {selected.success ? 'passed' : 'failed'}
              </span>
            </div>
            <p class="ops-subtitle mt-1">{formatKind(selected.kind)} · {formatTimestamp(selected.timestamp)}</p>
            <p class="ops-mono mt-2 break-all text-xs text-muted-foreground">{selected.id}</p>
          </div>
          <div class="flex shrink-0 gap-2">
            <a class="ops-button" href={api.lemonade.runEvidenceExportUrl(selected.id, 'json')} download title="Download JSON evidence">
              <Download class="h-4 w-4" /> JSON
            </a>
            <a class="ops-button" href={api.lemonade.runEvidenceExportUrl(selected.id, 'markdown')} download title="Download Markdown evidence">
              <Download class="h-4 w-4" /> Markdown
            </a>
          </div>
        </div>

        <div class="space-y-6 p-5 {detailLoading ? 'opacity-60' : ''}">
          <dl class="grid grid-cols-2 gap-px overflow-hidden border border-[#34382d] bg-[#34382d] sm:grid-cols-3 xl:grid-cols-6">
            <div class="bg-[#171a19] p-3"><dt class="ops-label">Duration</dt><dd class="ops-value mt-1">{selected.total_seconds.toFixed(3)}s</dd></div>
            <div class="bg-[#171a19] p-3"><dt class="ops-label">TTFT</dt><dd class="ops-value mt-1">{selected.kind === 'smoke_test' ? `${selected.ttft_seconds.toFixed(3)}s` : 'N/A'}</dd></div>
            <div class="bg-[#171a19] p-3"><dt class="ops-label">Generation</dt><dd class="ops-value mt-1">{selected.kind === 'smoke_test' ? `${selected.generation_tps.toFixed(1)} tok/s` : 'N/A'}</dd></div>
            <div class="bg-[#171a19] p-3"><dt class="ops-label">Tokens</dt><dd class="ops-value mt-1">{selected.kind === 'smoke_test' ? `${selected.input_tokens}/${selected.output_tokens}` : 'N/A'}</dd></div>
            <div class="bg-[#171a19] p-3"><dt class="ops-label">RAM delta</dt><dd class="ops-value mt-1">{memoryDelta(selected.ram_used_before_gb, selected.ram_used_after_gb)}</dd></div>
            <div class="bg-[#171a19] p-3"><dt class="ops-label">RSS</dt><dd class="ops-value mt-1">{selected.process_rss_gb === null ? 'Unavailable' : `${formatNumber(selected.process_rss_gb)} GB`}</dd></div>
          </dl>

          <section>
            <h4 class="ops-label mb-3">Identity</h4>
            <dl class="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
              <div><dt class="text-muted-foreground">Requested model</dt><dd class="ops-value mt-1 break-all">{selected.requested_model_name ?? selected.model_name}</dd></div>
              <div><dt class="text-muted-foreground">Observed model</dt><dd class="ops-value mt-1 break-all">{selected.observed_model_name ?? 'Unavailable'}</dd></div>
              <div><dt class="text-muted-foreground">LCC runtime</dt><dd class="ops-value mt-1">{selected.runtime_label ?? 'Unavailable'}{selected.runtime_id ? ` · ${selected.runtime_id}` : ''}</dd></div>
              <div><dt class="text-muted-foreground">Workflow profile</dt><dd class="ops-value mt-1">{selected.workflow_profile_name ?? 'Unavailable'}{selected.workflow_profile_id ? ` · ${selected.workflow_profile_id}` : ''}</dd></div>
              <div class="sm:col-span-2 xl:col-span-4"><dt class="text-muted-foreground">Server URL</dt><dd class="ops-value mt-1 break-all">{selected.runtime_server_url ?? 'Unavailable'}</dd></div>
            </dl>
          </section>

          <section>
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h4 class="ops-label">Telemetry Providers</h4>
              <span class="ops-badge ops-badge-warn">ownership {selected.accelerator_ownership}</span>
            </div>
            <p class="mb-3 text-sm text-muted-foreground">{selected.accelerator_ownership_note}</p>
            {#if selected.telemetry_samples.length > 0}
              <div class="space-y-3">
                {#each selected.telemetry_samples as sample}
                  <div class="border border-[#34382d] bg-[#111312] p-4">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="ops-value">{sample.provider_label}</span>
                      <span class="ops-badge">{sample.phase}</span>
                      <span class="ops-badge {sample.quality === 'measured' ? 'ops-badge-ok' : sample.quality === 'unsupported' ? '' : 'ops-badge-danger'}">{sample.quality}</span>
                    </div>
                    {#if sample.error}<p class="mt-2 text-sm text-status-warn">{sample.error}</p>{/if}
                    {#if sample.metrics.length > 0}
                      <dl class="mt-3 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-3">
                        {#each sample.metrics as metric}
                          <div>
                            <dt class="text-muted-foreground">{metric.name} · {metric.quality}</dt>
                            <dd class="ops-value mt-1">{metric.value ?? 'Unavailable'}{metric.value !== null ? metric.unit ?? '' : ''}</dd>
                            <dd class="mt-1 text-xs text-muted-foreground">{metric.evidence}</dd>
                          </div>
                        {/each}
                      </dl>
                    {/if}
                  </div>
                {/each}
              </div>
            {:else}
              <p class="text-sm text-muted-foreground">Legacy record: no provider samples were captured.</p>
            {/if}
          </section>

          <section>
            <h4 class="ops-label mb-3">Runtime</h4>
            <dl class="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
              <div><dt class="text-muted-foreground">Backend</dt><dd class="ops-value mt-1">{selected.observed_backend ?? 'Unavailable'}</dd></div>
              <div><dt class="text-muted-foreground">Context</dt><dd class="ops-value mt-1">{formatContext(selected.observed_ctx_size)}</dd></div>
              <div><dt class="text-muted-foreground">PID</dt><dd class="ops-value mt-1">{selected.observed_pid ?? 'Unavailable'}</dd></div>
              <div><dt class="text-muted-foreground">Endpoint</dt><dd class="ops-value mt-1 break-all">{selected.completion_endpoint ?? 'Unavailable'}</dd></div>
            </dl>
          </section>

          {#if selected.kind === 'smoke_test'}
            <section>
              <h4 class="ops-label mb-3">Request</h4>
              <dl class="mb-3 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
                <div><dt class="text-muted-foreground">Max tokens</dt><dd class="ops-value mt-1">{selected.request_max_tokens ?? 'Unavailable'}</dd></div>
                <div><dt class="text-muted-foreground">Temperature</dt><dd class="ops-value mt-1">{selected.request_temperature ?? 'Unavailable'}</dd></div>
                <div><dt class="text-muted-foreground">Timeout</dt><dd class="ops-value mt-1">{selected.request_timeout_seconds === null ? 'Unavailable' : `${selected.request_timeout_seconds}s`}</dd></div>
                <div><dt class="text-muted-foreground">Token source</dt><dd class="ops-value mt-1">{selected.token_count_source}</dd></div>
              </dl>
              <pre class="ops-mono max-h-56 overflow-auto whitespace-pre-wrap break-words border border-[#34382d] bg-[#111312] p-4 text-sm">{selected.prompt || 'No prompt recorded.'}</pre>
            </section>

            {#if selected.reasoning_text}
              <section>
                <h4 class="ops-label mb-3">Reasoning</h4>
                <pre class="ops-mono max-h-72 overflow-auto whitespace-pre-wrap break-words border border-[#34382d] bg-[#111312] p-4 text-sm">{selected.reasoning_text}</pre>
              </section>
            {/if}

            <section>
              <h4 class="ops-label mb-3">Response</h4>
              <pre class="ops-mono max-h-96 overflow-auto whitespace-pre-wrap break-words border border-[#34382d] bg-[#111312] p-4 text-sm">{selected.response_text || selected.error || 'No response recorded.'}</pre>
              <p class="mt-2 text-xs text-muted-foreground">Finish: {selected.finish_reason} · confidence {selected.finish_confidence}</p>
            </section>
          {:else}
            <section>
              <h4 class="ops-label mb-3">Load Request</h4>
              <dl class="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
                <div><dt class="text-muted-foreground">Requested backend</dt><dd class="ops-value mt-1">{selected.requested_backend ?? 'Default'}</dd></div>
                <div><dt class="text-muted-foreground">Requested context</dt><dd class="ops-value mt-1">{formatContext(selected.requested_ctx_size)}</dd></div>
                <div><dt class="text-muted-foreground">Merge args</dt><dd class="ops-value mt-1">{selected.merge_args === null ? 'Unavailable' : selected.merge_args ? 'Yes' : 'No'}</dd></div>
                <div><dt class="text-muted-foreground">Save options</dt><dd class="ops-value mt-1">{selected.save_options === null ? 'Unavailable' : selected.save_options ? 'Yes' : 'No'}</dd></div>
              </dl>
              {#if selected.requested_llamacpp_args}
                <pre class="ops-mono mt-4 overflow-auto whitespace-pre-wrap break-words border border-[#34382d] bg-[#111312] p-4 text-sm">{selected.requested_llamacpp_args}</pre>
              {/if}
              <p class="mt-4 text-sm text-muted-foreground">{selected.load_message ?? selected.error ?? 'No load message recorded.'}</p>
            </section>
          {/if}

          <section>
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h4 class="ops-label">Correlated Logs</h4>
              <span class="ops-badge {selected.log_source === 'journalctl' ? 'ops-badge-ok' : 'ops-badge-danger'}">
                {selected.log_source}
              </span>
            </div>
            {#if selected.log_window_started_at && selected.log_window_ended_at}
              <p class="mb-3 text-xs text-muted-foreground">
                {formatTimestamp(selected.log_window_started_at)} · {formatTimestamp(selected.log_window_ended_at)}
              </p>
            {/if}
            {#if selected.log_entries.length > 0}
              <div class="ops-terminal max-h-80 overflow-auto p-3 text-xs">
                {#each selected.log_entries as entry}
                  <div class="grid min-w-[620px] grid-cols-[210px_90px_1fr] gap-3 px-2 py-0.5">
                    <span class="text-muted-foreground">{entry.timestamp ? formatTimestamp(entry.timestamp) : 'Unknown time'}</span>
                    <span class={logLevelClass(entry.level)}>[{entry.level.toUpperCase()}]</span>
                    <span class="break-words">{entry.message}</span>
                  </div>
                {/each}
              </div>
            {:else}
              <p class="border border-[#34382d] bg-[#111312] p-4 text-sm text-muted-foreground">
                {selected.log_capture_error ?? 'No log entries were emitted during this run window.'}
              </p>
            {/if}
          </section>

          {#if selected.warnings.length > 0}
            <section class="ops-banner text-status-warn">
              <ul class="space-y-1">
                {#each selected.warnings as warning}<li>{warning}</li>{/each}
              </ul>
            </section>
          {/if}
        </div>
      {:else}
        <div class="flex min-h-[620px] items-center justify-center p-8 text-center text-muted-foreground">
          No run evidence is available for the current filters.
        </div>
      {/if}
    </div>
  </section>
</div>
