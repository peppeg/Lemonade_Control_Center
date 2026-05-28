<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { ArrowLeft, RefreshCw, Upload } from 'lucide-svelte';
  import ProfileCard from '$lib/components/profiles/ProfileCard.svelte';
  import ProfileEditor from '$lib/components/profiles/ProfileEditor.svelte';
  import SmartRecommendation from '$lib/components/profiles/SmartRecommendation.svelte';
  import {
    activeProfileId,
    applyAndLoadProfile,
    applyProfile,
    cloneProfile,
    createProfile,
    deleteProfile,
    exportProfile,
    importProfile,
    loadProfiles,
    modelProfiles,
    profilesError,
    profilesLoading,
    recommendation,
    setDefaultProfile,
    updateProfile,
  } from '$lib/stores/profiles';
  import type { Profile, ProfileConfig } from '$lib/types';

  $: modelName = $page.params.name ?? '';
  $: modelSizeGb = readModelSizeGb($page.url.searchParams.get('size'));

  let editingProfile: Profile | null = null;
  let cloneName = '';

  onMount(() => {
    if (modelName) loadProfiles(modelName, modelSizeGb);
  });

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
        Profiles store explicit runtime config and request defaults for this model. Apply writes runtime config when admin access is available; Apply & Load also sends a load request to Lemonade.
      </p>
    </div>
    <div class="flex flex-wrap gap-2">
      <button class="ops-button" type="button" on:click={() => loadProfiles(modelName, modelSizeGb)} disabled={$profilesLoading}>
        <RefreshCw class="h-4 w-4 {$profilesLoading ? 'animate-spin' : ''}" />
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
      <div class="flex items-center gap-2">
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
            on:applyLoad={() => applyAndLoadProfile(profile)}
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
