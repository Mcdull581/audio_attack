<template>
  <div class="bg-dark-800 rounded-lg border border-dark-600 p-4">
    <!-- Header row: play/pause + title -->
    <div class="flex items-center gap-3 mb-3">
      <button
        class="flex items-center justify-center w-8 h-8 rounded-md transition-colors"
        :class="
          hasAudio
            ? 'bg-dark-700 hover:bg-dark-600 text-gray-200 cursor-pointer'
            : 'bg-dark-700/50 text-gray-600 cursor-not-allowed'
        "
        :disabled="!hasAudio"
        :aria-label="isPlaying ? 'Pause' : 'Play'"
        @click="togglePlayback"
      >
        <span class="text-sm leading-none">{{ isPlaying ? '⏸' : '▶' }}</span>
      </button>
      <span class="text-xs font-semibold text-gray-300 uppercase tracking-wider">
        Waveform Comparison
      </span>
    </div>

    <!-- Empty state -->
    <div
      v-if="!hasAudio"
      class="flex flex-col items-center justify-center gap-2 py-10 text-gray-500"
    >
      <svg
        class="w-10 h-10 opacity-40"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      >
        <path d="M3 12h2m4-8v16m4-14v12m4-10v8m4-4v0" stroke-linecap="round" />
      </svg>
      <span class="text-sm font-mono">No audio loaded</span>
    </div>

    <!-- Waveform containers -->
    <template v-if="hasAudio">
      <!-- Original -->
      <div class="mb-2">
        <span class="text-[10px] font-mono text-gray-400 uppercase tracking-wider">
          Original
        </span>
        <div
          id="waveform-original"
          class="w-full rounded-sm overflow-hidden"
          style="height: 90px"
        ></div>
      </div>

      <!-- Adversarial -->
      <div>
        <span class="text-[10px] font-mono text-red-400 uppercase tracking-wider">
          Adversarial
        </span>
        <div
          id="waveform-adversarial"
          class="w-full rounded-sm overflow-hidden"
          style="height: 90px"
        ></div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useAudioStore } from '@/stores/audioStore'
import { useAudioPlayer } from '@/composables/useAudioPlayer'

const audioStore = useAudioStore()
const { initWaveforms, loadOriginal, loadAdversarial, playBoth, pauseBoth, destroy, isReady, isPlaying } =
  useAudioPlayer()

// ── Derived state ────────────────────────────────────────────────────────

const hasAudio = computed(() => !!audioStore.originalUrl && !!audioStore.adversarialUrl)

// ── Playback toggle ──────────────────────────────────────────────────────

function togglePlayback(): void {
  if (!hasAudio.value) return
  if (isPlaying.value) {
    pauseBoth()
  } else {
    playBoth()
  }
}

// ── Initialize wavesurfer on mount ───────────────────────────────────────

onMounted(() => {
  initWaveforms('#waveform-original', '#waveform-adversarial')
})

// ── Load audio when URLs change ──────────────────────────────────────────

watch(
  () => audioStore.originalUrl,
  (url) => {
    if (url && isReady.value) {
      loadOriginal(url)
    }
  },
)

watch(
  () => audioStore.adversarialUrl,
  (url) => {
    if (url && isReady.value) {
      loadAdversarial(url)
    }
  },
)

// ── Cleanup on unmount ───────────────────────────────────────────────────

onUnmounted(() => {
  destroy()
})
</script>
