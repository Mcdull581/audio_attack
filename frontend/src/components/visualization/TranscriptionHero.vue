<template>
  <div class="bg-dark-800 px-4 py-3 flex items-center gap-6">
    <!-- Left: Current (noisy) transcription -->
    <div class="flex-1 min-w-0">
      <div class="text-[10px] font-mono text-gray-500 uppercase tracking-wider mb-1">
        Live Recognition
      </div>
      <div
        class="text-xl font-mono font-bold truncate transition-colors duration-300"
        :class="transcriptionColor"
      >
        <span v-if="status === 'running' || status === 'completed'" class="animate-pulse">
          {{ currentTranscription || '...' }}
        </span>
        <span v-else class="text-gray-600">
          waiting for attack...
        </span>
      </div>
    </div>

    <!-- Center: Arrow -->
    <div class="flex-shrink-0">
      <span class="text-2xl font-mono text-gray-500">&rarr;</span>
    </div>

    <!-- Right: Target phrase -->
    <div class="flex-1 min-w-0">
      <div class="text-[10px] font-mono text-gray-500 uppercase tracking-wider mb-1">
        Target Phrase
      </div>
      <div class="text-xl font-mono font-bold text-accent-cyan truncate">
        {{ targetTranscription || '—' }}
      </div>
    </div>

    <!-- SNR Badge -->
    <div v-if="status === 'running' || status === 'completed'" class="flex-shrink-0">
      <div class="text-[10px] font-mono text-gray-500 uppercase tracking-wider mb-1 text-center">
        SNR
      </div>
      <div
        class="px-3 py-1 rounded font-mono text-sm font-bold text-center"
        :class="snrBadgeClass"
      >
        {{ snrDb.toFixed(1) }} dB
        <div class="text-[9px] font-normal opacity-70">{{ snrLabel }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useAttackStore } from '@/stores/attackStore'

const attackStore = useAttackStore()
const { status, currentTranscription, targetTranscription, snrDb } = storeToRefs(attackStore)

// ── Transcription color: red while not matching, emerald when matched ──
const transcriptionColor = computed(() => {
  if (!currentTranscription.value) return 'text-gray-600'
  const cur = currentTranscription.value.trim().toLowerCase()
  const tgt = targetTranscription.value.trim().toLowerCase()
  if (!tgt) return 'text-orange-400'
  if (cur === tgt) return 'text-accent-emerald'
  // Show progress: count matching chars
  let matches = 0
  for (let i = 0; i < Math.min(cur.length, tgt.length); i++) {
    if (cur[i] === tgt[i]) matches++
  }
  const ratio = matches / Math.max(tgt.length, 1)
  if (ratio > 0.8) return 'text-yellow-400'
  if (ratio > 0.4) return 'text-orange-400'
  return 'text-red-400'
})

// ── SNR badge ──────────────────────────────────────────────────────────
const snrBadgeClass = computed(() => {
  const v = snrDb.value
  if (v > 20) return 'bg-accent-emerald/20 border border-accent-emerald/40 text-accent-emerald'
  if (v > 10) return 'bg-yellow-400/20 border border-yellow-400/40 text-yellow-400'
  return 'bg-red-400/20 border border-red-400/40 text-red-400'
})

const snrLabel = computed(() => {
  const v = snrDb.value
  if (v > 20) return 'High Stealth'
  if (v > 10) return 'Noticeable'
  return 'Distorted'
})
</script>
