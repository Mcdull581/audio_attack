<template>
  <div class="bg-dark-800 rounded-lg border border-dark-600 p-4">
    <!-- Title -->
    <span class="text-xs font-semibold text-gray-300 uppercase tracking-wider">
      Spectrogram Comparison
    </span>

    <!-- Original -->
    <div class="mt-3">
      <span class="text-[10px] font-mono text-gray-400 uppercase tracking-wider">
        Original Spectrogram
      </span>
      <canvas
        ref="originalCanvasRef"
        class="w-full rounded-sm mt-1 block"
        height="150"
      ></canvas>
    </div>

    <!-- Adversarial -->
    <div class="mt-2">
      <span class="text-[10px] font-mono text-red-400 uppercase tracking-wider">
        Adversarial Spectrogram
      </span>
      <canvas
        ref="adversarialCanvasRef"
        class="w-full rounded-sm mt-1 block"
        height="150"
      ></canvas>
    </div>

    <!-- Fallback -->
    <p
      v-if="!hasAudio"
      class="text-[11px] font-mono text-gray-500 text-center mt-2"
    >
      Spectrogram requires loaded audio
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useAudioStore } from '@/stores/audioStore'

const audioStore = useAudioStore()

// ── Refs ─────────────────────────────────────────────────────────────────

const originalCanvasRef = ref<HTMLCanvasElement | null>(null)
const adversarialCanvasRef = ref<HTMLCanvasElement | null>(null)

let resizeObserver: ResizeObserver | null = null

// ── Derived state ────────────────────────────────────────────────────────

const hasAudio = computed(() => !!audioStore.originalUrl && !!audioStore.adversarialUrl)

// ── Color map for spectrogram heatmap ────────────────────────────────────
// Dark-blue (low) → cyan → yellow → red (high)

function heatmapColor(value: number): string {
  // value is 0..255 (from byte frequency data)
  const t = Math.min(1, Math.max(0, value / 255))
  if (t < 0.33) {
    // Dark blue → cyan
    const s = t / 0.33
    const r = Math.round(30 + s * 0)
    const g = Math.round(58 + s * (182 - 58))
    const b = Math.round(95 + s * (212 - 95))
    return `rgb(${r},${g},${b})`
  } else if (t < 0.66) {
    // Cyan → yellow
    const s = (t - 0.33) / 0.33
    const r = Math.round(0 + s * 234)
    const g = Math.round(182 + s * (179 - 182))
    const b = Math.round(212 + s * (8 - 212))
    return `rgb(${r},${g},${b})`
  } else {
    // Yellow → red
    const s = (t - 0.66) / 0.34
    const r = Math.round(234 + s * (239 - 234))
    const g = Math.round(179 + s * (68 - 179))
    const b = Math.round(8 + s * (68 - 8))
    return `rgb(${r},${g},${b})`
  }
}

// ── Draw placeholder (grid + text) ───────────────────────────────────────

function drawPlaceholder(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
): void {
  // Background
  ctx.fillStyle = '#0a0a0f'
  ctx.fillRect(0, 0, width, height)

  // Grid
  ctx.strokeStyle = '#1a1a2e'
  ctx.lineWidth = 0.5

  const gridSpacingX = 20
  const gridSpacingY = 15
  for (let x = gridSpacingX; x < width; x += gridSpacingX) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
    ctx.stroke()
  }
  for (let y = gridSpacingY; y < height; y += gridSpacingY) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
    ctx.stroke()
  }

  // Border accent
  ctx.strokeStyle = '#25253d'
  ctx.lineWidth = 1
  ctx.strokeRect(0.5, 0.5, width - 1, height - 1)

  // Placeholder text
  ctx.fillStyle = '#6b7280'
  ctx.font = '11px "JetBrains Mono", monospace'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('Spectrogram — connect audio to generate', width / 2, height / 2)
}

// ── Draw spectrogram from frequency data ─────────────────────────────────

function drawSpectrogram(
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  frequencyData: Uint8Array,
): void {
  const barCount = frequencyData.length
  const barWidth = Math.max(1, width / barCount)

  // Background
  ctx.fillStyle = '#0a0a0f'
  ctx.fillRect(0, 0, width, height)

  for (let i = 0; i < barCount; i++) {
    const value = frequencyData[i]
    const barHeight = (value / 255) * height
    const x = i * barWidth
    const y = height - barHeight

    ctx.fillStyle = heatmapColor(value)
    ctx.fillRect(x, y, barWidth, barHeight)
  }

  // Subtle horizontal grid
  ctx.strokeStyle = 'rgba(26, 26, 46, 0.4)'
  ctx.lineWidth = 0.5
  const hzSteps = 5
  for (let i = 1; i < hzSteps; i++) {
    const yLine = (height / hzSteps) * i
    ctx.beginPath()
    ctx.moveTo(0, yLine)
    ctx.lineTo(width, yLine)
    ctx.stroke()
  }

  // Border
  ctx.strokeStyle = '#25253d'
  ctx.lineWidth = 1
  ctx.strokeRect(0.5, 0.5, width - 1, height - 1)
}

// ── Render canvas at current size ────────────────────────────────────────

function renderCanvas(
  canvas: HTMLCanvasElement,
  frequencyData: Uint8Array | null,
): void {
  const dpr = window.devicePixelRatio || 1
  const rect = canvas.getBoundingClientRect()
  const displayWidth = rect.width
  const displayHeight = rect.height || 150

  canvas.width = displayWidth * dpr
  canvas.height = displayHeight * dpr

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.scale(dpr, dpr)

  if (frequencyData) {
    drawSpectrogram(ctx, displayWidth, displayHeight, frequencyData)
  } else {
    drawPlaceholder(ctx, displayWidth, displayHeight)
  }
}

// ── Fetch audio and compute frequency data ───────────────────────────────

async function loadAndDrawSpectrogram(
  canvas: HTMLCanvasElement,
  url: string,
): Promise<void> {
  try {
    const response = await fetch(url)
    const arrayBuffer = await response.arrayBuffer()

    const audioCtx = new AudioContext()
    const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer)

    // Create offline analyser-like processing
    const offlineCtx = new OfflineAudioContext(
      1,
      audioBuffer.length,
      audioBuffer.sampleRate,
    )
    const source = offlineCtx.createBufferSource()
    source.buffer = audioBuffer

    const analyser = offlineCtx.createAnalyser()
    analyser.fftSize = 256
    analyser.smoothingTimeConstant = 0
    source.connect(analyser)
    analyser.connect(offlineCtx.destination)

    source.start(0)
    await offlineCtx.startRendering()

    const freqData = new Uint8Array(analyser.frequencyBinCount)
    analyser.getByteFrequencyData(freqData)

    renderCanvas(canvas, freqData)
    audioCtx.close()
  } catch {
    // Fallback to placeholder on any error
    renderCanvas(canvas, null)
  }
}

// ── Draw all canvases ────────────────────────────────────────────────────

function drawAllCanvases(): void {
  if (originalCanvasRef.value) {
    renderCanvas(originalCanvasRef.value, null)
  }
  if (adversarialCanvasRef.value) {
    renderCanvas(adversarialCanvasRef.value, null)
  }
}

// ── Lifecycle ────────────────────────────────────────────────────────────

onMounted(() => {
  drawAllCanvases()

  // Observe container for responsive resizing
  const container = originalCanvasRef.value?.parentElement?.parentElement
  if (container) {
    resizeObserver = new ResizeObserver(() => {
      drawAllCanvases()
    })
    resizeObserver.observe(container)
  }

  // If audio URLs are already set, load them
  if (audioStore.originalUrl && originalCanvasRef.value) {
    loadAndDrawSpectrogram(originalCanvasRef.value, audioStore.originalUrl)
  }
  if (audioStore.adversarialUrl && adversarialCanvasRef.value) {
    loadAndDrawSpectrogram(adversarialCanvasRef.value, audioStore.adversarialUrl)
  }
})

// ── Watch audio URLs for changes ─────────────────────────────────────────

watch(
  () => audioStore.originalUrl,
  (url) => {
    if (url && originalCanvasRef.value) {
      loadAndDrawSpectrogram(originalCanvasRef.value, url)
    } else if (originalCanvasRef.value) {
      renderCanvas(originalCanvasRef.value, null)
    }
  },
)

watch(
  () => audioStore.adversarialUrl,
  (url) => {
    if (url && adversarialCanvasRef.value) {
      loadAndDrawSpectrogram(adversarialCanvasRef.value, url)
    } else if (adversarialCanvasRef.value) {
      renderCanvas(adversarialCanvasRef.value, null)
    }
  },
)

// ── Cleanup ──────────────────────────────────────────────────────────────

onUnmounted(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
})
</script>
