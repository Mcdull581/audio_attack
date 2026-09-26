<template>
  <div class="flex min-h-screen flex-col bg-dark-900 text-gray-200 md:h-screen md:flex-row">
    <!-- Left Sidebar -->
    <aside class="w-full max-h-[46vh] flex-shrink-0 bg-dark-800 border-b border-dark-600 flex flex-col overflow-hidden md:w-80 md:max-h-none md:border-b-0 md:border-r">
      <div class="flex-shrink-0 px-4 py-4 border-b border-dark-600">
        <h1 class="text-lg font-mono font-bold text-accent-cyan tracking-tight">
          ⚡ Audio Attack Lab
        </h1>
      </div>
      <div class="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        <SampleList />
        <AttackPanel />
      </div>
    </aside>

    <!-- Right Main Area -->
    <div class="flex min-h-[54vh] flex-1 flex-col min-w-0 overflow-hidden pb-10 md:min-h-0">
      <!-- Waveform View -->
      <div class="flex-shrink-0 border-b border-dark-600 bg-dark-900">
        <WaveformView />
      </div>

      <!-- Transcription Hero -->
      <div class="flex-shrink-0 border-b border-dark-600 bg-dark-900">
        <TranscriptionHero />
      </div>

      <!-- Loss Curve (h-72 max) -->
      <div class="h-72 flex-shrink-0 border-b border-dark-600 bg-dark-900 pb-2 mb-4 md:mb-12">
        <LossCurve />
      </div>

      <!-- Spectrogram -->
      <div class="flex-1 min-h-[360px] min-w-0 overflow-hidden bg-dark-900 mt-4 md:mt-8">
        <SpectrogramView />
      </div>
    </div>

    <StatusBar />
  </div>
</template>

<script setup lang="ts">
import SampleList from '@/components/dashboard/SampleList.vue'
import AttackPanel from '@/components/dashboard/AttackPanel.vue'
import WaveformView from '@/components/visualization/WaveformView.vue'
import TranscriptionHero from '@/components/visualization/TranscriptionHero.vue'
import LossCurve from '@/components/visualization/LossCurve.vue'
import SpectrogramView from '@/components/visualization/SpectrogramView.vue'
import StatusBar from '@/components/layout/StatusBar.vue'
</script>
