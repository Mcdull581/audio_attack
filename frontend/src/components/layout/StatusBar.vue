<template>
  <div class="fixed bottom-0 left-0 right-0 h-10 bg-dark-800 border-t border-dark-600 flex items-center px-4 z-50">
    <!-- Left: Attack status -->
    <div class="flex items-center gap-2 min-w-0">
      <span class="w-2 h-2 rounded-full flex-shrink-0" :class="statusDotClass" />
      <span class="text-xs font-mono text-gray-400">{{ statusLabel }}</span>
    </div>

    <!-- Center: Iteration progress -->
    <div class="flex-1 flex items-center justify-center gap-4 min-w-0 mx-4">
      <template v-if="status === 'running'">
        <span class="text-xs font-mono text-gray-400">
          Iter: <span class="text-accent-cyan">{{ currentIteration }}</span>/<span class="text-gray-500">{{ maxIterations }}</span>
        </span>
        <div class="w-24 h-1.5 bg-dark-700 rounded-full overflow-hidden">
          <div
            class="h-full bg-accent-cyan rounded-full transition-all duration-300"
            :style="{ width: progressPercent + '%' }"
          ></div>
        </div>
        <span class="text-xs font-mono text-gray-500">{{ progressPercent }}%</span>
      </template>
      <template v-else>
        <span class="text-xs font-mono text-gray-600">
          Ready — select sample and configure attack
        </span>
      </template>
    </div>

    <!-- Right: version -->
    <span class="text-[10px] font-mono text-gray-600">v0.1.0</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useAttackStore } from '@/stores/attackStore'

const attackStore = useAttackStore()
const { status, currentIteration } = storeToRefs(attackStore)

const maxIterations = computed(() => attackStore.config?.max_iterations ?? 0)

const progressPercent = computed(() => {
  if (!attackStore.config || attackStore.config.max_iterations <= 0) return 0
  return Math.min(100, Math.round((currentIteration.value / attackStore.config.max_iterations) * 100))
})

const statusDotClass = computed(() => {
  switch (status.value) {
    case 'running': return 'bg-green-500 animate-pulse'
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
