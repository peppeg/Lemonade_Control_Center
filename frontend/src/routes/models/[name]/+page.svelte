<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { ArrowLeft, RefreshCw, Upload } from 'lucide-svelte';
  import ProfileCard from '$lib/components/profiles/ProfileCard.svelte';
  import ProfileEditor from '$lib/components/profiles/ProfileEditor.svelte';
  import LemonadeSavedOptions from '$lib/components/profiles/LemonadeSavedOptions.svelte';
  import SmartRecommendation from '$lib/components/profiles/SmartRecommendation.svelte';
  import { api } from '$lib/api/client';
  import {
    activeProfileId,
    applyAndLoadProfile,
    applyProfile,
    cloneProfile,
    createProfile,
    deleteProfile,
    exportProfile,
    importFromLemonadeSavedOptions,
    importProfile,
    loadProfiles,
    modelProfiles,
    profilesError,
    profilesLoading,
    recommendation,
    setDefaultProfile,
    updateProfile,
  } from '$lib/stores/profiles';
  import type { LemonadeSavedOptions as LemonadeSavedOptionsData, Profile, ProfileConfig } from '$lib/types';

  $: modelName = $page.params.name ?? '';
  $: modelSizeGb = readModelSizeGb($page.url.searchParams.get('size'));

  let editingProfile: Profile | null = null;
  let cloneName = '';
  let savedOptions: LemonadeSavedOptionsData | null = null;
  let savedOptionsLoading = true;
  let saveApplyLoadToLemonade = false;

  onMount(() => {
    if (modelName) {
      loadProfiles(modelName, modelSizeGb);
      loadSavedOptions();
    }
  });

  async function refreshAll() {
    await Promise.all([
      loadProfiles(modelName, modelSizeGb),
      loadSavedOptions(),
    ]);
  }

  async function loadSavedOptions() {
    savedOptionsLoading = true;
    const result = await api.lemonade.savedOptions(modelName);
    savedOptions = result.ok
      ? result.data
      : {
          available: false,
          path: '',
          options: {},
          model_name: modelName,
          selected_key: null,
          selected_options: null,
          error: result.error,
        };
    savedOptionsLoading = false;
  }

  async function handleCreate(event: CustomEvent<{ name: string; description: string; icon: string; config: ProfileConfig }>) {
    await createProfile(event.detail);
  }

  async function handleUpdate(event: CustomEvent<{ name: string; description: string; icon: string; config: ProfileConfig }>) {
    if (!editingProfile) return;
    const ok = await updateProfile(editingProfile.id, event.detail);
    if (ok) editingProfile = null;
  }

  async function handleClone(profile: Profile) {
    const name = cloneName.trim() || `${profile.name} Copy`;
    cloneName = '';
    await cloneProfile(profile.id, name);
  }

  async function handleImport(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (file) await importProfile(file);
    input.value = '';
  }

  async function handleImportSavedOptions() {
    if (!savedOptions?.selected_options) return;
    await importFromLemonadeSavedOptions(savedOptions);
  }

  async function handleSaveToLemonade(profile: Profile) {
    const confirmed = window.confirm(
      `Save "${profile.name}" as Lemonade defaults for ${modelName}?\n\n` +
      'This will load the model through Lemonade and persist the profile runtime options to recipe_options.json.',
    );
    if (!confirmed) return;
    await applyAndLoadProfile(profile, true);
    await loadSavedOptions();
  }

  function readModelSizeGb(raw: string | null): number | null {
    if (!raw) return null;
    const bytes = Number(raw);
    if (!Number.isFinite(bytes) || bytes <= 0) return null;
    return bytes / (1024 ** 3);
  }
</script>

<div class="space-y-5">
  <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
    <div class="min-w-0">
      <a class="mb-4 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground" href="/models">
        <ArrowLeft class="h-4 w-4" />
        Back to Models
      </a>
      <h1 class="break-all text-3xl font-bold">Profiles: {modelName}</h1>
      <p class="mt-2 max-w-3xl text-sm text-muted-foreground">
        Profiles store explicit runtime config and LCC workflow defaults for this model. Apply writes runtime config when admin access is available; Apply & Load also sends a load request to Lemonade.
      </p>
    </div>
    <div class="flex flex-wrap gap-2">
      <button class="ops-button" type="button" on:click={refreshAll} disabled={$profilesLoading || savedOptionsLoading}>
        <RefreshCw class="h-4 w-4 {$profilesLoading || savedOptionsLoading ? 'animate-spin' : ''}" />
        Refresh
      </button>
      <label class="ops-button cursor-pointer">
        <Upload class="h-4 w-4" />
        Import
        <input class="hidden" type="file" accept="application/json,.json" on:change={handleImport} />
      </label>
    </div>
  </div>

  {#if $profilesError}
    <section class="ops-banner ops-banner-danger">{$profilesError}</section>
  {/if}

  {#if $recommendation}
    <SmartRecommendation data={$recommendation} />
  {/if}

  <LemonadeSavedOptions
    data={savedOptions}
    loading={savedOptionsLoading}
    on:importOptions={handleImportSavedOptions}
  />

  {#if editingProfile}
    <ProfileEditor profile={editingProfile} submitLabel="Update Profile" on:save={handleUpdate} on:cancel={() => editingProfile = null} />
  {:else}
    <ProfileEditor submitLabel="Create Profile" on:save={handleCreate} />
  {/if}

  <section class="ops-panel">
    <div class="ops-card-header">
      <div>
        <h2 class="ops-title">Model Profiles</h2>
        <p class="ops-subtitle">Built-in profiles are fixed. Clone one to create a custom editable variant.</p>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <label class="flex items-center gap-2 text-xs text-muted-foreground">
          <input type="checkbox" bind:checked={saveApplyLoadToLemonade} />
          Save Apply & Load to Lemonade defaults
        </label>
        <input class="ops-input max-w-56" bind:value={cloneName} placeholder="Clone name..." />
      </div>
    </div>

    <div class="space-y-4 p-5">
      {#if $profilesLoading && !$modelProfiles}
        <p class="text-sm text-muted-foreground">Loading profiles...</p>
      {:else if !$modelProfiles || $modelProfiles.profiles.length === 0}
        <p class="text-sm text-muted-foreground">No profiles available.</p>
      {:else}
        {#each $modelProfiles.profiles as profile (profile.id)}
          <ProfileCard
            {profile}
            active={$activeProfileId === profile.id}
            on:apply={() => applyProfile(profile)}
            on:applyLoad={() => applyAndLoadProfile(profile, saveApplyLoadToLemonade)}
            on:saveLemonade={() => handleSaveToLemonade(profile)}
            on:edit={() => editingProfile = profile}
            on:clone={() => handleClone(profile)}
            on:export={() => exportProfile(profile.id)}
            on:delete={() => deleteProfile(profile.id)}
            on:default={() => setDefaultProfile(profile.id)}
          />
        {/each}
      {/if}
    </div>
  </section>
</div>
