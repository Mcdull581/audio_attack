<template>
  <div class="flex flex-col">
    <span class="text-xs text-gray-500 font-mono uppercase tracking-wide">
      {{ label }}
    </span>
    <span :class="['text-lg font-mono font-semibold', colorClass]">
      {{ value }}<span v-if="unit" class="text-sm font-normal text-gray-400 ml-0.5">{{ unit }}</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  label: string
  value: string | number
  unit?: string
  color?: 'cyan' | 'emerald' | 'red' | 'yellow'
}>(), {
  color: 'cyan',
})

const colorMap: Record<string, string> = {
  cyan: 'text-accent-cyan',
  emerald: 'text-accent-emerald',
  red: 'text-red-400',
  yellow: 'text-yellow-400',
}

const colorClass = computed(() => colorMap[props.color] ?? colorMap.cyan)
</script>
