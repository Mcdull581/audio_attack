<template>
  <div class="bg-dark-800 rounded-lg border border-dark-600 flex flex-col h-full">
    <div class="flex-shrink-0 px-4 py-2 border-b border-dark-600 flex items-center gap-3">
      <span class="text-xs font-semibold text-gray-300 uppercase tracking-wider">Spectrogram Comparison</span>
      <span v-if="!hasOriginal" class="text-[10px] text-gray-500 font-mono">— select a sample</span>
      <span v-else-if="!hasAdversarial" class="text-[10px] text-yellow-400 font-mono">— awaiting attack</span>
    </div>

    <div class="flex-1 flex flex-col min-h-0">
      <!-- Original Spectrogram -->
      <div class="flex-1 flex flex-col min-h-0">
        <span class="text-[10px] font-mono text-gray-400 uppercase tracking-wider px-4 pt-2 flex-shrink-0">Original</span>
        <div id="spec-original" class="flex-1 w-full min-h-0 bg-[#0a0a0f] rounded-sm mx-4 my-1 overflow-hidden"></div>
      </div>

      <!-- Adversarial Spectrogram -->
      <div class="flex-1 flex flex-col min-h-0">
        <span class="text-[10px] font-mono text-red-400 uppercase tracking-wider px-4 pt-2 flex-shrink-0">Adversarial</span>
        <div id="spec-adversarial" class="flex-1 w-full min-h-0 bg-[#0a0a0f] rounded-sm mx-4 mb-2 overflow-hidden"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch, ref } from 'vue'
import { useAudioStore } from '@/stores/audioStore'
import WaveSurfer from 'wavesurfer.js'
import Spectrogram from 'wavesurfer.js/dist/plugins/spectrogram.js'

const audioStore = useAudioStore()

let originalWs: WaveSurfer | null = null
let adversarialWs: WaveSurfer | null = null
const hasOriginal = ref(false)
const hasAdversarial = ref(false)

function createSpecOnly(container: string): WaveSurfer {
  return WaveSurfer.create({
    container,
    waveColor: 'transparent',
    progressColor: 'transparent',
    cursorColor: 'transparent',
    cursorWidth: 0,
    height: 200,
    normalize: true,
    barWidth: 0,
    barGap: 0,
    plugins: [
      Spectrogram.create({
        labels: true,
        labelsBackground: '#0a0a0f',
        labelsColor: '#6b7280',
        labelsHzColor: '#9ca3af',
        height: 200,
        splitChannels: false,
        fftSamples: 1024,
        frequencyMax: 8000,
        frequencyMin: 0,
      }),
    ],
  })
}

onMounted(() => {
  originalWs = createSpecOnly('#spec-original')
  adversarialWs = createSpecOnly('#spec-adversarial')
})

async function loadOriginalTrack(): Promise<void> {
  if (audioStore.originalUrl && originalWs) {
    await originalWs.load(audioStore.originalUrl)
    hasOriginal.value = true
  }
}

async function loadAdversarialTrack(): Promise<void> {
  if (audioStore.adversarialUrl && adversarialWs) {
    await adversarialWs.load(audioStore.adversarialUrl)
    hasAdversarial.value = true
  }
}

watch(() => audioStore.originalUrl, () => loadOriginalTrack())
watch(() => audioStore.adversarialUrl, () => loadAdversarialTrack())

onUnmounted(() => {
  originalWs?.destroy()
  adversarialWs?.destroy()
})
</script>

<style scoped>
/* Force spectrogram canvases to transparent — kill the white blocks */
#spec-original canvas,
#spec-adversarial canvas,
#spec-original :deep(canvas),
#spec-adversarial :deep(canvas) {
  background-color: transparent !important;
}
</style>
