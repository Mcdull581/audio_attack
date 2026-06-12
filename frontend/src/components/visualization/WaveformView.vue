<template>
  <div class="bg-dark-800 rounded-lg border border-dark-600">
    <!-- Selected Sample Info Bar -->
    <div
      v-if="audioStore.selectedSample"
      class="flex items-center gap-3 px-4 py-2.5 border-b border-dark-600 bg-dark-700/50"
    >
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
      <span class="flex-shrink-0 text-xs bg-dark-600 px-2 py-0.5 rounded font-mono text-gray-300">
        {{ formatDuration(audioStore.selectedSample.duration_sec) }}
      </span>
    </div>
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
        <button
          class="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded text-xs transition-colors"
          :class="hasOriginal
            ? (isPlayingOriginal ? 'bg-accent-cyan text-dark-900' : 'bg-dark-600 hover:bg-dark-500 text-accent-cyan')
            : 'bg-dark-700/50 text-gray-600 cursor-not-allowed'"
          :disabled="!hasOriginal"
          :aria-label="isPlayingOriginal ? 'Pause Original' : 'Play Original'"
          @click="toggleOriginal"
        >
          {{ isPlayingOriginal ? '⏸' : '▶' }}
        </button>
        <span class="text-[11px] font-mono text-gray-400 uppercase tracking-wider">Original</span>
        <span v-if="!hasOriginal" class="text-[10px] text-gray-500 font-mono">— select a sample</span>
      </div>
      <div
        id="waveform-original"
        class="w-full rounded-sm overflow-hidden relative h-24"
        :class="hasOriginal ? 'opacity-100' : 'opacity-30'"
      ></div>
    </div>

    <!-- Waveform track: Adversarial -->
    <div class="px-4 pb-4">
      <div class="flex items-center gap-2 mb-2">
        <button
          class="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded text-xs transition-colors"
          :class="hasAdversarial
            ? (isPlayingAdversarial ? 'bg-red-500 text-white' : 'bg-dark-600 hover:bg-dark-500 text-red-400')
            : 'bg-dark-700/50 text-gray-600 cursor-not-allowed'"
          :disabled="!hasAdversarial"
          :aria-label="isPlayingAdversarial ? 'Pause Adversarial' : 'Play Adversarial'"
          @click="toggleAdversarial"
        >
          {{ isPlayingAdversarial ? '⏸' : '▶' }}
        </button>
        <span class="text-[11px] font-mono text-red-400 uppercase tracking-wider">Adversarial</span>
        <!-- Sync Scale toggle -->
        <button
          v-if="hasAdversarial"
          class="ml-auto text-[10px] font-mono px-2 py-0.5 rounded border transition-colors"
          :class="syncScale ? 'bg-accent-cyan/20 border-accent-cyan/40 text-accent-cyan' : 'bg-dark-700 border-dark-600 text-gray-500 hover:text-gray-300'"
          @click="toggleSyncScale"
        >
          Sync Scale
        </button>
        <span v-if="!hasAdversarial" class="text-[10px] text-gray-500 font-mono">— after attack completes</span>
      </div>
      <div
        id="waveform-adversarial"
        class="w-full rounded-sm overflow-hidden relative h-24"
        :class="hasAdversarial ? 'opacity-100' : 'opacity-30'"
      ></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch, ref } from 'vue'
import { useAudioStore } from '@/stores/audioStore'
import { useAudioPlayer } from '@/composables/useAudioPlayer'

const audioStore = useAudioStore()
const {
  initWaveforms, loadOriginal, loadAdversarial,
  toggleOriginal, toggleAdversarial,
  isReady, isPlayingOriginal, isPlayingAdversarial,
  destroy,
} = useAudioPlayer()

const hasOriginal = computed(() => !!audioStore.originalUrl)
const hasAdversarial = computed(() => !!audioStore.adversarialUrl)
const syncScale = ref(false)

function toggleSyncScale(): void {
  syncScale.value = !syncScale.value
  // Re-init adversarial with toggled normalize
  if (hasAdversarial.value) {
    initWaveforms('#waveform-original', '#waveform-adversarial', syncScale.value)
    if (audioStore.originalUrl) loadOriginal(audioStore.originalUrl)
    if (audioStore.adversarialUrl) loadAdversarial(audioStore.adversarialUrl)
  }
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

onMounted(() => {
  initWaveforms('#waveform-original', '#waveform-adversarial')
})

watch(() => audioStore.originalUrl, (url) => {
  if (url && isReady.value) loadOriginal(url)
})

watch(() => audioStore.adversarialUrl, (url) => {
  if (url && isReady.value) loadAdversarial(url)
})

onUnmounted(() => { destroy() })
</script>
