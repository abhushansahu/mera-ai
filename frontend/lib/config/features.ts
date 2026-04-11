import { chatApi } from '@/lib/api/client';

export type FeatureFlags = {
  threading: boolean;
  perMessageModel: boolean;
  secureProviderSettings: boolean;
  obsidianAdvanced: boolean;
  rpiCompactLayout: boolean;
  obsidianEventSync: boolean;
};

const envFeatureFlags: FeatureFlags = {
  threading: process.env.NEXT_PUBLIC_FEATURE_THREADING !== 'false',
  perMessageModel: process.env.NEXT_PUBLIC_FEATURE_PER_MESSAGE_MODEL !== 'false',
  secureProviderSettings: process.env.NEXT_PUBLIC_FEATURE_SECURE_PROVIDER_SETTINGS !== 'false',
  obsidianAdvanced: process.env.NEXT_PUBLIC_FEATURE_OBSIDIAN_ADVANCED !== 'false',
  rpiCompactLayout: process.env.NEXT_PUBLIC_FEATURE_RPI_COMPACT_LAYOUT !== 'false',
  obsidianEventSync: process.env.NEXT_PUBLIC_FEATURE_OBSIDIAN_EVENT_SYNC !== 'false',
};

const runtimeFeatureFlags: FeatureFlags = { ...envFeatureFlags };

export const featureFlags = runtimeFeatureFlags;

export function getFeatureFlags(): FeatureFlags {
  return runtimeFeatureFlags;
}

export async function hydrateFeatureFlags(): Promise<FeatureFlags> {
  try {
    const remote = await chatApi.getFeatureFlags();
    Object.assign(runtimeFeatureFlags, {
      threading: remote.threading,
      perMessageModel: remote.per_message_model,
      secureProviderSettings: remote.secure_provider_settings,
      obsidianAdvanced: remote.obsidian_advanced,
      rpiCompactLayout: remote.rpi_compact_layout,
      obsidianEventSync: remote.obsidian_event_sync,
    });
    return runtimeFeatureFlags;
  } catch {
    Object.assign(runtimeFeatureFlags, envFeatureFlags);
    return runtimeFeatureFlags;
  }
}

