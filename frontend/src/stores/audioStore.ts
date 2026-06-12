/**
 * Pinia store for audio playback state and resource URLs.
 * Receives resource URLs from useWebSocket on attack_complete
 * and exposes sample metadata for the UI.
 *
 * Uses Composition API style (setup function).
 */

import { ref } from 'vue';
import { defineStore } from 'pinia';
import type { SampleInfo } from '@/types/attack';
import type { AttackResourceUrls } from '@/types/ws';

export const useAudioStore = defineStore('audio', () => {
  // ── State ──────────────────────────────────────────────────────────────

  const originalUrl = ref<string | null>(null);
  const adversarialUrl = ref<string | null>(null);
  const deltaUrl = ref<string | null>(null);
  const selectedSample = ref<SampleInfo | null>(null);
  const isPlaying = ref(false);

  // ── Actions ────────────────────────────────────────────────────────────

  function setResources(urls: AttackResourceUrls): void {
    originalUrl.value = urls.original_wav_url;
    adversarialUrl.value = urls.adversarial_wav_url;
    deltaUrl.value = urls.perturbation_wav_url;
  }

  function setSample(sample: SampleInfo): void {
    selectedSample.value = sample;
  }

  function togglePlay(): void {
    isPlaying.value = !isPlaying.value;
  }

  function reset(): void {
    originalUrl.value = null;
    adversarialUrl.value = null;
    deltaUrl.value = null;
    selectedSample.value = null;
    isPlaying.value = false;
  }

  // ── Public API ─────────────────────────────────────────────────────────

  return {
    // state
    originalUrl,
    adversarialUrl,
    deltaUrl,
    selectedSample,
    isPlaying,
    // actions
    setResources,
    setSample,
    togglePlay,
    reset,
  };
});
