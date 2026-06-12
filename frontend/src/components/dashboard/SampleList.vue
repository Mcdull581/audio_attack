<template>
  <div class="bg-dark-800 rounded-lg border border-dark-600 overflow-hidden">
    <div class="px-4 py-3 border-b border-dark-600 flex items-center justify-between">
      <h3 class="text-sm uppercase tracking-wider text-gray-400 font-mono">
        Audio Samples
        <span v-if="samples.length > 0" class="ml-2 px-1.5 py-0.5 text-xs bg-dark-600 rounded text-gray-300">
          {{ samples.length }}
        </span>
      </h3>
    </div>

    <div class="max-h-[300px] overflow-y-auto">
      <div v-if="loading" class="p-4 space-y-3">
        <div v-for="n in 3" :key="n" class="h-10 bg-dark-700 rounded animate-pulse" />
      </div>

      <div v-else-if="samples.length === 0" class="p-6 text-center">
        <p class="text-sm text-gray-500 font-mono">No samples loaded.</p>
      </div>

      <template v-else>
        <button
          v-for="sample in samples"
          :key="sample.name"
          class="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-all duration-150"
          :class="selectedSample?.name === sample.name
            ? 'border-l-4 border-accent-cyan bg-dark-700 shadow-inner'
            : 'border-l-4 border-transparent hover:bg-dark-700/50'"
          @click="handleSelect(sample)"
        >
          <span
            class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded text-xs transition-colors"
            :class="selectedSample?.name === sample.name
              ? 'bg-accent-cyan/20 text-accent-cyan'
              : 'bg-dark-600 text-gray-400 hover:bg-dark-500 hover:text-accent-cyan'"
            @click.stop="handlePlay(sample)"
          >
            ▶
          </span>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-mono truncate"
              :class="selectedSample?.name === sample.name ? 'text-accent-cyan' : 'text-gray-200'">
              {{ sample.name }}
            </p>
            <p class="text-xs truncate"
              :class="selectedSample?.name === sample.name ? 'text-gray-400' : 'text-gray-500'">
              {{ sample.transcription || '—' }}
            </p>
          </div>
          <span class="flex-shrink-0 text-xs px-2 py-0.5 rounded font-mono"
            :class="selectedSample?.name === sample.name ? 'bg-accent-cyan/20 text-accent-cyan' : 'bg-dark-600 text-gray-300'">
            {{ formatDuration(sample.duration_sec) }}
          </span>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useAudioStore } from '@/stores/audioStore'
import { fetchSamples } from '@/utils/api'
import { transcribeSample } from '@/utils/api'
import type { SampleInfo } from '@/types/attack'

const audioStore = useAudioStore()
const { selectedSample } = storeToRefs(audioStore)

const samples = ref<SampleInfo[]>([])
const loading = ref(false)

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

async function loadSamples(): Promise<void> {
  loading.value = true
  try { const res = await fetchSamples(); samples.value = res.samples } catch { /* keep existing */ }
  finally { loading.value = false }
}

function handleSelect(sample: SampleInfo): void {
  audioStore.setSample(sample)
  const filename = sample.local_path.split('/').pop() || sample.local_path
  audioStore.originalUrl = `/data/${filename}`
  // Fetch ground truth transcription if not cached
  if (!sample.transcription) {
    transcribeSample(sample.name).then(text => {
      sample.transcription = text
      audioStore.selectedSample = { ...sample, transcription: text }
    }).catch(() => {})
  }
}

function handlePlay(sample: SampleInfo): void {
  audioStore.setSample(sample)
  const filename = sample.local_path.split('/').pop() || sample.local_path
  audioStore.originalUrl = `/data/${filename}`
  if (!sample.transcription) {
    transcribeSample(sample.name).then(text => {
      sample.transcription = text
      audioStore.selectedSample = { ...sample, transcription: text }
    }).catch(() => {})
  }
}

onMounted(() => { loadSamples() })
</script>
