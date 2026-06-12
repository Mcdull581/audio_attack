<template>
  <div class="bg-dark-800 rounded-lg border border-dark-600 overflow-hidden">
    <div
      v-if="title"
      class="px-4 py-3 border-b border-dark-600"
    >
      <h3 class="text-sm uppercase tracking-wider text-gray-400 font-mono">
        {{ title }}
      </h3>
    </div>
    <div :class="padding ? 'p-4' : ''">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  padding?: boolean
}>(), {
  padding: true,
})
</script>
