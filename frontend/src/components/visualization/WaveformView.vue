<template>
  <div class="bg-dark-800 rounded-lg border border-dark-600">
    <!-- Selected Sample Info Bar -->
    <div
      v-if="audioStore.selectedSample"
      class="flex items-center gap-3 px-4 py-2.5 border-b border-dark-600 bg-dark-700/50"
    >
      <!-- Preview play button -->
      <button
        class="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-md transition-colors"
        :class="isPlaying ? 'bg-accent-cyan text-dark-900' : 'bg-dark-600 hover:bg-dark-500 text-accent-cyan'"
        :aria-label="isPlaying ? 'Pause' : 'Play preview'"
        @click="togglePlayback"
      >
        <span class="text-xs">{{ isPlaying ? '⏸' : '▶' }}</span>
      </button>

      <!-- Sample name + transcription -->
      <div class="flex-1 min-w-0">
        <p class="text-sm font-mono text-accent-cyan truncate">
          {{ audioStore.selectedSample.name }}
        </p>
        <p
          class="text-xs text-gray-400 truncate font-mono"
          :title="audioStore.selectedSample.transcription || 'No transcription available'"
        >
          {{ audioStore.selectedSample.transcription || 'No transcription available' }}
        </p>
      </div>

      <!-- Duration badge -->
      <span class="flex-shrink-0 text-xs bg-dark-600 px-2 py-0.5 rounded font-mono text-gray-300">
        {{ formatDuration(audioStore.selectedSample.duration_sec) }}
      </span>
    </div>

    <!-- No sample selected -->
    <div
      v-else
      class="flex items-center gap-3 px-4 py-2.5 border-b border-dark-600 bg-dark-700/50"
    >
      <span class="text-xs text-gray-500 font-mono">
        Select an audio sample to preview waveform
      </span>
    </div>

    <!-- Waveform track: Original -->
    <div class="p-4 pb-2">
      <div class="flex items-center gap-2 mb-2">
        <span class="text-[11px] font-mono text-gray-400 uppercase tracking-wider">Original</span>
        <span v-if="!hasOriginal" class="text-[10px] text-gray-500 font-mono">— waiting for selection</span>
      </div>
      <div
        id="waveform-original"
        class="w-full rounded-sm overflow-hidden"
        :class="hasOriginal ? 'opacity-100' : 'opacity-30'"
        style="height: 90px"
      ></div>
    </div>

    <!-- Waveform track: Adversarial -->
    <div class="px-4 pb-4">
      <div class="flex items-center gap-2 mb-2">
        <span class="text-[11px] font-mono text-red-400 uppercase tracking-wider">Adversarial</span>
        <span v-if="!hasAdversarial" class="text-[10px] text-gray-500 font-mono">— appears after attack completes</span>
      </div>
      <div
        id="waveform-adversarial"
        class="w-full rounded-sm overflow-hidden"
        :class="hasAdversarial ? 'opacity-100' : 'opacity-30'"
        style="height: 90px"
      ></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useAudioStore } from '@/stores/audioStore'
import { useAudioPlayer } from '@/composables/useAudioPlayer'

const audioStore = useAudioStore()
const { initWaveforms, loadOriginal, loadAdversarial, playBoth, pauseBoth, destroy, isReady, isPlaying } =
  useAudioPlayer()

// ── Split audio state ─────────────────────────────────────────────────
const hasOriginal = computed(() => !!audioStore.originalUrl)
const hasAdversarial = computed(() => !!audioStore.adversarialUrl)

// ── Helpers ───────────────────────────────────────────────────────────
function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ── Playback ──────────────────────────────────────────────────────────
function togglePlayback(): void {
  if (isPlaying.value) {
    pauseBoth()
  } else {
    playBoth()
  }
}

// ── Initialize wavesurfer ─────────────────────────────────────────────
onMounted(() => {
  initWaveforms('#waveform-original', '#waveform-adversarial')
})

// ── Watch: load original when sample selected ─────────────────────────
watch(
  () => audioStore.originalUrl,
  (url) => {
    if (url && isReady.value) {
      loadOriginal(url)
    }
  },
  { immediate: false },
)

// ── Watch: load adversarial when attack completes ─────────────────────
watch(
  () => audioStore.adversarialUrl,
  (url) => {
    if (url && isReady.value) {
      loadAdversarial(url)
    }
  },
  { immediate: false },
)

// ── Cleanup ───────────────────────────────────────────────────────────
onUnmounted(() => {
  destroy()
})
</script>
