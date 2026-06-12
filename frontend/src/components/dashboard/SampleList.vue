<template>
  <div class="bg-dark-800 rounded-lg border border-dark-600 overflow-hidden">
    <!-- Header with preload -->
    <div class="px-4 py-3 border-b border-dark-600 flex items-center justify-between">
      <h3 class="text-sm uppercase tracking-wider text-gray-400 font-mono">
        Audio Samples
        <span
          v-if="samples.length > 0"
          class="ml-2 px-1.5 py-0.5 text-xs bg-dark-600 rounded text-gray-300"
        >
          {{ samples.length }}
        </span>
      </h3>
      <button
        class="text-xs text-accent-cyan hover:underline font-mono"
        :disabled="loading"
        @click="handlePreload"
      >
        {{ loading ? 'Loading...' : 'Preload Samples' }}
      </button>
    </div>

    <!-- Content area -->
    <div class="max-h-[300px] overflow-y-auto">
      <!-- Loading state -->
      <div v-if="loading" class="p-4 space-y-3">
        <div
          v-for="n in 3"
          :key="n"
          class="h-10 bg-dark-700 rounded animate-pulse"
        />
      </div>

      <!-- Empty state -->
      <div
        v-else-if="samples.length === 0"
        class="p-6 text-center"
      >
        <p class="text-sm text-gray-500 font-mono">
          No samples loaded. Click preload to fetch dataset.
        </p>
      </div>

      <!-- Sample list -->
      <template v-else>
        <button
          v-for="sample in samples"
          :key="sample.id"
          class="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors border-l-2 hover:bg-dark-700"
          :class="[
            selectedSample?.name === sample.name
              ? 'border-l-accent-cyan bg-dark-700'
              : 'border-l-transparent',
          ]"
          @click="handleSelect(sample)"
        >
          <!-- Play icon -->
          <span
            class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded bg-dark-600 text-accent-cyan text-xs cursor-pointer hover:bg-dark-700"
            @click.stop="handlePlay(sample)"
          >
            ▶
          </span>

          <!-- Name + transcription -->
          <div class="flex-1 min-w-0">
            <p class="text-sm font-mono text-gray-200 truncate">
              {{ sample.name }}
            </p>
            <p class="text-xs text-gray-400 truncate">
              {{ sample.transcription }}
            </p>
          </div>

          <!-- Duration badge -->
          <span class="flex-shrink-0 text-xs bg-dark-600 px-2 py-0.5 rounded font-mono text-gray-300">
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
import { fetchSamples, preloadSamples } from '@/utils/api'
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
  try {
    const res = await fetchSamples()
    samples.value = res.samples
  } catch {
    // keep existing list on failure
  } finally {
    loading.value = false
  }
}

async function handlePreload(): Promise<void> {
  loading.value = true
  try {
    await preloadSamples()
    await loadSamples()
  } catch {
    // swallow
  } finally {
    loading.value = false
  }
}

function handleSelect(sample: SampleInfo): void {
  audioStore.setSample(sample)
}

function handlePlay(sample: SampleInfo): void {
  audioStore.setSample(sample)
}

onMounted(() => {
  loadSamples()
})
</script>
