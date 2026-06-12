<template>
  <div class="fixed bottom-0 left-0 right-0 h-10 bg-dark-800 border-t border-dark-600 flex items-center px-4 z-50">
    <!-- Left: Attack status -->
    <div class="flex items-center gap-2 min-w-0 flex-shrink-0">
      <span
        class="w-2 h-2 rounded-full flex-shrink-0"
        :class="statusDotClass"
      />
      <span class="text-xs font-mono text-gray-400 truncate">
        {{ statusLabel }}
      </span>
    </div>

    <!-- Center: Iteration / SNR -->
    <div class="flex-1 flex items-center justify-center gap-4 min-w-0 mx-4">
      <template v-if="status !== 'idle'">
        <span class="text-xs font-mono text-gray-400 whitespace-nowrap">
          Iter: <span class="text-accent-cyan">{{ currentIteration }}</span>/<span class="text-gray-500">{{ maxIterations }}</span>
        </span>
        <span class="text-xs font-mono text-gray-400 whitespace-nowrap">
          SNR: <span class="text-accent-cyan">{{ snrDb.toFixed(1) }}</span> dB
        </span>
      </template>
      <template v-else>
        <span class="text-xs font-mono text-gray-500">
          Ready — configure attack to begin
        </span>
      </template>
    </div>

    <!-- Right: Transcription -->
    <div class="flex items-center gap-3 flex-shrink-0 min-w-0">
      <template v-if="status === 'running' || status === 'completed'">
        <span class="text-xs font-mono text-accent-emerald truncate max-w-[160px]">
          {{ currentTranscription || '---' }}
        </span>
        <span class="text-xs text-gray-500 font-mono flex-shrink-0">&rarr;</span>
        <span class="text-xs font-mono text-gray-300 truncate max-w-[160px]">
          {{ targetTranscription }}
        </span>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useAttackStore } from '@/stores/attackStore'

const attackStore = useAttackStore()
const {
  status,
  currentIteration,
  snrDb,
  currentTranscription,
  targetTranscription,
} = storeToRefs(attackStore)

const maxIterations = computed(() => attackStore.config?.max_iterations ?? 0)

const statusDotClass = computed(() => {
  switch (status.value) {
    case 'running': return 'bg-green-500'
    case 'queued': return 'bg-yellow-400'
    case 'completed': return 'bg-blue-400'
    case 'failed': return 'bg-red-400'
    default: return 'bg-gray-600'
  }
})

const statusLabel = computed(() => {
  switch (status.value) {
    case 'running': return 'Running'
    case 'queued': return 'Queued'
    case 'completed': return 'Completed'
    case 'failed': return 'Failed'
    default: return 'Idle'
  }
})
</script>
