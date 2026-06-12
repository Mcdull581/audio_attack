<template>
  <div class="bg-dark-800 rounded-lg border border-dark-600 p-4">
    <!-- Title -->
    <span class="text-xs font-semibold text-gray-300 uppercase tracking-wider">
      Loss Curve
    </span>

    <!-- Empty state -->
    <div
      v-if="!hasData"
      class="flex flex-col items-center justify-center gap-2 text-gray-500"
      style="height: 350px"
    >
      <svg
        class="w-8 h-8 opacity-40"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
      >
        <polyline
          points="3 17 9 11 13 15 21 7"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      <span class="text-sm font-mono">Waiting for attack data...</span>
    </div>

    <!-- Chart container -->
    <div
      ref="chartContainerRef"
      v-show="hasData"
      class="w-full"
      style="height: 350px"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { useAttackStore } from '@/stores/attackStore'
import type { LossDataPoint } from '@/types/attack'

const attackStore = useAttackStore()

// ── Refs ─────────────────────────────────────────────────────────────────

const chartContainerRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
let lastRenderedIndex = 0

// ── Derived state ────────────────────────────────────────────────────────

const hasData = computed(() => attackStore.lossHistory.length > 0)

// ── Chart options factory ────────────────────────────────────────────────

function buildBaseOption(): echarts.EChartOption {
  return {
    backgroundColor: 'transparent',
    textStyle: { color: '#9ca3af' },
    grid: { top: 40, right: 60, bottom: 40, left: 60 },
    xAxis: {
      type: 'value',
      name: 'Iteration',
      nameTextStyle: { color: '#6b7280', fontSize: 11 },
      axisLine: { lineStyle: { color: '#25253d' } },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#1a1a2e' } },
      min: 0,
    },
    yAxis: [
      {
        type: 'value',
        name: 'Loss',
        nameTextStyle: { color: '#6b7280', fontSize: 11 },
        axisLine: { lineStyle: { color: '#25253d' } },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: '#1a1a2e' } },
      },
      {
        type: 'value',
        name: 'SNR (dB)',
        nameTextStyle: { color: '#6b7280', fontSize: 11 },
        axisLine: { lineStyle: { color: '#25253d' } },
        axisTick: { show: false },
        splitLine: { show: false },
      },
    ],
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#12121a',
      borderColor: '#25253d',
      textStyle: { color: '#9ca3af', fontSize: 12 },
      formatter(params: unknown): string {
        const items = params as Array<{
          seriesName: string
          value: [number, number]
          color: string
          marker: string
        }>
        if (!items || items.length === 0) return ''
        const iter = items[0].value[0]
        let html = `<div class="font-mono text-xs">Iteration: <strong>${iter}</strong></div>`
        for (const item of items) {
          html += `<div>${item.marker} ${item.seriesName}: <strong>${item.value[1].toFixed(4)}</strong></div>`
        }
        return html
      },
    },
    legend: {
      top: 8,
      textStyle: { color: '#9ca3af', fontSize: 11 },
      data: ['CTC Loss', 'L2 Norm', 'SNR dB'],
    },
    series: [
      {
        name: 'CTC Loss',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#3b82f6', width: 1.5 },
        yAxisIndex: 0,
        data: [] as [number, number][],
      },
      {
        name: 'L2 Norm',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#f59e0b', width: 1.5 },
        yAxisIndex: 0,
        data: [] as [number, number][],
      },
      {
        name: 'SNR dB',
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color: '#10b981', width: 1.5, type: 'dashed' },
        itemStyle: { opacity: 0.7 },
        yAxisIndex: 1,
        data: [] as [number, number][],
      },
    ],
    animation: true,
    animationDuration: 200,
    animationEasing: 'linear',
  }
}

// ── Initialize chart ─────────────────────────────────────────────────────

function initChart(): void {
  if (!chartContainerRef.value) return
  chartInstance = echarts.init(chartContainerRef.value, 'dark')
  chartInstance.setOption(buildBaseOption())
  lastRenderedIndex = 0
}

// ── Append new data points ───────────────────────────────────────────────

function appendNewPoints(): void {
  if (!chartInstance) return
  const history = attackStore.lossHistory

  const ctcData: [number, number][] = []
  const l2Data: [number, number][] = []
  const snrData: [number, number][] = []
  for (const p of history) {
    ctcData.push([p.iteration, p.ctc_loss])
    l2Data.push([p.iteration, p.l2_loss])
    snrData.push([p.iteration, p.snr_db])
  }

  chartInstance.setOption({
    series: [
      { data: ctcData },
      { data: l2Data },
      { data: snrData },
    ],
    xAxis: { max: history.length > 0 ? history[history.length - 1].iteration : undefined },
  })
  lastRenderedIndex = history.length
}

// ── Handle resize ────────────────────────────────────────────────────────

function handleResize(): void {
  chartInstance?.resize()
}

let resizeObserver: ResizeObserver | null = null

// ── Lifecycle ────────────────────────────────────────────────────────────

onMounted(() => {
  initChart()

  if (chartContainerRef.value) {
    resizeObserver = new ResizeObserver(() => {
      handleResize()
    })
    resizeObserver.observe(chartContainerRef.value)
  }

  window.addEventListener('resize', handleResize)
})

// ── Watch for new loss data ──────────────────────────────────────────────

watch(
  () => attackStore.lossHistory.length,
  () => {
    appendNewPoints()
  },
)

// ── Cleanup ──────────────────────────────────────────────────────────────

onUnmounted(() => {
  chartInstance?.dispose()
  chartInstance = null
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('resize', handleResize)
})
</script>
