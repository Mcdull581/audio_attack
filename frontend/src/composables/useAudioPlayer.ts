/**
 * useAudioPlayer — Dual-track waveform player powered by wavesurfer.js v7.
 *
 * Manages two WaveSurfer instances (original + adversarial) with independent
 * play/pause controls. Adversarial track uses normalize + bar style.
 */
import { ref, onUnmounted } from 'vue';
import WaveSurfer from 'wavesurfer.js';
import type { WaveSurferOptions } from 'wavesurfer.js';
import { useAudioStore } from '@/stores/audioStore';

// ── Original track theme ────────────────────────────────────────────────
const ORIGINAL_THEME = {
  backgroundColor: '#0a0a0f',
  waveColor: '#06b6d4',
  progressColor: '#22d3ee',
  cursorColor: '#f97316',
  barWidth: 2,
  barGap: 1,
  barRadius: 2,
  height: 96,
  normalize: false,
} as const;

// ── Adversarial track theme ─────────────────────────────────────────────
const ADVERSARIAL_THEME = {
  backgroundColor: '#0a0a0f',
  waveColor: '#ef4444',
  progressColor: '#f87171',
  cursorColor: '#f97316',
  barWidth: 2,
  barGap: 1,
  barRadius: 2,
  height: 96,
  normalize: true,
} as const;

// ── Composable ───────────────────────────────────────────────────────────
export function useAudioPlayer() {
  const isReady = ref(false);
  const isPlayingOriginal = ref(false);
  const isPlayingAdversarial = ref(false);

  let originalWs: WaveSurfer | null = null;
  let adversarialWs: WaveSurfer | null = null;

  const audioStore = useAudioStore();

  // ── Initialization ────────────────────────────────────────────────────
  function initWaveforms(
    originalContainer: string,
    adversarialContainer: string,
    disableAdversarialNormalize: boolean = false,
  ): void {
    destroy();

    originalWs = WaveSurfer.create({
      container: originalContainer,
      ...ORIGINAL_THEME,
    });
    adversarialWs = WaveSurfer.create({
      container: adversarialContainer,
      ...ADVERSARIAL_THEME,
      normalize: disableAdversarialNormalize ? false : ADVERSARIAL_THEME.normalize,
    });

    // ── Per-track play/pause listeners ──────────────────────────────────
    originalWs.on('play', () => { isPlayingOriginal.value = true; });
    originalWs.on('pause', () => { isPlayingOriginal.value = false; });
    originalWs.on('finish', () => { isPlayingOriginal.value = false; });

    adversarialWs.on('play', () => { isPlayingAdversarial.value = true; });
    adversarialWs.on('pause', () => { isPlayingAdversarial.value = false; });
    adversarialWs.on('finish', () => { isPlayingAdversarial.value = false; });

    isReady.value = true;
  }

  // ── Loading ───────────────────────────────────────────────────────────
  async function loadOriginal(url: string): Promise<void> {
    if (!originalWs) return;
    await originalWs.load(url);
  }

  async function loadAdversarial(url: string): Promise<void> {
    if (!adversarialWs) return;
    await adversarialWs.load(url);
  }

  // ── Individual track controls ─────────────────────────────────────────
  function playOriginal(): void {
    originalWs?.play();
  }

  function pauseOriginal(): void {
    originalWs?.pause();
  }

  function toggleOriginal(): void {
    if (!originalWs) return;
    originalWs.playPause();
  }

  function playAdversarial(): void {
    adversarialWs?.play();
  }

  function pauseAdversarial(): void {
    adversarialWs?.pause();
  }

  function toggleAdversarial(): void {
    if (!adversarialWs) return;
    adversarialWs.playPause();
  }

  // ── Synchronized playback ─────────────────────────────────────────────
  function playBoth(): void {
    if (!originalWs || !adversarialWs) return;
    originalWs.setTime(0);
    adversarialWs.setTime(0);
    originalWs.play();
    adversarialWs.play();
  }

  function pauseBoth(): void {
    originalWs?.pause();
    adversarialWs?.pause();
  }

  // ── Cleanup ───────────────────────────────────────────────────────────
  function destroy(): void {
    if (originalWs) { originalWs.destroy(); originalWs = null; }
    if (adversarialWs) { adversarialWs.destroy(); adversarialWs = null; }
    isReady.value = false;
    isPlayingOriginal.value = false;
    isPlayingAdversarial.value = false;
  }

  onUnmounted(() => { destroy(); });

  return {
    isReady,
    isPlayingOriginal,
    isPlayingAdversarial,
    initWaveforms,
    loadOriginal,
    loadAdversarial,
    toggleOriginal,
    toggleAdversarial,
    playBoth,
    pauseBoth,
    destroy,
  };
}
