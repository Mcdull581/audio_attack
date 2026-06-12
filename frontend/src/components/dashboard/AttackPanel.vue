<template>
  <div class="bg-dark-800 rounded-lg border border-dark-600 p-4">
    <h3 class="text-sm uppercase tracking-wider text-gray-400 font-mono mb-4">
      Attack Configuration
    </h3>

    <!-- Target Phrase -->
    <div class="mb-4">
      <label class="block text-xs text-gray-500 font-mono mb-1.5">
        Target Phrase
      </label>
      <input
        v-model="targetPhrase"
        type="text"
        placeholder="enter target phrase..."
        :disabled="isRunning"
        class="w-full bg-dark-700 border border-dark-600 rounded px-3 py-2 text-cyan-400 font-mono text-sm placeholder-gray-500 focus:outline-none focus:border-accent-cyan disabled:opacity-50"
      />
    </div>

    <!-- Selected Sample -->
    <div class="mb-4">
      <label class="block text-xs text-gray-500 font-mono mb-1.5">
        Audio Sample
      </label>
      <div
        class="w-full bg-dark-700 border border-dark-600 rounded px-3 py-2 text-sm font-mono"
        :class="selectedSample ? 'text-gray-200' : 'text-gray-500'"
      >
        <template v-if="selectedSample">
          <span class="text-accent-cyan">{{ selectedSample.name }}</span>
          <span class="text-gray-500 ml-2">
            {{ formatDuration(selectedSample.duration_sec) }}
          </span>
        </template>
        <template v-else>
          Select a sample from the list
        </template>
      </div>
    </div>

    <!-- Epsilon -->
    <div class="mb-4">
      <div class="flex items-center justify-between mb-1.5">
        <label class="text-xs text-gray-500 font-mono">Epsilon (&epsilon;)</label>
        <input
          v-model.number="epsilon"
          type="number"
          :min="0.001"
          :max="0.1"
          :step="0.001"
          :disabled="isRunning"
          class="w-20 bg-dark-700 border border-dark-600 rounded px-2 py-0.5 text-xs text-accent-cyan font-mono text-right focus:outline-none focus:border-accent-cyan disabled:opacity-50"
        />
      </div>
      <input
        v-model.number="epsilon"
        type="range"
        :min="0.001"
        :max="0.1"
        :step="0.001"
        :disabled="isRunning"
        class="w-full h-1.5 bg-dark-700 rounded-lg appearance-none cursor-pointer accent-accent-cyan disabled:opacity-50"
      />
      <div class="flex justify-between text-[10px] text-gray-500 font-mono mt-0.5">
        <span>0.001</span>
        <span>0.1</span>
      </div>
    </div>

    <!-- Max Iterations -->
    <div class="mb-4">
      <label class="block text-xs text-gray-500 font-mono mb-1.5">
        Max Iterations
      </label>
      <input
        v-model.number="maxIterations"
        type="number"
        :min="100"
        :max="10000"
        :step="100"
        :disabled="isRunning"
        class="w-full bg-dark-700 border border-dark-600 rounded px-3 py-2 text-sm text-gray-200 font-mono focus:outline-none focus:border-accent-cyan disabled:opacity-50"
      />
    </div>

    <!-- Lambda L2 -->
    <div class="mb-5">
      <label class="block text-xs text-gray-500 font-mono mb-1.5">
        Lambda L2 (&lambda;)
      </label>
      <input
        v-model.number="lambdaL2"
        type="number"
        :min="0.001"
        :max="10"
        :step="0.01"
        :disabled="isRunning"
        class="w-full bg-dark-700 border border-dark-600 rounded px-3 py-2 text-sm text-gray-200 font-mono focus:outline-none focus:border-accent-cyan disabled:opacity-50"
      />
    </div>

    <!-- Action area -->
    <div>
      <!-- Idle: Start button -->
      <button
        v-if="status === 'idle' || status === 'failed'"
        class="w-full bg-accent-cyan hover:bg-cyan-500 text-dark-900 font-bold py-3 rounded font-mono text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="!canStart"
        @click="handleStart"
      >
        Start Attack
      </button>

      <!-- Running -->
      <div
        v-else-if="status === 'running'"
        class="flex items-center justify-center gap-2 py-3 text-accent-cyan font-mono text-sm"
      >
        <span class="inline-block w-4 h-4 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
        Attack Running...
      </div>

      <!-- Queued -->
      <div
        v-else-if="status === 'queued'"
        class="flex items-center justify-center gap-2 py-3 text-yellow-400 font-mono text-sm"
      >
        <span class="inline-block w-4 h-4 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
        Queued...
      </div>

      <!-- Completed -->
      <div v-else-if="status === 'completed'">
        <div
          class="mb-3 px-3 py-2 rounded text-sm font-mono"
          :class="attackSucceeded ? 'bg-accent-emerald/10 border border-accent-emerald/30 text-accent-emerald' : 'bg-red-400/10 border border-red-400/30 text-red-400'"
        >
          {{ attackSucceeded ? 'Attack succeeded! Transcription matched target.' : 'Attack finished but did not fully converge.' }}
        </div>
        <div class="flex gap-2">
          <button
            class="flex-1 bg-dark-700 hover:bg-dark-600 border border-dark-600 text-gray-200 font-mono text-sm py-2 rounded transition-colors"
            @click="handleReset"
          >
            New Attack
          </button>
          <button
            class="flex-1 bg-accent-cyan hover:bg-cyan-500 text-dark-900 font-mono font-bold text-sm py-2 rounded transition-colors"
            @click="handleDownload"
          >
            Download Results
          </button>
        </div>
      </div>
    </div>

    <!-- Error banner -->
    <div
      v-if="error"
      class="mt-3 px-3 py-2 rounded bg-red-400/10 border border-red-400/30 text-red-400 text-xs font-mono"
    >
      {{ error }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useAttackStore } from '@/stores/attackStore'
import { useAudioStore } from '@/stores/audioStore'
import { useAttack } from '@/composables/useAttack'

const attackStore = useAttackStore()
const audioStore = useAudioStore()
const { startAttack } = useAttack()

const { status, error } = storeToRefs(attackStore)

const { selectedSample, adversarialUrl } = storeToRefs(audioStore)

// Local form state — initialised from store config or defaults
const targetPhrase = ref(attackStore.config?.target_phrase ?? '')
const epsilon = ref(attackStore.config?.epsilon ?? 0.01)
const maxIterations = ref(attackStore.config?.max_iterations ?? 1000)
const lambdaL2 = ref(attackStore.config?.lambda_l2 ?? 0.1)

const isRunning = computed(() => status.value === 'running' || status.value === 'queued')

const canStart = computed(() =>
  targetPhrase.value.trim().length > 0 &&
  selectedSample.value !== null &&
  !isRunning.value,
)

const attackSucceeded = computed(() =>
  attackStore.isComplete &&
  attackStore.currentTranscription.trim().toLowerCase() === (attackStore.config?.target_phrase ?? '').trim().toLowerCase(),
)

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function handleStart(): void {
  if (!canStart.value) return

  startAttack(
    selectedSample.value!.name,
    targetPhrase.value,
    epsilon.value,
    maxIterations.value,
    lambdaL2.value,
  )
}

function handleReset(): void {
  attackStore.reset()
}

function handleDownload(): void {
  if (adversarialUrl.value) {
    window.open(adversarialUrl.value, '_blank')
  }
}
</script>
