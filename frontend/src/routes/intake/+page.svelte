<script lang="ts">
  import { api } from '$lib/api/client';
  import { notify } from '$lib/stores/notifications';
  import type { IntakeProfileResponse, IntakeReport, IntakeSearchResponse } from '$lib/types';
  import { Activity, Download, ExternalLink, FileClock, FlaskConical, Search } from 'lucide-svelte';

  let repoId = '';
  let report: IntakeReport | null = null;
  let selectedVariantName = '';
  let modelName = '';
  let profileName = 'Hugging Face Intake';
  let intent = 'Agent Fallback';
  let inspecting = false;
  let searchResults: IntakeSearchResponse | null = null;
  let creatingProfile = false;
  let pulling = false;
  let createdProfile: IntakeProfileResponse | null = null;
  let pullComplete = false;
  let errorMessage = '';

  $: selectedVariant = report?.variants.find((item) => item.name === selectedVariantName) ?? null;
  $: ggufSelected = selectedVariant?.format === 'gguf';

  async function inspect() {
    if (!repoId.trim()) return;
    if (!repoId.includes('/')) {
      await searchRepositories();
      return;
    }
    inspecting = true;
    errorMessage = '';
    report = null;
    searchResults = null;
    createdProfile = null;
    pullComplete = false;
    const result = await api.intake.inspect(repoId.trim());
    inspecting = false;
    if (!result.ok) {
      errorMessage = result.error;
      notify.error('Repository inspection failed', result.error);
      return;
    }
    report = result.data;
    modelName = result.data.suggested_model_name;
    selectedVariantName = result.data.recommended_variant ?? result.data.variants[0]?.name ?? '';
  }

  async function searchRepositories() {
    inspecting = true;
    errorMessage = '';
    report = null;
    searchResults = null;
    const result = await api.intake.search(repoId.trim());
    inspecting = false;
    if (!result.ok) {
      errorMessage = result.error;
      notify.error('Repository search failed', result.error);
      return;
    }
    searchResults = result.data;
  }

  async function selectCandidate(candidate: string) {
    repoId = candidate;
    await inspect();
  }

  async function createProfile() {
    if (!report || !selectedVariant) return;
    creatingProfile = true;
    const result = await api.intake.createProfile({
      repo_id: report.repo_id,
      model_name: modelName,
      variant_name: selectedVariant.name,
      variant_size_bytes: selectedVariant.size_bytes,
      profile_name: profileName,
      intent,
    });
    creatingProfile = false;
    if (!result.ok) {
      notify.error('Profile creation failed', result.error);
      return;
    }
    createdProfile = result.data;
    notify.success('Workflow profile created', `${result.data.profile_name} for ${result.data.model_name}`);
  }

  async function pullThroughLemonade() {
    if (!report || !selectedVariant || !ggufSelected) return;
    const checkpoint = `${report.repo_id}:${selectedVariant.name}`;
    if (!window.confirm(`Register and download ${modelName} through Lemonade?\n\nCheckpoint: ${checkpoint}\nThis can be a large download.`)) return;
    pulling = true;
    const labels = new Set(report.suggested_labels);
    const result = await api.intake.pull({
      model_name: modelName,
      checkpoint,
      recipe: 'llamacpp',
      vision: labels.has('vision'),
      embedding: labels.has('embeddings'),
      reranking: labels.has('reranking'),
      mmproj: labels.has('vision') ? report.mmproj_files[0] ?? null : null,
    });
    pulling = false;
    if (!result.ok || !result.data.success) {
      notify.error('Lemonade pull failed', result.ok ? result.data.message : result.error);
      return;
    }
    pullComplete = true;
    notify.success('Lemonade pull complete', result.data.message);
  }

  function formatBytes(value: number | null): string {
    return value === null ? 'unknown size' : `${(value / 1024 ** 3).toFixed(2)} GB`;
  }
</script>

<div class="space-y-6">
  <section class="ops-panel p-5">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end">
      <div class="min-w-0 flex-1">
        <h2 class="ops-title">Guided Hugging Face Intake</h2>
        <p class="ops-subtitle">Enter an exact owner/repository id, or a short name to resolve up to five GGUF candidates. Inspection never downloads.</p>
        <label class="ops-label mt-5 block" for="repo-id">Repository</label>
        <input id="repo-id" class="ops-input mt-2 w-full" bind:value={repoId} placeholder="owner/repository-GGUF" on:keydown={(event) => event.key === 'Enter' && inspect()} />
      </div>
      <button class="ops-button ops-button-primary" type="button" disabled={inspecting || !repoId.trim()} on:click={inspect}>
        <Search class="h-4 w-4 {inspecting ? 'animate-pulse' : ''}" /> {inspecting ? 'Working' : repoId.includes('/') ? 'Inspect repository' : 'Find repositories'}
      </button>
    </div>
  </section>

  {#if errorMessage}
    <section class="ops-panel border-status-danger p-5">
      <h3 class="ops-label text-status-danger">Request error</h3>
      <p class="mt-2 select-text break-words font-mono text-sm">{errorMessage}</p>
    </section>
  {/if}

  {#if searchResults}
    <section class="ops-panel p-5">
      <h3 class="ops-title">Repository candidates</h3>
      <p class="ops-subtitle">{searchResults.note} Popularity is not an endorsement; review the author, model card, and license.</p>
      <div class="mt-4 grid gap-2">
        {#each searchResults.results as candidate}
          <button class="flex items-center justify-between gap-3 border border-[#34382d] bg-[#111312] p-4 text-left hover:border-lemon" type="button" on:click={() => selectCandidate(candidate.repo_id)}>
            <span><strong class="ops-value">{candidate.repo_id}</strong>{#if candidate.gated}<span class="ops-badge ops-badge-warn ml-2">gated</span>{/if}</span>
            <span class="ops-muted text-xs">{candidate.downloads?.toLocaleString() ?? 'unknown'} downloads</span>
          </button>
        {/each}
        {#if searchResults.results.length === 0}<p class="ops-muted text-sm">No GGUF repository candidates found.</p>{/if}
      </div>
    </section>
  {/if}

  {#if report}
    <section class="ops-banner">
      <strong>Ownership boundary:</strong> {report.ownership_note}
    </section>

    <section class="grid gap-4 lg:grid-cols-2">
      {#each report.formats as format}
        <article class="ops-panel p-5">
          <div class="flex items-center justify-between gap-3">
            <h3 class="ops-title uppercase">{format.format}</h3>
            <span class="ops-badge {format.applicability === 'applicable' ? 'ops-badge-ok' : format.applicability === 'unsupported' ? '' : 'ops-badge-warn'}">{format.applicability}</span>
          </div>
          <p class="ops-muted mt-3 text-sm">{format.evidence}</p>
          <p class="mt-2 text-xs text-muted-foreground">Recipe: {format.recipe ?? 'unavailable'}</p>
        </article>
      {/each}
    </section>

    <section class="ops-panel p-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div><h3 class="ops-title">Variant and memory planning</h3><p class="ops-subtitle">Available RAM: {report.ram_available_gb.toFixed(2)} / {report.ram_total_gb.toFixed(2)} GB</p></div>
        <a class="ops-button" href={`https://huggingface.co/${report.repo_id}`} target="_blank" rel="noreferrer"><ExternalLink class="h-4 w-4" /> Model card</a>
      </div>
      <div class="mt-5 grid gap-3">
        {#each report.variants as variant}
          <label class="flex cursor-pointer items-start gap-3 border border-[#34382d] bg-[#111312] p-4">
            <input type="radio" name="variant" value={variant.name} bind:group={selectedVariantName} />
            <span class="min-w-0 flex-1">
              <span class="flex flex-wrap items-center gap-2"><strong class="ops-value">{variant.name}</strong><span class="ops-badge">{variant.format}</span><span class="ops-badge {variant.memory_risk === 'low' ? 'ops-badge-ok' : variant.memory_risk === 'high' ? 'ops-badge-danger' : 'ops-badge-warn'}">{variant.memory_risk} risk</span></span>
              <span class="ops-muted mt-2 block text-sm">{formatBytes(variant.size_bytes)} download · {variant.estimated_runtime_gb?.toFixed(2) ?? 'unknown'} GB estimated runtime</span>
              <span class="mt-1 block text-xs text-muted-foreground">{variant.estimate_note}</span>
            </span>
          </label>
        {/each}
      </div>
      {#if report.warnings.length}<ul class="mt-4 list-disc space-y-1 pl-5 text-sm text-status-warn">{#each report.warnings as warning}<li>{warning}</li>{/each}</ul>{/if}
    </section>

    {#if selectedVariant}
      <section class="ops-panel p-5">
        <h3 class="ops-title">Create the workflow memory</h3>
        <div class="mt-4 grid gap-4 md:grid-cols-3">
          <label><span class="ops-label">Lemonade registration name</span><input class="ops-input mt-2 w-full" bind:value={modelName} /><span class="mt-1 block text-xs text-muted-foreground">The linked profile uses the canonical inventory name without the user. prefix.</span></label>
          <label><span class="ops-label">Profile name</span><input class="ops-input mt-2 w-full" bind:value={profileName} /></label>
          <label><span class="ops-label">Intent</span><select class="ops-input mt-2 w-full" bind:value={intent}><option>Agent Fallback</option><option>Coding Fast</option><option>Coding Long Context</option><option>Review Heavy</option><option>Italian Writing</option><option>Stress Test</option></select></label>
        </div>
        <div class="mt-5 flex flex-wrap gap-2">
          <button class="ops-button ops-button-primary" type="button" disabled={creatingProfile || !modelName.startsWith('user.')} on:click={createProfile}><Activity class="h-4 w-4" /> {creatingProfile ? 'Creating' : 'Create profile'}</button>
          <button class="ops-button" type="button" disabled={pulling || !ggufSelected || !modelName.startsWith('user.')} on:click={pullThroughLemonade}><Download class="h-4 w-4" /> {pulling ? 'Lemonade downloading' : 'Pull through Lemonade'}</button>
        </div>
        {#if !ggufSelected}<p class="mt-3 text-sm text-status-warn">ONNX was detected, but direct pull is withheld because repository layout and OGA compatibility are not proven.</p>{/if}
      </section>
    {/if}

    {#if createdProfile || pullComplete}
      <section class="ops-panel p-5">
        <h3 class="ops-title">Follow-up workflow</h3>
        <p class="ops-subtitle">Load the installed model with the new profile, then capture a real Smoke Test or Bench Lab result.</p>
        <div class="mt-4 flex flex-wrap gap-2"><a class="ops-button ops-button-primary" href="/models"><Download class="h-4 w-4" /> Models</a><a class="ops-button" href="/evidence"><FileClock class="h-4 w-4" /> Run Evidence</a><a class="ops-button" href="/bench"><FlaskConical class="h-4 w-4" /> Bench Lab</a></div>
      </section>
    {/if}
  {/if}
</div>
