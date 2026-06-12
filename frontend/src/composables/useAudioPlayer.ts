/**
 * useAudioPlayer — Dual-track waveform player powered by wavesurfer.js v7.
 *
 * Manages two synchronized WaveSurfer instances (original + adversarial)
 * with dark-theme visuals. Exposes playBoth / pauseBoth for synchronized
 * playback and clean destroy on teardown.
 */

import { ref, onUnmounted } from 'vue';
import WaveSurfer from 'wavesurfer.js';
import type { WaveSurferOptions } from 'wavesurfer.js';
import { useAudioStore } from '@/stores/audioStore';

// ── Visual theme ─────────────────────────────────────────────────────────

const DARK_THEME = {
  backgroundColor: '#0a0a0f',
  waveColor: '#06b6d4', // cyan-500
  progressColor: '#22d3ee', // cyan-400
  cursorColor: '#f97316', // orange-500
  barWidth: 2,
  barGap: 1,
  barRadius: 2,
  height: 128,
} as const;

// ── WaveSurfer common options ────────────────────────────────────────────

function buildOptions(container: string): WaveSurferOptions {
  return {
    container,
    ...DARK_THEME,
  };
}

// ── Composable ───────────────────────────────────────────────────────────

export function useAudioPlayer() {
  const isReady = ref(false);
  const isPlaying = ref(false);

  let originalWs: WaveSurfer | null = null;
  let adversarialWs: WaveSurfer | null = null;

  const audioStore = useAudioStore();

  // ── Initialization ─────────────────────────────────────────────────────

  function initWaveforms(
    originalContainer: string,
    adversarialContainer: string,
  ): void {
    // Destroy any existing instances first (idempotent re-init)
    destroy();

    originalWs = WaveSurfer.create(buildOptions(originalContainer));
    adversarialWs = WaveSurfer.create(buildOptions(adversarialContainer));

    // Sync play state across both instances
    const onPlay = () => {
      isPlaying.value = true;
      audioStore.isPlaying = true;
    };
    const onPause = () => {
      isPlaying.value = false;
      audioStore.isPlaying = false;
    };
    const onFinish = () => {
      isPlaying.value = false;
      audioStore.isPlaying = false;
    };

    originalWs.on('play', onPlay);
    originalWs.on('pause', onPause);
    originalWs.on('finish', onFinish);

    isReady.value = true;
  }

  // ── Loading ────────────────────────────────────────────────────────────

  async function loadOriginal(url: string): Promise<void> {
    if (!originalWs) return;
    await originalWs.load(url);
  }

  async function loadAdversarial(url: string): Promise<void> {
    if (!adversarialWs) return;
    await adversarialWs.load(url);
  }

  // ── Synchronized playback ──────────────────────────────────────────────

  function playBoth(): void {
    if (!originalWs || !adversarialWs) return;

    // Seek both to zero for synchronized start
    originalWs.setTime(0);
    adversarialWs.setTime(0);

    originalWs.play();
    adversarialWs.play();
  }

  function pauseBoth(): void {
    originalWs?.pause();
    adversarialWs?.pause();
  }

  // ── Cleanup ────────────────────────────────────────────────────────────

  function destroy(): void {
    if (originalWs) {
      originalWs.destroy();
      originalWs = null;
    }
    if (adversarialWs) {
      adversarialWs.destroy();
      adversarialWs = null;
    }
    isReady.value = false;
    isPlaying.value = false;
  }

  onUnmounted(() => {
    destroy();
  });

  // ── Public API ─────────────────────────────────────────────────────────

  return {
    isReady,
    isPlaying,
    initWaveforms,
    loadOriginal,
    loadAdversarial,
    playBoth,
    pauseBoth,
    destroy,
  };
}
