<template>
  <div class="flex h-screen bg-dark-900 text-gray-200">
    <!-- Left Sidebar -->
    <aside class="w-80 flex-shrink-0 bg-dark-800 border-r border-dark-600 flex flex-col overflow-hidden">
      <!-- Logo header -->
      <div class="flex-shrink-0 px-4 py-4 border-b border-dark-600">
        <h1 class="text-lg font-mono font-bold text-accent-cyan tracking-tight">
          ⚡ Audio Attack Lab
        </h1>
      </div>

      <!-- Scrollable sidebar content -->
      <div class="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        <SampleList />
        <AttackPanel />
      </div>
    </aside>

    <!-- Right Main Area -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden pb-10">
      <!-- Waveform View -->
      <div class="flex-shrink-0 h-[200px] border-b border-dark-600 bg-dark-900">
        <WaveformView />
      </div>

      <!-- Loss Curve (grows to fill) -->
      <div class="flex-1 min-h-0 border-b border-dark-600 bg-dark-900">
        <LossCurve />
      </div>

      <!-- Spectrogram View -->
      <div class="flex-shrink-0 h-[200px] bg-dark-900">
        <SpectrogramView />
      </div>
    </div>

    <!-- Status Bar (fixed at bottom) -->
    <StatusBar />
  </div>
</template>

<script setup lang="ts">
import SampleList from '@/components/dashboard/SampleList.vue'
import AttackPanel from '@/components/dashboard/AttackPanel.vue'
import WaveformView from '@/components/visualization/WaveformView.vue'
import LossCurve from '@/components/visualization/LossCurve.vue'
import SpectrogramView from '@/components/visualization/SpectrogramView.vue'
import StatusBar from '@/components/layout/StatusBar.vue'
</script>
