import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'wavesurfer-browser-worker-guard',
      enforce: 'pre',
      transform(code, id) {
        if (id.includes('wavesurfer.js/dist/plugins/spectrogram.esm.js')) {
          // The distributed plugin probes Node's worker_threads module even
          // in browser builds. Rename only the probe target; the browser
          // implementation uses the native Web Worker path when enabled.
          return {
            code: code.replaceAll('"worker_threads"', '"__browser_worker_threads__"'),
            map: null,
          }
        }
        return null
      },
    },
  ],
  optimizeDeps: {
    exclude: ['wavesurfer.js/dist/plugins/spectrogram.esm.js'],
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:28000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:28000',
        ws: true,
      },
      '/data': {
        target: 'http://localhost:28000',
        changeOrigin: true,
      },
    },
  },
})
