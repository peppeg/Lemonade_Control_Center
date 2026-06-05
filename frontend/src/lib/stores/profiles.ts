import { get, writable } from 'svelte/store';
import { api } from '$lib/api/client';
import { loadModel } from '$lib/stores/models';
import { notify } from '$lib/stores/notifications';
import type { LemonadeSavedOptions, ModelProfiles, Profile, ProfileConfig, SmartRecommendation } from '$lib/types';

export const currentModelName = writable<string | null>(null);
export const modelProfiles = writable<ModelProfiles | null>(null);
export const recommendation = writable<SmartRecommendation | null>(null);
export const activeProfileId = writable<string | null>(null);
export const profilesLoading = writable(false);
export const profilesError = writable<string | null>(null);

export async function loadProfiles(modelName: string, modelSizeGb?: number | null): Promise<void> {
  profilesLoading.set(true);
  profilesError.set(null);
  currentModelName.set(modelName);

  const [profilesResult, recommendationResult] = await Promise.allSettled([
    api.profiles.list(modelName),
    api.profiles.recommendation(modelName, modelSizeGb),
  ]);

  if (profilesResult.status === 'fulfilled' && profilesResult.value.ok) {
    modelProfiles.set(profilesResult.value.data);
    activeProfileId.set(profilesResult.value.data.default_profile_id);
  } else {
    profilesError.set(
      profilesResult.status === 'fulfilled' && !profilesResult.value.ok
        ? profilesResult.value.error
        : 'Profiles request failed',
    );
  }

  if (recommendationResult.status === 'fulfilled' && recommendationResult.value.ok) {
    recommendation.set(recommendationResult.value.data);
  } else {
    recommendation.set(null);
  }

  profilesLoading.set(false);
}

export async function createProfile(input: {
  name: string;
  description?: string;
  icon?: string;
  config: ProfileConfig;
}): Promise<boolean> {
  const modelName = get(currentModelName);
  if (!modelName) return false;

  const result = await api.profiles.create(modelName, input);
  if (result.ok) {
    notify.success('Profile created', result.data.name, { href: `/models/${encodeURIComponent(modelName)}` });
    await loadProfiles(modelName);
    return true;
  }
  notify.error('Profile create failed', result.error);
  return false;
}

export async function updateProfile(profileId: string, input: {
  name?: string;
  description?: string;
  icon?: string;
  config?: ProfileConfig;
  is_default?: boolean;
}): Promise<boolean> {
  const modelName = get(currentModelName);
  if (!modelName) return false;

  const result = await api.profiles.update(modelName, profileId, input);
  if (result.ok) {
    notify.success('Profile updated', result.data.name, { href: `/models/${encodeURIComponent(modelName)}` });
    await loadProfiles(modelName);
    return true;
  }
  notify.error('Profile update failed', result.error);
  return false;
}

export async function deleteProfile(profileId: string): Promise<boolean> {
  const modelName = get(currentModelName);
  if (!modelName) return false;

  const result = await api.profiles.delete(modelName, profileId);
  if (result.ok) {
    notify.success('Profile deleted', profileId, { href: `/models/${encodeURIComponent(modelName)}` });
    await loadProfiles(modelName);
    return true;
  }
  notify.error('Profile delete failed', result.error);
  return false;
}

export async function cloneProfile(profileId: string, newName: string): Promise<boolean> {
  const modelName = get(currentModelName);
  if (!modelName) return false;

  const result = await api.profiles.clone(modelName, profileId, newName);
  if (result.ok) {
    notify.success('Profile cloned', result.data.name, { href: `/models/${encodeURIComponent(modelName)}` });
    await loadProfiles(modelName);
    return true;
  }
  notify.error('Profile clone failed', result.error);
  return false;
}

export async function setDefaultProfile(profileId: string): Promise<boolean> {
  const modelName = get(currentModelName);
  if (!modelName) return false;

  const result = await api.profiles.setDefault(modelName, profileId);
  if (result.ok) {
    notify.info('Default profile set', profileId, { toastDuration: 2500 });
    await loadProfiles(modelName);
    return true;
  }
  notify.error('Default update failed', result.error);
  return false;
}

export async function exportProfile(profileId: string): Promise<void> {
  const modelName = get(currentModelName);
  if (!modelName) return;

  const result = await api.profiles.export(modelName, profileId);
  if (!result.ok) {
    notify.error('Profile export failed', result.error);
    return;
  }

  const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `lcc-profile-${profileId}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
  notify.success('Profile exported', profileId, { toastDuration: 2500 });
}

export async function importProfile(file: File): Promise<boolean> {
  const modelName = get(currentModelName);
  if (!modelName) return false;

  try {
    const parsed = JSON.parse(await file.text()) as Record<string, unknown>;
    const result = await api.profiles.importProfile(modelName, parsed);
    if (result.ok) {
      notify.success('Profile imported', result.data.name, { href: `/models/${encodeURIComponent(modelName)}` });
      await loadProfiles(modelName);
      return true;
    }
    notify.error('Profile import failed', result.error);
  } catch {
    notify.error('Profile import failed', 'The selected file is not valid JSON.');
  }
  return false;
}

export async function applyProfile(profile: Profile): Promise<boolean> {
  const modelName = get(currentModelName);
  if (!modelName) return false;

  const runtimeUpdates: Record<string, unknown> = {};
  if (profile.config.ctx_size !== null) runtimeUpdates.ctx_size = profile.config.ctx_size;
  if (profile.config.global_timeout !== null) runtimeUpdates.global_timeout = profile.config.global_timeout;
  if (profile.config.llamacpp_backend) runtimeUpdates.llamacpp_backend = profile.config.llamacpp_backend;

  const requestDefaults = {
    maxOutputTokens: profile.config.max_tokens,
    temperature: profile.config.temperature,
    appTimeoutSeconds: profile.config.app_timeout,
    stopSequences: parseStopSequences(profile.config.stop_sequences),
    activePreset: profile.name,
  };
  localStorage.setItem('lcc.requestDefaults', JSON.stringify(requestDefaults));

  if (Object.keys(runtimeUpdates).length === 0) {
    activeProfileId.set(profile.id);
    notify.info('Profile applied locally', profile.name, { href: `/models/${encodeURIComponent(modelName)}` });
    return true;
  }

  const result = await api.lemonade.setConfig(runtimeUpdates);
  activeProfileId.set(profile.id);
  if (result.ok) {
    notify.success('Profile applied', profile.name, { href: `/models/${encodeURIComponent(modelName)}` });
    return true;
  }

  notify.warning('Profile partially applied', `Local defaults saved. Runtime config failed: ${result.error}`, {
    href: '/config',
  });
  return false;
}

export async function applyAndLoadProfile(profile: Profile, saveOptions = false): Promise<boolean> {
  await applyProfile(profile);
  const success = await loadModel({
    modelName: get(currentModelName) ?? '',
    ctxSize: profile.config.ctx_size,
    llamacppBackend: profile.config.llamacpp_backend,
    llamacppArgs: profile.config.llamacpp_args ?? '',
    mergeArgs: true,
    saveOptions,
  });
  if (success && saveOptions) {
    notify.success('Lemonade defaults saved', profile.name, { href: `/models/${encodeURIComponent(get(currentModelName) ?? '')}` });
  }
  return success;
}

export async function importFromLemonadeSavedOptions(savedOptions: LemonadeSavedOptions): Promise<boolean> {
  const modelName = get(currentModelName);
  const options = savedOptions.selected_options;
  if (!modelName || !options) return false;

  return createProfile({
    name: 'Lemonade Defaults',
    description: `Imported from Lemonade saved options (${savedOptions.selected_key ?? 'recipe_options.json'}).`,
    icon: 'lemonade',
    config: {
      ctx_size: numberOrNull(options.ctx_size),
      global_timeout: numberOrNull(options.global_timeout),
      llamacpp_backend: stringOrNull(options.llamacpp_backend ?? options.llamacpp),
      llamacpp_args: stringOrNull(options.llamacpp_args),
      max_tokens: numberOrNull(options.max_tokens),
      temperature: numberOrNull(options.temperature),
      app_timeout: null,
      stop_sequences: null,
    },
  });
}

function parseStopSequences(value: string | null): string[] {
  if (!value) return [];
  return value.split('\n').map((item) => item.trim()).filter(Boolean);
}

function numberOrNull(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}
